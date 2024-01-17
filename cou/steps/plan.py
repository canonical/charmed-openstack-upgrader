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
from cou.apps.core import Keystone, Octavia  # noqa: F401
from cou.apps.subordinate import (  # noqa: F401
    OpenStackSubordinateApplication,
    SubordinateBaseClass,
)
from cou.commands import DATA_PLANE, CLIargs
from cou.exceptions import (
    DataPlaneCannotUpgrade,
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


def pre_plan_sane_checks(args: CLIargs, analysis_result: Analysis) -> None:
    """Pre checks to generate the upgrade plan.

    :param args: CLI arguments
    :type args: Namespace
    :param analysis_result: Analysis result.
    :type analysis_result: Analysis
    """
    is_valid_openstack_cloud(analysis_result)
    is_supported_series(analysis_result)
    is_highest_release_achieved(analysis_result)

    if args.upgrade_group == DATA_PLANE:
        is_data_plane_ready_to_upgrade(analysis_result)


def is_valid_openstack_cloud(analysis_result: Analysis) -> None:
    """Check if the model passed is a valid OpenStack cloud.

    :param analysis_result: Analysis result
    :type analysis_result: Analysis
    :raises NoTargetError: When cannot determine the current OS release
        or Ubuntu series.
    """
    if not analysis_result.current_cloud_os_release:
        raise NoTargetError(
            "Cannot determine the current OS release in the cloud. "
            "Is this a valid OpenStack cloud?"
        )

    if not analysis_result.current_cloud_series:
        raise NoTargetError(
            "Cannot determine the current Ubuntu series in the cloud. "
            "Is this a valid OpenStack cloud?"
        )


def is_supported_series(analysis_result: Analysis) -> None:
    """Check the Ubuntu series of the cloud to see if it is supported.

    :param analysis_result: Analysis result.
    :type analysis_result: Analysis
    :raises OutOfSupportRange: When series is not supported.
    """
    supporting_lts_series = ", ".join(LTS_TO_OS_RELEASE)
    # series already checked at is_valid_openstack_cloud
    if (
        current_series := analysis_result.current_cloud_series
    ) and current_series not in LTS_TO_OS_RELEASE:
        raise OutOfSupportRange(
            f"Cloud series '{current_series}' is not a Ubuntu LTS series supported by COU. "
            f"The supporting series are: {supporting_lts_series}"
        )


def is_highest_release_achieved(analysis_result: Analysis) -> None:
    """Check if the highest OpenStack release is reached by the ubuntu series.

    :param analysis_result: Analysis result.
    :type analysis_result: Analysis
    :raises HighestReleaseAchieved: When the OpenStack release is the last supported by the series.
    """
    if (
        (current_os_release := analysis_result.current_cloud_os_release)
        and (current_series := analysis_result.current_cloud_series)
        and str(current_os_release) == LTS_TO_OS_RELEASE[current_series][-1]
    ):
        raise HighestReleaseAchieved(
            f"No upgrades available for OpenStack {str(current_os_release).capitalize()} on "
            f"Ubuntu {current_series.capitalize()}.\nNewer OpenStack releases "
            "may be available after upgrading to a later Ubuntu series."
        )


def is_data_plane_ready_to_upgrade(analysis_result: Analysis) -> None:
    """Check if data plane is ready to upgrade.

    To be able to upgrade data-plane, first all control plane apps should be upgraded.

    :param analysis_result: Analysis result
    :type analysis_result: Analysis
    :raises DataPlaneCannotUpgrade: When data-plane is not ready to upgrade.
    """
    if not analysis_result.min_os_version_data_plane:
        raise DataPlaneCannotUpgrade(
            "Cannot find data-plane apps. Is this a valid OpenStack cloud?"
        )
    if not is_control_plane_upgraded(analysis_result):
        raise DataPlaneCannotUpgrade("Please, upgrade control-plane before data-plane")


def is_control_plane_upgraded(analysis_result: Analysis) -> bool:
    """Check if control plane is already upgraded.

    Control-plane will be considered as upgraded when the OpenStack version of it
    is bigger than the data-plane.

    :param analysis_result: Analysis result
    :type analysis_result: Analysis
    :return: Whether the control plane is already upgraded or not.
    :rtype: bool
    """
    control_plane = analysis_result.min_os_version_control_plane
    data_plane = analysis_result.min_os_version_data_plane

    return bool(control_plane and data_plane and control_plane > data_plane)


def determine_upgrade_target(analysis_result: Analysis) -> OpenStackRelease:
    """Determine the target release to upgrade to.

    :param analysis_result: Analysis result.
    :type analysis_result: Analysis
    :raises NoTargetError: When cannot find target to upgrade
    :raises OutOfSupportRange: When the upgrade scope is not supported
        by the current series.
    :return: The target OS release to upgrade the cloud to.
    :rtype: OpenStackRelease
    """
    if (
        (current_os_release := analysis_result.current_cloud_os_release)
        and (current_series := analysis_result.current_cloud_series)
        and not (target := current_os_release.next_release)
    ):
        raise NoTargetError(
            "Cannot find target to upgrade. Current minimum OS release is "
            f"'{str(current_os_release)}'. Current Ubuntu series is '{current_series}'."
        )

    if (
        current_series
        and (supporting_os_release := ", ".join(LTS_TO_OS_RELEASE[current_series]))
        and str(current_os_release) not in supporting_os_release
        or str(target) not in supporting_os_release
    ):
        raise OutOfSupportRange(
            f"Unable to upgrade cloud from `{current_series}` to '{target}'. "
            "Both the from and to releases need to be supported by the current "
            "Ubuntu series '{current_series}': {supporting_os_release}."
        )

    return target  # type: ignore


async def generate_plan(analysis_result: Analysis, args: CLIargs) -> UpgradePlan:
    """Generate plan for upgrade.

    :param analysis_result: Analysis result.
    :type analysis_result: Analysis
    :param args: CLI arguments
    :type args: CLIargs
    :return: Plan with all upgrade steps necessary based on the Analysis.
    :rtype: UpgradePlan
    """
    pre_plan_sane_checks(args, analysis_result)
    target = determine_upgrade_target(analysis_result)

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
                description="Backup mysql databases",
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
) -> UpgradePlan:
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
