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

import cou.utils.juju_utils as model
from cou.steps.backup import backup
from cou.steps.plan import generate_plan


@pytest.mark.asyncio
async def test_generate_plan(mocker):
    args = MagicMock()
    mocker.patch.object(model, "async_set_current_model_name", return_value="my_model")
    plan = await generate_plan(args)

    assert plan.description == "Top level plan"
    assert not plan.parallel
    assert not plan.function
    assert len(plan.sub_steps) == 1

    sub_step = plan.sub_steps[0]
    assert sub_step.description == "backup mysql databases"
    assert not sub_step.parallel
    assert sub_step.function == backup
