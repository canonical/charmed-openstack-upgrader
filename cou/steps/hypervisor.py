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
    UpgradeStep,
)
from cou.utils.juju_utils import Machine, Unit
from cou.utils.openstack import OpenStackRelease

logger = logging.getLogger(__name__)


@dataclass
class HypervisorGroup:
    """Group of hypervisors.

    For example, this can represent a group of all hypervisors in a single availability zone.
    """

    name: str
    app_units: dict[str, list[Unit]]

    def __eq__(self, other: Any) -> bool:
        """Equal magic method for HypervisorGroup.

        :param other: HypervisorGroup object to compare.
        :type other: Any
        :return: True if equal False if different.
        :rtype: bool
        """
        if not isinstance(other, HypervisorGroup):
            return NotImplemented

        return other.name == self.name and other.app_units == self.app_units


class AZs(defaultdict):
    """AZs dictionary object with default value HypervisorGroup."""

    def __init__(self) -> None:
        """Initialize the Hypervisor class.

        The AZs represent default dict, with predefined HypervisorGroup as default value.
        """
        super().__init__()
        self.default_factory = None

    def __missing__(self, key: str) -> HypervisorGroup:
        """Handle missing keys in AZs.

        If a key is missing in the AZs dict, the default value
        HypervisorGroup(name=key, apps=defaultdict(list) will be used. Like this we can always
        access the az["my-az"].name == "my-az" or az["my-az"].apps["my-app"].
        """
        self[key] = HypervisorGroup(name=key, app_units=defaultdict(list))
        return self[key]


