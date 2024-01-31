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
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from cou.apps.base import OpenStackApplication
from cou.exceptions import (
    DataPlaneCannotUpgrade,
    DataPlaneMachineFilterError,
    HaltUpgradePlanGeneration,
    HighestReleaseAchieved,
    NoTargetError,
    OutOfSupportRange,
)
from cou.steps import (
    ApplicationUpgradePlan,
    PostUpgradeStep,
    PreUpgradeStep,
    UpgradePlan,
    UpgradeStep,
)
from cou.steps import plan as cou_plan
from cou.steps.analyze import Analysis
from cou.steps.backup import backup
from cou.utils import app_utils
from cou.utils.openstack import OpenStackRelease
from tests.unit.apps.utils import add_steps
from tests.unit.conftest import KEYSTONE_MACHINES, NOVA_MACHINES


def generate_expected_upgrade_plan_principal(app, target, model):
    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target.codename}"
    )
    if app.charm in ["rabbitmq-server", "ceph-mon", "keystone"]:
        # apps waiting for whole model
        wait_step = PostUpgradeStep(
            description=f"Wait 1800s for model {model.name} to reach the idle state.",
            parallel=False,
            coro=model.wait_for_active_idle(1800, apps=None),
        )
    else:
        wait_step = PostUpgradeStep(
            description=f"Wait 300s for app {app.name} to reach the idle state.",
            parallel=False,
            coro=model.wait_for_active_idle(300, apps=[app.name]),
        )

    upgrade_steps = [
        PreUpgradeStep(
            description=(
                f"Upgrade software packages of '{app.name}' from the current APT repositories"
            ),
            parallel=False,
            coro=app_utils.upgrade_packages(app.status.units.keys(), model, None),
        ),
        PreUpgradeStep(
            description=(
                f"Refresh '{app.name}' to the latest revision of "
                f"'{target.previous_release}/stable'"
            ),
            parallel=False,
            coro=model.upgrade_charm(app.name, f"{target.previous_release}/stable", switch=None),
        ),
        UpgradeStep(
            description=f"Change charm config of '{app.name}' 'action-managed-upgrade' to False.",
            parallel=False,
            coro=model.set_application_config(app.name, {"action-managed-upgrade": False}),
        ),
        UpgradeStep(
            description=(f"Upgrade '{app.name}' to the new channel: '{target.codename}/stable'"),
            parallel=False,
            coro=model.upgrade_charm(app.name, f"{target.codename}/stable"),
        ),
        UpgradeStep(
            description=(
                f"Change charm config of '{app.name}' "
                f"'{app.origin_setting}' to 'cloud:focal-{target.codename}'"
            ),
            parallel=False,
            coro=model.set_application_config(
                app.name, {f"{app.origin_setting}": f"cloud:focal-{target.codename}"}
            ),
        ),
        wait_step,
        PostUpgradeStep(
            description=f"Check if the workload of '{app.name}' has been upgraded",
            parallel=False,
            coro=app._check_upgrade(target),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)
    return expected_plan


def generate_expected_upgrade_plan_subordinate(app, target, model):
    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}"
    )
    upgrade_steps = [
        PreUpgradeStep(
            description=(
                f"Refresh '{app.name}' to the latest revision of "
                f"'{target.previous_release}/stable'"
            ),
            parallel=False,
            coro=model.upgrade_charm(app.name, f"{target.previous_release}/stable", switch=None),
        ),
        UpgradeStep(
            description=(f"Upgrade '{app.name}' to the new channel: '{target.codename}/stable'"),
            parallel=False,
            coro=model.upgrade_charm(app.name, f"{target.codename}/stable"),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)
    return expected_plan


@pytest.mark.asyncio
async def test_generate_plan(apps, model, cli_args):
    cli_args.is_data_plane_command = False
    target = OpenStackRelease("victoria")
    app_keystone = apps["keystone_focal_ussuri"]
    app_cinder = apps["cinder_focal_ussuri"]
    app_keystone_ldap = apps["keystone_ldap_focal_ussuri"]
    analysis_result = Analysis(
        model=model,
        apps_control_plane=[app_keystone, app_cinder, app_keystone_ldap],
        apps_data_plane=[],
    )

    upgrade_plan = await cou_plan.generate_plan(analysis_result, cli_args)

    expected_plan = UpgradePlan("Upgrade cloud from 'ussuri' to 'victoria'")
    expected_plan.add_step(
        PreUpgradeStep(
            description="Verify that all OpenStack applications are in idle state",
            parallel=False,
            coro=analysis_result.model.wait_for_active_idle(
                timeout=11, idle_period=10, raise_on_blocked=True
            ),
        )
    )
    expected_plan.add_step(
        PreUpgradeStep(
            description="Backup mysql databases",
            parallel=False,
            coro=backup(model),
        )
    )

    control_plane_principals = UpgradePlan("Control Plane principal(s) upgrade plan")
    keystone_plan = generate_expected_upgrade_plan_principal(app_keystone, target, model)
    cinder_plan = generate_expected_upgrade_plan_principal(app_cinder, target, model)
    control_plane_principals.add_step(keystone_plan)
    control_plane_principals.add_step(cinder_plan)

    control_plane_subordinates = UpgradePlan("Control Plane subordinate(s) upgrade plan")
    keystone_ldap_plan = generate_expected_upgrade_plan_subordinate(
        app_keystone_ldap, target, model
    )
    control_plane_subordinates.add_step(keystone_ldap_plan)

    expected_plan.add_step(control_plane_principals)
    expected_plan.add_step(control_plane_subordinates)
    assert upgrade_plan == expected_plan


@pytest.mark.parametrize(
    "is_data_plane_command, expected_call",
    [
        (False, False),
        ("data-plane", True),
    ],
)
@patch("cou.steps.plan.verify_data_plane_cli_input")
@patch("cou.steps.plan.verify_supported_series")
@patch("cou.steps.plan.verify_highest_release_achieved")
@patch("cou.steps.plan.verify_data_plane_ready_to_upgrade")
def test_pre_plan_sanity_checks(
    mock_verify_data_plane_ready_to_upgrade,
    mock_verify_highest_release_achieved,
    mock_verify_supported_series,
    mock_verify_data_plane_cli_input,
    is_data_plane_command,
    expected_call,
    cli_args,
):
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.current_cloud_os_release = OpenStackRelease("ussuri")
    mock_analysis_result.current_cloud_series = "focal"
    cli_args.is_data_plane_command = is_data_plane_command
    cou_plan.pre_plan_sanity_checks(cli_args, mock_analysis_result)
    mock_verify_highest_release_achieved.assert_called_once()
    mock_verify_supported_series.assert_called_once()
    if expected_call:
        mock_verify_data_plane_ready_to_upgrade.assert_called_once_with(mock_analysis_result)
        mock_verify_data_plane_cli_input.assert_called_once_with(cli_args, mock_analysis_result)
    else:
        mock_verify_data_plane_ready_to_upgrade.assert_not_called()
        mock_verify_data_plane_cli_input.assert_not_called()


@pytest.mark.parametrize(
    "current_os_release, current_series, exp_error_msg",
    [
        (
            OpenStackRelease("yoga"),
            "jammy",
            "Cloud series 'jammy' is not a Ubuntu LTS series supported by COU. "
            "The supporting series are: focal",
        ),
        (
            OpenStackRelease("train"),
            "bionic",
            "Cloud series 'bionic' is not a Ubuntu LTS series supported by COU. "
            "The supporting series are: focal",
        ),
    ],
)
def test_verify_supported_series(current_os_release, current_series, exp_error_msg):
    mock_analysis_result = MagicMock(spec=Analysis)()
    with pytest.raises(OutOfSupportRange, match=exp_error_msg):
        mock_analysis_result.current_cloud_os_release = current_os_release
        mock_analysis_result.current_cloud_series = current_series
        cou_plan.verify_supported_series(mock_analysis_result)


def test_verify_highest_release_achieved():
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.current_cloud_os_release = OpenStackRelease("yoga")
    mock_analysis_result.current_cloud_series = "focal"
    exp_error_msg = (
        "No upgrades available for OpenStack Yoga on Ubuntu Focal.\n"
        "Newer OpenStack releases may be available after upgrading to a later Ubuntu series."
    )
    with pytest.raises(HighestReleaseAchieved, match=exp_error_msg):
        cou_plan.verify_highest_release_achieved(mock_analysis_result)


@pytest.mark.parametrize(
    "min_os_version_control_plane, min_os_version_data_plane, exp_error_msg",
    [
        (
            OpenStackRelease("ussuri"),
            OpenStackRelease("ussuri"),
            "Please, upgrade control-plane before data-plane",
        ),
        (
            OpenStackRelease("ussuri"),
            None,
            "Cannot find data-plane apps. Is this a valid OpenStack cloud?",
        ),
    ],
)
def test_verify_data_plane_ready_to_upgrade_error(
    min_os_version_control_plane, min_os_version_data_plane, exp_error_msg, cli_args
):
    cli_args.upgrade_group = "data-plane"
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.current_cloud_series = "focal"
    mock_analysis_result.min_os_version_control_plane = min_os_version_control_plane
    mock_analysis_result.min_os_version_data_plane = min_os_version_data_plane
    with pytest.raises(DataPlaneCannotUpgrade, match=exp_error_msg):
        cou_plan.verify_data_plane_ready_to_upgrade(mock_analysis_result)


@pytest.mark.parametrize(
    "min_os_version_control_plane, min_os_version_data_plane, expected_result",
    [
        (OpenStackRelease("ussuri"), OpenStackRelease("ussuri"), False),
        (OpenStackRelease("ussuri"), OpenStackRelease("victoria"), False),
        (OpenStackRelease("ussuri"), None, False),
        (OpenStackRelease("victoria"), OpenStackRelease("ussuri"), True),
    ],
)
def test_is_control_plane_upgraded(
    min_os_version_control_plane, min_os_version_data_plane, expected_result
):
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.min_os_version_control_plane = min_os_version_control_plane
    mock_analysis_result.min_os_version_data_plane = min_os_version_data_plane
    assert cou_plan.is_control_plane_upgraded(mock_analysis_result) is expected_result


@pytest.mark.parametrize(
    "current_os_release, current_series, next_release",
    [
        (OpenStackRelease("victoria"), "focal", "wallaby"),
        (OpenStackRelease("xena"), "focal", "yoga"),
    ],
)
def test_determine_upgrade_target(current_os_release, current_series, next_release):
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.current_cloud_os_release = current_os_release
    mock_analysis_result.current_cloud_series = current_series

    target = cou_plan.determine_upgrade_target(mock_analysis_result)

    assert target == next_release


@pytest.mark.parametrize(
    "current_os_release, current_series, exp_error_msg",
    [
        (
            None,
            "bionic",
            "Cannot determine the current OS release in the cloud. "
            "Is this a valid OpenStack cloud?",
        ),  # current_os_release is None
        (
            OpenStackRelease("ussuri"),
            None,
            "Cannot determine the current Ubuntu series in the cloud. "
            "Is this a valid OpenStack cloud?",
        ),  # current_series is None
    ],
)
def test_determine_upgrade_target_current_os_and_series(
    current_os_release, current_series, exp_error_msg
):
    with pytest.raises(NoTargetError, match=exp_error_msg):
        mock_analysis_result = MagicMock(spec=Analysis)()
        mock_analysis_result.current_cloud_series = current_series
        mock_analysis_result.current_cloud_os_release = current_os_release
        cou_plan.determine_upgrade_target(mock_analysis_result)


def test_determine_upgrade_target_no_next_release():
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.current_cloud_series = "focal"

    exp_error_msg = "Cannot find target to upgrade. Current minimum OS release is "
    "'ussuri'. Current Ubuntu series is 'focal'."

    with pytest.raises(NoTargetError, match=exp_error_msg), patch(
        "cou.utils.openstack.OpenStackRelease.next_release", new_callable=PropertyMock
    ) as mock_next_release:
        mock_next_release.return_value = None
        current_os_release = OpenStackRelease(
            "ussuri"
        )  # instantiate OpenStackRelease with any valid codename
        mock_analysis_result.current_cloud_os_release = current_os_release
        cou_plan.determine_upgrade_target(mock_analysis_result)


def test_determine_upgrade_target_out_support_range():
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.current_cloud_series = "focal"
    mock_analysis_result.current_cloud_os_release = OpenStackRelease("zed")

    exp_error_msg = (
        "Unable to upgrade cloud from Ubuntu series `focal` to 'antelope'. "
        "Both the from and to releases need to be supported by the current "
        "Ubuntu series 'focal': ussuri, victoria, wallaby, xena, yoga."
    )
    with pytest.raises(OutOfSupportRange, match=exp_error_msg):
        cou_plan.determine_upgrade_target(mock_analysis_result)


@pytest.mark.asyncio
async def test_create_upgrade_plan():
    """Test create_upgrade_group."""
    app: OpenStackApplication = MagicMock(spec_set=OpenStackApplication)
    app.generate_upgrade_plan.return_value = MagicMock(spec_set=ApplicationUpgradePlan)
    target = OpenStackRelease("victoria")
    description = "test"

    plan = await cou_plan.create_upgrade_group([app], target, description, lambda *_: True)

    assert plan.description == description
    assert plan.parallel is False
    assert plan._coro is None
    assert len(plan.sub_steps) == 1
    assert plan.sub_steps[0] == app.generate_upgrade_plan.return_value
    app.generate_upgrade_plan.assert_called_once_with(target)


@pytest.mark.asyncio
async def test_create_upgrade_plan_HaltUpgradePlanGeneration():
    """Test create_upgrade_group."""
    app: OpenStackApplication = MagicMock(spec=OpenStackApplication)
    app.name = "test-app"
    app.generate_upgrade_plan.side_effect = HaltUpgradePlanGeneration
    target = OpenStackRelease("victoria")
    description = "test"

    plan = await cou_plan.create_upgrade_group([app], target, description, lambda *_: True)

    assert len(plan.sub_steps) == 0
    app.generate_upgrade_plan.assert_called_once_with(target)


@pytest.mark.asyncio
async def test_create_upgrade_plan_failed():
    """Test create_upgrade_group."""
    app: OpenStackApplication = MagicMock(spec=OpenStackApplication)
    app.name = "test-app"
    app.generate_upgrade_plan.side_effect = Exception("test")

    with pytest.raises(Exception, match="test"):
        await cou_plan.create_upgrade_group([app], "victoria", "test", lambda *_: True)


@patch("builtins.print")
def test_plan_print_warn_manually_upgrade(mock_print, model, apps):
    result = Analysis(
        model=model,
        apps_control_plane=[apps["keystone_focal_wallaby"]],
        apps_data_plane=[apps["nova_focal_ussuri"]],
    )
    cou_plan.manually_upgrade_data_plane(result)
    mock_print.assert_called_with(
        "WARNING: Please upgrade manually the data plane apps: nova-compute"
    )


@patch("builtins.print")
def test_analysis_not_print_warn_manually_upgrade(mock_print, analysis_result):
    cou_plan.manually_upgrade_data_plane(analysis_result)
    mock_print.assert_not_called()


@patch("cou.steps.plan.verify_data_plane_cli_azs")
@patch("cou.steps.plan.verify_data_plane_cli_hostnames")
@patch("cou.steps.plan.verify_data_plane_cli_machines")
def test_verify_data_plane_cli_no_input(
    mock_verify_machines,
    mock_verify_hostnames,
    mock_verify_azs,
    analysis_result,
    cli_args,
):
    cli_args.machines = None
    cli_args.hostnames = None
    cli_args.availability_zones = None

    assert cou_plan.verify_data_plane_cli_input(cli_args, analysis_result) is None

    mock_verify_machines.assert_not_called()
    mock_verify_hostnames.assert_not_called()
    mock_verify_azs.assert_not_called()


@pytest.mark.parametrize(
    "cli_machines",
    [
        {NOVA_MACHINES[0]},
        {NOVA_MACHINES[1]},
        {NOVA_MACHINES[2]},
        {NOVA_MACHINES[0], NOVA_MACHINES[1], NOVA_MACHINES[2]},
    ],
)
@patch("cou.steps.plan.verify_data_plane_cli_azs")
@patch("cou.steps.plan.verify_data_plane_cli_hostnames")
def test_verify_data_plane_cli_input_machines(
    mock_verify_hostnames,
    mock_verify_azs,
    cli_machines,
    analysis_result,
    cli_args,
):
    cli_args.machines = cli_machines
    cli_args.hostnames = None
    cli_args.availability_zones = None

    assert cou_plan.verify_data_plane_cli_input(cli_args, analysis_result) is None

    mock_verify_hostnames.assert_not_called()
    mock_verify_azs.assert_not_called()


@pytest.mark.parametrize(
    "nova_unit",
    [0, 1, 2],
)
@patch("cou.steps.plan.verify_data_plane_cli_azs")
@patch("cou.steps.plan.verify_data_plane_cli_machines")
def test_verify_data_plane_cli_input_hostnames(
    mock_verify_machines,
    mock_verify_azs,
    nova_unit,
    analysis_result,
    apps,
    cli_args,
):
    nova_machine = list(apps["nova_focal_ussuri"].machines.values())[nova_unit]
    cli_args.machines = None
    cli_args.hostnames = {nova_machine.hostname}
    cli_args.availability_zones = None

    assert cou_plan.verify_data_plane_cli_input(cli_args, analysis_result) is None

    mock_verify_machines.assert_not_called()
    mock_verify_azs.assert_not_called()


@pytest.mark.parametrize(
    "nova_unit",
    [0, 1, 2],
)
@patch("cou.steps.plan.verify_data_plane_cli_hostnames")
@patch("cou.steps.plan.verify_data_plane_cli_machines")
def test_verify_data_plane_cli_input_azs(
    mock_verify_machines,
    mock_verify_hostnames,
    nova_unit,
    analysis_result,
    apps,
    cli_args,
):
    nova_machine = list(apps["nova_focal_ussuri"].machines.values())[nova_unit]
    cli_args.machines = None
    cli_args.hostnames = None
    cli_args.availability_zones = {nova_machine.az}

    assert cou_plan.verify_data_plane_cli_input(cli_args, analysis_result) is None

    mock_verify_machines.assert_not_called()
    mock_verify_hostnames.assert_not_called()


@pytest.mark.parametrize(
    "machine, exp_error_msg",
    [
        ({KEYSTONE_MACHINES[0]}, r"Machine.*are not considered as data-plane."),
        ({"5/lxd/18"}, r"Machine.*don't exist."),
    ],
)
def test_verify_data_plane_cli_machines_raise(analysis_result, machine, exp_error_msg):
    with pytest.raises(DataPlaneMachineFilterError, match=exp_error_msg):
        cou_plan.verify_data_plane_cli_machines(machine, analysis_result)


@pytest.mark.parametrize(
    "app, exp_error_msg",
    [
        ("keystone", r"Hostname.*are not considered as data-plane."),
        ("cinder", r"Hostname.*don't exist."),  # cinder is not on the Analysis
    ],
)
def test_verify_data_plane_cli_hostname_raise(apps, analysis_result, app, exp_error_msg):
    with pytest.raises(DataPlaneMachineFilterError, match=exp_error_msg):
        machine = list(apps[f"{app}_focal_ussuri"].machines.values())[0]
        cou_plan.verify_data_plane_cli_hostnames({machine.hostname}, analysis_result)


@pytest.mark.parametrize(
    "azs, exp_error_msg",
    [
        ({"zone-foo"}, r"Availability Zone.*don't exist."),
        ({"zone-1", "zone-foo"}, r"Availability Zone.*don't exist."),
    ],
)
def test_verify_data_plane_cli_azs_raise_dont_exist(analysis_result, azs, exp_error_msg):
    with pytest.raises(DataPlaneMachineFilterError, match=exp_error_msg):
        cou_plan.verify_data_plane_cli_azs(azs, analysis_result)


def test_verify_data_plane_cli_azs_raise_cannot_find():
    exp_error_msg = r"Cannot find Availability Zone\(s\). Is this a valid OpenStack cloud?"
    mock_analyze = MagicMock()

    mock_machine = MagicMock()
    mock_machine.az = None
    mock_machine.id = "1"
    mock_machine.hostname = "juju-5e8cf8-1"

    mock_analyze.machines = {"1": mock_machine}
    mock_analyze.data_plane_machines = {"1": mock_machine}
    with pytest.raises(DataPlaneMachineFilterError, match=exp_error_msg):
        cou_plan.verify_data_plane_cli_azs({"zone-1"}, mock_analyze)


@pytest.mark.parametrize(
    "force, novas_machines_input, novas_machines_expected",
    [
        (False, [0, 1, 2], [0, 1]),
        (False, [2], []),
        (False, [0, 1], [0, 1]),
        (False, [0], [0]),
        (True, [0, 1, 2], [0, 1, 2]),
        (True, [2], [2]),
        (True, [0], [0]),
    ],
)
@pytest.mark.asyncio
@patch("cou.steps.plan._get_hypervisors_machines_possible_to_upgrade")
async def test_filter_hypervisors_machines_by_machine_id(
    mock_hypervisors_machines,
    apps_machines,
    cli_args,
    analysis_result,
    force,
    novas_machines_input,
    novas_machines_expected,
):

    expected_hypervisors, hypervisors_to_upgrade = _generate_expected_hypervisors_to_test(
        force, novas_machines_expected, apps_machines
    )
    mock_hypervisors_machines.return_value = hypervisors_to_upgrade

    cli_machines = {NOVA_MACHINES[machine_id] for machine_id in novas_machines_input}

    cli_args = _prepare_cli_args(cli_args, cli_machines, None, None, force)

    hypervisors = await cou_plan.filter_hypervisors_machines(cli_args, analysis_result)

    assert hypervisors == expected_hypervisors


@pytest.mark.parametrize(
    "force, novas_machines_input, novas_machines_expected",
    [
        (False, [0, 1, 2], [0, 1]),
        (False, [2], []),
        (False, [0, 1], [0, 1]),
        (False, [0], [0]),
        (True, [0, 1, 2], [0, 1, 2]),
        (True, [2], [2]),
        (True, [0], [0]),
    ],
)
@pytest.mark.asyncio
@patch("cou.steps.plan._get_hypervisors_machines_possible_to_upgrade")
async def test_filter_hypervisors_machines_by_hostname(
    mock_hypervisors_machines,
    force,
    novas_machines_input,
    novas_machines_expected,
    apps_machines,
    cli_args,
    analysis_result,
):
    expected_hypervisors, hypervisors_to_upgrade = _generate_expected_hypervisors_to_test(
        force, novas_machines_expected, apps_machines
    )

    mock_hypervisors_machines.return_value = hypervisors_to_upgrade

    cli_hostnames = {
        apps_machines["nova-compute"][NOVA_MACHINES[machine_id]].hostname
        for machine_id in novas_machines_input
    }

    cli_args = _prepare_cli_args(cli_args, None, cli_hostnames, None, force)

    hypervisors = await cou_plan.filter_hypervisors_machines(cli_args, analysis_result)

    assert hypervisors == expected_hypervisors


@pytest.mark.parametrize(
    "force, novas_machines_input, novas_machines_expected",
    [
        (False, [0, 1, 2], [0, 1]),
        (False, [2], []),
        (False, [0, 1], [0, 1]),
        (False, [0], [0]),
        (True, [0, 1, 2], [0, 1, 2]),
        (True, [2], [2]),
        (True, [0], [0]),
    ],
)
@pytest.mark.asyncio
@patch("cou.steps.plan._get_hypervisors_machines_possible_to_upgrade")
async def test_filter_hypervisors_machines_by_az(
    mock_hypervisors_machines,
    force,
    novas_machines_input,
    novas_machines_expected,
    apps_machines,
    cli_args,
    analysis_result,
):
    expected_hypervisors, hypervisors_to_upgrade = _generate_expected_hypervisors_to_test(
        force, novas_machines_expected, apps_machines
    )
    mock_hypervisors_machines.return_value = hypervisors_to_upgrade

    cli_azs = {
        apps_machines["nova-compute"][NOVA_MACHINES[machine_id]].az
        for machine_id in novas_machines_input
    }

    cli_args = _prepare_cli_args(cli_args, None, None, cli_azs, force)

    hypervisors = await cou_plan.filter_hypervisors_machines(cli_args, analysis_result)

    assert hypervisors == expected_hypervisors


@pytest.mark.parametrize(
    "force, novas_machines_expected",
    [
        (False, [0, 1]),
        (True, [0, 1, 2]),
    ],
)
@pytest.mark.asyncio
@patch("cou.steps.plan._get_hypervisors_machines_possible_to_upgrade")
async def test_filter_hypervisors_machines_no_parameter(
    mock_hypervisors_machines,
    force,
    novas_machines_expected,
    apps_machines,
    cli_args,
    analysis_result,
):
    expected_hypervisors, hypervisors_to_upgrade = _generate_expected_hypervisors_to_test(
        force, novas_machines_expected, apps_machines
    )
    mock_hypervisors_machines.return_value = hypervisors_to_upgrade

    cli_args = _prepare_cli_args(cli_args, None, None, None, force)

    hypervisors = await cou_plan.filter_hypervisors_machines(cli_args, analysis_result)

    assert hypervisors == expected_hypervisors


def _generate_expected_hypervisors_to_test(force, novas_machines_expected, apps_machines):
    """Wrap the generation of the expected hypervisors to upgrade for testing."""
    expected_hypervisors = {
        apps_machines["nova-compute"][NOVA_MACHINES[machine_id]]
        for machine_id in novas_machines_expected
    }

    # assume that machine 2 is running a vm.
    hypervisors_to_upgrade = {
        apps_machines["nova-compute"][NOVA_MACHINES[0]],
        apps_machines["nova-compute"][NOVA_MACHINES[1]],
    }
    if force:
        hypervisors_to_upgrade.add(apps_machines["nova-compute"][NOVA_MACHINES[2]])

    return expected_hypervisors, hypervisors_to_upgrade


def _prepare_cli_args(cli_args, machines, hostnames, az, force):
    """Wrap the preparation of the cli arguments for testing."""
    cli_args.machines = machines
    cli_args.hostnames = hostnames
    cli_args.availability_zones = az
    cli_args.force = force
    return cli_args


@pytest.mark.parametrize(
    "cli_force, empty_hypervisors, expected_result",
    [
        (True, {"nova-compute/0", "nova-compute/1", "nova-compute/2"}, {"0", "1", "2"}),
        (True, {"nova-compute/0", "nova-compute/1"}, {"0", "1", "2"}),
        (True, {"nova-compute/0", "nova-compute/2"}, {"0", "1", "2"}),
        (True, {"nova-compute/1", "nova-compute/2"}, {"0", "1", "2"}),
        (True, {"nova-compute/0"}, {"0", "1", "2"}),
        (True, {"nova-compute/1"}, {"0", "1", "2"}),
        (True, {"nova-compute/2"}, {"0", "1", "2"}),
        (True, set(), {"0", "1", "2"}),
        (False, {"nova-compute/0", "nova-compute/1", "nova-compute/2"}, {"0", "1", "2"}),
        (False, {"nova-compute/0", "nova-compute/1"}, {"0", "1"}),
        (False, {"nova-compute/0", "nova-compute/2"}, {"0", "2"}),
        (False, {"nova-compute/1", "nova-compute/2"}, {"1", "2"}),
        (False, {"nova-compute/0"}, {"0"}),
        (False, {"nova-compute/1"}, {"1"}),
        (False, {"nova-compute/2"}, {"2"}),
        (False, set(), set()),
    ],
)
@pytest.mark.asyncio
@patch("cou.steps.plan._get_empty_hypervisors")
async def test_get_hypervisors_machines_possible_to_upgrade(
    mock_empty_hypervisors,
    cli_force,
    empty_hypervisors,
    expected_result,
    analysis_result,
):
    mock_empty_hypervisors.return_value = empty_hypervisors
    hypervisors_possible_to_upgrade = await cou_plan._get_hypervisors_machines_possible_to_upgrade(
        cli_force, analysis_result
    )

    assert {
        hypervisor.machine_id for hypervisor in hypervisors_possible_to_upgrade
    } == expected_result
