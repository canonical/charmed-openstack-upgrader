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
from cou.apps.subordinate import SubordinateApplication
from cou.exceptions import (
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
from cou.steps.analyze import Analysis
from cou.steps.backup import backup
from cou.steps.plan import (
    create_upgrade_group,
    determine_upgrade_target,
    generate_plan,
    manually_upgrade_data_plane,
)
from cou.utils import app_utils
from cou.utils.juju_utils import Machine, Unit
from cou.utils.openstack import OpenStackRelease
from tests.unit.utils import assert_steps


def generate_expected_upgrade_plan_principal(app, target, model):
    expected_plan = ApplicationUpgradePlan(f"Upgrade plan for '{app.name}' to '{target.codename}'")
    if app.charm in ["rabbitmq-server", "ceph-mon", "keystone"]:
        # apps waiting for whole model
        wait_step = PostUpgradeStep(
            description=f"Wait for up to 1800s for model '{model.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_active_idle(1800, apps=None),
        )
    else:
        wait_step = PostUpgradeStep(
            description=f"Wait for up to 300s for app '{app.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_active_idle(300, apps=[app.name]),
        )

    upgrade_packages = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    upgrade_packages.add_steps(
        UnitUpgradeStep(
            description=f"Upgrade software packages on unit {unit.name}",
            coro=app_utils.upgrade_packages(unit.name, model, None),
        )
        for unit in app.units.values()
    )

    upgrade_steps = [
        upgrade_packages,
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of "
            f"'{target.previous_release}/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, f"{target.previous_release}/stable", switch=None),
        ),
        UpgradeStep(
            description=f"Change charm config of '{app.name}' 'action-managed-upgrade' to 'False'",
            parallel=False,
            coro=model.set_application_config(app.name, {"action-managed-upgrade": False}),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: '{target.codename}/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, f"{target.codename}/stable"),
        ),
        UpgradeStep(
            description=f"Change charm config of '{app.name}' "
            f"'{app.origin_setting}' to 'cloud:focal-{target.codename}'",
            parallel=False,
            coro=model.set_application_config(
                app.name, {f"{app.origin_setting}": f"cloud:focal-{target.codename}"}
            ),
        ),
        wait_step,
        PostUpgradeStep(
            description=f"Verify that the workload of '{app.name}' has been upgraded",
            parallel=False,
            coro=app._check_upgrade(target),
        ),
    ]
    expected_plan.add_steps(upgrade_steps)
    return expected_plan


def generate_expected_upgrade_plan_subordinate(app, target, model):
    expected_plan = ApplicationUpgradePlan(f"Upgrade plan for '{app.name}' to '{target}'")
    upgrade_steps = [
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of "
            f"'{target.previous_release}/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, f"{target.previous_release}/stable", switch=None),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: '{target.codename}/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, f"{target.codename}/stable"),
        ),
    ]
    expected_plan.add_steps(upgrade_steps)
    return expected_plan


