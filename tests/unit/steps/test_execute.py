#  Copyright 2023 Canonical Limited.
#  #
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
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
