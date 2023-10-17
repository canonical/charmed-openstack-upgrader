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

from cou.apps.app import AppFactory, OpenStackApplication
from cou.exceptions import ApplicationError
from cou.utils.openstack import (
    OPENSTACK_TO_TRACK_MAPPING,
    TRACK_TO_OPENSTACK_MAPPING,
    OpenStackRelease,
)

logger = logging.getLogger(__name__)


@AppFactory.register_application(
    ["rabbitmq-server", "vault", "mysql-innodb-cluster", "ceph-fs", "ceph-radosgw"]
)
class OpenStackAuxiliaryApplication(OpenStackApplication):
    """Application for charms that can have multiple OpenStack releases for a workload."""

    @property
    def possible_current_channels(self) -> list[str]:
        """Return the possible current channels based on the series and current OpenStack release.

        :raises ApplicationError: When cannot find tracks.
        :return: The possible current channels for the application.
        :rtype: list[str]
        """
        tracks = OPENSTACK_TO_TRACK_MAPPING.get(
            (self.charm, self.series, self.current_os_release.codename)
        )
        if tracks:
            return [f"{track}/stable" for track in tracks]

        raise ApplicationError(
            (
                f"Cannot find a suitable '{self.charm}' charm channel for "
                f"{self.current_os_release.codename}"
            )
        )

    def target_channel(self, target: OpenStackRelease) -> str:
        """Return the appropriate channel for the passed OpenStack target.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :raises ApplicationError: When cannot find a track.
        :return: The next channel for the application. E.g: 3.8/stable
        :rtype: str
        """
        tracks = OPENSTACK_TO_TRACK_MAPPING.get((self.charm, self.series, target.codename))
        if tracks:
            return f"{tracks[-1]}/stable"

        raise ApplicationError(
            f"Cannot find a suitable '{self.charm}' charm channel for {target.codename}"
        )

    @property
    def channel_codename(self) -> OpenStackRelease:
        """Identify the OpenStack release set in the charm channel.

        Auxiliary charms can have multiple compatible OpenStack releases. In
        that case, return the latest compatible OpenStack version.
        :raises ApplicationError: When cannot identify suitable OpenStack release codename
            based on the track of the charm channel.
        :return: OpenStackRelease object
        :rtype: OpenStackRelease
        """
        track: str = self.channel.split("/", maxsplit=1)[0]
        compatible_os_releases = TRACK_TO_OPENSTACK_MAPPING.get((self.charm, self.series, track))
        if compatible_os_releases:
            return max(compatible_os_releases)

        raise ApplicationError(
            (
                f"'{self.charm}' cannot identify suitable OpenStack release codename "
                f"for channel: '{self.channel}'"
            )
        )
