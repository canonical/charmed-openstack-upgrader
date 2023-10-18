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

"""Test steps package."""
import asyncio
import re
from unittest.mock import MagicMock

import pytest

from cou.exceptions import CanceledUpgradeStep
from cou.steps import UpgradeStep, compare_step_coroutines


async def mock_coro(*args, **kwargs):
    ...


@pytest.mark.parametrize(
    "coro1, coro2, exp_result",
    [
        (None, mock_coro(), False),
        (mock_coro(), None, False),
        (mock_coro(), mock_coro(1, 2, 3), False),
        (mock_coro(), mock_coro(arg1=True), False),
        (mock_coro(), mock_coro(), True),
        (mock_coro(1, 2, 3, kwarg1=True), mock_coro(1, 2, 3, kwarg1=True), True),
    ],
)
def test_compare_step_coroutines(coro1, coro2, exp_result):
    """Test coroutine comparison."""
    assert compare_step_coroutines(coro1, coro2) == exp_result


@pytest.mark.parametrize("description, parallel", [("test", False), ("test description", True)])
def test_step_init(description, parallel):
    """Test UpgradeStep initialization."""
    coro = mock_coro()
    step = UpgradeStep(description, parallel, coro)

    assert step.description == description
    assert step.parallel == parallel
    assert step._coro == coro
    assert step._canceled is False
    assert step._task is None


def test_step_hash():
    """Test creation of hash from UpgradeStep."""
    coro = mock_coro()
    step = UpgradeStep("test hash", False, coro)

    assert hash(("test hash", False, coro)) == hash(step)


@pytest.mark.parametrize(
    "description, parallel, args",
    [("test", False, ()), ("test description", True, ("name", 1, 2))],
)
def test_step_eq(description, parallel, args):
    """Test UpgradeStep comparison."""
    step_1 = UpgradeStep(description, parallel, mock_coro(*args))
    step_2 = UpgradeStep(description, parallel, mock_coro(*args))
    # define step with different coro
    step_3 = UpgradeStep(description, parallel, mock_coro(unique_arg=True))

    assert step_1 == step_2
    assert step_1 != step_3
    assert step_1 != 1


def test_step_str():
    """Test UpgradeStep string representation."""
    expected = "a\n\ta.a\n\t\ta.a.a\n\t\ta.a.b\n\ta.b\n"
    plan = UpgradeStep(description="a")
    sub_step = UpgradeStep(description="a.a")
    sub_step.sub_steps = [
        UpgradeStep(description="a.a.a"),
        UpgradeStep(description="a.a.b"),
    ]
    plan.sub_steps = [sub_step, UpgradeStep(description="a.b")]

    assert str(plan) == expected


def test_step_repr():
    """Test UpgradeStep representation."""
    description = "test plan"
    upgrade_step = UpgradeStep(description=description)
    upgrade_step.add_step(UpgradeStep(description="test sub-step"))
    expected_repr = f"UpgradeStep({description})"
    assert repr(upgrade_step) == expected_repr


@pytest.mark.asyncio
async def test_properties():
    """Test UpgradeStep properties."""

    async def coro():
        return 42

    upgrade_step = UpgradeStep(description="test", coro=coro())

    assert upgrade_step.canceled == upgrade_step._canceled
    assert upgrade_step.results is None

    await upgrade_step.run()

    assert upgrade_step.results == 42


def test_step_add_step():
    """Test UpgradeStep adding sub steps."""
    exp_sub_steps = 3
    plan = UpgradeStep(description="plan")
    for i in range(exp_sub_steps):
        plan.add_step(UpgradeStep(description=f"sub-step-{i}"))

    assert len(plan.sub_steps) == exp_sub_steps


