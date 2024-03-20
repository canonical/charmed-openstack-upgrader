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
    AuxiliaryApplication,
    CephMon,
    OvnPrincipal,
    RabbitMQServer,
)
from cou.apps.auxiliary_subordinate import (  # noqa: F401
    AuxiliarySubordinateApplication,
    OvnSubordinate,
)
from cou.apps.base import OpenStackApplication
from cou.apps.channel_based import ChannelBasedApplication  # noqa: F401
from cou.apps.core import Keystone, Octavia  # noqa: F401
from cou.apps.subordinate import SubordinateApplication, SubordinateBase  # noqa: F401
from cou.commands import CLIargs
from cou.exceptions import (
    HaltUpgradePlanGeneration,
    HighestReleaseAchieved,
    NoTargetError,
    OutOfSupportRange,
)
from cou.steps import PreUpgradeStep, UpgradePlan
from cou.steps.analyze import Analysis
from cou.steps.backup import backup
from cou.utils.juju_utils import DEFAULT_TIMEOUT
from cou.utils.openstack import LTS_TO_OS_RELEASE, OpenStackRelease

logger = logging.getLogger(__name__)


async def generate_plan(analysis_result: Analysis, args: CLIargs) -> UpgradePlan:
    """Generate plan for upgrade.

    :param analysis_result: Analysis result.
    :type analysis_result: Analysis
    :param args: CLI arguments
    :type args: CLIargs
    :return: Plan with all upgrade steps necessary based on the Analysis.
    :rtype: UpgradePlan
    """
    target = determine_upgrade_target(
        analysis_result.current_cloud_os_release, analysis_result.current_cloud_series
    )

    plan = UpgradePlan(
        f"Upgrade cloud from '{analysis_result.current_cloud_os_release}' to '{target}'"
    )
    plan.add_step(
        PreUpgradeStep(
            description="Verify that all OpenStack applications are in idle state",
            parallel=False,
            coro=analysis_result.model.wait_for_active_idle(
                # NOTE (rgildein): We need to DEFAULT_TIMEOUT so it's possible to change if
                # a network is too slow, this could cause an issue.
                # We are using max function to ensure timeout is always at least 11 (1 second
                # higher than the idle_period to prevent false negative).
                timeout=max(DEFAULT_TIMEOUT + 1, 11),
                idle_period=10,
                raise_on_blocked=True,
            ),
        )
    )
    if args.backup:
        plan.add_step(
            PreUpgradeStep(
                description="Back up MySQL databases",
                parallel=False,
                coro=backup(analysis_result.model),
            )
        )

    control_plane_principal_upgrade_plan = await create_upgrade_group(
        apps=analysis_result.apps_control_plane,
        description="Control Plane principal(s) upgrade plan",
        target=target,
        filter_function=lambda app: not isinstance(app, SubordinateBase),
    )
    plan.add_step(control_plane_principal_upgrade_plan)

    control_plane_subordinate_upgrade_plan = await create_upgrade_group(
        apps=analysis_result.apps_control_plane,
        description="Control Plane subordinate(s) upgrade plan",
        target=target,
        filter_function=lambda app: isinstance(app, SubordinateBase),
    )
    plan.add_step(control_plane_subordinate_upgrade_plan)

    return plan


async def create_upgrade_group(
    apps: list[OpenStackApplication],
    target: OpenStackRelease,
    description: str,
    filter_function: Callable[[OpenStackApplication], bool],
) -> UpgradePlan:
    """Create upgrade group.

    :param apps: Result of the analysis.
    :type apps: list[OpenStackApplication]
    :param target: Target OpenStack release.
    :type target: OpenStackRelease
    :param description: Description of the upgrade plan.
    :type description: str
    :param filter_function: Function to filter applications.
    :type filter_function: Callable[[OpenStackApplication], bool]
    :raises Exception: When cannot generate upgrade plan.
    :return: Upgrade group.
    :rtype: UpgradePlan
    """
    group_upgrade_plan = UpgradePlan(description)
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
) -> OpenStackRelease:
    """Determine the target release to upgrade to.

    Inform user if the cloud is already at the highest supporting release of the current series.
    :param current_os_release: The current minimum OS release in cloud.
    :type current_os_release: Optional[OpenStackRelease]
    :param current_series: The current minimum Ubuntu series in cloud.
    :type current_series: Optional[str]
    :raises NoTargetError: When cannot find target to upgrade.
    :raises HighestReleaseAchieved: When the highest possible OpenStack release is
    already achieved.
    :raises OutOfSupportRange: When the OpenStack release or Ubuntu series is out of the current
    supporting range.
    :return: The target OS release to upgrade the cloud to.
    :rtype: OpenStackRelease
    """
    if not current_os_release:
        raise NoTargetError(
            "Cannot determine the current OS release in the cloud. "
            "Is this a valid OpenStack cloud?"
        )

    if not current_series:
        raise NoTargetError(
            "Cannot determine the current Ubuntu series in the cloud. "
            "Is this a valid OpenStack cloud?"
        )

    # raise exception if the series is not supported
    supporting_lts_series = ", ".join(LTS_TO_OS_RELEASE)
    if current_series not in supporting_lts_series:
        raise OutOfSupportRange(
            f"Cloud series '{current_series}' is not a Ubuntu LTS series supported by COU. "
            f"The supporting series are: {supporting_lts_series}"
        )

    # Check if the release is the "last" supported by the series
    if str(current_os_release) == LTS_TO_OS_RELEASE[current_series][-1]:
        raise HighestReleaseAchieved(
            f"No upgrades available for OpenStack {str(current_os_release).capitalize()} on "
            f"Ubuntu {current_series.capitalize()}.\nNewer OpenStack releases may be available "
            "after upgrading to a later Ubuntu series."
        )

    # get the next release as the target from the current cloud os release
    target = current_os_release.next_release
    if not target:
        raise NoTargetError(
            "Cannot find target to upgrade. Current minimum OS release is "
            f"'{str(current_os_release)}'. Current Ubuntu series is '{current_series}'."
        )

    supporting_os_release = ", ".join(LTS_TO_OS_RELEASE[current_series])
    # raise exception if the upgrade scope is not supported by the current series
    if (
        str(current_os_release) not in supporting_os_release
        or str(target) not in supporting_os_release
    ):
        raise OutOfSupportRange(
            f"Unable to upgrade cloud from `{current_series}` to '{target}'. Both the from and "
            f"to releases need to be supported by the current Ubuntu series '{current_series}': "
            f"{supporting_os_release}."
        )

    return target


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
