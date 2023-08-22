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

from cou.exceptions import MismatchedOpenStackVersions
from cou.steps import UpgradeStep
from cou.utils.juju_utils import (
    async_get_status,
    async_set_application_config,
    async_upgrade_charm,
)
from cou.utils.openstack import CHARM_TYPES, OpenStackCodenameLookup, OpenStackRelease

logger = logging.getLogger(__name__)


class AppFactory:
    """Factory class for Application objects."""

    apps_type: dict[str, type[Application]] = {}

    @classmethod
    def create(cls, app_type: str, **params: Any) -> Application:
        """Create the standard Application or registered subclasses.

        Applications Subclasses registered with the "register_application"
        decorator can be instantiated and used with their customized methods.
        :param app_type: App type to be accessed on apps_type dictionary.
        :type app_type: str
        :return: Standard Application class or registered sub-classes.
        :rtype: Application
        """
        app_class = cls.apps_type.get(app_type, Application)
        return app_class(**params)

    @classmethod
    def register_application(
        cls, app_types: list[str]
    ) -> Callable[[type[Application]], type[Application]]:
        """Register Application subclasses.

        Use this method as decorator to register Applications that
        have special needs.

        :param app_types: List of charm names the Application sub class should handle.
        :type app_types: list[str]
        """

        def decorator(application: type[Application]) -> type[Application]:
            for app_type in app_types:
                cls.apps_type[app_type] = application
            return application

        return decorator


