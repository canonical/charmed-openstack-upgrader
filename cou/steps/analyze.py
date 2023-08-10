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
from dataclasses import dataclass
from typing import Iterable, List, Optional

from cou.apps.app import Application
from cou.utils.juju_utils import async_get_application_config, async_get_status
from cou.utils.openstack import UPGRADE_ORDER, OpenStackRelease

logger = logging.getLogger(__name__)


@dataclass
class Analysis:
    """Analyze result.

    :param apps: Applications in the model
    :type apps:  Iterable[Application]
    """

    apps: Iterable[Application]

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
        """Analyze the applications in the model.

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
        upgradeable_apps = {app for app in apps if app.charm in UPGRADE_ORDER}
        unknown_apps = apps - upgradeable_apps
        upgradeable_apps_sorted = sorted(
            upgradeable_apps, key=lambda app: UPGRADE_ORDER.index(app.charm)
        )
        return upgradeable_apps_sorted + list(unknown_apps)

    def __str__(self) -> str:
        """Dump as string.

        :return: String representation of Application objects.
        :rtype: str
        """
        return os.linesep.join([str(app) for app in self.apps])

    @property
    def current_cloud_os_release(self) -> Optional[OpenStackRelease]:
        """Shows the current OpenStack release codename.

        :return: OpenStack release codename
        :rtype: OpenStackRelease
        """
        os_versions = set()
        for app in self.apps:
            if app.current_os_release:
                os_versions.add(app.current_os_release)
        return min(os_versions) if os_versions else None
