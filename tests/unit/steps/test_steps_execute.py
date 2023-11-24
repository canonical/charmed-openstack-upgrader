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

import asyncio
import unittest
from random import randint
from textwrap import dedent
from unittest.mock import AsyncMock, call, patch

import pytest

from cou.steps import (
    ApplicationUpgradePlan,
    PostUpgradeStep,
    PreUpgradeStep,
    UpgradePlan,
    UpgradeStep,
)
from cou.steps.execute import _run_step, apply_step, prompt


@pytest.mark.asyncio
@patch("cou.steps.execute.apply_step")
async def test_run_step_sequentially(mock_apply_step):
    """Test running step and all sub-steps sequentially."""
    upgrade_step = AsyncMock(spec_set=UpgradeStep())
    upgrade_step.parallel = False
    upgrade_step.sub_steps = sub_steps = [
        AsyncMock(spec_set=PreUpgradeStep()),
        AsyncMock(spec_set=UpgradeStep()),
        AsyncMock(spec_set=PostUpgradeStep()),
    ]

    await _run_step(upgrade_step, False)

    upgrade_step.run.assert_awaited_once_with()
    mock_apply_step.assert_has_awaits([call(sub_step, False) for sub_step in sub_steps])


@pytest.mark.asyncio
@patch("cou.steps.execute.apply_step")
async def test_run_step_in_parallel(mock_apply_step):
    """Test running step and all sub-steps in parallel."""
    upgrade_step = AsyncMock(spec_set=UpgradeStep())
    upgrade_step.parallel = True
    upgrade_step.sub_steps = sub_steps = [
        AsyncMock(spec_set=PreUpgradeStep()),
        AsyncMock(spec_set=UpgradeStep()),
        AsyncMock(spec_set=PostUpgradeStep()),
    ]

    await _run_step(upgrade_step, False)

    upgrade_step.run.assert_awaited_once_with()
    mock_apply_step.assert_has_awaits([call(step, False) for step in sub_steps])


@pytest.mark.asyncio
@pytest.mark.parametrize("step", [UpgradeStep, PreUpgradeStep, PostUpgradeStep])
@patch("cou.steps.execute.progress_indicator")
async def test_run_step_with_progress_indicator(mock_progress_indicator, step):
    upgrade_step = AsyncMock(spec=step())
    await _run_step(upgrade_step, False)
    mock_progress_indicator.start.assert_called_once()
    mock_progress_indicator.succeed.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("plan", [UpgradePlan, ApplicationUpgradePlan])
@patch("cou.steps.execute.progress_indicator")
async def test_run_step_no_progress_indicator(mock_progress_indicator, plan):
    upgrade_plan = AsyncMock(spec_set=plan("Test plan"))
    await _run_step(upgrade_plan, False)
    mock_progress_indicator.start.assert_not_called()
    mock_progress_indicator.succeed.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("input_value", ["n", "N"])
@patch("cou.steps.execute.ainput")
@patch("cou.steps.execute._run_step")
async def test_apply_step_abort(mock_run_step, mock_input, input_value):
    upgrade_step = AsyncMock(spec_set=UpgradeStep())
    upgrade_step.description = "Test Step"
    mock_input.return_value = input_value

    with pytest.raises(SystemExit):
        await apply_step(upgrade_step, True)

    mock_input.assert_awaited_once_with(prompt("Test Step "))
    mock_run_step.assert_not_awaited()


@pytest.mark.asyncio
@patch("cou.steps.execute.ainput")
@patch("cou.steps.execute._run_step")
async def test_apply_step_non_interactive(mock_run_step, mock_input):
    upgrade_step = AsyncMock(spec_set=UpgradeStep())
    upgrade_step.description = "Test Step"

    await apply_step(upgrade_step, False)

    mock_input.assert_not_awaited()
    mock_run_step.assert_awaited_once_with(upgrade_step, False)


