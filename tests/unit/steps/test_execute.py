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
from unittest.mock import ANY, AsyncMock, call, patch

import pytest

from cou.steps import UpgradeStep
from cou.steps.execute import _run_step, apply_plan, prompt


@pytest.mark.asyncio
@patch("cou.steps.execute.apply_plan")
async def test_run_step_sequentially(mock_apply_plan):
    """Test running step and all sub-steps sequentially."""
    upgrade_plan = AsyncMock(auto_spec=UpgradeStep)
    upgrade_plan.parallel = False
    upgrade_plan.sub_steps = sub_steps = [
        AsyncMock(auto_spec=UpgradeStep),
        AsyncMock(auto_spec=UpgradeStep),
    ]

    await _run_step(upgrade_plan, False)

    upgrade_plan.run.assert_awaited_once_with()
    mock_apply_plan.assert_has_awaits([call(sub_step, False) for sub_step in sub_steps])


@pytest.mark.asyncio
@patch("cou.steps.execute.apply_plan")
@patch("cou.steps.execute.asyncio.gather", new_callable=AsyncMock)
async def test_run_step_parallel(mock_gather, mock_apply_plan):
    """Test running step and all sub-steps in parallel."""
    upgrade_plan = AsyncMock(auto_spec=UpgradeStep)
    upgrade_plan.parallel = True
    upgrade_plan.sub_steps = sub_steps = [
        AsyncMock(auto_spec=UpgradeStep),
        AsyncMock(auto_spec=UpgradeStep),
        AsyncMock(auto_spec=UpgradeStep),
    ]

    await _run_step(upgrade_plan, False)

    upgrade_plan.run.assert_awaited_once_with()
    mock_apply_plan.assert_has_calls([call(step, False) for step in sub_steps])
    mock_gather.assert_awaited_once_with(ANY, ANY, ANY)  # called with 3 arguments


@pytest.mark.asyncio
@patch("cou.steps.execute.ainput")
@patch("cou.steps.execute._run_step")
async def test_apply_plan_abort(mock_run_step, mock_input):
    upgrade_plan = AsyncMock(auto_spec=UpgradeStep)
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
    upgrade_plan = AsyncMock(auto_spec=UpgradeStep)
    upgrade_plan.description = "Test Plan"

    await apply_plan(upgrade_plan, False)

    mock_input.assert_not_awaited()
    mock_run_step.assert_awaited_once_with(upgrade_plan, False)


@pytest.mark.asyncio
@patch("cou.steps.execute.ainput")
@patch("cou.steps.execute._run_step")
async def test_apply_plan_continue(mock_run_step, mock_input):
    upgrade_plan = AsyncMock(auto_spec=UpgradeStep)
    upgrade_plan.description = "Test Plan"
    mock_input.return_value = "C"

    await apply_plan(upgrade_plan, True)

    mock_input.assert_awaited_once_with(prompt("Test Plan"))
    mock_run_step.assert_awaited_once_with(upgrade_plan, True)


@pytest.mark.asyncio
@patch("cou.steps.execute.ainput")
@patch("cou.steps.execute._run_step")
async def test_apply_plan_nonsense(mock_run_step, mock_input):
    upgrade_plan = AsyncMock(auto_spec=UpgradeStep)
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
    upgrade_plan = AsyncMock(auto_spec=UpgradeStep)
    upgrade_plan.description = "Test Plan"
    mock_input.return_value = "s"

    await apply_plan(upgrade_plan, True)

    mock_input.assert_awaited_once_with(prompt("Test Plan"))
    mock_run_step.assert_not_awaited()


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

        self.plan = UpgradeStep("test plan", parallel=False, function=None)
        # define parallel step
        parallel_step = UpgradeStep("parallel", parallel=True, function=append, name="parallel")
        for i in range(5):
            sub_step = UpgradeStep(
                f"parallel.{i}", parallel=False, function=append, name=f"parallel.{i}"
            )
            for j in range(3):
                sub_step.add_step(
                    UpgradeStep(
                        f"parallel.{i}.{j}",
                        parallel=False,
                        function=append,
                        name=f"parallel.{i}.{j}",
                    )
                )

            parallel_step.add_step(sub_step)
        self.plan.add_step(parallel_step)
        # define sequential step
        sequential_step = UpgradeStep(
            "sequential", parallel=False, function=append, name="sequential"
        )
        for i in range(5):
            sub_step = UpgradeStep(
                f"sequential.{i}", parallel=False, function=append, name=f"sequential.{i}"
            )
            sub_step.add_step(
                UpgradeStep(
                    f"sequential.{i}.0", parallel=False, function=append, name=f"sequential.{i}.0"
                )
            )
            sequential_step.add_step(sub_step)
        self.plan.add_step(sequential_step)

    async def test_plan_structure(self):
        """Test plan structure."""
        expected_structure = dedent(
            """
        test plan
            parallel
                parallel.0
                    parallel.0.0
                    parallel.0.1
                    parallel.0.2
                parallel.1
                    parallel.1.0
                    parallel.1.1
                    parallel.1.2
                parallel.2
                    parallel.2.0
                    parallel.2.1
                    parallel.2.2
                parallel.3
                    parallel.3.0
                    parallel.3.1
                    parallel.3.2
                parallel.4
                    parallel.4.0
                    parallel.4.1
                    parallel.4.2
            sequential
                sequential.0
                    sequential.0.0
                sequential.1
                    sequential.1.0
                sequential.2
                    sequential.2.0
                sequential.3
                    sequential.3.0
                sequential.4
                    sequential.4.0
        """
        )
        expected_structure = expected_structure[1:]  # drop first new line
        expected_structure = expected_structure.replace("    ", "\t")  # replace 4 spaces with \t
        assert str(self.plan) == expected_structure

    async def test_apply_plan_sequential_part(self):
        """Test apply_plan sequential part.

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

        await apply_plan(self.plan, interactive=False)
        results = self.execution_order[21:]

        self.assertListEqual(results, exp_results)

    async def test_apply_plan_parallel_part(self):
        """Test apply_plan parallel part.

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

        await apply_plan(self.plan, interactive=False)
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
