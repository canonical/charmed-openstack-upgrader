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
from dataclasses import dataclass, field
from typing import Optional

from cou.apps.base import OpenStackApplication
from cou.apps.factory import AppFactory
from cou.utils import juju_utils
from cou.utils.openstack import (
    DATA_PLANE_CHARMS,
    OVN_SUBORDINATES,
    UPGRADE_ORDER,
    OpenStackRelease,
)

logger = logging.getLogger(__name__)


@dataclass
class Analysis:
    """Analyze result.

    :param model: Model object
    :type model: Model
    :param apps_control_plane: Control plane applications in the model
    :type apps_control_plane:  list[OpenStackApplication]
    :param apps_data_plane: Data plane applications in the model
    :type apps_data_plane:  list[OpenStackApplication]
    """

    model: juju_utils.Model
    apps: list[OpenStackApplication]
    min_o7k_version_control_plane: Optional[OpenStackRelease] = None
    min_o7k_version_data_plane: Optional[OpenStackRelease] = None

    current_cloud_o7k_release: Optional[OpenStackRelease] = field(init=False)
    current_cloud_series: Optional[str] = field(init=False)

    def __post_init__(self) -> None:
        """Initialize the Analysis dataclass."""
        self.min_o7k_version_control_plane = self.min_o7k_release_apps(self.apps_control_plane)
        self.min_o7k_version_data_plane = self.min_o7k_release_apps(self.apps_data_plane)
        self.current_cloud_o7k_release = self._get_minimum_cloud_o7k_release()
        self.current_cloud_series = self._get_minimum_cloud_series()

    @property
    def apps_control_plane(self) -> list[OpenStackApplication]:
        """Return list of control plane applications.

        :return: Control plane application lists.
        :rtype: list[OpenStackApplication]
        """
        control_plane, _ = self._split_apps(self.apps)
        return control_plane

    @property
    def apps_data_plane(self) -> list[OpenStackApplication]:
        """Return list of data plane applications.

        OVN_SUBORDINATES is not part of the data plane apps because they need to be
        upgraded before the ovn-contral.

        :return: data plane application lists.
        :rtype: list[OpenStackApplication]
        """
        _, data_plane = self._split_apps(self.apps)
        # Remove ovn subordinates from the data plane since they have to upgrade before
        # ovn-central
        data_plane = [app for app in data_plane if app.charm not in OVN_SUBORDINATES]
        return data_plane

    @property
    def apps_ovn_subordinate(self) -> list[OpenStackApplication]:
        """Return list of ovn subordinate applications.

        :return: ovn subordinate application lists.
        :rtype: list[OpenStackApplication]
        """
        apps = []
        for app in self.apps:
            if app.charm in OVN_SUBORDINATES:
                apps.append(app)
        return apps

    @staticmethod
    def _split_apps(
        apps: list[OpenStackApplication],
    ) -> tuple[list[OpenStackApplication], list[OpenStackApplication]]:
        """Split applications to control plane and data plane apps.

        :param apps: List of applications to split.
        :type apps: Iterable[OpenStackApplication]
        :return: Control plane and data plane application lists.
        :rtype: tuple[list[OpenStackApplication], list[OpenStackApplication]]
        """

        def is_data_plane(app: OpenStackApplication) -> bool:
            """Check if app belong to data plane.

            :param app: application
            :type app: OpenStackApplication
            :return: boolean
            :rtype: bool
            """
            return app.charm in DATA_PLANE_CHARMS

        control_plane, data_plane = [], []
        data_plane_machines = {
            unit.machine for app in apps if is_data_plane(app) for unit in app.units.values()
        }

        for app in apps:
            if is_data_plane(app):
                data_plane.append(app)
            elif any(machine in data_plane_machines for machine in app.machines.values()):
                data_plane.append(app)
            else:
                control_plane.append(app)

        return control_plane, data_plane

    @classmethod
    async def create(
        cls, model: juju_utils.Model, skip_apps: Optional[set[str]] = None
    ) -> Analysis:
        """Analyze the deployment before planning.

        :param model: Model object
        :type model: Model
        :param skip_apps: Application to skip upgrading
        :type skip_apps: set of string
        :return: Analysis object populated with the model applications.
        :rtype: Analysis
        """
        logger.info("Analyzing the OpenStack deployment...")
        apps = await Analysis._populate(model)

        return Analysis(
            model=model, apps=[app for app in apps if app.name not in (skip_apps or set())]
        )

    @classmethod
    async def _populate(cls, model: juju_utils.Model) -> list[OpenStackApplication]:
        """Analyze the applications in the model.

        Applications that must be upgraded in a specific order will be returned first, followed
        by applications that can be upgraded in any order. Applications that are not supported
        will be ignored.

        :param model: Model object
        :type model: Model
        :return: Application objects with their respective information.
        :rtype: List[OpenStackApplication]
        """
        juju_applications = await model.get_applications()
        apps = set()
        for name, app in juju_applications.items():
            if o7k_app := AppFactory.create(app):
                apps.add(o7k_app)
                logger.info("Found %s application:\n%s", name, o7k_app)

        apps_to_upgrade_in_order = {app for app in apps if app.charm in UPGRADE_ORDER}
        other_o7k_apps = apps - apps_to_upgrade_in_order
        sorted_apps_to_upgrade_in_order = sorted(
            apps_to_upgrade_in_order,
            key=lambda app: UPGRADE_ORDER.index(app.charm),
        )
        # order by charm name to have a predictable upgrade sequence of other o7k charms.
        other_o7k_apps_sorted_by_name = sorted(
            other_o7k_apps, key=lambda app: (app.charm, app.name)
        )
        return sorted_apps_to_upgrade_in_order + other_o7k_apps_sorted_by_name

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
            + f"\nCurrent minimum OS release in the cloud: {self.current_cloud_o7k_release}\n"
            + f"\nCurrent minimum Ubuntu series in the cloud: {self.current_cloud_series}\n"
        )

    @staticmethod
    def min_o7k_release_apps(apps: list[OpenStackApplication]) -> Optional[OpenStackRelease]:
        """Get the minimal OpenStack release from a list of applications.

        - subordinates or channel based apps are not considered if not using release channels
        - other apps are considered even if not using release channels

        :param apps: Applications.
        :type apps: list[OpenStackApplication]
        :return: OpenStack release.
        :rtype: Optional[OpenStackRelease]
        """
        # NOTE(gabrielcocenza) Apps based on channels to identify OpenStack release cannot
        # be considered when on 'latest/stable' or from Charmstore because it's not reliable and
        # will be considered as Ussuri.
        apps_skipped = {app for app in apps if app.based_on_channel and app.need_crossgrade}
        if apps_skipped:
            logger.debug(
                "%s were skipped from calculating cloud OpenStack release",
                sorted(apps_skipped, key=lambda app: app.name),
            )
        return min((app.o7k_release for app in set(apps) - apps_skipped), default=None)

    def _get_minimum_cloud_o7k_release(self) -> Optional[OpenStackRelease]:
        """Get the current minimum OpenStack release in the cloud.

        :return: OpenStack release
        :rtype: Optional[Optional[OpenStackRelease]]
        """
        control_plane = (
            [self.min_o7k_version_control_plane] if self.min_o7k_version_control_plane else []
        )
        data_plane = [self.min_o7k_version_data_plane] if self.min_o7k_version_data_plane else []
        return min(control_plane + data_plane, default=None)

    def _get_minimum_cloud_series(self) -> Optional[str]:
        """Get the current minimum Ubuntu series codename in the cloud.

        :return: Ubuntu series codename. E.g. 'focal', 'jammy'
        :rtype: Optional[str]
        """
        return min(
            (app.series for app in self.apps_control_plane + self.apps_data_plane),
            default=None,
        )

    @property
    def data_plane_machines(self) -> dict[str, juju_utils.Machine]:
        """Data-plane machines of the model.

        :return: Data-plane machines of the model.
        :rtype: dict[str, Machine]
        """
        return {
            machine_id: app.machines[machine_id]
            for app in self.apps_data_plane
            for machine_id in app.machines
        }

    @property
    def control_plane_machines(self) -> dict[str, juju_utils.Machine]:
        """Control-plane machines of the model.

        :return: Control-plane machines of the model.
        :rtype: dict[str, Machine]
        """
        return {
            machine_id: app.machines[machine_id]
            for app in self.apps_control_plane
            for machine_id in app.machines
        }

    @property
    def machines(self) -> dict[str, juju_utils.Machine]:
        """All OpenStack machines of the model.

        :return: All OpenStack machines of the model.
        :rtype: dict[str, Machine]
        """
        return {**self.data_plane_machines, **self.control_plane_machines}
