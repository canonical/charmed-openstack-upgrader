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

from cou.apps.base import ApplicationUnit, OpenStackApplication
from cou.apps.factory import AppFactory
from cou.steps import PostUpgradeStep, PreUpgradeStep, UpgradeStep
from cou.utils.openstack import SUBORDINATES, OpenStackRelease

logger = logging.getLogger(__name__)


class SubordinateBaseClass(OpenStackApplication):
    """Subordinate base class."""

    def pre_upgrade_steps(
        self, target: OpenStackRelease, units: Optional[list[ApplicationUnit]]
    ) -> list[PreUpgradeStep]:
        """Pre Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate upgrade plan
        :type units: Optional[list[ApplicationUnit]]
        :return: List of pre upgrade steps.
        :rtype: list[PreUpgradeStep]
        """
        return [self._get_refresh_charm_step(target)]

    def upgrade_steps(
        self, target: OpenStackRelease, units: Optional[list[ApplicationUnit]], force: bool
    ) -> list[UpgradeStep]:
        """Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate upgrade steps
        :type units: Optional[list[ApplicationUnit]]
        :param force: Whether the plan generation should be forced
        :type force: bool
        :return: List of upgrade steps.
        :rtype: list[UpgradeStep]
        """
        return [self._get_upgrade_charm_step(target)]

    def post_upgrade_steps(self, target: OpenStackRelease) -> list[PostUpgradeStep]:
        """Post Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: List of post upgrade steps.
        :rtype: list[PostUpgradeStep]
        """
        return []


@AppFactory.register_application(SUBORDINATES)
class OpenStackSubordinateApplication(SubordinateBaseClass):
    """Subordinate application class."""

    @property
    def current_os_release(self) -> OpenStackRelease:
        """Infer the OpenStack release from subordinate charm's channel.

        We cannot determine the OpenStack release base on workload packages because the principal
        charm has already upgraded the packages.
        :return: OpenStackRelease object.
        :rtype: OpenStackRelease
        """
        if self.is_from_charm_store:  # pylint: disable=duplicate-code
            logger.debug(
                "'%s' is from charm store and will be considered with channel codename as ussuri",
                self.name,
            )
            return OpenStackRelease("ussuri")
        return OpenStackRelease(self._get_track_from_channel(self.channel))
