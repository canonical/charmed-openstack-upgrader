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

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Union

import yaml
from juju.client._definitions import ApplicationStatus

from cou.exceptions import CommandRunFailed
from cou.utils.juju_utils import (
    async_get_application_config,
    async_get_full_juju_status,
    async_run_on_unit,
)
from cou.utils.openstack import CHARM_TYPES, get_os_code_info
from cou.utils.upgrade_utils import extract_charm_name_from_url


@dataclass
class Analysis:
    """Analyze result."""

    apps: Iterable[Application]

    @classmethod
    async def create(cls) -> Analysis:
        """Analyze the deployment before planning."""
        logging.info("Analyzing the Openstack deployment...")
        apps = await Analysis._populate()

        return Analysis(apps=apps)

    @classmethod
    async def _populate(cls) -> set[Application]:
        """Generate the applications model."""
        juju_status = await async_get_full_juju_status()
        model_name = juju_status.model.name
        app_list = [
            Application(
                name=app,
                status=app_status,
                config=await async_get_application_config(app),
                model_name=model_name,
            ).fill()
            for app, app_status in juju_status.applications.items()
        ]
        apps = set(await asyncio.gather(*app_list))
        # NOTE(gabrielcocenza) Not all openstack-charms are mapped in the zaza lookup.
        openstack_apps = {app for app in apps if app.charm in CHARM_TYPES}
        not_supported_apps = apps - openstack_apps
        not_supported_apps_names = sorted([app.name for app in not_supported_apps])
        logging.warning(
            "App(s): %s are not supported in the analyze process",
            ", ".join(not_supported_apps_names),
        )
        return openstack_apps

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
    pkg_name: str = ""
    # E.g of units: {"keystone/0": {'os_version': 'victoria', 'pkg_version': '2:18.1'}}
    units: defaultdict[str, dict] = field(default_factory=lambda: defaultdict(dict))
    #  E.g of os_release_units: {"ussuri":{"keystone/0"}, "victoria": {"keystone/1"}}
    os_release_units: defaultdict[str, set] = field(default_factory=lambda: defaultdict(set))
    #  E.g of pkg_version_units: {"2:17.0": {"keystone/0"}, "2:18.0": {"keystone/1"}}
    pkg_version_units: defaultdict[str, set] = field(default_factory=lambda: defaultdict(set))

    async def fill(self) -> Application:
        """Initialize the Application dataclass."""
        self.charm = extract_charm_name_from_url(self.status.charm)
        self.channel = self.status.charm_channel
        self.charm_origin = self.status.charm.split(":")[0]
        self.pkg_name = self._get_pkg_name()
        self.os_origin = self._get_os_origin()
        for unit in self.status.units.keys():
            os_version = await self._get_current_os_versions(unit)
            self.units[unit]["os_version"] = os_version
            self.os_release_units[os_version].add(unit)
        return self

    def __hash__(self) -> int:
        """Hash magic method for Application."""
        return hash(f"{self.name}{self.charm}")

    def __eq__(self, other: Any) -> Any:
        """Equal magic method for Application."""
        return other.name == self.name and other.charm == self.charm

    def to_dict(self) -> Dict:
        """Return a string in yaml format.

        Passing the Application class directly to dump contain some fields that are big,
        e.g: config and status. This output contains just the important fields for
        the operator.
        """
        return {
            self.name: {
                "model_name": self.model_name,
                "charm": self.charm,
                "charm_origin": self.charm_origin,
                "os_origin": self.os_origin,
                "channel": self.channel,
                "pkg_name": self.pkg_name,
                "units": {
                    unit: {
                        "pkg_version": details.get("pkg_version", ""),
                        "os_version": details.get("os_version", ""),
                    }
                    for unit, details in self.units.items()
                },
            }
        }

    def __str__(self) -> str:
        """Dump as string."""
        return yaml.dump(self.to_dict())

    def _get_pkg_name(self) -> str:
        """Get the package name depending on the name of the charm."""
        try:
            pkg_name = CHARM_TYPES[self.charm]["pkg"]
        except KeyError:
            logging.warning("package not found for application: %s", self.name)
            pkg_name = ""
        return pkg_name

    # NOTE (gabrielcocenza) Ideally, the application should provide the openstack version
    # and packages versions by a charm action. This might be possible with Sunbeam.
    async def _get_current_os_versions(self, unit: str) -> str:
        """Get the openstack version of a unit."""
        version = ""
        pkg_version = self._get_pkg_version(unit)
        self.units[unit]["pkg_version"] = pkg_version
        self.pkg_version_units[pkg_version].add(unit)

        # for openstack releases >= wallaby
        codename = await self._get_openstack_release(unit, model_name=self.model_name)
        if codename:
            version = codename
        # for openstack releases < wallaby
        elif self.pkg_name and pkg_version:
            version = get_os_code_info(self.pkg_name, pkg_version)
        return version

    def _get_os_origin(self) -> str:
        """Get application configuration for openstack-origin or source."""
        for origin in ("openstack-origin", "source"):
            if self.config.get(origin):
                return self.config[origin].get("value", "")

        logging.warning("Failed to get origin for %s, no origin config found", self.name)
        return ""

    async def _get_openstack_release(
        self, unit: str, model_name: Union[str, None] = None
    ) -> Union[str, None]:
        """Return the openstack release codename based on /etc/openstack-release."""
        cmd = "grep -Po '(?<=OPENSTACK_CODENAME=).*' /etc/openstack-release"
        try:
            out = await async_run_on_unit(unit, cmd, model_name=model_name, timeout=20)
        except CommandRunFailed:
            logging.warning("Fall back to version check for OpenStack codename")
            return None
        return out["Stdout"].strip()

    def _get_pkg_version(self, unit: str) -> str:
        """Get the openstack package version in a unit."""
        try:
            return self.status.units[unit].workload_version
        except AttributeError:
            logging.warning("Failed to get pkg version for '%s'", self.name)
            return ""
