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
from cou.utils.openstack import (
    AUXILIARY_SUBORDINATES,
    CHARM_FAMILIES,
    OPENSTACK_TO_TRACK_MAPPING,
    TRACK_TO_OPENSTACK_MAPPING,
    OpenStackRelease,
)

logger = logging.getLogger(__name__)


# NOTE (gabrielcocenza) ceph-osd might need to be removed if data plane has a specific class
@AppFactory.register_application(
    ["rabbitmq-server", "vault", "mysql-innodb-cluster", "ceph-fs", "ceph-radosgw"]
    + CHARM_FAMILIES["ovn"]
    + AUXILIARY_SUBORDINATES
    + ["ceph-osd"]
)
class OpenStackAuxiliaryApplication(OpenStackApplication):
    """Application for charms that can have multiple OpenStack releases for a workload."""

    def _get_channels_based_on_os(self, os_release: OpenStackRelease) -> list[str]:
        """Get the channel based on the OpenStack release.

        :param os_release: OpenStack release.
        :type os_release: OpenStackRelease
        :return: List of possible channels compatible with a OpenStack release.
        :rtype: list[str]
        """
        tracks = OPENSTACK_TO_TRACK_MAPPING.get((self.charm, self.series, os_release.codename), [])
        return [f"{track}/stable" for track in tracks]

    @property
    def _get_channel_codename(self) -> OpenStackRelease:
        """Property responsible to get the channel codename.

        Auxiliary charms can have multiple compatible OpenStack releases. In
        that case, return the latest compatible OpenStack version.
        :return: The OpenStack release codename based on the channel.
        :rtype: OpenStackRelease
        """
        track: str = self._get_track_from_channel(self.channel)
        compatible_os_releases = TRACK_TO_OPENSTACK_MAPPING.get((self.charm, self.series, track))
        # channel setter already validate if it is a valid channel.
        return max(compatible_os_releases)  # type: ignore

    @property
    def is_os_channel_based(self) -> bool:
        """Check if application is channel based.

        For auxiliary charms, always return false because they are
        not OpenStack channel based.
        :return: True if does have origin setting, False otherwise.
        :rtype: bool
        """
        return False

    def is_valid_track(self, charm_channel: str) -> bool:
        """Check if the channel track is valid.

        :param charm_channel: Charm channel. E.g: ussuri/stable
        :type charm_channel: str
        :return: True if valid, False otherwise.
        :rtype: bool
        """
        if self.is_from_charm_store:
            return True

        track = self._get_track_from_channel(charm_channel)
        possible_channels = self._get_channels_based_on_os(self.current_os_release)
        return any((channel for channel in possible_channels if track in channel))

    def channel_err_msg(self, charm_channel: str) -> str:
        """Error message when channel is not valid.

        :param charm_channel: Charm channel.
        :type charm_channel: str
        :return: error message
        :rtype: str
        """
        return (
            f"'{self.name}' cannot find a channel track for charm: '{charm_channel}' "
            f"series: {self.series} and OpenStack "
            f"release: {self.current_os_release.codename}"
        )
