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

"""Upgrade planning utilities."""

import logging
from collections import defaultdict
from typing import List

from cou.steps import UpgradeStep
from cou.steps.analyze import Analysis
from cou.apps.app import Application
from cou.steps.backup import backup
from cou.utils.openstack import (
    SPECIAL_CHARMS,
    UPGRADE_ORDER,
    CompareOpenStack,
    determine_next_openstack_release,
)

logger = logging.getLogger(__name__)


async def generate_plan(analysis_result: Analysis) -> UpgradeStep:
    """Generate plan for upgrade.

    :param args: Analysis result.
    :type args: Analysis
    :return: Plan with all upgrade steps necessary based on the Analysis.
    :rtype: UpgradeStep
    """
    apps_to_upgrade = determine_apps_to_upgrade(analysis_result)
    plan = UpgradeStep(description="Top level plan", parallel=False, function=None)
    plan.add_step(
        UpgradeStep(description="backup mysql databases", parallel=False, function=backup)
    )
    for app in apps_to_upgrade:
        plan.add_step(app.generate_upgrade_plan())
    return plan


def determine_apps_to_upgrade(analysis_result: Analysis) -> List[Application]:
    """Determine applications to upgrade.

    This function find the oldest OpenStack version in the deployment and
    select the applications to upgrade for the next version (N + 1).

    :param analysis_result: Analysis result containing all applications in the model.
    :type analysis_result: Analysis
    :return: Tuple containing the current and next OpenStack release and a  list
        of applications to be upgraded.
    :rtype: Tuple[str, str, List[Application]]
    """
    # E.g: {"ussuri": {"keystone"}, "victoria": {"cinder"}}
    os_versions: defaultdict[str, set] = defaultdict(set)

    for app in analysis_result.apps:
        if app.current_os_release:
            os_versions[app.current_os_release].add(app)

    os_sequence = sorted(os_versions.keys(), key=CompareOpenStack)
    current_cloud_os_release = os_sequence[0]
    _, next_cloud_os_release = determine_next_openstack_release(current_cloud_os_release)

    if len(os_versions) > 1:
        logging.warning("Charms are not in the same openstack version")

    else:
        logging.info(
            (
                "All supported charms are in the same openstack version "
                "and can be upgrade from: %s to: %s"
            ),
            current_cloud_os_release,
            next_cloud_os_release,
        )
    apps_to_upgrade = list(os_versions[current_cloud_os_release])
    special_charms_to_upgrade = add_special_charms_to_upgrade(
        analysis_result.apps, next_cloud_os_release
    )
    apps_to_upgrade = apps_to_upgrade + special_charms_to_upgrade
    apps_to_upgrade.sort(key=lambda app: UPGRADE_ORDER.index(app.charm))
    return apps_to_upgrade


def add_special_charms_to_upgrade(apps, next_cloud_os_release):
    special_charms_to_upgrade = []
    for app in apps:
        if app.charm in SPECIAL_CHARMS and app.os_origin:
            os_origin = app.os_origin.split("-")[-1]
            if CompareOpenStack(app.current_os_release) < next_cloud_os_release or (
                os_origin != "distro" and CompareOpenStack(os_origin) < next_cloud_os_release
            ):
                special_charms_to_upgrade.append(app)
    return special_charms_to_upgrade
