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
from unittest.mock import AsyncMock, MagicMock, PropertyMock, call, patch

import pytest

from cou.apps.auxiliary import CephOsd
from cou.apps.auxiliary_subordinate import OVNSubordinate
from cou.apps.base import OpenStackApplication
from cou.apps.core import Keystone, NovaCompute
from cou.apps.subordinate import SubordinateApplication
from cou.commands import CONTROL_PLANE, DATA_PLANE, HYPERVISORS, CLIargs
from cou.exceptions import (
    ApplicationError,
    ApplicationNotFound,
    COUException,
    DataPlaneMachineFilterError,
    HaltUpgradePlanGeneration,
    MismatchedOpenStackVersions,
    NoTargetError,
    OutOfSupportRange,
    VaultSealed,
)
from cou.steps import (
    ApplicationUpgradePlan,
    PostUpgradeStep,
    PreUpgradeStep,
    UnitUpgradeStep,
    UpgradePlan,
    UpgradeStep,
    ceph,
)
from cou.steps import plan as cou_plan
from cou.steps.analyze import Analysis
from cou.steps.backup import backup
from cou.steps.ceph import set_require_osd_release_option
from cou.steps.hypervisor import HypervisorGroup, HypervisorUpgradePlanner
from cou.steps.nova_cloud_controller import archive, purge
from cou.utils import app_utils
from cou.utils.juju_utils import Machine, Unit
from cou.utils.openstack import OpenStackRelease
from tests.unit.utils import dedent_plan, generate_cou_machine, get_applications


def generate_expected_upgrade_plan_principal(app, target, model):
    """Generate expected upgrade plan for principal charms."""
    expected_plan = ApplicationUpgradePlan(f"Upgrade plan for '{app.name}' to '{target.codename}'")
    if app.charm in ["rabbitmq-server", "ceph-mon", "keystone"]:
        # apps waiting for whole model
        wait_step = PostUpgradeStep(
            description=f"Wait for up to 2400s for model '{model.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_idle(2400, apps=None),
        )
    else:
        wait_step = PostUpgradeStep(
            description=f"Wait for up to 300s for app '{app.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_idle(300, apps=[app.name]),
        )

    upgrade_packages = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    upgrade_packages.add_steps(
        UnitUpgradeStep(
            description=f"Upgrade software packages on unit '{unit.name}'",
            coro=app_utils.upgrade_packages(unit.name, model, None),
        )
        for unit in app.units.values()
    )

    upgrade_steps = [
        upgrade_packages,
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of "
            f"'{target.previous_release.track}/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, f"{target.previous_release.track}/stable"),
        ),
        UpgradeStep(
            description=f"Change charm config of '{app.name}' 'action-managed-upgrade' to 'False'",
            parallel=False,
            coro=model.set_application_config(app.name, {"action-managed-upgrade": False}),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' from '{target.previous_release.track}/stable' "
            f"to the new channel: '{target.track}/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, f"{target.track}/stable"),
        ),
        UpgradeStep(
            description=f"Change charm config of '{app.name}' "
            f"'{app.origin_setting}' to 'cloud:focal-{target.track}'",
            parallel=False,
            coro=model.set_application_config(
                app.name, {f"{app.origin_setting}": f"cloud:focal-{target.track}"}
            ),
        ),
        wait_step,
        PostUpgradeStep(
            description=f"Verify that the workload of '{app.name}' has been upgraded on units: "
            f"{', '.join([unit for unit in app.units.keys()])}",
            parallel=False,
            coro=app._verify_workload_upgrade(target, list(app.units.values())),
        ),
    ]
    expected_plan.add_steps(upgrade_steps)
    return expected_plan


def generate_expected_upgrade_plan_subordinate(app, target, model):
    """Generate expected upgrade plan for subordiante charms."""
    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to '{target}'"
    )
    upgrade_steps = [
        PreUpgradeStep(
            (
                f"Refresh '{app.name}' to the latest revision of "
                f"'{target.previous_release.track}/stable'"
            ),
            parallel=False,
            coro=model.upgrade_charm(app.name, f"{target.previous_release.track}/stable"),
        ),
        UpgradeStep(
            (
                f"Upgrade '{app.name}' from "
                f"'{target.previous_release.track}/stable' to the new channel: "
                f"'{target.track}/stable'"
            ),
            parallel=False,
            coro=model.upgrade_charm(app.name, f"{target.track}/stable"),
        ),
    ]
    expected_plan.add_steps(upgrade_steps)
    return expected_plan


@pytest.mark.asyncio
@patch("cou.steps.plan._filter_hypervisors_machines")
async def test_generate_plan(mock_filter_hypervisors, model, cli_args):
    """Test generation of upgrade plan."""
    exp_plan = dedent_plan(
        """\
    Upgrade cloud from 'ussuri' to 'victoria'
        Back up MySQL databases
        Archive old database data on nova-cloud-controller
        Subordinate(s) upgrade plan
            Upgrade plan for 'keystone-ldap' to 'victoria'
                Refresh 'keystone-ldap' to the latest revision of 'ussuri/stable'
                Wait for up to 300s for app 'keystone-ldap' to reach the idle state
                Upgrade 'keystone-ldap' from 'ussuri/stable' to the new channel: 'victoria/stable'
                Wait for up to 300s for app 'keystone-ldap' to reach the idle state
            Upgrade plan for 'ovn-chassis' to 'victoria'
                Refresh 'ovn-chassis' to the latest revision of '22.03/stable'
                Wait for up to 300s for app 'ovn-chassis' to reach the idle state
        Control Plane principal(s) upgrade plan
            Upgrade plan for 'keystone' to 'victoria'
                Upgrade software packages of 'keystone' from the current APT repositories
                    Ψ Upgrade software packages on unit 'keystone/0'
                Refresh 'keystone' to the latest revision of 'ussuri/stable'
                Wait for up to 1200s for app 'keystone' to reach the idle state
                Change charm config of 'keystone' 'action-managed-upgrade' from 'True' to 'False'
                Upgrade 'keystone' from 'ussuri/stable' to the new channel: 'victoria/stable'
                Wait for up to 1200s for app 'keystone' to reach the idle state
                Change charm config of 'keystone' 'openstack-origin' to 'cloud:focal-victoria'
                Wait for up to 2400s for model 'test_model' to reach the idle state
                Verify that the workload of 'keystone' has been upgraded on units: keystone/0
        Upgrading all applications deployed on machines with hypervisor.
            Upgrade plan for [nova-compute/0] in 'az-1' to 'victoria'
                Disable nova-compute scheduler from unit: 'nova-compute/0'
                Upgrade software packages of 'nova-compute' from the current APT repositories
                    Ψ Upgrade software packages on unit 'nova-compute/0'
                Refresh 'nova-compute' to the latest revision of 'ussuri/stable'
                Wait for up to 300s for app 'nova-compute' to reach the idle state
                Change charm config of 'nova-compute' 'action-managed-upgrade' from 'False' to 'True'
                Upgrade 'nova-compute' from 'ussuri/stable' to the new channel: 'victoria/stable'
                Wait for up to 300s for app 'nova-compute' to reach the idle state
                Change charm config of 'nova-compute' 'source' to 'cloud:focal-victoria'
                Upgrade plan for units: nova-compute/0
                    Ψ Upgrade plan for unit 'nova-compute/0'
                        Verify that unit 'nova-compute/0' has no VMs running
                        ├── Pause the unit: 'nova-compute/0'
                        ├── Upgrade the unit: 'nova-compute/0'
                        ├── Resume the unit: 'nova-compute/0'
                Enable nova-compute scheduler from unit: 'nova-compute/0'
                Wait for up to 2400s for model 'test_model' to reach the idle state
                Verify that the workload of 'nova-compute' has been upgraded on units: \
nova-compute/0
        Remaining Data Plane principal(s) upgrade plan
            Upgrade plan for 'ceph-osd' to 'victoria'
                Verify that all 'nova-compute' units has been upgraded
                Upgrade software packages of 'ceph-osd' from the current APT repositories
                    Ψ Upgrade software packages on unit 'ceph-osd/0'
                Refresh 'ceph-osd' to the latest revision of 'octopus/stable'
                Wait for up to 300s for app 'ceph-osd' to reach the idle state
                Change charm config of 'ceph-osd' 'source' to 'cloud:focal-victoria'
                Wait for up to 300s for app 'ceph-osd' to reach the idle state
                Verify that the workload of 'ceph-osd' has been upgraded on units: ceph-osd/0
        Ensure ceph-mon's 'require-osd-release' option matches the 'ceph-osd' version
    """  # noqa: E501 line too long
    )
    cli_args.upgrade_group = None
    cli_args.force = False
    cli_args.set_noout = False

    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
    mock_filter_hypervisors.return_value = [machines["1"]]
    keystone = Keystone(
        name="keystone",
        can_upgrade_to="ussuri/stable",
        charm="keystone",
        channel="ussuri/stable",
        config={
            "openstack-origin": {"value": "distro"},
            "action-managed-upgrade": {"value": True},
        },
        machines={"0": machines["0"]},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "keystone/0": Unit(
                name="keystone/0",
                workload_version="17.0.1",
                machine=machines["0"],
            )
        },
        workload_version="17.0.1",
    )
    keystone_ldap = SubordinateApplication(
        name="keystone-ldap",
        can_upgrade_to="ussuri/stable",
        charm="keystone-ldap",
        channel="ussuri/stable",
        config={},
        machines={"0": machines["0"]},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=["keystone"],
        units={},
        workload_version="17.0.1",
    )

    nova_compute = NovaCompute(
        name="nova-compute",
        can_upgrade_to="ussuri/stable",
        charm="nova-compute",
        channel="ussuri/stable",
        config={"source": {"value": "distro"}, "action-managed-upgrade": {"value": False}},
        machines={"1": machines["1"]},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "nova-compute/0": Unit(
                name="nova-compute/0",
                workload_version="21.0.0",
                machine=machines["1"],
            )
        },
        workload_version="21.0.0",
    )

    ceph_osd = CephOsd(
        name="ceph-osd",
        can_upgrade_to="octopus/stable",
        charm="ceph-osd",
        channel="octopus/stable",
        config={"source": {"value": "distro"}},
        machines={"2": machines["2"]},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "ceph-osd/0": Unit(
                name="ceph-osd/0",
                workload_version="15.2.0",
                machine=machines["2"],
            )
        },
        workload_version="15.2.0",
    )

    ovn_chassis = OVNSubordinate(
        name="ovn-chassis",
        can_upgrade_to="22.03/stable",
        charm="ovn-chassis",
        channel="22.03/stable",
        config={"enable-version-pinning": {"value": False}},
        machines={"1": machines["1"]},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=["nova-compute"],
        units={},
        workload_version="22.3",
    )

    analysis_result = Analysis(
        model=model,
        apps=[keystone, keystone_ldap, ceph_osd, nova_compute, ovn_chassis],
    )

    upgrade_plan = await cou_plan.generate_plan(analysis_result, cli_args)
    assert str(upgrade_plan) == exp_plan


