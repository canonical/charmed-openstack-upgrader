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
"""Ceph application class."""
import logging
from typing import Optional

from cou.apps.app import AppFactory
from cou.apps.auxiliary import OpenStackAuxiliaryApplication
from cou.steps import UpgradeStep
from cou.utils.openstack import OpenStackRelease

logger = logging.getLogger(__name__)


@AppFactory.register_application(["ceph-mon"])
class CephMonApplication(OpenStackAuxiliaryApplication):
    """Application for Ceph Monitor charm."""

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
            self._get_set_require_osd_release_plan(target, self.expected_current_channel),
        ]

    def post_upgrade_plan(self, target: OpenStackRelease) -> list[Optional[UpgradeStep]]:
        """Post Upgrade planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Plan that will add post upgrade as sub steps.
        :rtype: list[UpgradeStep]
        """
        return [
            self._get_reached_expected_target_plan(target),
            self._get_set_require_osd_release_plan(target, self.target_channel(target)),
        ]

    def _get_set_require_osd_release_plan(
        self, target: OpenStackRelease, channel: str, parallel: bool = False
    ) -> Optional[UpgradeStep]:
        """Get plan to set correct value for require-osd-release option on ceph-mon.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param channel: The channel to get ceph track from.
        :type str
        :param parallel: Parallel running, defaults to False
        :type parallel: bool, optional
        :return: Plan to check if application workload has been upgraded
        :rtype: UpgradeStep
        """
        if self.expected_current_channel != self.target_channel(target):
            track: str = channel.split("/", maxsplit=1)[0]
            set_command = f"sudo ceph osd require-osd-release {track}"

            return UpgradeStep(
                description=(f"Set '{track}' for require-osd-release option on ceph-mon units"),
                parallel=parallel,
                function=self.model.run_on_unit,
                unit=list(self.units.keys())[0],
                command=set_command,
            )
        return None
