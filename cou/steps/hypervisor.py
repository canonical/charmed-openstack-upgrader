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

"""Hypervisor planner."""
import logging
from dataclasses import dataclass

from cou.apps.base import ApplicationUnit, OpenStackApplication
from cou.steps import (
    HypervisorUpgradePlan,
    PostUpgradeStep,
    PreUpgradeStep,
    UpgradePlan,
)
from cou.utils.openstack import OpenStackRelease

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Hypervisor:
    """Hypervisor containing units for multiple applications."""

    name: str
    units: list[ApplicationUnit]


@dataclass(frozen=True)
class AZ:
    """Availability Zone hypervisors in the az."""

    name: str
    hypervisors: list[Hypervisor]


def verify_apps(apps: list[OpenStackApplication]) -> None:
    """Verify OpenStack applications.

    This function will verify that all machines contain nova-compute application.

    :param apps: list of OpenStack applications
    :type apps: list[OpenStackApplication]
    """
    raise NotImplementedError


class HypervisorUpgradePlanner:
    """Planer for all hypervisor updates.

    This planner is meant to be used to upgrade machines contains the nova-compute application.
    """

    def __init__(self, apps: list[OpenStackApplication]) -> None:
        """Initialize the Hypervisor class.

        :param apps: list of OpenStack applications
        :type apps: list[OpenStackApplication]
        """
        verify_apps(apps)
        self._apps = apps

    @property
    def apps(self) -> list[OpenStackApplication]:
        """Return list of apps in hypervisor class."""
        return self._apps

    @property
    def azs(self) -> list[AZ]:
        """Returns list of AZs defined in individual applications.

        Each AZ contains a sorted list hypervisors, where each hypervisor has sorted list of units.
        The order of units depends on the order in which they needs to be upgraded.
        eg.
        az1:
        - hypervisor0:
          - nova-compute/0
          - cinder/0
        - hypervisor1:
          - nova-compute/1
          - cinder/1
        ...
        """
        raise NotImplementedError

    def _generate_pre_upgrade_plan(self) -> PreUpgradeStep:
        """Generate pre upgrade plan all application.

        This section should create a plan with steps like changing Juju config option, etc.

        :return: Pre-upgrade step with all needed pre-upgrade steps.
        :rtype: PreUpgradeStep
        """
        raise NotImplementedError

    def _generate_hypervisor_upgrade_plan(self, hypervisor: Hypervisor) -> HypervisorUpgradePlan:
        """Genarete upgrade plan for single hypevisors.

        Each hypervisor upgrade consists of a UnitUpgradeStep, so all substeps should be based
        on UnitUpgradeStep.

        :param hypervisor: hypervisor object
        :type hypervisor: Hypervisor
        :return: Upgrade plan for hypervisor.
        :rtype: HypervisorUpgradePlan
        """
        raise NotImplementedError

    def _generate_post_upgrade_plan(self) -> PostUpgradeStep:
        """Generate post upgrade plan all application.

        This section should create a plan with steps like checking versions, status of
        application, etc.

        :return: Post-upgrade step with all needed post-upgrade steps.
        :rtype: PostUpgradeStep
        """
        raise NotImplementedError

    # pylint: disable=unused-argument
    def generate_upgrade_plan(self, target: OpenStackRelease) -> UpgradePlan:
        """Generate full upgrade plan for all hypervisors.

        This plan will be based on multiple HypervisorUpgradePlan.

        :param target: OpenStack codename to upgrade.
        :type target: OpenStackRelease
        :return: Full upgrade plan
        :rtype: UpgradePlan
        """
        plan = UpgradePlan("Upgrading all applications deployed on machines with hypervisor.")
        logger.debug("generating pre upgrade steps")
        plan.add_step(self._generate_pre_upgrade_plan())
        for az in self.azs:
            for hypervisor in az.hypervisors:
                logger.debug("generating upgrade steps for %s in %s AZ", hypervisor.name, az.name)
                plan.add_step(self._generate_hypervisor_upgrade_plan(hypervisor))

        logger.debug("generating post upgrade steps")
        plan.add_step(self._generate_post_upgrade_plan())

        return plan