@pytest.mark.asyncio
@patch("cou.steps.plan._filter_hypervisors_machines")
async def test_generate_plan_with_warning_messages(mock_filter_hypervisors, model, cli_args):
    """Test generation of upgrade plan with error messages."""
    exp_plan = dedent_plan(
        """\
    Upgrade cloud from 'ussuri' to 'victoria'
        Back up MySQL databases
        Archive old database data on nova-cloud-controller
        Subordinate(s) upgrade plan
            Upgrade plan for 'keystone-ldap' to 'victoria'
                Refresh 'keystone-ldap' to the latest revision of 'ussuri/stable'
                Wait for up to 300s for app 'keystone-ldap' to reach the idle state
                Upgrade 'keystone-ldap' from 'ussuri/stable' to the new channel: 'victoria/stable'
                Wait for up to 300s for app 'keystone-ldap' to reach the idle state
            Upgrade plan for 'ovn-chassis' to 'victoria'
                Refresh 'ovn-chassis' to the latest revision of '22.03/stable'
                Wait for up to 300s for app 'ovn-chassis' to reach the idle state
        Upgrading all applications deployed on machines with hypervisor.
            Upgrade plan for [nova-compute/0] in 'az-1' to 'victoria'
                Disable nova-compute scheduler from unit: 'nova-compute/0'
                Upgrade software packages of 'nova-compute' from the current APT repositories
                    Ψ Upgrade software packages on unit 'nova-compute/0'
                Refresh 'nova-compute' to the latest revision of 'ussuri/stable'
                Wait for up to 300s for app 'nova-compute' to reach the idle state
                Change charm config of 'nova-compute' 'action-managed-upgrade' from 'False' to 'True'
                Upgrade 'nova-compute' from 'ussuri/stable' to the new channel: 'victoria/stable'
                Wait for up to 300s for app 'nova-compute' to reach the idle state
                Change charm config of 'nova-compute' 'source' to 'cloud:focal-victoria'
                Upgrade plan for units: nova-compute/0
                    Ψ Upgrade plan for unit 'nova-compute/0'
                        Verify that unit 'nova-compute/0' has no VMs running
                        ├── Pause the unit: 'nova-compute/0'
                        ├── Upgrade the unit: 'nova-compute/0'
                        ├── Resume the unit: 'nova-compute/0'
                Enable nova-compute scheduler from unit: 'nova-compute/0'
                Wait for up to 2400s for model 'test_model' to reach the idle state
                Verify that the workload of 'nova-compute' has been upgraded on units: \
nova-compute/0
        Remaining Data Plane principal(s) upgrade plan
            Upgrade plan for 'ceph-osd' to 'victoria'
                Verify that all 'nova-compute' units has been upgraded
                Upgrade software packages of 'ceph-osd' from the current APT repositories
                    Ψ Upgrade software packages on unit 'ceph-osd/0'
                Refresh 'ceph-osd' to the latest revision of 'octopus/stable'
                Wait for up to 300s for app 'ceph-osd' to reach the idle state
                Change charm config of 'ceph-osd' 'source' to 'cloud:focal-victoria'
                Wait for up to 300s for app 'ceph-osd' to reach the idle state
                Verify that the workload of 'ceph-osd' has been upgraded on units: ceph-osd/0
        Ensure ceph-mon's 'require-osd-release' option matches the 'ceph-osd' version
    """  # noqa: E501 line too long
    )
    cli_args.upgrade_group = None
    cli_args.force = False
    cli_args.set_noout = False

    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
    mock_filter_hypervisors.return_value = [machines["1"]]
    keystone = Keystone(
        name="keystone",
        can_upgrade_to="ussuri/stable",
        charm="keystone",
        channel="ussuri/stable",
        config={
            "openstack-origin": {"value": "distro"},
            "action-managed-upgrade": {"value": True},
        },
        machines={"0": machines["0"]},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "keystone/0": Unit(
                name="keystone/0",
                workload_version="17.0.1",
                machine=machines["0"],
            ),
            "keystone/1": Unit(
                name="keystone/1",
                workload_version="18.0.1",  # mismatched unit versions
                machine=machines["0"],
            ),
        },
        workload_version="17.0.1",
    )
    keystone_ldap = SubordinateApplication(
        name="keystone-ldap",
        can_upgrade_to="ussuri/stable",
        charm="keystone-ldap",
        channel="ussuri/stable",
        config={},
        machines={"0": machines["0"]},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=["keystone"],
        units={},
        workload_version="17.0.1",
    )

    nova_compute = NovaCompute(
        name="nova-compute",
        can_upgrade_to="ussuri/stable",
        charm="nova-compute",
        channel="ussuri/stable",
        config={"source": {"value": "distro"}, "action-managed-upgrade": {"value": False}},
        machines={"1": machines["1"]},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "nova-compute/0": Unit(
                name="nova-compute/0",
                workload_version="21.0.0",
                machine=machines["1"],
            )
        },
        workload_version="21.0.0",
    )

    ceph_osd = CephOsd(
        name="ceph-osd",
        can_upgrade_to="octopus/stable",
        charm="ceph-osd",
        channel="octopus/stable",
        config={"source": {"value": "distro"}},
        machines={"2": machines["2"]},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "ceph-osd/0": Unit(
                name="ceph-osd/0",
                workload_version="17.0.1",
                machine=machines["2"],
            )
        },
        workload_version="17.0.1",
    )

    ovn_chassis = OVNSubordinate(
        name="ovn-chassis",
        can_upgrade_to="22.03/stable",
        charm="ovn-chassis",
        channel="22.03/stable",
        config={"enable-version-pinning": {"value": False}},
        machines={"1": machines["1"]},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=["nova-compute"],
        units={},
        workload_version="22.3",
    )

    analysis_result = Analysis(
        model=model,
        apps=[keystone, keystone_ldap, ceph_osd, nova_compute, ovn_chassis],
    )

    upgrade_plan = await cou_plan.generate_plan(analysis_result, cli_args)
    assert str(upgrade_plan) == exp_plan
    assert len(cou_plan.PlanStatus.error_messages) == 1  # set_noout error
    assert len(cou_plan.PlanStatus.warning_messages) == 1  # keystone mismatch warning


def test_planstatus_warnings_property():
    """Test PlanStatus object."""
    exp_warnings = ["Mock warning message1", "Mock warning message2"]

    for warning in exp_warnings:
        cou_plan.PlanStatus.add_message(warning, message_type=cou_plan.MessageType.WARNING)

    # Check only the last two entries because this is a singleton class which is
    # also being tested in other functions
    assert cou_plan.PlanStatus.warning_messages[-2:] == exp_warnings


