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
import abc
import logging
from typing import Optional

from packaging.version import Version

from cou.apps.base import LONG_IDLE_TIMEOUT, OpenStackApplication
from cou.apps.factory import AppFactory
from cou.exceptions import ApplicationError
from cou.steps import ApplicationUpgradePlan, PreUpgradeStep
from cou.utils.app_utils import set_require_osd_release_option
from cou.utils.juju_utils import Unit
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
        current_track = self._get_track_from_channel(charm_channel)
        possible_tracks = OPENSTACK_TO_TRACK_MAPPING.get(
            (self.charm, self.series, self.current_os_release.codename), []
        )
        return (
            self.charm,
            self.series,
            current_track,
        ) in TRACK_TO_OPENSTACK_MAPPING and len(possible_tracks) > 0

    def expected_current_channel(self, target: OpenStackRelease) -> str:
        """Return the expected current channel.

        Expected current channel is the channel that the application is supposed to be using based
        on the current series, workload version and, by consequence, the OpenStack release
        identified.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: The expected current channel of the application. E.g: "3.9/stable"
        :rtype: str
        """
        if self.need_crossgrade and self.based_on_channel:
            *_, track = OPENSTACK_TO_TRACK_MAPPING[
                (self.charm, self.series, f"{target.previous_release}")
            ]
        else:
            *_, track = OPENSTACK_TO_TRACK_MAPPING[
                (self.charm, self.series, self.current_os_release.codename)
            ]

        return f"{track}/stable"

    def target_channel(self, target: OpenStackRelease) -> str:
        """Return the appropriate channel for the passed OpenStack target.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: The next channel for the application. E.g: 3.8/stable
        :rtype: str
        :raises ApplicationError: When cannot find a track.
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

    def _get_os_release_from_channel(self, channel: str) -> OpenStackRelease:
        """Get the OpenStack release from a channel.

        Auxiliary charms can have multiple compatible OpenStack releases. In that case, return the
        latest compatible OpenStack version.

        :param channel: channel to get the release
        :type channel: str
        :return: OpenStack release that the channel points to
        :rtype: OpenStackRelease
        :raises ApplicationError: When cannot identify suitable OpenStack release codename
        """
        track: str = self._get_track_from_channel(channel)
        compatible_os_releases = TRACK_TO_OPENSTACK_MAPPING[(self.charm, self.series, track)]

        if not compatible_os_releases:
            raise ApplicationError(
                f"Channel: {self.channel} for charm '{self.charm}' on series '{self.series}' is "
                f"not supported by COU. Please take a look at the documentation: "
                "https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html to see "
                "if you are using the right track."
            )

        return max(compatible_os_releases)

    def generate_upgrade_plan(
        self,
        target: OpenStackRelease,
        force: bool,
        units: Optional[list[Unit]] = None,
    ) -> ApplicationUpgradePlan:
        """Generate full upgrade plan for an Application.

        Auxiliary applications cannot be upgraded unit by unit.

        :param target: OpenStack codename to upgrade.
        :type target: OpenStackRelease
        :param force: Whether the plan generation should be forced
        :type force: bool
        :param units: Units to generate upgrade plan, defaults to None
        :type units: Optional[list[Unit]], optional
        :return: Full upgrade plan if the Application is able to generate it.
        :rtype: ApplicationUpgradePlan
        """
        if units:
            logger.warning(
                "%s cannot be upgraded using the single-unit method. "
                "The upgrade will proceed using the all-in-one method.",
                self.name,
            )
        return super().generate_upgrade_plan(target, force, None)

    def _need_current_channel_refresh(self, target: OpenStackRelease) -> bool:
        """Check if the application needs to refresh the current channel.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: True if needs to refresh, False otherwise
        :rtype: bool
        """
        track: str = self._get_track_from_channel(self.channel)
        compatible_os_releases = TRACK_TO_OPENSTACK_MAPPING[(self.charm, self.series, track)]
        return bool(self.can_upgrade_to) and any(
            os_release <= target for os_release in compatible_os_releases
        )


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
        self, target: OpenStackRelease, units: Optional[list[Unit]]
    ) -> list[PreUpgradeStep]:
        """Pre Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate upgrade plan
        :type units: Optional[list[Unit]]
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
            "Ensure that the 'require-osd-release' option matches the 'ceph-osd' version",
            coro=set_require_osd_release_option(ceph_mon_unit.name, self.model),
        )


class OVN(AuxiliaryApplication):
    """OVN generic application class."""

    @abc.abstractmethod
    def _check_ovn_support(self) -> None:
        """Check OVN version to be implemented."""

    @staticmethod
    def _validate_ovn_support(version: str) -> None:
        """Validate COU OVN support.

        COU does not support upgrade clouds with OVN version lower than 22.03.

        :param version: Version of the OVN.
        :type version: str
        :raises ApplicationError: When workload version is lower than 22.03.0.
        """
        if Version(version) < Version("22.03.0"):
            raise ApplicationError(
                (
                    "OVN versions lower than 22.03 are not supported. It's necessary to upgrade "
                    "OVN to 22.03 before upgrading the cloud. Follow the instructions at: "
                    "https://docs.openstack.org/charm-guide/latest/project/procedures/"
                    "ovn-upgrade-2203.html"
                )
            )

    def _check_version_pinning(self) -> None:
        """Check if the version pinning is False.

        :raises ApplicationError: When version pinning is True
        """
        if "enable-version-pinning" not in self.config:
            logger.debug(
                "OVN application: '%s' does not offer the 'enable-version-pinning' configuration.",
                self.name,
            )
            return
        if self.config["enable-version-pinning"].get("value"):
            raise ApplicationError(
                f"Cannot upgrade '{self.name}'. 'enable-version-pinning' must be set to 'false'."
            )

    def upgrade_plan_sanity_checks(
        self, target: OpenStackRelease, units: Optional[list[Unit]]
    ) -> None:
        """Run sanity checks before generating upgrade plan.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate upgrade plan, defaults to None
        :type units: Optional[list[Unit]], optional
        :raises ApplicationError: When application is wrongly configured.
        :raises HaltUpgradePlanGeneration: When the application halt the upgrade plan generation.
        :raises MismatchedOpenStackVersions: When the units of the app are running different
                                             OpenStack versions.
        """
        self._check_ovn_support()
        self._check_version_pinning()
        super().upgrade_plan_sanity_checks(target, units)


@AppFactory.register_application(["ovn-central", "ovn-dedicated-chassis"])
class OVNPrincipal(OVN):
    """OVN principal application class."""

    def _check_ovn_support(self) -> None:
        """Check OVN version.

        :raises ApplicationError: When workload version is lower than 22.03.0.
        """
        for unit in self.units.values():
            OVNPrincipal._validate_ovn_support(unit.workload_version)


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
        self, target: OpenStackRelease, units: Optional[list[Unit]]
    ) -> list[PreUpgradeStep]:
        """Pre Upgrade steps planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate upgrade plan
        :type units: Optional[list[Unit]]
        :return: List of pre upgrade steps.
        :rtype: list[PreUpgradeStep]
        """
        steps = [
            PreUpgradeStep(
                description="Verify that all 'nova-compute' units has been upgraded",
                coro=self._verify_nova_compute(target),
            )
        ]
        steps.extend(super().pre_upgrade_steps(target, units))
        return steps

    async def _verify_nova_compute(self, target: OpenStackRelease) -> None:
        """Check if all units of nova-compute applications has upgraded their workload version.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :raises ApplicationError: When any nova-compute app workload version isn't reached.
        """
        units_not_upgraded = []
        apps = await self.model.get_applications()

        for app in apps.values():
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
