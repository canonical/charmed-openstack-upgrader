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
from typing import Iterable, List

from cou.apps.app import Application
from cou.utils.juju_utils import async_get_application_config, async_get_status
from cou.utils.openstack import UPGRADE_ORDER, OpenStackRelease

logger = logging.getLogger(__name__)


@dataclass
class Analysis:
    """Analyze result.

    :param apps: Applications in the model
    :type apps:  Iterable[Application]
    :param os_versions: Dictionary containing OpenStack codenames and set of Applications name.
    :type os_versions:  defaultdict[str, set]
    """

    apps: Iterable[Application]
    os_versions: defaultdict[str, set] = field(default_factory=lambda: defaultdict(set))

    def __post_init__(self) -> None:
        """Initialize the Analysis dataclass."""
        for app in self.apps:
            if app.current_os_release:
                self.os_versions[app.current_os_release].add(app.name)

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
    async def _populate(cls) -> List[Application]:
        """Generate the applications model.

        :return: Application objects with their respective information.
        :rtype: List[Application]
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
        return sorted(apps, key=lambda app: UPGRADE_ORDER.index(app.charm))

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
        os_sequence = sorted(self.os_versions.keys(), key=OpenStackRelease)
        return os_sequence[0]

    @property
    def next_cloud_os_release(self) -> str:
        """Shows the next OpenStack release codename.

        :return: OpenStack release codename
        :rtype: str
        """
        return OpenStackRelease(self.current_cloud_os_release).next_release
