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
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, DefaultDict, Dict, Set, Tuple

from cou.zaza_utils import model
from cou.zaza_utils.juju import get_application_status, get_full_juju_status
from cou.zaza_utils.openstack import get_current_os_versions
from cou.zaza_utils.os_versions import (
    SERVICE_GROUPS,
    CompareOpenStack,
    determine_next_openstack_release,
)
from cou.zaza_utils.upgrade_utils import extract_charm_name


@dataclass
class Analyze:
    """Analyze result."""

    upgrade_units: DefaultDict
    upgrade_charms: DefaultDict
    change_channel: DefaultDict
    charmhub_migration: DefaultDict
    change_openstack_release: DefaultDict


def analyze() -> Analyze:
    """Analyze the deployment before planning."""
    logging.info("Analyzing the Openstack release in the deployment...")
    os_versions = extract_os_versions()
    upgrade_units, upgrade_charms = check_os_versions(os_versions)
    change_channel, charmhub_migration = check_os_channels_and_migration(os_versions)
    change_openstack_release = check_os_origin(os_versions)
    return Analyze(
        upgrade_units, upgrade_charms, change_channel, charmhub_migration, change_openstack_release
    )


def extract_os_versions() -> Dict[str, defaultdict[Any, Set]]:
    """Extract OpenStack version on the deployment."""
    os_versions = {}
    status = get_full_juju_status().applications
    openstack_charms = set()
    for _, charms in SERVICE_GROUPS[2:]:
        for charm in charms:
            openstack_charms.add(charm)

    for app, app_status in status.items():
        charm = extract_charm_name(app_status.charm)
        if charm in openstack_charms:
            os_versions[app] = get_current_os_versions((app, charm))

    logging.debug(os_versions)
    return os_versions


def extract_app_channel_and_origin(app: str) -> Tuple:
    """Extract application channel and origin (cs or ch) by the juju status."""
    app_status = get_application_status(app)
    return app_status.get("charm-channel"), app_status.get("charm").split(":")[0]


def extract_os_charm_config(app: str) -> str:
    """Extract application configuration for openstack-origin."""
    app_config = model.get_application_config(app)
    for origin in ("openstack-origin", "source"):
        if app_config.get(origin):
            return app_config.get(origin).get("value")

    logging.warning("Failed to get origin for %s, no origin config found", app)
    return ""


def check_os_versions(os_versions: Dict[str, defaultdict[Any, Set]]) -> Tuple:
    """Check the consistency of OpenStack version on the deployment."""
    versions = defaultdict(set)
    upgrade_units = defaultdict(set)
    upgrade_charms = defaultdict(set)

    for app, os_release_units in os_versions.items():
        os_version_units = set(os_release_units.keys())
        for os_version_unit in os_version_units:
            versions[os_version_unit].add(app)
        if len(os_version_units) > 1:
            logging.warning("Units from %s are not in the same openstack version", app)
            os_sequence = sorted(
                list(os_version_units),
                key=lambda release: CompareOpenStack(release),  # pylint: disable=W0108
            )
            for os_release in os_sequence[:-1]:
                next_release = determine_next_openstack_release(os_release)[1]
                upgrade_units[next_release].update(os_release_units[os_release])
                logging.warning(
                    "upgrade units: %s from: %s to %s",
                    os_release_units[os_release],
                    os_release,
                    next_release,
                )

    if len(versions) > 1:
        logging.warning("Charms are not in the same openstack version")
        os_sequence = sorted(
            versions.keys(), key=lambda release: CompareOpenStack(release)  # pylint: disable=W0108
        )
        for os_release in os_sequence[:-1]:
            next_release = determine_next_openstack_release(os_release)[1]
            upgrade_charms[next_release].update(versions[os_release])
            logging.warning(
                "upgrade charm: %s from: %s to %s", versions[os_release], os_release, next_release
            )

    else:
        actual_release = list(versions)[0]
        next_release = determine_next_openstack_release(actual_release)[1]
        logging.info(
            "Charms are in the same openstack version and can be upgrade from: %s to: %s",
            actual_release,
            next_release,
        )
        upgrade_charms[next_release].update(os_versions.keys())

    return upgrade_units, upgrade_charms


def check_os_channels_and_migration(os_versions: Dict[str, defaultdict[Any, Set]]) -> Tuple:
    """Check if applications has the right channel set and if needs charmhub migration."""
    change_channel = defaultdict(set)
    charmhub_migration = defaultdict(set)

    for app in os_versions.keys():
        app_channel, charm_origin = extract_app_channel_and_origin(app)
        actual_release = list(os_versions[app].keys())
        if len(actual_release) > 1:
            logging.warning(
                "Skip check of channels. App %s has units with different openstack version",
                app,
            )
        else:
            actual_release = actual_release[0]
            expected_channel = f"{actual_release}/stable"
            if actual_release not in app_channel:
                change_channel[expected_channel].add(app)
                logging.warning("App:%s need to track the channel: %s", app, expected_channel)
            if charm_origin == "cs":
                charmhub_migration[expected_channel].add(app)
                logging.warning("App:%s need to perform migration to charmhub", app)

    return change_channel, charmhub_migration


def check_os_origin(os_versions: Dict[str, defaultdict[Any, Set]]) -> defaultdict[Any, Any]:
    """Check if application config for openstack-origin is set right."""
    change_openstack_release = defaultdict(set)
    for app in os_versions.keys():
        os_charm_config = extract_os_charm_config(app)
        actual_release = list(os_versions[app].keys())

        if len(actual_release) > 1:
            logging.warning(
                "Skip openstack-origin check. App %s has units with different openstack version",
                app,
            )

        else:
            actual_release = actual_release[0]
            expected_os_origin = f"cloud:focal-{actual_release}"
            # Exceptionally, if upgrading from Ussuri to Victoria
            if actual_release == "ussuri":
                if os_charm_config != "distro":
                    logging.warning(
                        "App: %s need to set openstack-origin or source to 'distro'", app
                    )
                    change_openstack_release["distro"].add(app)
            else:
                if expected_os_origin not in os_charm_config:
                    change_openstack_release[expected_os_origin].add(app)
                    logging.warning(
                        "App: %s need to set openstack-origin or source to %s",
                        app,
                        expected_os_origin,
                    )
    return change_openstack_release
