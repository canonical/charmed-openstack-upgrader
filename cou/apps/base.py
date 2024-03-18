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
import os
from collections import defaultdict
from dataclasses import dataclass, field
from io import StringIO
from typing import Any, Optional

from juju.client._definitions import ApplicationStatus, UnitStatus
from ruamel.yaml import YAML

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
from cou.utils.juju_utils import COUModel, Machine
from cou.utils.openstack import (
    DISTRO_TO_OPENSTACK_MAPPING,
    OpenStackCodenameLookup,
    OpenStackRelease,
)

logger = logging.getLogger(__name__)

STANDARD_IDLE_TIMEOUT: int = int(
    os.environ.get("COU_STANDARD_IDLE_TIMEOUT", 5 * 60)
)  # default of 5 min
LONG_IDLE_TIMEOUT: int = int(os.environ.get("COU_LONG_IDLE_TIMEOUT", 30 * 60))  # default of 30 min


@dataclass
class ApplicationUnit:
    """Representation of a single unit of application."""

    name: str
    os_version: OpenStackRelease
    machine: Machine
    workload_version: str = ""


@dataclass
class OpenStackApplication:
    """Representation of a charmed OpenStack application in the deployment.

    :param name: Name of the application
    :type name: str
    :param status: Status of the application.
    :type status: ApplicationStatus
    :param config: Configuration of the application.
    :type config: dict
    :param model: COUModel object
    :type model: COUModel
    :param charm: Name of the charm.
    :type charm: str
    :param machines: dictionary with Machine
    :type machines: dict[str, Machine]
    :param units: Units representation of an application.
    :type units: list[ApplicationUnit]
    :raises ApplicationError: When there are no compatible OpenStack release for the
        workload version.
    :raises CommandRunFailed: When a command fails to run.
    :raises RunUpgradeError: When an upgrade fails.
    """

    # pylint: disable=too-many-instance-attributes, too-many-public-methods

    name: str
    status: ApplicationStatus
    config: dict
    model: COUModel
    charm: str
    machines: dict[str, Machine]
    units: list[ApplicationUnit] = field(default_factory=lambda: [])
    packages_to_hold: Optional[list] = field(default=None, init=False)
    wait_timeout: int = field(default=STANDARD_IDLE_TIMEOUT, init=False)
    wait_for_model: bool = field(default=False, init=False)  # waiting only for application itself

    def __post_init__(self) -> None:
        """Initialize the Application dataclass."""
        self._verify_channel()
        self._populate_units()

    def __hash__(self) -> int:
        """Hash magic method for Application.

        :return: Unique hash identifier for Application object.
        :rtype: int
        """
        return hash(f"{self.name}{self.charm}")

    def __eq__(self, other: Any) -> bool:
        """Equal magic method for Application.

        :param other: Application object to compare.
        :type other: Any
        :return: True if equal False if different.
        :rtype: bool
        """
        return other.name == self.name and other.charm == self.charm

    def __str__(self) -> str:
        """Dump as string.

        :return: Summary representation of an Application.
        :rtype: str
        """
        summary = {
            self.name: {
                "model_name": self.model.name,
                "charm": self.charm,
                "charm_origin": self.charm_origin,
                "os_origin": self.os_origin,
                "channel": self.channel,
                "units": {
                    unit.name: {
                        "workload_version": unit.workload_version,
                        "os_version": str(unit.os_version),
                    }
                    for unit in self.units
                },
            }
        }
        yaml = YAML()
        with StringIO() as stream:
            yaml.dump(summary, stream)
            return stream.getvalue()

    def _verify_channel(self) -> None:
        """Verify app channel from current data.

        :raises ApplicationError: Exception raised when channel is not a valid OpenStack channel.
        """
        if self.is_from_charm_store or self.is_valid_track(self.status.charm_channel):
            logger.debug("%s app has proper channel %s", self.name, self.status.charm_channel)
            return

        raise ApplicationError(
            f"Channel: {self.status.charm_channel} for charm '{self.charm}' on series "
            f"'{self.series}' is currently not supported in this tool. Please take a look at the "
            "documentation: "
            "https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html to see if "
            "you are using the right track."
        )

    def _populate_units(self) -> None:
        """Populate application units."""
        if not self.is_subordinate:
            for name, unit in self.status.units.items():
                compatible_os_version = self._get_latest_os_version(unit)
                self.units.append(
                    ApplicationUnit(
                        name=name,
                        workload_version=unit.workload_version,
                        os_version=compatible_os_version,
                        machine=self.machines[unit.machine],
                    )
                )

    @property
    def is_subordinate(self) -> bool:
        """Check if application is subordinate.

        :return: True if subordinate, False otherwise.
        :rtype: bool
        """
        return bool(self.status.subordinate_to)

    @property
    def channel(self) -> str:
        """Get charm channel of the application.

        :return: Charm channel. E.g: ussuri/stable
        :rtype: str
        """
        return self.status.charm_channel

    @property
    def charm_origin(self) -> str:
        """Get the charm origin of application.

        :return: Charm origin. E.g: cs or ch
        :rtype: str
        """
        return self.status.charm.split(":")[0]

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
        for origin in ("openstack-origin", "source"):
            if origin in self.config:
                return origin

        return None

    @property
    def is_from_charm_store(self) -> bool:
        """Check if application comes from charm store.

        :return: True if comes, False otherwise.
        :rtype: bool
        """
        return self.charm_origin == "cs"

    @property
    def os_release_units(self) -> dict[OpenStackRelease, list[str]]:
        """Get the OpenStack release versions from the units.

        :return: OpenStack release versions from the units.
        :rtype: defaultdict[OpenStackRelease, list[str]]
        """
        os_versions = defaultdict(list)
        for unit in self.units:
            os_version = self._get_latest_os_version(unit)
            os_versions[os_version].append(unit.name)

        return dict(os_versions)

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

    def _get_latest_os_version(self, unit: UnitStatus) -> OpenStackRelease:
        """Get the latest compatible OpenStack release based on the unit workload version.

        :param unit: Application Unit
        :type unit: UnitStatus
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
    def series(self) -> str:
        """Ubuntu series of the application.

        :return: Ubuntu series of application. E.g: focal
        :rtype: str
        """
        return self.status.series

    @property
    def current_os_release(self) -> OpenStackRelease:
        """Current OpenStack Release of the application.

        :return: OpenStackRelease object
        :rtype: OpenStackRelease
        """
        return min(self.os_release_units.keys())

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
        return bool(self.status.can_upgrade_to)

    def new_origin(self, target: OpenStackRelease) -> str:
        """Return the new openstack-origin or source configuration.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Repository from which to install.
        :rtype: str
        """
        return f"cloud:{self.series}-{target.codename}"

    async def _check_upgrade(self, target: OpenStackRelease) -> None:
        """Check if an application has upgraded its workload version.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :raises ApplicationError: When the workload version of the charm doesn't upgrade.
        """
        status = await self.model.get_status()
        app_status = status.applications.get(self.name)
        units_not_upgraded = []
        for unit in app_status.units.keys():
            workload_version = app_status.units[unit].workload_version
            compatible_os_versions = OpenStackCodenameLookup.find_compatible_versions(
                self.charm, workload_version
            )
            if target not in compatible_os_versions:
                units_not_upgraded.append(unit)

        if units_not_upgraded:
            units_not_upgraded_string = ", ".join(units_not_upgraded)
            raise ApplicationError(
                f"Cannot upgrade units '{units_not_upgraded_string}' to {target}."
            )

    def upgrade_plan_sanity_checks(self, target: OpenStackRelease) -> None:
        """Run sanity checks before generating upgrade plan.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :raises ApplicationError: When enable-auto-restarts is not enabled.
        :raises HaltUpgradePlanGeneration: When the application halt the upgrade plan generation.
        :raises MismatchedOpenStackVersions: When the units of the app are running different
                                             OpenStack versions.
        :raises ApplicationError: When enable-auto-restarts is not enabled.
        """
        self._check_application_target(target)
        self._check_mismatched_versions()
        self._check_auto_restarts()
        logger.info(
            "%s application met all the necessary prerequisites to generate the upgrade plan",
            self.name,
        )

    def pre_upgrade_steps(self, target: OpenStackRelease) -> list[PreUpgradeStep]:
        """Pre Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: List of pre upgrade steps.
        :rtype: list[PreUpgradeStep]
        """
        return [
            self._get_upgrade_current_release_packages_step(),
            self._get_refresh_charm_step(target),
        ]

    def upgrade_steps(self, target: OpenStackRelease) -> list[UpgradeStep]:
        """Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :raises HaltUpgradePlanGeneration: When the application halt the upgrade plan generation.
        :return: List of upgrade steps.
        :rtype: list[UpgradeStep]
        """
        return [
            self._get_disable_action_managed_step(),
            self._get_upgrade_charm_step(target),
            self._get_workload_upgrade_step(target),
        ]

    def post_upgrade_steps(self, target: OpenStackRelease) -> list[PostUpgradeStep]:
        """Post Upgrade steps planning.

        Wait until the application reaches the idle state and then check the target workload.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: List of post upgrade steps.
        :rtype: list[PostUpgradeStep]
        """
        return [
            self._get_wait_step(),
            self._get_reached_expected_target_step(target),
        ]

    def generate_upgrade_plan(self, target: OpenStackRelease) -> ApplicationUpgradePlan:
        """Generate full upgrade plan for an Application.

        :param target: OpenStack codename to upgrade.
        :type target: OpenStackRelease
        :return: Full upgrade plan if the Application is able to generate it.
        :rtype: ApplicationUpgradePlan
        """
        self.upgrade_plan_sanity_checks(target)

        upgrade_plan = ApplicationUpgradePlan(
            description=f"Upgrade plan for '{self.name}' to {target}",
        )
        upgrade_plan.add_steps(self.pre_upgrade_steps(target))
        upgrade_plan.add_steps(self.upgrade_steps(target))
        upgrade_plan.add_steps(self.post_upgrade_steps(target))

        return upgrade_plan

    def _get_upgrade_current_release_packages_step(self) -> PreUpgradeStep:
        """Get step for upgrading software packages to the latest of the current release.

        :return: Step for upgrading software packages to the latest of the current release.
        :rtype: PreUpgradeStep
        """
        step = PreUpgradeStep(
            description=(
                f"Upgrade software packages of '{self.name}' from the current APT repositories"
            ),
            parallel=True,
        )
        step.add_steps(
            UnitUpgradeStep(
                description=f"Upgrade software packages on unit {unit.name}",
                coro=upgrade_packages(unit.name, self.model, self.packages_to_hold),
            )
            for unit in self.units
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

        if self.charm_origin == "cs":
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
        if self.channel != self.target_channel(target):
            return UpgradeStep(
                description=(
                    f"Upgrade '{self.name}' to the new channel: '{self.target_channel(target)}'"
                ),
                coro=self.model.upgrade_charm(self.name, self.target_channel(target)),
            )
        return UpgradeStep()

    def _get_disable_action_managed_step(self) -> UpgradeStep:
        """Get step to disable action-managed-upgrade.

        This is used to upgrade as "all-in-one" strategy.

        :return: Step to disable action-managed-upgrade
        :rtype: UpgradeStep
        """
        if self.config.get("action-managed-upgrade", {}).get("value", False):
            return UpgradeStep(
                description=(
                    f"Change charm config of '{self.name}' 'action-managed-upgrade' to False."
                ),
                coro=self.model.set_application_config(
                    self.name, {"action-managed-upgrade": False}
                ),
            )
        return UpgradeStep()

    def _get_workload_upgrade_step(self, target: OpenStackRelease) -> UpgradeStep:
        """Get workload upgrade step by changing openstack-origin or source.

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
            "Not triggering the workload upgrade of app %s: %s already set to %s",
            self.name,
            self.origin_setting,
            self.new_origin(target),
        )
        return UpgradeStep()

    def _get_reached_expected_target_step(self, target: OpenStackRelease) -> PostUpgradeStep:
        """Get post upgrade step to check if application workload has been upgraded.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Post Upgrade step to check if application workload has been upgraded.
        :rtype: PostUpgradeStep
        """
        return PostUpgradeStep(
            description=f"Check if the workload of '{self.name}' has been upgraded",
            coro=self._check_upgrade(target),
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
        """Check if application release is not lower than or equal to target.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :raises HaltUpgradePlanGeneration: When the application halt the upgrade plan generation.
        """
        logger.debug(
            "%s application current os_release is %s and apt source is %s",
            self.name,
            self.current_os_release,
            self.apt_source_codename,
        )

        if self.current_os_release >= target and self.apt_source_codename >= target:
            raise HaltUpgradePlanGeneration(
                f"Application '{self.name}' already configured for release equal to or greater "
                f"than {target}. Ignoring."
            )

    def _check_mismatched_versions(self) -> None:
        """Check that there are no mismatched versions on app units.

        :raises MismatchedOpenStackVersions: When the units of the app are running different
                                             OpenStack versions.
        """
        os_versions = self.os_release_units
        if len(os_versions.keys()) > 1:
            mismatched_repr = [
                f"'{openstack_release.codename}': {units}"
                for openstack_release, units in os_versions.items()
            ]

            raise MismatchedOpenStackVersions(
                f"Units of application {self.name} are running mismatched OpenStack versions: "
                f"{', '.join(mismatched_repr)}. This is not currently handled."
            )
