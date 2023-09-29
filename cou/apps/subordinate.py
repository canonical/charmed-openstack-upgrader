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
"""Subordinate application class."""
import logging
from typing import Optional

from cou.apps.app import AppFactory, OpenStackApplication
from cou.steps import UpgradeStep
from cou.utils.openstack import SUBORDINATES, OpenStackRelease

logger = logging.getLogger(__name__)


@AppFactory.register_application(SUBORDINATES)
class OpenStackSubordinateApplication(OpenStackApplication):
    """Subordinate application class."""

    @property
    def current_os_release(self) -> OpenStackRelease:
        """Infer the OpenStack release from subordinate charm's channel.

        We cannot determine the OpenStack release base on workload packages because the principal
        charm has already upgraded the packages.
        :return: OpenStackRelease object.
        :rtype: OpenStackRelease
        """
        return OpenStackRelease(self.channel.split("/")[0])

    def pre_upgrade_plan(self, target: OpenStackRelease) -> list[Optional[UpgradeStep]]:
        """Pre Upgrade planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Plan that will add pre upgrade as sub steps.
        :rtype: list[Optional[UpgradeStep]]
        """
        return [self._get_refresh_charm_plan(target)]

    def upgrade_plan(self, target: OpenStackRelease) -> list[Optional[UpgradeStep]]:
        """Upgrade planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :raises HaltUpgradePlanGeneration: When the application halt the upgrade plan generation.
        :return: Plan that will add upgrade as sub steps.
        :rtype: list[Optional[UpgradeStep]]
        """
        return [self._get_upgrade_charm_plan(target)]

    def post_upgrade_plan(self, target: OpenStackRelease) -> list[Optional[UpgradeStep]]:
        """Post Upgrade planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Plan that will add post upgrade as sub steps.
        :rtype: list[Optional[UpgradeStep]]
        """
        return [None]

    @property
    def channel(self) -> str:
        """Get charm channel of the application.

        :return: Charm channel. E.g: ussuri/stable
        :rtype: str
        """
        return self._channel

    @channel.setter
    def channel(self, charm_channel: str) -> None:
        """Set charm channel of the application.

        :param charm_channel: Charm channel. E.g: ussuri/stable
        :type charm_channel: str
        :raises ApplicationError: Exception raised when channel is not a valid OpenStack
            channel.
        """
        try:
            OpenStackRelease(charm_channel.split("/")[0])
            self._channel = charm_channel
        except ValueError:
            # if it has charm origin like cs:
            # or latest/stable it means it does not support openstack channels yet,
            # so it should be minimum
            self._channel = "ussuri/stable"
