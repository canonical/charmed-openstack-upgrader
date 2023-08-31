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

from cou.apps.app import SUBORDINATES, AppFactory, OpenStackApplication
from cou.exceptions import ApplicationError
from cou.steps import UpgradeStep
from cou.utils.openstack import OpenStackRelease

logger = logging.getLogger(__name__)


@AppFactory.register_application(SUBORDINATES)
class OpenStackSubordinateApplication(OpenStackApplication):
    """Subordinate application class."""

    def __post_init__(self) -> None:
        """Initialize the Application dataclass."""
        self.channel = self.status.charm_channel
        self.charm_origin = self.status.charm.split(":")[0]
        self.os_origin = self._get_os_origin()

    @property
    def current_os_release(self) -> OpenStackRelease:
        """Assume latest version since principal already upgraded the packages."""
        return OpenStackRelease(self.channel.split("/")[0])

    def generate_upgrade_plan(self, target: str) -> UpgradeStep:
        """Generate full upgrade plan for an Application.

        :param target: OpenStack codename to upgrade.
        :type target: str
        :return: Full upgrade plan if the Application is able to generate it.
        :rtype: UpgradeStep
        """
        plan = UpgradeStep(description=f"Upgrade {self.name}", parallel=False, function=None)
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
        """
        try:
            OpenStackRelease(charm_channel.split("/")[0])
            self._channel = charm_channel
        except ValueError as exc:
            logger.error(
                "Unable to determine the OpenStack version from channel: %s, %s",
                charm_channel,
                exc,
            )
            raise ApplicationError from exc
