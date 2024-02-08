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
import logging

from cou.apps.base import ApplicationUnit
from cou.apps.machine import Machine
from cou.exceptions import HaltUpgradeExecution
from cou.utils.juju_utils import COUModel

logger = logging.getLogger(__name__)


async def get_empty_hypervisors(units: list[ApplicationUnit], model: COUModel) -> list[Machine]:
    """Get the empty hypervisors in the model.

    :param units: all nova-compute units.
    :type units: list[ApplicationUnit]
    :param model: COUModel object
    :type model: COUModel
    :return: List with just the empty hypervisors machines.
    :rtype: list[Machine]
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


async def get_instance_count_to_upgrade(unit: ApplicationUnit, model: COUModel) -> None:
    """Get the instance count of a unit and enable the scheduler if it cannot upgrade.

    :param unit: Unit to check if there are VMs running.
    :type unit: ApplicationUnit
    :param model: COUModel
    :type model: COUModel
    :raises HaltUpgradeExecution: When a unit has VMs running.
    """
    unit_instance_count = await get_instance_count(unit.name, model)
    if unit_instance_count != 0:
        await model.run_action(unit_name=unit.name, action_name="enable", raise_on_failure=True)
        logger.warning(
            (
                "VMs are running on unit %s. The upgrade on this unit cannot happen "
                "unless it's empty or force flag is used"
            ),
            unit.name,
        )
        raise HaltUpgradeExecution(f"Unit: {unit.name} has {unit_instance_count} VMs running")
