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

from cou.exceptions import ActionFailed, HaltUpgradeExecution
from cou.utils.juju_utils import Machine, Model, Unit

logger = logging.getLogger(__name__)


async def get_empty_hypervisors(units: list[Unit], model: Model) -> list[Machine]:
    """Get the empty hypervisors in the model.

    :param units: all nova-compute units.
    :type units: list[Unit]
    :param model: Model object
    :type model: Model
    :return: List with just the empty hypervisors machines.
    :rtype: list[Machine]
    """
    tasks = [get_instance_count(unit.name, model) for unit in units]
    instances = await asyncio.gather(*tasks)
    units_instances = zip(units, instances)
    return [unit.machine for unit, instances in units_instances if instances == 0]


async def get_instance_count(unit: str, model: Model) -> int:
    """Get instance count on a nova-compute unit.

    :param unit: Name of the nova-compute unit where the action runs on.
    :type unit: str
    :param model: Model object
    :type model: Model
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


async def verify_empty_hypervisor_before_upgrade(unit: Unit, model: Model) -> None:
    """Verify if there are no VMs running in a nova-compute unit before upgrading.

    If there are VMs running, it will enable the scheduler again to leave the cloud
    in the same state before upgrading.
    :param unit: Unit to check if there are VMs running.
    :type unit: Unit
    :param model: Model
    :type model: Model
    :raises HaltUpgradeExecution: When a unit has VMs running.
    """
    unit_instance_count = await get_instance_count(unit.name, model)
    if unit_instance_count != 0:
        try:
            await model.run_action(
                unit_name=unit.name, action_name="enable", raise_on_failure=True
            )
            logger.info("Successfully enabled nova-compute scheduler from unit %s.", unit.name)
        except ActionFailed:
            logger.error("Failed to enable nova-compute scheduler from unit %s.", unit.name)
        logger.warning(
            "Unit: %s has %s VMs running. The upgrade on this unit cannot happen "
            "unless it's empty or force flag is used",
            unit.name,
            unit_instance_count,
        )
        raise HaltUpgradeExecution(f"Unit: {unit.name} has {unit_instance_count} VMs running")
