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

"""Functions for analyze openstack cloud before upgrade."""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Tuple, Union

import yaml
from juju.client._definitions import ApplicationStatus

from cou.zaza_utils import model
from cou.zaza_utils.juju import get_full_juju_status
from cou.zaza_utils.openstack import CHARM_TYPES, get_os_code_info
from cou.zaza_utils.os_versions import (
    CompareOpenStack,
    determine_next_openstack_release,
)


class InvalidCharmNameError(Exception):
    """Represents an invalid charm name being processed."""


@dataclass
class Analyze:
    """Analyze result."""

    upgrade_units: defaultdict[str, set]
    upgrade_charms: defaultdict[str, set]
    change_channel: defaultdict[str, set]
    charmhub_migration: defaultdict[str, set]
    change_openstack_release: defaultdict[str, set]


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

    def __post_init__(self) -> None:
        """Initiate the Apllication dataclass."""
        self.charm = self.extract_charm_name()
        self.channel = self.status.base.get("channel")
        self.charm_origin = self.status.charm.split(":")[0]
        self.pkg_name = self.get_pkg_name()
        self.os_origin = self.get_os_origin()
        for unit in self.status.units.keys():
            os_version = self.get_current_os_versions(unit)
            self.units[unit]["os_version"] = os_version
            self.os_release_units[os_version].add(unit)

    def to_yaml(self) -> str:
        """Return a string in yaml format.

        Passing the Application class directly to dump contain some fields that are big,
        e.g: config and status. This output contains just the important fields for
        the operator.
        """
        app = {
            self.name: {
                "channel": self.channel,
                "model_name": self.model_name,
                "pkg_name": self.pkg_name,
                "units": {
                    unit: {
                        "pkg_version": details.get("pkg_version"),
                        "os_version": details.get("os_version"),
                    }
                    for unit, details in self.units.items()
                },
            }
        }
        return yaml.dump(
            app,
            default_flow_style=False,
            allow_unicode=True,
            encoding=None,
            sort_keys=False,
        )

    def extract_charm_name(self) -> str:
        """Extract the charm name using regex."""
        match = re.match(
            r"^(?:\w+:)?(?:~[\w\.-]+/)?(?:\w+/)*([a-zA-Z0-9-]+?)(?:-\d+)?$", self.status.charm
        )
        if not match:
            raise InvalidCharmNameError(f"charm name '{self.status.charm}' is invalid")
        return match.group(1)

    def get_pkg_name(self) -> str:
        """Get the package name depending on the name of the charm."""
        return CHARM_TYPES[self.charm]["pkg"]

    def get_current_os_versions(self, unit: str) -> str:
        """Get the openstack version of a unit."""
        version = None
        pkg_version = get_pkg_version(unit, self.pkg_name, self.model_name)
        self.units[unit]["pkg_version"] = pkg_version
        self.pkg_version_units[pkg_version].add(unit)

        # for openstack releases >= wallaby
        codename = get_openstack_release(unit, model_name=self.model_name)
        if codename:
            version = codename
        # for openstack releases < wallaby
        else:
            version = get_os_code_info(self.pkg_name, pkg_version)
        return version

    def get_os_origin(self) -> str:
        """Get application configuration for openstack-origin or source."""
        for origin in ("openstack-origin", "source"):
            if self.config.get(origin):
                return self.config[origin]["value"]

        logging.warning("Failed to get origin for %s, no origin config found", self.name)
        return ""

    def check_os_versions_units(
        self, upgrade_units: defaultdict[str, set]
    ) -> defaultdict[str, set]:
        """Check openstack versions in an application."""
        if len(self.os_release_units.keys()) > 1:
            logging.warning("Units from %s are not in the same openstack version", self.name)
            os_sequence = sorted(
                list(self.os_release_units.keys()),
                key=CompareOpenStack,
            )
            for os_release in os_sequence[:-1]:
                next_release = determine_next_openstack_release(os_release)[1]
                upgrade_units[next_release].update(self.os_release_units[os_release])
                logging.warning(
                    "upgrade units: %s from: %s to %s",
                    self.os_release_units[os_release],
                    os_release,
                    next_release,
                )
        return upgrade_units

    def check_os_channels_and_migration(
        self, change_channel: defaultdict[str, set], charmhub_migration: defaultdict[str, set]
    ) -> Tuple:
        """Check openstack channel and if it's necessary a charmhub migration."""
        if len(self.os_release_units.keys()) > 1:
            logging.warning(
                "Skip check of channels. App %s has units with different openstack version",
                self.name,
            )
        else:
            actual_release = list(self.os_release_units.keys())[0]
            expected_channel = f"{actual_release}/stable"
            if actual_release not in self.channel:
                change_channel[expected_channel].add(self.name)
                logging.warning(
                    "App:%s need to track the channel: %s", self.name, expected_channel
                )
            if self.charm_origin == "cs":
                charmhub_migration[expected_channel].add(self.name)
                logging.warning("App:%s need to perform migration to charmhub", self.name)
        return change_channel, charmhub_migration

    def check_os_origin(
        self, change_openstack_release: defaultdict[str, set]
    ) -> defaultdict[str, set]:
        """Check if charm configuration for openstack-origin is set correct."""
        if len(self.os_release_units.keys()) > 1:
            logging.warning(
                "Skip openstack-origin check. App %s has units with different openstack version",
                self.name,
            )
        else:
            actual_release = list(self.os_release_units.keys())[0]
            expected_os_origin = f"cloud:focal-{actual_release}"
            # Exceptionally, if upgrading from Ussuri to Victoria
            if actual_release == "ussuri":
                if self.os_origin != "distro":
                    logging.warning(
                        "App: %s need to set openstack-origin or source to 'distro'", self.name
                    )
                    change_openstack_release["distro"].add(self.name)
            else:
                if expected_os_origin not in self.os_origin:
                    change_openstack_release[expected_os_origin].add(self.name)
                    logging.warning(
                        "App: %s need to set openstack-origin or source to %s",
                        self.name,
                        expected_os_origin,
                    )
        return change_openstack_release


