# Copyright 2023 Canonical Limited.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from cou.steps.backup import backup
from cou.steps.plan import apply_plan, dump_plan, generate_plan, prompt


def test_generate_plan():
    args = MagicMock()
    plan = generate_plan(args)

    assert plan.description == "Top level plan"
    assert not plan.parallel
    assert not plan.function
    assert len(plan.sub_steps) == 1

    sub_step = plan.sub_steps[0]
    assert sub_step.description == "backup mysql databases"
    assert not sub_step.parallel
    assert sub_step.function == backup


@pytest.mark.asyncio
async def test_apply_plan_continue():
    upgrade_plan = AsyncMock()
    upgrade_plan.description = "Test Plan"
    upgrade_plan.run = AsyncMock()
    sub_step = AsyncMock()
    sub_step.description = "Test Plan"
    upgrade_plan.sub_steps = [sub_step]

    with patch("cou.steps.plan.input") as mock_input, patch("cou.steps.plan.sys") as mock_sys:
        mock_input.return_value = "C"
        await apply_plan(upgrade_plan)

        mock_input.assert_called_with(prompt("Test Plan"))
        assert upgrade_plan.run.call_count == 1
        assert sub_step.run.call_count == 1
        mock_sys.exit.assert_not_called()


@pytest.mark.asyncio
async def test_apply_plan_abort():
    upgrade_plan = AsyncMock()
    upgrade_plan.description = "Test Plan"

    with patch("cou.steps.plan.input") as mock_input:
        mock_input.return_value = "a"
        with pytest.raises(SystemExit):
            await apply_plan(upgrade_plan)

        mock_input.assert_called_once_with(prompt("Test Plan"))
        upgrade_plan.function.assert_not_called()


@pytest.mark.asyncio
async def test_apply_plan_nonsense():
    upgrade_plan = MagicMock()
    upgrade_plan.description = "Test Plan"

    with pytest.raises(SystemExit):
        with patch("cou.steps.plan.input") as mock_input, patch(
            "cou.steps.plan.logging.info"
        ) as log:
            mock_input.side_effect = ["x", "a"]
            await apply_plan(upgrade_plan)

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

    with patch("cou.steps.plan.input") as mock_input, patch("cou.steps.plan.sys") as mock_sys:
        mock_input.return_value = "s"
        await apply_plan(upgrade_plan)

        upgrade_plan.function.assert_not_called()
        mock_sys.exit.assert_not_called()


def test_dump_plan():
    upgrade_plan = MagicMock()
    upgrade_plan.description = "Test Plan"
    sub_step = MagicMock()
    sub_step.description = "Sub Step"
    sub_step.sub_steps = []
    upgrade_plan.sub_steps = [sub_step]

    with patch("cou.steps.plan.logging.info") as mock_print:
        dump_plan(upgrade_plan)

        mock_print.assert_has_calls([call("Test Plan"), call("\tSub Step")])
        mock_print.call_count = 2
