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

import cou.utils.juju_utils as utils
from cou.steps import UpgradeStep
from cou.steps.analyze import Analysis, Application
from cou.steps.backup import backup
from cou.steps.openstack_checks import openstack_version_check_apps
from cou.steps.upgrade.basic import BasicCharmUpgradePlan
from cou.steps.upgrade.ceph import CephUpgradePlan
from cou.utils.juju_utils import async_block_until_all_units_idle


async def generate_plan(args: Analysis) -> UpgradeStep:
    """Generate plan for upgrade.

    :param args: Analysis result.
    :type args: Analysis
    :return: Plan with all upgrade steps necessary based on the Analysis.
    :rtype: UpgradeStep
    """
    logging.info(args)  # for placeholder
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
        description="Refresh current channel", parallel=False, function=None
    )
    plan_refresh_next_channel = UpgradeStep(
        description="Refresh next channel", parallel=False, function=None
    )
    plan_disable_action_managed = UpgradeStep(
        description="Set action-managed-upgrade to False (all-in-one)",
        parallel=False,
        function=None,
    )
    plan_payload_upgrade = UpgradeStep(
        description="Payload upgrade", parallel=False, function=None
    )

    for app in apps:
        app_upgrade_plan = PLAN_HANDLER.get(app.charm, BasicCharmUpgradePlan)(
            app, current_os_release, next_release
        )
        plan_refresh_current_channel = app_upgrade_plan.add_plan_refresh_current_channel(
            plan_refresh_current_channel
        )
        plan_refresh_next_channel = app_upgrade_plan.add_plan_refresh_next_channel(
            plan_refresh_next_channel
        )
        plan_disable_action_managed = app_upgrade_plan.add_plan_disable_action_managed(
            plan_disable_action_managed
        )
        plan_payload_upgrade = app_upgrade_plan.add_plan_payload_upgrade(plan_payload_upgrade)

    sub_plans = [
        plan_refresh_current_channel,
        plan_refresh_next_channel,
        plan_disable_action_managed,
        plan_payload_upgrade,
    ]
    for sub_plan in sub_plans:
        if sub_plan.sub_steps:
            sub_plan.add_step(wait_for_idle())
            plan.add_step(sub_plan)

    return plan
