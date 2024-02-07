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
from cou.apps.machine import Machine
from cou.apps.subordinate import (  # noqa: F401
    OpenStackSubordinateApplication,
    SubordinateBaseClass,
)
from cou.commands import CLIargs
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
from cou.utils.nova_compute import get_empty_hypervisors
from cou.utils.openstack import LTS_TO_OS_RELEASE, OpenStackRelease

logger = logging.getLogger(__name__)


def pre_plan_sanity_checks(args: CLIargs, analysis_result: Analysis) -> None:
    """Pre checks to generate the upgrade plan.

    :param args: CLI arguments
    :type args: CLIargs
    :param analysis_result: Analysis result.
    :type analysis_result: Analysis
    """
    verify_supported_series(analysis_result)
    verify_highest_release_achieved(analysis_result)

    if args.is_data_plane_command:
        verify_data_plane_ready_to_upgrade(analysis_result)
        verify_data_plane_cli_input(args, analysis_result)


def verify_supported_series(analysis_result: Analysis) -> None:
    """Verify the Ubuntu series of the cloud to see if it is supported.

    :param analysis_result: Analysis result.
    :type analysis_result: Analysis
    :raises OutOfSupportRange: When series is not supported.
    """
    supporting_lts_series = ", ".join(LTS_TO_OS_RELEASE)
    current_series = analysis_result.current_cloud_series
    if current_series not in LTS_TO_OS_RELEASE:
        raise OutOfSupportRange(
            f"Cloud series '{current_series}' is not a Ubuntu LTS series supported by COU. "
            f"The supporting series are: {supporting_lts_series}"
        )


def verify_highest_release_achieved(analysis_result: Analysis) -> None:
    """Verify if the highest OpenStack release is reached for the current Ubuntu series.

    :param analysis_result: Analysis result.
    :type analysis_result: Analysis
    :raises HighestReleaseAchieved: When the OpenStack release is the last supported by the series.
    """
    current_os_release = analysis_result.current_cloud_os_release
    current_series = analysis_result.current_cloud_series or ""
    last_supported = LTS_TO_OS_RELEASE.get(current_series, [])[-1]
    if current_os_release and current_series and str(current_os_release) == last_supported:
        raise HighestReleaseAchieved(
            f"No upgrades available for OpenStack {str(current_os_release).capitalize()} on "
            f"Ubuntu {current_series.capitalize()}.\nNewer OpenStack releases "
            "may be available after upgrading to a later Ubuntu series."
        )


def verify_data_plane_ready_to_upgrade(analysis_result: Analysis) -> None:
    """Verify if data plane is ready to upgrade.

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
    """Check if control plane has been fully upgraded.

    Control-plane will be considered as upgraded when the OpenStack version of it
    is higher than the data-plane.

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
    current_os_release, current_series = _get_os_release_and_series(analysis_result)

    target = current_os_release.next_release
    if not target:
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
            f"Unable to upgrade cloud from Ubuntu series `{current_series}` to '{target}'. "
            "Both the from and to releases need to be supported by the current "
            f"Ubuntu series '{current_series}': {supporting_os_release}."
        )

    return target


def verify_data_plane_cli_input(args: CLIargs, analysis_result: Analysis) -> None:
    """Sanity checks from the parameters passed in the cli to upgrade data-plane.

    :param args: CLI arguments
    :type args: CLIargs
    :param analysis_result: Analysis result
    :type analysis_result: Analysis
    """
    if cli_machines := args.machines:
        verify_data_plane_cli_machines(cli_machines, analysis_result)

    elif cli_hostnames := args.hostnames:
        verify_data_plane_cli_hostnames(cli_hostnames, analysis_result)

    elif cli_azs := args.availability_zones:
        verify_data_plane_cli_azs(cli_azs, analysis_result)


def verify_data_plane_cli_machines(cli_machines: set[str], analysis_result: Analysis) -> None:
    """Verify if the machines passed from the CLI are valid.

    :param cli_machines: Machines passed to the CLI as arguments
    :type cli_machines: set[str]
    :param analysis_result: Analysis result
    :type analysis_result: Analysis
    """
    verify_data_plane_membership(
        all_options=set(analysis_result.machines.keys()),
        data_plane_options=set(analysis_result.data_plane_machines.keys()),
        cli_input=cli_machines,
        parameter_type="Machine(s)",
    )


def verify_data_plane_cli_hostnames(cli_hostnames: set[str], analysis_result: Analysis) -> None:
    """Verify if the hostnames passed from the CLI are valid.

    :param cli_hostnames: Hostnames passed to the CLI as arguments
    :type cli_hostnames: set[str]
    :param analysis_result: Analysis result
    :type analysis_result: Analysis
    """
    all_hostnames = {machine.hostname for machine in analysis_result.machines.values()}
    data_plane_hostnames = {
        machine.hostname for machine in analysis_result.data_plane_machines.values()
    }

    verify_data_plane_membership(
        all_options=all_hostnames,
        data_plane_options=data_plane_hostnames,
        cli_input=cli_hostnames,
        parameter_type="Hostname(s)",
    )


