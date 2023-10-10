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
    AUXILIARY_SUBORDINATES,
    CHARM_FAMILIES,
    OPENSTACK_TO_TRACK_MAPPING,
    TRACK_TO_OPENSTACK_MAPPING,
    OpenStackRelease,
)

logger = logging.getLogger(__name__)


@AppFactory.register_application(
    ["rabbitmq-server", "vault", "mysql-innodb-cluster", "ceph-fs", "ceph-radosgw"]
    + CHARM_FAMILIES["ovn"]
    + AUXILIARY_SUBORDINATES
)
class OpenStackAuxiliaryApplication(OpenStackApplication):
    """Application for charms that can have multiple OpenStack releases for a workload."""

    @property
    def possible_current_channels(self) -> list[str]:
        """Return the possible current channels based on the series and current OpenStack release.

        :return: The possible current channels for the application.
        :rtype: list[str]
        """
        tracks = OPENSTACK_TO_TRACK_MAPPING.get(
            (self.charm, self.series, self.current_os_release.codename), []
        )
        return [f"{track}/stable" for track in tracks]

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
        When application comes from charm store, it's not possible to determine the
        OpenStack release codename and in that case it will be considered as ussuri.
        :return: OpenStackRelease object
        :rtype: OpenStackRelease
        """
        if self.is_from_charm_store:
            return OpenStackRelease("ussuri")

        track: str = self.channel.split("/", maxsplit=1)[0]
        compatible_os_releases = TRACK_TO_OPENSTACK_MAPPING.get((self.charm, self.series, track))
        # channel setter already validate if it is a valid channel.
        return max(compatible_os_releases)  # type: ignore

    @property
    def channel(self) -> str:
        """Get charm channel of the application.

        :return: Charm channel. E.g: 3.8/stable
        :rtype: str
        """
        return self._channel

    @channel.setter
    def channel(self, charm_channel: str) -> None:
        """Set charm channel of the application.

        When application comes from charm store, the channel won't be track related.
        If the application is subordinate, we can't check the tracks because the OpenStack
        release is based on the channel itself.
        :param charm_channel: Charm channel. E.g: 3.8/stable
        :type charm_channel: str
        :raises ValueError: Exception raised when cannot find a channel track
            based on the charm name, series and current OpenStack codename.
        """
        if self.is_from_charm_store or self.is_subordinate:
            self._channel = charm_channel
            return

        tracks = OPENSTACK_TO_TRACK_MAPPING.get(
            (self.charm, self.series, self.current_os_release.codename), []
        )
        track_from_channel = charm_channel.split("/", maxsplit=1)[0]
        if track_from_channel not in tracks:
            raise ValueError(
                (
                    f"'{self.name}' cannot find a channel track for charm: '{charm_channel}' "
                    f"series: {self.series} and OpenStack "
                    f"release: {self.current_os_release.codename}"
                )
            )
        self._channel = charm_channel
