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
"""OVN application class."""
from typing import Callable, Optional

from packaging.version import Version

from cou.apps.app import AppFactory
from cou.apps.auxiliary import OpenStackAuxiliaryApplication
from cou.apps.auxiliary_subordinate import OpenStackAuxiliarySubordinateApplication
from cou.exceptions import ApplicationError
from cou.steps import UpgradeStep
from cou.utils.openstack import OpenStackRelease


@AppFactory.register_application(["ovn-central", "ovn-dedicated-chassis"])
class OvnPrincipalApplication(OpenStackAuxiliaryApplication):
    """Ovn central application class."""

    def pre_upgrade_plan(self, target: OpenStackRelease) -> list[Optional[UpgradeStep]]:
        """Pre Upgrade planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Plan that will add pre upgrade as sub steps.
        :rtype: list[Optional[UpgradeStep]]
        """
        self.check_ovn_workload_version()
        return super().pre_upgrade_plan(target)

    @property
    def ovn_version_lower_than_22(self) -> bool:
        """Check if OVN version is lower than 22.03.

        :return: True if OVN version is lower than 22.03.
        :rtype: bool
        """
        return any((Version(unit.workload_version) < Version("22.03.0") for unit in self.units))

    def check_ovn_workload_version(self) -> None:
        """Check whether it is necessary to manually upgrade OVN to 22.03.

        :raises ApplicationError: When workload version is lower than 22.03.0.
        """
        if self.ovn_version_lower_than_22:
            raise ApplicationError(
                (
                    "OVN versions lower than 22.03 are not supported. It's necessary to upgrade "
                    "OVN to 22.03 before upgrading the cloud. Follow the instructions at: "
                    "https://docs.openstack.org/charm-guide/latest/project/procedures/"
                    "ovn-upgrade-2203.html"
                )
            )


@AppFactory.register_application(["ovn-chassis"])
class OvnSubordinateApplication(OpenStackAuxiliarySubordinateApplication):
    """Ovn chassis application class."""

    check_ovn_workload_version: Callable = OvnPrincipalApplication.check_ovn_workload_version

    def pre_upgrade_plan(self, target: OpenStackRelease) -> list[Optional[UpgradeStep]]:
        """Pre Upgrade planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Plan that will add pre upgrade as sub steps.
        :rtype: list[Optional[UpgradeStep]]
        """
        self.check_ovn_workload_version()
        return super().pre_upgrade_plan(target)

    @property
    def ovn_version_lower_than_22(self) -> bool:
        """Check if OVN version is lower than 22.03.

        :return: True if OVN version is lower than 22.03.
        :rtype: bool
        """
        return Version(self.status.workload_version) < Version("22.03.0")
