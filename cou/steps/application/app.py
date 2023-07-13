# Copyright 2023 Canonical Limited.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Class Application."""
from __future__ import annotations

import logging
from collections import defaultdict
from io import StringIO
from typing import Any, Iterable

from juju.client._definitions import ApplicationStatus
from ruamel.yaml import YAML

from cou.steps import UpgradeStep
from cou.utils.juju_utils import async_set_application_config, async_upgrade_charm
from cou.utils.openstack import CHARM_TYPES, get_os_code_info
from cou.utils.os_versions import CompareOpenStack
from cou.utils.upgrade_utils import determine_next_openstack_release


class Application:
    subclasses = {}
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
    :type charm_origin: str, optional
    :param os_origin: Openstack origin of the application. E.g: cloud:focal-wallaby, defaults to ""
    :type os_origin: str, optional
    :param channel: Channel that the charm tracks. E.g: "ussuri/stable", defaults to ""
    :type channel: str, optional
    :param units: Units representation of an application.
        E.g: {"keystone/0": {'os_version': 'victoria', 'workload_version': '2:18.1'}}
    :type units: defaultdict[str, dict]
    """

    def __init__(
        self,
        name: str,
        status: ApplicationStatus,
        config: dict,
        model_name: str,
        charm: str,
    ):
        self.name = name
        self.status = status
        self.config = config
        self.model_name = model_name
        self.charm = charm
        self.units = defaultdict(dict)
        self.os_origin = self._get_os_origin()
        self.current_os_release = None
        self.next_os_release = None
        os_versions = set()
        for unit in self.status.units.keys():
            workload_version = self.status.units[unit].workload_version
            self.units[unit]["workload_version"] = workload_version
            unit_os_version = self._get_current_os_version(workload_version)
            self.units[unit]["os_version"] = unit_os_version
            if unit_os_version:
                os_versions.add(unit_os_version)
        if os_versions:
            os_sequence = sorted(list(os_versions), key=CompareOpenStack)
            self.current_os_release = os_sequence[0]
            _, self.next_os_release = determine_next_openstack_release(os_sequence[0])

    @classmethod
    def register_subclass(cls, app_type):
        def decorator(subclass):
            cls.subclasses[app_type] = subclass
            return subclass

        return decorator

    @classmethod
    def create(cls, app_type, **params):
        if app_type not in cls.subclasses:
            return Application(**params)
        return cls.subclasses[app_type](params)

    @property
    def channel(self) -> str:
        """Channel of the application.

        :return: Channel of the application. Eg: ussuri/stable
        :rtype: str
        """
        return self.status.charm_channel

    @property
    def charm_origin(self) -> str:
        """Origin of the application.

        :return: Origin of the charm. Eg: ch
        :rtype: str
        """
        return self.status.charm.split(":")[0]

    @property
    def series(self) -> str:
        """Series of application.

        :return: Series of application. E.g: focal
        :rtype: str
        """
        return self.status.series

    @property
    def current_channel(self) -> str:
        return f"{self.current_os_release}/stable"

    @property
    def next_channel(self) -> str:
        return f"{self.next_os_release}/stable"

    @property
    def new_origin(self) -> str:
        return f"cloud:{self.series}-{self.next_os_release}"

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
                        "os_version": details.get("os_version", ""),
                    }
                    for unit, details in self.units.items()
                },
            }
        }
        yaml = YAML()
        with StringIO() as stream:
            yaml.dump(summary, stream)
            return stream.getvalue()

    def _get_representative_workload_pkg(self) -> str:
        """Get the representative package name of a charm workload.

        :return: Package name that represents the charm workload. E.g: cinder-common
        :rtype: str
        """
        try:
            package = CHARM_TYPES[self.charm]["representative_workload_pkg"]
        except KeyError:
            logging.warning(
                "Representative workload package not found for application: %s", self.name
            )
            package = ""
        return package

    def _get_current_os_version(self, workload_version: str) -> str:
        """Get the openstack version of a unit.

        :param workload_version: Version of the workload of a charm. E.g: 10.2.6
        :type workload_version: str
        :return: OpenStack version detected. If not detected return an empty string.
            E.g: ussuri.
        :rtype: str
        """
        version = ""
        package = self._get_representative_workload_pkg()

        if package and workload_version:
            version = get_os_code_info(package, workload_version)
        return version

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

        return ""

    def add_plan_refresh_current_channel(self, plan) -> UpgradeStep:
        if self.charm_origin == "cs":
            plan = self._add_plan_charmhub_migration(plan)
            return plan
        plan = self._add_plan_change_current_channel(plan)
        plan = self._add_plan_update_current_channel(plan)
        return plan

    def _add_plan_charmhub_migration(self, plan) -> UpgradeStep:
        plan.add_step(
            UpgradeStep(
                description=f"App: {self.name} -> Migration from charmstore to charmhub",
                parallel=False,
                function=async_upgrade_charm,
                application_name=self.name,
                channel=self.current_channel,
                model_name=self.model_name,
                switch=f"ch:{self.charm}",
            )
        )
        return plan

    def _add_plan_change_current_channel(self, plan) -> UpgradeStep:
        if self.channel != self.current_channel and self.channel != self.next_channel:
            plan.add_step(
                UpgradeStep(
                    description=f"Changing {self.name} channel from: {self.channel} to: {self.current_channel}",
                    parallel=False,
                    function=async_upgrade_charm,
                    application_name=self.name,
                    channel=self.current_channel,
                )
            )
        return plan

    def _add_plan_update_current_channel(self, plan) -> UpgradeStep:
        if self.channel == self.next_channel:
            logging.warning(
                "App: %s already has the channel set for the next OpenStack version %s",
                self.name,
                self.next_os_release,
            )
        else:
            plan.add_step(
                UpgradeStep(
                    description=f"Refresh {self.name} to the latest revision of {self.current_channel}",
                    parallel=False,
                    function=async_upgrade_charm,
                    application_name=self.name,
                )
            )
        return plan

    def add_plan_refresh_next_channel(self, plan):
        if self.channel != self.next_channel:
            plan.add_step(
                UpgradeStep(
                    description=f"Refresh {self.name} to the new channel: '{self.next_channel}'",
                    parallel=False,
                    function=async_upgrade_charm,
                    application_name=self.name,
                    channel=self.next_channel,
                    model_name=self.model_name,
                )
            )
        return plan

    def add_plan_disable_action_managed(self, plan) -> UpgradeStep:
        if self.config.get("action-managed-upgrade"):
            if self.config["action-managed-upgrade"].get("value", False):
                plan.add_step(
                    UpgradeStep(
                        description=f"App: '{self.name}' -> Set action-managed-upgrade to False.",
                        parallel=False,
                        function=async_set_application_config,
                        application_name=self.name,
                        configuration={"action-managed-upgrade": False},
                    )
                )
        return plan

    def add_plan_payload_upgrade(self, plan):
        if self.os_origin != self.new_origin:
            plan.add_step(
                UpgradeStep(
                    description=f"App: '{self.name}' -> Change charm config '{self.origin_setting}' to '{self.new_origin}'",
                    parallel=False,
                    function=async_set_application_config,
                    application_name=self.name,
                    configuration={self.origin_setting: self.new_origin},
                )
            )
        else:
            logging.warning(
                "App: %s already have %s set to %s",
                self.name,
                self.origin_setting,
                self.new_origin,
            )
        return plan