def get_openstack_release(unit: str, model_name: Union[str, None] = None) -> Union[str, None]:
    """Return the openstack release codename based on /etc/openstack-release."""
    cmd = "grep -Po '(?<=OPENSTACK_CODENAME=).*' /etc/openstack-release"
    try:
        out = model.run_on_unit(unit, cmd, model_name=model_name, timeout=20)
    except model.CommandRunFailed:
        logging.debug("Fall back to version check for OpenStack codename")
        return None
    return out["Stdout"]


def get_pkg_version(unit: str, pkg: str, model_name: Union[str, None] = None) -> str:
    """Get package version of a specific package in a unit."""
    cmd = f"dpkg-query --show --showformat='${{Version}}' {pkg}"
    out = model.run_on_unit(unit, cmd, model_name=model_name, timeout=20)
    return out["Stdout"]


def generate_model() -> List[Application]:
    """Generate the applications model."""
    juju_status = get_full_juju_status()
    model_name = juju_status.model.name
    apps = [
        Application(
            name=app,
            status=app_status,
            config=model.get_application_config(app),
            model_name=model_name,
        )
        for app, app_status in juju_status.applications.items()
    ]
    return apps


def analyze() -> Analyze:
    """Analyze the deployment before planning."""
    logging.info("Analyzing the Openstack release in the deployment...")
    apps = generate_model()
    os_versions: defaultdict[str, set] = defaultdict(set)
    upgrade_units: defaultdict[str, set] = defaultdict(set)
    change_channel: defaultdict[str, set] = defaultdict(set)
    charmhub_migration: defaultdict[str, set] = defaultdict(set)
    change_openstack_release: defaultdict[str, set] = defaultdict(set)
    for app in apps:
        for os_version_unit in app.os_release_units.keys():
            os_versions[os_version_unit].add(app.name)
        upgrade_units = app.check_os_versions_units(upgrade_units)
        change_channel, charmhub_migration = app.check_os_channels_and_migration(
            change_channel, charmhub_migration
        )
        change_openstack_release = app.check_os_origin(change_openstack_release)

    upgrade_charms = check_upgrade_charms(os_versions)

    return Analyze(
        upgrade_units, upgrade_charms, change_channel, charmhub_migration, change_openstack_release
    )


def check_upgrade_charms(os_versions: defaultdict[str, set]) -> defaultdict[str, set]:
    """Check if all charms of a model are in the same openstack release."""
    upgrade_charms = defaultdict(set)
    if len(os_versions) > 1:
        logging.warning("Charms are not in the same openstack version")
        os_sequence = sorted(os_versions.keys(), key=CompareOpenStack)
        for os_release in os_sequence[:-1]:
            next_release = determine_next_openstack_release(os_release)[1]
            upgrade_charms[next_release].update(os_versions[os_release])
            logging.warning(
                "upgrade charm: %s from: %s to %s",
                os_versions[os_release],
                os_release,
                next_release,
            )
    else:
        actual_release = list(os_versions)[0]
        next_release = determine_next_openstack_release(actual_release)[1]
        logging.info(
            "Charms are in the same openstack version and can be upgrade from: %s to: %s",
            actual_release,
            next_release,
        )
        upgrade_charms[next_release].update(os_versions[actual_release])
    return upgrade_charms