@pytest.mark.asyncio
@patch("cou.steps.plan._verify_model_idle")
@patch("cou.steps.plan._verify_osd_noout_unset")
@patch("cou.steps.plan._verify_vault_is_unsealed")
@patch("cou.steps.plan._verify_hypervisors_cli_input")
@patch("cou.steps.plan._verify_supported_series")
@patch("cou.steps.plan._verify_highest_release_achieved")
@patch("cou.steps.plan._verify_data_plane_ready_to_upgrade")
@patch("cou.steps.plan._verify_nova_cloud_controller_scheduler_default_filters")
async def test_pre_plan_sanity_checks(
    mock_verify_nova_cloud_controller_scheduler_default_filters,
    mock_verify_data_plane_ready_to_upgrade,
    mock_verify_highest_release_achieved,
    mock_verify_supported_series,
    mock_verify_hypervisors_cli_input,
    mock_verify_vault_is_unsealed,
    mock_verify_osd_noout_unset,
    mock_verify_model_idle,
    cli_args,
):
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.current_cloud_o7k_release = OpenStackRelease("ussuri")
    mock_analysis_result.current_cloud_series = "focal"
    await cou_plan.verify_cloud(mock_analysis_result, cli_args)
    mock_verify_highest_release_achieved.assert_called_once_with(mock_analysis_result)
    mock_verify_supported_series.assert_called_once_with(mock_analysis_result)
    mock_verify_data_plane_ready_to_upgrade.assert_called_once_with(cli_args, mock_analysis_result)
    mock_verify_hypervisors_cli_input.assert_called_once_with(cli_args, mock_analysis_result)
    mock_verify_nova_cloud_controller_scheduler_default_filters.assert_called_once_with(
        cli_args, mock_analysis_result
    )
    mock_verify_vault_is_unsealed.assert_awaited_once_with(mock_analysis_result)
    mock_verify_osd_noout_unset.assert_awaited_once_with(mock_analysis_result)
    mock_verify_model_idle.assert_awaited_once_with(mock_analysis_result)


@pytest.mark.parametrize(
    "o7k_release, current_series, exp_error_msg",
    [
        (
            OpenStackRelease("caracal"),
            "noble",
            "Cloud series 'noble' is not a Ubuntu LTS series supported by COU. ",
        ),
        (
            OpenStackRelease("train"),
            "bionic",
            "Cloud series 'bionic' is not a Ubuntu LTS series supported by COU. ",
        ),
    ],
)
def test_verify_supported_series(o7k_release, current_series, exp_error_msg):
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.current_cloud_o7k_release = o7k_release
    mock_analysis_result.current_cloud_series = current_series
    cou_plan._verify_supported_series(mock_analysis_result)
    assert exp_error_msg in cou_plan.PlanStatus.error_messages[0]


@pytest.mark.parametrize(
    "o7k_release, series",
    [
        ("yoga", "focal"),
        ("caracal", "jammy"),
    ],
)
def test_verify_highest_release_achieved(o7k_release, series):
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.current_cloud_o7k_release = OpenStackRelease(o7k_release)
    mock_analysis_result.current_cloud_series = series
    exp_error_msg = (
        f"No upgrades available for OpenStack {o7k_release.capitalize()} on "
        f"Ubuntu {series.capitalize()}.\nIn future releases of COU, newer OpenStack releases "
        "may available after manually upgrading to a later Ubuntu series.\n"
        "Charmed OpenStack Upgrader will not support upgrade across series,\n"
        "please refer to the official documentation on how to do series upgrade:\n"
        "- https://docs.openstack.org/charm-guide/latest/admin/upgrades/series.html\n"
        "- https://docs.openstack.org/charm-guide/latest/admin/upgrades/series-openstack.html"
    )
    cou_plan._verify_highest_release_achieved(mock_analysis_result)
    assert cou_plan.PlanStatus.error_messages[0] == exp_error_msg


@pytest.mark.parametrize(
    "upgrade_group",
    [CONTROL_PLANE, None],
)
@patch("cou.steps.plan.get_applications_by_charm_name")
def test_verify_nova_cloud_controller_scheduler_default_filters_failed(
    mock_get_applications_by_charm_name, upgrade_group, cli_args
):
    app_count = 2
    cli_args.upgrade_group = upgrade_group
    nova_cloud_controllers = get_applications("nova-cloud-controller", app_count=app_count)
    for nova_cloud_controller in nova_cloud_controllers:
        nova_cloud_controller.config = {"scheduler-default-filters": "AvailabilityZoneFilter"}
    mock_get_applications_by_charm_name.return_value = nova_cloud_controllers
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.current_cloud_o7k_release = OpenStackRelease("antelope")
    exp_error_msg = (
        "Upgrade from 'antelope' to 'bobcat' is not possible "
        "if `AvailabilityZoneFilter` is in `scheduler-default-filters` option"
    )
    cou_plan._verify_nova_cloud_controller_scheduler_default_filters(
        cli_args, mock_analysis_result
    )
    for i in range(app_count):
        assert exp_error_msg in cou_plan.PlanStatus.error_messages[i]


@pytest.mark.parametrize(
    "upgrade_group",
    [CONTROL_PLANE, None],
)
@patch("cou.steps.plan.get_applications_by_charm_name")
def test_verify_nova_cloud_controller_scheduler_default_filters_missing_app(
    mock_get_applications_by_charm_name, upgrade_group, cli_args
):
    cli_args.upgrade_group = upgrade_group
    mock_get_applications_by_charm_name.side_effect = ApplicationNotFound
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.current_cloud_o7k_release = OpenStackRelease("antelope")
    exp_error_msg = "Cannot find nova-cloud-controller apps"
    cou_plan._verify_nova_cloud_controller_scheduler_default_filters(
        cli_args, mock_analysis_result
    )
    assert exp_error_msg in cou_plan.PlanStatus.warning_messages[0]


@patch("cou.steps.plan.get_applications_by_charm_name")
def test_verify_nova_cloud_controller_scheduler_default_filters_skip_upgrade_group(
    mock_get_applications_by_charm_name, cli_args
):
    app_count = 2
    cli_args.upgrade_group = DATA_PLANE
    mock_get_applications_by_charm_name.return_value = get_applications(
        "nova-cloud-controller", app_count=app_count
    )
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.current_cloud_o7k_release = OpenStackRelease("antelope")
    cou_plan._verify_nova_cloud_controller_scheduler_default_filters(
        cli_args, mock_analysis_result
    )
    assert not cou_plan.PlanStatus.error_messages


@patch("cou.steps.plan.get_applications_by_charm_name")
def test_verify_nova_cloud_controller_scheduler_default_filters_skip_not_antelope(
    mock_get_applications_by_charm_name, cli_args
):
    app_count = 2
    cli_args.upgrade_group = CONTROL_PLANE
    mock_get_applications_by_charm_name.return_value = get_applications(
        "nova-cloud-controller", app_count=app_count
    )
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.current_cloud_o7k_release = OpenStackRelease("yoga")  # not antelope
    cou_plan._verify_nova_cloud_controller_scheduler_default_filters(
        cli_args, mock_analysis_result
    )
    assert not cou_plan.PlanStatus.error_messages


@pytest.mark.parametrize(
    "min_o7k_version_control_plane, min_o7k_version_data_plane, exp_error_msg",
    [
        (
            OpenStackRelease("ussuri"),
            OpenStackRelease("ussuri"),
            "Please upgrade control-plane before data-plane",
        ),
        (
            OpenStackRelease("ussuri"),
            None,
            "Cannot find data-plane apps. Is this a valid OpenStack cloud?",
        ),
    ],
)
def test_verify_data_plane_ready_to_upgrade_error(
    min_o7k_version_control_plane, min_o7k_version_data_plane, exp_error_msg, cli_args
):
    cli_args.upgrade_group = DATA_PLANE
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.current_cloud_series = "focal"
    mock_analysis_result.min_o7k_version_control_plane = min_o7k_version_control_plane
    mock_analysis_result.min_o7k_version_data_plane = min_o7k_version_data_plane
    cou_plan._verify_data_plane_ready_to_upgrade(cli_args, mock_analysis_result)
    assert exp_error_msg in cou_plan.PlanStatus.error_messages[0]


@pytest.mark.parametrize("upgrade_group", [DATA_PLANE, HYPERVISORS])
@patch("cou.steps.plan._is_control_plane_upgraded")
def test_verify_data_plane_ready_to_upgrade_data_plane_cmd(
    mock_control_plane_upgraded, cli_args, upgrade_group
):
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.min_o7k_version_data_plane = OpenStackRelease("ussuri")
    cli_args.upgrade_group = upgrade_group

    cou_plan._verify_data_plane_ready_to_upgrade(cli_args, mock_analysis_result)

    mock_control_plane_upgraded.assert_called_once_with(mock_analysis_result)


@pytest.mark.parametrize("upgrade_group", [CONTROL_PLANE, None])
@patch("cou.steps.plan._is_control_plane_upgraded")
def test_verify_data_plane_ready_to_upgrade_non_data_plane_cmd(
    mock_control_plane_upgraded, cli_args, upgrade_group
):
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.min_o7k_version_data_plane = OpenStackRelease("ussuri")
    cli_args.upgrade_group = upgrade_group

    cou_plan._verify_data_plane_ready_to_upgrade(cli_args, mock_analysis_result)

    mock_control_plane_upgraded.assert_not_called()


@pytest.mark.parametrize(
    "min_o7k_version_control_plane, min_o7k_version_data_plane, expected_result",
    [
        (OpenStackRelease("ussuri"), OpenStackRelease("ussuri"), False),
        (OpenStackRelease("ussuri"), OpenStackRelease("victoria"), False),
        (OpenStackRelease("ussuri"), None, False),
        (OpenStackRelease("victoria"), OpenStackRelease("ussuri"), True),
    ],
)
def test_is_control_plane_upgraded(
    min_o7k_version_control_plane, min_o7k_version_data_plane, expected_result
):
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.min_o7k_version_control_plane = min_o7k_version_control_plane
    mock_analysis_result.min_o7k_version_data_plane = min_o7k_version_data_plane
    assert cou_plan._is_control_plane_upgraded(mock_analysis_result) is expected_result


