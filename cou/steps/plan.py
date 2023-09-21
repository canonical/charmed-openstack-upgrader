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
from typing import Callable

from cou.apps.app import OpenStackApplication

# NOTE we need to import the modules to register the charms with the register_application
# decorator
# pylint: disable=unused-import
from cou.apps.auxiliary import OpenStackAuxiliaryApplication  # noqa: F401
from cou.apps.auxiliary_subordinate import OpenStackAuxiliarySubordinateApplication
from cou.apps.ceph import CephMonApplication  # noqa: F401
from cou.apps.subordinate import OpenStackSubordinateApplication
from cou.exceptions import HaltUpgradePlanGeneration, NoTargetError
from cou.steps import UpgradeStep
from cou.steps.analyze import Analysis
from cou.steps.backup import backup

logger = logging.getLogger(__name__)


async def generate_plan(analysis_result: Analysis) -> UpgradeStep:
    """Generate plan for upgrade.

    :param analysis_result: Analysis result.
    :type analysis_result: Analysis
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

    control_plane_principal_upgrade_plan = await create_upgrade_group(
        apps=analysis_result.apps_control_plane,
        description="Control Plane principal(s) upgrade plan",
        target=target,
        filter_function=lambda app: not isinstance(
            app, (OpenStackSubordinateApplication, OpenStackAuxiliarySubordinateApplication)
        ),
    )
    plan.add_step(control_plane_principal_upgrade_plan)

    control_plan_subordinate_upgrade_plan = await create_upgrade_group(
        apps=analysis_result.apps_control_plane,
        description="Control Plane subordinate(s) upgrade plan",
        target=target,
        filter_function=lambda app: isinstance(
            app, (OpenStackSubordinateApplication, OpenStackAuxiliarySubordinateApplication)
        ),
    )
    plan.add_step(control_plan_subordinate_upgrade_plan)

    return plan


async def create_upgrade_group(
    apps: list[OpenStackApplication],
    target: str,
    description: str,
    filter_function: Callable[[OpenStackApplication], bool],
) -> UpgradeStep:
    """Create upgrade group.

    :param apps: Result of the analysis.
    :type apps: list[OpenStackApplication]
    :param target: Target OpenStack version.
    :type target: str
    :param description: Description of the upgrade step.
    :type description: str
    :param filter_function: Function to filter applications.
    :type filter_function: Callable[[OpenStackApplication], bool]
    :return: Upgrade group.
    :rtype: UpgradeStep
    """
    group_upgrade_plan = UpgradeStep(description=description, parallel=False, function=None)
    for app in filter(filter_function, apps):
        try:
            app_upgrade_plan = app.generate_upgrade_plan(target)
            group_upgrade_plan.add_step(app_upgrade_plan)
        except HaltUpgradePlanGeneration as exc:
            # we do not care if applications halt the upgrade plan generation
            # for some known reason.
            logger.debug("'%s' halted the upgrade planning generation: %s", app.name, exc)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Cannot generate upgrade plan for '%s': %s", app.name, exc)
            raise

    return group_upgrade_plan
