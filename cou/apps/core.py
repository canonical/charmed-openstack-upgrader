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
import os
from typing import Optional

from cou.apps.base import OpenStackApplication
from cou.apps.factory import AppFactory
from cou.steps import UnitUpgradeStep, UpgradeStep
from cou.utils.juju_utils import COUUnit
from cou.utils.nova_compute import verify_empty_hypervisor_before_upgrade
from cou.utils.openstack import OpenStackRelease

logger = logging.getLogger(__name__)


@AppFactory.register_application(["keystone"])
class Keystone(OpenStackApplication):
    """Keystone application.

    Keystone must wait for the entire model to be idle before declaring the upgrade complete.
    """

    wait_timeout = int(os.environ.get("COU_LONG_IDLE_TIMEOUT", 30 * 60))  # 30 min
    wait_for_model = True


@AppFactory.register_application(["octavia"])
class Octavia(OpenStackApplication):
    """Octavia application.

    Octavia required more time to settle before COU can continue.
    """

    wait_timeout = int(os.environ.get("COU_LONG_IDLE_TIMEOUT", 30 * 60))  # 30 min


@AppFactory.register_application(["nova-compute"])
class NovaCompute(OpenStackApplication):
    """Nova Compute application.

    Nova Compute must wait for the entire model to be idle before declaring the upgrade complete.
    """

    wait_timeout = int(os.environ.get("COU_LONG_IDLE_TIMEOUT", 30 * 60))  # 30 min
    wait_for_model = True
    upgrade_units_running_vms = False

    def upgrade_steps(
        self,
        target: OpenStackRelease,
        units: Optional[list[COUUnit]],
        force: bool,
    ) -> list[UpgradeStep]:
        """Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate upgrade steps,
        :type units: Optional[list[COUUnit]]
        :param force: Whether the plan generation should be forced
        :type force: bool
        :return: List of upgrade steps.
        :rtype: list[UpgradeStep]
        """
        if not units:
            units = list(self.units.values())

        app_steps = super().upgrade_steps(target, units, force)
        unit_steps = self._get_units_upgrade_steps(units, force)
        return app_steps + unit_steps

    def _get_units_upgrade_steps(self, units: list[COUUnit], force: bool) -> list[UpgradeStep]:
        """Get the upgrade steps for the units.

        :param units: Units to generate upgrade steps
        :type units: list[COUUnit]
        :param force: Whether the plan generation should be forced
        :type force: bool
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

            if not force:
                unit_steps.add_step(self._get_empty_hypervisor_step(unit))

            is_dependent = not force
            unit_steps.add_step(self._get_pause_unit_step(unit, is_dependent))
            unit_steps.add_step(self._get_openstack_upgrade_step(unit, is_dependent))
            unit_steps.add_step(self._get_resume_unit_step(unit, is_dependent))
            unit_steps.add_step(self._get_enable_scheduler_step(unit))
            units_steps.add_step(unit_steps)

        return [units_steps]

    def _get_empty_hypervisor_step(self, unit: COUUnit) -> UnitUpgradeStep:
        """Get the step to check if the unit has no VMs running.

        In case force is set to true, no check is done.

        :param unit: Unit to check the instance-count
        :type unit: COUUnit
        :return: Step to check if the hypervisor is empty.
        :rtype: UnitUpgradeStep
        """
        return UnitUpgradeStep(
            description=f"Check if unit {unit.name} has no VMs running before upgrading.",
            coro=verify_empty_hypervisor_before_upgrade(unit, self.model),
        )

    def _get_enable_scheduler_step(self, unit: COUUnit) -> UnitUpgradeStep:
        """Get the step to enable the scheduler, so the unit can create new VMs.

        :param unit: Unit to be enabled.
        :type unit: COUUnit
        :return: Step to enable the scheduler
        :rtype: UnitUpgradeStep
        """
        return UnitUpgradeStep(
            description=f"Enable nova-compute scheduler from unit: '{unit.name}'.",
            coro=self.model.run_action(
                unit_name=unit.name, action_name="enable", raise_on_failure=True
            ),
        )

    def _get_disable_scheduler_step(self, unit: COUUnit) -> UnitUpgradeStep:
        """Get the step to disable the scheduler,  so the unit cannot create new VMs.

        :param unit: Unit to be disabled.
        :type unit: COUUnit
        :return: Step to disable the scheduler
        :rtype: UnitUpgradeStep
        """
        return UnitUpgradeStep(
            description=f"Disable nova-compute scheduler from unit: '{unit.name}'.",
            coro=self.model.run_action(
                unit_name=unit.name, action_name="disable", raise_on_failure=True
            ),
        )
