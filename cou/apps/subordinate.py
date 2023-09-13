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

from cou.apps.app import AppFactory, OpenStackApplication
from cou.steps import UpgradeStep
from cou.utils.openstack import SUBORDINATES, OpenStackRelease

logger = logging.getLogger(__name__)


@AppFactory.register_application(SUBORDINATES)
class OpenStackSubordinateApplication(OpenStackApplication):
    """Subordinate application class."""

    _default_used = False

    @property
    def current_os_release(self) -> OpenStackRelease:
        """Infer the OpenStack release from subordinate charm's channel.

        We cannot determine the OpenStack release base on workload packages because the principal
        charm has already upgraded the packages.
        :return: OpenStackRelease object.
        :rtype: OpenStackRelease
        """
        return OpenStackRelease(self.channel.split("/")[0])

    def generate_upgrade_plan(self, target: str) -> UpgradeStep:
        """Generate full upgrade plan for an Application.

        :param target: OpenStack codename to upgrade.
        :type target: str
        :return: Full upgrade plan if the Application is able to generate it.
        :rtype: UpgradeStep
        """
        plan = UpgradeStep(
            description=f"Upgrade plan for '{self.name}' to {target}",
            parallel=False,
            function=None,
        )

        if not self._default_used:
            refresh_charm_plan = self._get_refresh_charm_plan(OpenStackRelease(target))
            if refresh_charm_plan:
                plan.add_step(refresh_charm_plan)

        upgrade_charm_plan = self._get_upgrade_charm_plan(OpenStackRelease(target))
        if upgrade_charm_plan:
            plan.add_step(upgrade_charm_plan)

        return plan

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
            self._default_used = False
        except ValueError:
            # if it has charm origin like cs:
            # or latest/stable it means it does not support openstack channels yet,
            # so it should be minimum
            self._default_used = True
            self._channel = "ussuri/stable"
