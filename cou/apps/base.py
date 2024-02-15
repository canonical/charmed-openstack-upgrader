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
from cou.utils.juju_utils import COUMachine, COUModel
from cou.utils.openstack import (
    DISTRO_TO_OPENSTACK_MAPPING,
    OpenStackCodenameLookup,
    OpenStackRelease,
)

logger = logging.getLogger(__name__)

DEFAULT_WAITING_TIMEOUT = 5 * 60  # 5 min


@dataclass(frozen=True)
class ApplicationUnit:
    """Representation of a single unit of application."""

    name: str
    os_version: OpenStackRelease
    machine: COUMachine
    workload_version: str = ""

    def __repr__(self) -> str:
        """Representation of the application unit.

        :return: Representation of the application unit
        :rtype: str
        """
        return f"Unit[{self.name}]-Machine[{self.machine.machine_id}]"


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
    :param units: Units representation of an application.
    :type units: list[ApplicationUnit]
    :raises ApplicationError: When there are no compatible OpenStack release for the
        workload version.
    :raises MismatchedOpenStackVersions: When units part of this application are running mismatched
        OpenStack versions.
    :raises HaltUpgradePlanGeneration: When the class halts the upgrade plan generation.
    :raises CommandRunFailed: When a command fails to run.
    :raises RunUpgradeError: When an upgrade fails.
    """

    # pylint: disable=too-many-instance-attributes

    name: str
    status: ApplicationStatus
    config: dict
    model: COUModel
    charm: str
    machines: dict[str, COUMachine]
    units: list[ApplicationUnit] = field(default_factory=lambda: [])
    packages_to_hold: Optional[list] = field(default=None, init=False)
    wait_timeout: int = field(default=DEFAULT_WAITING_TIMEOUT, init=False)
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

        :raises MismatchedOpenStackVersions: When units part of this application are
        running mismatched OpenStack versions.
        :return: OpenStackRelease object
        :rtype: OpenStackRelease
        """
        os_versions = defaultdict(list)
        for unit in self.units:
            os_versions[unit.os_version].append(unit.name)

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

    def pre_upgrade_steps(
        self, target: OpenStackRelease, units: Optional[list[ApplicationUnit]]
    ) -> list[PreUpgradeStep]:
        """Pre Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate upgrade plan
        :type units: Optional[list[ApplicationUnit]]
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
        units: Optional[list[ApplicationUnit]],
        force: bool,
    ) -> list[UpgradeStep]:
        """Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate upgrade steps
        :type units: Optional[list[ApplicationUnit]]
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
            (
                self._get_enable_action_managed_step()
                if units
                else self._get_disable_action_managed_step()
            ),
            self._get_upgrade_charm_step(target),
            self._get_change_install_repository_step(target),
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

    def generate_upgrade_plan(
        self,
        target: OpenStackRelease,
        units: Optional[list[ApplicationUnit]] = None,
        force: bool = False,
    ) -> ApplicationUpgradePlan:
        """Generate full upgrade plan for an Application.

        Units are passed if the application should upgrade unit by unit.

        :param target: OpenStack codename to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate upgrade plan, defaults to None
        :type units: Optional[list[ApplicationUnit]], optional
        :param force: Whether the plan generation should be forced,defaults to False
        :type force: bool, optional
        :return: Full upgrade plan if the Application is able to generate it.
        :rtype: ApplicationUpgradePlan
        """
        upgrade_steps = ApplicationUpgradePlan(
            description=f"Upgrade plan for '{self.name}' to {target}",
        )
        all_steps = (
            self.pre_upgrade_steps(target, units)
            + self.upgrade_steps(target, units, force)
            + self.post_upgrade_steps(target)
        )
        for step in all_steps:
            if step:
                upgrade_steps.add_step(step)
        return upgrade_steps

    def _get_upgrade_current_release_packages_step(
        self, units: Optional[list[ApplicationUnit]]
    ) -> PreUpgradeStep:
        """Get step for upgrading software packages to the latest of the current release.

        :param units: Units to generate upgrade plan
        :type units: Optional[list[ApplicationUnit]]
        :return: Step for upgrading software packages to the latest of the current release.
        :rtype: PreUpgradeStep
        """
        if not units:
            units = self.units
        step = PreUpgradeStep(
            description=(
                f"Upgrade software packages of '{self.name}' on units "
                f"'{', '.join([unit.name for unit in units])}' from the current APT repositories."
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

    def _get_enable_action_managed_step(self) -> UpgradeStep:
        """Get step to enable action-managed-upgrade.

        This is used to upgrade as "paused-single-unit" strategy.

        :return: Step to enable action-managed-upgrade
        :rtype: UpgradeStep
        """
        if self.config.get("action-managed-upgrade", {}).get("value", False):
            return UpgradeStep()
        return UpgradeStep(
            description=(
                f"Change charm config of '{self.name}' 'action-managed-upgrade' to True."
            ),
            coro=self.model.set_application_config(self.name, {"action-managed-upgrade": True}),
        )

    def _get_pause_unit_step(
        self, unit: ApplicationUnit, dependent: bool = False
    ) -> UnitUpgradeStep:
        """Get the step to pause a unit to upgrade.

        :param unit: Unit to be paused.
        :type unit: ApplicationUnit
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

    def _get_resume_unit_step(
        self, unit: ApplicationUnit, dependent: bool = False
    ) -> UnitUpgradeStep:
        """Get the step to resume a unit after upgrading the workload version.

        :param unit: Unit to be resumed.
        :type unit: ApplicationUnit
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
        self, unit: ApplicationUnit, dependent: bool = False
    ) -> UnitUpgradeStep:
        """Get the step to upgrade a unit.

        :param unit: Unit to be upgraded.
        :type unit: ApplicationUnit
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