@pytest.mark.parametrize(
    "o7k_release, current_series, next_release",
    [
        (OpenStackRelease("victoria"), "focal", "wallaby"),
        (OpenStackRelease("xena"), "focal", "yoga"),
        (OpenStackRelease("yoga"), "jammy", "zed"),
        (OpenStackRelease("zed"), "jammy", "antelope"),
        (OpenStackRelease("antelope"), "jammy", "bobcat"),
        (OpenStackRelease("bobcat"), "jammy", "caracal"),
    ],
)
def test_determine_upgrade_target(o7k_release, current_series, next_release):
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.current_cloud_o7k_release = o7k_release
    mock_analysis_result.current_cloud_series = current_series

    target = cou_plan._determine_upgrade_target(mock_analysis_result)

    assert target == next_release


@pytest.mark.parametrize(
    "o7k_release, current_series, exp_error_msg",
    [
        (
            None,
            "bionic",
            "Cannot determine the current OS release in the cloud. "
            "Is this a valid OpenStack cloud?",
        ),  # o7k_release is None
        (
            OpenStackRelease("ussuri"),
            None,
            "Cannot determine the current Ubuntu series in the cloud. "
            "Is this a valid OpenStack cloud?",
        ),  # current_series is None
    ],
)
def test_determine_upgrade_target_current_o7k_and_series(
    o7k_release, current_series, exp_error_msg
):
    with pytest.raises(NoTargetError, match=exp_error_msg):
        mock_analysis_result = MagicMock(spec=Analysis)()
        mock_analysis_result.current_cloud_series = current_series
        mock_analysis_result.current_cloud_o7k_release = o7k_release
        cou_plan._determine_upgrade_target(mock_analysis_result)


def test_determine_upgrade_target_no_next_release():
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.current_cloud_series = "focal"

    exp_error_msg = "Cannot find target to upgrade. Current minimum OS release is "
    "'ussuri'. Current Ubuntu series is 'focal'."

    with pytest.raises(NoTargetError, match=exp_error_msg), patch(
        "cou.utils.openstack.OpenStackRelease.next_release", new_callable=PropertyMock
    ) as mock_next_release:
        mock_next_release.return_value = None
        o7k_release = OpenStackRelease(
            "ussuri"
        )  # instantiate OpenStackRelease with any valid codename
        mock_analysis_result.current_cloud_o7k_release = o7k_release
        cou_plan._determine_upgrade_target(mock_analysis_result)


def test_determine_upgrade_target_out_support_range():
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.current_cloud_series = "focal"
    mock_analysis_result.current_cloud_o7k_release = OpenStackRelease("zed")

    exp_error_msg = (
        "Unable to upgrade cloud from Ubuntu series "
        f"`{mock_analysis_result.current_cloud_series}` to 'antelope'. "
        "Both the from and to releases need to be supported by the current "
        "Ubuntu series 'focal': ussuri, victoria, wallaby, xena, yoga."
    )
    with pytest.raises(OutOfSupportRange, match=exp_error_msg):
        cou_plan._determine_upgrade_target(mock_analysis_result)


@pytest.mark.parametrize("force", [True, False])
def test_create_upgrade_plan(force):
    """Test _create_upgrade_group."""
    app: OpenStackApplication = MagicMock(spec=OpenStackApplication)
    app.name = "test-app"
    app.generate_upgrade_plan.return_value = MagicMock(spec_set=ApplicationUpgradePlan)
    target = OpenStackRelease("victoria")
    description = "test"

    plan = cou_plan._create_upgrade_group([app], target, description, force)

    assert plan.description == description
    assert plan.parallel is False
    assert plan._coro is None
    assert len(plan.sub_steps) == 1
    assert plan.sub_steps[0] == app.generate_upgrade_plan.return_value
    app.generate_upgrade_plan.assert_called_once_with(target, force)


@patch("cou.steps.plan._get_nova_compute_units_and_machines")
@patch("cou.steps.plan.verify_hypervisors_membership")
def test_verify_hypervisors_cli_input_machines(
    mock_verify_hypervisors_membership, mock_nova_compute, cli_args
):
    machine0 = MagicMock(spec_set=Machine)()
    machine0.machine_id = "0"
    machine0.az = "zone-0"

    machine1 = MagicMock(spec_set=Machine)()
    machine1.machine_id = "1"
    machine1.az = "zone-1"

    nova_compute_machines = [machine0]
    mock_nova_compute.return_value = (MagicMock(), nova_compute_machines)
    cli_args.machines = {"0"}
    cli_args.availability_zones = None

    analysis_result = MagicMock(spec_set=Analysis)()
    analysis_result.machines.return_value = {"0": machine0, "1": machine1}

    assert cou_plan._verify_hypervisors_cli_input(cli_args, analysis_result) is None

    mock_verify_hypervisors_membership.assert_called_once_with(
        all_options=set(analysis_result.machines.keys()),
        hypervisors_options={machine.machine_id for machine in nova_compute_machines},
        cli_input=cli_args.machines,
        parameter_type="Machine(s)",
    )


@patch("cou.steps.plan._get_nova_compute_units_and_machines")
@patch("cou.steps.plan.verify_hypervisors_membership")
def test_verify_hypervisors_cli_input_azs(
    mock_verify_hypervisors_membership, mock_nova_compute, cli_args
):
    machine0 = MagicMock(spec_set=Machine)()
    machine0.machine_id = "0"
    machine0.az = "zone-0"

    machine1 = MagicMock(spec_set=Machine)()
    machine1.machine_id = "1"
    machine1.az = "zone-1"

    nova_compute_machines = [machine0]
    mock_nova_compute.return_value = (MagicMock(), nova_compute_machines)
    cli_args.machines = None
    cli_args.availability_zones = {"zone-0"}

    analysis_result = MagicMock(spec_set=Analysis)()
    analysis_result.machines.return_value = {"0": machine0, "1": machine1}

    assert cou_plan._verify_hypervisors_cli_input(cli_args, analysis_result) is None

    mock_verify_hypervisors_membership.assert_called_once_with(
        all_options={
            machine.az for machine in analysis_result.machines.values() if machine.az is not None
        },
        hypervisors_options={
            machine.az for machine in nova_compute_machines if machine.az is not None
        },
        cli_input=cli_args.availability_zones,
        parameter_type="Availability Zone(s)",
    )


@patch("cou.steps.plan._get_nova_compute_units_and_machines")
@patch("cou.steps.plan.verify_hypervisors_membership")
def test_verify_hypervisors_cli_input_none(
    mock_verify_hypervisors_membership, mock_nova_compute, cli_args
):
    mock_nova_compute.return_value = [MagicMock(), MagicMock()]
    cli_args.machines = None
    cli_args.availability_zones = None

    analysis_result = MagicMock(spec_set=Analysis)()

    assert cou_plan._verify_hypervisors_cli_input(cli_args, analysis_result) is None

    mock_nova_compute.assert_called_once_with(analysis_result.apps_data_plane)
    mock_verify_hypervisors_membership.assert_not_called()


@pytest.mark.parametrize(
    "all_options, hypervisors_options, cli_input, parameter_type",
    [
        ({"0", "1", "2"}, {"1", "2"}, {"1"}, "Machine(s)"),
        ({"0", "1", "2"}, {"1", "2"}, {"2"}, "Machine(s)"),
        ({"zone-0", "zone-1", "zone-2"}, {"zone-1", "zone-2"}, {"zone-1"}, "Availability Zone(s)"),
        ({"zone-0", "zone-1", "zone-2"}, {"zone-1", "zone-2"}, {"zone-2"}, "Availability Zone(s)"),
    ],
)
def test_verify_hypervisors_membership(
    all_options, hypervisors_options, cli_input, parameter_type
):
    assert (
        cou_plan.verify_hypervisors_membership(
            all_options, hypervisors_options, cli_input, parameter_type
        )
        is None
    )


@pytest.mark.parametrize(
    "all_options, hypervisors_options, cli_input, parameter_type, exp_error_msg",
    [
        ({"0", "1", "2"}, {"1", "2"}, {"3"}, "Machine(s)", r"Machine.*don't exist."),
        (
            {"zone-0", "zone-1", "zone-2"},
            {"zone-1", "zone-2"},
            {"zone-3"},
            "Availability Zone(s)",
            r"Availability Zone.*don't exist.",
        ),
    ],
)
def test_verify_hypervisors_membership_raise_dont_exist(
    all_options, hypervisors_options, cli_input, parameter_type, exp_error_msg
):
    with pytest.raises(DataPlaneMachineFilterError, match=exp_error_msg):
        cou_plan.verify_hypervisors_membership(
            all_options, hypervisors_options, cli_input, parameter_type
        )


@pytest.mark.parametrize(
    "all_options, hypervisors_options, cli_input, parameter_type, exp_error_msg",
    [
        (
            {"0", "1", "2"},
            {"1", "2"},
            {"0"},
            "Machine(s)",
            r"Machine.*are not considered as hypervisors.",
        ),
        (
            {"zone-0", "zone-1", "zone-2"},
            {"zone-1", "zone-2"},
            {"zone-0"},
            "Availability Zone(s)",
            r"Availability Zone.* are not considered as hypervisors.",
        ),
    ],
)
def test_verify_hypervisors_membership_raise_not_data_plane(
    all_options, hypervisors_options, cli_input, parameter_type, exp_error_msg
):
    with pytest.raises(DataPlaneMachineFilterError, match=exp_error_msg):
        cou_plan.verify_hypervisors_membership(
            all_options, hypervisors_options, cli_input, parameter_type
        )


