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

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cou.steps.execute import execute, prompt


@pytest.mark.asyncio
async def test_apply_plan_abort():
    upgrade_plan = AsyncMock()
    upgrade_plan.description = "Test Plan"

    with patch("cou.steps.execute.ainput") as mock_input:
        mock_input.return_value = "a"
        with pytest.raises(SystemExit):
            await execute(upgrade_plan, True)

        mock_input.assert_called_once_with(prompt("Test Plan"))
        upgrade_plan.function.assert_not_called()


@pytest.mark.asyncio
async def test_apply_plan_non_interactive(mocker):
    upgrade_plan = AsyncMock()
    upgrade_plan.description = "A"
    sub_step = AsyncMock()
    sub_step.description = "B is Sub step from A"
    sub_sub_step = AsyncMock()
    sub_sub_step.description = "C is Sub step from B"

    upgrade_plan.sub_steps = [sub_step]
    sub_step.sub_steps = [sub_sub_step]
    mock_input = mocker.patch("cou.steps.execute.input")
    mock_logger = mocker.patch("cou.steps.execute.logger")
    await execute(upgrade_plan, False)
    assert upgrade_plan.run.call_count == 1
    assert sub_step.run.call_count == 1
    assert sub_sub_step.run.call_count == 1
    assert mock_logger.info.call_count == 3
    mock_input.assert_not_called()


@pytest.mark.asyncio
async def test_apply_plan_continue():
    upgrade_plan = AsyncMock()
    upgrade_plan.description = "Test Plan"
    upgrade_plan.run = AsyncMock()
    sub_step = AsyncMock()
    sub_step.description = "Test Plan"
    upgrade_plan.sub_steps = [sub_step]

    with patch("cou.steps.execute.ainput") as mock_input, patch(
        "cou.steps.execute.sys"
    ) as mock_sys:
        mock_input.return_value = "C"
        await execute(upgrade_plan, True)

        mock_input.assert_called_with(prompt("Test Plan"))
        assert upgrade_plan.run.call_count == 1
        assert sub_step.run.call_count == 1
        mock_sys.exit.assert_not_called()


@pytest.mark.asyncio
async def test_apply_plan_nonsense():
    upgrade_plan = MagicMock()
    upgrade_plan.description = "Test Plan"

    with pytest.raises(SystemExit):
        with patch("cou.steps.execute.ainput") as mock_input, patch(
            "cou.steps.execute.logger.info"
        ) as log:
            mock_input.side_effect = ["x", "a"]
            await execute(upgrade_plan, True)

            log.assert_called_once_with("No valid input provided!")
            mock_input.assert_called_once_with(prompt("Test Plan"))
            upgrade_plan.function.assert_not_called()


@pytest.mark.asyncio
async def test_apply_plan_skip():
    upgrade_plan = MagicMock()
    upgrade_plan.description = "Test Plan"
    sub_step = MagicMock()
    sub_step.description = sub_step
    upgrade_plan.sub_steps = [sub_step]

    with patch("cou.steps.execute.ainput") as mock_input, patch(
        "cou.steps.execute.sys"
    ) as mock_sys:
        mock_input.return_value = "s"
        await execute(upgrade_plan, True)

        upgrade_plan.function.assert_not_called()
        mock_sys.exit.assert_not_called()
