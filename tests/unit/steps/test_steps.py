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

from cou.exceptions import CanceledStep
from cou.steps import (
    DEPENDENCY_DESCRIPTION_PREFIX,
    BaseStep,
    PostUpgradeStep,
    PreUpgradeStep,
    UpgradePlan,
    compare_step_coroutines,
)


async def mock_coro(*args, **kwargs): ...


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


@pytest.mark.parametrize(
    "description, parallel",
    [
        ("test", False),
        ("test description", True),
        ("test description", True),
    ],
)
def test_step_init(description, parallel):
    """Test BaseStep initialization."""
    coro = mock_coro()
    step = BaseStep(description, parallel, coro)

    assert step.description == description
    assert step.parallel == parallel
    assert step._coro == coro
    assert step.prompt is True
    assert step._canceled is False
    assert step._task is None


def test_step_hash():
    """Test creation of hash from BaseStep."""
    coro = mock_coro()
    step = BaseStep("test hash", False, coro)

    assert hash(("test hash", False, coro)) == hash(step)


@pytest.mark.parametrize(
    "description, parallel, args",
    [("test", False, ()), ("test description", True, ("name", 1, 2))],
)
def test_step_eq(description, parallel, args):
    """Test BaseStep comparison."""
    step_1 = BaseStep(description, parallel, mock_coro(*args))
    step_2 = BaseStep(description, parallel, mock_coro(*args))
    # define step with different coro
    step_3 = BaseStep(description, parallel, mock_coro(unique_arg=True))

    assert step_1 == step_2
    assert step_1 != step_3
    assert step_1 != 1  # check __eq__ with another object


def test_step_eq_empty_upgrades():
    step_1 = BaseStep()
    step_2 = BaseStep()
    assert step_1 == step_2


def test_step_bool():
    """Test BaseStep boolean method."""
    # no coroutine in the plan
    plan = BaseStep(description="a")
    assert bool(plan) is False

    # no coroutine in the plan and sub_step
    sub_step = BaseStep(description="a.a")
    assert bool(sub_step) is False

    plan.add_step(sub_step)
    assert bool(plan) is False

    # coroutine in the plan sub_steps tree
    sub_sub_step = BaseStep(description="a.a.a", coro=mock_coro("a.a.a"))
    sub_step.add_step(sub_sub_step)
    plan.add_step(sub_step)

    assert bool(sub_sub_step) is True
    assert bool(sub_step) is True
    assert bool(plan) is True


def test_step_str():
    """Test BaseStep string representation."""
    expected = "a\n\ta.a\n\t\ta.a.a\n\t\ta.a.b\n\ta.b\n"
    plan = BaseStep(description="a")
    sub_step = BaseStep(description="a.a")
    sub_step.sub_steps = [
        BaseStep(description="a.a.a", coro=mock_coro("a.a.a")),
        BaseStep(description="a.a.b", coro=mock_coro("a.a.b")),
    ]
    plan.sub_steps = [sub_step, BaseStep(description="a.b", coro=mock_coro("a.b"))]

    assert str(plan) == expected


def test_step_str_dependent():
    """Test BaseStep string representation."""
    expected = (
        f"a\n\ta.a\n\t\t{DEPENDENCY_DESCRIPTION_PREFIX}a.a.a\n"
        f"\t\t{DEPENDENCY_DESCRIPTION_PREFIX}a.a.b\n\ta.b\n"
    )
    plan = BaseStep(description="a")
    sub_step = BaseStep(description="a.a")
    sub_step.sub_steps = [
        BaseStep(description="a.a.a", coro=mock_coro("a.a.a"), dependent=True),
        BaseStep(description="a.a.b", coro=mock_coro("a.a.b"), dependent=True),
    ]
    plan.sub_steps = [sub_step, BaseStep(description="a.b", coro=mock_coro("a.b"))]

    assert str(plan) == expected


def test_step_str_not_show():
    """Test BaseStep string representation when does not print because it's empty."""
    plan = BaseStep(description="a")
    sub_step = BaseStep(description="a.a")
    sub_step.sub_steps = [
        BaseStep(description="a.a.a"),
        BaseStep(description="a.a.b"),
    ]
    plan.sub_steps = [sub_step, BaseStep(description="a.b")]

    assert str(plan) == ""


def test_step_str_partially_show():
    """Test BaseStep string representation when print BaseSteps that have coro."""
    expected = "a\n\ta.a\n\t\ta.a.a\n"
    plan = BaseStep(description="a")
    sub_step = BaseStep(description="a.a")
    sub_step.sub_steps = [
        BaseStep(description="a.a.a", coro=mock_coro("a.a.a")),
        BaseStep(description="a.a.b"),
    ]
    # empty BaseStep does not show up
    plan.sub_steps = [BaseStep(), sub_step, BaseStep(description="a.b")]

    assert str(plan) == expected


def test_step_repr():
    """Test BaseStep representation."""
    description = "test plan"
    upgrade_step = BaseStep(description=description)
    upgrade_step.add_step(BaseStep(description="test sub-step"))
    expected_repr = f"BaseStep({description})"
    assert repr(upgrade_step) == expected_repr


@pytest.mark.parametrize("step", [BaseStep, PreUpgradeStep, PostUpgradeStep])
def test_step_repr_no_description(step):
    """Test BaseStep representation when there is no description."""
    with pytest.raises(ValueError):
        step(coro=mock_coro("a"))


