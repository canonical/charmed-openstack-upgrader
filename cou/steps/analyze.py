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
from typing import Any, Iterable

from juju.client._definitions import ApplicationStatus
from ruamel.yaml import YAML

from cou.utils.juju_utils import (
    async_get_application_config,
    async_get_full_juju_status,
    extract_charm_name_from_url,
)
from cou.utils.openstack import CHARM_TYPES, get_os_code_info


@dataclass
class Analysis:
    """Analyze result."""

    apps: Iterable[Application]

    @classmethod
    async def create(cls) -> Analysis:
        """Analyze the deployment before planning."""
        logging.info("Analyzing the OpenStack deployment...")
        apps = await Analysis._populate()

        return Analysis(apps=apps)

    @classmethod
    async def _populate(cls) -> set[Application]:
        """Generate the applications model."""
        juju_status = await async_get_full_juju_status()
        model_name = juju_status.model.name
        apps = {
            Application(
                name=app,
                status=app_status,
                config=await async_get_application_config(app),
                model_name=model_name,
            )
            for app, app_status in juju_status.applications.items()
        }
        return apps

    def __str__(self) -> str:
        """Dump as string."""
        return "\n".join([str(app) for app in self.apps])


@dataclass
class Application:
    """Representation of an application in the deployment."""

    # pylint: disable=too-many-instance-attributes

    name: str
    status: ApplicationStatus
    config: dict
    model_name: str
    charm: str = ""
    charm_origin: str = ""
    os_origin: str = ""
    channel: str = ""

    # e.g: {"keystone/0": {'os_version': 'victoria', 'workload_version': '2:18.1'}}
    units: defaultdict[str, dict] = field(default_factory=lambda: defaultdict(dict))

    def __post_init__(self) -> None:
        """Initialize the Application dataclass."""
        self.charm = extract_charm_name_from_url(self.status.charm)
        self.channel = self.status.charm_channel
        self.charm_origin = self.status.charm.split(":")[0]
        self.os_origin = self._get_os_origin()
        for unit in self.status.units.keys():
            workload_version = self._get_charm_workload_version(unit)
            self.units[unit]["workload_version"] = workload_version
            os_version = self._get_current_os_version(workload_version)
            self.units[unit]["os_version"] = os_version

    def __hash__(self) -> int:
        """Hash magic method for Application."""
        return hash(f"{self.name}{self.charm}")

    def __eq__(self, other: Any) -> Any:
        """Equal magic method for Application."""
        return other.name == self.name and other.charm == self.charm

    def __str__(self) -> str:
        """Dump as string."""
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

    def _get_workload_name(self) -> str:
        """Get the workload name depending on the name of the charm."""
        try:
            workload = CHARM_TYPES[self.charm]["workload"]
        except KeyError:
            logging.warning("workload not found for application: %s", self.name)
            workload = ""
        return workload

    def _get_current_os_version(self, workload_version: str) -> str:
        """Get the openstack version of a unit."""
        version = ""
        workload_name = self._get_workload_name()

        if workload_name and workload_version:
            version = get_os_code_info(workload_name, workload_version)
        return version

    def _get_os_origin(self) -> str:
        """Get application configuration for openstack-origin or source."""
        for origin in ("openstack-origin", "source"):
            if self.config.get(origin):
                return self.config[origin].get("value", "")

        logging.warning("Failed to get origin for %s, no origin config found", self.name)
        return ""

    def _get_charm_workload_version(self, unit: str) -> str:
        """Get the payload version of a charm."""
        try:
            return self.status.units[unit].workload_version
        except AttributeError:
            logging.warning("Failed to get workload version for '%s'", self.name)
            return ""
