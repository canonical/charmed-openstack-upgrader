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
from typing import Callable

from cou.apps.app import AppFactory
from cou.apps.auxiliary import OpenStackAuxiliaryApplication
from cou.apps.subordinate import OpenStackSubordinateApplication
from cou.exceptions import ApplicationError
from cou.utils.openstack import TRACK_TO_OPENSTACK_MAPPING, OpenStackRelease

logger = logging.getLogger(__name__)


@AppFactory.register_application(["ovn-central", "ovn-dedicated-chassis"])
class OvnPrincipalApplication(OpenStackAuxiliaryApplication):
    """Ovn central application class."""

    @property
    def channel_codename(self) -> OpenStackRelease:
        """Identify the OpenStack release set in the charm channel.

        Ovn charms can have multiple compatible OpenStack releases. In
        that case, return the latest compatible OpenStack version.
        :raises ApplicationError: When cannot identify suitable OpenStack release codename
            based on the track of the charm channel or if it is using channel lesser than 22.03.
        :return: OpenStackRelease object
        :rtype: OpenStackRelease
        """
        track: str = self.channel.split("/", maxsplit=1)[0]
        if track in ["20.03", "20.12", "21.09"]:
            raise ApplicationError(
                (
                    "It's recommended to upgrade OVN to 22.03 before upgrading the cloud. "
                    "Follow the instructions at: "
                    "https://docs.openstack.org/charm-guide/latest/project/procedures/"
                    "ovn-upgrade-2203.html"
                )
            )
        compatible_os_releases = TRACK_TO_OPENSTACK_MAPPING.get((self.charm, self.series, track))
        if compatible_os_releases:  # pylint: disable=R0801
            return max(compatible_os_releases)

        raise ApplicationError(
            (
                f"'{self.charm}' cannot identify suitable OpenStack release codename "
                f"for channel: '{self.channel}'"
            )
        )


@AppFactory.register_application(["ovn-chassis"])
class OvnSubordinateApplication(OvnPrincipalApplication):
    """Ovn chassis application class."""

    generate_upgrade_plan: Callable = OpenStackSubordinateApplication.generate_upgrade_plan

    @property
    def current_os_release(self) -> OpenStackRelease:
        """Infer the OpenStack release from subordinate charm's channel.

        We cannot determine the OpenStack release base on workload packages because the principal
        charm has already upgraded the packages.
        :return: OpenStackRelease object.
        :rtype: OpenStackRelease
        """
        return self.channel_codename