def test_step_cancel_safe():
    """Test step safe cancel."""
    plan = UpgradeStep(description="plan")
    plan.sub_steps = sub_steps = [UpgradeStep(description=f"sub-{i}") for i in range(10)]
    # add sub-sub-steps to one sub-step
    sub_steps[0].sub_steps = [UpgradeStep(description=f"sub-0.{i}") for i in range(3)]

    plan.cancel()

    assert plan.canceled is True
    assert all(step.canceled is True for step in sub_steps)
    assert all(step.canceled for step in sub_steps[0].sub_steps)


def test_step_cancel_unsafe():
    """Test step unsafe cancel."""
    plan = UpgradeStep(description="test plan")
    plan._task = mock_task = MagicMock(spec_sep=asyncio.Task)

    plan.cancel(safe=False)

    assert plan.canceled is True
    mock_task.cancel.assert_called_once_with("canceled: UpgradeStep(test plan)")


@pytest.mark.asyncio
async def test_step_run():
    """Test UpgradeStep run."""

    async def asquared(num):
        return num**2

    step = UpgradeStep(description="plan", coro=asquared(5))
    value = await step.run()

    assert value == 25


@pytest.mark.asyncio
async def test_step_run_canceled():
    """Test UpgradeStep run canceled step."""
    description = "test plan"
    exp_error = re.escape(f"Could not run canceled step: UpgradeStep({description})")
    step = UpgradeStep(description=description, coro=mock_coro())
    step.cancel()
    assert step.canceled is True
    with pytest.raises(CanceledUpgradeStep, match=exp_error):
        await step.run()


@pytest.mark.asyncio
async def test_step_cancel_task():
    """Test UpgradeStep cancel step task."""

    async def step_canceller(_step):
        await asyncio.sleep(0.5)
        _step._task.cancel()

    # simulate a cancel step task that waits 10 minutes without CancelledError
    step = UpgradeStep(description="test plan", coro=asyncio.sleep(600))
    assert step._task is None

    asyncio.create_task(step_canceller(step))

    await step.run()

    assert step._task is not None
    assert step._task.cancelling() == 1  # task was canceled once


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sub_steps, exp_order, parallel",
    [
        (
            [("sub-1", 0.4, []), ("sub-2", 0.2, []), ("sub-3", 0.6, []), ("sub-4", 0.8, [])],
            ["sub-2", "sub-1", "sub-3", "sub-4"],
            True,
        ),
        (
            [("sub-1", 0.2, [("sub-1.1", 0.05), ("sub-1.2", 0.3)]), ("sub-2", 0.3, [])],
            ["sub-1", "sub-1.1", "sub-2", "sub-1.2"],
            True,
        ),
        (
            [("sub-1", 0.6, []), ("sub-2", 0.2, []), ("sub-3", 0.4, [])],
            ["sub-1", "sub-2", "sub-3"],
            False,
        ),
        (
            [("sub-1", 0.6, [("sub-1.1", 0.3)]), ("sub-2", 0.2, []), ("sub-3", 0.4, [])],
            ["sub-1", "sub-1.1", "sub-2", "sub-3"],
            False,
        ),
    ],
)
async def test_step_full_run(sub_steps, exp_order, parallel):
    """Test to simulate running full plan with steps."""
    steps_order = []

    async def sub_step(name, time):
        await asyncio.sleep(time)
        steps_order.append(name)

    async def step_run(_step):
        await _step.run()
        for _sub_step in _step.sub_steps:
            if step.canceled is False:
                await step_run(_sub_step)

    plan = UpgradeStep(description="upgrade plan")
    for name, time, step_sub_steps in sub_steps:
        step = UpgradeStep(description=name, coro=sub_step(name, time))
        plan.add_step(step)
        for sub_name, sub_time in step_sub_steps:
            step.add_step(UpgradeStep(description=sub_name, coro=sub_step(sub_name, sub_time)))

    await plan.run()
    if parallel:
        await asyncio.gather(*(step_run(step) for step in plan.sub_steps))
    else:
        await step_run(plan)

    assert steps_order == exp_order
