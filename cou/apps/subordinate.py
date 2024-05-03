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

from cou.apps.base import OpenStackApplication
from cou.apps.factory import AppFactory
from cou.exceptions import HaltUpgradePlanGeneration
from cou.steps import PostUpgradeStep, PreUpgradeStep, UpgradeStep
from cou.utils.juju_utils import Unit
from cou.utils.openstack import SUBORDINATES, OpenStackRelease

logger = logging.getLogger(__name__)


@AppFactory.register_application(SUBORDINATES)
class SubordinateApplication(OpenStackApplication):
    """Subordinate base class."""

    # subordinate apps rely on the channel to evaluate current OpenStack release
    based_on_channel = True

    @property
    def o7k_release(self) -> OpenStackRelease:
        """Infer the OpenStack release from subordinate charm's channel.

        We cannot determine the OpenStack release base on workload packages because the principal
        charm has already upgraded the packages.

        :return: OpenStackRelease object.
        :rtype: OpenStackRelease
        """
        return self.channel_o7k_release

    def _check_application_target(self, target: OpenStackRelease) -> None:
        """Check if the application is already upgraded.

        Subordinate applications use the apt source of the related principal and don't have an
        origin/openstack-origin config option.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :raises HaltUpgradePlanGeneration: When the application halt the upgrade plan generation.
        """
        logger.debug("%s application current o7k_release is %s", self.name, self.o7k_release)

        if self.o7k_release >= target and not self.can_upgrade_to:
            raise HaltUpgradePlanGeneration(
                f"Application '{self.name}' already configured for release equal to or greater "
                f"than {target}. Ignoring."
            )

    def _get_upgrade_current_release_packages_step(
        self, units: Optional[list[Unit]]
    ) -> PreUpgradeStep:
        """Get step for upgrading software packages to the latest of the current release.

        :param units: Units to generate upgrade plan
        :type units: Optional[list[Unit]]
        :return: Step for upgrading software packages to the latest of the current release.
        :rtype: PreUpgradeStep
        """
        return PreUpgradeStep()

    def upgrade_steps(
        self, target: OpenStackRelease, units: Optional[list[Unit]], force: bool
    ) -> list[UpgradeStep]:
        """Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate upgrade steps
        :type units: Optional[list[Unit]]
        :param force: Whether the plan generation should be forced
        :type force: bool
        :return: List of upgrade steps.
        :rtype: list[UpgradeStep]
        """
        return [self._get_upgrade_charm_step(target)]

    def post_upgrade_steps(
        self, target: OpenStackRelease, units: Optional[list[Unit]]
    ) -> list[PostUpgradeStep]:
        """Post Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate post upgrade plan
        :type units: Optional[list[Unit]]
        :return: List of post upgrade steps.
        :rtype: list[PostUpgradeStep]
        """
        return []