@pytest.mark.asyncio
@pytest.mark.parametrize("input_value", ["y", "Y"])
@patch("cou.steps.execute.ainput")
@patch("cou.steps.execute._run_step")
async def test_apply_step_continue(mock_run_step, mock_input, input_value):
    upgrade_step = AsyncMock(spec_set=UpgradeStep())
    upgrade_step.description = "Test Step"
    mock_input.return_value = input_value

    await apply_step(upgrade_step, True)

    mock_input.assert_awaited_once_with(prompt("Test Step "))
    mock_run_step.assert_awaited_once_with(upgrade_step, True)


@pytest.mark.asyncio
@patch("cou.steps.execute.ainput")
@patch("cou.steps.execute._run_step")
async def test_apply_step_nonsense(mock_run_step, mock_input):
    upgrade_step = AsyncMock(spec_set=UpgradeStep())
    upgrade_step.description = "Test Step"
    mock_input.side_effect = ["x", "n"]

    with pytest.raises(SystemExit, match="1"):
        await apply_step(upgrade_step, True)

    mock_input.assert_has_awaits([call(prompt("Test Step ")), call(prompt("Test Step "))])
    mock_run_step.assert_not_awaited()


@pytest.mark.asyncio
@patch("cou.steps.execute.ainput")
@patch("cou.steps.execute._run_step")
async def test_apply_application_upgrade_plan(mock_run_step, mock_input):
    expected_prompt = (
        "Test plan\n\t[pre-upgrade] Test pre-upgrade step\n\t[upgrade] Test upgrade step\n\t"
        + "[post-upgrade] Test post-upgrade step\n\n"
    )
    upgrade_plan = ApplicationUpgradePlan("Test plan")
    upgrade_plan.sub_steps = [
        PreUpgradeStep(description="Test pre-upgrade step", coro=AsyncMock()),
        UpgradeStep(description="Test upgrade step", coro=AsyncMock()),
        PostUpgradeStep(description="Test post-upgrade step", coro=AsyncMock()),
    ]

    mock_input.side_effect = ["y"]
    await apply_step(upgrade_plan, True)

    mock_input.assert_has_awaits([call(prompt(expected_prompt))])


@pytest.mark.asyncio
@patch(("cou.steps.execute.print"))
@patch("cou.steps.execute.ainput")
@patch("cou.steps.execute._run_step")
async def test_apply_application_upgrade_plan_non_interactive(
    mock_run_step, mock_input, mock_print
):
    plan_description = "Test plan"
    upgrade_plan = ApplicationUpgradePlan(plan_description)
    upgrade_plan.sub_steps = [
        PreUpgradeStep(description="Test pre-upgrade step", coro=AsyncMock()),
        UpgradeStep(description="Test upgrade step", coro=AsyncMock()),
        PostUpgradeStep(description="Test post-upgrade step", coro=AsyncMock()),
    ]

    await apply_step(upgrade_plan, False)

    mock_print.assert_called_once_with(plan_description)
    mock_input.assert_not_awaited()


@pytest.mark.asyncio
@patch("cou.steps.execute.ainput")
async def test_apply_empty_step(mock_input):
    # upgrade_plan is empty because it has neither coro nor sub-steps
    upgrade_plan = ApplicationUpgradePlan("Test plan")

    await apply_step(upgrade_plan, True)

    mock_input.assert_not_awaited()


