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
from juju.action import Action

from cou.exceptions import ActionFailed, HaltUpgradeExecution
from cou.utils import nova_compute
from cou.utils.juju_utils import COUMachine, COUUnit


@pytest.mark.asyncio
async def test_get_instance_count(model):
    expected_count = 1
    model.run_action.return_value = mocked_action = AsyncMock(spec_set=Action).return_value
    mocked_action.results = {"Code": "0", "instance-count": str(expected_count)}

    actual_count = await nova_compute.get_instance_count(unit="nova-compute/0", model=model)

    model.run_action.assert_called_once_with(
        unit_name="nova-compute/0",
        action_name="instance-count",
    )
    assert actual_count == expected_count


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "result_key, value",
    [
        ("not_valid", "1"),  # invalid key
        ("instance-count", "not_valid"),  # invalid value
        ("not_valid", "not_valid"),  # invalid key and value
    ],
)
async def test_get_instance_count_invalid_result(model, result_key, value):
    model.run_action.return_value = mocked_action = AsyncMock(spec_set=Action).return_value
    mocked_action.results = {"Code": "0", result_key: value}

    with pytest.raises(ValueError):
        await nova_compute.get_instance_count(unit="nova-compute/0", model=model)


@pytest.mark.parametrize(
    "hypervisors_count, expected_result",
    [
        ([(0, 0), (1, 0), (2, 0)], {"0", "1", "2"}),
        ([(0, 1), (1, 0), (2, 0)], {"1", "2"}),
        ([(0, 1), (1, 3), (2, 0)], {"2"}),
        ([(0, 1), (1, 3), (2, 5)], set()),
    ],
)
@pytest.mark.asyncio
@patch("cou.utils.nova_compute.get_instance_count")
async def test_get_empty_hypervisors(
    mock_instance_count, hypervisors_count, expected_result, model
):
    mock_instance_count.side_effect = [count for _, count in hypervisors_count]
    result = await nova_compute.get_empty_hypervisors(
        [_mock_nova_unit(nova_unit) for nova_unit, _ in hypervisors_count], model
    )
    assert {machine.machine_id for machine in result} == expected_result


@pytest.mark.parametrize("instance_count", [1, 10, 50])
@pytest.mark.asyncio
@patch("cou.utils.nova_compute.logger")
@patch("cou.utils.nova_compute.get_instance_count")
async def test_verify_empty_hypervisor_before_upgrade_exception(
    mock_instance_count, mock_logger, instance_count, model
):
    mock_instance_count.return_value = instance_count
    nova_unit = _mock_nova_unit(1)
    exp_error_msg = f"Unit: {nova_unit.name} has {instance_count} VMs running"
    with pytest.raises(HaltUpgradeExecution, match=exp_error_msg):
        await nova_compute.verify_empty_hypervisor_before_upgrade(nova_unit, model)
    model.run_action.assert_called_once_with(
        unit_name=nova_unit.name, action_name="enable", raise_on_failure=True
    )
    mock_logger.error.assert_not_called()
    mock_logger.warning.assert_called_once()


@pytest.mark.parametrize("instance_count", [1, 10, 50])
@pytest.mark.asyncio
@patch("cou.utils.nova_compute.logger")
@patch("cou.utils.nova_compute.get_instance_count")
async def test_verify_empty_hypervisor_before_upgrade_ActionFailed(
    mock_instance_count, mock_logger, instance_count, model
):
    mock_instance_count.return_value = instance_count
    model.run_action.side_effect = ActionFailed("enable")
    nova_unit = _mock_nova_unit(1)
    exp_error_msg = f"Unit: {nova_unit.name} has {instance_count} VMs running"
    with pytest.raises(HaltUpgradeExecution, match=exp_error_msg):
        await nova_compute.verify_empty_hypervisor_before_upgrade(nova_unit, model) is None

    mock_logger.error.assert_called_once()
    mock_logger.warning.assert_called_once()


@pytest.mark.asyncio
@patch("cou.utils.nova_compute.get_instance_count", return_value=0)
async def test_verify_empty_hypervisor_before_upgrade(mock_instance_count, model):
    nova_unit = _mock_nova_unit(1)
    assert await nova_compute.verify_empty_hypervisor_before_upgrade(nova_unit, model) is None


def _mock_nova_unit(nova_unit):
    mock_nova_unit = MagicMock(spec_set=COUUnit(MagicMock(), MagicMock(), MagicMock()))
    mock_nova_unit.name = f"nova-compute/{nova_unit}"
    nova_machine = COUMachine(str(nova_unit), f"juju-c307f8-{nova_unit}", f"zone-{nova_unit + 1}")
    mock_nova_unit.machine = nova_machine

    return mock_nova_unit
