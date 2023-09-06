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

from unittest.mock import AsyncMock, call, patch

import pytest

from cou.steps import UpgradeStep
from cou.steps.execute import apply_plan, prompt


@pytest.mark.asyncio
@patch("cou.steps.execute.ainput")
@patch("cou.steps.execute._run_step")
async def test_apply_plan_abort(mock_run_step, mock_input):
    upgrade_plan = AsyncMock(spec=UpgradeStep)
    upgrade_plan.description = "Test Plan"
    mock_input.return_value = "a"

    with pytest.raises(SystemExit):
        await apply_plan(upgrade_plan, True)

    mock_input.assert_called_once_with(prompt("Test Plan"))
    mock_run_step.assert_not_awaited()


@pytest.mark.asyncio
@patch("cou.steps.execute.ainput")
@patch("cou.steps.execute._run_step")
async def test_apply_plan_non_interactive(mock_run_step, mock_input):
    upgrade_plan = AsyncMock(spec=UpgradeStep)
    upgrade_plan.description = "Test Plan"

    await apply_plan(upgrade_plan, False)

    mock_input.assert_not_awaited()
    mock_run_step.assert_awaited_once_with(upgrade_plan, False)


@pytest.mark.asyncio
@patch("cou.steps.execute.ainput")
@patch("cou.steps.execute._run_step")
async def test_apply_plan_continue(mock_run_step, mock_input):
    upgrade_plan = AsyncMock(spec=UpgradeStep)
    upgrade_plan.description = "Test Plan"
    mock_input.return_value = "C"

    await apply_plan(upgrade_plan, True)

    mock_input.assert_awaited_once_with(prompt("Test Plan"))
    mock_run_step.assert_awaited_once_with(upgrade_plan, True)


@pytest.mark.asyncio
@patch("cou.steps.execute.ainput")
@patch("cou.steps.execute._run_step")
async def test_apply_plan_nonsense(mock_run_step, mock_input):
    upgrade_plan = AsyncMock(spec=UpgradeStep)
    upgrade_plan.description = "Test Plan"
    mock_input.side_effect = ["x", "a"]

    with pytest.raises(SystemExit, match="1"):
        await apply_plan(upgrade_plan, True)

    mock_input.assert_has_awaits([call(prompt("Test Plan")), call(prompt("Test Plan"))])
    mock_run_step.assert_not_awaited()


@pytest.mark.asyncio
@patch("cou.steps.execute.ainput")
@patch("cou.steps.execute._run_step")
async def test_apply_plan_skip(mock_run_step, mock_input):
    upgrade_plan = AsyncMock(spec=UpgradeStep)
    upgrade_plan.description = "Test Plan"
    mock_input.return_value = "s"

    await apply_plan(upgrade_plan, True)

    mock_input.assert_awaited_once_with(prompt("Test Plan"))
    mock_run_step.assert_not_awaited()
