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

"""Application class."""
from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from io import StringIO
from typing import Any, Optional

from juju.client._definitions import ApplicationStatus
from ruamel.yaml import YAML

from cou.exceptions import (
    ApplicationError,
    HaltUpgradePlanGeneration,
    MismatchedOpenStackVersions,
)
from cou.steps import UpgradeStep
from cou.utils.app_utils import upgrade_packages
from cou.utils.juju_utils import (
    async_get_status,
    async_set_application_config,
    async_upgrade_charm,
)
from cou.utils.openstack import (
    OpenStackCodenameLookup,
    OpenStackRelease,
    is_charm_supported,
)

logger = logging.getLogger(__name__)


class AppFactory:
    """Factory class for Application objects."""

    apps_type: dict[str, type[OpenStackApplication]] = {}

    @classmethod
    def create(
        cls,
        name: str,
        status: ApplicationStatus,
        config: dict,
        model_name: str,
        charm: str,
    ) -> Optional[OpenStackApplication]:
        """Create the OpenStackApplication or registered subclasses.

        Applications Subclasses registered with the "register_application"
        decorator can be instantiated and used with their customized methods.
        :param name: Name of the application
        :type name: str
        :param status: Status of the application
        :type status: ApplicationStatus
        :param config: Configuration of the application
        :type config: dict
        :param model_name: Model name
        :type model_name: str
        :param charm: Name of the charm
        :type charm: str
        :return: The OpenStackApplication class or None if not supported.
        :rtype: Optional[OpenStackApplication]
        """
        # pylint: disable=too-many-arguments
        if is_charm_supported(charm):
            app_class = cls.apps_type.get(charm, OpenStackApplication)
            return app_class(
                name=name, status=status, config=config, model_name=model_name, charm=charm
            )
        logger.debug(
            "'%s' is not a supported OpenStack related application and will be ignored.",
            name,
        )
        return None

    @classmethod
    def register_application(
        cls, app_types: list[str]
    ) -> Callable[[type[OpenStackApplication]], type[OpenStackApplication]]:
        """Register Application subclasses.

        Use this method as decorator to register Applications that
        cannot be described appropriately by the OpenStackApplication class.

        Example:
        ceph_types = ["ceph-mon", "ceph-fs", "ceph-radosgw", "ceph-osd"]

        @AppFactory.register_application(ceph_types)
        class Ceph(OpenStackApplication):
            pass
        This is registering the charms "ceph-mon", "ceph-fs", "ceph-radosgw", "ceph-osd"
        to the Ceph class.

        :param app_types: List of charm names the Application sub class should handle.
        :type app_types: list[str]
        :return: The decorated class. E.g: the Ceph class in the example above.
        :rtype: Callable[[type[OpenStackApplication]], type[OpenStackApplication]]
        """

        def decorator(application: type[OpenStackApplication]) -> type[OpenStackApplication]:
            for app_type in app_types:
                cls.apps_type[app_type] = application
            return application

        return decorator


