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
from typing import Optional

from packaging.version import Version

from cou.apps.app import AppFactory
from cou.apps.auxiliary import OpenStackAuxiliaryApplication
from cou.apps.auxiliary_subordinate import OpenStackAuxiliarySubordinateApplication
from cou.exceptions import ApplicationError
from cou.steps import UpgradeStep
from cou.utils.openstack import OpenStackRelease


@AppFactory.register_application(["ovn-central", "ovn-dedicated-chassis"])
class OvnPrincipalApplication(OpenStackAuxiliaryApplication):
    """Ovn principal application class."""

    def pre_upgrade_plan(self, target: OpenStackRelease) -> list[Optional[UpgradeStep]]:
        """Pre Upgrade planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Plan that will add pre upgrade as sub steps.
        :rtype: list[Optional[UpgradeStep]]
        """
        for unit in self.units:
            validate_ovn_support(unit.workload_version)
        return super().pre_upgrade_plan(target)


@AppFactory.register_application(["ovn-chassis"])
class OvnSubordinateApplication(OpenStackAuxiliarySubordinateApplication):
    """Ovn subordinate application class."""

    def pre_upgrade_plan(self, target: OpenStackRelease) -> list[Optional[UpgradeStep]]:
        """Pre Upgrade planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Plan that will add pre upgrade as sub steps.
        :rtype: list[Optional[UpgradeStep]]
        """
        validate_ovn_support(self.status.workload_version)
        return super().pre_upgrade_plan(target)


def validate_ovn_support(version: str) -> None:
    """Validate COU OVN support.

    COU does not support upgrade clouds with OVN version lower than 22.03.

    :param version: Version of the OVN.
    :type version: str
    :raises ApplicationError: When workload version is lower than 22.03.0.
    """
    if Version(version) < Version("22.03.0"):
        raise ApplicationError(
            (
                "OVN versions lower than 22.03 are not supported. It's necessary to upgrade "
                "OVN to 22.03 before upgrading the cloud. Follow the instructions at: "
                "https://docs.openstack.org/charm-guide/latest/project/procedures/"
                "ovn-upgrade-2203.html"
            )
        )
