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

from unittest.mock import MagicMock

import pytest

from cou.apps.app import OpenStackApplication
from cou.exceptions import HaltUpgradePlanGeneration, NoTargetError
from cou.steps import UpgradeStep
from cou.steps.analyze import Analysis
from cou.steps.backup import backup
from cou.steps.plan import create_upgrade_group, generate_plan
from cou.utils import app_utils
from cou.utils.openstack import OpenStackRelease
from tests.unit.apps.utils import add_steps


def generate_expected_upgrade_plan_principal(app, target, model):
    target_version = OpenStackRelease(target)
    expected_plan = UpgradeStep(
        description=f"Upgrade plan for '{app.name}' to {target_version.codename}",
        parallel=False,
        function=None,
    )
    upgrade_steps = [
        UpgradeStep(
            description=(
                f"Upgrade software packages of '{app.name}' from the current APT repositories"
            ),
            parallel=False,
            function=app_utils.upgrade_packages,
            units=app.units.keys(),
            model=model,
        ),
        UpgradeStep(
            description=(
                f"Refresh '{app.name}' to the latest revision of "
                f"'{target_version.previous_release}/stable'"
            ),
            parallel=False,
            function=model.upgrade_charm,
            application_name=app.name,
            channel=f"{target_version.previous_release}/stable",
            switch=None,
        ),
        UpgradeStep(
            description=f"Change charm config of '{app.name}' 'action-managed-upgrade' to False.",
            parallel=False,
            function=model.set_application_config,
            name=app.name,
            configuration={"action-managed-upgrade": False},
        ),
        UpgradeStep(
            description=(
                f"Upgrade '{app.name}' to the new channel: '{target_version.codename}/stable'"
            ),
            parallel=False,
            function=model.upgrade_charm,
            application_name=app.name,
            channel=f"{target_version.codename}/stable",
        ),
        UpgradeStep(
            description=(
                f"Change charm config of '{app.name}' "
                f"'{app.origin_setting}' to 'cloud:focal-{target_version.codename}'"
            ),
            parallel=False,
            function=model.set_application_config,
            name=app.name,
            configuration={f"{app.origin_setting}": f"cloud:focal-{target_version.codename}"},
        ),
        UpgradeStep(
            description=f"Check if the workload of '{app.name}' has been upgraded",
            parallel=False,
            function=app._check_upgrade,
            target=OpenStackRelease(target),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)
    return expected_plan


def generate_expected_upgrade_plan_subordinate(app, target, model):
    target_version = OpenStackRelease(target)
    expected_plan = UpgradeStep(
        description=f"Upgrade plan for '{app.name}' to {target}",
        parallel=False,
        function=None,
    )
    upgrade_steps = [
        UpgradeStep(
            description=(
                f"Refresh '{app.name}' to the latest revision of "
                f"'{target_version.previous_release}/stable'"
            ),
            parallel=False,
            function=model.upgrade_charm,
            application_name=app.name,
            channel=f"{target_version.previous_release}/stable",
            switch=None,
        ),
        UpgradeStep(
            description=(
                f"Upgrade '{app.name}' to the new channel: '{target_version.codename}/stable'"
            ),
            parallel=False,
            function=model.upgrade_charm,
            application_name=app.name,
            channel=f"{target_version.codename}/stable",
        ),
    ]
    add_steps(expected_plan, upgrade_steps)
    return expected_plan


@pytest.mark.asyncio
async def test_generate_plan(apps, model):
    target = "victoria"
    app_keystone = apps["keystone_ussuri"]
    app_cinder = apps["cinder_ussuri"]
    app_keystone_ldap = apps["keystone_ldap"]
    analysis_result = Analysis(
        model=model,
        apps_control_plane=[app_keystone, app_cinder, app_keystone_ldap],
        apps_data_plane=[],
    )

    upgrade_plan = await generate_plan(analysis_result)

    expected_plan = UpgradeStep(
        description="Top level plan",
        parallel=False,
        function=None,
    )

    expected_plan.add_step(
        UpgradeStep(
            description="backup mysql databases",
            parallel=False,
            function=backup,
        )
    )

    control_plane_principals = UpgradeStep(
        description="Control Plane principal(s) upgrade plan",
        parallel=False,
        function=None,
    )
    keystone_plan = generate_expected_upgrade_plan_principal(app_keystone, target, model)
    cinder_plan = generate_expected_upgrade_plan_principal(app_cinder, target, model)
    control_plane_principals.add_step(keystone_plan)
    control_plane_principals.add_step(cinder_plan)

    control_plane_subordinates = UpgradeStep(
        description="Control Plane subordinate(s) upgrade plan",
        parallel=False,
        function=None,
    )
    keystone_ldap_plan = generate_expected_upgrade_plan_subordinate(
        app_keystone_ldap, target, model
    )
    control_plane_subordinates.add_step(keystone_ldap_plan)

    expected_plan.add_step(control_plane_principals)
    expected_plan.add_step(control_plane_subordinates)
    assert upgrade_plan == expected_plan


@pytest.mark.asyncio
async def test_generate_plan_raise_NoTargetError(mocker):
    exp_error_msg = "Cannot find target to upgrade."
    analysis_result = MagicMock(spec=Analysis)
    analysis_result.current_cloud_os_release.next_release = None
    # not possible to determine target
    with pytest.raises(NoTargetError, match=exp_error_msg):
        await generate_plan(analysis_result)


@pytest.mark.asyncio
async def test_create_upgrade_plan():
    """Test create_upgrade_group."""
    app: OpenStackApplication = MagicMock(spec=OpenStackApplication)
    target = "victoria"
    description = "test"

    plan = await create_upgrade_group([app], target, description, lambda *_: True)

    assert plan.description == description
    assert plan.parallel is False
    assert plan.function is None
    assert len(plan.sub_steps) == 1
    assert plan.sub_steps[0] == app.generate_upgrade_plan.return_value
    app.generate_upgrade_plan.assert_called_once_with(target)


@pytest.mark.asyncio
async def test_create_upgrade_plan_HaltUpgradePlanGeneration():
    """Test create_upgrade_group."""
    app: OpenStackApplication = MagicMock(spec=OpenStackApplication)
    app.name = "test-app"
    app.generate_upgrade_plan.side_effect = HaltUpgradePlanGeneration
    target = "victoria"
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
