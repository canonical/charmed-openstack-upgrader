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

import pytest

import cou.utils.juju_utils as model
from cou.exceptions import HaltUpgradePlanGeneration, NoTargetError
from cou.steps.analyze import Analysis
from cou.steps.backup import backup
from cou.steps.plan import generate_plan
from cou.utils.openstack import OpenStackRelease


@pytest.mark.asyncio
async def test_generate_plan(mocker, apps):
    target = "victoria"
    app_keystone = apps["keystone_ussuri"]
    app_cinder = apps["cinder_ussuri"]
    analysis_result = Analysis(apps=[app_keystone, app_cinder])
    mocker.patch.object(model, "async_set_current_model_name", return_value="my_model")
    plan = await generate_plan(analysis_result)

    assert plan.description == "Top level plan"
    assert not plan.parallel
    assert not plan.function
    assert len(plan.sub_steps) == 2

    sub_step_back_up = plan.sub_steps[0]
    assert sub_step_back_up.description == "backup mysql databases"
    assert not sub_step_back_up.parallel
    assert sub_step_back_up.function == backup

    sub_step_upgrade_plan = plan.sub_steps[1]
    assert sub_step_upgrade_plan.description == "Application(s) upgrade plan"

    sub_step_upgrade_keystone = sub_step_upgrade_plan.sub_steps[0]
    assert (
        sub_step_upgrade_keystone.description
        == "Upgrade plan for 'keystone' from: ussuri to victoria"
    )
    expected_description_upgrade_keystone = generate_expected_upgrade_plan_description(
        app_keystone, target
    )
    assert_plan_description(sub_step_upgrade_keystone, expected_description_upgrade_keystone)

    sub_step_upgrade_cinder = sub_step_upgrade_plan.sub_steps[1]
    assert (
        sub_step_upgrade_cinder.description == "Upgrade plan for 'cinder' from: ussuri to victoria"
    )
    expected_description_upgrade_cinder = generate_expected_upgrade_plan_description(
        app_cinder, target
    )
    assert_plan_description(sub_step_upgrade_cinder, expected_description_upgrade_cinder)


@pytest.mark.asyncio
async def test_generate_plan_raise_NoTargetError(mocker):
    analysis_result = mocker.MagicMock()
    analysis_result.current_cloud_os_release.next_release = None
    # not possible to determine target
    with pytest.raises(NoTargetError):
        await generate_plan(analysis_result)


@pytest.mark.asyncio
async def test_generate_plan_raise_HaltUpgradePlanGeneration(mocker):
    mock_logger = mocker.patch("cou.steps.plan.logger")
    app = mocker.MagicMock()
    app.generate_upgrade_plan.side_effect = HaltUpgradePlanGeneration
    analysis_result = Analysis(apps=[app])
    upgrade_plan = await generate_plan(analysis_result)
    mock_logger.debug.assert_called_once()
    assert upgrade_plan is not None


@pytest.mark.asyncio
async def test_generate_plan_raise_Exception(mocker):
    mock_logger = mocker.patch("cou.steps.plan.logger")
    app = mocker.MagicMock()
    app.generate_upgrade_plan.side_effect = Exception("An error occurred")
    # Generate an exception during the upgrade plan
    analysis_result = Analysis(apps=[app])
    with pytest.raises(Exception):
        await generate_plan(analysis_result)
    mock_logger.error.assert_called_once()


def generate_expected_upgrade_plan_description(charm, target):
    target_version = OpenStackRelease(target)
    return [
        f"Upgrade software packages of '{charm.name}' to the latest "
        f"in '{charm.current_os_release}' release",
        f"Refresh '{charm.name}' to the latest revision of '{charm.expected_current_channel}'",
        f"Change charm config of '{charm.name}' 'action-managed-upgrade' to False.",
        f"Upgrade '{charm.name}' to the new channel: '{charm.target_channel(target_version)}'",
        (
            f"Change charm config of '{charm.name}' "
            f"'{charm.origin_setting}' to '{charm.new_origin(target_version)}'"
        ),
        f"Check if the workload of '{charm.name}' has been upgraded",
    ]


def assert_plan_description(upgrade_plan, steps_description):
    assert len(upgrade_plan.sub_steps) == len(steps_description)
    sub_steps_check = zip(upgrade_plan.sub_steps, steps_description)
    for sub_step, description in sub_steps_check:
        assert sub_step.description == description
