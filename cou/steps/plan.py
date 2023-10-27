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
from typing import Callable, Optional

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
from cou.apps.core import Keystone  # noqa: F401
from cou.apps.subordinate import (  # noqa: F401
    OpenStackSubordinateApplication,
    SubordinateBaseClass,
)
from cou.exceptions import (
    HaltUpgradePlanGeneration,
    HighestReleaseAchieved,
    NoTargetError,
    ReleaseOutOfRange,
)
from cou.steps import UpgradeStep
from cou.steps.analyze import Analysis
from cou.steps.backup import backup
from cou.utils.openstack import LTS_TO_OS_RELEASE, OpenStackRelease

logger = logging.getLogger(__name__)


async def generate_plan(analysis_result: Analysis) -> UpgradeStep:
    """Generate plan for upgrade.

    :param analysis_result: Analysis result.
    :type analysis_result: Analysis
    :raises NoTargetError: When cannot find target to upgrade.
    :raises HighestReleaseAchieved: When the highest possible OpenStack release is
    already achieved.
    :raises ReleaseOutOfRange: When the release is out of the current supporting range.
    :return: Plan with all upgrade steps necessary based on the Analysis.
    :rtype: UpgradeStep
    """
    target = determine_upgrade_target(
        analysis_result.current_cloud_os_release, analysis_result.current_cloud_series
    )

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


def determine_upgrade_target(
    current_os_release: Optional[OpenStackRelease], current_series: Optional[str]
) -> str:
    """Determine the target release to upgrade to.

    Inform user if the cloud is already at the highest supporting release of the current series.
    :param current_os_release: The current minimum OS release in cloud.
    :type current_os_release: Optional[OpenStackRelease]
    :param current_series: The current minimum Ubuntu series in cloud.
    :type current_series: Optional[str]
    :raises NoTargetError: When cannot find target to upgrade.
    :raises HighestReleaseAchieved: When the highest possible OpenStack release is
    already achieved.
    :raises ReleaseOutOfRange: When the release is out of the current supporting range.
    :return: The target OS release to upgrade the cloud to.
    :rtype: str
    """
    if not current_os_release:
        raise NoTargetError(
            "Cannot determine the current OS release in the cloud. "
            "Is this a valid OpenStack cloud?"
        )

    supporting_lts_series = ", ".join(LTS_TO_OS_RELEASE)
    if not current_series:
        raise NoTargetError(
            "Cannot determine the current Ubuntu series of the cloud series. "
            f"The supporting series are: {supporting_lts_series}"
        )

    try:
        # Check if the release is the "last" supported by the series
        if str(current_os_release) == LTS_TO_OS_RELEASE[current_series][-1]:
            raise HighestReleaseAchieved(
                f"The cloud is already at the latest OpenStack release '{current_os_release}' "
                f"compatible with series '{current_series}', and COU does not support series "
                "upgrade. Please manually upgrade series and run COU again."
            )

        # get the next release as the target from the current cloud os release
        target = current_os_release.next_release
        if not target:
            raise NoTargetError(
                "Cannot find target to upgrade. Current minimum OS release is "
                f"'{str(current_os_release)}'. Current Ubuntu series is '{current_series}'."
            )
        # raise exception if the upgrade is not in range from ussuri to yoga
        if current_os_release < OpenStackRelease("ussuri") or OpenStackRelease(
            target
        ) > OpenStackRelease("yoga"):
            raise ReleaseOutOfRange(
                "At the moment COU only supports upgrade in the range of `ussuri` and `yoga` "
                "(inclusive) for `focal` series. Current minimum OS release is "
                f"'{str(current_os_release)}'. Current Ubuntu series is '{current_series}'."
            )
        return target
    except KeyError:  # raise exception if the current series is not in LTS_TO_OS_RELEASE map
        raise NoTargetError(
            f"Cloud series '{current_series}' is not a recognized Ubuntu LTS series. "
            f"The supporting series are: {supporting_lts_series}"
        ) from KeyError