@pytest.mark.asyncio
async def test_generate_plan(model, cli_args):
    """Test generation of upgrade plan."""
    cli_args.is_data_plane_command = False
    target = OpenStackRelease("victoria")
    # keystone = Keystone()
    machines = {"0": MagicMock(spec_set=Machine)}
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
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=["nova-compute"],
        units={},
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
            "cinder/0": Unit(
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
            description="Back up MySQL databases",
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

    upgrade_plan = await generate_plan(analysis_result, cli_args)
    assert_steps(upgrade_plan, expected_plan)


@pytest.mark.parametrize(
    "current_os_release, current_series, next_release",
    [
        (OpenStackRelease("victoria"), "focal", "wallaby"),
        (OpenStackRelease("xena"), "focal", "yoga"),
    ],
)
def test_determine_upgrade_target(current_os_release, current_series, next_release):
    target = determine_upgrade_target(current_os_release, current_series)

    assert target == next_release


def test_determine_upgrade_target_no_upgrade_available():
    current_os_release = OpenStackRelease("yoga")
    current_series = "focal"
    with pytest.raises(HighestReleaseAchieved):
        determine_upgrade_target(current_os_release, current_series)


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
def test_determine_upgrade_target_invalid_input(current_os_release, current_series, exp_error_msg):
    with pytest.raises(NoTargetError, match=exp_error_msg):
        determine_upgrade_target(current_os_release, current_series)


def test_determine_upgrade_target_no_next_release():
    exp_error_msg = "Cannot find target to upgrade. Current minimum OS release is "
    "'ussuri'. Current Ubuntu series is 'focal'."
    current_series = "focal"

    with pytest.raises(NoTargetError, match=exp_error_msg), patch(
        "cou.utils.openstack.OpenStackRelease.next_release", new_callable=PropertyMock
    ) as mock_next_release:
        mock_next_release.return_value = None
        current_os_release = OpenStackRelease(
            "ussuri"
        )  # instantiate OpenStackRelease with any valid codename
        determine_upgrade_target(current_os_release, current_series)


@pytest.mark.parametrize(
    "current_os_release, current_series",
    [
        (OpenStackRelease("yoga"), "jammy"),
        (OpenStackRelease("train"), "bionic"),
        (OpenStackRelease("zed"), "focal"),
    ],
)
def test_determine_upgrade_target_release_out_of_range(current_os_release, current_series):
    with pytest.raises(OutOfSupportRange):
        determine_upgrade_target(current_os_release, current_series)


@pytest.mark.asyncio
async def test_create_upgrade_plan():
    """Test create_upgrade_group."""
    app: OpenStackApplication = MagicMock(spec_set=OpenStackApplication)
    app.generate_upgrade_plan.return_value = MagicMock(spec_set=ApplicationUpgradePlan)
    target = OpenStackRelease("victoria")
    description = "test"

    plan = await create_upgrade_group([app], target, description, lambda *_: True)

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

    plan = await create_upgrade_group([app], target, description, lambda *_: True)

    assert len(plan.sub_steps) == 0
    app.generate_upgrade_plan.assert_called_once_with(target)


@pytest.mark.asyncio
async def test_create_upgrade_plan_failed():
    """Test create_upgrade_group."""
    app: OpenStackApplication = MagicMock(spec=OpenStackApplication)
    app.name = "test-app"
    app.generate_upgrade_plan.side_effect = Exception("test")

    with pytest.raises(Exception, match="test"):
        await create_upgrade_group([app], "victoria", "test", lambda *_: True)


@patch("builtins.print")
def test_plan_print_warn_manually_upgrade(mock_print, model):
    nova_compute = MagicMock(spec_set=OpenStackApplication)()
    nova_compute.name = "nova-compute"
    nova_compute.current_os_release = OpenStackRelease("victoria")
    nova_compute.series = "focal"
    keystone = MagicMock(spec_set=OpenStackApplication)()
    keystone.name = "keystone"
    keystone.current_os_release = OpenStackRelease("wallaby")
    keystone.series = "focal"

    result = Analysis(
        model=model,
        apps_control_plane=[keystone],
        apps_data_plane=[nova_compute],
    )
    manually_upgrade_data_plane(result)
    mock_print.assert_called_with(
        f"WARNING: Please upgrade manually the data plane apps: {nova_compute.name}"
    )


@patch("builtins.print")
def test_analysis_not_print_warn_manually_upgrade(mock_print, model):
    keystone = MagicMock(spec_set=OpenStackApplication)()
    keystone.name = "keystone"
    keystone.current_os_release = OpenStackRelease("wallaby")
    keystone.series = "focal"

    result = Analysis(
        model=model,
        apps_control_plane=[keystone],
        apps_data_plane=[],
    )
    manually_upgrade_data_plane(result)
    mock_print.assert_not_called()
