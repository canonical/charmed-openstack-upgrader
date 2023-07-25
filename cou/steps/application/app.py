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

"""Functions for analyzing an OpenStack cloud before an upgrade."""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from io import StringIO
from typing import Any, Optional

from juju.client._definitions import ApplicationStatus
from ruamel.yaml import YAML

from cou.steps import UpgradeStep
from cou.utils.juju_utils import (
    async_set_application_config,
    async_upgrade_charm,
    extract_charm_name_from_url,
)
from cou.utils.openstack import (
    OpenStackCodenameLookup,
    determine_next_openstack_release,
)

logger = logging.getLogger(__name__)


@dataclass
class StandardApplication:
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
    :param os_origin: OpenStack origin of the application. E.g: cloud:focal-wallaby, defaults to ""
    :type os_origin: str, optional
    :param channel: Channel that the charm tracks. E.g: "ussuri/stable", defaults to ""
    :type channel: str, optional
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
        self.origin_setting = None
        self.channel = self.status.charm_channel
        self.charm_origin = self.status.charm.split(":")[0]
        self.os_origin = self._get_os_origin()
        self.current_os_release = None
        self.next_os_release = None
        os_versions = set()
        for unit in self.status.units.keys():
            workload_version = self.status.units[unit].workload_version
            self.units[unit]["workload_version"] = workload_version
            compatible_os_versions = OpenStackCodenameLookup.lookup(self.charm, workload_version)
            # NOTE(gabrielcocenza) get the latest compatible OpenStack version.
            if compatible_os_versions:
                unit_os_version = compatible_os_versions[-1]
                self.units[unit]["os_version"] = unit_os_version
                os_versions.add(unit_os_version)
            else:
                self.units[unit]["os_version"] = ""
            if len(os_versions) == 1:
                self.current_os_release = list(os_versions)[0]
                _, self.next_os_release = determine_next_openstack_release(self.current_os_release)

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

    @property
    def series(self) -> str:
        """Ubuntu series of the application.

        :return: Ubuntu series of application. E.g: focal
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
        # LTS should be "distro"
        if self.next_os_release in ["ussuri", "yoga"]:
            return "distro"
        return f"cloud:{self.series}-{self.next_os_release}"

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

    def can_generate_upgrade_plan(self):
        if self.current_os_release is None:
            logger.warning("Not possible to determine OpenStack release for '%s'.", self.name)
            return False
        return True

    def generate_upgrade_plan(self) -> Optional[UpgradeStep]:
        if self.can_generate_upgrade_plan():
            upgrade_plan = UpgradeStep(
                description=f"Upgrade plan for '{self.name}'",
                parallel=False,
                function=None,
            )

            upgrade_plan_sub_steps = [
                self.add_plan_refresh_current_channel,
                self.add_plan_refresh_next_channel,
                self.add_plan_disable_action_managed,
                self.add_plan_workload_upgrade,
            ]

            for sub_step_func in upgrade_plan_sub_steps:
                sub_step_func(upgrade_plan)

            return upgrade_plan
        logger.warning("Aborting upgrade plan for '%s'", self.name)

    def add_plan_refresh_current_channel(self, plan: UpgradeStep) -> None:
        if self.charm_origin == "cs":
            plan = self._add_plan_charmhub_migration(plan)
            return
        self._add_plan_change_current_channel(plan)
        self._add_plan_update_current_channel(plan)

    def _add_plan_charmhub_migration(self, plan: UpgradeStep, parallel=False) -> None:
        plan.add_step(
            UpgradeStep(
                description=f"App: {self.name} -> Migration from charmstore to charmhub",
                parallel=parallel,
                function=async_upgrade_charm,
                application_name=self.name,
                channel=self.current_channel,
                model_name=self.model_name,
                switch=f"ch:{self.charm}",
            )
        )

    def _add_plan_change_current_channel(self, plan: UpgradeStep, parallel=False) -> None:
        if self.channel != self.current_channel and self.channel != self.next_channel:
            plan.add_step(
                UpgradeStep(
                    description=f"Changing {self.name} channel from: {self.channel} to: {self.current_channel}",
                    parallel=parallel,
                    function=async_upgrade_charm,
                    application_name=self.name,
                    channel=self.current_channel,
                )
            )

    def _add_plan_update_current_channel(self, plan: UpgradeStep, parallel=False) -> None:
        if self.channel == self.next_channel:
            logger.warning(
                "App: %s already has the channel set for the next OpenStack version %s",
                self.name,
                self.next_os_release,
            )
        else:
            plan.add_step(
                UpgradeStep(
                    description=f"Refresh {self.name} to the latest revision of {self.current_channel}",
                    parallel=parallel,
                    function=async_upgrade_charm,
                    application_name=self.name,
                )
            )

    def add_plan_refresh_next_channel(self, plan: UpgradeStep, parallel=False) -> None:
        if self.channel != self.next_channel:
            plan.add_step(
                UpgradeStep(
                    description=f"Refresh {self.name} to the new channel: '{self.next_channel}'",
                    parallel=parallel,
                    function=async_upgrade_charm,
                    application_name=self.name,
                    channel=self.next_channel,
                    model_name=self.model_name,
                )
            )

    def add_plan_disable_action_managed(self, plan: UpgradeStep, parallel=False) -> None:
        if self.config.get("action-managed-upgrade"):
            if self.config["action-managed-upgrade"].get("value", False):
                plan.add_step(
                    UpgradeStep(
                        description=f"App: '{self.name}' -> Set action-managed-upgrade to False.",
                        parallel=parallel,
                        function=async_set_application_config,
                        application_name=self.name,
                        configuration={"action-managed-upgrade": False},
                    )
                )

    def add_plan_workload_upgrade(self, plan: UpgradeStep, parallel=False) -> None:
        if self.os_origin != self.new_origin:
            plan.add_step(
                UpgradeStep(
                    description=f"App: '{self.name}' -> Change charm config '{self.origin_setting}' to '{self.new_origin}'",
                    parallel=parallel,
                    function=async_set_application_config,
                    application_name=self.name,
                    configuration={self.origin_setting: self.new_origin},
                )
            )
        else:
            logger.warning(
                "App: %s already have %s set to %s",
                self.name,
                self.origin_setting,
                self.new_origin,
            )
