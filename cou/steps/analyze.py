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
from dataclasses import dataclass
from typing import Optional

from cou.apps.app import AppFactory, OpenStackApplication
from cou.utils import juju_utils
from cou.utils.openstack import DATA_PLANE_CHARMS, UPGRADE_ORDER, OpenStackRelease

logger = logging.getLogger(__name__)


@dataclass
class Analysis:
    """Analyze result.

    :param apps_control_plane: Control plane applications in the model
    :type apps_control_plane:  list[OpenStackApplication]
    :param apps_data_plane: Data plane applications in the model
    :type apps_data_plane:  list[OpenStackApplication]
    """

    model_name: Optional[str]
    apps_control_plane: list[OpenStackApplication]
    apps_data_plane: list[OpenStackApplication]

    @classmethod
    async def create(cls, model_name: Optional[str] = None) -> Analysis:
        """Analyze the deployment before planning.

        :param model_name: Name of model to query, if None the current model will be used
        :type model_name: Optional[str]
        :return: Analysis object populated with the model applications.
        :rtype: Analysis
        """
        logger.info("Analyzing the OpenStack deployment...")
        apps = await Analysis._populate(model_name)

        control_plane, data_plane = cls._split_control_plane_and_data_plane(apps)

        return Analysis(
            model_name=model_name, apps_data_plane=data_plane, apps_control_plane=control_plane
        )

    @classmethod
    def _split_control_plane_and_data_plane(
        cls, apps: list[OpenStackApplication]
    ) -> tuple[list[OpenStackApplication], list[OpenStackApplication]]:
        """Split control plane and data plane apps.

        :param apps: List of applications to split.
        :type apps:  Iterable[OpenStackApplication]
        :return: Control plane and data plane application lists.
        :rtype: tuple[list[OpenStackApplication], list[OpenStackApplication]]
        """
        data_plane = []
        control_plane = []
        for app in apps:
            if app.charm in DATA_PLANE_CHARMS:
                data_plane.append(app)
            else:
                control_plane.append(app)
        return control_plane, data_plane

    @classmethod
    async def _populate(cls, model_name: Optional[str]) -> list[OpenStackApplication]:
        """Analyze the applications in the model.

        Applications that must be upgraded in a specific order will be returned first, followed
        by applications that can be upgraded in any order. Applications that are not supported
        will be ignored.

        :param model_name: Name of model to query
        :type model_name: Optional[str]
        :return: Application objects with their respective information.
        :rtype: List[OpenStackApplication]
        """
        juju_status = await juju_utils.get_status(model_name)
        apps = {
            AppFactory.create(
                name=app,
                status=app_status,
                config=await juju_utils.get_application_config(app, model_name),
                model_name=model_name,
                charm=await juju_utils.extract_charm_name(app, model_name),
            )
            for app, app_status in juju_status.applications.items()
        }
        # remove non-supported charms that return None on AppFactory.create
        apps.discard(None)
        # mypy complains that apps can have None, but we already removed.
        apps_to_upgrade_in_order = {
            app for app in apps if app.charm in UPGRADE_ORDER  # type: ignore
        }
        other_o7k_apps = apps - apps_to_upgrade_in_order
        sorted_apps_to_upgrade_in_order = sorted(
            apps_to_upgrade_in_order,
            key=lambda app: UPGRADE_ORDER.index(app.charm),  # type: ignore
        )
        # order by charm name to have a predicable upgrade sequence of others o7k charms.
        other_o7k_apps_sorted_by_name = sorted(
            other_o7k_apps, key=lambda app: app.charm  # type: ignore
        )
        return sorted_apps_to_upgrade_in_order + other_o7k_apps_sorted_by_name  # type: ignore

    def __str__(self) -> str:
        """Dump as string.

        :return: String representation of Application objects.
        :rtype: str
        """
        return (
            "Control Plane:\n"
            + "\n".join([str(app) for app in self.apps_control_plane])
            + "Data Plane:\n"
            + "\n".join([str(app) for app in self.apps_data_plane])
        )

    @property
    def current_cloud_os_release(self) -> Optional[OpenStackRelease]:
        """Shows the current OpenStack release codename.

        This property just consider OpenStack charms as those that have
        openstack-origin or source on the charm configuration (app.os_origin).
        :return: OpenStack release codename
        :rtype: OpenStackRelease
        """
        return min(
            (app.current_os_release for app in self.apps_control_plane + self.apps_data_plane),
            default=None,
        )
