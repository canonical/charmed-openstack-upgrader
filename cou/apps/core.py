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

"""Core application class."""
import logging
from typing import Optional

from cou.apps.base import ApplicationUnit, OpenStackApplication
from cou.apps.factory import AppFactory
from cou.exceptions import ApplicationError
from cou.steps import UnitUpgradeStep, UpgradeStep
from cou.utils.nova_compute import get_instance_count_to_upgrade
from cou.utils.openstack import OpenStackRelease

logger = logging.getLogger(__name__)


@AppFactory.register_application(["keystone"])
class Keystone(OpenStackApplication):
    """Keystone application.

    Keystone must wait for the entire model to be idle before declaring the upgrade complete.
    """

    wait_timeout = 30 * 60  # 30 min
    wait_for_model = True


@AppFactory.register_application(["octavia"])
class Octavia(OpenStackApplication):
    """Octavia application.

    Octavia required more time to settle before COU can continue.
    """

    wait_timeout = 30 * 60  # 30 min


@AppFactory.register_application(["nova-compute"])
class NovaCompute(OpenStackApplication):
    """Nova Compute application.

    Nova Compute must wait for the entire model to be idle before declaring the upgrade complete.
    """

    wait_timeout = 30 * 60  # 30 min
    wait_for_model = True
    force: bool = False

    def upgrade_steps(
        self, target: OpenStackRelease, units: Optional[list[ApplicationUnit]]
    ) -> list[UpgradeStep]:
        """Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate upgrade steps,
        :type units: Optional[list[ApplicationUnit]]
        :raises ApplicationError: If no units are passed to upgrade Nova Compute
        :return: List of upgrade steps.
        :rtype: list[UpgradeStep]
        """
        if not units:
            raise ApplicationError("No units passed to upgrade Nova Compute.")
        app_steps = super().upgrade_steps(target, units)
        unit_steps = self._get_units_upgrade_steps(units)
        return app_steps + unit_steps

    def _get_units_upgrade_steps(self, units: list[ApplicationUnit]) -> list[UpgradeStep]:
        """Get the upgrade steps for the units.

        :param units: Units to generate upgrade steps
        :type units: list[ApplicationUnit]
        :return: List of upgrade steps
        :rtype: list[UpgradeStep]
        """
        units_steps = UpgradeStep(
            description=f"Upgrade plan for units: {', '.join([unit.name for unit in units])}",
            parallel=True,
        )

        for unit in units:
            unit_steps = UnitUpgradeStep(description=f"Upgrade plan for unit: {unit.name}")
            unit_steps.add_step(self._get_disable_scheduler_step(unit))
            unit_steps.add_step(self._get_empty_hypervisor_step(unit))
            unit_steps.add_step(self._get_pause_unit_step(unit, self._dependency_of_steps))
            unit_steps.add_step(self._get_openstack_upgrade_step(unit, self._dependency_of_steps))
            unit_steps.add_step(self._get_resume_unit_step(unit, self._dependency_of_steps))
            unit_steps.add_step(self._get_enable_scheduler_step(unit))
            units_steps.add_step(unit_steps)

        return [units_steps]

    @property
    def _dependency_of_steps(self) -> bool:
        """Check if it needs to show dependency on unit upgrade steps.

        If force is used, there are no dependencies.

        :return: True if there are dependency, False otherwise
        :rtype: bool
        """
        return not self.force

    def _get_empty_hypervisor_step(self, unit: ApplicationUnit) -> UnitUpgradeStep:
        """Get the step to check if the unit has no VMs running.

        In case force is set to true, no check is done.

        :param unit: Unit to check the instance-count
        :type unit: ApplicationUnit
        :return: Step to check if the hypervisor is empty.
        :rtype: UnitUpgradeStep
        """
        if self.force:
            return UnitUpgradeStep()
        return UnitUpgradeStep(
            description=f"Check if unit {unit.name} has no VMs running to upgrade.",
            coro=get_instance_count_to_upgrade(unit, self.model),
        )

    def _get_enable_scheduler_step(self, unit: ApplicationUnit) -> UnitUpgradeStep:
        """Get the step to enable the scheduler, so the unit can create new VMs.

        :param unit: Unit to be enabled.
        :type unit: ApplicationUnit
        :return: Step to enable the scheduler
        :rtype: UnitUpgradeStep
        """
        return UnitUpgradeStep(
            description=f"Enable nova-compute scheduler from unit: '{unit.name}'.",
            coro=self.model.run_action(
                unit_name=unit.name, action_name="enable", raise_on_failure=True
            ),
        )

    def _get_disable_scheduler_step(self, unit: ApplicationUnit) -> UnitUpgradeStep:
        """Get the step to disable the scheduler,  so the unit cannot create new VMs.

        :param unit: Unit to be disabled.
        :type unit: ApplicationUnit
        :return: Step to disable the scheduler
        :rtype: UnitUpgradeStep
        """
        return UnitUpgradeStep(
            description=f"Disable nova-compute scheduler from unit: '{unit.name}'.",
            coro=self.model.run_action(
                unit_name=unit.name, action_name="enable", raise_on_failure=True
            ),
        )