@pytest.mark.parametrize(
    "all_options, hypervisors_options, cli_input, parameter_type, exp_error_msg",
    [
        (
            {},
            {},
            {"0"},
            "Machine(s)",
            r"Cannot find Machine\(s\). Is this a valid OpenStack cloud?",
        ),
        (
            {},
            {},
            {"zone-0"},
            "Availability Zone(s)",
            r"Cannot find Availability Zone\(s\). Is this a valid OpenStack cloud?",
        ),
    ],
)
def test_verify_hypervisors_membership_raise_valid_openstack(
    all_options, hypervisors_options, cli_input, parameter_type, exp_error_msg
):
    with pytest.raises(DataPlaneMachineFilterError, match=exp_error_msg):
        cou_plan.verify_hypervisors_membership(
            all_options, hypervisors_options, cli_input, parameter_type
        )


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
        Machine(str(machine_id), (), f"zone-{machine_id + 1}") for machine_id in range(2)
    }
    # assuming that machine-2 has some VMs running
    non_empty_hypervisor_machine = Machine("2", (), "zone-3")

    upgradable_hypervisors = empty_hypervisors_machines
    if force:
        upgradable_hypervisors.add(non_empty_hypervisor_machine)

    mock_hypervisors_machines.return_value = upgradable_hypervisors

    cli_args.machines = cli_machines
    cli_args.availability_zones = cli_azs
    cli_args.force = force

    machines = await cou_plan._filter_hypervisors_machines(cli_args, MagicMock())

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
    machines = {f"{i}": Machine(f"{i}", (), f"zone-{i + 1}") for i in range(3)}
    nova_compute = MagicMock(spec_set=OpenStackApplication)()
    nova_compute.charm = "nova-compute"
    nova_compute.units = {
        f"nova-compute/{i}": Unit(
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


@patch("cou.steps.plan._get_purge_data_steps", return_value=["purge_step"])
@patch("cou.steps.plan._get_archive_data_steps", return_value=["archive_step"])
@patch("cou.steps.plan._get_backup_steps", return_value=["backup_step"])
def test_get_pre_upgrade_steps(
    mock_get_backup_steps,
    mock_get_archive_steps,
    mock_get_purge_steps,
    cli_args,
    model,
):
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.current_cloud_o7k_release = OpenStackRelease("ussuri")
    mock_analysis_result.model = model

    expected_steps = []
    expected_steps.append("backup_step")
    expected_steps.append("archive_step")
    expected_steps.append("purge_step")

    pre_upgrade_steps = cou_plan._get_pre_upgrade_steps(mock_analysis_result, cli_args)

    assert pre_upgrade_steps == expected_steps
    mock_get_backup_steps.assert_called_with(mock_analysis_result, cli_args)
    mock_get_archive_steps.assert_called_with(mock_analysis_result, cli_args)
    mock_get_purge_steps.assert_called_with(mock_analysis_result, cli_args)


def test_get_backup_steps(cli_args, model):
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.model = model
    cli_args.backup = True

    steps = cou_plan._get_backup_steps(mock_analysis_result, cli_args)
    assert steps == [
        PreUpgradeStep(
            description="Back up MySQL databases",
            coro=backup(mock_analysis_result.model),
        )
    ]


def test_get_backup_steps_no_backup(cli_args, model):
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.model = model
    cli_args.backup = False

    steps = cou_plan._get_backup_steps(mock_analysis_result, cli_args)
    assert steps == []


def test_get_archive_data_steps(cli_args, model):
    cli_args.archive_batch_size = 2000
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.model = model

    steps = cou_plan._get_archive_data_steps(mock_analysis_result, cli_args)
    assert steps == [
        PreUpgradeStep(
            description="Archive old database data on nova-cloud-controller",
            coro=archive(
                mock_analysis_result.model,
                mock_analysis_result.apps_control_plane,
                batch_size=2000,
            ),
        )
    ]


def test_get_archive_data_steps_no_archive(cli_args, model):
    cli_args.archive_batch_size = 2000
    cli_args.archive = False
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.model = model

    steps = cou_plan._get_archive_data_steps(mock_analysis_result, cli_args)
    assert steps == []


def test_get_purge_data_steps_no_purge(cli_args, model):
    cli_args.purge = False
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.model = model

    app: OpenStackApplication = MagicMock(spec=OpenStackApplication)
    app.charm = "nova-cloud-controller"
    mock_analysis_result.apps_control_plane = [app]
    app.actions = {"purge-data": True}

    steps = cou_plan._get_purge_data_steps(mock_analysis_result, cli_args)
    assert [] == steps


def test_get_purge_data_steps_no_action(cli_args, model):
    cli_args.purge = True
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.model = model

    app: OpenStackApplication = MagicMock(spec=OpenStackApplication)
    app.charm = "nova-cloud-controller"
    mock_analysis_result.apps_control_plane = [app]
    app.actions = {}

    steps = cou_plan._get_purge_data_steps(mock_analysis_result, cli_args)
    assert [] == steps


def test_get_purge_data_steps_no_app(cli_args, model):
    cli_args.purge = True
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.model = model

    steps = cou_plan._get_purge_data_steps(mock_analysis_result, cli_args)
    assert [] == steps


@pytest.mark.parametrize(
    "case,purge_before_arg,msg",
    [
        ("Purge all", None, "Purge all data from shadow tables on nova-cloud-controller"),
        (
            "Purge before",
            "2000-01-02",
            "Purge data before 2000-01-02 from shadow tables on nova-cloud-controller",
        ),
    ],
)
def test_get_purge_data_steps(
    case,
    purge_before_arg,
    msg,
    cli_args,
    model,
):
    cli_args.purge = True
    cli_args.purge_before = purge_before_arg
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.model = model

    app: OpenStackApplication = MagicMock(spec=OpenStackApplication)
    app.charm = "nova-cloud-controller"
    app.actions = {"purge-data": True}

    # nova-cloud-controller is a control plane app
    mock_analysis_result.apps_control_plane = [app]

    expected_steps = [
        PreUpgradeStep(
            description=msg,
            coro=purge(mock_analysis_result.model, [app], before=cli_args.purge_before),
        )
    ]
    steps = cou_plan._get_purge_data_steps(mock_analysis_result, cli_args)
    assert expected_steps == steps


@pytest.mark.parametrize("upgrade_group", [CONTROL_PLANE, HYPERVISORS])
def test_get_post_upgrade_steps_empty(upgrade_group):
    """Test get post upgrade steps not run for control-plane or hypervisors group."""
    args = MagicMock(spec_set=CLIargs)()
    args.upgrade_group = upgrade_group

    post_upgrade_steps = cou_plan._get_post_upgrade_steps(MagicMock(), args)

    assert post_upgrade_steps == []


@pytest.mark.parametrize("upgrade_group", [DATA_PLANE, None])
def test_get_post_upgrade_steps_ceph_mon(upgrade_group):
    """Test get post upgrade steps including ceph-mon."""
    args = MagicMock(spec_set=CLIargs)()
    args.set_noout = True
    args.upgrade_group = upgrade_group
    analysis_result = MagicMock(spec_set=Analysis)()

    post_upgrade_steps = cou_plan._get_post_upgrade_steps(analysis_result, args)

    assert post_upgrade_steps == [
        PostUpgradeStep(
            "Ensure ceph-mon's 'require-osd-release' option matches the 'ceph-osd' version",
            coro=set_require_osd_release_option(
                analysis_result.model, analysis_result.apps_control_plane
            ),
        ),
        PostUpgradeStep(
            description="Unset ceph cluster 'noout' flag after data plane upgrade",
            coro=ceph.osd_noout(
                analysis_result.model, analysis_result.apps_control_plane, enable=False
            ),
        ),
    ]


@patch("cou.steps.plan._create_upgrade_group")
def test_generate_control_plane_plan(mock_create_upgrade_group):
    target = OpenStackRelease("victoria")
    force = False

    keystone = MagicMock(spec_set=OpenStackApplication)()
    keystone.is_subordinate = False

    keystone_ldap = MagicMock(spec_set=SubordinateApplication)()
    keystone_ldap.is_subordinate = True

    cou_plan._generate_control_plane_plan(target, [keystone, keystone_ldap], force)

    expected_calls = [
        call(
            apps=[keystone],
            description="Control Plane principal(s) upgrade plan",
            target=target,
            force=force,
        ),
        call(
            apps=[keystone_ldap],
            description="Subordinate(s) upgrade plan",
            target=target,
            force=force,
        ),
    ]

    mock_create_upgrade_group.assert_has_calls(expected_calls)


@pytest.mark.asyncio
@patch("cou.steps.plan._determine_upgrade_target")
@patch("cou.steps.plan._get_pre_upgrade_steps")
@patch("cou.steps.plan._generate_control_plane_plan", return_value=MagicMock())
@patch("cou.steps.plan._separate_hypervisors_apps", return_value=(MagicMock(), MagicMock()))
@patch("cou.steps.plan._generate_data_plane_hypervisors_plan", return_value=UpgradePlan("foo"))
@patch(
    "cou.steps.plan._generate_data_plane_remaining_plan",
    return_value=MagicMock(),
)
@patch("cou.steps.plan._get_post_upgrade_steps")
async def test_generate_plan_upgrade_group_none(
    mock_post_upgrade_steps,
    mock_ceph_osd_subordinates,
    mock_generate_data_plane_hypervisors_plan,
    mock_separate_hypervisors_apps,
    mock_control_plane,
    mock_pre_upgrade_steps,
    mock_determine_upgrade_target,
    cli_args,
):
    cli_args.upgrade_group = None
    mock_analysis_result = MagicMock(spec=Analysis)()

    await cou_plan.generate_plan(mock_analysis_result, cli_args)

    mock_determine_upgrade_target.assert_called_once()
    mock_pre_upgrade_steps.assert_called_once()
    mock_control_plane.assert_called_once()
    mock_separate_hypervisors_apps.assert_called_once()

    mock_generate_data_plane_hypervisors_plan.assert_called_once()
    mock_ceph_osd_subordinates.assert_called_once()
    mock_post_upgrade_steps.assert_called_once()


@pytest.mark.asyncio
@patch("cou.steps.plan._determine_upgrade_target")
@patch("cou.steps.plan._get_pre_upgrade_steps")
@patch(
    "cou.steps.plan._generate_control_plane_plan",
    return_value=MagicMock(),
)
@patch("cou.steps.plan._separate_hypervisors_apps", return_value=(MagicMock(), MagicMock()))
@patch("cou.steps.plan._generate_data_plane_hypervisors_plan", return_value=UpgradePlan("foo"))
@patch(
    "cou.steps.plan._generate_data_plane_remaining_plan",
    return_value=MagicMock(),
)
@patch("cou.steps.plan._get_post_upgrade_steps")
async def test_generate_plan_upgrade_group_control_plane(
    mock_post_upgrade_steps,
    mock_ceph_osd_subordinates,
    mock_generate_data_plane_hypervisors_plan,
    mock_separate_hypervisors_apps,
    mock_control_plane,
    mock_pre_upgrade_steps,
    mock_determine_upgrade_target,
    cli_args,
):
    cli_args.upgrade_group = CONTROL_PLANE
    mock_analysis_result = MagicMock(spec=Analysis)()

    await cou_plan.generate_plan(mock_analysis_result, cli_args)

    mock_determine_upgrade_target.assert_called_once()
    mock_pre_upgrade_steps.assert_called_once()
    mock_control_plane.assert_called_once()

    mock_separate_hypervisors_apps.assert_not_called()
    mock_generate_data_plane_hypervisors_plan.assert_not_called()
    mock_ceph_osd_subordinates.assert_not_called()
    mock_post_upgrade_steps.assert_called_once()


@pytest.mark.asyncio
@patch("cou.steps.plan._determine_upgrade_target")
@patch("cou.steps.plan._get_pre_upgrade_steps")
@patch(
    "cou.steps.plan._generate_control_plane_plan",
    return_value=MagicMock(),
)
@patch("cou.steps.plan._separate_hypervisors_apps", return_value=(MagicMock(), MagicMock()))
@patch("cou.steps.plan._generate_data_plane_hypervisors_plan", return_value=UpgradePlan("foo"))
@patch(
    "cou.steps.plan._generate_data_plane_remaining_plan",
    return_value=MagicMock(),
)
@patch("cou.steps.plan._get_post_upgrade_steps")
async def test_generate_plan_upgrade_group_data_plane(
    mock_post_upgrade_steps,
    mock_ceph_osd_subordinates,
    mock_generate_data_plane_hypervisors_plan,
    mock_separate_hypervisors_apps,
    mock_control_plane,
    mock_pre_upgrade_steps,
    mock_determine_upgrade_target,
    cli_args,
):
    cli_args.upgrade_group = DATA_PLANE
    mock_analysis_result = MagicMock(spec=Analysis)()

    await cou_plan.generate_plan(mock_analysis_result, cli_args)

    mock_determine_upgrade_target.assert_called_once()
    mock_pre_upgrade_steps.assert_called_once()
    mock_control_plane.assert_not_called()
    mock_separate_hypervisors_apps.assert_called_once()

    mock_generate_data_plane_hypervisors_plan.assert_called_once()
    mock_ceph_osd_subordinates.assert_called_once()
    mock_post_upgrade_steps.assert_called_once()


@pytest.mark.asyncio
@patch("cou.steps.plan._determine_upgrade_target")
@patch("cou.steps.plan._get_pre_upgrade_steps")
@patch("cou.steps.plan._generate_control_plane_plan")
@patch("cou.steps.plan._separate_hypervisors_apps", return_value=(MagicMock(), MagicMock()))
@patch("cou.steps.plan._generate_data_plane_hypervisors_plan", return_value=UpgradePlan("foo"))
@patch("cou.steps.plan._generate_data_plane_remaining_plan")
@patch("cou.steps.plan._get_post_upgrade_steps")
async def test_generate_plan_upgrade_group_hypervisors(
    mock_post_upgrade_steps,
    mock_ceph_osd_subordinates,
    mock_generate_data_plane_hypervisors_plan,
    mock_separate_hypervisors_apps,
    mock_control_plane,
    mock_pre_upgrade_steps,
    mock_determine_upgrade_target,
    cli_args,
):
    cli_args.upgrade_group = HYPERVISORS
    mock_analysis_result = MagicMock(spec=Analysis)()

    await cou_plan.generate_plan(mock_analysis_result, cli_args)

    mock_determine_upgrade_target.assert_called_once()
    mock_pre_upgrade_steps.assert_called_once()
    mock_control_plane.assert_not_called()
    mock_separate_hypervisors_apps.assert_called_once()

    mock_generate_data_plane_hypervisors_plan.assert_called_once()
    mock_ceph_osd_subordinates.assert_not_called()
    mock_post_upgrade_steps.assert_called_once()


def test_separate_hypervisors_apps(model):
    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}

    nova_compute = NovaCompute(
        name="nova-compute",
        can_upgrade_to="ussuri/stable",
        charm="nova-compute",
        channel="ussuri/stable",
        config={"source": {"value": "distro"}, "action-managed-upgrade": {"value": False}},
        machines=machines["0"],
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "nova-compute/0": Unit(
                name="nova-compute/0",
                workload_version="21.0.0",
                machine=machines["0"],
            )
        },
        workload_version="21.0.0",
    )

    # apps colocated with nova-compute are considered as hypervisor
    cinder = OpenStackApplication(
        name="cinder",
        can_upgrade_to="ussuri/stable",
        charm="cinder",
        channel="ussuri/stable",
        config={
            "openstack-origin": {"value": "distro"},
            "action-managed-upgrade": {"value": False},
        },
        machines=machines["0"],
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "cinder/0": Unit(
                name="cinder/0",
                workload_version="16.4.2",
                machine=machines["0"],
            )
        },
        workload_version="16.4.2",
    )

    # subordinates are considered as non-hypervisors
    ovn_chassis = OVNSubordinate(
        name="ovn-chassis",
        can_upgrade_to="22.03/stable",
        charm="ovn-chassis",
        channel="22.03/stable",
        config={},
        machines=machines["0"],
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=["nova-compute"],
        units={},
        workload_version="22.3",
    )

    # ceph-osd colocated with nova-compute is considered as non-hypervisor
    ceph_osd_colocated = CephOsd(
        name="ceph-osd-colocated",
        can_upgrade_to="octopus/stable",
        charm="ceph-osd",
        channel="octopus/stable",
        config={"source": {"value": "distro"}},
        machines=machines["0"],
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "ceph-osd/0": Unit(
                name="ceph-osd/0",
                workload_version="17.0.1",
                machine=machines["0"],
            )
        },
        workload_version="17.0.1",
    )

    # ceph-osd not colocated with nova-compute is considered as non-hypervisor
    ceph_osd_not_colocated = CephOsd(
        name="ceph-osd-not-colocated",
        can_upgrade_to="octopus/stable",
        charm="ceph-osd",
        channel="octopus/stable",
        config={"source": {"value": "distro"}},
        machines=machines["1"],
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "ceph-osd/0": Unit(
                name="ceph-osd/0",
                workload_version="17.0.1",
                machine=machines["1"],
            )
        },
        workload_version="17.0.1",
    )

    result = cou_plan._separate_hypervisors_apps(
        [
            nova_compute,
            cinder,
            ceph_osd_colocated,
            ceph_osd_not_colocated,
            ovn_chassis,
        ]
    )
    assert result == (
        [nova_compute, cinder],
        [ceph_osd_colocated, ceph_osd_not_colocated, ovn_chassis],
    )


