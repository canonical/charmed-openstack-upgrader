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
from cou.exceptions import ApplicationError, HaltUpgradePlanGeneration
from cou.steps import UpgradeStep
from cou.utils.juju_utils import async_upgrade_charm
from cou.utils.openstack import (
    CHARM_TYPES,
    LTS_SERIES,
    OPENSTACK_TO_TRACK_MAPPING,
    OpenStackRelease,
)

logger = logging.getLogger(__name__)


@AppFactory.register_application(
    ["rabbitmq-server", "vault"] + CHARM_TYPES["mysql"] + CHARM_TYPES["ovn"]
)
class AuxiliaryOpenStackApplication(OpenStackApplication):
    """Application for charms that can have multiple OpenStack releases for a workload."""

    def openstack_to_track(self, os_release: OpenStackRelease) -> str:
        """Find the track of auxiliary charms by Ubuntu release and OpenStack release codename.

        :param os_release: OpenStack release to track.
        :type os_release: OpenStackRelease
        :raises ApplicationError: When there is no track compatible.
        :return: The track of the auxiliary charm.
        :rtype: str
        """
        try:
            return OPENSTACK_TO_TRACK_MAPPING[self.series][self.charm][os_release.codename]
        except KeyError as exc:
            raise ApplicationError(
                f"Not possible to find the track for '{self.charm}' on {os_release.codename}"
            ) from exc

    def os_origin_config(self, target: OpenStackRelease) -> Optional[OpenStackRelease]:
        """Identify the OpenStack release set on openstack-origin or source config.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: OpenStackRelease object or None if the app doesn't have os_origin config.
        :rtype: Optional[OpenStackRelease]
        """
        # that means that the charm doesn't have source or openstack-origin config.
        if self.origin_setting is None:
            return None

        # Ex: "cloud:focal-ussuri" will result in "ussuri"
        os_origin_parsed: Optional[str] = self.os_origin.rsplit("-", maxsplit=1)[-1]
        if os_origin_parsed == "distro":
            # find the OpenStack release based on ubuntu series
            os_origin_parsed = LTS_SERIES[self.series]
        elif os_origin_parsed == "":
            # if it's empty we consider the previous release from the target.
            # Ex: rabbitmq-server has empty "source" and receive target "victoria".
            # In that case it will be considered as ussuri and with the upgrade,
            # "source" config will be changed to "cloud:focal-victoria".
            os_origin_parsed = target.previous_release

        return OpenStackRelease(os_origin_parsed) if os_origin_parsed else None

    @property
    def expected_current_channel(self) -> str:
        """Return the expected current channel based on the current OpenStack release.

        Note that this is not necessarily equal to the "channel" property since it is
        determined based on the workload version.

        :return: The expected current channel for the application.
        :rtype: str
        """
        return f"{self.openstack_to_track(self.current_os_release)}/stable"

    def target_channel(self, target: OpenStackRelease) -> str:
        """Return the channel based on the target passed.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: The next channel for the application. E.g: victoria/stable
        :rtype: str
        """
        return f"{self.openstack_to_track(target)}/stable"

    def _get_refresh_charm_plan(
        self, target: OpenStackRelease, parallel: bool = False
    ) -> Optional[UpgradeStep]:
        """Get plan for refreshing the current channel.

        This function also identifies if charm comes from charmstore and in that case,
        makes the migration.
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
            function=async_upgrade_charm,
            application_name=self.name,
            channel=channel,
            model_name=self.model_name,
            switch=switch,
        )

    def upgrade_plan(self, target: OpenStackRelease) -> list[Optional[UpgradeStep]]:
        """Upgrade planning.

        Auxiliary charms have multiple compatible OpenStack releases. In that case,
        we check also the OpenStack origin from the "source" or "openstack-origin" to know
        if it's necessary to change it. E.g: rabbitmq-server with workload version 3.8 is
        compatible from ussuri to yoga. Even that is considered as yoga, we need to set the
        source accordingly with the OpenStack components that might be in a lower version than
        yoga.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :raises HaltUpgradePlanGeneration: When the application halt the upgrade plan generation
        :return: Plan that will add upgrade as sub steps.
        :rtype: list[Optional[UpgradeStep]]
        """
        os_origin_config = self.os_origin_config(target)
        if self.current_os_release >= target and os_origin_config >= target:
            msg = (
                f"Application: '{self.name}' already configured for release equal or greater "
                f"version than {target}. Ignoring."
            )
            logger.info(msg)
            raise HaltUpgradePlanGeneration(msg)
        return [
            self._get_upgrade_charm_plan(target),
            self._get_workload_upgrade_plan(target),
        ]
