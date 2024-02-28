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
from cou.apps.core import Keystone
from cou.apps.subordinate import OpenStackSubordinateApplication
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
    UnitUpgradeStep,
    UpgradePlan,
    UpgradeStep,
)
from cou.steps import plan as cou_plan
from cou.steps.analyze import Analysis
from cou.steps.backup import backup
from cou.utils import app_utils
from cou.utils.juju_utils import COUMachine, COUUnit
from cou.utils.openstack import OpenStackRelease
from tests.unit.apps.utils import add_steps
from tests.unit.utils import assert_steps


def generate_expected_upgrade_plan_principal(app, target, model):
    """Generate expected upgrade plan for principal charms."""
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

    upgrade_packages = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    for unit in app.units.values():
        upgrade_packages.add_step(
            UnitUpgradeStep(
                description=f"Upgrade software packages on unit {unit.name}",
                coro=app_utils.upgrade_packages(unit.name, model, None),
            )
        )

    upgrade_steps = [
        upgrade_packages,
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
            description=(
                f"Check if the workload of '{app.name}' has been upgraded on units: "
                f"{', '.join([unit for unit in app.units.keys()])}"
            ),
            parallel=False,
            coro=app._verify_workload_upgrade(target, app.units.values()),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)
    return expected_plan


def generate_expected_upgrade_plan_subordinate(app, target, model):
    """Generate expected upgrade plan for subordiante charms."""
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
async def test_generate_plan(model, cli_args):
    """Test generation of upgrade plan."""
    cli_args.is_data_plane_command = False
    cli_args.force = False
    target = OpenStackRelease("victoria")
    # keystone = Keystone()
    machines = {"0": MagicMock(spec_set=COUMachine)}
    keystone = Keystone(
        name="keystone",
        can_upgrade_to="ussuri/stable",
        charm="keystone",
        channel="ussuri/stable",
        config={
            "openstack-origin": {"value": "distro"},
            "action-managed-upgrade": {"value": True},
        },
        machines={},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "keystone/0": COUUnit(
                name="keystone/0",
                workload_version="17.0.1",
                machine=machines["0"],
            )
        },
        workload_version="17.0.1",
    )
    keystone_ldap = OpenStackSubordinateApplication(
        name="keystone-ldap",
        can_upgrade_to="ussuri/stable",
        charm="keystone-ldap",
        channel="ussuri/stable",
        config={},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=["nova-compute"],
        units={
            "keystone-ldap/0": COUUnit(
                name="keystone-ldap/0",
                workload_version="17.0.1",
                machine=machines["0"],
            )
        },
        workload_version="17.0.1",
    )
    cinder = OpenStackApplication(
        name="cinder",
        can_upgrade_to="ussuri/stable",
        charm="cinder",
        channel="ussuri/stable",
        config={
            "openstack-origin": {"value": "distro"},
            "action-managed-upgrade": {"value": True},
        },
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "cinder/0": COUUnit(
                name="cinder/0",
                workload_version="16.4.2",
                machine=machines["0"],
            )
        },
        workload_version="16.4.2",
    )

    analysis_result = Analysis(
        model=model,
        apps_control_plane=[keystone, cinder, keystone_ldap],
        apps_data_plane=[],
    )

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
    keystone_plan = generate_expected_upgrade_plan_principal(keystone, target, model)
    cinder_plan = generate_expected_upgrade_plan_principal(cinder, target, model)
    control_plane_principals.add_step(keystone_plan)
    control_plane_principals.add_step(cinder_plan)

    control_plane_subordinates = UpgradePlan("Control Plane subordinate(s) upgrade plan")
    keystone_ldap_plan = generate_expected_upgrade_plan_subordinate(keystone_ldap, target, model)
    control_plane_subordinates.add_step(keystone_ldap_plan)

    expected_plan.add_step(control_plane_principals)
    expected_plan.add_step(control_plane_subordinates)

    upgrade_plan = await cou_plan.generate_plan(analysis_result, cli_args)
    assert_steps(upgrade_plan, expected_plan)


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


