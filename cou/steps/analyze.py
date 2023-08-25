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
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Optional

from cou.apps.app import AppFactory, OpenStackApplication
from cou.utils.juju_utils import (
    async_get_application_config,
    async_get_status,
    extract_charm_name,
)
from cou.utils.openstack import UPGRADE_ORDER, OpenStackRelease

logger = logging.getLogger(__name__)


@dataclass
class Analysis:
    """Analyze result.

    :param apps: Applications in the model
    :type apps:  Iterable[OpenStackApplication]
    """

    apps: Iterable[OpenStackApplication]

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
    async def _populate(cls) -> list[OpenStackApplication]:
        """Analyze the applications in the model.

        :return: Application objects with their respective information.
        :rtype: List[OpenStackApplication]
        """
        juju_status = await async_get_status()
        model_name = juju_status.model.name
        apps = {
            AppFactory.create(
                name=app,
                status=app_status,
                config=await async_get_application_config(app),
                model_name=model_name,
                charm=await extract_charm_name(app),
            )
            for app, app_status in juju_status.applications.items()
        }
        # remove non-supported charms that return None on AppFactory.create
        apps.discard(None)
        apps_to_upgrade_in_order = {app for app in apps if app and app.charm in UPGRADE_ORDER}
        disordered_upgrade_apps = apps - apps_to_upgrade_in_order
        sorted_apps_to_upgrade_in_order = sorted(
            apps_to_upgrade_in_order, key=lambda app: UPGRADE_ORDER.index(app.charm)
        )
        disordered_upgrade_apps_sorted_by_name = sorted(
            disordered_upgrade_apps, key=lambda app: app.charm  # type: ignore
        )
        # mypy complains that unknown_apps can have None, but we already removed None from apps
        return (
            sorted_apps_to_upgrade_in_order
            + disordered_upgrade_apps_sorted_by_name  # type: ignore
        )

    def __str__(self) -> str:
        """Dump as string.

        :return: String representation of Application objects.
        :rtype: str
        """
        return os.linesep.join([str(app) for app in self.apps])

    @property
    def current_cloud_os_release(self) -> Optional[OpenStackRelease]:
        """Shows the current OpenStack release codename.

        This property just consider OpenStack charms as those that have
        openstack-origin or source on the charm configuration (app.os_origin).
        :return: OpenStack release codename
        :rtype: OpenStackRelease
        """
        os_versions = set()
        for app in self.apps:
            os_versions.add(app.current_os_release)
        return min(os_versions) if os_versions else None
