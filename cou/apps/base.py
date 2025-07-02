# Copyright 2023 Canonical Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Base application class."""
from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

import yaml

from cou.exceptions import (
    ApplicationError,
    HaltUpgradePlanGeneration,
    MismatchedOpenStackVersions,
)
from cou.steps import (
    ApplicationUpgradePlan,
    PostUpgradeStep,
    PreUpgradeStep,
    UnitUpgradeStep,
    UpgradeStep,
)
from cou.utils.app_utils import upgrade_packages
from cou.utils.juju_utils import Application, Unit
from cou.utils.openstack import (
    DISTRO_TO_OPENSTACK_MAPPING,
    OpenStackCodenameLookup,
    OpenStackRelease,
)

logger = logging.getLogger(__name__)

STANDARD_IDLE_TIMEOUT: int = int(
    os.environ.get("COU_STANDARD_IDLE_TIMEOUT", 5 * 60)
)  # default of 5 min
LONG_IDLE_TIMEOUT: int = int(os.environ.get("COU_LONG_IDLE_TIMEOUT", 40 * 60))  # default of 40 min
ORIGIN_SETTINGS = ("openstack-origin", "source")
REQUIRED_SETTINGS = ("enable-auto-restarts", "action-managed-upgrade", *ORIGIN_SETTINGS)
LATEST_STABLE = {"stable", "latest/stable"}