@pytest.mark.parametrize("force", [True, False])
def test_create_upgrade_plan(force):
    """Test create_upgrade_group."""
    app: OpenStackApplication = MagicMock(spec_set=OpenStackApplication)
    app.generate_upgrade_plan.return_value = MagicMock(spec_set=ApplicationUpgradePlan)
    target = OpenStackRelease("victoria")
    description = "test"

    plan = cou_plan.create_upgrade_group([app], target, description, force, lambda *_: True)

    assert plan.description == description
    assert plan.parallel is False
    assert plan._coro is None
    assert len(plan.sub_steps) == 1
    assert plan.sub_steps[0] == app.generate_upgrade_plan.return_value
    app.generate_upgrade_plan.assert_called_once_with(target, force)


@pytest.mark.parametrize("force", [True, False])
def test_create_upgrade_plan_HaltUpgradePlanGeneration(force):
    """Test create_upgrade_group."""
    app: OpenStackApplication = MagicMock(spec=OpenStackApplication)
    app.name = "test-app"
    app.generate_upgrade_plan.side_effect = HaltUpgradePlanGeneration
    target = OpenStackRelease("victoria")
    description = "test"

    plan = cou_plan.create_upgrade_group([app], target, description, force, lambda *_: True)

    assert len(plan.sub_steps) == 0
    app.generate_upgrade_plan.assert_called_once_with(target, force)


@pytest.mark.parametrize("force", [True, False])
def test_create_upgrade_plan_failed(force):
    """Test create_upgrade_group."""
    app: OpenStackApplication = MagicMock(spec=OpenStackApplication)
    app.name = "test-app"
    app.generate_upgrade_plan.side_effect = Exception("test")

    with pytest.raises(Exception, match="test"):
        cou_plan.create_upgrade_group([app], "victoria", "test", force, lambda *_: True)


@patch("cou.steps.plan.verify_data_plane_cli_azs")
@patch("cou.steps.plan.verify_data_plane_cli_machines")
def test_verify_data_plane_cli_no_input(
    mock_verify_machines,
    mock_verify_azs,
    cli_args,
):
    cli_args.machines = None
    cli_args.availability_zones = None

    assert cou_plan.verify_data_plane_cli_input(cli_args, MagicMock(spec_set=Analysis)()) is None

    mock_verify_machines.assert_not_called()
    mock_verify_azs.assert_not_called()


@pytest.mark.parametrize(
    "cli_machines",
    [
        {"0"},
        {"1"},
        {"2"},
        {"0", "1", "2"},
    ],
)
@patch("cou.steps.plan.verify_data_plane_cli_azs")
def test_verify_data_plane_cli_input_machines(mock_verify_azs, cli_machines, cli_args):
    cli_args.machines = cli_machines
    cli_args.availability_zones = None
    analysis_result = MagicMock(spec_set=Analysis)()
    analysis_result.data_plane_machines = analysis_result.machines = {
        f"{i}": MagicMock(spec_set=COUMachine)() for i in range(3)
    }

    assert cou_plan.verify_data_plane_cli_input(cli_args, analysis_result) is None

    mock_verify_azs.assert_not_called()


@patch("cou.steps.plan.verify_data_plane_cli_machines")
def test_verify_data_plane_cli_input_azs(mock_verify_machines, cli_args):
    az = "test-az-0"
    machine = MagicMock(spec_set=COUMachine)()
    machine.az = az
    analysis_result = MagicMock(spec_set=Analysis)()
    analysis_result.data_plane_machines = analysis_result.machines = {"0": machine}
    cli_args.machines = None
    cli_args.availability_zones = {az}

    assert cou_plan.verify_data_plane_cli_input(cli_args, analysis_result) is None

    mock_verify_machines.assert_not_called()


@pytest.mark.parametrize(
    "cli_machines, exp_error_msg",
    [
        ({"1"}, r"Machine.*are not considered as data-plane."),
        ({"5/lxd/18"}, r"Machine.*don't exist."),
    ],
)
def test_verify_data_plane_cli_machines_raise(cli_machines, exp_error_msg):
    machine0 = MagicMock(spec_set=COUMachine)()
    machine1 = MagicMock(spec_set=COUMachine)()
    analysis_result = MagicMock(spec_set=Analysis)()
    analysis_result.machines = {"0": machine0, "1": machine1}
    analysis_result.data_plane_machines = {"0": machine0}
    analysis_result.control_plane_machines = {"1": machine1}

    with pytest.raises(DataPlaneMachineFilterError, match=exp_error_msg):
        cou_plan.verify_data_plane_cli_machines(cli_machines, analysis_result)


