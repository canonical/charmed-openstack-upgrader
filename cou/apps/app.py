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
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from io import StringIO
from typing import Any, Callable, Dict, List, Optional, Type

from juju.client._definitions import ApplicationStatus
from ruamel.yaml import YAML

from cou.steps import UpgradeStep
from cou.utils.juju_utils import (
    async_get_status,
    async_set_application_config,
    async_upgrade_charm,
)
from cou.utils.openstack import (
    CHARM_TYPES,
    LTS_SERIES,
    OpenStackCodenameLookup,
    OpenStackRelease,
)

logger = logging.getLogger(__name__)


class AppFactory:
    """Factory class for Application objects."""

    apps_type: Dict[str, Type[Application]] = {}

    @classmethod
    def create(cls, app_type: str, **params: Any) -> Application:
        """Create the standard Application or registered subclasses.

        Applications Subclasses registered with the "register_application"
        decorator can be instantiate and used with their customized methods.
        :param app_type: App type to be accessed on apps_type dictionary.
        :type app_type: str
        :return: Standard Application class or registered sub-classes.
        :rtype: Application
        """
        if app_type not in cls.apps_type:
            return Application(**params)
        return cls.apps_type[app_type](**params)

    @classmethod
    def register_application(
        cls, app_types: List[str]
    ) -> Callable[[type[Application]], type[Application]]:
        """Register Application subclasses.

        Use this method as decorator to register Applications that
        have special needs.

        :param app_types: List of charms to register the Application sub class.
        :type app_types: List[str]
        """

        def decorator(application: Type[Application]) -> Type[Application]:
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
    os_origin: Optional[str] = None
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
                        "os_version": str(details.get("os_version", "")),
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
        if self.current_os_release:
            return f"{self.current_os_release}/stable"
        return None

    @property
    def next_channel(self) -> Optional[str]:
        """Return the next channel based on the next OpenStack release.

        If it's not possible to determine the next OpenStack release, the value is None.
        :return: The next channel for the application.
        :rtype: Optional[str]
        """
        if self.current_os_release:
            return f"{self.next_os_release}/stable"
        return None

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

        :return: OpenStackRelease object
        :rtype: Optional[OpenStackRelease]
        """
        os_versions = {unit_values.get("os_version") for unit_values in self.units.values()}
        if len(os_versions) == 1:
            return list(os_versions)[0]
        return None

    @property
    def next_os_release(self) -> Optional[str]:
        """Next OpenStack release codename of the application.

        :return: Next OpenStack release codename.
        :rtype: Optional[str]
        """
        if self.current_os_release:
            return self.current_os_release.next_release
        return None

    def os_origin_release(self, target: str) -> Optional[OpenStackRelease]:
        """Identify the OpenStack release set on openstack-origin or source config.

        :return: OpenStackRelease object or None if the app doesn't have os_origin config.
        :rtype: Optional[OpenStackRelease]
        """
        os_origin_release = None
        if self.os_origin is not None:
            os_origin_release = self.os_origin.rsplit("-", maxsplit=1)[-1]
            match os_origin_release:
                case "distro":
                    os_origin_release = LTS_SERIES[self.series]
                case "":
                    os_origin_release = OpenStackRelease(target).previous_release
        return OpenStackRelease(os_origin_release) if os_origin_release else None

    def new_origin(self, target: str) -> Optional[str]:
        """Return the new openstack-origin or source configuration.

        :param target: Target to upgrade.
        :type target: str
        :return: Repository from which to install.
        :rtype: Optional[str]
        """
        if self.current_os_release is None:
            return None
        os_origin_release = self.os_origin_release(target)
        if os_origin_release:
            if os_origin_release <= target:
                return f"cloud:{self.series}-{target}"
        return None

    def _get_os_origin(self) -> Optional[str]:
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
        return None

    async def check_upgrade(self) -> None:
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

        Applications where it's not possible to identify the current OpenStack release,
        should not generate upgrade plan.
        :return: True if can generate a plan, else False.
        :rtype: bool
        """
        if not self.current_os_release:
            logger.warning("Not possible to generate upgrade plan for '%s'.", self.name)
            logger.warning("'%s' might need manual intervention to upgrade.", self.name)
            return False
        return True

    def pre_upgrade_plan(self, plan: UpgradeStep) -> None:
        """Pre Upgrade planning.

        :param plan: Plan that will add pre upgrade as sub steps.
        :type plan: UpgradeStep
        """
        self.refresh_current_channel(plan)

    def upgrade_plan(self, plan: UpgradeStep, target: str) -> None:
        """Upgrade planning.

        :param plan: Plan that will add upgrade as sub steps.
        :type plan: UpgradeStep
        """
        logger.debug("Running upgrade plan to %s", target)
        self.disable_action_managed(plan)
        self.refresh_next_channel(plan)
        self.workload_upgrade(plan, target)

    def post_upgrade_plan(self, plan: UpgradeStep) -> None:
        """Post Upgrade planning.

        :param plan: Plan that will add post upgrade as sub steps.
        :type plan: UpgradeStep
        """
        self.reached_expected_target(plan)

    def generate_upgrade_plan(self, target: str) -> Optional[UpgradeStep]:
        """Generate full upgrade plan for an Application.

        :return: Full upgrade plan if the Application is able to generate it.
        :rtype: Optional[UpgradeStep]
        """
        target_version = OpenStackRelease(target)

        if not self.can_generate_upgrade_plan():
            logger.warning("Aborting upgrade plan for '%s'", self.name)
            return None
        if self.current_os_release >= target_version:
            logger.warning(
                "Application: '%s' already on a newer version than %s. Aborting upgrade.",
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
        self.pre_upgrade_plan(upgrade_plan)
        self.upgrade_plan(upgrade_plan, target)
        self.post_upgrade_plan(upgrade_plan)
        return upgrade_plan

    def refresh_current_channel(self, plan: UpgradeStep, parallel: bool = False) -> None:
        """Add Plan for refresh current channel.

        This function also identify if charm comes from charmstore and in that case,
        makes the migration.
        :param plan: Plan to add refresh current channel as sub step.
        :type plan: UpgradeStep
        :param parallel: Parallel running, defaults to False
        :type parallel: bool
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
            return

        if self.charm_origin == "cs":
            description = f"Migration of '{self.name}' from charmstore to charmhub"
            switch = f"ch:{self.charm}"

        elif self.channel not in (self.expected_current_channel, self.next_channel):
            description = (
                f"Changing '{self.name}' channel from: '{self.channel}' "
                f"to: '{self.expected_current_channel}'"
            )

        plan.add_step(
            UpgradeStep(
                description=description,
                parallel=parallel,
                function=async_upgrade_charm,
                application_name=self.name,
                channel=self.expected_current_channel,
                model_name=self.model_name,
                switch=switch,
            )
        )

    def refresh_next_channel(self, plan: UpgradeStep, parallel: bool = False) -> None:
        """Add plan for refresh to next channel.

        :param plan: Plan to add refresh next channel as sub step.
        :type plan: UpgradeStep
        :param parallel: Parallel running, defaults to False
        :type parallel: bool
        """
        if self.channel != self.next_channel:
            plan.add_step(
                UpgradeStep(
                    description=f"Refresh '{self.name}' to the new channel: '{self.next_channel}'",
                    parallel=parallel,
                    function=async_upgrade_charm,
                    application_name=self.name,
                    channel=self.next_channel,
                    model_name=self.model_name,
                )
            )

    def disable_action_managed(self, plan: UpgradeStep, parallel: bool = False) -> None:
        """Disable action-managed-upgrade to upgrade as "all-in-one" strategy.

        :param plan: Plan to disable action managed upgrade as sub step.
        :type plan: UpgradeStep
        :param parallel: Parallel running, defaults to False
        :type parallel: bool
        """
        if self.config.get("action-managed-upgrade"):
            if self.config["action-managed-upgrade"].get("value", False):
                plan.add_step(
                    UpgradeStep(
                        description=(
                            f"Change charm config of '{self.name}' "
                            "'action-managed-upgrade' to False."
                        ),
                        parallel=parallel,
                        function=async_set_application_config,
                        application_name=self.name,
                        configuration={"action-managed-upgrade": False},
                    )
                )

    def workload_upgrade(self, plan: UpgradeStep, target: str, parallel: bool = False) -> None:
        """Change openstack-origin or source to the repository from which to install.

        :param plan: Plan to add workload upgrade as sub step.
        :type plan: UpgradeStep
        :param parallel: Parallel running, defaults to False
        :type parallel: bool, optional
        """
        if self.os_origin != self.new_origin(target):
            plan.add_step(
                UpgradeStep(
                    description=(
                        f"Change charm config of '{self.name}' "
                        f"'{self.origin_setting}' to '{self.new_origin(target)}'"
                    ),
                    parallel=parallel,
                    function=async_set_application_config,
                    application_name=self.name,
                    configuration={self.origin_setting: self.new_origin(target)},
                )
            )
        else:
            logger.warning(
                "App: %s already have %s set to %s",
                self.name,
                self.origin_setting,
                self.new_origin(target),
            )

    def reached_expected_target(self, plan: UpgradeStep, parallel: bool = False) -> None:
        """Add plan to check if application workload has upgraded.

        :param plan: Plan to add check of workload upgrade as sub step.
        :type plan: UpgradeStep
        :param parallel: Parallel running, defaults to False
        :type parallel: bool, optional
        """
        plan.add_step(
            UpgradeStep(
                description=f"Check if workload of '{self.name}' has upgraded",
                parallel=parallel,
                function=self.check_upgrade,
            )
        )


class SpecialApplications(ABC, Application):
    """Application for charms that can have multiple OpenStack releases for a workload."""

    @property
    @abstractmethod
    def openstack_map(self) -> Dict:
        """Abstract property of openstack_map.

        :return: Dictionary containing OpenStackRelease codename and the expected channel.
        :rtype: Dict
        """

    @property
    def expected_current_channel(self) -> Optional[str]:
        """Return the expected current channel based on the current OpenStack release.

        Note that this is not necessary equal to the "channel" property if the application
        has wrong configuration for it. If it's not possible to determine the current
        OpenStack release, the value is None.

        :return: The expected current channel for the application.
        :rtype: Optional[str]
        """
        if self.current_os_release:
            return f"{self.openstack_map[self.current_os_release.codename]}/stable"
        return None

    @property
    def next_channel(self) -> Optional[str]:
        """Return the next channel based on the next OpenStack release.

        If it's not possible to determine the next OpenStack release, the value is None.
        :return: The next channel for the application.
        :rtype: Optional[str]
        """
        if self.current_os_release:
            if self.next_os_release:
                return f"{self.openstack_map[self.next_os_release]}/stable"
        return None

    def generate_upgrade_plan(self, target: str) -> Optional[UpgradeStep]:
        """Generate full upgrade plan for special Applications.

        :return: Full upgrade plan if the Application is able to generate it.
        :rtype: Optional[UpgradeStep]
        """
        if not self.can_generate_upgrade_plan():
            logger.warning("Aborting upgrade plan for '%s'", self.name)
            return None
        os_origin_release = self.os_origin_release(target)
        if (
            self.current_os_release
            and self.current_os_release >= target
            and os_origin_release
            and os_origin_release > target
        ):
            logger.warning(
                "Application: '%s' already on a newer version than %s. Aborting upgrade.",
                self.name,
                target,
            )
            return None
        upgrade_plan = UpgradeStep(
            description=f"Upgrade plan for '{self.name}' to: {target}",
            parallel=False,
            function=None,
        )
        self.pre_upgrade_plan(upgrade_plan)
        self.upgrade_plan(upgrade_plan, target)
        self.post_upgrade_plan(upgrade_plan)
        return upgrade_plan

    def upgrade_plan(self, plan: UpgradeStep, target: str) -> None:
        """Upgrade planning.

        :param plan: Plan that will add upgrade as sub steps.
        :type plan: UpgradeStep
        """
        self.disable_action_managed(plan)
        if self.current_os_release and self.current_os_release <= self.os_origin_release(target):
            self.refresh_next_channel(plan)
        self.workload_upgrade(plan, target)


@AppFactory.register_application(["rabbitmq-server"])
class RabbitMQServer(SpecialApplications):
    """RabbitMQ server Application."""

    # NOTE (gabrielcocenza)
    # https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html

    @property
    def openstack_map(self) -> Dict:
        return {
            "ussuri": "3.8",
            "victoria": "3.8",
            "wallaby": "3.8",
            "xena": "3.8",
            "yoga": "3.8",
            "zed": "3.9",
        }


@AppFactory.register_application(CHARM_TYPES["ceph"])
class Ceph(SpecialApplications):
    """Ceph charms Application."""

    # NOTE (gabrielcocenza)
    # https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html
    @property
    def openstack_map(self) -> Dict:
        return {
            "ussuri": "octopus",
            "victoria": "octopus",
            "wallaby": "pacific",
            "xena": "pacific",
            "yoga": "quincy",
            "zed": "quincy",
        }
