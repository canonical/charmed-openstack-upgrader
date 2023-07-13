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
from typing import List, Tuple

import cou.utils.juju_utils as utils
from cou.steps import UpgradeStep
from cou.steps.analyze import Analysis, Application
from cou.steps.backup import backup
from cou.utils.os_versions import CompareOpenStack
from cou.utils.upgrade_utils import UPGRADE_ORDER, determine_next_openstack_release


async def generate_plan(analysis_result: Analysis) -> UpgradeStep:
    """Generate plan for upgrade.

    :param args: Analysis result.
    :type args: Analysis
    :return: Plan with all upgrade steps necessary based on the Analysis.
    :rtype: UpgradeStep
    """
    current_os_release, next_os_release, apps_to_upgrade = determine_apps_to_upgrade(
        analysis_result
    )
    plan = UpgradeStep(description="Top level plan", parallel=False, function=None)
    plan.add_step(
        UpgradeStep(
            description="backup mysql databases",
            parallel=False,
            function=backup,
            model_name=await utils.async_get_current_model_name(),
        )
    )
    plan_refresh_current_channel = UpgradeStep(
        description="Refresh current channel", parallel=True, function=None
    )
    plan_refresh_next_channel = UpgradeStep(
        description="Refresh next channel", parallel=True, function=None
    )
    plan_disable_action_managed = UpgradeStep(
        description="Set action-managed-upgrade to False (all-in-one)",
        parallel=True,
        function=None,
    )
    plan_payload_upgrade = UpgradeStep(
        description="Payload upgrade", parallel=False, function=None
    )

    for app in apps_to_upgrade:
        plan_refresh_current_channel = app.add_plan_refresh_current_channel(
            plan_refresh_current_channel
        )
        plan_refresh_next_channel = app.add_plan_refresh_next_channel(plan_refresh_next_channel)
        plan_disable_action_managed = app.add_plan_disable_action_managed(
            plan_disable_action_managed
        )
        plan_payload_upgrade = app.add_plan_payload_upgrade(plan_payload_upgrade)

    sub_plans = [
        plan_refresh_current_channel,
        plan_refresh_next_channel,
        plan_disable_action_managed,
        plan_payload_upgrade,
    ]
    for sub_plan in sub_plans:
        if sub_plan.sub_steps:
            plan.add_step(sub_plan)

    return plan


def determine_apps_to_upgrade(analysis_result: Analysis) -> Tuple[str, str, List[Application]]:
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
    current_os_release = os_sequence[0]
    _, next_os_release = determine_next_openstack_release(current_os_release)

    if len(os_versions) > 1:
        logging.warning("Charms are not in the same openstack version")

    else:
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