def verify_data_plane_cli_azs(cli_azs: set[str], analysis_result: Analysis) -> None:
    """Verify if the availability zones passed from the CLI are valid.

    :param cli_azs: AZs passed to the CLI as arguments
    :type cli_azs: set[str]
    :param analysis_result:  Analysis result
    :type analysis_result: Analysis
    :raises DataPlaneMachineFilterError: When the cloud does not have availability zones.
    """
    all_azs: set[str] = {
        machine.az for machine in analysis_result.machines.values() if machine.az is not None
    }
    data_plane_azs: set[str] = {
        machine.az
        for machine in analysis_result.data_plane_machines.values()
        if machine.az is not None
    }

    if not data_plane_azs and not all_azs:
        raise DataPlaneMachineFilterError(
            "Cannot find Availability Zone(s). Is this a valid OpenStack cloud?"
        )

    verify_data_plane_membership(
        all_options=all_azs,
        data_plane_options=data_plane_azs,
        cli_input=cli_azs,
        parameter_type="Availability Zone(s)",
    )


def verify_data_plane_membership(
    all_options: set[str],
    data_plane_options: set[str],
    cli_input: set[str],
    parameter_type: str,
) -> None:
    """Check if the parameter passed are member of data-plane.

    :param all_options: All possible options for a parameter.
    :type all_options: set[str]
    :param data_plane_options: All data-plane possible options for a parameter.
    :type data_plane_options: set[str]
    :param cli_input: The input that come from the cli
    :type cli_input: set[str]
    :param parameter_type: Type of the parameter passed (az, hostname or machine).
    :type parameter_type: str
    :raises DataPlaneMachineFilterError: When the value passed from the user is not sane.
    """
    if not cli_input.issubset(all_options):
        raise DataPlaneMachineFilterError(
            f"{parameter_type}: {cli_input - all_options} don't exist."
        )
    if not cli_input.issubset(data_plane_options):
        raise DataPlaneMachineFilterError(
            f"{parameter_type}: {cli_input - data_plane_options} are not considered as data-plane."
        )


def _get_os_release_and_series(analysis_result: Analysis) -> tuple[OpenStackRelease, str]:
    """Get the current OpenStack release and series of the cloud.

    This function also checks if the model passed is a valid OpenStack cloud.

    :param analysis_result: Analysis result
    :type analysis_result: Analysis
    :raises NoTargetError: When cannot determine the current OS release
        or Ubuntu series.
    :return: Current OpenStack release and series of the cloud.
    :rtype: tuple[OpenStackRelease, str]
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
    return current_os_release, current_series


async def generate_plan(analysis_result: Analysis, args: CLIargs) -> UpgradePlan:
    """Generate plan for upgrade.

    :param analysis_result: Analysis result.
    :type analysis_result: Analysis
    :param args: CLI arguments
    :type args: CLIargs
    :return: Plan with all upgrade steps necessary based on the Analysis.
    :rtype: UpgradePlan
    """
    pre_plan_sanity_checks(args, analysis_result)
    set_upgrade_strategy(args, analysis_result)
    hypervisors = await filter_hypervisors_machines(args, analysis_result)
    logger.info("Hypervisors selected: %s", hypervisors)
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


async def filter_hypervisors_machines(args: CLIargs, analysis_result: Analysis) -> list[Machine]:
    """Filter the hypervisors to generate plan and upgrade.

    :param args: CLI arguments
    :type args: CLIargs
    :param analysis_result: Analysis result
    :type analysis_result: Analysis
    :return: hypervisors filtered to generate plan and upgrade.
    :rtype: list[Machine]
    """
    hypervisors_machines = await _get_upgradable_hypervisors_machines(args.force, analysis_result)

    if cli_machines := args.machines:
        return [machine for machine in hypervisors_machines if machine.machine_id in cli_machines]

    if cli_hostnames := args.hostnames:
        return [machine for machine in hypervisors_machines if machine.hostname in cli_hostnames]

    if cli_azs := args.availability_zones:
        return [machine for machine in hypervisors_machines if machine.az in cli_azs]

    return hypervisors_machines


async def _get_upgradable_hypervisors_machines(
    cli_force: bool, analysis_result: Analysis
) -> list[Machine]:
    """Get the hypervisors that are possible to upgrade.

    :param cli_force: If force is used, it gets all hypervisors, otherwise just the empty ones
    :type cli_force: bool
    :param analysis_result: Analysis result
    :type analysis_result: Analysis
    :return: List of nova-compute units to upgrade
    :rtype: list[Machine]
    """
    nova_compute_units = [
        unit
        for app in analysis_result.apps_data_plane
        for unit in app.units
        if app.charm == "nova-compute"
    ]

    if cli_force:
        return [unit.machine for unit in nova_compute_units]

    return await get_empty_hypervisors(nova_compute_units, analysis_result.model)


def set_upgrade_strategy(args: CLIargs, analysis_result: Analysis):
    nova_compute_machines = _get_upgradable_hypervisors_machines(True, analysis_result)
    for app in analysis_result.data_plane_apps:
        if any(unit.machine in nova_compute_machines for unit in app.units):
            app.upgrade_by_unit = True
        if app.charm == "nova-compute" and args.force:
            app.force_upgrade = args.force


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