@pytest.mark.asyncio
async def test_properties():
    """Test BaseStep properties."""

    async def coro():
        return 42

    upgrade_step = BaseStep(description="test", coro=coro())

    assert upgrade_step.canceled == upgrade_step._canceled
    assert upgrade_step.done is False
    assert upgrade_step.all_done is False

    await upgrade_step.run()

    assert upgrade_step.done is True
    assert upgrade_step.all_done is True


def test_step_add_step():
    """Test BaseStep adding sub steps."""
    exp_sub_steps = 3
    plan = BaseStep(description="plan")
    for i in range(exp_sub_steps):
        plan.add_step(BaseStep(description=f"sub-step-{i}", coro=mock_coro()))

    assert len(plan.sub_steps) == exp_sub_steps


def test_step_add_step_skipping_empty():
    """Test BaseStep skipping to add empty sub steps."""
    exp_sub_steps = 0
    plan = BaseStep(description="plan")
    for i in range(3):
        plan.add_step(BaseStep(description=f"sub-step-{i}"))

    assert len(plan.sub_steps) == exp_sub_steps


def test_step_add_step_failed():
    """Test BaseStep adding sub steps failing."""
    exp_error_msg = "Cannot add an upgrade step that is not derived from BaseStep"
    plan = BaseStep(description="plan")

    with pytest.raises(TypeError, match=exp_error_msg):
        plan.add_step(MagicMock())


def test_step_add_steps():
    """Test BaseStep adding sub steps at once."""
    exp_sub_steps = 3
    plan = BaseStep(description="plan")
    plan.add_steps(
        [BaseStep(description=f"sub-step-{i}", coro=mock_coro()) for i in range(exp_sub_steps)]
        + [BaseStep(description="empty-step")]  # we also check that empty step will not be added
    )

    assert len(plan.sub_steps) == exp_sub_steps


def test_step_cancel_safe():
    """Test step safe cancel."""
    plan = BaseStep(description="plan")
    plan.sub_steps = sub_steps = [
        BaseStep(description=f"sub-{i}", coro=mock_coro()) for i in range(10)
    ]
    # add sub-sub-steps to one sub-step
    sub_steps[0].sub_steps = [
        BaseStep(description=f"sub-0.{i}", coro=mock_coro()) for i in range(3)
    ]

    plan.cancel()

    assert plan.canceled is True
    assert all(step.canceled is True for step in sub_steps)
    assert all(step.canceled for step in sub_steps[0].sub_steps)


def test_step_cancel_unsafe():
    """Test step unsafe cancel."""
    plan = BaseStep(description="test plan")
    plan._task = mock_task = MagicMock(spec_sep=asyncio.Task)

    plan.cancel(safe=False)

    assert plan.canceled is True
    mock_task.cancel.assert_called_once_with("canceled: BaseStep(test plan)")


@pytest.mark.asyncio
async def test_step_run():
    """Test BaseStep run."""

    async def asquared(num):
        return num**2

    step = BaseStep(description="plan", coro=asquared(5))
    value = await step.run()

    assert value == 25


@pytest.mark.asyncio
async def test_step_run_canceled():
    """Test BaseStep run canceled step."""
    description = "test plan"
    exp_error = re.escape(f"Could not run canceled step: BaseStep({description})")
    step = BaseStep(description=description, coro=mock_coro())
    step.cancel()
    assert step.canceled is True
    with pytest.raises(CanceledStep, match=exp_error):
        await step.run()


@pytest.mark.asyncio
async def test_step_cancel_task():
    """Test BaseStep cancel step task."""

    async def step_canceller(_step):
        await asyncio.sleep(0.5)
        _step._task.cancel()

    # simulate a cancel step task that waits 10 minutes without CancelledError
    step = BaseStep(description="test plan", coro=asyncio.sleep(600))
    assert step._task is None

    asyncio.create_task(step_canceller(step))

    await step.run()

    assert step._task is not None
    assert step._task.cancelled() == 1  # task was canceled once


@pytest.mark.asyncio
async def test_upgrade_plan_step_instances():
    """Test setting parallel for UpgradePlan."""
    description = "test plan"
    step = UpgradePlan(description=description)

    assert step._coro is None
    assert step.parallel is False
    assert step.prompt is False


@pytest.mark.asyncio
async def test_upgrade_plan_step_invalid_coro_input():
    """Test setting coro for UpgradePlan."""
    description = "test plan"
    with pytest.raises(TypeError):
        UpgradePlan(description=description, coro=mock_coro())


@pytest.mark.asyncio
async def test_upgrade_plan_step_invalid_parallel_input():
    """Test setting parallel for UpgradePlan."""
    description = "test plan"
    with pytest.raises(TypeError):
        UpgradePlan(description=description, parallel=False)


@pytest.mark.asyncio
async def test_application_upgrade_plan_step_default_prompt():
    """Test setting parallel for UpgradePlan."""
    description = "test plan"
    with pytest.raises(TypeError):
        UpgradePlan(description=description, parallel=False)


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

    plan = BaseStep(description="upgrade plan")
    for name, time, step_sub_steps in sub_steps:
        step = BaseStep(description=name, coro=sub_step(name, time))
        plan.add_step(step)
        for sub_name, sub_time in step_sub_steps:
            step.add_step(BaseStep(description=sub_name, coro=sub_step(sub_name, sub_time)))

    await plan.run()
    if parallel:
        await asyncio.gather(*(step_run(step) for step in plan.sub_steps))
    else:
        await step_run(plan)

    assert steps_order == exp_order
