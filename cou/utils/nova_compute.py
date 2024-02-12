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

"""Nova Compute utilities."""

import asyncio

from cou.utils.juju_utils import COUMachine, COUModel, COUUnit


async def get_empty_hypervisors(units: list[COUUnit], model: COUModel) -> list[COUMachine]:
    """Get the empty hypervisors in the model.

    :param units: all nova-compute units.
    :type units: list[COUUnit]
    :param model: COUModel object
    :type model: COUModel
    :return: List with just the empty hypervisors machines.
    :rtype: list[COUMachine]
    """
    tasks = [get_instance_count(unit.name, model) for unit in units]
    instances = await asyncio.gather(*tasks)
    units_instances = zip(units, instances)
    return [unit.machine for unit, instances in units_instances if instances == 0]


async def get_instance_count(unit: str, model: COUModel) -> int:
    """Get instance count on a nova-compute unit.

    :param unit: Name of the nova-compute unit where the action runs on.
    :type unit: str
    :param model: COUModel object
    :type model: COUModel
    :return: Instance count of the nova-compute unit
    :rtype: int
    :raises ValueError: When the action result is not valid.
    """
    action_name = "instance-count"
    action = await model.run_action(unit_name=unit, action_name=action_name)

    if (
        instance_count := action.results.get("instance-count", "").strip()
    ) and instance_count.isdigit():
        return int(instance_count)

    raise ValueError(
        f"No valid instance count value found in the result of {action_name} action "
        f"running on '{unit}': {action.results}"
    )
