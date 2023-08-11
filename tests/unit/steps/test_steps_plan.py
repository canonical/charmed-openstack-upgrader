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
from cou.steps.analyze import Analysis
from cou.steps.backup import backup
from cou.steps.plan import generate_plan


@pytest.mark.asyncio
async def test_generate_plan(mocker, apps):
    app_keystone = apps["keystone_ussuri"]
    app_cinder = apps["cinder_ussuri"]
    analysis_result = Analysis(apps=[app_keystone, app_cinder])
    mocker.patch.object(model, "async_set_current_model_name", return_value="my_model")
    plan = await generate_plan(analysis_result)

    assert plan.description == "Top level plan"
    assert not plan.parallel
    assert not plan.function
    assert len(plan.sub_steps) == 3

    sub_step_back_up = plan.sub_steps[0]
    assert sub_step_back_up.description == "backup mysql databases"
    assert not sub_step_back_up.parallel
    assert sub_step_back_up.function == backup

    sub_step_upgrade_keystone = plan.sub_steps[1]
    assert (
        sub_step_upgrade_keystone.description
        == "Upgrade plan for 'keystone' from: ussuri to victoria"
    )
    expected_description_upgrade_keystone = generate_expected_upgrade_plan_description(
        app_keystone
    )
    assert_plan_description(sub_step_upgrade_keystone, expected_description_upgrade_keystone)

    sub_step_upgrade_cinder = plan.sub_steps[2]
    assert (
        sub_step_upgrade_cinder.description == "Upgrade plan for 'cinder' from: ussuri to victoria"
    )
    expected_description_upgrade_cinder = generate_expected_upgrade_plan_description(app_cinder)
    assert_plan_description(sub_step_upgrade_cinder, expected_description_upgrade_cinder)


def generate_expected_upgrade_plan_description(charm):
    return [
        f"Refresh '{charm.name}' to the latest revision of '{charm.expected_current_channel}'",
        f"Change charm config of '{charm.name}' 'action-managed-upgrade' to False.",
        f"Refresh '{charm.name}' to the new channel: '{charm.next_channel}'",
        f"Change charm config of '{charm.name}' '{charm.origin_setting}' to '{charm.new_origin}'",
        f"Check if workload of '{charm.name}' has upgraded",
    ]


def assert_plan_description(upgrade_plan, steps_description):
    assert len(upgrade_plan.sub_steps) == len(steps_description)
    sub_steps_check = zip(upgrade_plan.sub_steps, steps_description)
    for sub_step, description in sub_steps_check:
        assert sub_step.description == description
