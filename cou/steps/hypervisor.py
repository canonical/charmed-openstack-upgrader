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

from cou.apps.base import OpenStackApplication
from cou.steps import (
    HypervisorUpgradePlan,
    PostUpgradeStep,
    PreUpgradeStep,
    UpgradePlan,
)
from cou.utils.juju_utils import COUUnit
from cou.utils.openstack import OpenStackRelease

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HypervisorMachine:
    """Hypervisor machine containing units for multiple applications."""

    name: str
    units: list[COUUnit]


@dataclass(frozen=True)
class HypervisorGroup:
    """Group of hypervisors.

    For example, this can represent a group of all hypervisors in a single availability zone.
    """

    name: str
    hypervisors: list[HypervisorMachine]


def verify_apps(apps: list[OpenStackApplication]) -> None:
    """Verify OpenStack applications.

    This function will verify that all machines contain nova-compute application.

    :param apps: list of OpenStack applications
    :type apps: list[OpenStackApplication]
    """
    raise NotImplementedError


class HypervisorUpgradePlanner:
    """Planner for all hypervisor updates.

    This planner is meant to be used to upgrade machines contains the nova-compute application.
    """

    def __init__(self, apps: list[OpenStackApplication]) -> None:
        """Initialize the Hypervisor class.

        :param apps: list of OpenStack applications
        :type apps: list[OpenStackApplication]
        """
        self._apps = apps

    @property
    def apps(self) -> list[OpenStackApplication]:
        """Return a list of apps in the hypervisor class.

        :return: List of OpenStack applications.
        :rtype: list[OpenStackApplication]
        """
        return self._apps

    @property
    def azs(self) -> list[HypervisorGroup]:
        """Returns a list of AZs defined in individual applications.

        Each AZ contains a sorted list hypervisors, where each hypervisor has sorted list of units.
        The order of units depends on the order in which they needs to be upgraded.
        eg.
        az1:
        - hypervisor0:
          - cinder/0
          - nova-compute/0
        - hypervisor1:
          - cinder/1
          - nova-compute/1
        ...

        :return: List of availability zones.
        :rtype: list[HypervisorGroup]
        """
        raise NotImplementedError

    def _generate_pre_upgrade_plan(self, target: OpenStackRelease) -> list[PreUpgradeStep]:
        """Generate pre upgrade plan for all applications.

        This section should create a list of steps like changing charm config option, etc.

        :param target: OpenStack codename to upgrade.
        :type target: OpenStackRelease
        :return: List of pre-upgrade steps.
        :rtype: list[PreUpgradeStep]
        """
        steps = []
        for app in self.apps:
            steps.extend(app.pre_upgrade_steps(target, units=None))
            logger.info("generating pre-upgrade steps for %s app", app.name)

        return steps

    def _generate_hypervisor_upgrade_plan(
        self, hypervisor: HypervisorMachine
    ) -> HypervisorUpgradePlan:
        """Genarete upgrade plan for a single hypervisor.

        Each hypervisor upgrade consists of a UnitUpgradeStep, so all substeps should be based
        on UnitUpgradeStep.

        :param hypervisor: hypervisor object
        :type hypervisor: Hypervisor
        :return: Upgrade plan for hypervisor.
        :rtype: HypervisorUpgradePlan
        """
        raise NotImplementedError

    def _generate_post_upgrade_plan(self, target: OpenStackRelease) -> list[PostUpgradeStep]:
        """Generate post upgrade plan for all applications.

        This section should create a list of steps like checking versions, status of
        application, etc.

        :param target: OpenStack codename to upgrade.
        :type target: OpenStackRelease
        :return: List of post-upgrade steps.
        :rtype: list[PostUpgradeStep]
        """
        steps = []
        # NOTE(rgildein): Using the reverse order of post-upgrade steps, so these steps starts from
        #                 subordinate or colocated apps and not nova-compute.
        for app in self.apps[::-1]:
            steps.extend(app.post_upgrade_steps(target, units=None))
            logger.info("generating post-upgrade steps for %s app", app.name)

        return steps

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
        plan.sub_steps.extend(self._generate_pre_upgrade_plan(target))

        logger.debug("generating post upgrade steps")
        plan.sub_steps.extend(self._generate_post_upgrade_plan(target))

        return plan