@dataclass
class OpenStackApplication:
    """Representation of a charmed OpenStack application in the deployment.

    :param name: Name of the application
    :type name: str
    :param status: Status of the application.
    :type status: ApplicationStatus
    :param config: Configuration of the application.
    :type config: dict
    :param model_name: Model name.
    :type model_name: str
    :param charm: Name of the charm.
    :type charm: str
    :param charm_origin: Origin of the charm (local, ch, cs and etc.), defaults to ""
    :type charm_origin: str, defaults to ""
    :param os_origin: OpenStack origin of the application. E.g: cloud:focal-wallaby, defaults to ""
    :type os_origin: str, defaults to ""
    :param channel: Channel that the charm tracks. E.g: "ussuri/stable", defaults to ""
    :type channel: str, defaults to ""
    :param units: Units representation of an application.
        E.g: {"keystone/0": {'os_version': 'victoria', 'workload_version': '2:18.1'}}
    :type units: defaultdict[str, dict]
    :raises ApplicationError: When there are no compatible OpenStack release for the
        workload version
    :raises MismatchedOpenStackVersions: When units part of this application are running mismatched
        OpenStack versions.
    :raises HaltUpgradePlanGeneration: When the class halts the upgrade plan generation
    :raises PackageUpgradeError: When the package upgrade fails.
    """

    # pylint: disable=too-many-instance-attributes

    name: str
    status: ApplicationStatus
    config: dict
    model_name: str
    charm: str
    charm_origin: str = ""
    os_origin: str = ""
    units: defaultdict[str, dict] = field(default_factory=lambda: defaultdict(dict))

    def __post_init__(self) -> None:
        """Initialize the Application dataclass."""
        self.channel = self.status.charm_channel
        self.charm_origin = self.status.charm.split(":")[0]
        self.os_origin = self._get_os_origin()
        # subordinates don't have units
        units = getattr(self.status, "units", {})
        for unit in units.keys():
            workload_version = self.status.units[unit].workload_version
            self.units[unit]["workload_version"] = workload_version
            compatible_os_versions = OpenStackCodenameLookup.find_compatible_versions(
                self.charm, workload_version
            )
            # NOTE(gabrielcocenza) get the latest compatible OpenStack version.
            if compatible_os_versions:
                unit_os_version = max(compatible_os_versions)
                self.units[unit]["os_version"] = unit_os_version
            else:
                logger.error(
                    (
                        "'%s' with workload version %s has no compatible OpenStack "
                        "release in the lookup."
                    ),
                    self.name,
                    workload_version,
                )
                raise ApplicationError()

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
                "model_name": self.model_name,
                "charm": self.charm,
                "charm_origin": self.charm_origin,
                "os_origin": self.os_origin,
                "channel": self.channel,
                "units": {
                    unit: {
                        "workload_version": details.get("workload_version", ""),
                        "os_version": str(details.get("os_version")),
                    }
                    for unit, details in self.units.items()
                },
            }
        }
        yaml = YAML()
        with StringIO() as stream:
            yaml.dump(summary, stream)
            return stream.getvalue()

    @property
    def expected_current_channel(self) -> str:
        """Return the expected current channel based on the current OpenStack release.

        Note that this is not necessarily equal to the "channel" property since it is
        determined based on the workload version.
        :return: The expected current channel for the application. E.g: ussuri/stable
        :rtype: str
        """
        return f"{self.current_os_release.codename}/stable"

    def target_channel(self, target: OpenStackRelease) -> str:
        """Return the channel based on the target passed.

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

        :raises MismatchedOpenStackVersions: Raise MismatchedOpenStackVersions if units of
            an application are running mismatched OpenStack versions.
        :return: OpenStackRelease object
        :rtype: OpenStackRelease
        """
        os_versions = {unit_values["os_version"] for unit_values in self.units.values()}

        if len(os_versions) == 1:
            return os_versions.pop()
        # NOTE (gabrielcocenza) on applications that use single-unit or paused-single-unit
        # upgrade methods, more than one version can be found.
        logger.error(
            (
                "Units of application %s are running mismatched OpenStack versions: %s. "
                "This is not currently handled."
            ),
            self.name,
            os_versions,
        )
        raise MismatchedOpenStackVersions()

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
        status = await async_get_status()
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
            logger.error(
                "Units '%s' failed to upgrade to %s",
                ", ".join(units_not_upgraded),
                str(target),
            )
            raise ApplicationError()

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
        :raises HaltUpgradePlanGeneration: When the application halt the upgrade plan generation
        :return: Plan that will add upgrade as sub steps.
        :rtype: list[Optional[UpgradeStep]]
        """
        if self.current_os_release >= target:
            logger.info(
                (
                    "Application: '%s' already running %s that is equal or greater "
                    "version than %s. Ignoring."
                ),
                self.name,
                str(self.current_os_release),
                target,
            )
            raise HaltUpgradePlanGeneration()
        return [
            self._get_disable_action_managed_plan(),
            self._get_upgrade_charm_plan(target),
            self._get_workload_upgrade_plan(target),
        ]

    def post_upgrade_plan(self, target: OpenStackRelease) -> list[UpgradeStep]:
        """Post Upgrade planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Plan that will add post upgrade as sub steps.
        :rtype: list[UpgradeStep]
        """
        return [self._get_reached_expected_target_plan(target)]

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
            function=None,
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
        :return plan: Plan for upgrading software packages to the latest of the current release.
        :type plan: UpgradeStep
        """
        return UpgradeStep(
            description=(
                f"Upgrade software packages of '{self.name}' to the latest "
                f"'{self.current_os_release}' release"
            ),
            parallel=parallel,
            function=upgrade_packages,
            units=self.status.units.keys(),
            model_name=self.model_name,
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
        :return: Plan for refreshing the charm.
        :rtype: Optional[UpgradeStep]
        """
        switch = None
        description = (
            f"Changing '{self.name}' channel from: '{self.channel}' "
            f"to: '{self.expected_current_channel}'"
        )

        try:
            # get the OpenStack release from the channel track of the application.
            os_track_release_channel = OpenStackRelease(self.channel.split("/", maxsplit=1)[0])
        except ValueError:
            logger.debug("The current channel does not exist or is unexpectedly formatted")
            os_track_release_channel = self.current_os_release

        if self.charm_origin == "cs":
            description = f"Migration of '{self.name}' from charmstore to charmhub"
            switch = f"ch:{self.charm}"
        elif self.channel == self.expected_current_channel:
            description = (
                f"Refresh '{self.name}' to the latest revision of "
                f"'{self.expected_current_channel}'"
            )
        elif os_track_release_channel >= target:
            logger.info(
                (
                    "Skipping charm refresh for %s, its channel is already set to %s."
                    "release than target %s"
                ),
                self.name,
                self.channel,
                str(target),
            )
            return None

        return UpgradeStep(
            description=description,
            parallel=parallel,
            function=async_upgrade_charm,
            application_name=self.name,
            channel=self.expected_current_channel,
            model_name=self.model_name,
            switch=switch,
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
                function=async_upgrade_charm,
                application_name=self.name,
                channel=self.target_channel(target),
                model_name=self.model_name,
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
                    f"Change charm config of '{self.name}' " "'action-managed-upgrade' to False."
                ),
                parallel=parallel,
                function=async_set_application_config,
                application_name=self.name,
                configuration={"action-managed-upgrade": False},
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
        if self.os_origin != self.new_origin(target):
            return UpgradeStep(
                description=(
                    f"Change charm config of '{self.name}' "
                    f"'{self.origin_setting}' to '{self.new_origin(target)}'"
                ),
                parallel=parallel,
                function=async_set_application_config,
                application_name=self.name,
                configuration={self.origin_setting: self.new_origin(target)},
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
            function=self._check_upgrade,
            target=target,
        )
