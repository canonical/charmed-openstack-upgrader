# Copyright 2023 Canonical Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Upgrade planning utilities."""

import logging

# NOTE we need to import the module to register the charms with the register_application decorator
# pylint: disable=unused-import
from cou.apps.auxiliary import AuxiliaryOpenStackApplication  # noqa: F401
from cou.exceptions import HaltUpgradePlanGeneration, NoTargetError
from cou.steps import UpgradeStep
from cou.steps.analyze import Analysis
from cou.steps.backup import backup

logger = logging.getLogger(__name__)


async def generate_plan(analysis_result: Analysis) -> UpgradeStep:
    """Generate plan for upgrade.

    :param args: Analysis result.
    :type args: Analysis
    :return: Plan with all upgrade steps necessary based on the Analysis.
    :rtype: UpgradeStep
    """
    target = getattr(analysis_result.current_cloud_os_release, "next_release", None)
    if not target:
        raise NoTargetError("Cannot find target to upgrade.")

    plan = UpgradeStep(description="Top level plan", parallel=False, function=None)
    plan.add_step(
        UpgradeStep(description="backup mysql databases", parallel=False, function=backup)
    )

    upgrade_plan = UpgradeStep(
        description="Application(s) upgrade plan", parallel=False, function=None
    )
    for app in analysis_result.apps:
        try:
            app_upgrade_plan = app.generate_upgrade_plan(target)
        except HaltUpgradePlanGeneration as exc:
            # we do not care if applications halt the upgrade plan generation
            # for some known reason.
            logger.debug("'%s' halted the upgrade planning generation: %s", app.name, exc)
            app_upgrade_plan = None
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Cannot generate upgrade plan for '%s': %s", app.name, exc)
            raise
        if app_upgrade_plan:
            upgrade_plan.add_step(app_upgrade_plan)

    plan.add_step(upgrade_plan)
    return plan
