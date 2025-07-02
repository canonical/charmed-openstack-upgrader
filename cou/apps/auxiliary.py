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
import base64
import getpass
import logging
import os
import tempfile
from typing import Optional

import hvac
from packaging.version import Version

from cou.apps.base import LONG_IDLE_TIMEOUT, OpenStackApplication
from cou.apps.factory import AppFactory
from cou.exceptions import ApplicationError
from cou.steps import (
    ApplicationUpgradePlan,
    PostUpgradeStep,
    PreUpgradeStep,
    UnitUpgradeStep,
)
from cou.steps.ceph import set_require_osd_release_option_on_unit
from cou.utils import progress_indicator
from cou.utils.juju_utils import Unit
from cou.utils.openstack import (
    OPENSTACK_TO_TRACK_MAPPING,
    TRACK_TO_OPENSTACK_MAPPING,
    OpenStackRelease,
)

logger = logging.getLogger(__name__)


@AppFactory.register_application(["ceph-fs", "ceph-radosgw"])
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
            (self.charm, self.series, self.o7k_release.track), []
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
                (self.charm, self.series, self.o7k_release.track)
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
        tracks = OPENSTACK_TO_TRACK_MAPPING.get((self.charm, self.series, target.track))
        if tracks:
            return f"{tracks[-1]}/stable"

        raise ApplicationError(
            (
                f"Cannot find a suitable '{self.charm}' charm channel for {target.track} "
                f"on series '{self.series}'. Please take a look at the documentation: "
                "https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html"
            )
        )

    def _get_o7k_release_from_channel(self, channel: str) -> OpenStackRelease:
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
        compatible_o7k_releases = TRACK_TO_OPENSTACK_MAPPING[(self.charm, self.series, track)]

        if not compatible_o7k_releases:
            raise ApplicationError(
                f"Channel: {self.channel} for charm '{self.charm}' on series '{self.series}' is "
                f"not supported by COU. Please take a look at the documentation: "
                "https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html to see "
                "if you are using the right track."
            )

        return max(compatible_o7k_releases)

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
        compatible_o7k_releases = TRACK_TO_OPENSTACK_MAPPING[(self.charm, self.series, track)]
        return bool(self.can_upgrade_to) and any(
            o7k_release <= target for o7k_release in compatible_o7k_releases
        )

    def get_run_deferred_hooks_and_restart_pre_upgrade_step(
        self, units: Optional[list[Unit]]
    ) -> list[PreUpgradeStep]:
        """Get the steps for run deferred hook and restart services for before upgrade.

        This step will run the `run-deferred-hooks` action to clear any
        potential event and wait until the app is ready before performing
        upgrade. If there are no pending events, this step should be a no-op,
        so it's safe to run anyways.

        :param units: Units to generate upgrade plan
        :type units: Optional[list[Unit]]
        :return: Steps for run deferred hooks and restart service
        :rtype: List of PreUpgradeStep
        """
        run_hook_step = PreUpgradeStep(
            description=(
                f"Execute run-deferred-hooks for all '{self.name}' units "
                "to clear any leftover events"
            ),
            parallel=False,
        )
        run_hook_step.add_steps(
            [
                UnitUpgradeStep(
                    description=f"Execute run-deferred-hooks on unit: '{unit.name}'",
                    coro=self.model.run_action(
                        unit.name, "run-deferred-hooks", raise_on_failure=True
                    ),
                )
                for unit in units or self.units.values()
            ]
        )
        wait_step = PreUpgradeStep(
            description=(
                f"Wait for up to {self.wait_timeout}s for app '{self.name}'"
                " to reach the idle state"
            ),
            parallel=False,
            coro=self.model.wait_for_idle(self.wait_timeout, apps=[self.name]),
        )
        return [
            run_hook_step,
            wait_step,
        ]

    def get_run_deferred_hooks_and_restart_post_upgrade_step(
        self, units: Optional[list[Unit]]
    ) -> list[PostUpgradeStep]:
        """Get the step for run deferred hook and restart services for after upgrade.

        This step will wait for the app to complete the upgrade step and then
        run the `run-deferred-hooks` action to restart the service. If there
        are no pending events, this step should be a no-op, so it's safe to run
        anyways.

        :param units: Units to generate upgrade plan
        :type units: Optional[list[Unit]]
        :return: Step for run deferred hooks and restart service
        :rtype: PostUpgradeStep
        """
        wait_step = PostUpgradeStep(
            description=(
                f"Wait for up to {self.wait_timeout}s for app '{self.name}'"
                " to reach the idle state"
            ),
            parallel=False,
            coro=self.model.wait_for_idle(self.wait_timeout, apps=[self.name]),
        )
        run_hook_step = PostUpgradeStep(
            description=(
                f"Execute run-deferred-hooks for all '{self.name}' units "
                "to restart the service after upgrade"
            ),
            parallel=False,
        )
        run_hook_step.add_steps(
            [
                UnitUpgradeStep(
                    description=f"Execute run-deferred-hooks on unit: '{unit.name}'",
                    coro=self.model.run_action(
                        unit.name, "run-deferred-hooks", raise_on_failure=True
                    ),
                )
                for unit in units or self.units.values()
            ]
        )
        return [
            wait_step,
            run_hook_step,
        ]


