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
from cou.steps import UpgradeStep
from cou.utils.app_utils import upgrade_packages
from cou.utils.juju_utils import COUModel
from cou.utils.openstack import (
    DISTRO_TO_OPENSTACK_MAPPING,
    OpenStackCodenameLookup,
    OpenStackRelease,
)

logger = logging.getLogger(__name__)

DEFAULT_WAITING_TIMEOUT = 120


@dataclass
class ApplicationUnit:
    """Representation of a single unit of application."""

    name: str
    os_version: OpenStackRelease
    workload_version: str = ""
    machine: str = ""


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
    :param charm_origin: Origin of the charm (local, ch, cs and etc.), defaults to ""
    :type charm_origin: str, defaults to ""
    :param os_origin: OpenStack origin of the application. E.g: cloud:focal-wallaby, defaults to ""
    :type os_origin: str, defaults to ""
    :param origin_setting: "source" or "openstack-origin" of the charm configuration.
        Return None if not present
    :type origin_setting: Optional[str], defaults to None
    :param channel: Channel that the charm tracks. E.g: "ussuri/stable", defaults to ""
    :type channel: str, defaults to ""
    :param units: Units representation of an application.
    :type units: list[ApplicationUnit]
    :raises ApplicationError: When there are no compatible OpenStack release for the
        workload version.
    :raises MismatchedOpenStackVersions: When units part of this application are running mismatched
        OpenStack versions.
    :raises HaltUpgradePlanGeneration: When the class halts the upgrade plan generation.
    :raises RunUpgradeError: When an upgrade fails.
    """

    # pylint: disable=too-many-instance-attributes

    name: str
    status: ApplicationStatus
    config: dict
    model: COUModel
    charm: str
    charm_origin: str = ""
    os_origin: str = ""
    origin_setting: Optional[str] = None
    units: list[ApplicationUnit] = field(default_factory=lambda: [])
    packages_to_hold: Optional[list] = field(default=None, init=False)
    wait_timeout: int = field(default=DEFAULT_WAITING_TIMEOUT, init=False)
    wait_for_model: bool = field(default=False, init=False)  # waiting only for application itself

    def __post_init__(self) -> None:
        """Initialize the Application dataclass."""
        self.charm_origin = self.status.charm.split(":")[0]
        self.os_origin = self._get_os_origin()
        self._populate_units()
        self.channel = self.status.charm_channel

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

    def _populate_units(self) -> None:
        """Populate application units."""
        if not self.is_subordinate:
            for name, unit in self.status.units.items():
                compatible_os_version = self._get_latest_os_version_by_workload_version(unit)
                self.units.append(
                    ApplicationUnit(
                        name=name,
                        workload_version=unit.workload_version,
                        os_version=compatible_os_version,
                        machine=unit.machine,
                    )
                )

    @property
    def is_subordinate(self) -> bool:
        """Check if application is subordinate.

        :return: True if subordinate, False otherwise.
        :rtype: bool
        """
        return bool(self.status.subordinate_to)

    def _get_latest_os_version_by_workload_version(self, unit: UnitStatus) -> OpenStackRelease:
        """Get the latest compatible OpenStack release based on the unit workload version.

        :param unit: Application Unit
        :type unit: UnitStatus
        :raises ApplicationError: When there are no compatible OpenStack release for the
        workload version.
        :return: The latest compatible OpenStack release.
        :rtype: OpenStackRelease
        """
        try:
            return max(
                OpenStackCodenameLookup.find_compatible_versions(self.charm, unit.workload_version)
            )
        except ValueError as exc:
            raise ApplicationError(
                f"'{self.name}' with workload version {unit.workload_version} has no "
                "compatible OpenStack release."
            ) from exc

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

        :raises MismatchedOpenStackVersions: When units part of this application are
        running mismatched OpenStack versions.
        :return: OpenStackRelease object
        :rtype: OpenStackRelease
        """
        os_versions = {unit.os_version for unit in self.units}

        if len(os_versions) == 1:
            return os_versions.pop()
        # NOTE (gabrielcocenza) on applications that use single-unit or paused-single-unit
        # upgrade methods, more than one version can be found.
        raise MismatchedOpenStackVersions(
            f"Units of application {self.name} are running mismatched OpenStack versions: "
            f"{os_versions}. This is not currently handled."
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
        try:
            # get the OpenStack release from the channel track of the application.
            os_track_release_channel = OpenStackRelease(self._get_track_from_channel(self.channel))
        except ValueError:
            logger.debug(
                "The current channel of '%s' does not exist or is unexpectedly formatted",
                self.name,
            )
            os_track_release_channel = self.current_os_release
        return os_track_release_channel

    def new_origin(self, target: OpenStackRelease) -> str:
        """Return the new openstack-origin or source configuration.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Repository from which to install.
        :rtype: str
        """
        return f"cloud:{self.series}-{target.codename}"

    def _get_os_origin(self) -> str:
        """Get application configuration for openstack-origin or source.

        :return: Configuration parameter of the charm to set OpenStack origin.
            E.g: cloud:focal-wallaby
        :rtype: str
        """
        for origin in ("openstack-origin", "source"):
            if self.config.get(origin):
                self.origin_setting = origin
                return self.config[origin].get("value", "")

        logger.warning("Failed to get origin for %s, no origin config found", self.name)
        return ""

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

    def pre_upgrade_plan(self, target: OpenStackRelease) -> list[Optional[UpgradeStep]]:
        """Pre Upgrade planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Plan that will add pre upgrade as sub steps.
        :rtype: list[Optional[UpgradeStep]]
        """
        return [
            self._get_upgrade_current_release_packages_plan(),
            self._get_refresh_charm_plan(target),
        ]

    def upgrade_plan(self, target: OpenStackRelease) -> list[Optional[UpgradeStep]]:
        """Upgrade planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :raises HaltUpgradePlanGeneration: When the application halt the upgrade plan generation.
        :return: Plan that will add upgrade as sub steps.
        :rtype: list[Optional[UpgradeStep]]
        """
        if self.current_os_release >= target and self.apt_source_codename >= target:
            msg = (
                f"Application '{self.name}' already configured for release equal or greater "
                f"than {target}. Ignoring."
            )
            logger.info(msg)
            raise HaltUpgradePlanGeneration(msg)

        return [
            self._get_disable_action_managed_plan(),
            self._get_upgrade_charm_plan(target),
            self._get_workload_upgrade_plan(target),
        ]

    def post_upgrade_plan(self, target: OpenStackRelease) -> list[Optional[UpgradeStep]]:
        """Post Upgrade planning.

        Wait until the application reaches the idle state and then check the target workload.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Plan that will add post upgrade as sub steps.
        :rtype: list[Optional[UpgradeStep]]
        """
        return [
            self._get_wait_step(),
            self._get_reached_expected_target_plan(target),
        ]

    def generate_upgrade_plan(self, target: str) -> UpgradeStep:
        """Generate full upgrade plan for an Application.

        :param target: OpenStack codename to upgrade.
        :type target: str
        :return: Full upgrade plan if the Application is able to generate it.
        :rtype: UpgradeStep
        """
        target_version = OpenStackRelease(target)
        upgrade_steps = UpgradeStep(
            description=f"Upgrade plan for '{self.name}' to {target}",
            parallel=False,
        )
        all_steps = (
            self.pre_upgrade_plan(target_version)
            + self.upgrade_plan(target_version)
            + self.post_upgrade_plan(target_version)
        )
        for step in all_steps:
            if step:
                upgrade_steps.add_step(step)
        return upgrade_steps

    def _get_upgrade_current_release_packages_plan(self, parallel: bool = False) -> UpgradeStep:
        """Get Plan for upgrading software packages to the latest of the current release.

        :param parallel: Parallel running, defaults to False
        :type parallel: bool, optional
        :return: Plan for upgrading software packages to the latest of the current release.
        :rtype: UpgradeStep
        """
        return UpgradeStep(
            description=(
                f"Upgrade software packages of '{self.name}' from the current APT repositories"
            ),
            parallel=parallel,
            coro=upgrade_packages(self.status.units.keys(), self.model, self.packages_to_hold),
        )

    def _get_refresh_charm_plan(
        self, target: OpenStackRelease, parallel: bool = False
    ) -> Optional[UpgradeStep]:
        """Get plan for refreshing the current channel.

        This function also identifies if charm comes from charmstore and in that case,
        makes the migration.
        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param parallel: Parallel running, defaults to False
        :type parallel: bool, optional
        :raises ApplicationError: When application has unexpected channel.
        :return: Plan for refreshing the charm.
        :rtype: Optional[UpgradeStep]
        """
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
            return None
        elif self.channel not in self.possible_current_channels:
            raise ApplicationError(
                f"'{self.name}' has unexpected channel: '{self.channel}' for the current workload "
                f"version and OpenStack release: '{self.current_os_release.codename}'. "
                f"Possible channels are: {','.join(self.possible_current_channels)}"
            )

        return UpgradeStep(
            description=description,
            parallel=parallel,
            coro=self.model.upgrade_charm(self.name, channel, switch=switch),
        )

    def _get_upgrade_charm_plan(
        self, target: OpenStackRelease, parallel: bool = False
    ) -> Optional[UpgradeStep]:
        """Get plan for upgrading the charm.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param parallel: Parallel running, defaults to False
        :type parallel: bool, optional
        :return: Plan for upgrading the charm.
        :rtype: Optional[UpgradeStep]
        """
        if self.channel != self.target_channel(target):
            return UpgradeStep(
                description=(
                    f"Upgrade '{self.name}' to the new channel: '{self.target_channel(target)}'"
                ),
                parallel=parallel,
                coro=self.model.upgrade_charm(self.name, self.target_channel(target)),
            )
        return None

    def _get_disable_action_managed_plan(self, parallel: bool = False) -> Optional[UpgradeStep]:
        """Get plan to disable action-managed-upgrade.

        This is used to upgrade as "all-in-one" strategy.

        :param parallel: Parallel running, defaults to False
        :type parallel: bool, optional
        :return: Plan to disable action-managed-upgrade
        :rtype: Optional[UpgradeStep]
        """
        if self.config.get("action-managed-upgrade", {}).get("value", False):
            return UpgradeStep(
                description=(
                    f"Change charm config of '{self.name}' 'action-managed-upgrade' to False."
                ),
                parallel=parallel,
                coro=self.model.set_application_config(
                    self.name, {"action-managed-upgrade": False}
                ),
            )
        return None

    def _get_workload_upgrade_plan(
        self, target: OpenStackRelease, parallel: bool = False
    ) -> Optional[UpgradeStep]:
        """Get workload upgrade plan by changing openstack-origin or source.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param parallel: Parallel running, defaults to False
        :type parallel: bool, optional
        :return: Workload upgrade plan
        :rtype: Optional[UpgradeStep]
        """
        if self.os_origin != self.new_origin(target) and self.origin_setting:
            return UpgradeStep(
                description=(
                    f"Change charm config of '{self.name}' "
                    f"'{self.origin_setting}' to '{self.new_origin(target)}'"
                ),
                parallel=parallel,
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
        return None

    def _get_reached_expected_target_plan(
        self, target: OpenStackRelease, parallel: bool = False
    ) -> UpgradeStep:
        """Get plan to check if application workload has been upgraded.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param parallel: Parallel running, defaults to False
        :type parallel: bool, optional
        :return: Plan to check if application workload has been upgraded
        :rtype: UpgradeStep
        """
        return UpgradeStep(
            description=f"Check if the workload of '{self.name}' has been upgraded",
            parallel=parallel,
            coro=self._check_upgrade(target),
        )

    def _get_wait_step(self) -> UpgradeStep:
        """Get wait step for entire model or application.

        :return: Step waiting for entire model or application itself
        :rtype: UpgradeStep
        """
        if self.wait_for_model:
            description = (
                f"Wait {self.wait_timeout} s for model {self.model.name} to reach the idle state."
            )
            apps = None
        else:
            description = (
                f"Wait {self.wait_timeout} s for app {self.name} to reach the idle state."
            )
            apps = [self.name]

        return UpgradeStep(
            description=description,
            parallel=False,
            coro=self.model.wait_for_idle(self.wait_timeout, apps),
        )
