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

from cou.apps.base import OpenStackApplication
from cou.apps.factory import AppFactory
from cou.exceptions import HaltUpgradePlanGeneration
from cou.steps import PostUpgradeStep, PreUpgradeStep, UpgradeStep
from cou.utils.openstack import SUBORDINATES, OpenStackRelease

logger = logging.getLogger(__name__)


class SubordinateBase(OpenStackApplication):
    """Subordinate base class."""

    def _check_application_target(self, target: OpenStackRelease) -> None:
        """Check if the application is already upgraded.

        Subordinate applications use the apt source of the related principal and don't have an
        origin/openstack-origin config option.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :raises HaltUpgradePlanGeneration: When the application halt the upgrade plan generation.
        """
        logger.debug("%s application current os_release is %s", self.name, self.current_os_release)

        if self.current_os_release >= target and self.can_upgrade_current_channel is False:
            raise HaltUpgradePlanGeneration(
                f"Application '{self.name}' already configured for release equal to or greater "
                f"than {target}. Ignoring."
            )

    def pre_upgrade_steps(self, target: OpenStackRelease) -> list[PreUpgradeStep]:
        """Pre Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: List of pre upgrade steps.
        :rtype: list[PreUpgradeStep]
        """
        return [self._get_refresh_charm_step(target)]

    def upgrade_steps(self, target: OpenStackRelease) -> list[UpgradeStep]:
        """Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
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
class SubordinateApplication(SubordinateBase):
    """Subordinate application class."""

    @property
    def current_os_release(self) -> OpenStackRelease:
        """Infer the OpenStack release from subordinate charm's channel.

        We cannot determine the OpenStack release base on workload packages because the principal
        charm has already upgraded the packages.
        :return: OpenStackRelease object.
        :rtype: OpenStackRelease
        """
        if self.is_from_charm_store:
            logger.debug(
                "'%s' is from charm store and will be considered with channel codename as ussuri",
                self.name,
            )
            return OpenStackRelease("ussuri")
        return OpenStackRelease(self._get_track_from_channel(self.channel))
