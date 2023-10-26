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

from cou.apps.base import OpenStackApplication
from cou.apps.factory import AppFactory
from cou.exceptions import ApplicationError
from cou.steps import UpgradeStep
from cou.utils.app_utils import set_require_osd_release_option, validate_ovn_support
from cou.utils.openstack import (
    OPENSTACK_TO_TRACK_MAPPING,
    TRACK_TO_OPENSTACK_MAPPING,
    OpenStackRelease,
)

logger = logging.getLogger(__name__)


@AppFactory.register_application(["vault", "ceph-fs", "ceph-radosgw"])
class OpenStackAuxiliaryApplication(OpenStackApplication):
    """Application for charms that can have multiple OpenStack releases for a workload."""

    @property
    def is_os_channel_based(self) -> bool:
        """Check if application is OpenStack channel based.

        For auxiliary charms, always return false because they are
        not OpenStack channel based.
        :return: False.
        :rtype: bool
        """
        return False

    def is_valid_track(self, charm_channel: str) -> bool:
        """Check if the channel track is valid.

        Auxiliary charms don't follow the OpenStack track convention
        and are validated based on the openstack_to_track_mapping.csv table.
        :param charm_channel: Charm channel. E.g: 3.8/stable
        :type charm_channel: str
        :return: True if valid, False otherwise.
        :rtype: bool
        """
        if self.is_from_charm_store:
            logger.debug(
                "'%s' has been installed from from the charm store",
                self.name,
            )
            return True

        track = self._get_track_from_channel(charm_channel)
        return bool(TRACK_TO_OPENSTACK_MAPPING.get((self.charm, self.series, track)))

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
        if self.is_from_charm_store:
            logger.debug(
                (
                    "'Application %s' installed from charm store; assuming Ussuri as the "
                    "underlying version."
                ),
                self.name,
            )
            return OpenStackRelease("ussuri")

        track: str = self._get_track_from_channel(self.channel)
        compatible_os_releases = TRACK_TO_OPENSTACK_MAPPING[(self.charm, self.series, track)]
        # channel setter already validate if it is a valid channel.
        return max(compatible_os_releases)


@AppFactory.register_application(["rabbitmq-server"])
class RabbitMQServer(OpenStackAuxiliaryApplication):
    """RabbitMQ application.

    RabbitMQ must wait for the entire model to be idle before declaring the upgrade complete.
    """

    wait_timeout = 300
    wait_for_model = True


@AppFactory.register_application(["ceph-mon"])
class CephMonApplication(OpenStackAuxiliaryApplication):
    """Application for Ceph Monitor charm."""

    wait_timeout = 300
    wait_for_model = True

    def pre_upgrade_plan(self, target: OpenStackRelease) -> list[Optional[UpgradeStep]]:
        """Pre Upgrade planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Plan that will add pre upgrade as sub steps.
        :rtype: list[Optional[UpgradeStep]]
        """
        return [
            self._get_upgrade_current_release_packages_plan(),
            self._get_refresh_charm_plan(target),
            self._get_change_require_osd_release_plan(self.possible_current_channels[-1]),
        ]

    def post_upgrade_plan(self, target: OpenStackRelease) -> list[Optional[UpgradeStep]]:
        """Post Upgrade planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Plan that will add post upgrade as sub steps.
        :rtype: list[UpgradeStep]
        """
        steps = super().post_upgrade_plan(target)
        return [
            *steps,
            self._get_change_require_osd_release_plan(self.target_channel(target)),
        ]

    def _get_change_require_osd_release_plan(
        self, channel: str, parallel: bool = False
    ) -> UpgradeStep:
        """Get plan to set correct value for require-osd-release option on ceph-mon.

        This step is needed as a workaround for LP#1929254. Reference:
        https://docs.openstack.org/charm-guide/latest/project/issues/upgrade-issues.html#ceph-require-osd-release

        :param channel: The channel to get ceph track from.
        :type channel: str
        :param parallel: Parallel running, defaults to False
        :type parallel: bool, optional
        :return: Plan to check and set correct value for require-osd-release
        :rtype: UpgradeStep
        """
        ceph_release: str = self._get_track_from_channel(channel)
        ceph_mon_unit, *_ = self.units
        return UpgradeStep(
            description=(
                "Ensure require-osd-release option on ceph-mon units correctly "
                f"set to '{ceph_release}'"
            ),
            parallel=parallel,
            coro=set_require_osd_release_option(ceph_mon_unit.name, self.model, ceph_release),
        )


@AppFactory.register_application(["ovn-central", "ovn-dedicated-chassis"])
class OvnPrincipalApplication(OpenStackAuxiliaryApplication):
    """Ovn principal application class."""

    def pre_upgrade_plan(self, target: OpenStackRelease) -> list[Optional[UpgradeStep]]:
        """Pre Upgrade planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Plan that will add pre upgrade as sub steps.
        :rtype: list[Optional[UpgradeStep]]
        """
        for unit in self.units:
            validate_ovn_support(unit.workload_version)
        return super().pre_upgrade_plan(target)


@AppFactory.register_application(["mysql-innodb-cluster"])
class MysqlInnodbClusterApplication(OpenStackAuxiliaryApplication):
    """Application for mysql-innodb-cluster charm."""

    # NOTE(agileshaw): holding 'mysql-server-core-8.0' package prevents undesired
    # mysqld processes from restarting, which lead to outages
    packages_to_hold: Optional[list] = ["mysql-server-core-8.0"]
