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

from cou.apps.base import LONG_IDLE_TIMEOUT, OpenStackApplication
from cou.apps.factory import AppFactory
from cou.exceptions import ActionFailed, ApplicationNotSupported
from cou.steps import PostUpgradeStep, PreUpgradeStep, UnitUpgradeStep, UpgradeStep
from cou.utils.juju_utils import Model, Unit
from cou.utils.nova_compute import verify_empty_hypervisor
from cou.utils.openstack import OpenStackRelease

logger = logging.getLogger(__name__)


@AppFactory.register_application(["keystone"])
class Keystone(OpenStackApplication):
    """Keystone application.

    Keystone must wait for the entire model to be idle before declaring the upgrade complete.
    """

    wait_timeout = LONG_IDLE_TIMEOUT
    charm_refresh_timeout = 1200
    wait_for_model = True


@AppFactory.register_application(["octavia"])
class Octavia(OpenStackApplication):
    """Octavia application.

    Octavia required more time to settle before COU can continue.
    """

    wait_timeout = LONG_IDLE_TIMEOUT


@AppFactory.register_application(["nova-compute"])
class NovaCompute(OpenStackApplication):
    """Nova Compute application.

    Nova Compute must wait for the entire model to be idle before declaring the upgrade complete.
    """

    wait_timeout = LONG_IDLE_TIMEOUT
    wait_for_model = True
    upgrade_units_running_vms = False

    def pre_upgrade_steps(
        self, target: OpenStackRelease, units: Optional[list[Unit]]
    ) -> list[PreUpgradeStep]:
        """Pre Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate upgrade plan
        :type units: Optional[list[COUUnit]]
        :return: List of pre upgrade steps.
        :rtype: list[PreUpgradeStep]
        """
        return self._get_disable_scheduler_step(units) + super().pre_upgrade_steps(target, units)

    def upgrade_steps(
        self, target: OpenStackRelease, units: Optional[list[Unit]], force: bool
    ) -> list[UpgradeStep]:
        """Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate upgrade steps.
        :type units: Optional[list[Unit]]
        :param force: Whether the plan generation should be forced.
        :type force: bool
        :return: List of upgrade steps.
        :rtype: list[UpgradeStep]
        """
        if units is None:
            units = list(self.units.values())

        return super().upgrade_steps(target, units, force)

    def post_upgrade_steps(
        self, target: OpenStackRelease, units: Optional[list[Unit]]
    ) -> list[PostUpgradeStep]:
        """Post Upgrade steps planning.

        Wait until the application reaches the idle state and then check the target workload.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate post upgrade plan
        :type units: Optional[list[Unit]]
        :return: List of post upgrade steps.
        :rtype: list[PostUpgradeStep]
        """
        return self._get_enable_scheduler_step(units) + super().post_upgrade_steps(target, units)

    def _get_unit_upgrade_steps(self, unit: Unit, force: bool) -> UnitUpgradeStep:
        """Get the upgrade steps for a single unit.

        :param unit: Unit to generate upgrade steps
        :type unit: Unit
        :param force: Whether the unit step generation should be forced
        :type force: bool
        :return: Unit upgrade step
        :rtype: UnitUpgradeStep
        """
        unit_plan = UnitUpgradeStep(f"Upgrade plan for unit '{unit.name}'")

        if not force:
            unit_plan.add_step(self._get_empty_hypervisor_step(unit))

        is_dependent = not force
        unit_plan.add_step(self._get_pause_unit_step(unit, is_dependent))
        unit_plan.add_step(self._get_openstack_upgrade_step(unit, is_dependent))
        unit_plan.add_step(self._get_resume_unit_step(unit, is_dependent))

        return unit_plan

    def _get_empty_hypervisor_step(self, unit: Unit) -> UnitUpgradeStep:
        """Get the step to check if the unit has no VMs running.

        In case force is set to true, no check is done.

        :param unit: Unit to check the instance-count.
        :type unit: Unit
        :return: Step to check if the hypervisor is empty.
        :rtype: UnitUpgradeStep
        """
        return UnitUpgradeStep(
            f"Verify that unit '{unit.name}' has no VMs running",
            coro=verify_empty_hypervisor(unit, self.model),
        )

    def _get_enable_scheduler_step(self, units: Optional[list[Unit]]) -> list[PostUpgradeStep]:
        """Get the step to enable the scheduler, so the unit can create new VMs.

        :param units: Units to be enabled.
        :type units: Optional[list[Unit]]
        :return: Steps to enable the scheduler on units
        :rtype: list[PostUpgradeStep]
        """
        units_to_enable = self.units.values() if units is None else units
        return [
            PostUpgradeStep(
                description=f"Enable nova-compute scheduler from unit: '{unit.name}'",
                coro=self.model.run_action(
                    unit_name=unit.name, action_name="enable", raise_on_failure=True
                ),
            )
            for unit in units_to_enable
        ]

    def _get_disable_scheduler_step(self, units: Optional[list[Unit]]) -> list[PreUpgradeStep]:
        """Get the step to disable the scheduler, so the unit cannot create new VMs.

        :param units: Units to be disabled.
        :type units:  Optional[list[Unit]]
        :return: Steps to disable the scheduler on units
        :rtype: list[PreUpgradeStep]
        """
        units_to_disable = self.units.values() if units is None else units
        return [
            PreUpgradeStep(
                description=f"Disable nova-compute scheduler from unit: '{unit.name}'",
                coro=self.model.run_action(
                    unit_name=unit.name, action_name="disable", raise_on_failure=True
                ),
            )
            for unit in units_to_disable
        ]

    def _get_resume_unit_step(self, unit: Unit, dependent: bool = False) -> UnitUpgradeStep:
        """Override the resume unit step, because extra error handling is required.

        :param unit: Unit to be resumed.
        :type unit: Unit
        :param dependent: Whether the step is dependent of another step, defaults to False
        :type dependent: bool, optional
        :return: Step to resume a unit.
        :rtype: UnitUpgradeStep
        """
        # workaround for https://bugs.launchpad.net/charm-ceilometer-agent/+bug/1947585
        return UnitUpgradeStep(
            description=(f"Resume the unit: '{unit.name}'"),
            coro=resume_nova_compute_unit(self.model, unit),
            dependent=dependent,
        )


