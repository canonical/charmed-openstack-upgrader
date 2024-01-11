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

import argparse
import logging
from typing import Any, Callable, Optional

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
from cou.exceptions import (
    DataPlaneCannotUpgrade,
    DataPlaneMachineFilterError,
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


def pre_plan_sane_checks(args: argparse.Namespace, analysis_result: Analysis) -> None:
    """Pre checks to generate the upgrade plan.

    :param args: CLI arguments
    :type args: argparse.Namespace
    :param analysis_result: Analysis result.
    :type analysis_result: Analysis
    """
    checks = [
        is_valid_openstack_cloud,
        is_supported_series,
        is_highest_release_achieved,
        is_target_supported,
    ]
    if args.upgrade_group == "data-plane":
        checks.append(is_data_plane_ready_to_upgrade)
        check_data_plane_cli_input(args, analysis_result)
    for check in checks:
        check(analysis_result)


def is_valid_openstack_cloud(analysis_result: Analysis) -> None:
    """Check if the model passed is a valid OpenStack cloud.

    :param analysis_result: Analysis result
    :type analysis_result: Analysis
    :raises NoTargetError: When cannot determine the current OS release
        or Ubuntu series.
    """
    current_os_release = analysis_result.current_cloud_os_release
    current_series = analysis_result.current_cloud_series
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


def is_supported_series(analysis_result: Analysis) -> None:
    """Check the Ubuntu series of the cloud to see if it is supported.

    :param analysis_result: Analysis result.
    :type analysis_result: Analysis
    :raises OutOfSupportRange: When series is not supported.
    """
    current_series = analysis_result.current_cloud_series
    supporting_lts_series = ", ".join(LTS_TO_OS_RELEASE)
    # series already checked at is_valid_openstack_cloud
    if current_series not in supporting_lts_series:  # type: ignore
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
    # series and current OS release already checked at is_valid_openstack_cloud
    current_os_release = analysis_result.current_cloud_os_release
    current_series = analysis_result.current_cloud_series
    if str(current_os_release) == LTS_TO_OS_RELEASE[current_series][-1]:  # type: ignore
        raise HighestReleaseAchieved(
            f"No upgrades available for OpenStack {str(current_os_release).capitalize()} on "
            f"Ubuntu {current_series.capitalize()}.\nNewer OpenStack releases "  # type: ignore
            "may be available after upgrading to a later Ubuntu series."
        )


def is_target_supported(analysis_result: Analysis) -> None:
    """Check if the target to upgrade is supported.

    :param analysis_result: Analysis result.
    :type analysis_result: Analysis
    :raises NoTargetError: When cannot find target to upgrade
    :raises OutOfSupportRange: When the upgrade scope is not supported
        by the current series.
    """
    current_os_release = analysis_result.current_cloud_os_release
    current_series = analysis_result.current_cloud_series
    if current_os_release and current_series:
        target = current_os_release.next_release
        if not target:
            raise NoTargetError(
                "Cannot find target to upgrade. Current minimum OS release is "
                f"'{str(current_os_release)}'. Current Ubuntu series is '{current_series}'."
            )

        supporting_os_release = ", ".join(LTS_TO_OS_RELEASE[current_series])
        if (
            str(current_os_release) not in supporting_os_release
            or str(target) not in supporting_os_release
        ):
            raise OutOfSupportRange(
                f"Unable to upgrade cloud from `{current_series}` to '{target}'. "
                "Both the from and to releases need to be supported by the current "
                "Ubuntu series '{current_series}': {supporting_os_release}."
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
            "Cannot find data-plane charms. Is this a valid OpenStack cloud?"
        )
    if not is_control_plane_upgraded(analysis_result):
        raise DataPlaneCannotUpgrade("Please, upgrade control-plane before data-plane")


def check_data_plane_cli_input(args: argparse.Namespace, analysis_result: Analysis) -> None:
    """Sane checks from the parameters passed in the cli to upgrade data-plane.

    :param args: CLI arguments
    :type args: argparse.Namespace
    :param analysis_result: Analysis result
    :type analysis_result: Analysis
    """
    data_plane_machines = {
        id: machine for id, machine in analysis_result.machines.items() if machine.is_data_plane
    }

    if machines_from_cli := parametrize_cli_inputs(args.machines):
        all_machines = set(analysis_result.machines.keys())
        data_plane_membership_check(
            all_machines, set(data_plane_machines.keys()), machines_from_cli, "Machines"
        )

    elif hostnames_from_cli := parametrize_cli_inputs(args.hostnames):
        all_hostnames = {machine.hostname for machine in analysis_result.machines.values()}
        data_plane_hostnames = {machine.hostname for machine in data_plane_machines.values()}
        data_plane_membership_check(
            all_hostnames, data_plane_hostnames, hostnames_from_cli, "Hostnames"
        )

    elif azs_from_cli := parametrize_cli_inputs(args.availability_zones):
        all_azs = {machine.az for machine in analysis_result.machines.values()}
        data_plane_azs = {machine.az for machine in data_plane_machines.values()}
        data_plane_membership_check(all_azs, data_plane_azs, azs_from_cli, "Availability Zones")


def parametrize_cli_inputs(cli_input: list[str]) -> Optional[set]:
    """Parametrize the cli inputs.

    :param cli_input: cli inputs.
    :type cli_input: list[str]
    :return: A set of elements passed in the cli.
    :rtype: Optional[set]
    """
    if cli_input:
        return {raw_item.strip() for raw_items in cli_input for raw_item in raw_items.split(",")}
    return None


def data_plane_membership_check(
    all_options: set[Any],
    data_plane_options: set[Any],
    cli_input: Optional[set[str]],
    parameter_type: str,
) -> None:
    """Check if the parameter passed are member of data-plane.

    :param all_options: All possible options for a parameter.
    :type all_options: set[Any]
    :param data_plane_options: All data-plane possible options for a parameter.
    :type data_plane_options: set[Any]
    :param cli_input: The input that come from the cli
    :type cli_input: Optional[set[str]]
    :param parameter_type: Type of the parameter passed (az, hostname or machine).
    :type parameter_type: str
    :raises DataPlaneMachineFilterError: When the value passed from the user is not sane.
    """
    if all_options != {None} and cli_input and not cli_input.issubset(all_options):
        raise DataPlaneMachineFilterError(
            f"{parameter_type}: {cli_input - all_options} don't exist."
        )
    if cli_input and not cli_input.issubset(data_plane_options):
        raise DataPlaneMachineFilterError(
            f"{parameter_type}: {cli_input - data_plane_options} are not considered as data-plane."
        )


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

    if control_plane and data_plane:
        return control_plane > data_plane
    return False


async def generate_plan(analysis_result: Analysis, backup_database: bool) -> UpgradePlan:
    """Generate plan for upgrade.

    :param analysis_result: Analysis result.
    :type analysis_result: Analysis
    :param backup_database: Whether to create database backup before upgrade.
    :type backup_database: bool
    :return: Plan with all upgrade steps necessary based on the Analysis.
    :rtype: UpgradePlan
    """
    # target already checked on pre_plan_sane_checks
    target = analysis_result.current_cloud_os_release.next_release  # type: ignore

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
    if backup_database:
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
        target=target,  # type: ignore
        filter_function=lambda app: not isinstance(app, SubordinateBaseClass),
    )
    plan.add_step(control_plane_principal_upgrade_plan)

    control_plane_subordinate_upgrade_plan = await create_upgrade_group(
        apps=analysis_result.apps_control_plane,
        description="Control Plane subordinate(s) upgrade plan",
        target=target,  # type: ignore
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
