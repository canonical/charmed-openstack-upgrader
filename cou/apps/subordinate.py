#  Copyright 2023 Canonical Limited
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
"""Subordinate application class."""
from typing import Optional

from cou.apps.app import AppFactory, OpenStackAlternativeApplication
from cou.steps import UpgradeStep
from cou.utils.openstack import SUBORDINATES, OpenStackRelease


@AppFactory.register_application(SUBORDINATES)
class OpenStackSubordinateApplication(OpenStackAlternativeApplication):
    """Subordinate application class."""

    def pre_upgrade_plan(self, target: OpenStackRelease) -> list[Optional[UpgradeStep]]:
        """Pre Upgrade planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Plan that will add pre upgrade as sub steps.
        :rtype: list[Optional[UpgradeStep]]
        """
        return [self._get_refresh_charm_plan(target)]

    def post_upgrade_plan(self, target: OpenStackRelease) -> list[Optional[UpgradeStep]]:
        """Post Upgrade planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Plan that will add post upgrade as sub steps.
        :rtype: list[Optional[UpgradeStep]]
        """
        return [None]
