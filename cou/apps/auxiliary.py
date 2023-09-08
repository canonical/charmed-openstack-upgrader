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
"""Auxiliary application class."""
import logging
from typing import Optional

from cou.apps.app import AppFactory, OpenStackApplication
from cou.exceptions import ApplicationError
from cou.steps import UpgradeStep
from cou.utils.juju_utils import upgrade_charm
from cou.utils.openstack import CHARM_FAMILIES, OpenStackRelease, openstack_to_track

logger = logging.getLogger(__name__)


@AppFactory.register_application(
    ["rabbitmq-server", "vault", "mysql-innodb-cluster"] + CHARM_FAMILIES["ovn"]
)
class OpenStackAuxiliaryApplication(OpenStackApplication):
    """Application for charms that can have multiple OpenStack releases for a workload."""

    @property
    def expected_current_channel(self) -> str:
        """Return the expected current channel based on the current OpenStack release.

        Note that this is not necessarily equal to the "channel" property since it is
        determined based on the workload version.

        :raises ApplicationError: When cannot find a track.
        :return: The expected current channel for the application.
        :rtype: str
        """
        track = openstack_to_track(self.charm, self.series, self.current_os_release)
        if track:
            return f"{track}/stable"

        raise ApplicationError(
            f"Cannot find a track of '{self.charm}' for {self.current_os_release.codename}"
        )

    def target_channel(self, target: OpenStackRelease) -> str:
        """Return the channel based on the target passed.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :raises ApplicationError: When cannot find a track.
        :return: The next channel for the application. E.g: 3.8/stable
        :rtype: str
        """
        track = openstack_to_track(self.charm, self.series, target)
        if track:
            return f"{track}/stable"

        raise ApplicationError(f"Cannot find a track of '{self.charm}' for {target.codename}")

    def _get_refresh_charm_plan(
        self, target: OpenStackRelease, parallel: bool = False
    ) -> Optional[UpgradeStep]:
        """Get plan for refreshing the current channel.

        This function also identifies if charm comes from charmstore and in that case,
        makes the migration. This method overwrite OpenStackApplication method because
        a channel track from auxiliary charms can have multiple OpenStack releases.
        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param parallel: Parallel running, defaults to False
        :type parallel: bool, optional
        :return: Plan for refreshing the charm.
        :rtype: Optional[UpgradeStep]
        """
        switch = None
        channel = self.channel

        description = f"Refresh '{self.name}' to the latest revision of '{self.channel}'"

        if self.charm_origin == "cs":
            description = f"Migration of '{self.name}' from charmstore to charmhub"
            switch = f"ch:{self.charm}"
            channel = self.expected_current_channel
        elif self.channel != self.expected_current_channel:
            logger.warning(
                "'%s' has the channel set to: %s which is different from the expected channel: %s",
                self.name,
                self.channel,
                self.expected_current_channel,
            )
            return None

        # pylint: disable=duplicate-code
        return UpgradeStep(
            description=description,
            parallel=parallel,
            function=upgrade_charm,
            application_name=self.name,
            channel=channel,
            model_name=self.model_name,
            switch=switch,
        )
