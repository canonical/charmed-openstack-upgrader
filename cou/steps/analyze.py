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

"""Functions for analyzing an OpenStack cloud before an upgrade."""
from __future__ import annotations

import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from cou.apps.app import Application
from cou.utils.juju_utils import async_get_application_config, async_get_status
from cou.utils.openstack import (
    LTS_SERIES,
    SPECIAL_CHARMS,
    UPGRADE_ORDER,
    CompareOpenStack,
    determine_next_openstack_release,
)

logger = logging.getLogger(__name__)


@dataclass
class Analysis:
    """Analyze result.

    :param apps: Applications in the model
    :type apps:  Iterable[Application]
    :param apps_to_upgrade: Applications to upgrade in the model
    :type apps_to_upgrade: Optional[List[Application]]
    :param os_versions: Dictionary containing OpenStack codenames and set of Applications
    :type os_versions:  defaultdict[str, set]
    """

    apps: Iterable[Application]
    apps_to_upgrade: Optional[List[Application]] = None
    os_versions: defaultdict[str, set] = field(default_factory=lambda: defaultdict(set))

    def __post_init__(self) -> None:
        """Initialize the Analysis dataclass."""
        for app in self.apps:
            if app.current_os_release:
                self.os_versions[app.current_os_release].add(app)
        self.apps_to_upgrade = self.determine_apps_to_upgrade()

    @classmethod
    async def create(cls) -> Analysis:
        """Analyze the deployment before planning.

        :return: Analysis object populated with the model applications.
        :rtype: Analysis
        """
        logger.info("Analyzing the OpenStack deployment...")
        apps = await Analysis._populate()

        return Analysis(apps=apps)

    @classmethod
    async def _populate(cls) -> set[Application]:
        """Generate the applications model.

        :return: Application objects with their respective information.
        :rtype: set[Application]
        """
        juju_status = await async_get_status()
        model_name = juju_status.model.name
        apps = {
            Application(
                name=app,
                status=app_status,
                config=await async_get_application_config(app),
                model_name=model_name,
            )
            for app, app_status in juju_status.applications.items()
        }
        return apps

    def __str__(self) -> str:
        """Dump as string.

        :return: String representation of Application objects.
        :rtype: str
        """
        return os.linesep.join([str(app) for app in self.apps])

    @property
    def current_cloud_os_release(self) -> str:
        """Shows the current OpenStack release codename.

        :return: OpenStack release codename
        :rtype: str
        """
        os_sequence = sorted(self.os_versions.keys(), key=CompareOpenStack)
        return os_sequence[0]

    @property
    def next_cloud_os_release(self) -> str:
        """Shows the next OpenStack release codename.

        :return: OpenStack release codename
        :rtype: str
        """
        _, next_cloud_os_release = determine_next_openstack_release(self.current_cloud_os_release)
        return next_cloud_os_release

    def determine_apps_to_upgrade(self) -> List[Application]:
        """Determine applications to upgrade.

        This function find the oldest OpenStack version in the deployment and
        select the applications to upgrade for the next version (N + 1).

        :return: List of applications to be upgraded.
        :rtype: List[Application]
        """
        apps_to_upgrade = self.os_versions[self.current_cloud_os_release].copy()
        special_charms_to_upgrade = self._add_special_charms_to_upgrade()
        apps_to_upgrade.update(special_charms_to_upgrade)

        return sorted(apps_to_upgrade, key=lambda app: UPGRADE_ORDER.index(app.charm))

    def _add_special_charms_to_upgrade(self) -> set:
        """Add special charms to upgrade if openstack-origin is set to a lower OpenStack version.

        Special charms are those that can have multiple OpenStack releases for a workload version.
        When source is configured to "distro", we should check the ubuntu series that matches with
        this configuration.
        :return: Set of Applications to upgrade
        :rtype: set
        """
        special_charms_to_upgrade = set()
        for app in self.apps:
            if app.charm in SPECIAL_CHARMS and app.os_origin:
                os_origin = app.os_origin.split("-")[-1]
                if os_origin == "distro":
                    os_origin = LTS_SERIES[app.series]
                if (
                    CompareOpenStack(app.current_os_release) < self.next_cloud_os_release
                    or CompareOpenStack(os_origin) < self.next_cloud_os_release
                ):
                    special_charms_to_upgrade.add(app)
        return special_charms_to_upgrade