@dataclass(frozen=True)
class OpenStackApplication(Application):
    """Representation of a charmed OpenStack application in the deployment.

    :raises ApplicationError: When there are no compatible OpenStack release for the
                              workload version.
    :raises MismatchedOpenStackVersions: When units part of this application are running mismatched
                                         OpenStack versions.
    """

    packages_to_hold: Optional[list] = field(default=None, init=False)
    charm_refresh_timeout: int = field(default=STANDARD_IDLE_TIMEOUT, init=False)
    wait_timeout: int = field(default=STANDARD_IDLE_TIMEOUT, init=False)
    wait_for_model: bool = field(default=False, init=False)  # waiting only for application itself
    # OpenStack apps rely on the workload version of the packages to evaluate current OpenStack
    # release
    based_on_channel = False
    # multiple_channels set to False means that the charm supports only one channel for
    # an OpenStack release
    multiple_channels = False

    def __hash__(self) -> int:
        """Hash magic method for Application.

        :return: Unique hash identifier for Application object.
        :rtype: int
        """
        return hash(f"{self.name}({self.charm})")

    def __eq__(self, other: Any) -> bool:
        """Equal magic method for Application.

        :param other: Application object to compare.
        :type other: Any
        :return: True if equal False if different.
        :rtype: bool
        """
        if not isinstance(other, OpenStackApplication):
            return NotImplemented

        return other.name == self.name and other.charm == self.charm

    def __str__(self) -> str:
        """Dump as string.

        :return: Summary representation of an Application.
        :rtype: str
        """
        summary = {
            self.name: {
                "model_name": self.model.name,
                "can_upgrade_to": self.can_upgrade_to,
                "charm": self.charm,
                "channel": self.channel,
                # Note (rgildein): sanitized the config
                "config": {
                    key: self.config[key] for key in self.config if key in REQUIRED_SETTINGS
                },
                "origin": self.origin,
                "series": self.series,
                "subordinate_to": self.subordinate_to,
                "workload_version": self.workload_version,
                "units": {
                    unit.name: {
                        "name": unit.name,
                        "machine": unit.machine.machine_id,
                        "workload_version": unit.workload_version,
                        "o7k_version": str(self.get_latest_o7k_version(unit)),
                        "subordinates": {
                            subordinate.name: {
                                "name": subordinate.name,
                                "charm": subordinate.charm,
                            }
                            for subordinate in unit.subordinates
                        },
                    }
                    for unit in self.units.values()
                },
                "machines": {
                    machine.machine_id: {
                        "id": machine.machine_id,
                        "apps_charms": machine.apps_charms,
                        "az": machine.az,
                    }
                    for machine in self.machines.values()
                },
            }
        }

        return yaml.dump(summary, sort_keys=False)

    def __repr__(self) -> str:
        """App representation.

        :return: Name of the application
        :rtype: str
        """
        return self.name

    @property
    def apt_source_codename(self) -> OpenStackRelease:
        """Identify the OpenStack release set on "openstack-origin" or "source" config.

        :raises ApplicationError: When origin setting or series are not valid.
        :return: OpenStackRelease object.
        :rtype: OpenStackRelease
        """
        if self.o7k_origin.startswith("cloud"):
            return self._extract_from_uca_source()

        # consider as "distro" if the application does not have source or is empty
        if self.o7k_origin in {"distro", ""}:
            # find the OpenStack release based on ubuntu series
            if self.series not in DISTRO_TO_OPENSTACK_MAPPING:
                raise ApplicationError(f"Series '{self.series}' is not supported by COU.")
            return OpenStackRelease(DISTRO_TO_OPENSTACK_MAPPING[self.series])

        # probably because user set a ppa or a url
        raise ApplicationError(
            f"'{self.name}' has an invalid '{self.origin_setting}': {self.o7k_origin}"
        )

    def _extract_from_uca_source(self) -> OpenStackRelease:
        """Extract the OpenStack release from Ubuntu Cloud Archive (UCA) sources.

        :raises ApplicationError: When origin setting is not valid.
        :return: OpenStackRelease object
        :rtype: OpenStackRelease
        """
        # Ex: "cloud:focal-victoria" will result in "victoria"
        try:
            _, o7k_origin_parsed = self.o7k_origin.rsplit("-", maxsplit=1)
            return OpenStackRelease(o7k_origin_parsed)
        except ValueError as exc:
            raise ApplicationError(
                f"'{self.name}' has an invalid '{self.origin_setting}': {self.o7k_origin}"
            ) from exc

    @property
    def channel_o7k_release(self) -> OpenStackRelease:
        """Identify the OpenStack release set in the charm channel.

        :return: OpenStackRelease object
        :rtype: OpenStackRelease
        """
        if self.need_crossgrade:
            logger.debug(
                "Cannot determine the OpenStack release of '%s' "
                "via its channel. Assuming Ussuri",
                self.name,
            )
            return OpenStackRelease("ussuri")
        return self._get_o7k_release_from_channel(self.channel)

    def _get_o7k_release_from_channel(self, channel: str) -> OpenStackRelease:
        """Get the OpenStack release from a channel.

        :param channel: channel to get the release
        :type channel: str
        :return: OpenStack release that the channel points to
        :rtype: OpenStackRelease
        """
        return OpenStackRelease(self._get_track_from_channel(channel))

    @property
    def o7k_release(self) -> OpenStackRelease:
        """Current OpenStack Release of the application.

        Applications that are colocated in a same machine will upgrade all the packages in the
        machine during an upgrade. This means that when upgrading a application X, the application
        Y colocated with it also upgrades its packages. To ensure to change the 'source' or
        'openstack-origin' and run all the upgrade steps necessary, it's necessary to include the
        OpenStack release set in the application configuration.
        :return: OpenStackRelease object
        :rtype: OpenStackRelease
        """
        if self.o7k_origin:
            return min(list(self.o7k_release_units.keys()) + [self.apt_source_codename])
        return min(self.o7k_release_units.keys())

    @property
    def o7k_origin(self) -> str:
        """Get application configuration for openstack-origin or source.

        :return: Configuration parameter of the charm to set OpenStack origin.
            e.g: cloud:focal-wallaby
        :rtype: str
        """
        if origin := self.origin_setting:
            return self.config[origin].get("value", "")

        return ""

    @property
    def origin_setting(self) -> Optional[str]:
        """Get charm origin setting name.

        :return: return name of charm origin setting, e.g. "source", "openstack-origin" or None
        :rtype: Optional[str]
        """
        for origin in ORIGIN_SETTINGS:
            if origin in self.config:
                return origin

        logger.debug("%s has no origin setting config", self.name)
        return None

    def expected_current_channel(self, target: OpenStackRelease) -> str:
        """Return the expected current channel.

        Expected current channel is the channel that the application is supposed to be using based
        on the current series, workload version and, by consequence, the OpenStack release
        identified.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: The expected current channel of the application. E.g: "ussuri/stable"
        :rtype: str
        """
        if self.need_crossgrade and self.based_on_channel:
            return f"{target.previous_release}/stable"
        return f"{self.o7k_release}/stable"

    @property
    def o7k_release_units(self) -> dict[OpenStackRelease, list[str]]:
        """Get the OpenStack release versions from the units.

        :return: OpenStack release versions from the units.
        :rtype: defaultdict[OpenStackRelease, list[str]]
        """
        o7k_versions = defaultdict(list)
        for unit in self.units.values():
            o7k_version = self.get_latest_o7k_version(unit)
            o7k_versions[o7k_version].append(unit.name)

        return dict(o7k_versions)

    @property
    def need_crossgrade(self) -> bool:
        """Check if need a charm crossgrade.

        :return: True if necessary, False otherwise
        :rtype: bool
        """
        return self.is_from_charm_store or self.channel in LATEST_STABLE

    def is_valid_track(self, charm_channel: str) -> bool:
        """Check if the channel track is valid.

        :param charm_channel: Charm channel. E.g: ussuri/stable
        :type charm_channel: str
        :return: True if valid, False otherwise
        :rtype: bool
        """
        try:
            OpenStackRelease(self._get_track_from_channel(charm_channel))
            return True
        except ValueError:
            return False

    def get_latest_o7k_version(self, unit: Unit) -> OpenStackRelease:
        """Get the latest compatible OpenStack release based on the unit workload version.

        :param unit: Unit
        :type unit: Unit
        :return: The latest compatible OpenStack release.
        :rtype: OpenStackRelease
        :raises ApplicationError: When there are no compatible OpenStack release for the
                                  workload version.
        """
        compatible_o7k_versions = OpenStackCodenameLookup.find_compatible_versions(
            self.charm, unit.workload_version
        )
        if not compatible_o7k_versions:
            raise ApplicationError(
                f"'{self.name}' with workload version {unit.workload_version} has no "
                "compatible OpenStack release."
            )

        return max(compatible_o7k_versions)

    @staticmethod
    def _get_track_from_channel(charm_channel: str) -> str:
        """Get the track from a given channel.

        :param charm_channel: Charm channel. E.g: ussuri/stable
        :type charm_channel: str
        :return: The track from a channel. E.g: ussuri
        :rtype: str
        """
        return charm_channel.split("/", maxsplit=1)[0]

    def target_channel(self, target: OpenStackRelease) -> str:
        """Return the appropriate channel for the passed OpenStack target.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: The next channel for the application. E.g: victoria/stable
        :rtype: str
        """
        return f"{target.track}/stable"

    def new_origin(self, target: OpenStackRelease) -> str:
        """Return the new openstack-origin or source configuration.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Repository from which to install.
        :rtype: str
        """
        return f"cloud:{self.series}-{target.codename}"

    async def _verify_workload_upgrade(self, target: OpenStackRelease, units: list[Unit]) -> None:
        """Check if an application has upgraded its workload version.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to check if got upgraded
        :type units: list[Unit]
        :raises ApplicationError: When the workload version of the charm doesn't upgrade.
        """
        # NOTE (gabrielcocenza) force the update-status hook on units
        # to update the workload version
        tasks = [self.model.update_status(unit.name) for unit in units]
        await asyncio.gather(*tasks)

        status = await self.model.get_status()
        app_status = status.applications.get(self.name)
        units_not_upgraded = []
        for unit in units:
            workload_version = app_status.units[unit.name].workload_version
            compatible_o7k_versions = OpenStackCodenameLookup.find_compatible_versions(
                self.charm, workload_version
            )
            if target not in compatible_o7k_versions:
                units_not_upgraded.append(unit.name)

        if units_not_upgraded:
            raise ApplicationError(
                f"Unit(s) '{', '.join(units_not_upgraded)}' did not complete the upgrade to "
                f"{target}. Some local processes may still be executing; you may try re-running "
                "COU in a few minutes."
            )

    def upgrade_plan_sanity_checks(self, target: OpenStackRelease) -> None:
        """Run sanity checks before generating upgrade plan.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :raises ApplicationError: When application is wrongly configured.
        :raises HaltUpgradePlanGeneration: When the application halt the upgrade plan generation.
        :raises MismatchedOpenStackVersions: When the units of the app are running
                                             different OpenStack versions.
        """
        self._check_channel()
        self._check_application_target(target)
        self._check_mismatched_versions()
        self._check_auto_restarts()
        logger.info(
            "%s application met all the necessary prerequisites to generate the upgrade plan",
            self.name,
        )

    def pre_upgrade_steps(
        self, target: OpenStackRelease, units: Optional[list[Unit]]
    ) -> list[PreUpgradeStep]:
        """Pre Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate upgrade plan
        :type units: Optional[list[Unit]]
        :return: List of pre upgrade steps.
        :rtype: list[PreUpgradeStep]
        """
        return [
            self._get_upgrade_current_release_packages_step(units),
            *self._get_refresh_charm_steps(target),
        ]

    def upgrade_steps(
        self, target: OpenStackRelease, units: Optional[list[Unit]], force: bool
    ) -> list[UpgradeStep]:
        """Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate upgrade steps
        :type units: Optional[list[Unit]]
        :param force: Whether the plan generation should be forced
        :type force: bool
        :return: List of upgrade steps.
        :rtype: list[UpgradeStep]
        """
        return [
            self._set_action_managed_upgrade(enable=bool(units)),
            *self._get_upgrade_charm_steps(target),
            self._get_change_install_repository_step(target),
            self._get_units_upgrade_steps(units, force),
        ]

    def post_upgrade_steps(
        self, target: OpenStackRelease, units: Optional[list[Unit]]
    ) -> list[PostUpgradeStep]:
        """Post Upgrade steps planning.

        Wait until the application reaches the idle state and then check the target workload.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate post upgrade plan
        :type units: Optional[list[Unit]]
        :return: List of post upgrade steps.
        :rtype: list[PostUpgradeStep]
        """
        return [
            self._get_wait_step(),
            self._get_reached_expected_target_step(target, units),
        ]

    def generate_upgrade_plan(
        self,
        target: OpenStackRelease,
        force: bool,
        units: Optional[list[Unit]] = None,
    ) -> ApplicationUpgradePlan:
        """Generate full upgrade plan for an Application.

        Units are passed if the application should be upgraded unit by unit.

        :param target: OpenStack codename to upgrade.
        :type target: OpenStackRelease
        :param force: Whether the plan generation should be forced
        :type force: bool
        :param units: Units to generate upgrade plan, defaults to None
        :type units: Optional[list[Unit]]
        :return: Full upgrade plan if the Application is able to generate it.
        :rtype: ApplicationUpgradePlan
        """
        self.upgrade_plan_sanity_checks(target)

        upgrade_plan = ApplicationUpgradePlan(f"Upgrade plan for '{self.name}' to '{target}'")
        upgrade_plan.add_steps(self.pre_upgrade_steps(target, units))
        upgrade_plan.add_steps(self.upgrade_steps(target, units, force))
        upgrade_plan.add_steps(self.post_upgrade_steps(target, units))

        return upgrade_plan

    def _get_unit_upgrade_steps(self, unit: Unit, force: bool) -> UnitUpgradeStep:
        """Get the upgrade steps for a single unit.

        :param unit: Unit to generate upgrade steps
        :type unit: Unit
        :param force: Whether the unit step generation should be forced
        :type force: bool
        :return: Unit upgrade step
        :rtype: UnitUpgradeStep
        """
        # pylint: disable=unused-argument
        unit_plan = UnitUpgradeStep(description=f"Upgrade plan for unit '{unit.name}'")
        unit_plan.add_step(self._get_pause_unit_step(unit))
        unit_plan.add_step(self._get_openstack_upgrade_step(unit))
        unit_plan.add_step(self._get_resume_unit_step(unit))
        return unit_plan

    def _get_units_upgrade_steps(self, units: Optional[list[Unit]], force: bool) -> UpgradeStep:
        """Get the upgrade steps for the units.

        :param units: Units to generate upgrade steps
        :type units: list[Unit]
        :param force: Whether the plan generation should be forced
        :type force: bool
        :return: Upgrade step
        :rtype: UpgradeStep
        """
        if not units:
            logger.debug("units were not provided, skipping")
            return UpgradeStep()

        units_plan = UpgradeStep(
            description=f"Upgrade plan for units: {', '.join([unit.name for unit in units])}",
            parallel=True,
        )
        units_plan.add_steps(self._get_unit_upgrade_steps(unit, force) for unit in units)
        return units_plan

    def _get_upgrade_current_release_packages_step(
        self, units: Optional[list[Unit]]
    ) -> PreUpgradeStep:
        """Get step for upgrading software packages to the latest of the current release.

        :param units: Units to generate upgrade plan
        :type units: Optional[list[Unit]]
        :return: Step for upgrading software packages to the latest of the current release.
        :rtype: PreUpgradeStep
        """
        step = PreUpgradeStep(
            f"Upgrade software packages of '{self.name}' from the current APT repositories",
            parallel=True,
        )
        step.add_steps(
            UnitUpgradeStep(
                description=f"Upgrade software packages on unit '{unit.name}'",
                coro=upgrade_packages(unit.name, self.model, self.packages_to_hold),
            )
            for unit in units or self.units.values()
        )

        return step

    def _get_refresh_charm_steps(self, target: OpenStackRelease) -> list[PreUpgradeStep]:
        """Get steps for refreshing the charm.

        :param target: OpenStack release as target to upgrade
        :type target: OpenStackRelease
        :raises ApplicationError: When application has unexpected channel.
        :return: Steps for refreshing the charm
        :rtype: list[PreUpgradeStep]
        """
        wait_step = PreUpgradeStep(
            description=f"Wait for up to {self.charm_refresh_timeout}s for "
            f"app '{self.name}' to reach the idle state",
            parallel=False,
            coro=self.model.wait_for_idle(self.charm_refresh_timeout, apps=[self.name]),
        )
        if self.is_from_charm_store:
            return [self._get_charmhub_migration_step(target), wait_step]
        if self.channel in LATEST_STABLE:
            return [
                self._get_change_channel_possible_downgrade_step(
                    target, self.expected_current_channel(target)
                ),
                wait_step,
            ]

        if self._need_current_channel_refresh(target):
            return [self._get_refresh_current_channel_step(), wait_step]
        logger.info(
            "'%s' does not need to refresh the current channel: %s", self.name, self.channel
        )
        return []

    def _get_charmhub_migration_step(self, target: OpenStackRelease) -> PreUpgradeStep:
        """Get the step for charm hub migration from charm store.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Step for charmhub migration
        :rtype: PreUpgradeStep
        """
        return PreUpgradeStep(
            f"Migrate '{self.name}' from charmstore to charmhub",
            coro=self.model.upgrade_charm(
                self.name, self.expected_current_channel(target), switch=f"ch:{self.charm}"
            ),
        )

    def _get_change_channel_possible_downgrade_step(
        self, target: OpenStackRelease, channel: str
    ) -> PreUpgradeStep:
        """Get the step for changing to a channel that can be a downgrade.

        :param target:  OpenStack release as target to upgrade
        :type target: OpenStackRelease
        :param channel: channel to upgrade
        :type channel: str
        :return:  Step for possible downgrade.
        :rtype: PreUpgradeStep
        """
        logger.warning(
            "Changing '%s' channel from %s to %s to upgrade to %s. This may be a charm downgrade, "
            "which is generally not supported.",
            self.name,
            self.channel,
            channel,
            target,
        )
        description = (
            f"WARNING: Changing '{self.name}' channel from {self.channel} to "
            f"{channel}. This may be a charm downgrade, which is generally not supported."
        )
        return PreUpgradeStep(
            description=description, coro=self.model.upgrade_charm(self.name, channel)
        )

    def _get_refresh_current_channel_step(self) -> PreUpgradeStep:
        """Get step for refreshing the current channel.

        :return: Step for refreshing the charm
        :rtype: PreUpgradeStep
        """
        return PreUpgradeStep(
            f"Refresh '{self.name}' to the latest revision of '{self.channel}'",
            coro=self.model.upgrade_charm(self.name, self.channel),
        )

    def _need_current_channel_refresh(self, target: OpenStackRelease) -> bool:
        """Check if the application needs to refresh the current channel.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: True if needs to refresh, False otherwise
        :rtype: bool
        """
        return bool(self.can_upgrade_to) and self.channel_o7k_release <= target

    def _get_upgrade_charm_steps(self, target: OpenStackRelease) -> list[UpgradeStep]:
        """Get steps for upgrading the charm.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :raises ApplicationError: When the current channel is ahead of the upgrade target.
        :return: List of steps for upgrading the charm.
        :rtype: list[UpgradeStep]
        """
        channel = self.expected_current_channel(target) if self.need_crossgrade else self.channel

        if channel == self.target_channel(target):
            logger.debug("%s channel already set to %s", self.name, self.channel)
            return []

        # Normally, prior the upgrade the channel is equal to the application release.
        # However, when colocated with other app, the channel can be in a release lesser than the
        # workload version of the application.
        if self.channel_o7k_release <= self.o7k_release or self.multiple_channels:
            return [
                UpgradeStep(
                    description=f"Upgrade '{self.name}' from '{channel}' to the new channel: "
                    f"'{self.target_channel(target)}'",
                    coro=self.model.upgrade_charm(self.name, self.target_channel(target)),
                ),
                UpgradeStep(
                    description=f"Wait for up to {self.charm_refresh_timeout}s for "
                    f"app '{self.name}' to reach the idle state",
                    parallel=False,
                    coro=self.model.wait_for_idle(self.charm_refresh_timeout, apps=[self.name]),
                ),
            ]

        raise ApplicationError(
            f"The '{self.name}' application is using an unexpected channel: '{self.channel}'. "
            "Channels supported during this upgrade are, "
            f"before upgrade: '{self.expected_current_channel(target)}', "
            f"or after upgrade: '{self.target_channel(target)}'. "
            "Manual intervention required, most likely to manually upgrade "
            "other cloud components until all are consistent releases."
        )

    def _set_action_managed_upgrade(self, enable: bool) -> UpgradeStep:
        """Set action-managed-upgrade config option.

        :param enable: enable or disable option
        :type enable: bool
        :return: Step to change action-managed-upgrade config option, if option exist.
        :rtype: UnitUpgradeStep
        """
        if "action-managed-upgrade" not in self.config:
            logger.debug(
                "%s application doesn't have an action-managed-upgrade config option", self.name
            )
            return UpgradeStep()

        amu_config = self.config["action-managed-upgrade"].get("value")
        if amu_config == enable:
            logger.debug(
                "%s application already has action-managed-upgrade set to %s", self.name, enable
            )
            return UpgradeStep()

        return UpgradeStep(
            f"Change charm config of '{self.name}' 'action-managed-upgrade' "
            f"from '{amu_config}' to '{enable}'",
            coro=self.model.set_application_config(
                self.name, {"action-managed-upgrade": str(enable)}
            ),
        )

    def _get_pause_unit_step(self, unit: Unit, dependent: bool = False) -> UnitUpgradeStep:
        """Get the step to pause a unit to upgrade.

        :param unit: Unit to be paused.
        :type unit: Unit
        :param dependent: Whether the step is dependent of another step, defaults to False
        :type dependent: bool, optional
        :return: Step to pause a unit.
        :rtype: UnitUpgradeStep
        """
        return UnitUpgradeStep(
            description=f"Pause the unit: '{unit.name}'",
            coro=self.model.run_action(unit.name, "pause", raise_on_failure=True),
            dependent=dependent,
        )

    def _get_resume_unit_step(self, unit: Unit, dependent: bool = False) -> UnitUpgradeStep:
        """Get the step to resume a unit after upgrading the workload version.

        :param unit: Unit to be resumed.
        :type unit: Unit
        :param dependent: Whether the step is dependent of another step, defaults to False
        :type dependent: bool, optional
        :return: Step to resume a unit.
        :rtype: UnitUpgradeStep
        """
        return UnitUpgradeStep(
            description=f"Resume the unit: '{unit.name}'",
            coro=self.model.run_action(unit.name, "resume", raise_on_failure=True),
            dependent=dependent,
        )

    def _get_openstack_upgrade_step(self, unit: Unit, dependent: bool = False) -> UnitUpgradeStep:
        """Get the step to upgrade a unit.

        :param unit: Unit to be upgraded.
        :type unit: Unit
        :param dependent: Whether the step is dependent of another step, defaults to False
        :type dependent: bool, optional
        :return: Step to upgrade a unit.
        :rtype: UnitUpgradeStep
        """
        return UnitUpgradeStep(
            description=f"Upgrade the unit: '{unit.name}'",
            coro=self.model.run_action(unit.name, "openstack-upgrade", raise_on_failure=True),
            dependent=dependent,
        )

    def _get_change_install_repository_step(self, target: OpenStackRelease) -> UpgradeStep:
        """Change openstack-origin or source for the next OpenStack target.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Workload upgrade step
        :rtype: UpgradeStep
        """
        if self.o7k_origin != self.new_origin(target) and self.origin_setting:
            return UpgradeStep(
                f"Change charm config of '{self.name}' '{self.origin_setting}' to "
                f"'{self.new_origin(target)}'",
                coro=self.model.set_application_config(
                    self.name, {self.origin_setting: self.new_origin(target)}
                ),
            )
        logger.warning(
            "Not changing the install repository of app %s: %s already set to %s",
            self.name,
            self.origin_setting,
            self.new_origin(target),
        )
        return UpgradeStep()

    def _get_reached_expected_target_step(
        self, target: OpenStackRelease, units: Optional[list[Unit]]
    ) -> PostUpgradeStep:
        """Get post upgrade step to check if application workload has been upgraded.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate post upgrade plan
        :type units: Optional[list[Unit]]
        :return: Post Upgrade step to check if application workload has been upgraded.
        :rtype: PostUpgradeStep
        """
        if not units:
            units = list(self.units.values())

        return PostUpgradeStep(
            f"Verify that the workload of '{self.name}' has been upgraded on units: "
            f"{', '.join([unit.name for unit in units])}",
            coro=self._verify_workload_upgrade(target, units),
        )

    def _get_wait_step(self) -> PostUpgradeStep:
        """Get wait step for entire model or application.

        :return: Step waiting for entire model or application itself
        :rtype: PostUpgradeStep
        """
        if self.wait_for_model:
            description = (
                f"Wait for up to {self.wait_timeout}s for model '{self.model.name}' "
                "to reach the idle state"
            )
            apps = None
        else:
            description = (
                f"Wait for up to {self.wait_timeout}s for app '{self.name}' "
                "to reach the idle state"
            )
            apps = [self.name]

        return PostUpgradeStep(
            description=description,
            parallel=False,
            coro=self.model.wait_for_idle(self.wait_timeout, apps=apps),
        )

    def _check_channel(self) -> None:
        """Check app channel from current data.

        :raises ApplicationError: Exception raised when channel is not a valid OpenStack channel.
        """
        if self.need_crossgrade or self.is_valid_track(self.channel):
            logger.debug("%s app has proper channel %s", self.name, self.channel)
            return

        raise ApplicationError(
            f"Channel: {self.channel} for charm '{self.charm}' on series "
            f"'{self.series}' is not supported by COU. Please take a look at the documentation: "
            "https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html to see if "
            "you are using the right track."
        )

    def _check_auto_restarts(self) -> None:
        """Check if enable-auto-restarts is enabled.

        If the enable-auto-restart option is not enabled, this check will raise an exception.

        :raises ApplicationError: When enable-auto-restarts is not enabled.
        """
        if "enable-auto-restarts" not in self.config:
            logger.debug(
                "%s application does not have an enable-auto-restarts config option", self.name
            )
            return

        if self.config["enable-auto-restarts"].get("value") is False:
            raise ApplicationError(
                "COU does not currently support upgrading applications that disable service "
                "restarts. Please enable charm option enable-auto-restart and rerun COU to "
                f"upgrade the {self.name} application."
            )

    def _check_application_target(self, target: OpenStackRelease) -> None:
        """Check if the application is already upgraded.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :raises HaltUpgradePlanGeneration: When the application halt the upgrade plan generation.
        """
        logger.debug(
            "%s current os_release is '%s' with origin setting '%s' and apt source '%s'",
            self.name,
            self.o7k_release,
            self.o7k_origin,
            self.apt_source_codename,
        )

        if (
            self.o7k_release >= target
            and not self.can_upgrade_to
            # consider apt_source_codename just when exist or not empty
            and (self.apt_source_codename >= target if self.o7k_origin else True)
        ):
            raise HaltUpgradePlanGeneration(
                f"Application '{self.name}' already configured for release equal to or greater "
                f"than {target}. Ignoring."
            )

    def _check_mismatched_versions(self) -> None:
        """Check that there are no unexpected mismatched versions on app units.

        For cases where mismatched versions may be expected
        (eg. nova-compute which is upgraded unit-by-unit),
        then it will not check.

        :raises MismatchedOpenStackVersions: When the units of the app are running
                                             different OpenStack versions.
        """
        # nova-compute is upgraded one unit at a time,
        # so it's possible to have mismatched version in
        # units of applications that are nova-compute or colocated with it.
        if any(
            "nova-compute" in app_charm
            for machine in self.machines.values()
            for app_charm in machine.apps_charms
        ):
            return

        if len({self.get_latest_o7k_version(unit) for unit in self.units.values()}) > 1:
            formatted_results = "\n".join(
                f"  {unit.name}: {self.get_latest_o7k_version(unit)} "
                f"(workload: {unit.workload_version})"
                for unit in sorted(self.units.values(), key=lambda unit: unit.name)
            )
            raise MismatchedOpenStackVersions(
                f"Units of application {self.name} are running mismatched OpenStack releases, "
                "based on the workload versions as reported by juju status. "
                "Observed OpenStack releases for each unit:\n"
                f"{formatted_results}\n"
                "This requires manually resolving the issue to continue."
            )