async def resume_nova_compute_unit(model: Model, unit: Unit) -> None:
    """Run the resume action on nova-compute, with workarounds.

    Includes a workaround for https://bugs.launchpad.net/charm-ceilometer-agent/+bug/1947585

    :param model: juju model to work with
    :type model: Model
    :param unit: nova-compute unit to resume
    :type unit: Unit
    :raises ActionFailed: when the resume action fails with an unknown failure
    """
    action = await model.run_action(unit.name, "resume", raise_on_failure=False)

    # If the action was successful, there is nothing left to do
    if action.status == "completed":
        return

    # If it failed because of https://bugs.launchpad.net/charm-ceilometer-agent/+bug/1947585 ,
    # apply the workaround.
    if "Services not running that should be: ceilometer-agent-compute" in action.safe_data.get(
        "message", ""
    ):
        logger.debug("Resume failed because ceilometer-agent-compute not running.")
        logger.debug("Restarting ceilometer-agent-compute on %s", unit.name)
        await model.run_on_unit(unit.name, "sudo systemctl restart ceilometer-agent-compute")

        # Update status manually, otherwise nova-compute and ceilometer-agent
        # will be blocked until next update-status hook.
        await model.update_status(unit.name)
        for subordinate in unit.subordinates:
            if subordinate.charm == "ceilometer-agent":
                await model.update_status(subordinate.name)

    # Otherwise, it's an unknown error, so raise the exception
    else:
        raise ActionFailed(action)


@AppFactory.register_application(["swift-proxy", "swift-storage"])
class Swift(OpenStackApplication):
    """Swift application.

    Swift applications, including swift-proxy and swift-storage, are considered as
    valid OpenStack components, but not currently supported by COU for upgrade.
    """

    def upgrade_plan_sanity_checks(self, target: OpenStackRelease) -> None:
        """Run sanity checks before generating upgrade plan.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :raises ApplicationNotSupported: When application is known but not currently
                                         supported by COU.
        """
        raise ApplicationNotSupported(
            f"'{self.name}' application is not currently supported by COU. Please manually "
            "upgrade it."
        )


@AppFactory.register_application(["neutron-api"])
class NeutronApi(OpenStackApplication):
    """Neutron API application class."""

    def pre_upgrade_steps(
        self, target: OpenStackRelease, units: Optional[list[Unit]]
    ) -> list[PreUpgradeStep]:
        """Pre Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate upgrade plan
        :type units: Optional[list[Unit]]
        :return: List of pre upgrade steps.
        :rtype: list[PreUpgradeStep]
        """
        steps = self._verify_nova_compute_step(target)
        steps.extend(super().pre_upgrade_steps(target, units))
        return steps