@pytest.mark.asyncio
@patch("cou.steps.plan.HypervisorUpgradePlanner")
@patch("cou.steps.plan._filter_hypervisors_machines")
async def test_generate_data_plane_hypervisors_plan(
    mock_filter_hypervisors, mock_hypervisor_planner, cli_args
):
    apps = [MagicMock(spec_set=OpenStackApplication)()]
    target = OpenStackRelease("victoria")
    analysis_result = MagicMock(spec_set=Analysis)()
    hypervisors_machines = [Machine("0", (), "zone-0")]
    mock_filter_hypervisors.return_value = hypervisors_machines
    hypervisor_planner_instance = mock_hypervisor_planner.return_value
    cli_args.force = False

    await cou_plan._generate_data_plane_hypervisors_plan(target, analysis_result, cli_args, apps)

    mock_filter_hypervisors.assert_called_once_with(cli_args, analysis_result)
    mock_hypervisor_planner.assert_called_once_with(apps, hypervisors_machines)
    hypervisor_planner_instance.generate_upgrade_plan.assert_called_once_with(
        target, cli_args.force
    )


@pytest.mark.asyncio
@patch("cou.steps.plan.HypervisorUpgradePlanner")
@patch("cou.steps.plan._filter_hypervisors_machines")
@patch("cou.steps.plan._generate_instance_plan")
async def test_generate_data_plane_hypervisors_plan_none(
    mock_generate_instance_plan, mock_filter_hypervisors, mock_hypervisor_planner, cli_args
):
    """Test hypervisor plan is not None when _generate_instance_plan return None."""
    apps = [MagicMock(spec_set=OpenStackApplication)()]
    target = OpenStackRelease("victoria")
    analysis_result = MagicMock(spec_set=Analysis)()
    hypervisors_machines = [Machine("0", (), "zone-0")]
    mock_filter_hypervisors.return_value = hypervisors_machines
    mock_generate_instance_plan.return_value = None
    cli_args.force = False

    plan = await cou_plan._generate_data_plane_hypervisors_plan(
        target, analysis_result, cli_args, apps
    )

    assert isinstance(plan, UpgradePlan)  # plan is not None
    mock_filter_hypervisors.assert_called_once_with(cli_args, analysis_result)
    mock_hypervisor_planner.assert_called_once_with(apps, hypervisors_machines)


