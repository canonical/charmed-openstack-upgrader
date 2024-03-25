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
from typing import Optional

from cou.apps.auxiliary import AuxiliaryApplication
from cou.apps.factory import AppFactory
from cou.apps.subordinate import SubordinateBase
from cou.exceptions import ApplicationError
from cou.steps import PreUpgradeStep
from cou.utils.app_utils import validate_ovn_support
from cou.utils.juju_utils import Unit
from cou.utils.openstack import AUXILIARY_SUBORDINATES, OpenStackRelease


@AppFactory.register_application(AUXILIARY_SUBORDINATES)
class AuxiliarySubordinateApplication(SubordinateBase, AuxiliaryApplication):
    """Auxiliary subordinate application class."""

    @property
    def current_os_release(self) -> OpenStackRelease:
        """Infer the OpenStack release from subordinate charm's channel.

        We cannot determine the OpenStack release base on workload packages because the principal
        charm has already upgraded the packages.
        :return: OpenStackRelease object.
        :rtype: OpenStackRelease
        """
        return self.channel_codename


@AppFactory.register_application(["ovn-chassis"])
class OvnSubordinate(AuxiliarySubordinateApplication):
    """Ovn subordinate application class."""

    def upgrade_plan_sanity_checks(
        self, target: OpenStackRelease, units: Optional[list[Unit]]
    ) -> None:
        """Run sanity checks before generating upgrade plan.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate upgrade plan, defaults to None
        :type units: Optional[list[Unit]]
        :raises ApplicationError: When enable-version-pinning is True
        """
        super().upgrade_plan_sanity_checks(target, units)
        if self.config["enable-version-pinning"].get("value"):
            raise ApplicationError(
                f"'{self.name}' should set 'enable-version-pinning' before upgrading"
            )

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
        validate_ovn_support(self.workload_version)
        return super().pre_upgrade_steps(target, units)
