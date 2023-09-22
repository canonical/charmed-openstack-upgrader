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
from cou.steps.analyze import Analysis
from cou.steps.backup import backup
from cou.steps.plan import create_upgrade_group, generate_plan
from cou.utils.openstack import OpenStackRelease


def assert_plan_description(upgrade_plan, steps_description):
    assert len(upgrade_plan.sub_steps) == len(steps_description)
    sub_steps_check = zip(upgrade_plan.sub_steps, steps_description)
    for sub_step, description in sub_steps_check:
        assert sub_step.description == description


def generate_expected_upgrade_plan_description(charm, target):
    target_version = OpenStackRelease(target)
    return [
        f"Upgrade software packages of '{charm.name}' from the current APT repositories",
        f"Refresh '{charm.name}' to the latest revision of '{charm.expected_current_channel}'",
        f"Change charm config of '{charm.name}' 'action-managed-upgrade' to False.",
        f"Upgrade '{charm.name}' to the new channel: '{charm.target_channel(target_version)}'",
        (
            f"Change charm config of '{charm.name}' "
            f"'{charm.origin_setting}' to '{charm.new_origin(target_version)}'"
        ),
        f"Check if the workload of '{charm.name}' has been upgraded",
    ]


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

    plan = await generate_plan(analysis_result)

    assert plan.description == "Top level plan"
    assert not plan.parallel
    assert not plan.function
    assert len(plan.sub_steps) == 3

    sub_step_back_up = plan.sub_steps[0]
    assert sub_step_back_up.description == "backup mysql databases"
    assert not sub_step_back_up.parallel
    assert sub_step_back_up.function == backup

    sub_step_upgrade_plan = plan.sub_steps[1]
    assert sub_step_upgrade_plan.description == "Control Plane principal(s) upgrade plan"

    sub_step_upgrade_keystone = sub_step_upgrade_plan.sub_steps[0]
    assert sub_step_upgrade_keystone.description == "Upgrade plan for 'keystone' to victoria"
    expected_description_upgrade_keystone = generate_expected_upgrade_plan_description(
        app_keystone, target
    )
    assert_plan_description(sub_step_upgrade_keystone, expected_description_upgrade_keystone)

    sub_step_upgrade_cinder = sub_step_upgrade_plan.sub_steps[1]
    assert sub_step_upgrade_cinder.description == "Upgrade plan for 'cinder' to victoria"
    expected_description_upgrade_cinder = generate_expected_upgrade_plan_description(
        app_cinder, target
    )
    assert_plan_description(sub_step_upgrade_cinder, expected_description_upgrade_cinder)

    subordinate_plan = plan.sub_steps[2]
    assert subordinate_plan.description == "Control Plane subordinate(s) upgrade plan"
    assert (
        subordinate_plan.sub_steps[0].description == "Upgrade plan for 'keystone-ldap' to victoria"
    )


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
