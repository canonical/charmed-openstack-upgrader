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

# NOTE we need to import the modules to register the charms with the register_application
# decorator
# pylint: disable=unused-import
from cou.apps.auxiliary import (  # noqa: F401
    AuxiliaryApplication,
    CephMon,
    CephOsd,
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
from cou.commands import CONTROL_PLANE, DATA_PLANE, HYPERVISORS, CLIargs
from cou.exceptions import (
    DataPlaneCannotUpgrade,
    DataPlaneMachineFilterError,
    HaltUpgradePlanGeneration,
    HighestReleaseAchieved,
    NoTargetError,
    OutOfSupportRange,
)
from cou.steps import PostUpgradeStep, PreUpgradeStep, UpgradePlan
from cou.steps.analyze import Analysis
from cou.steps.backup import backup
from cou.steps.hypervisor import HypervisorUpgradePlanner
from cou.utils.app_utils import set_require_osd_release_option
from cou.utils.juju_utils import DEFAULT_TIMEOUT, COUMachine, COUUnit
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
    verify_data_plane_ready_to_upgrade(args, analysis_result)
    verify_hypervisors_cli_input(args, analysis_result)


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


def verify_data_plane_ready_to_upgrade(args: CLIargs, analysis_result: Analysis) -> None:
    """Verify if data plane is ready to upgrade.

    To be able to upgrade data-plane, first all control plane apps should be upgraded.

    :param args: CLI arguments
    :type args: CLIargs
    :param analysis_result: Analysis result
    :type analysis_result: Analysis
    :raises DataPlaneCannotUpgrade: When data-plane is not ready to upgrade.
    """
    if args.upgrade_group in {DATA_PLANE, HYPERVISORS}:
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


def verify_hypervisors_cli_input(args: CLIargs, analysis_result: Analysis) -> None:
    """Sanity checks from the parameters passed in the cli to upgrade data-plane.

    :param args: CLI arguments
    :type args: CLIargs
    :param analysis_result: Analysis result
    :type analysis_result: Analysis
    """
    if args.machines:
        verify_hypervisors_cli_machines(args.machines, analysis_result)
    elif args.availability_zones:
        verify_hypervisors_cli_azs(args.availability_zones, analysis_result)


def verify_hypervisors_cli_machines(cli_machines: set[str], analysis_result: Analysis) -> None:
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


def verify_hypervisors_cli_azs(cli_azs: set[str], analysis_result: Analysis) -> None:
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
    :param parameter_type: Type of the parameter passed (az or machine).
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
    target = determine_upgrade_target(analysis_result)

    plan = UpgradePlan(
        f"Upgrade cloud from '{analysis_result.current_cloud_os_release}' to '{target}'"
    )
    plan.add_steps(_get_pre_upgrade_steps(analysis_result, args))

    # NOTE (gabrielcocenza) upgrade group as None means that the user wants to upgrade
    #  the whole cloud.
    if args.upgrade_group in {CONTROL_PLANE, None}:
        plan.add_steps(
            _generate_control_plane_plan(target, analysis_result.apps_control_plane, args.force)
        )

    hypervisor_apps, non_hypervisors_apps = _separate_hypervisors_apps(
        analysis_result.apps_data_plane
    )
    if args.upgrade_group in {DATA_PLANE, HYPERVISORS, None}:
        plan.add_step(
            await _generate_data_plane_hypervisors_plan(
                args, analysis_result, target, hypervisor_apps
            )
        )

    if args.upgrade_group in {DATA_PLANE, None}:
        plan.add_steps(
            _generate_data_plane_remaining_plan(target, non_hypervisors_apps, args.force)
        )

    plan.add_steps(_get_post_upgrade_steps(analysis_result, args))

    return plan


def _get_pre_upgrade_steps(analysis_result: Analysis, args: CLIargs) -> list[PreUpgradeStep]:
    """Get the pre-upgrade steps.

    :param analysis_result: Analysis result
    :type analysis_result: Analysis
    :param args: CLI arguments
    :type args: CLIargs
    :return: List of pre-upgrade steps.
    :rtype: list[PreUpgradeStep]
    """
    steps = [
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
    ]
    if args.backup:
        steps.append(
            PreUpgradeStep(
                description="Back up MySQL databases",
                coro=backup(analysis_result.model),
            )
        )

    return steps


def _get_post_upgrade_steps(analysis_result: Analysis, args: CLIargs) -> list[PostUpgradeStep]:
    """Get the post-upgrade steps.

    :param analysis_result: Analysis result
    :type analysis_result: Analysis
    :param args: CLI arguments
    :type args: CLIargs
    :return: List of post-upgrade steps.
    :rtype: list[PreUpgradeStep]
    """
    steps = []
    if args.upgrade_group in {DATA_PLANE, None}:
        steps.extend(_get_ceph_mon_post_upgrade_steps(analysis_result.apps_data_plane))

    return steps


def _get_ceph_mon_post_upgrade_steps(apps: list[OpenStackApplication]) -> list[PostUpgradeStep]:
    """Get the post-upgrade step for ceph-mon, where we check the require-osd-release option.

    :param apps: List of OpenStackApplication.
    :type apps: list[OpenStackApplication]
    :return: List of post-upgrade steps.
    :rtype: list[PreUpgradeStep]
    """
    ceph_mons_apps = [app for app in apps if isinstance(app, CephMon)]

    steps = []
    for app in ceph_mons_apps:
        unit = list(app.units.values())[0]  # getting the first unit, since we don't care which one
        steps.append(
            PostUpgradeStep(
                f"Ensure that the 'require-osd-release' option in '{app.name}' matches the "
                "'ceph-osd' version",
                coro=set_require_osd_release_option(unit.name, app.model),
            )
        )

    return steps


def _generate_control_plane_plan(
    target: OpenStackRelease, apps: list[OpenStackApplication], force: bool
) -> list[UpgradePlan]:
    """Generate upgrade plan for control plane.

    :param target: Target OpenStack release.
    :type target: OpenStackRelease
    :param apps: List of control plane applications.
    :type apps: list[OpenStackApplication]
    :param force: Whether the plan generation should be forced
    :type force: bool
    :return: Principal and Subordinate upgrade plan.
    :rtype: list[UpgradePlan]
    """
    principal_upgrade_plan = create_upgrade_group(
        apps=[app for app in apps if app.is_subordinate is False],
        description="Control Plane principal(s) upgrade plan",
        target=target,
        force=force,
    )

    subordinate_upgrade_plan = create_upgrade_group(
        apps=[app for app in apps if app.is_subordinate],
        description="Control Plane subordinate(s) upgrade plan",
        target=target,
        force=force,
    )

    logger.debug("Generation of the control plane upgrade plan complete")
    return [principal_upgrade_plan, subordinate_upgrade_plan]


def _separate_hypervisors_apps(
    apps_data_plane: list[OpenStackApplication],
) -> tuple[list[OpenStackApplication], list[OpenStackApplication]]:
    """Separate what is considered hypervisors apps from non-hypervisors apps.

    :param apps_data_plane: Applications from data-plane
    :type apps_data_plane: list[OpenStackApplication]
    :raises DataPlaneCannotUpgrade: When an unknown data-plane app is passed.
    :return: Tuple containing two lists of hypervisors and non-hypervisors apps
    :rtype: tuple[list[OpenStackApplication], list[OpenStackApplication]]
    """
    hypervisor_apps = []
    non_hypervisors_apps = []
    _, nova_compute_machines = _get_nova_compute_units_and_machines(apps_data_plane)
    for app in apps_data_plane:
        if app.charm == "ceph-osd" or app.is_subordinate:
            non_hypervisors_apps.append(app)
        elif any(unit.machine in nova_compute_machines for unit in app.units.values()):
            hypervisor_apps.append(app)
        else:
            raise DataPlaneCannotUpgrade(f"COU does not know how to upgrade '{app.name}'")
    return hypervisor_apps, non_hypervisors_apps


async def _generate_data_plane_hypervisors_plan(
    args: CLIargs,
    analysis_result: Analysis,
    target: OpenStackRelease,
    apps: list[OpenStackApplication],
) -> UpgradePlan:
    """Generate upgrade plan for hypervisors.

    :param args: CLI arguments
    :type args: CLIargs
    :param analysis_result: Analysis result
    :type analysis_result: Analysis
    :param target: Target OpenStack release.
    :type target: OpenStackRelease
    :param apps: Hypervisor apps
    :type apps: list[OpenStackApplication]
    :return: Hypervisors upgrade plan.
    :rtype: UpgradePlan
    """
    hypervisors_machines = await filter_hypervisors_machines(args, analysis_result)
    logger.info("Hypervisors selected: %s", hypervisors_machines)
    hypervisor_planner = HypervisorUpgradePlanner(apps, hypervisors_machines)
    hypervisor_plan = hypervisor_planner.generate_upgrade_plan(target, args.force)
    logger.debug("Generation of the hypervisors upgrade plan completed")
    return hypervisor_plan


def _generate_data_plane_remaining_plan(
    target: OpenStackRelease, apps: list[OpenStackApplication], force: bool
) -> list[UpgradePlan]:
    """Generate upgrade plan for principals and subordinates data-plane apps.

    Those plans are done using the all-in-one upgrade strategy.

    :param target:  Target OpenStack release.
    :type target: OpenStackRelease
    :param apps:  List of non-hypervisor apps
    :type apps: list[OpenStackApplication]
    :param force: Whether the plan generation should be forced
    :type force: bool
    :return: list containing the upgrade plan for principals and subordinates
        data-plane apps.
    :rtype: list[UpgradePlan]
    """
    return [
        create_upgrade_group(
            apps=[app for app in apps if app.is_subordinate is False],
            description="Remaining Data Plane principal(s) upgrade plan",
            target=target,
            force=force,
        ),
        create_upgrade_group(
            apps=[app for app in apps if app.is_subordinate],
            description="Data Plane subordinate(s) upgrade plan",
            target=target,
            force=force,
        ),
    ]


async def filter_hypervisors_machines(
    args: CLIargs, analysis_result: Analysis
) -> list[COUMachine]:
    """Filter the hypervisors to generate plan and upgrade.

    :param args: CLI arguments
    :type args: CLIargs
    :param analysis_result: Analysis result
    :type analysis_result: Analysis
    :return: hypervisors filtered to generate plan and upgrade.
    :rtype: list[COUMachine]
    """
    hypervisors_machines = await _get_upgradable_hypervisors_machines(args.force, analysis_result)

    if cli_machines := args.machines:
        return [machine for machine in hypervisors_machines if machine.machine_id in cli_machines]

    if cli_azs := args.availability_zones:
        return [machine for machine in hypervisors_machines if machine.az in cli_azs]

    return hypervisors_machines


async def _get_upgradable_hypervisors_machines(
    cli_force: bool, analysis_result: Analysis
) -> list[COUMachine]:
    """Get the hypervisors that are possible to upgrade.

    :param cli_force: If force is used, it gets all hypervisors, otherwise just the empty ones
    :type cli_force: bool
    :param analysis_result: Analysis result
    :type analysis_result: Analysis
    :return: List of nova-compute units to upgrade
    :rtype: list[COUMachine]
    """
    nova_compute_units, nova_compute_machines = _get_nova_compute_units_and_machines(
        analysis_result.apps_data_plane
    )

    if cli_force:
        return nova_compute_machines

    return await get_empty_hypervisors(nova_compute_units, analysis_result.model)


def _get_nova_compute_units_and_machines(
    apps_data_plane: list[OpenStackApplication],
) -> tuple[list[COUUnit], list[COUMachine]]:
    """Get the nova-compute units and machines.

    :param apps_data_plane: Data-plane apps
    :type apps_data_plane: list[OpenStackApplication]
    :return: A tuple containing a list of nova-compute units and a list of machines
    :rtype: tuple[list[COUUnit], list[COUMachine]]
    """
    nova_compute_units = [
        unit
        for app in apps_data_plane
        for unit in app.units.values()
        if app.charm == "nova-compute"
    ]

    return nova_compute_units, [unit.machine for unit in nova_compute_units]


def create_upgrade_group(
    apps: list[OpenStackApplication],
    target: OpenStackRelease,
    description: str,
    force: bool,
) -> UpgradePlan:
    """Create upgrade group.

    :param apps: Apps to create the group.
    :type apps: list[OpenStackApplication]
    :param target: Target OpenStack release.
    :type target: OpenStackRelease
    :param description: Description of the upgrade plan.
    :type description: str
    :param force: Whether the plan generation should be forced
    :type force: bool
    :raises Exception: When cannot generate upgrade plan.
    :return: Upgrade group.
    :rtype: UpgradePlan
    """
    group_upgrade_plan = UpgradePlan(description)
    for app in apps:
        try:
            app_upgrade_plan = app.generate_upgrade_plan(target, force)
            group_upgrade_plan.add_step(app_upgrade_plan)
        except HaltUpgradePlanGeneration as exc:
            # we do not care if applications halt the upgrade plan generation
            # for some known reason.
            logger.debug("'%s' halted the upgrade planning generation: %s", app.name, exc)
        except Exception as exc:
            logger.error("Cannot generate upgrade plan for '%s': %s", app.name, exc)
            raise

    return group_upgrade_plan
