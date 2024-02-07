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
from dataclasses import dataclass, field

from cou.apps.base import ApplicationUnit, OpenStackApplication
from cou.apps.factory import AppFactory
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
@dataclass(kw_only=True)
class NovaCompute(OpenStackApplication):
    """Nova Compute application.

    Nova Compute must wait for the entire model to be idle before declaring the upgrade complete.
    """

    wait_timeout = 30 * 60  # 30 min
    wait_for_model = True
    force: bool = field(default=False, init=False)

    def upgrade_steps(
        self, target: OpenStackRelease, units: list[ApplicationUnit]
    ) -> list[UpgradeStep]:
        """Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :raises HaltUpgradePlanGeneration: When the application halt the upgrade plan generation.
        :return: List of upgrade steps.
        :rtype: list[UpgradeStep]
        """
        app_steps = super().upgrade_steps(target, units)
        unit_steps = self._get_units_upgrade_steps(units)
        return app_steps + unit_steps

    def _get_units_upgrade_steps(self, units: list[ApplicationUnit]) -> list[UpgradeStep]:
        units_steps = UpgradeStep(
            description=f"Upgrade plan for units: {', '.join([unit.name for unit in units])}",
            parallel=True,
        )

        for unit in units:
            unit_steps = UnitUpgradeStep(description=f"Upgrade plan for unit: {unit.name}")
            unit_steps.add_step(self._get_disable_scheduler_step(unit))
            empty_hypervisor_check_step = self._get_empty_hypervisor_check(unit)

            other_steps = [
                self._get_pause_unit_step(unit),
                self._get_openstack_upgrade_step(unit),
                self._get_resume_unit_step(unit),
            ]

            if empty_hypervisor_check_step:
                [empty_hypervisor_check_step.add_step(step) for step in other_steps]
                unit_steps.add_step(empty_hypervisor_check_step)
            else:
                [unit_steps.add_step(step) for step in other_steps]

            unit_steps.add_step(self._get_enable_scheduler_step(unit))
            units_steps.add_step(unit_steps)

        return [units_steps]

    def _get_empty_hypervisor_check(self, unit) -> UnitUpgradeStep:
        """Get the step to check if the unit has no VMs running.

        In case force is set to true,

        :param unit: _description_
        :type unit: _type_
        :return: _description_
        :rtype: UnitUpgradeStep
        """
        if self.force:
            return UnitUpgradeStep()
        return UnitUpgradeStep(
            description="Run the instance-count to upgrade",
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
