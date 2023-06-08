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
from typing import Any, Dict, List, Set, Tuple

from juju.client._definitions import ApplicationStatus

from cou.zaza_utils import juju, model
from cou.zaza_utils.juju import get_full_juju_status
from cou.zaza_utils.openstack import CHARM_TYPES, get_os_code_info
from cou.zaza_utils.os_versions import (
    CompareOpenStack,
    determine_next_openstack_release,
)


class InvalidCharmNameError(Exception):
    """Represents an invalid charm name being processed."""

    pass


@dataclass
class Analyze:
    """Analyze result."""

    upgrade_units: defaultdict(set)
    upgrade_charms: defaultdict(set)
    change_channel: defaultdict(set)
    charmhub_migration: defaultdict(set)
    change_openstack_release: defaultdict(set)


@dataclass
class Application:
    "Representation of an application in the deployment"
    name: str
    status: ApplicationStatus
    config: dict
    model_name: str
    os_version_units: set | None = None
    charm: str | None = None
    units: set | None = None
    channel: str | None = None
    pkg_name: str | None = None
    os_release_units: defaultdict(set) = field(default_factory=lambda: defaultdict(set))
    pkg_version_units: defaultdict(set) = field(default_factory=lambda: defaultdict(set))

    def __post_init__(self):
        self.extract_charm_name()
        self.channel = self.status.base.get("channel")
        self.origin = self.status.charm.split(":")[0]
        self.units = self.status.units.keys()
        self.pkg_name = self.get_pkg_name()
        for unit in self.units:
            self.os_release_units[self.get_current_os_versions(unit, self.model_name)].add(unit)
        self.os_version_units = set(self.os_release_units.keys())

    def extract_charm_name(self) -> str:
        """Extract the charm name using regex."""
        match = re.match(
            r"^(?:\w+:)?(?:~[\w\.-]+/)?(?:\w+/)*([a-zA-Z0-9-]+?)(?:-\d+)?$", self.status.charm
        )
        if not match:
            raise InvalidCharmNameError("charm name '{}' is invalid".format(self.status.charm))
        self.charm = match.group(1)

    def get_pkg_name(self) -> str:
        return CHARM_TYPES.get(self.charm, {self.charm: {"pkg": None}}).get("pkg")

    def get_current_os_versions(self, unit, model_name=None) -> str:
        version = None
        codename = get_openstack_release(unit, model_name=model_name)
        if codename:
            version = codename
        else:
            pkg_version = get_pkg_version(unit, self.pkg_name, model_name)
            self.pkg_version_units[pkg_version].add(unit)
            version = get_os_code_info(self.pkg_name, pkg_version)
        return version

    def get_os_origin(self) -> str:
        """Get application configuration for openstack-origin or source."""
        for origin in ("openstack-origin", "source"):
            if self.config.get(origin):
                return self.config.get(origin).get("value")

        logging.warning("Failed to get origin for %s, no origin config found", self.name)

    def check_os_versions_units(self, upgrade_units: defaultdict(set)) -> defaultdict(set):
        """Check openstack versions in an application."""
        if len(self.os_version_units) > 1:
            logging.warning("Units from %s are not in the same openstack version", self.name)
            os_sequence = sorted(
                list(self.os_version_units),
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
        self, change_channel: defaultdict(set), charmhub_migration: defaultdict(set)
    ) -> Tuple:
        if len(self.os_version_units) > 1:
            logging.warning(
                "Skip check of channels. App %s has units with different openstack version",
                self.name,
            )
        else:
            actual_release = list(self.os_version_units)[0]
            expected_channel = f"{actual_release}/stable"
            if actual_release not in self.channel:
                change_channel[expected_channel].add(self.name)
                logging.warning(
                    "App:%s need to track the channel: %s", self.name, expected_channel
                )
            if self.origin == "cs":
                charmhub_migration[expected_channel].add(self.name)
                logging.warning("App:%s need to perform migration to charmhub", self.name)
        return change_channel, charmhub_migration

    def check_os_origin(self, change_openstack_release: defaultdict(set)) -> defaultdict(set):
        os_charm_config = self.get_os_origin()
        if len(self.os_version_units) > 1:
            logging.warning(
                "Skip openstack-origin check. App %s has units with different openstack version",
                self.name,
            )
        else:
            actual_release = list(self.os_version_units)[0]
            expected_os_origin = f"cloud:focal-{actual_release}"
            # Exceptionally, if upgrading from Ussuri to Victoria
            if actual_release == "ussuri":
                if os_charm_config != "distro":
                    logging.warning(
                        "App: %s need to set openstack-origin or source to 'distro'", self.name
                    )
                    change_openstack_release["distro"].add(self.name)
            else:
                if expected_os_origin not in os_charm_config:
                    change_openstack_release[expected_os_origin].add(self.name)
                    logging.warning(
                        "App: %s need to set openstack-origin or source to %s",
                        self.name,
                        expected_os_origin,
                    )
        return change_openstack_release


def get_openstack_release(unit, model_name):
    """Return the openstack release codename based on /etc/openstack-release."""
    cmd = "cat /etc/openstack-release | grep OPENSTACK_CODENAME"
    try:
        out = juju.remote_run(unit, cmd, model_name=model_name)
    except model.CommandRunFailed:
        logging.debug("Fall back to version check for OpenStack codename")
    else:
        return out.split("=")[1].strip()


def get_pkg_version(unit, pkg, model_name=None):
    cmd = "dpkg -l | grep {}".format(pkg)
    out = juju.remote_run(unit, cmd, model_name=model_name)
    return out.split("\n")[0].split()[2]


def generate_model():
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
    os_versions = defaultdict(set)
    upgrade_units = defaultdict(set)
    change_channel = defaultdict(set)
    charmhub_migration = defaultdict(set)
    change_openstack_release = defaultdict(set)
    for app in apps:
        for os_version_unit in app.os_version_units:
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


def check_upgrade_charms(os_versions: defaultdict(set)) -> defaultdict(set):
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
        upgrade_charms[next_release].update(os_versions.values())
    return upgrade_charms
