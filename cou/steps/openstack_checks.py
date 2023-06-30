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

"""Functions for checking Openstack versions."""
import logging
from collections import defaultdict

from cou.steps import UpgradeStep
from cou.steps.analyze import Analysis
from cou.utils.os_versions import CompareOpenStack
from cou.utils.upgrade_utils import UPGRADE_ORDER, determine_next_openstack_release


def openstack_version_check_apps(analysis_result: Analysis) -> str:
    # E.g: {"ussuri": {"keystone"}, "victoria": {"cinder"}}
    os_versions: defaultdict[str, set] = defaultdict(set)

    for app in analysis_result.apps:
        for os_version_unit in app.os_release_units.keys():
            os_versions[os_version_unit].add(app)

    if len(os_versions) > 1:
        logging.warning("Charms are not in the same openstack version")
        os_sequence = sorted(os_versions.keys(), key=CompareOpenStack)
        current_os_release = os_sequence[0]
        _, next_os_release = determine_next_openstack_release(current_os_release)

    else:
        current_os_release = list(os_versions)[0]
        next_os_release = determine_next_openstack_release(current_os_release)[1]
        logging.info(
            (
                "All supported charms are in the same openstack version "
                "and can be upgrade from: %s to: %s"
            ),
            current_os_release,
            next_os_release,
        )
    apps_to_upgrade = list(os_versions[current_os_release])
    apps_to_upgrade.sort(key=lambda app: UPGRADE_ORDER.index(app.charm))
    return current_os_release, next_os_release, apps_to_upgrade