class TestFullApplyPlan(unittest.IsolatedAsyncioTestCase):
    """Simulate real world scenario for better coverage.

    This tests will create plan with parallel and sequential, where each of these
    step will have sequential sub-step.
    """

    async def asyncSetUp(self) -> None:
        self.execution_order = []
        self.addCleanup(self.execution_order.clear)  # clean all results

        async def append(name: str) -> None:
            await asyncio.sleep(randint(10, 200) / 1000)  # wait randomly between 10ms and 200ms
            self.execution_order.append(name)

        self.plan = UpgradePlan("test plan")
        # define parallel step
        parallel_step = UpgradeStep("parallel", parallel=True, coro=append("parallel"))
        for i in range(5):
            sub_step = UpgradeStep(f"parallel.{i}", parallel=False, coro=append(f"parallel.{i}"))
            for j in range(3):
                sub_step.add_step(
                    UpgradeStep(
                        f"parallel.{i}.{j}",
                        parallel=False,
                        coro=append(f"parallel.{i}.{j}"),
                    )
                )

            parallel_step.add_step(sub_step)
        self.plan.add_step(parallel_step)
        # define sequential step
        sequential_step = UpgradeStep("sequential", parallel=False, coro=append("sequential"))
        for i in range(5):
            sub_step = UpgradeStep(
                f"sequential.{i}",
                parallel=False,
                coro=append(f"sequential.{i}"),
            )
            sub_step.add_step(
                UpgradeStep(
                    f"sequential.{i}.0",
                    parallel=False,
                    coro=append(f"sequential.{i}.0"),
                )
            )
            sequential_step.add_step(sub_step)
        self.plan.add_step(sequential_step)

    async def test_plan_structure(self):
        """Test plan structure."""
        expected_structure = dedent(
            """
        test plan
            [upgrade] parallel
                [upgrade] parallel.0
                    [upgrade] parallel.0.0
                    [upgrade] parallel.0.1
                    [upgrade] parallel.0.2
                [upgrade] parallel.1
                    [upgrade] parallel.1.0
                    [upgrade] parallel.1.1
                    [upgrade] parallel.1.2
                [upgrade] parallel.2
                    [upgrade] parallel.2.0
                    [upgrade] parallel.2.1
                    [upgrade] parallel.2.2
                [upgrade] parallel.3
                    [upgrade] parallel.3.0
                    [upgrade] parallel.3.1
                    [upgrade] parallel.3.2
                [upgrade] parallel.4
                    [upgrade] parallel.4.0
                    [upgrade] parallel.4.1
                    [upgrade] parallel.4.2
            [upgrade] sequential
                [upgrade] sequential.0
                    [upgrade] sequential.0.0
                [upgrade] sequential.1
                    [upgrade] sequential.1.0
                [upgrade] sequential.2
                    [upgrade] sequential.2.0
                [upgrade] sequential.3
                    [upgrade] sequential.3.0
                [upgrade] sequential.4
                    [upgrade] sequential.4.0
        """
        )
        expected_structure = expected_structure[1:]  # drop first new line
        expected_structure = expected_structure.replace("    ", "\t")  # replace 4 spaces with \t
        assert str(self.plan) == expected_structure

    async def test_apply_step_sequential_part(self):
        """Test apply_step sequential part.

        This this will check if all steps are run in right order.
        """
        exp_results = [
            "sequential",
            "sequential.0",
            "sequential.0.0",
            "sequential.1",
            "sequential.1.0",
            "sequential.2",
            "sequential.2.0",
            "sequential.3",
            "sequential.3.0",
            "sequential.4",
            "sequential.4.0",
        ]

        await apply_step(self.plan, interactive=False)
        results = self.execution_order[21:]

        self.assertListEqual(results, exp_results)

    async def test_apply_step_parallel_part(self):
        """Test apply_step parallel part.

        This this will check if sub-steps of parallel step was run in random order
        and their sub-sub-steps in sequential order.
        """
        exp_results = [
            "parallel",
            "parallel.0",
            "parallel.0.0",
            "parallel.0.1",
            "parallel.0.2",
            "parallel.1",
            "parallel.1.0",
            "parallel.1.1",
            "parallel.1.2",
            "parallel.2",
            "parallel.2.0",
            "parallel.2.1",
            "parallel.2.2",
            "parallel.3",
            "parallel.3.0",
            "parallel.3.1",
            "parallel.3.2",
            "parallel.4",
            "parallel.4.0",
            "parallel.4.1",
            "parallel.4.2",
        ]

        await apply_step(self.plan, interactive=False)
        results = self.execution_order[:21]

        # checking the results without order, since they are run in parallel with
        # random sleep there only small possibility that they will be in original order
        self.assertNotEqual(results, exp_results)

        # checking if sub-step of each parallel step is run sequentially
        for i in range(5):
            sub_step_order = [result for result in results if result.startswith(f"parallel.{i}.")]
            exp_sub_step_order = [f"parallel.{i}.{j}" for j in range(3)]
            self.assertListEqual(sub_step_order, exp_sub_step_order)

        # checking if each result is in expected results and if lists are same length
        for result in results:
            self.assertIn(result, exp_results)

        self.assertEqual(len(results), len(exp_results))
