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

from cou.apps import LONG_IDLE_TIMEOUT
from cou.apps.base import OpenStackApplication
from cou.apps.factory import AppFactory
from cou.exceptions import ApplicationError
from cou.steps import PreUpgradeStep
from cou.utils.app_utils import set_require_osd_release_option, validate_ovn_support
from cou.utils.juju_utils import COUUnit
from cou.utils.openstack import (
    OPENSTACK_TO_TRACK_MAPPING,
    TRACK_TO_OPENSTACK_MAPPING,
    OpenStackCodenameLookup,
    OpenStackRelease,
)

logger = logging.getLogger(__name__)


@AppFactory.register_application(["vault", "ceph-fs", "ceph-radosgw"])
class AuxiliaryApplication(OpenStackApplication):
    """Application for charms that can have multiple OpenStack releases for a workload."""

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
            logger.debug("'%s' has been installed from the charm store", self.name)
            return True

        track = self._get_track_from_channel(charm_channel)
        return (self.charm, self.series, track) in TRACK_TO_OPENSTACK_MAPPING

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
                f"{self.current_os_release.codename} on series '{self.series}'. "
                "Please take a look at the documentation: "
                "https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html"
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
            (
                f"Cannot find a suitable '{self.charm}' charm channel for {target.codename} "
                f"on series '{self.series}'. Please take a look at the documentation: "
                "https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html"
            )
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
class RabbitMQServer(AuxiliaryApplication):
    """RabbitMQ application.

    RabbitMQ must wait for the entire model to be idle before declaring the upgrade complete.
    """

    wait_timeout = LONG_IDLE_TIMEOUT
    wait_for_model = True


@AppFactory.register_application(["ceph-mon"])
class CephMon(AuxiliaryApplication):
    """Application for Ceph Monitor charm."""

    wait_timeout = LONG_IDLE_TIMEOUT
    wait_for_model = True

    def pre_upgrade_steps(
        self, target: OpenStackRelease, units: Optional[list[COUUnit]]
    ) -> list[PreUpgradeStep]:
        """Pre Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate upgrade plan
        :type units: Optional[list[COUUnit]]
        :return:  List of pre upgrade steps.
        :rtype: list[PreUpgradeStep]
        """
        return super().pre_upgrade_steps(target, units) + [
            self._get_change_require_osd_release_step()
        ]

    def _get_change_require_osd_release_step(self) -> PreUpgradeStep:
        """Get the step to set correct value for require-osd-release option on ceph-mon.

        This step is needed as a workaround for LP#1929254. Reference:
        https://docs.openstack.org/charm-guide/latest/project/issues/upgrade-issues.html#ceph-require-osd-release

        :return: Step to check and set correct value for require-osd-release
        :rtype: PreUpgradeStep
        """
        ceph_mon_unit, *_ = self.units.values()
        return PreUpgradeStep(
            description="Ensure require-osd-release option matches with ceph-osd version",
            coro=set_require_osd_release_option(ceph_mon_unit.name, self.model),
        )


@AppFactory.register_application(["ovn-central", "ovn-dedicated-chassis"])
class OvnPrincipal(AuxiliaryApplication):
    """Ovn principal application class."""

    def pre_upgrade_steps(
        self, target: OpenStackRelease, units: Optional[list[COUUnit]]
    ) -> list[PreUpgradeStep]:
        """Pre Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate upgrade plan
        :type units: Optional[list[COUUnit]]
        :return: List of pre upgrade steps.
        :rtype: list[PreUpgradeStep]
        """
        for unit in self.units.values():
            validate_ovn_support(unit.workload_version)
        return super().pre_upgrade_steps(target, units)


@AppFactory.register_application(["mysql-innodb-cluster"])
class MysqlInnodbCluster(AuxiliaryApplication):
    """Application for mysql-innodb-cluster charm."""

    # NOTE(agileshaw): holding 'mysql-server-core-8.0' package prevents undesired
    # mysqld processes from restarting, which lead to outages
    packages_to_hold: Optional[list] = ["mysql-server-core-8.0"]
    wait_timeout = LONG_IDLE_TIMEOUT


@AppFactory.register_application(["ceph-osd"])
class CephOsd(AuxiliaryApplication):
    """Application for ceph-osd."""

    def pre_upgrade_steps(
        self, target: OpenStackRelease, units: Optional[list[COUUnit]]
    ) -> list[PreUpgradeStep]:
        """Pre Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate upgrade plan
        :type units: Optional[list[COUUnit]]
        :return: List of pre upgrade steps.
        :rtype: list[PreUpgradeStep]
        """
        steps = [
            PreUpgradeStep(
                description="Check if all nova-compute units had been upgraded",
                coro=self._verify_nova_compute(target),
            )
        ]
        steps.extend(super().pre_upgrade_steps(target, units))
        return steps

    async def _verify_nova_compute(self, target: OpenStackRelease) -> None:
        """Check if a nova-compute application has upgraded its workload version.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :raises ApplicationError: When any nova-compute app workload version isn't reached.
        """
        units_not_upgraded = []
        apps = await self.model.get_applications()

        for app in apps:
            if app.charm != "nova-compute":
                logger.debug("skipping application %s", app.name)
                continue

            for unit in app.units.values():
                compatible_os_versions = OpenStackCodenameLookup.find_compatible_versions(
                    app.charm, unit.workload_version
                )

                if target not in compatible_os_versions:
                    units_not_upgraded.append(unit.name)

        if units_not_upgraded:
            raise ApplicationError(
                f"Units '{', '.join(units_not_upgraded)}' did not reach {target}."
            )
