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

"""Test steps package."""
import pytest

from cou.steps import UpgradeStep


def test_upgrade_step():
    def sample_function():
        return 1

    u = UpgradeStep(description="test", function=sample_function, parallel=False)
    assert u.description == "test"
    assert u.function is sample_function
    assert not u.parallel
    assert u.params == {}


def test_upgrade_step_add():
    u = UpgradeStep(description="test", function=None, parallel=False)
    substep = u.add_step(UpgradeStep(description="substep", function=None, parallel=False))
    substep_of_substep1 = substep.add_step(
        UpgradeStep(description="substep_of_substep1", function=None, parallel=False)
    )
    substep_of_substep2 = substep.add_step(
        UpgradeStep(description="substep_of_substep2", function=None, parallel=False)
    )
    assert u.sub_steps[0] is substep
    assert substep.sub_steps[0] is substep_of_substep1
    assert substep.sub_steps[1] is substep_of_substep2


@pytest.mark.asyncio
async def test_upgrade_step_run():
    async def sample_function(**kwargs):
        return kwargs["x"]

    u = UpgradeStep(description="test", function=sample_function, parallel=False, **{"x": 10})

    result = await u.run()
    assert result == 10


@pytest.mark.asyncio
async def test_upgrade_step_run_empty():
    async def sample_function(**kwargs):
        return 5

    u = UpgradeStep(description="test", function=sample_function, parallel=False)

    result = await u.run()
    assert result == 5


@pytest.mark.asyncio
async def test_upgrade_step_run_none():
    u = UpgradeStep(description="test", function=None, parallel=False)
    result = await u.run()
    assert result is None


def test___str__():
    expected = "Top level plan\n\tbackup mysql databases\n"
    plan = UpgradeStep(description="Top level plan", parallel=False, function=None)
    plan.add_step(UpgradeStep(description="backup mysql databases", parallel=False, function=None))
    assert str(plan) == expected


def test___str__substep_has_substeps():
    expected = "a\n\ta.a\n\t\ta.a.a\n\t\ta.a.b\n\ta.b\n"
    plan = UpgradeStep(description="a", parallel=False, function=None)
    aa = plan.add_step(UpgradeStep(description="a.a", parallel=False, function=None))
    plan.add_step(UpgradeStep(description="a.b", parallel=False, function=None))
    aa.add_step(UpgradeStep(description="a.a.a", parallel=False, function=None))
    aa.add_step(UpgradeStep(description="a.a.b", parallel=False, function=None))
    assert str(plan) == expected
