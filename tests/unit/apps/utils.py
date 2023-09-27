#  Copyright 2023 Canonical Limited
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.


def assert_plan_description(upgrade_plan, steps_description):
    assert len(upgrade_plan.sub_steps) == len(steps_description)
    sub_steps_check = zip(upgrade_plan.sub_steps, steps_description)
    for sub_step, description in sub_steps_check:
        assert sub_step.description == description


def assert_plan(upgrade_plan, expected_plan):
    assert len(upgrade_plan.sub_steps) == len(expected_plan)
    sub_steps_check = zip(upgrade_plan.sub_steps, expected_plan)
    for sub_step, expected_step in sub_steps_check:
        assert sub_step.description == expected_step["description"]
        assert sub_step.function == expected_step["function"]
        assert sub_step.params == expected_step["params"]
