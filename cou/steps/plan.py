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

# NOTE we need to import the modules to register the charms with the register_application
# decorator
# pylint: disable=unused-import
from cou.apps.auxiliary import (  # noqa: F401
    CephMonApplication,
    OpenStackAuxiliaryApplication,
    OvnPrincipalApplication,
    RabbitMQServer,
)
from cou.apps.auxiliary_subordinate import (  # noqa: F401
    OpenStackAuxiliarySubordinateApplication,
    OvnSubordinateApplication,
)
from cou.apps.base import OpenStackApplication
from cou.apps.channel_based import OpenStackChannelBasedApplication  # noqa: F401
from cou.apps.core import Keystone  # noqa: F401
from cou.apps.subordinate import (  # noqa: F401
    OpenStackSubordinateApplication,
    SubordinateBaseClass,
)
from cou.exceptions import HaltUpgradePlanGeneration, NoTargetError
from cou.steps import UpgradeStep
from cou.steps.analyze import Analysis
from cou.steps.backup import backup
from cou.utils.openstack import OpenStackRelease

logger = logging.getLogger(__name__)


async def generate_plan(analysis_result: Analysis) -> UpgradeStep:
    """Generate plan for upgrade.

    :param analysis_result: Analysis result.
    :type analysis_result: Analysis
    :raises NoTargetError: When cannot find target to upgrade.
    :return: Plan with all upgrade steps necessary based on the Analysis.
    :rtype: UpgradeStep
    """
    target = getattr(analysis_result.current_cloud_os_release, "next_release", None)
    if not target:
        raise NoTargetError("Cannot find target to upgrade.")

    plan = UpgradeStep(description="Top level plan", parallel=False)
    plan.add_step(
        UpgradeStep(
            description="backup mysql databases",
            parallel=False,
            coro=backup(analysis_result.model),
        )
    )

    control_plane_principal_upgrade_plan = await create_upgrade_group(
        apps=analysis_result.apps_control_plane,
        description="Control Plane principal(s) upgrade plan",
        target=target,
        filter_function=lambda app: not isinstance(app, SubordinateBaseClass),
    )
    plan.add_step(control_plane_principal_upgrade_plan)

    control_plane_subordinate_upgrade_plan = await create_upgrade_group(
        apps=analysis_result.apps_control_plane,
        description="Control Plane subordinate(s) upgrade plan",
        target=target,
        filter_function=lambda app: isinstance(app, SubordinateBaseClass),
    )
    plan.add_step(control_plane_subordinate_upgrade_plan)

    return plan


async def create_upgrade_group(
    apps: list[OpenStackApplication],
    target: OpenStackRelease,
    description: str,
    filter_function: Callable[[OpenStackApplication], bool],
) -> UpgradeStep:
    """Create upgrade group.

    :param apps: Result of the analysis.
    :type apps: list[OpenStackApplication]
    :param target: Target OpenStack release.
    :type target: OpenStackRelease
    :param description: Description of the upgrade step.
    :type description: str
    :param filter_function: Function to filter applications.
    :type filter_function: Callable[[OpenStackApplication], bool]
    :raises Exception: When cannot generate upgrade plan.
    :return: Upgrade group.
    :rtype: UpgradeStep
    """
    group_upgrade_plan = UpgradeStep(description=description, parallel=False)
    for app in filter(filter_function, apps):
        try:
            app_upgrade_plan = app.generate_upgrade_plan(target)
            group_upgrade_plan.add_step(app_upgrade_plan)
        except HaltUpgradePlanGeneration as exc:
            # we do not care if applications halt the upgrade plan generation
            # for some known reason.
            logger.debug("'%s' halted the upgrade planning generation: %s", app.name, exc)
        except Exception as exc:
            logger.error("Cannot generate upgrade plan for '%s': %s", app.name, exc)
            raise

    return group_upgrade_plan


def manually_upgrade_data_plane(analysis_result: Analysis) -> None:
    """Warning message to upgrade data plane charms if necessary.

    NOTE(gabrielcocenza) This function should be removed when cou starts
    supporting data plan upgrades.
    :param analysis_result: Analysis result.
    :type analysis_result: Analysis
    """
    if (
        analysis_result.min_os_version_control_plane
        and analysis_result.min_os_version_data_plane
        and (
            analysis_result.min_os_version_control_plane
            > analysis_result.min_os_version_data_plane
        )
    ):
        data_plane_apps = ", ".join([app.name for app in analysis_result.apps_data_plane])
        print(f"WARNING: Please upgrade manually the data plane apps: {data_plane_apps}")