@patch("cou.steps.plan._create_upgrade_group")
def test_generate_data_plane_remaining_plan(mock_create_upgrade_group):
    target = OpenStackRelease("victoria")
    force = False

    ceph_osd = MagicMock(spec_set=CephOsd)()
    ceph_osd.is_subordinate = False

    ovn_chassis = MagicMock(spec_set=OVNSubordinate)()
    ovn_chassis.is_subordinate = True

    cou_plan._generate_data_plane_remaining_plan(target, [ceph_osd, ovn_chassis], force)
    expected_calls = [
        call(
            apps=[ceph_osd],
            description="Remaining Data Plane principal(s) upgrade plan",
            target=target,
            force=force,
        ),
    ]
    mock_create_upgrade_group.assert_has_calls(expected_calls)


def test_generate_instance_plan_app():
    """Test _generate_instance_plan for OpenStackApplication."""
    app: OpenStackApplication = MagicMock(spec=OpenStackApplication)
    app.name = "test-app"
    app.generate_upgrade_plan.return_value = MagicMock(spec_set=ApplicationUpgradePlan)
    target = OpenStackRelease("victoria")

    plan = cou_plan._generate_instance_plan(app, target, False)

    assert isinstance(plan, ApplicationUpgradePlan)
    app.generate_upgrade_plan.assert_called_once_with(target, False)


def test_generate_instance_plan_hypervisors():
    """Test _generate_instance_plan for HypervisorUpgradePlanner."""
    hypervisors: HypervisorUpgradePlanner = MagicMock(spec=HypervisorUpgradePlanner)
    hypervisors.get_azs.return_value = {
        "az1": MagicMock(spec_set=HypervisorGroup),
        "az2": MagicMock(spec_set=HypervisorGroup),
    }
    hypervisors.generate_upgrade_plan.return_value = MagicMock(spec_set=UpgradePlan)
    target = OpenStackRelease("victoria")

    plan = cou_plan._generate_instance_plan(hypervisors, target, False)

    assert isinstance(plan, UpgradePlan)
    hypervisors.generate_upgrade_plan.assert_called_once_with(target, False)


def test_generate_instance_plan_haltupgradeplangeneration():
    """Test _generate_instance_plan with HaltUpgradePlanGeneration."""
    app: OpenStackApplication = MagicMock(spec=OpenStackApplication)
    app.name = "test-app"
    app.generate_upgrade_plan.side_effect = HaltUpgradePlanGeneration
    target = OpenStackRelease("victoria")

    plan = cou_plan._generate_instance_plan(app, target, False)

    assert plan is None
    app.generate_upgrade_plan.assert_called_once_with(target, False)


@pytest.mark.parametrize(
    "exceptions", [ApplicationError, MismatchedOpenStackVersions, COUException]
)
@patch("cou.steps.plan.PlanStatus", spec_set=cou_plan.PlanStatus)
def test_generate_instance_plan_couexception(mock_plan_warnings, exceptions):
    """Test _generate_instance_plan with COUException."""
    app: OpenStackApplication = MagicMock(spec=OpenStackApplication)
    app.name = "test-app"
    app.generate_upgrade_plan.side_effect = exceptions("mock message")
    target = OpenStackRelease("victoria")

    plan = cou_plan._generate_instance_plan(app, target, False)

    assert plan is None
    app.generate_upgrade_plan.assert_called_once_with(target, False)
    mock_plan_warnings.add_message.assert_called_once_with(
        "Cannot generate plan for 'test-app'\n\tmock message", cou_plan.MessageType.ERROR
    )


def test_create_upgrade_plan_failed():
    """Test _generate_instance_plan with unknown exception."""
    app: OpenStackApplication = MagicMock(spec=OpenStackApplication)
    app.name = "test-app"
    app.generate_upgrade_plan.side_effect = Exception("test")

    with pytest.raises(Exception, match="test"):
        cou_plan._create_upgrade_group([app], "victoria", "test", False)


@pytest.mark.asyncio
@patch("cou.steps.plan.print_and_debug")
@patch("cou.steps.analyze.Analysis")
@patch("cou.steps.plan.ceph")
async def test_post_upgrade_sanity_checks(mock_ceph, mock_analysis, mock_print_and_debug):
    """Test post_upgrade_sanity_checks with exception."""
    mock_ceph.assert_osd_noout_state = AsyncMock(side_effect=ApplicationError)
    await cou_plan.post_upgrade_sanity_checks(mock_analysis)
    mock_print_and_debug.assert_called()


@pytest.mark.asyncio
@patch("cou.steps.plan.print_and_debug")
@patch("cou.steps.analyze.Analysis")
@patch("cou.steps.plan.ceph")
async def test_post_upgrade_sanity_checks_no_exception(
    mock_ceph, mock_analysis, mock_print_and_debug
):
    """Test post_upgrade_sanity_checks without exception."""
    mock_ceph.assert_osd_noout_state = AsyncMock()
    await cou_plan.post_upgrade_sanity_checks(mock_analysis)
    mock_print_and_debug.assert_not_called()


@patch("cou.steps.analyze.Analysis")
def test_get_set_noout_steps(mock_analysis, cli_args):
    """Test _get_set_noout_steps with --set-noout."""
    cli_args.set_noout = True
    cli_args.upgrade_group = None

    step = cou_plan._get_set_noout_steps(mock_analysis, cli_args)
    assert step == [
        PreUpgradeStep(
            description="Set ceph cluster 'noout' flag before data plane upgrade",
            coro=ceph.osd_noout(
                mock_analysis.model, mock_analysis.apps_control_plane, enable=True
            ),
        )
    ]


@pytest.mark.asyncio
@patch("cou.steps.plan.PlanStatus")
@patch("cou.steps.analyze.Analysis")
@patch("cou.steps.plan.verify_vault_is_unsealed")
async def test_verify_vault_is_unsealed_failed(
    mock_verify_vault_is_unsealed, mock_analysis, mock_plan_status
):
    """Test _verify_vault_is_unsealed."""
    mock_verify_vault_is_unsealed.side_effect = VaultSealed()
    await cou_plan._verify_vault_is_unsealed(mock_analysis)
    mock_plan_status.add_message.assert_called_once()


@pytest.mark.asyncio
@patch("cou.steps.plan.PlanStatus")
@patch("cou.steps.analyze.Analysis")
@patch("cou.steps.plan.ceph.assert_osd_noout_state")
async def test_verify_osd_noout_unset_failed(
    mock_verify_osd_noout_unset, mock_analysis, mock_plan_status
):
    """Test _verify_osd_noout_unset."""
    mock_verify_osd_noout_unset.side_effect = ApplicationError()
    await cou_plan._verify_osd_noout_unset(mock_analysis)
    mock_plan_status.add_message.assert_called_once()


@pytest.mark.asyncio
@patch("cou.steps.plan.PlanStatus")
@patch("cou.steps.analyze.Analysis")
@patch("cou.steps.plan.verify_vault_is_unsealed")
async def test_verify_model_idle_failed(mock_verify_model_idle, mock_analysis, mock_plan_status):
    """Test _verify_model_idle."""
    mock_verify_model_idle.side_effect = Exception()
    await cou_plan._verify_model_idle(mock_analysis)
    mock_plan_status.add_message.assert_called_once()