@AppFactory.register_application(["rabbitmq-server"])
class RabbitMQServer(AuxiliaryApplication):
    """RabbitMQ application.

    RabbitMQ must wait for the entire model to be idle before declaring the upgrade complete.
    """

    wait_timeout = LONG_IDLE_TIMEOUT
    wait_for_model = True
    # rabbitmq-server can use channels 3.8 or 3.9 on focal.
    # COU changes to 3.9 if the channel is set to 3.8
    multiple_channels = True

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
        steps = super().pre_upgrade_steps(target, units)
        if self.config.get("enable-auto-restarts", {}).get("value") is False:
            steps.extend(self.get_run_deferred_hooks_and_restart_pre_upgrade_step(units))
        return steps

    def post_upgrade_steps(
        self, target: OpenStackRelease, units: Optional[list[Unit]]
    ) -> list[PostUpgradeStep]:
        """Post Upgrade steps planning.

        Wait until the application reaches the idle state and then check the target workload.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate post upgrade plan
        :type units: Optional[list[Unit]]
        :return: List of post upgrade steps.
        :rtype: list[PostUpgradeStep]
        """
        steps = []
        if self.config.get("enable-auto-restarts", {}).get("value") is False:
            steps.extend(self.get_run_deferred_hooks_and_restart_post_upgrade_step(units))
        steps.extend(super().post_upgrade_steps(target, units))
        return steps

    def _check_auto_restarts(self) -> None:
        """Check if enable-auto-restarts is enabled.

        Due to the charm [bug](https://bugs.launchpad.net/charm-rabbitmq-server/+bug/2046381),
        if the `enable-auto-restarts` option is enabled, this check will raise an exception.

        :raises ApplicationError: When enable-auto-restarts is enabled.
        """
        if self.config["enable-auto-restarts"].get("value") is True:
            raise ApplicationError(
                "`enable-auto-restarts` must be `False` due to "
                "https://bugs.launchpad.net/charm-rabbitmq-server/+bug/2046381 "
                f"Please run `juju config {self.name} enable-auto-restarts=False` "
                "before performing upgrades and rollback to original value after "
                "upgrade is completed"
            )


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
            coro=set_require_osd_release_option_on_unit(self.model, ceph_mon_unit.name),
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
                (
                    f"Cannot upgrade '{self.name}'. "
                    "'enable-version-pinning' must be set to 'false' because "
                    "from OVN LTS version 22.03 and onwards, rolling chassis upgrades are "
                    "supported when upgrading to minor versions as well as to any version within"
                    "the next major OVN LTS version."
                    "For move information, please refer to the charm guide at: "
                    "https://docs.openstack.org/charm-guide/latest/project/procedures/"
                    "ovn-upgrade-2203.html#disable-version-pinning"
                )
            )

    def upgrade_plan_sanity_checks(self, target: OpenStackRelease) -> None:
        """Run sanity checks before generating upgrade plan.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :raises ApplicationError: When application is wrongly configured.
        :raises HaltUpgradePlanGeneration: When the application halt the upgrade plan generation.
        :raises MismatchedOpenStackVersions: When the units of the app are running different
                                             OpenStack versions.
        """
        self._check_ovn_support()
        self._check_version_pinning()
        super().upgrade_plan_sanity_checks(target)


@AppFactory.register_application(["ovn-dedicated-chassis"])
class OVNPrincipal(OVN):
    """OVN principal application class."""

    def _check_ovn_support(self) -> None:
        """Check OVN version.

        :raises ApplicationError: When workload version is lower than 22.03.0.
        """
        for unit in self.units.values():
            OVNPrincipal._validate_ovn_support(unit.workload_version)


@AppFactory.register_application(["ovn-central"])
class OVNCentral(OVN):
    """OVN principal application class."""

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
        steps = self._verify_nova_compute_step(target)
        steps.extend(super().pre_upgrade_steps(target, units))
        return steps


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
        steps = self._verify_nova_compute_step(target)
        steps.extend(super().pre_upgrade_steps(target, units))
        return steps


