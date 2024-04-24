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
"""Channel based application class."""
import logging
from typing import Optional

from cou.apps.base import OpenStackApplication
from cou.apps.factory import AppFactory
from cou.steps import PostUpgradeStep
from cou.utils.juju_utils import Unit
from cou.utils.openstack import CHANNEL_BASED_CHARMS, OpenStackRelease

logger = logging.getLogger(__name__)


@AppFactory.register_application(CHANNEL_BASED_CHARMS)
class ChannelBasedApplication(OpenStackApplication):
    """Application for charms that are channel based."""

    # rely on the channel to evaluate current OpenStack release
    based_on_channel = True

    def get_latest_os_version(self, unit: Unit) -> OpenStackRelease:
        """Get the latest compatible OpenStack release based on the channel.

        :param unit: Unit
        :type unit: Unit
        :return: The latest compatible OpenStack release.
        :rtype: OpenStackRelease
        """
        return self.current_channel_os_release

    @property
    def current_os_release(self) -> OpenStackRelease:
        """Current OpenStack Release of the application.

        :return: OpenStackRelease object
        :rtype: OpenStackRelease
        """
        return self.current_channel_os_release

    @property
    def is_versionless(self) -> bool:
        """Check if the application is versionless.

        Versionless applications are those that does not set a workload version.
        E.g: glance-simplestreams-sync

        :return: True if is versionless, False otherwise.
        :rtype: bool
        """
        return not all(unit.workload_version for unit in self.units.values())

    def post_upgrade_steps(
        self, target: OpenStackRelease, units: Optional[list[Unit]]
    ) -> list[PostUpgradeStep]:
        """Post Upgrade steps planning.

        Wait until the application reaches the idle state and then check the target workload.
        In case the application is versionless, there are no post upgrade steps to run.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate post upgrade plan
        :type units: Optional[list[Unit]]
        :return: List of post upgrade steps.
        :rtype: list[PostUpgradeStep]
        """
        if self.is_versionless:
            return []

        return super().post_upgrade_steps(target, units)