@pytest.mark.asyncio
@patch("cou.steps.plan.PlanStatus", autospec=True)
@patch("cou.steps.analyze.Analysis")
@patch("cou.steps.plan.ceph.get_versions", autospec=True)
async def test_verify_ceph_running_versions_consistent(
    mock_get_versions, mock_analysis, mock_plan_status
):
    """Test _verify_ceph_running_versions_consistent (normal success case)."""
    # the scenario: two ceph clouds, both with consistent running versions
    mock_analysis.apps_control_plane = [
        MagicMock(charm="ceph-mon", units={"first/0": MagicMock(name="first/0")}),
        MagicMock(charm="ceph-mon", units={"second/0": MagicMock(name="second/0")}),
    ]
    mock_get_versions.side_effect = [
        {
            "mon": {
                # hashes truncated for brevity in tests
                "ceph version 16.2.15 (618f440) pacific (stable)": 1,
            },
            "osd": {
                "ceph version 16.2.15 (618f440) pacific (stable)": 18,
            },
            "overall": {
                "ceph version 16.2.15 (618f440) pacific (stable)": 20,
            },
        },
        {
            "mon": {"ceph version 15.2.17 (8a82819) octopus (stable)": 1},
            "osd": {
                "ceph version 15.2.17 (8a82819) octopus (stable)": 2,
            },
            "overall": {
                "ceph version 15.2.17 (8a82819) octopus (stable)": 2,
            },
        },
    ]

    await cou_plan._verify_ceph_running_versions_consistent(mock_analysis)

    # verify that for this scenario, no warnings were generated
    mock_plan_status.add_message.assert_not_called()


@pytest.mark.asyncio
@patch("cou.steps.plan.PlanStatus", autospec=True)
@patch("cou.steps.analyze.Analysis")
@patch("cou.steps.plan.ceph.get_versions", autospec=True)
async def test_verify_ceph_running_versions_inconsistent(
    mock_get_versions, mock_analysis, mock_plan_status
):
    """Test _verify_ceph_running_versions_consistent (failure case)."""
    # the scenario: two ceph clouds, both with inconsistent running versions
    mock_analysis.apps_control_plane = [
        MagicMock(charm="ceph-mon", units={"first/0": MagicMock(name="first/0")}),
        MagicMock(charm="ceph-mon", units={"second/0": MagicMock(name="second/0")}),
    ]
    mock_get_versions.side_effect = [
        {
            "mon": {
                # hashes truncated for brevity in tests
                "ceph version 16.2.14 (238ba60) pacific (stable)": 2,
                "ceph version 16.2.15 (618f440) pacific (stable)": 1,
            },
            "osd": {
                "ceph version 15.2.17 (8a82819) octopus (stable)": 2,
                "ceph version 16.2.15 (618f440) pacific (stable)": 18,
            },
            "overall": {
                "ceph version 15.2.17 (8a82819) octopus (stable)": 2,
                "ceph version 16.2.14 (238ba60) pacific (stable)": 5,
                "ceph version 16.2.15 (618f440) pacific (stable)": 20,
            },
        },
        {
            "mon": {"ceph version 16.2.15 (618f440) pacific (stable)": 1},
            "osd": {
                "ceph version 15.2.17 (8a82819) octopus (stable)": 2,
                "ceph version 16.2.15 (618f440) pacific (stable)": 18,
            },
            "overall": {
                "ceph version 15.2.17 (8a82819) octopus (stable)": 2,
                "ceph version 16.2.15 (618f440) pacific (stable)": 20,
            },
        },
    ]

    await cou_plan._verify_ceph_running_versions_consistent(mock_analysis)

    # verify that for this scenario, there is a plan warning message added
    assert mock_plan_status.add_message.call_count == 2
    assert "first" in mock_plan_status.add_message.call_args_list[0].args[0]
    assert "mismatched versions" in mock_plan_status.add_message.call_args_list[0].args[0]
    assert "pacific" in mock_plan_status.add_message.call_args_list[0].args[0]
    assert mock_plan_status.add_message.call_args_list[0].args[1] == cou_plan.MessageType.WARNING
    assert "second" in mock_plan_status.add_message.call_args_list[1].args[0]
    assert "mismatched versions" in mock_plan_status.add_message.call_args_list[1].args[0]
    assert "pacific" in mock_plan_status.add_message.call_args_list[1].args[0]
    assert mock_plan_status.add_message.call_args_list[1].args[1] == cou_plan.MessageType.WARNING


@pytest.mark.asyncio
@patch("cou.steps.plan.PlanStatus", autospec=True)
@patch("cou.steps.analyze.Analysis")
@patch("cou.steps.plan.ceph.get_versions", autospec=True)
async def test_verify_ceph_running_versions_no_units(
    mock_get_versions, mock_analysis, mock_plan_status
):
    """Test _verify_ceph_running_versions_consistent (no units edge case)."""
    mock_analysis.apps_control_plane = [
        MagicMock(charm="ceph-mon", units={}),
    ]

    await cou_plan._verify_ceph_running_versions_consistent(mock_analysis)

    mock_plan_status.add_message.assert_not_called()


@pytest.mark.asyncio
@patch("cou.steps.plan.print_and_debug")
@patch("cou.steps.analyze.Analysis")
@patch("cou.steps.plan.ceph.assert_osd_noout_state", AsyncMock())
async def test_post_upgrade_sanity_checks_ceph_mon_versions_no_units(
    mock_analysis, mock_print_and_debug
):
    """Test post_upgrade_sanity_checks with exception."""
    mock_analysis.apps_control_plane = [
        MagicMock(charm="ceph-mon", units={}),
    ]

    await cou_plan.post_upgrade_sanity_checks(mock_analysis)

    mock_print_and_debug.assert_not_called()


@pytest.mark.asyncio
@patch("cou.steps.plan.print_and_debug")
@patch("cou.steps.analyze.Analysis")
@patch("cou.steps.plan.ceph.assert_osd_noout_state", AsyncMock())
@patch("cou.steps.plan.ceph.get_versions", autospec=True)
async def test_post_upgrade_sanity_checks_ceph_mon_versions_inconsistent(
    mock_get_versions, mock_analysis, mock_print_and_debug
):
    """Test post_upgrade_sanity_checks with exception."""
    # the scenario: two ceph clouds, both with inconsistent running versions
    mock_analysis.apps_control_plane = [
        MagicMock(charm="ceph-mon", units={"first/0": MagicMock(name="first/0")}),
        MagicMock(charm="ceph-mon", units={"second/0": MagicMock(name="second/0")}),
    ]
    mock_get_versions.side_effect = [
        {
            "mon": {
                # hashes truncated for brevity in tests
                "ceph version 16.2.14 (238ba60) pacific (stable)": 2,
                "ceph version 16.2.15 (618f440) pacific (stable)": 1,
            },
            "osd": {
                "ceph version 15.2.17 (8a82819) octopus (stable)": 2,
                "ceph version 16.2.15 (618f440) pacific (stable)": 18,
            },
            "overall": {
                "ceph version 15.2.17 (8a82819) octopus (stable)": 2,
                "ceph version 16.2.14 (238ba60) pacific (stable)": 5,
                "ceph version 16.2.15 (618f440) pacific (stable)": 20,
            },
        },
        {
            "mon": {"ceph version 16.2.15 (618f440) pacific (stable)": 1},
            "osd": {
                "ceph version 15.2.17 (8a82819) octopus (stable)": 2,
                "ceph version 16.2.15 (618f440) pacific (stable)": 18,
            },
            "overall": {
                "ceph version 15.2.17 (8a82819) octopus (stable)": 2,
                "ceph version 16.2.15 (618f440) pacific (stable)": 20,
            },
        },
    ]

    await cou_plan.post_upgrade_sanity_checks(mock_analysis)

    assert mock_print_and_debug.call_count == 2
    assert "first" in mock_print_and_debug.call_args_list[0].args[0]
    assert "mismatched versions" in mock_print_and_debug.call_args_list[0].args[0]
    assert "pacific" in mock_print_and_debug.call_args_list[0].args[0]
    assert "second" in mock_print_and_debug.call_args_list[1].args[0]
    assert "mismatched versions" in mock_print_and_debug.call_args_list[1].args[0]
    assert "pacific" in mock_print_and_debug.call_args_list[1].args[0]


@pytest.mark.asyncio
@patch("cou.steps.plan.print_and_debug")
@patch("cou.steps.analyze.Analysis")
@patch("cou.steps.plan.ceph.assert_osd_noout_state", AsyncMock())
@patch("cou.steps.plan.ceph.get_versions", autospec=True)
async def test_post_upgrade_sanity_checks_ceph_mon_versions_consistent(
    mock_get_versions, mock_analysis, mock_print_and_debug
):
    """Test post_upgrade_sanity_checks with exception."""
    # the scenario: two ceph clouds, both with consistent running versions
    mock_analysis.apps_control_plane = [
        MagicMock(charm="ceph-mon", units={"first/0": MagicMock(name="first/0")}),
        MagicMock(charm="ceph-mon", units={"second/0": MagicMock(name="second/0")}),
    ]
    mock_get_versions.side_effect = [
        {
            "mon": {
                # hashes truncated for brevity in tests
                "ceph version 16.2.15 (618f440) pacific (stable)": 1,
            },
            "osd": {
                "ceph version 16.2.15 (618f440) pacific (stable)": 18,
            },
            "overall": {
                "ceph version 16.2.15 (618f440) pacific (stable)": 20,
            },
        },
        {
            "mon": {"ceph version 15.2.17 (8a82819) octopus (stable)": 1},
            "osd": {
                "ceph version 15.2.17 (8a82819) octopus (stable)": 2,
            },
            "overall": {
                "ceph version 15.2.17 (8a82819) octopus (stable)": 2,
            },
        },
    ]

    await cou_plan.post_upgrade_sanity_checks(mock_analysis)

    mock_print_and_debug.assert_not_called()
