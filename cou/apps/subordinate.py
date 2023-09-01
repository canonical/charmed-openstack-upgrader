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
        self.channel = self._try_getting_channel(self.status.charm_channel)
        self.charm_origin = self.status.charm.split(":")[0]
        self.os_origin = self._get_os_origin()

    @property
    def current_os_release(self) -> OpenStackRelease:
        """Infer the OS release from subordinate charm's channel.

        We cannot determine the OS release base on workload packages because the principal charm
        has already upgraded the packages.
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
        plan = UpgradeStep(description=f"Upgrade {self.name}", parallel=False, function=None)
        refresh_charm_plan = self._get_refresh_charm_plan(OpenStackRelease(target))
        if refresh_charm_plan:
            plan.add_step(refresh_charm_plan)

        upgrade_charm_plan = self._get_upgrade_charm_plan(OpenStackRelease(target))
        if upgrade_charm_plan:
            plan.add_step(upgrade_charm_plan)

        return plan

    def _try_getting_channel(self, charm_channel: str) -> str:
        """Try getting the channel having a valid OpenStack channel.

        :param charm_channel: Charm channel.
        :type charm_channel: str
        :return: Charm channel if it is a valid OpenStack channel.
        :rtype: str
        :raises ApplicationError: Exception raised when channel is not a valid OpenStack
            channel.
        """
        try:
            OpenStackRelease(charm_channel.split("/")[0])
            return charm_channel
        except ValueError as exc:
            raise ApplicationError(
                f"Unable to determine the OpenStack version from channel: {charm_channel}, {exc}"
            ) from exc
