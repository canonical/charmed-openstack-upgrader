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
