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
import os
from collections import defaultdict
from dataclasses import dataclass, field
from io import StringIO
from typing import Any, Iterable

from juju.client._definitions import ApplicationStatus
from ruamel.yaml import YAML

from cou.utils.juju_utils import (
    async_get_application_config,
    async_get_status,
    extract_charm_name_from_url,
)
from cou.utils.openstack import CHARM_TYPES, get_os_code_info


@dataclass
class Analysis:
    """Analyze result."""

    apps: Iterable[Application]

    @classmethod
    async def create(cls) -> Analysis:
        """Analyze the deployment before planning.

        :return: Analysis object populated with the model applications.
        :rtype: Analysis
        """
        logging.info("Analyzing the OpenStack deployment...")
        apps = await Analysis._populate()

        return Analysis(apps=apps)

    @classmethod
    async def _populate(cls) -> set[Application]:
        """Generate the applications model.

        :return: Application objects with their respective information.
        :rtype: set[Application]
        """
        juju_status = await async_get_status()
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
        """Dump as string.

        :return: String representation of Application objects.
        :rtype: str
        """
        return os.linesep.join([str(app) for app in self.apps])


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
    :type charm_origin: str, optional
    :param os_origin: Openstack origin of the application. E.g: cloud:focal-wallaby, defaults to ""
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
    charm: str = ""
    charm_origin: str = ""
    os_origin: str = ""
    channel: str = ""
    units: defaultdict[str, dict] = field(default_factory=lambda: defaultdict(dict))

    def __post_init__(self) -> None:
        """Initialize the Application dataclass."""
        self.charm = extract_charm_name_from_url(self.status.charm)
        self.channel = self.status.charm_channel
        self.charm_origin = self.status.charm.split(":")[0]
        self.os_origin = self._get_os_origin()
        for unit in self.status.units.keys():
            workload_version = self.status.units[unit].workload_version
            self.units[unit]["workload_version"] = workload_version
            os_version = self._get_current_os_version(workload_version)
            self.units[unit]["os_version"] = os_version

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
                return self.config[origin].get("value", "")

        logging.warning("Failed to get origin for %s, no origin config found", self.name)
        return ""
