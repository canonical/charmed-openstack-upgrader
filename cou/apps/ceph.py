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
from cou.utils.app_utils import set_require_osd_release_option
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
            self._get_change_require_osd_release_plan(self.possible_current_channels[-1]),
        ]

    def post_upgrade_plan(self, target: OpenStackRelease) -> list[Optional[UpgradeStep]]:
        """Post Upgrade planning.

        Wait until the entire model reaches the idle state and then check the target workload.
        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Plan that will add post upgrade as sub steps.
        :rtype: list[UpgradeStep]
        """
        return [
            self._get_wait_step(300, wait_for_itself=False),
            self._get_reached_expected_target_plan(target),
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
        ceph_release: str = channel.split("/", maxsplit=1)[0]
        ceph_mon_unit, *_ = self.units
        return UpgradeStep(
            description=(
                "Ensure require-osd-release option on ceph-mon units correctly "
                f"set to '{ceph_release}'"
            ),
            parallel=parallel,
            function=set_require_osd_release_option,
            unit=ceph_mon_unit.name,
            model=self.model,
            ceph_release=ceph_release,
        )