@pytest.mark.parametrize(
    "cli_azs, exp_error_msg",
    [
        ({"zone-1"}, r"Availability Zone.* are not considered as data-plane."),
        ({"zone-test", "zone-foo"}, r"Availability Zone.*don't exist."),
    ],
)
def test_verify_data_plane_cli_azs_raise_dont_exist(cli_azs, exp_error_msg):
    machine0 = MagicMock(spec_set=COUMachine)()
    machine0.az = "zone-0"
    machine1 = MagicMock(spec_set=COUMachine)()
    machine1.az = "zone-1"
    analysis_result = MagicMock(spec_set=Analysis)()
    analysis_result.machines = {"0": machine0, "1": machine1}
    analysis_result.data_plane_machines = {"0": machine0}
    analysis_result.control_plane_machines = {"1": machine1}

    with pytest.raises(DataPlaneMachineFilterError, match=exp_error_msg):
        cou_plan.verify_data_plane_cli_azs(cli_azs, analysis_result)


def test_verify_data_plane_cli_azs_raise_cannot_find():
    exp_error_msg = r"Cannot find Availability Zone\(s\). Is this a valid OpenStack cloud?"
    mock_analyze = MagicMock()

    mock_machine = MagicMock()
    mock_machine.az = None
    mock_machine.id = "1"

    mock_analyze.machines = {"1": mock_machine}
    mock_analyze.data_plane_machines = {"1": mock_machine}
    with pytest.raises(DataPlaneMachineFilterError, match=exp_error_msg):
        cou_plan.verify_data_plane_cli_azs({"zone-1"}, mock_analyze)


@pytest.mark.parametrize(
    "force, cli_machines, cli_azs, expected_machines",
    [
        # machines input
        (False, {"0", "1", "2"}, None, {"0", "1"}),
        (False, {"2"}, None, set()),
        (False, {"0", "1"}, None, {"0", "1"}),
        (False, {"0"}, None, {"0"}),
        (True, {"0", "1", "2"}, None, {"0", "1", "2"}),
        (True, {"2"}, None, {"2"}),
        (True, {"0"}, None, {"0"}),
        # az input
        (False, None, {"zone-1", "zone-2", "zone-3"}, {"0", "1"}),
        (False, None, {"zone-3"}, set()),
        (False, None, {"zone-1", "zone-2"}, {"0", "1"}),
        (False, None, {"zone-1"}, {"0"}),
        (True, None, {"zone-1", "zone-2", "zone-3"}, {"0", "1", "2"}),
        (True, None, {"zone-3"}, {"2"}),
        (True, None, {"zone-1"}, {"0"}),
        # no input
        (False, None, None, {"0", "1"}),
        (True, None, None, {"0", "1", "2"}),
    ],
)
@pytest.mark.asyncio
@patch("cou.steps.plan._get_upgradable_hypervisors_machines")
async def test_filter_hypervisors_machines(
    mock_hypervisors_machines,
    force,
    cli_machines,
    cli_azs,
    expected_machines,
    cli_args,
):

    empty_hypervisors_machines = {
        COUMachine(str(machine_id), (), f"zone-{machine_id + 1}") for machine_id in range(2)
    }
    # assuming that machine-2 has some VMs running
    non_empty_hypervisor_machine = COUMachine("2", (), "zone-3")

    upgradable_hypervisors = empty_hypervisors_machines
    if force:
        upgradable_hypervisors.add(non_empty_hypervisor_machine)

    mock_hypervisors_machines.return_value = upgradable_hypervisors

    cli_args.machines = cli_machines
    cli_args.availability_zones = cli_azs
    cli_args.force = force

    machines = await cou_plan.filter_hypervisors_machines(cli_args, MagicMock())

    assert {machine.machine_id for machine in machines} == expected_machines