@dataclass
class Application:
    """Representation of an application in the deployment.

    :param name: name of the application
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
    """

    # pylint: disable=too-many-instance-attributes

    name: str
    status: ApplicationStatus
    config: dict
    model_name: str
    charm: str
    charm_origin: str = ""
    os_origin: str = ""
    channel: str = ""
    units: defaultdict[str, dict] = field(default_factory=lambda: defaultdict(dict))

    def __post_init__(self) -> None:
        """Initialize the Application dataclass."""
        self.channel = self.status.charm_channel
        self.charm_origin = self.status.charm.split(":")[0]
        self.os_origin = self._get_os_origin()
        for unit in self.status.units.keys():
            workload_version = self.status.units[unit].workload_version
            self.units[unit]["workload_version"] = workload_version
            compatible_os_versions = OpenStackCodenameLookup.lookup(self.charm, workload_version)
            # NOTE(gabrielcocenza) get the latest compatible OpenStack version.
            if compatible_os_versions:
                unit_os_version = max(compatible_os_versions)
                self.units[unit]["os_version"] = unit_os_version
            else:
                self.units[unit]["os_version"] = None
                logger.warning(
                    "No compatible OpenStack versions were found to %s with workload version %s",
                    self.name,
                    workload_version,
                )

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
    def expected_current_channel(self) -> Optional[str]:
        """Return the expected current channel based on the current OpenStack release.

        Note that this is not necessary equal to the "channel" property if the application
        has wrong configuration for it. If it's not possible to determine the current
        OpenStack release, the value is None.
        :return: The expected current channel for the application.
        :rtype: Optional[str]
        """
        return f"{self.current_os_release}/stable" if self.current_os_release else None

    @property
    def next_channel(self) -> Optional[str]:
        """Return the next channel based on the next OpenStack release.

        If it's not possible to determine the next OpenStack release, the value is None.
        :return: The next channel for the application.
        :rtype: Optional[str]
        """
        return f"{self.next_os_release}/stable" if self.next_os_release else None

    @property
    def series(self) -> str:
        """Ubuntu series of the application.

        :return: Ubuntu series of application. E.g: focal
        :rtype: str
        """
        return self.status.series

    @property
    def current_os_release(self) -> Optional[OpenStackRelease]:
        """Current OpenStack Release of the application.

        :raises MismatchedOpenStackVersions: Raise MismatchedOpenStackVersions if units of
            an application are running mismatched OpenStack versions.
        :return: OpenStackRelease object
        :rtype: OpenStackRelease
        """
        os_versions = {unit_values.get("os_version") for unit_values in self.units.values()}
        if not os_versions:
            # TODO(gabrielcocenza) subordinate charms doesn't have units on ApplicationStatus and
            # return an empty set. This should be handled by a future implementation of
            # subordinate applications class.
            return None
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

    @property
    def next_os_release(self) -> Optional[str]:
        """Next OpenStack release codename of the application.

        :return: Next OpenStack release codename.
        :rtype: Optional[str]
        """
        return self.current_os_release.next_release if self.current_os_release else None

    @property
    def new_origin(self) -> Optional[str]:
        """Return the new openstack-origin or source configuration.

        :return: Repository from which to install.
        :rtype: Optional[str]
        """
        return f"cloud:{self.series}-{self.next_os_release}" if self.next_os_release else None

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

    async def _check_upgrade(self) -> None:
        """Check if an application has upgraded its workload version."""
        status = await async_get_status()
        app_status = status.applications.get(self.name)
        units_not_upgraded = []
        for unit in app_status.units.keys():
            workload_version = app_status.units[unit].workload_version
            compatible_os_versions = OpenStackCodenameLookup.lookup(self.charm, workload_version)
            if self.next_os_release not in compatible_os_versions:
                units_not_upgraded.append(unit)
        if units_not_upgraded:
            logger.error(
                "App: '%s' has units: '%s' didn't upgrade to %s",
                self.name,
                ", ".join(units_not_upgraded),
                self.next_os_release,
            )

    def can_generate_upgrade_plan(self) -> bool:
        """Check if application can generate an upgrade plan.

        Applications where it's not possible to identify the next OpenStack release,
        should not generate upgrade plan.
        :return: True if can generate a plan, else False.
        :rtype: bool
        """
        if not self.next_os_release:
            logger.warning("Not possible to generate upgrade plan for '%s'.", self.name)
            logger.warning("'%s' might need manual intervention to upgrade.", self.name)
            return False
        return True

    def pre_upgrade_plan(self) -> list[Optional[UpgradeStep]]:
        """Pre Upgrade planning.

        :return: Plan that will add pre upgrade as sub steps.
        :rtype: list[Optional[UpgradeStep]]
        """
        return [self._get_refresh_charm_plan()]

    def upgrade_plan(self) -> list[Optional[UpgradeStep]]:
        """Upgrade planning.

        :return: Plan that will add upgrade as sub steps.
        :rtype: list[Optional[UpgradeStep]]
        """
        return [
            self._get_disable_action_managed_plan(),
            self._get_upgrade_charm_plan(),
            self._get_workload_upgrade_plan(),
        ]

    def post_upgrade_plan(self) -> list[UpgradeStep]:
        """Post Upgrade planning.

        :return: Plan that will add post upgrade as sub steps.
        :rtype: list[UpgradeStep]
        """
        return [self._get_reached_expected_target_plan()]

    def generate_upgrade_plan(self, target: str) -> Optional[UpgradeStep]:
        """Generate full upgrade plan for an Application.

        :param target: OpenStack codename to upgrade.
        :type target: str
        :return: Full upgrade plan if the Application is able to generate it.
        :rtype: Optional[UpgradeStep]
        """
        target_version = OpenStackRelease(target)

        if not self.can_generate_upgrade_plan():
            logger.warning("Aborting upgrade plan for '%s'", self.name)
            return None
        if self.current_os_release >= target_version:
            logger.warning(
                "Application: '%s' already on a newer version than %s. Ignoring.",
                self.name,
                target,
            )
            return None
        upgrade_plan = UpgradeStep(
            description=(
                f"Upgrade plan for '{self.name}' from: {self.current_os_release} "
                f"to {self.next_os_release}"
            ),
            parallel=False,
            function=None,
        )
        all_steps = self.pre_upgrade_plan() + self.upgrade_plan() + self.post_upgrade_plan()
        for step in all_steps:
            if step:
                upgrade_plan.add_step(step)
        return upgrade_plan

    def _get_refresh_charm_plan(self, parallel: bool = False) -> Optional[UpgradeStep]:
        """Get plan for refreshing the current channel.

        :param parallel: Parallel running, defaults to False
        :type parallel: bool, optional
        :return: Plan for refreshing the current channel.
        :rtype: Optional[UpgradeStep]
        """
        switch = None
        description = (
            f"Refresh '{self.name}' to the latest revision of '{self.expected_current_channel}'"
        )

        if self.channel == self.next_channel:
            logger.warning(
                "App: %s already has the channel set for the next OpenStack version %s",
                self.name,
                self.next_os_release,
            )
            return None

        if self.charm_origin == "cs":
            description = f"Migration of '{self.name}' from charmstore to charmhub"
            switch = f"ch:{self.charm}"

        elif self.channel not in (self.expected_current_channel, self.next_channel):
            description = (
                f"Changing '{self.name}' channel from: '{self.channel}' "
                f"to: '{self.expected_current_channel}'"
            )

        return UpgradeStep(
            description=description,
            parallel=parallel,
            function=async_upgrade_charm,
            application_name=self.name,
            channel=self.expected_current_channel,
            model_name=self.model_name,
            switch=switch,
        )

    def _get_upgrade_charm_plan(self, parallel: bool = False) -> Optional[UpgradeStep]:
        """Get plan for upgrading the charm.

        :param parallel: Parallel running, defaults to False
        :type parallel: bool, optional
        :return: Plan for upgrading the charm.
        :rtype: Optional[UpgradeStep]
        """
        if self.channel != self.next_channel:
            return UpgradeStep(
                description=f"Refresh '{self.name}' to the new channel: '{self.next_channel}'",
                parallel=parallel,
                function=async_upgrade_charm,
                application_name=self.name,
                channel=self.next_channel,
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

    def _get_workload_upgrade_plan(self, parallel: bool = False) -> Optional[UpgradeStep]:
        """Get workload upgrade plan by changing openstack-origin or source.

        :param parallel: Parallel running, defaults to False
        :type parallel: bool, optional
        :return: Workload upgrade plan
        :rtype: Optional[UpgradeStep]
        """
        if self.os_origin != self.new_origin:
            return UpgradeStep(
                description=(
                    f"Change charm config of '{self.name}' "
                    f"'{self.origin_setting}' to '{self.new_origin}'"
                ),
                parallel=parallel,
                function=async_set_application_config,
                application_name=self.name,
                configuration={self.origin_setting: self.new_origin},
            )
        logger.warning(
            "App: %s already have %s set to %s",
            self.name,
            self.origin_setting,
            self.new_origin,
        )
        return None

    def _get_reached_expected_target_plan(self, parallel: bool = False) -> UpgradeStep:
        """Get plan to check if application workload has upgraded.

        :param parallel: Parallel running, defaults to False
        :type parallel: bool, optional
        :return: Plan to check if application workload has upgraded
        :rtype: UpgradeStep
        """
        return UpgradeStep(
            description=f"Check if the workload of '{self.name}' has been upgraded",
            parallel=parallel,
            function=self._check_upgrade,
        )


@AppFactory.register_application(CHARM_TYPES["ceph"])
class Ceph(Application):
    """Ceph charms Application."""

    # NOTE (gabrielcocenza)
    # https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html
    openstack_map = {
        "ussuri": "octopus",
        "victoria": "octopus",
        "wallaby": "pacific",
        "xena": "pacific",
        "yoga": "quincy",
        "zed": "quincy",
    }

    @property
    def expected_current_channel(self) -> Optional[str]:
        """Return the expected current channel based on the current OpenStack release.

        Note that this is not necessary equal to the "channel" property if the application
        has wrong configuration for it. If it's not possible to determine the current
        OpenStack release, the value is None.

        :return: The expected current channel for the application.
        :rtype: Optional[str]
        """
        return (
            f"{self.openstack_map[self.current_os_release.codename]}/stable"
            if self.current_os_release
            else None
        )

    @property
    def next_channel(self) -> Optional[str]:
        """Return the next channel based on the next OpenStack release.

        If it's not possible to determine the next OpenStack release, the value is None.
        :return: The next channel for the application.
        :rtype: Optional[str]
        """
        return (
            f"{self.openstack_map[self.next_os_release]}/stable" if self.next_os_release else None
        )