class HypervisorUpgradePlanner:
    """Planner for all hypervisor updates.

    This planner is meant to be used to upgrade machines contains the nova-compute application.
    """

    def __init__(self, apps: list[OpenStackApplication], machines: list[Machine]) -> None:
        """Initialize the Hypervisor class.

        The application should be sorted by upgrade order.

        :param apps: sorted list of OpenStack applications
        :type apps: list[OpenStackApplication]
        :param machines: Hypervisor machines to generate upgrade plan.
        :type machines: list[Machine]
        """
        self._apps = apps
        self._machines = machines

    @property
    def apps(self) -> list[OpenStackApplication]:
        """Return a list of apps in the hypervisor class.

        :return: List of OpenStack applications.
        :rtype: list[OpenStackApplication]
        """
        return self._apps

    @property
    def machines(self) -> list[Machine]:
        """Return a list of hypervisor machines to upgrade.

        :return: List of hypervisor machines.
        :rtype: list[Machine]
        """
        return self._machines

    def get_azs(self, target: OpenStackRelease) -> AZs:
        """Return a list of AZs defined in individual applications.

        Each AZ contains a dictionary of application name and all units not yet upgraded
        in the AZ for a certain target.
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

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: dictionary with key as az name and value as HypervisorGroup
        :rtype: dict[str, HypervisorGroup]
        """
        azs = AZs()
        for app in self.apps:
            for unit in app.units.values():
                if unit.machine not in self.machines:
                    logger.debug("skipping machine %s", unit.machine.machine_id)
                    continue

                unit_os_release = app.get_latest_os_version(unit)
                if unit_os_release >= target:
                    logger.info("skipping unit %s is already on %s", unit.name, unit_os_release)
                    continue

                # NOTE(rgildein): If there is no AZ, we will use an empty string and group all
                #                 units to a single hypervisor group.
                az = unit.machine.az or ""
                azs[az].app_units[app.name].append(unit)

        return azs

    def _upgrade_plan_sanity_checks(
        self, target: OpenStackRelease, group: HypervisorGroup
    ) -> None:
        """Run sanity checks before generating upgrade plan for hypervisor group.

        :param target: OpenStack codename to upgrade.
        :type target: OpenStackRelease
        :param group: HypervisorGroup object
        :type group: HypervisorGroup
        """
        for app in self.apps:
            if app.name not in group.app_units:
                logger.debug(
                    "skipping application %s because it is not part of group %s",
                    app.name,
                    group.name,
                )
                continue

            units = group.app_units[app.name]
            logger.info("running sanoty checks for %s units of %s app", app.name, units)
            # Note(rgildein): We don't catch the error here because we shouldn't generate any
            #                 update plan if sanity checks for any application in the group fails.
            app.upgrade_plan_sanity_checks(target, units)

    def _generate_pre_upgrade_steps(
        self, target: OpenStackRelease, group: HypervisorGroup
    ) -> list[PreUpgradeStep]:
        """Generate pre upgrade plan for all applications.

        This section should create a list of steps like changing charm config option, etc.

        :param target: OpenStack codename to upgrade.
        :type target: OpenStackRelease
        :param group: HypervisorGroup object
        :type group: HypervisorGroup
        :return: List of pre-upgrade steps.
        :rtype: list[PreUpgradeStep]
        """
        steps = []
        for app in self.apps:
            if app.name not in group.app_units:
                logger.debug(
                    "skipping application %s because it is not part of group %s",
                    app.name,
                    group.name,
                )
                continue

            units = group.app_units[app.name]
            logger.info("generating pre-upgrade steps for %s units of %s app", app.name, units)
            steps.extend(app.pre_upgrade_steps(target, units))

        return steps

    def _generate_upgrade_steps(
        self, target: OpenStackRelease, force: bool, group: HypervisorGroup
    ) -> list[UpgradeStep]:
        """Generate upgrade plan for a single hypervisor group.

        :param target: OpenStack codename to upgrade.
        :type target: OpenStackRelease
        :param force: Whether the plan generation should be forced
        :type force: bool
        :param group: HypervisorGroup object
        :type group: HypervisorGroup
        :return: Upgrade plan for hypervisor group.
        :rtype: HypervisorUpgradePlan
        """
        steps = []
        for app in self.apps:
            if app.name not in group.app_units:
                logger.debug(
                    "skipping application %s because it is not part of group %s",
                    app.name,
                    group.name,
                )
                continue

            units = group.app_units[app.name]
            logger.info("generating upgrade steps for %s units of %s app", app.name, units)
            steps.extend(app.upgrade_steps(target, units, force))

        return steps

    def _generate_post_upgrade_steps(
        self, target: OpenStackRelease, group: HypervisorGroup
    ) -> list[PostUpgradeStep]:
        """Generate post upgrade plan for hypervisor group.

        This section should create a list of steps like checking versions, status of
        application, etc.

        :param target: OpenStack codename to upgrade.
        :type target: OpenStackRelease
        :param group: HypervisorGroup object
        :type group: HypervisorGroup
        :return: List of post-upgrade steps.
        :rtype: list[PostUpgradeStep]
        """
        steps = []
        for app in self.apps:
            if app.name not in group.app_units:
                logger.debug(
                    "skipping application %s because it is not part of group %s",
                    app.name,
                    group.name,
                )
                continue

            units = group.app_units[app.name]
            logger.info("generating post-upgrade steps for %s units of %s app", app.name, units)
            steps.extend(app.post_upgrade_steps(target, units=units))

        return steps

    def generate_upgrade_plan(self, target: OpenStackRelease, force: bool) -> UpgradePlan:
        """Generate full upgrade plan for all hypervisors.

        This plan will be based on multiple HypervisorUpgradePlan.

        :param target: OpenStack codename to upgrade.
        :type target: OpenStackRelease
        :param force: Whether the plan generation should be forced
        :type force: bool
        :return: Full upgrade plan
        :rtype: UpgradePlan
        """
        plan = UpgradePlan("Upgrading all applications deployed on machines with hypervisor.")
        for az, group in self.get_azs(target).items():
            hypervisor_plan = HypervisorUpgradePlan(
                f"Upgrade plan for '{group.name}' to '{target}'"
            )
            # snity checks
            logger.debug("running sanity checks for %s AZ", az)
            self._upgrade_plan_sanity_checks(target, group)

            # pre upgrade steps
            logger.debug("generating pre-upgrade steps for %s AZ", az)
            hypervisor_plan.add_steps(self._generate_pre_upgrade_steps(target, group))

            # upgrade steps
            logger.debug("generating upgrade steps for %s AZ", az)
            hypervisor_plan.add_steps(self._generate_upgrade_steps(target, force, group))

            # post upgrade steps
            logger.debug("generating post-upgrade steps for %s AZ", az)
            hypervisor_plan.add_steps(self._generate_post_upgrade_steps(target, group))

            plan.add_step(hypervisor_plan)

        return plan
