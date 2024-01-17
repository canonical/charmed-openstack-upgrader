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
from cou.steps.analyze import Analysis
from cou.steps.backup import backup
from cou.steps.plan import (
    create_upgrade_group,
    determine_upgrade_target,
    generate_plan,
    is_control_plane_upgraded,
    manually_upgrade_data_plane,
    pre_plan_sanity_checks,
)
from cou.utils import app_utils
from cou.utils.openstack import OpenStackRelease
from tests.unit.apps.utils import add_steps


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
    app_keystone = apps["keystone_ussuri"]
    app_cinder = apps["cinder_ussuri"]
    app_keystone_ldap = apps["keystone_ldap"]
    analysis_result = Analysis(
        model=model,
        apps_control_plane=[app_keystone, app_cinder, app_keystone_ldap],
        apps_data_plane=[],
    )

    upgrade_plan = await generate_plan(analysis_result, cli_args)

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
@patch("cou.steps.plan.is_data_plane_ready_to_upgrade")
def test_pre_plan_sanity_checks(
    mock_is_data_plane_ready_to_upgrade, is_data_plane_command, expected_call, cli_args
):
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.current_cloud_os_release = OpenStackRelease("ussuri")
    mock_analysis_result.current_cloud_series = "focal"
    cli_args.is_data_plane_command = is_data_plane_command
    pre_plan_sanity_checks(cli_args, mock_analysis_result)
    if expected_call:
        mock_is_data_plane_ready_to_upgrade.assert_called_once_with(mock_analysis_result)
    else:
        mock_is_data_plane_ready_to_upgrade.assert_not_called()


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
def test_pre_plan_sanity_checks_is_valid_openstack_cloud(
    current_os_release, current_series, exp_error_msg, cli_args
):
    with pytest.raises(NoTargetError, match=exp_error_msg):
        mock_analysis_result = MagicMock(spec=Analysis)()
        mock_analysis_result.current_cloud_series = current_series
        mock_analysis_result.current_cloud_os_release = current_os_release
        pre_plan_sanity_checks(cli_args, mock_analysis_result)


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
def test_pre_plan_sanity_checks_is_supported_series(
    current_os_release, current_series, exp_error_msg, cli_args
):
    mock_analysis_result = MagicMock(spec=Analysis)()
    with pytest.raises(OutOfSupportRange, match=exp_error_msg):
        mock_analysis_result.current_cloud_os_release = current_os_release
        mock_analysis_result.current_cloud_series = current_series
        pre_plan_sanity_checks(cli_args, mock_analysis_result)


def test_pre_plan_sanity_checks_is_highest_release_achieved(cli_args):
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.current_cloud_os_release = OpenStackRelease("yoga")
    mock_analysis_result.current_cloud_series = "focal"
    exp_error_msg = (
        "No upgrades available for OpenStack Yoga on Ubuntu Focal.\n"
        "Newer OpenStack releases may be available after upgrading to a later Ubuntu series."
    )
    with pytest.raises(HighestReleaseAchieved, match=exp_error_msg):
        pre_plan_sanity_checks(cli_args, mock_analysis_result)


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
def test_pre_plan_sanity_checks_is_data_plane_ready_to_upgrade_error(
    min_os_version_control_plane, min_os_version_data_plane, exp_error_msg, cli_args
):
    cli_args.upgrade_group = "data-plane"
    mock_analysis_result = MagicMock(spec=Analysis)()
    mock_analysis_result.current_cloud_series = "focal"
    mock_analysis_result.min_os_version_control_plane = min_os_version_control_plane
    mock_analysis_result.min_os_version_data_plane = min_os_version_data_plane
    with pytest.raises(DataPlaneCannotUpgrade, match=exp_error_msg):
        pre_plan_sanity_checks(cli_args, mock_analysis_result)


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
    assert is_control_plane_upgraded(mock_analysis_result) is expected_result


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

    target = determine_upgrade_target(mock_analysis_result)

    assert target == next_release


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
        determine_upgrade_target(mock_analysis_result)


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
        determine_upgrade_target(mock_analysis_result)


@pytest.mark.asyncio
async def test_create_upgrade_plan():
    """Test create_upgrade_group."""
    app: OpenStackApplication = MagicMock(spec=OpenStackApplication)
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
def test_plan_print_warn_manually_upgrade(mock_print, model, apps):
    result = Analysis(
        model=model,
        apps_control_plane=[apps["keystone_wallaby"]],
        apps_data_plane=[apps["nova_ussuri"]],
    )
    manually_upgrade_data_plane(result)
    mock_print.assert_called_with(
        "WARNING: Please upgrade manually the data plane apps: nova-compute"
    )


@patch("builtins.print")
def test_analysis_not_print_warn_manually_upgrade(mock_print, model, apps):
    result = Analysis(
        model=model,
        apps_control_plane=[apps["keystone_ussuri"]],
        apps_data_plane=[apps["nova_ussuri"]],
    )
    manually_upgrade_data_plane(result)
    mock_print.assert_not_called()
