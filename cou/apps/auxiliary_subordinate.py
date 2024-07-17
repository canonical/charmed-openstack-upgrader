#  Copyright 2023 Canonical Limited
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
"""Auxiliary subordinate application class."""

# We have to disable duplicate code because some code are intended to add to
# the child class, it cannot be added to parent class to reuse the code.
#
# pylint: disable=duplicate-code

from typing import Optional

from cou.apps.auxiliary import OVN, AuxiliaryApplication
from cou.apps.factory import AppFactory
from cou.apps.subordinate import SubordinateApplication
from cou.steps import PostUpgradeStep, PreUpgradeStep
from cou.utils.juju_utils import Unit
from cou.utils.openstack import OpenStackRelease


@AppFactory.register_application(["mysql-router", "ceph-dashboard"])
class AuxiliarySubordinateApplication(SubordinateApplication, AuxiliaryApplication):
    """Auxiliary subordinate application class."""


@AppFactory.register_application(["ovn-chassis"])
class OVNSubordinate(OVN, AuxiliarySubordinateApplication):
    """OVN subordinate application class."""

    def _check_ovn_support(self) -> None:
        """Check OVN version.

        :raises ApplicationError: When workload version is lower than 22.03.0.
        """
        OVNSubordinate._validate_ovn_support(self.workload_version)

    def _check_auto_restarts(self) -> None:
        """No-op, skip check auto restarts option.

        This method override the parent class's `_check_auto_restarts()` method
        because the parent class's will raise an `ApplicationError` if
        `enable-auto-restarts` is `True`.
        """

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
        # OVN subordinate charm does not have upgrade_step; the "upgrade" is
        # done during the pre-upgrade step, so we need to put the run deferred
        # hook step before pre-upgrade step.
        steps = []
        if self.config.get("enable-auto-restarts", {}).get("value") is False:
            steps.extend(
                self.get_run_deferred_hooks_and_restart_pre_upgrade_step(self.subordinate_units)
            )
        steps.extend(super().pre_upgrade_steps(target, units))
        return steps

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
        steps = []
        if self.config.get("enable-auto-restarts", {}).get("value") is False:
            steps.extend(
                self.get_run_deferred_hooks_and_restart_post_upgrade_step(self.subordinate_units)
            )
        steps.extend(super().post_upgrade_steps(target, units))
        return steps


@AppFactory.register_application(["hacluster"])
class HACluster(AuxiliarySubordinateApplication):
    """HACluster application class."""

    # hacluster can use channels 2.0.3 or 2.4 on focal.
    # COU changes to 2.4 if the channel is set to 2.0.3
    multiple_channels = True
