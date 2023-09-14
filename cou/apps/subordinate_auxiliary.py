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
"""Auxiliary subordinate application class."""

from cou.apps.app import AppFactory
from cou.apps.auxiliary import OpenStackAuxiliaryApplication
from cou.steps import UpgradeStep
from cou.utils.openstack import AUXILIARY_SUBORDINATES, OpenStackRelease


@AppFactory.register_application(AUXILIARY_SUBORDINATES)
class OpenStackAuxiliarySubordinateApplication(OpenStackAuxiliaryApplication):
    """Auxiliary subordinate application class."""

    @property
    def current_os_release(self) -> OpenStackRelease:
        """Infer the OpenStack release from subordinate charm's channel.

        We cannot determine the OpenStack release base on workload packages because the principal
        charm has already upgraded the packages.
        :return: OpenStackRelease object.
        :rtype: OpenStackRelease
        """
        return self.channel_codename

    def generate_upgrade_plan(self, target: str) -> UpgradeStep:
        """Generate full upgrade plan for an Application.

        :param target: OpenStack codename to upgrade.
        :type target: str
        :return: Full upgrade plan if the Application is able to generate it.
        :rtype: UpgradeStep
        """
        target_version = OpenStackRelease(target)
        plan = UpgradeStep(
            description=f"Upgrade plan for '{self.name}' to {target}",
            parallel=False,
            function=None,
        )

        refresh_charm_plan = self._get_refresh_charm_plan(target_version)
        if refresh_charm_plan:
            plan.add_step(refresh_charm_plan)

        upgrade_charm_plan = self._get_upgrade_charm_plan(target_version)
        if upgrade_charm_plan:
            plan.add_step(upgrade_charm_plan)

        return plan
