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

"""Nova Compute application class."""
import logging

from cou.apps.base import ApplicationUnit, OpenStackApplication
from cou.apps.factory import AppFactory
from cou.steps import UnitUpgradeStep
from cou.utils.nova_compute import _get_instance_count_to_upgrade

logger = logging.getLogger(__name__)


@AppFactory.register_application(["keystone"])
class NovaCompute(OpenStackApplication):
    """Nova Compute application.

    Nova Compute must wait for the entire model to be idle before declaring the upgrade complete.
    """

    wait_timeout = 30 * 60  # 30 min
    wait_for_model = True
    force_upgrade = False

    @property
    def need_canary_node(self) -> bool:
        os_versions_units = self._get_os_from_units()
        return len(os_versions_units.keys()) == 1

    def _get_workload_upgrade_steps(
        self, units: list[ApplicationUnit]
    ) -> list[list[UnitUpgradeStep]]:
        units_steps = []

        if self.need_canary_node:
            units = [units[0]]

        for unit in units:
            unit_steps = [
                self._get_disable_scheduler_step(unit),
                self._get_empty_hypervisor_check(unit),
                self._get_pause_unit_step(unit),
                self._get_openstack_upgrade_step(unit),
                self._get_resume_unit_step(unit),
                self._get_enable_scheduler_step(unit),
            ]
            units_steps.append(unit_steps)
        return units_steps

    def _get_empty_hypervisor_check(self, unit) -> UnitUpgradeStep:
        if self.force:
            return UnitUpgradeStep()
        return UnitUpgradeStep(
            description="Run the instance-count to upgrade",
            coro=_get_instance_count_to_upgrade(unit),
        )

    def _get_enable_scheduler_step(self, unit: ApplicationUnit) -> UnitUpgradeStep:
        """Get the step to enable the scheduler, so the unit can create new VMs.

        :param unit: Unit to be enabled.
        :type unit: ApplicationUnit
        :return: Step to enable the scheduler
        :rtype: UnitUpgradeStep
        """
        return UnitUpgradeStep(
            description=f"Pause the unit: '{unit.name}'.",
            coro=self.model.run_action(
                unit_name=unit.name, action_name="enable", raise_on_failure=True
            ),
        )

    def _get_disable_scheduler_step(self, unit: ApplicationUnit) -> UnitUpgradeStep:
        """Get the step to disable the scheduler,  so the unit cannot create new VMs.

        :param unit: Unit to be disabled.
        :type unit: ApplicationUnit
        :return: Step to enable the scheduler
        :rtype: UnitUpgradeStep
        """
        return UnitUpgradeStep(
            description=f"Pause the unit: '{unit.name}'.",
            coro=self.model.run_action(
                unit_name=unit.name, action_name="enable", raise_on_failure=True
            ),
        )
