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
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

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


@dataclass
class HypervisorGroup:
    """Group of hypervisors.

    For example, this can represent a group of all hypervisors in a single availability zone.
    """

    name: str
    apps: dict[str, list[COUUnit]]

    def __eq__(self, other: Any) -> bool:
        """Equal magic method for HypervisorGroup.

        :param other: HypervisorGroup object to compare.
        :type other: Any
        :return: True if equal False if different.
        :rtype: bool
        """
        if not isinstance(other, HypervisorGroup):
            return NotImplemented

        return other.name == self.name


class AZs(defaultdict):
    """AZs dictionary object with default value HypervisorGroup."""

    def __init__(self) -> None:
        """Initialize the Hypervisor class.

        The AZs represent default dict, with predefined HypervisorGroup as default value.
        """
        super().__init__(default_factory=None)

    def __missing__(self, key: str) -> HypervisorGroup:
        """Handle missing key in AZs.

        If key is missing in the AZs dict, the default value
        HypervisorGroup(name=key, apps=defaultdict(list) will be used. Like this we can always
        access the az["my-az"].name == "my-az" or az["my-az"].apps["my-app"].
        """
        self[key] = HypervisorGroup(name=key, apps=defaultdict(list))
        return self[key]


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

        The application should be sorted by upgrade order.

        :param apps: sorted list of OpenStack applications
        :type apps: list[OpenStackApplication]
        """
        # verify_apps(apps)
        self._apps = apps

    @property
    def apps(self) -> list[OpenStackApplication]:
        """Return a list of apps in the hypervisor class.

        :return: List of OpenStack applications.
        :rtype: list[OpenStackApplication]
        """
        return self._apps

    @property
    def azs(self) -> AZs:
        """Returns a list of AZs defined in individual applications.

        Each AZ contains a dictionary of application name and all units in the AZ.
        eg.
        az1:
        - cinder:
          - cinder/0
          - cinder/1
          - cinder/2
        - nova-compute
          - nova-compute/0
          - nova-compute/1
          - nova-compute/2
        ...
        az2
        - cinder
          -cinder/3
        ...
        ...

        :return: dictionary with key as az name and value as HypervisorGroup
        :rtype: dict[str, HypervisorGroup]
        :raises ApplicationError: if there is unit without az defined
        """
        azs = AZs()
        for app in self.apps:
            for unit in app.units.values():
                # NOTE(rgildein): If there is no AZ, we will use empty string and all units will
                #                 belong to a single group.
                az = unit.machine.az or ""
                azs[az].apps[app.name].append(unit)

        return azs

    def _generate_pre_upgrade_plan(self) -> PreUpgradeStep:
        """Generate pre upgrade plan for all applications.

        This section should create a plan with steps like changing charm config option, etc.

        :return: Pre-upgrade step with all needed pre-upgrade steps.
        :rtype: PreUpgradeStep
        """
        raise NotImplementedError

    def _generate_hypervisor_group_upgrade_plan(
        self, target: OpenStackRelease, group: HypervisorGroup
    ) -> HypervisorUpgradePlan:
        """Generate upgrade plan for a single hypervisor group.

        :param target: OpenStack codename to upgrade.
        :type target: OpenStackRelease
        :param group: HypervisorGroup object
        :type group: HypervisorGroup
        :return: Upgrade plan for hypervisor group.
        :rtype: HypervisorUpgradePlan
        """
        plan = HypervisorUpgradePlan(description=f"Upgrade plan for '{group.name}' to {target}")
        for app in self.apps:
            if app.name not in group.apps:
                logger.debug(
                    "skipping application %s because it is not part of group %s",
                    app.name,
                    group.name,
                )
                continue

            units = group.apps[app.name]
            logger.info("generating upgrade steps for %s app and %s units", app.name, units)
            plan.sub_steps = app.upgrade_steps(target, units)  # type: ignore[call-arg, assignment]

        return plan

    def _generate_post_upgrade_plan(self) -> PostUpgradeStep:
        """Generate post upgrade plan for all applications.

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

        # pre upgrade steps
        logger.debug("generating pre upgrade steps")
        plan.add_step(self._generate_pre_upgrade_plan())

        # upgrade steps
        for az, group in self.azs.items():
            logger.debug("generating upgrade steps for %s AZ", az)
            plan.add_step(self._generate_hypervisor_group_upgrade_plan(target, group))

        # post upgrade steps
        logger.debug("generating post upgrade steps")
        plan.add_step(self._generate_post_upgrade_plan())

        return plan