@AppFactory.register_application(["vault"])
class Vault(AuxiliaryApplication):
    """Application for vault."""

    wait_timeout = LONG_IDLE_TIMEOUT
    wait_for_model = True

    def _get_cacert_file(self) -> Optional[str]:
        """Read cert file and write into temporary file.

        :return: Temporary file path
        :rtype: str
        """
        cacert_b64 = self.config["ssl-ca"].get("value")
        cacert_file = None
        if cacert_b64:
            with tempfile.NamedTemporaryFile(mode="wb", delete=False) as fp:
                fp.write(base64.b64decode(cacert_b64))
                cacert_file = fp.name
                logger.debug("Create tempfile: %s", cacert_file)
        return cacert_file

    async def _get_unit_api_url(self, unit_name: str) -> str:
        """Get unit's vault api address.

        :param unit_name: vault unit name
        :type unit_name: str
        :return: unit's vault api url
        :rtype: str
        """
        if self.config["hostname"].get("value"):  # Use hostname if hostname is being used.
            address = self.config["hostname"].get("value")
        elif self.config["vip"].get("value"):  # Use vip as address if vip is being used.
            address = self.config["vip"].get("value")
        else:
            juju_unit = await self.model.get_unit(unit_name)
            address = juju_unit.public_address

        transport = "https" if self.config["ssl-cert"].get("value") else "http"
        return f"{transport}://{address}:8200"

    async def _wait_for_sealed_status(self) -> None:
        """Wait for application vault go into sealed.

        :raises ApplicationError: When application vault is not in sealed.
        """
        await self.model.wait_for_idle(
            timeout=self.wait_timeout,
            status="blocked",
            apps=[self.name],
            # The Vault application will first enter an error state, followed by a blocked state.
            # This occurs due to a race condition in the Vault charm's hook. The charm will then
            # auto-recover from the error state.
            raise_on_error=False,
        )

        app_status = await self.model.get_application_status(app_name=self.name)
        if not app_status.status.info == "Unit is sealed":
            # It's an exception if vault not in sealed after upgrading.
            raise ApplicationError(
                "Application vault not in sealed."
                " The vault expected to be sealed after upgrading."
                " Please check application log for more details."
            )
        logger.debug("Application 'vault' in sealed status")

    async def _get_vault_client(self, unit_name: str, cacert_file: Optional[str]) -> hvac.Client:
        """Get vault client.

        :param unit_name: vault unit name
        :type unit_name: str
        :param cacert_file: cacert file path
        :type cacert_file: str
        :return: hvac vault Client object
        :rtype: hvac.Client
        """
        vault_url = await self._get_unit_api_url(unit_name)
        client = hvac.Client(url=vault_url, verify=cacert_file)
        return client

    async def _unseal_vault(self) -> None:
        """Unseal vault on every vault unit."""
        # Stop progress_indicator because it will clear the unseal key input.
        progress_indicator.stop()

        for unit_name in self.units:
            logger.debug("Start unseal %s", unit_name)
            cacert_file = self._get_cacert_file()
            client = await self._get_vault_client(unit_name, cacert_file)
            while True:
                status = client.sys.read_seal_status()
                if not status["sealed"]:
                    break
                unseal_key = getpass.getpass("Unseal Key (will be hidden):")
                if unseal_key:
                    client.sys.submit_unseal_key(key=unseal_key)
                # remove unseal key from memory
                del unseal_key

            # Delete temporary ca file
            if cacert_file:
                os.remove(cacert_file)
                logger.debug("Remove tempfile: %s", cacert_file)

    def post_upgrade_steps(
        self, target: OpenStackRelease, units: Optional[list[Unit]]
    ) -> list[PostUpgradeStep]:
        """Post Upgrade steps planning.

        Wait until the application reaches the idle state and then check the target workload.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param units: Units to generate post upgrade plan
        :type units: Optional[list[Unit]]
        :return: List of post upgrade steps.
        :rtype: list[PostUpgradeStep]
        """
        upgrade_step = self._get_upgrade_charm_steps(target=target)
        steps = []

        # Add unseal steps only if chaneel is changed.
        if upgrade_step:
            steps.extend(
                [
                    # Vault application should get into blocked and sealed status after upgrading.
                    PostUpgradeStep(
                        description=(
                            f"Wait for up to {self.wait_timeout}s"
                            " for vault to reach the sealed status"
                        ),
                        coro=self._wait_for_sealed_status(),
                    ),
                    PostUpgradeStep(
                        description="Unseal vault",
                        coro=self._unseal_vault(),
                    ),
                    PostUpgradeStep(
                        description=(
                            f"Wait for up to {self.wait_timeout}s for vault to reach active status"
                        ),
                        coro=self.model.wait_for_idle(
                            timeout=self.wait_timeout,
                            status="active",
                            apps=[self.name],
                            raise_on_blocked=False,
                            raise_on_error=False,
                        ),
                    ),
                    # Some applications will get into error status because vault in sealed status.
                    # Need to resolve them.
                    PostUpgradeStep(
                        description="Resolve all applications in error status",
                        coro=self.model.resolve_all(),
                    ),
                ]
            )
        steps.extend(super().post_upgrade_steps(target, units))
        return steps