@pytest.mark.parametrize(
    "cli_force, empty_hypervisors, expected_result",
    [
        (True, {0, 1, 2}, {"0", "1", "2"}),
        (True, {0, 1}, {"0", "1", "2"}),
        (True, {0, 2}, {"0", "1", "2"}),
        (True, {1, 2}, {"0", "1", "2"}),
        (True, {0}, {"0", "1", "2"}),
        (True, {1}, {"0", "1", "2"}),
        (True, {2}, {"0", "1", "2"}),
        (True, set(), {"0", "1", "2"}),
        (False, {0, 1, 2}, {"0", "1", "2"}),
        (False, {0, 1}, {"0", "1"}),
        (False, {0, 2}, {"0", "2"}),
        (False, {1, 2}, {"1", "2"}),
        (False, {0}, {"0"}),
        (False, {1}, {"1"}),
        (False, {2}, {"2"}),
        (False, set(), set()),
    ],
)
@pytest.mark.asyncio
@patch("cou.steps.plan.get_empty_hypervisors")
async def test_get_upgradable_hypervisors_machines(
    mock_empty_hypervisors, cli_force, empty_hypervisors, expected_result
):
    machines = {f"{i}": COUMachine(f"{i}", (), f"zone-{i + 1}") for i in range(3)}
    nova_compute = MagicMock(spec_set=OpenStackApplication)()
    nova_compute.charm = "nova-compute"
    nova_compute.units = {
        f"nova-compute/{i}": COUUnit(
            name=f"nova-compute/{i}",
            workload_version="21.0.0",
            machine=machines[f"{i}"],
        )
        for i in range(3)
    }
    analysis_result = MagicMock(spec_set=Analysis)()
    analysis_result.data_plane_machines = analysis_result.machines = machines
    analysis_result.apps_data_plane = [nova_compute]
    mock_empty_hypervisors.return_value = {
        machines[f"{machine_id}"] for machine_id in empty_hypervisors
    }
    hypervisors_possible_to_upgrade = await cou_plan._get_upgradable_hypervisors_machines(
        cli_force, analysis_result
    )

    if not cli_force:
        mock_empty_hypervisors.assert_called_once_with(
            [unit for unit in nova_compute.units.values()], analysis_result.model
        )
    else:
        mock_empty_hypervisors.assert_not_called()

    assert {
        hypervisor.machine_id for hypervisor in hypervisors_possible_to_upgrade
    } == expected_result


@pytest.mark.parametrize("backup", [True, False])
def test_generate_common_plan(backup, cli_args):
    target = OpenStackRelease("victoria")
    nova_compute = MagicMock(spec_set=OpenStackApplication)()

    # analysis_result.model.wait_for_active_idle() should have __name__
    # to not raise an error.
    class AnalysisResult(MagicMock):
        __name__ = "wait_for_active_idle"

    mock_analysis_result = AnalysisResult(spec=Analysis)()
    mock_analysis_result.apps_control_plane = [nova_compute]

    cli_args.backup = backup

    plan = cou_plan.generate_common_plan(mock_analysis_result, cli_args, target)

    if backup:
        assert len(plan.sub_steps) == 2
        assert plan.sub_steps[1].description == "Backup mysql databases"
    else:
        assert len(plan.sub_steps) == 1
        assert plan.sub_steps[0].description != "Backup mysql databases"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "is_control_plane_command, is_generic_command", [(True, False), (False, False), (False, True)]
)
@patch("cou.steps.plan.create_upgrade_group")
async def test_generate_control_plane_plan(
    mock_create_upgrade_group, is_control_plane_command, is_generic_command, cli_args
):
    target = OpenStackRelease("victoria")
    nova_compute = MagicMock(spec_set=OpenStackApplication)()
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.apps_control_plane = [nova_compute]

    cli_args.is_control_plane_command = is_control_plane_command
    cli_args.is_generic_command = is_generic_command

    await cou_plan.generate_control_plane_plan(mock_analysis_result, cli_args, target)

    if is_control_plane_command or is_generic_command:
        assert mock_create_upgrade_group.await_count == 2
    else:
        mock_create_upgrade_group.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "is_data_plane_command, is_generic_command", [(True, False), (False, False), (False, True)]
)
@patch("cou.steps.plan.filter_hypervisors_machines")
async def test_generate_data_plane_plan(
    mock_filtered_hypervisors, is_data_plane_command, is_generic_command, cli_args
):
    mock_analysis_result = MagicMock(spec=Analysis)()
    cli_args.is_data_plane_command = is_data_plane_command
    cli_args.is_generic_command = is_generic_command

    await cou_plan.generate_data_plane_plan(mock_analysis_result, cli_args)

    if is_data_plane_command or is_generic_command:
        mock_filtered_hypervisors.assert_awaited_with(cli_args, mock_analysis_result)
    else:
        mock_filtered_hypervisors.assert_not_awaited()
