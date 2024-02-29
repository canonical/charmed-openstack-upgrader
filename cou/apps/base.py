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

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

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
from cou.utils.juju_utils import COUApplication, COUUnit
from cou.utils.openstack import (
    DISTRO_TO_OPENSTACK_MAPPING,
    OpenStackCodenameLookup,
    OpenStackRelease,
)

logger = logging.getLogger(__name__)

DEFAULT_WAITING_TIMEOUT = 5 * 60  # 5 min
ORIGIN_SETTINGS = ("openstack-origin", "source")
REQUIRED_SETTINGS = ("enable-auto-restarts", "action-managed-upgrade", *ORIGIN_SETTINGS)


@dataclass(frozen=True)
class OpenStackApplication(COUApplication):
    """Representation of a charmed OpenStack application in the deployment.

    :raises ApplicationError: When there are no compatible OpenStack release for the
        workload version.
    :raises MismatchedOpenStackVersions: When units part of this application are running mismatched
        OpenStack versions.
    :raises HaltUpgradePlanGeneration: When the class halts the upgrade plan generation.
    :raises CommandRunFailed: When a command fails to run.
    :raises RunUpgradeError: When an upgrade fails.
    """

    packages_to_hold: Optional[list] = field(default=None, init=False)
    wait_timeout: int = field(default=DEFAULT_WAITING_TIMEOUT, init=False)
    wait_for_model: bool = field(default=False, init=False)  # waiting only for application itself

    def __post_init__(self) -> None:
        """Initialize the Application dataclass."""
        self._verify_channel()

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
                        "os_version": str(self._get_latest_os_version(unit)),
                    }
                    for unit in self.units.values()
                },
                "machines": {
                    machine.machine_id: {
                        "id": machine.machine_id,
                        "apps": machine.apps,
                        "az": machine.az,
                    }
                    for machine in self.machines.values()
                },
            }
        }

        return yaml.dump(summary, sort_keys=False)

    def _verify_channel(self) -> None:
        """Verify app channel from current data.

        :raises ApplicationError: Exception raised when channel is not a valid OpenStack channel.
        """
        if self.is_from_charm_store or self.is_valid_track(self.channel):
            logger.debug("%s app has proper channel %s", self.name, self.channel)
            return

        raise ApplicationError(
            f"Channel: {self.channel} for charm '{self.charm}' on series "
            f"'{self.series}' is currently not supported in this tool. Please take a look at the "
            "documentation: "
            "https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html to see if "
            "you are using the right track."
        )

    @property
    def os_origin(self) -> str:
        """Get application configuration for openstack-origin or source.

        :return: Configuration parameter of the charm to set OpenStack origin.
            e.g: cloud:focal-wallaby
        :rtype: str
        """
        if origin := self.origin_setting:
            return self.config[origin].get("value", "")

        logger.warning("Failed to get origin for %s, no origin config found", self.name)
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

        return None

    def is_valid_track(self, charm_channel: str) -> bool:
        """Check if the channel track is valid.

        :param charm_channel: Charm channel. E.g: ussuri/stable
        :type charm_channel: str
        :return: True if valid, False otherwise.
        :rtype: bool
        """
        try:
            OpenStackRelease(self._get_track_from_channel(charm_channel))
            return True
        except ValueError:
            return self.is_from_charm_store

    def _get_latest_os_version(self, unit: COUUnit) -> OpenStackRelease:
        """Get the latest compatible OpenStack release based on the unit workload version.

        :param unit: Application Unit
        :type unit: COUUnit
        :raises ApplicationError: When there are no compatible OpenStack release for the
        workload version.
        :return: The latest compatible OpenStack release.
        :rtype: OpenStackRelease
        """
        compatible_os_versions = OpenStackCodenameLookup.find_compatible_versions(
            self.charm, unit.workload_version
        )
        if not compatible_os_versions:
            raise ApplicationError(
                f"'{self.name}' with workload version {unit.workload_version} has no "
                "compatible OpenStack release."
            )

        return max(compatible_os_versions)

    @staticmethod
    def _get_track_from_channel(charm_channel: str) -> str:
        """Get the track from a given channel.

        :param charm_channel: Charm channel. E.g: ussuri/stable
        :type charm_channel: str
        :return: The track from a channel. E.g: ussuri
        :rtype: str
        """
        return charm_channel.split("/", maxsplit=1)[0]

    @property
    def possible_current_channels(self) -> list[str]:
        """Return the possible current channels based on the current OpenStack release.

        :return: The possible current channels for the application. E.g: ["ussuri/stable"]
        :rtype: list[str]
        """
        return [f"{self.current_os_release.codename}/stable"]

    def target_channel(self, target: OpenStackRelease) -> str:
        """Return the appropriate channel for the passed OpenStack target.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: The next channel for the application. E.g: victoria/stable
        :rtype: str
        """
        return f"{target.codename}/stable"

    @property
    def current_os_release(self) -> OpenStackRelease:
        """Current OpenStack Release of the application.

        :raises MismatchedOpenStackVersions: When units part of this application are
        running mismatched OpenStack versions.
        :return: OpenStackRelease object
        :rtype: OpenStackRelease
        """
        os_versions = defaultdict(list)
        for unit in self.units.values():
            os_version = self._get_latest_os_version(unit)
            os_versions[os_version].append(unit.name)

        if len(os_versions.keys()) == 1:
            return next(iter(os_versions))

        # NOTE (gabrielcocenza) on applications that use single-unit or paused-single-unit
        # upgrade methods, more than one version can be found.
        mismatched_repr = [
            f"'{openstack_release.codename}': {units}"
            for openstack_release, units in os_versions.items()
        ]

        raise MismatchedOpenStackVersions(
            f"Units of application {self.name} are running mismatched OpenStack versions: "
            f"{', '.join(mismatched_repr)}. This is not currently handled."
        )

    @property
    def apt_source_codename(self) -> Optional[OpenStackRelease]:
        """Identify the OpenStack release set on "openstack-origin" or "source" config.

        :raises ApplicationError: If os_origin_parsed is not a valid OpenStack release or os_origin
            is in an unexpected format (ppa, url, etc).
        :return: OpenStackRelease object or None if the app doesn't have os_origin config.
        :rtype: Optional[OpenStackRelease]
        """
        os_origin_parsed: Optional[str]
        # that means that the charm doesn't have "source" or "openstack-origin" config.
        if self.origin_setting is None:
            return None

        # Ex: "cloud:focal-ussuri" will result in "ussuri"
        if self.os_origin.startswith("cloud"):
            *_, os_origin_parsed = self.os_origin.rsplit("-", maxsplit=1)
            try:
                return OpenStackRelease(os_origin_parsed)
            except ValueError as exc:
                raise ApplicationError(
                    f"'{self.name}' has an invalid '{self.origin_setting}': {self.os_origin}"
                ) from exc

        elif self.os_origin == "distro":
            # find the OpenStack release based on ubuntu series
            os_origin_parsed = DISTRO_TO_OPENSTACK_MAPPING[self.series]
            return OpenStackRelease(os_origin_parsed)

        elif self.os_origin == "":
            return None

        else:
            # probably because user set a ppa or an url
            raise ApplicationError(
                f"'{self.name}' has an invalid '{self.origin_setting}': {self.os_origin}"
            )

    @property
    def channel_codename(self) -> OpenStackRelease:
        """Identify the OpenStack release set in the charm channel.

        :return: OpenStackRelease object
        :rtype: OpenStackRelease
        """
        # get the OpenStack release from the channel track of the application.
        return OpenStackRelease(self._get_track_from_channel(self.channel))

    @property
    def can_upgrade_current_channel(self) -> bool:
        """Check if it's possible to upgrade the charm code.

        :return: True if can upgrade, False otherwise.
        :rtype: bool
        """
        return bool(self.can_upgrade_to)

    def new_origin(self, target: OpenStackRelease) -> str:
        """Return the new openstack-origin or source configuration.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Repository from which to install.
        :rtype: str
        """
        return f"cloud:{self.series}-{target.codename}"

    def pre_upgrade_steps(
        self, target: OpenStackRelease, units: Optional[list[COUUnit]]
    ) -> list[PreUpgradeStep]:
        """Pre Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate upgrade plan
        :type units: Optional[list[COUUnit]]
        :return: List of pre upgrade steps.
        :rtype: list[PreUpgradeStep]
        """
        return [
            self._get_upgrade_current_release_packages_step(units),
            self._get_refresh_charm_step(target),
        ]

    def upgrade_steps(
        self,
        target: OpenStackRelease,
        units: Optional[list[COUUnit]],
        force: bool,
    ) -> list[UpgradeStep]:
        """Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate upgrade steps
        :type units: Optional[list[COUUnit]]
        :param force: Whether the plan generation should be forced
        :type force: bool
        :raises HaltUpgradePlanGeneration: When the application halt the upgrade plan generation.
        :return: List of upgrade steps.
        :rtype: list[UpgradeStep]
        """
        # pylint: disable=unused-argument
        if self.current_os_release >= target and self.apt_source_codename >= target:
            msg = (
                f"Application '{self.name}' already configured for release equal or greater "
                f"than {target}. Ignoring."
            )
            logger.info(msg)
            raise HaltUpgradePlanGeneration(msg)

        return [
            self._set_action_managed_upgrade(enable=bool(units)),
            self._get_upgrade_charm_step(target),
            self._get_change_install_repository_step(target),
        ]

    def post_upgrade_steps(
        self, target: OpenStackRelease, units: Optional[Iterable[COUUnit]]
    ) -> list[PostUpgradeStep]:
        """Post Upgrade steps planning.

        Wait until the application reaches the idle state and then check the target workload.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate post upgrade plan
        :type units: Optional[Iterable[COUUnit]]
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
        units: Optional[list[COUUnit]] = None,
    ) -> ApplicationUpgradePlan:
        """Generate full upgrade plan for an Application.

        Units are passed if the application should upgrade unit by unit.

        :param target: OpenStack codename to upgrade.
        :type target: OpenStackRelease
        :param force: Whether the plan generation should be forced
        :type force: bool
        :param units: Units to generate upgrade plan, defaults to None
        :type units: Optional[list[COUUnit]], optional
        :return: Full upgrade plan if the Application is able to generate it.
        :rtype: ApplicationUpgradePlan
        """
        upgrade_steps = ApplicationUpgradePlan(
            description=f"Upgrade plan for '{self.name}' to {target}",
        )
        all_steps = (
            self.pre_upgrade_steps(target, units)
            + self.upgrade_steps(target, units, force)
            + self.post_upgrade_steps(target, units)
        )
        for step in all_steps:
            if step:
                upgrade_steps.add_step(step)
        return upgrade_steps

    def _get_upgrade_current_release_packages_step(
        self, units: Optional[list[COUUnit]]
    ) -> PreUpgradeStep:
        """Get step for upgrading software packages to the latest of the current release.

        :param units: Units to generate upgrade plan
        :type units: Optional[list[COUUnit]]
        :return: Step for upgrading software packages to the latest of the current release.
        :rtype: PreUpgradeStep
        """
        if not units:
            units = list(self.units.values())
        step = PreUpgradeStep(
            description=(
                f"Upgrade software packages of '{self.name}' from the current APT repositories"
            ),
            parallel=True,
        )
        for unit in units:
            step.add_step(
                UnitUpgradeStep(
                    description=f"Upgrade software packages on unit {unit.name}",
                    coro=upgrade_packages(unit.name, self.model, self.packages_to_hold),
                )
            )

        return step

    def _get_refresh_charm_step(self, target: OpenStackRelease) -> PreUpgradeStep:
        """Get step for refreshing the current channel.

        This function also identifies if charm comes from charmstore and in that case,
        makes the migration.
        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :raises ApplicationError: When application has unexpected channel.
        :return: Step for refreshing the charm.
        :rtype: PreUpgradeStep
        """
        if not self.can_upgrade_current_channel:
            return PreUpgradeStep()

        switch = None
        *_, channel = self.possible_current_channels

        # corner case for rabbitmq and hacluster.
        if len(self.possible_current_channels) > 1:
            logger.info(
                (
                    "'%s' has more than one channel compatible with the current OpenStack "
                    "release: '%s'. '%s' will be used"
                ),
                self.name,
                self.current_os_release.codename,
                channel,
            )

        if self.origin == "cs":
            description = f"Migration of '{self.name}' from charmstore to charmhub"
            switch = f"ch:{self.charm}"
        elif self.channel in self.possible_current_channels:
            channel = self.channel
            description = f"Refresh '{self.name}' to the latest revision of '{channel}'"
        elif self.channel_codename >= target:
            logger.info(
                "Skipping charm refresh for %s, its channel is already set to %s.",
                self.name,
                self.channel,
            )
            return PreUpgradeStep()
        elif self.channel not in self.possible_current_channels:
            raise ApplicationError(
                f"'{self.name}' has unexpected channel: '{self.channel}' for the current workload "
                f"version and OpenStack release: '{self.current_os_release.codename}'. "
                f"Possible channels are: {','.join(self.possible_current_channels)}"
            )

        return PreUpgradeStep(
            description=description,
            coro=self.model.upgrade_charm(self.name, channel, switch=switch),
        )

    def _get_upgrade_charm_step(self, target: OpenStackRelease) -> UpgradeStep:
        """Get step for upgrading the charm.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Step for upgrading the charm.
        :rtype: UpgradeStep
        """
        if self.channel == self.target_channel(target):
            return UpgradeStep()

        return UpgradeStep(
            f"Upgrade '{self.name}' to the new channel: '{self.target_channel(target)}'",
            coro=self.model.upgrade_charm(self.name, self.target_channel(target)),
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

        if self.config["action-managed-upgrade"].get("value") != enable:
            return UpgradeStep(
                f"Change charm config of '{self.name}' 'action-managed-upgrade' to {enable}",
                coro=self.model.set_application_config(
                    self.name, {"action-managed-upgrade": enable}
                ),
            )

        return UpgradeStep()

    def _get_pause_unit_step(self, unit: COUUnit, dependent: bool = False) -> UnitUpgradeStep:
        """Get the step to pause a unit to upgrade.

        :param unit: Unit to be paused.
        :type unit: COUUnit
        :param dependent: Whether the step is dependent of another step, defaults to False
        :type dependent: bool, optional
        :return: Step to pause a unit.
        :rtype: UnitUpgradeStep
        """
        return UnitUpgradeStep(
            description=f"Pause the unit: '{unit.name}'.",
            coro=self.model.run_action(
                unit_name=unit.name, action_name="pause", raise_on_failure=True
            ),
            dependent=dependent,
        )

    def _get_resume_unit_step(self, unit: COUUnit, dependent: bool = False) -> UnitUpgradeStep:
        """Get the step to resume a unit after upgrading the workload version.

        :param unit: Unit to be resumed.
        :type unit: COUUnit
        :param dependent: Whether the step is dependent of another step, defaults to False
        :type dependent: bool, optional
        :return: Step to resume a unit.
        :rtype: UnitUpgradeStep
        """
        return UnitUpgradeStep(
            description=(f"Resume the unit: '{unit.name}'."),
            coro=self.model.run_action(
                unit_name=unit.name, action_name="resume", raise_on_failure=True
            ),
            dependent=dependent,
        )

    def _get_openstack_upgrade_step(
        self, unit: COUUnit, dependent: bool = False
    ) -> UnitUpgradeStep:
        """Get the step to upgrade a unit.

        :param unit: Unit to be upgraded.
        :type unit: COUUnit
        :param dependent: Whether the step is dependent of another step, defaults to False
        :type dependent: bool, optional
        :return: Step to upgrade a unit.
        :rtype: UnitUpgradeStep
        """
        return UnitUpgradeStep(
            description=f"Upgrade the unit: '{unit.name}'.",
            coro=self.model.run_action(
                unit_name=unit.name, action_name="openstack-upgrade", raise_on_failure=True
            ),
            dependent=dependent,
        )

    def _get_change_install_repository_step(self, target: OpenStackRelease) -> UpgradeStep:
        """Change openstack-origin or source for the next OpenStack target.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Workload upgrade step
        :rtype: UpgradeStep
        """
        if self.os_origin != self.new_origin(target) and self.origin_setting:
            return UpgradeStep(
                description=(
                    f"Change charm config of '{self.name}' "
                    f"'{self.origin_setting}' to '{self.new_origin(target)}'"
                ),
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
        self, target: OpenStackRelease, units: Optional[Iterable[COUUnit]]
    ) -> PostUpgradeStep:
        """Get post upgrade step to check if application workload has been upgraded.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate post upgrade plan
        :type units: Optional[Iterable[COUUnit]]
        :return: Post Upgrade step to check if application workload has been upgraded.
        :rtype: PostUpgradeStep
        """
        if not units:
            units = list(self.units.values())
        return PostUpgradeStep(
            description=(
                f"Check if the workload of '{self.name}' has been upgraded on units: "
                f"{', '.join([unit.name for unit in units])}"
            ),
            coro=self._verify_workload_upgrade(target, units),
        )

    async def _verify_workload_upgrade(
        self, target: OpenStackRelease, units: Iterable[COUUnit]
    ) -> None:
        """Check if an application has upgraded its workload version.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to check if got upgraded
        :type units: Iterable[COUUnit]
        :raises ApplicationError: When the workload version of the charm doesn't upgrade.
        """
        status = await self.model.get_status()
        app_status = status.applications.get(self.name)
        units_not_upgraded = []
        for unit in units:
            workload_version = app_status.units[unit.name].workload_version
            compatible_os_versions = OpenStackCodenameLookup.find_compatible_versions(
                self.charm, workload_version
            )
            if target not in compatible_os_versions:
                units_not_upgraded.append(unit.name)

        if units_not_upgraded:
            raise ApplicationError(
                f"Cannot upgrade units '{', '.join(units_not_upgraded)}' to {target}."
            )

    def _get_wait_step(self) -> PostUpgradeStep:
        """Get wait step for entire model or application.

        :return: Step waiting for entire model or application itself
        :rtype: PostUpgradeStep
        """
        if self.wait_for_model:
            description = (
                f"Wait {self.wait_timeout}s for model {self.model.name} to reach the idle state."
            )
            apps = None
        else:
            description = f"Wait {self.wait_timeout}s for app {self.name} to reach the idle state."
            apps = [self.name]

        return PostUpgradeStep(
            description=description,
            parallel=False,
            coro=self.model.wait_for_active_idle(self.wait_timeout, apps=apps),
        )
