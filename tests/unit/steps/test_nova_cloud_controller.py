# Copyright 2024 Canonical Limited
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

from unittest.mock import AsyncMock, MagicMock, call

import pytest

from cou.exceptions import ApplicationNotFound, COUException, UnitNotFound
from cou.steps.nova_cloud_controller import archive
from tests.unit.utils import get_status


@pytest.mark.asyncio
async def test_archive_succeeds(model):
    model.get_charm_name.side_effect = lambda x: x
    model.run_action.return_value = action = MagicMock()
    action.results = {"archive-deleted-rows": "Nothing was archived."}

    await archive(model, batch_size=999)

    model.run_action.assert_awaited_once_with(
        unit_name="nova-cloud-controller/0",
        action_name="archive-data",
        raise_on_failure=True,
        action_params={"batch-size": 999},
    )


@pytest.mark.asyncio
async def test_archive_with_broken_charm_action(model):
    model.get_charm_name.side_effect = lambda x: x
    model.run_action.return_value = action = MagicMock()
    # simulate the expected archive-deleted-rows key missing
    action.results = {}

    # It should raise an expected exception
    # (this will be more graceful than a KeyError for example).
    with pytest.raises(COUException, match="archive-deleted-rows"):
        await archive(model, batch_size=999)

    model.run_action.assert_awaited_once_with(
        unit_name="nova-cloud-controller/0",
        action_name="archive-data",
        raise_on_failure=True,
        action_params={"batch-size": 999},
    )


@pytest.mark.asyncio
async def test_archive_app_not_found(model):
    # Update the mocked status so a nova-cloud-controller charm doesn't exist
    status = get_status()
    del status.applications["nova-cloud-controller"]
    model.get_status = AsyncMock(return_value=status)

    with pytest.raises(ApplicationNotFound):
        await archive(model, batch_size=999)

    model.run_action.assert_not_called()


@pytest.mark.asyncio
async def test_archive_unit_not_found(model):
    # Update the mocked status so nova-cloud-controller doesn't have any units
    status = get_status()
    status.applications["nova-cloud-controller"].units = {}
    model.get_status = AsyncMock(return_value=status)

    with pytest.raises(UnitNotFound):
        await archive(model, batch_size=999)

    model.run_action.assert_not_called()


@pytest.mark.asyncio
async def test_archive_handles_multiple_batches(model):
    model.get_charm_name.side_effect = lambda x: x
    model.run_action.side_effect = [
        MagicMock(results={"archive-deleted-rows": "placeholder 25 rows"}),
        MagicMock(results={"archive-deleted-rows": "Nothing was archived."}),
    ]

    await archive(model, batch_size=999)

    assert model.run_action.call_count == 2
    expected_call = call(
        unit_name="nova-cloud-controller/0",
        action_name="archive-data",
        raise_on_failure=True,
        action_params={"batch-size": 999},
    )
    model.run_action.assert_has_awaits([expected_call, expected_call])
