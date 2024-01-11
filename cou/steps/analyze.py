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
from typing import Any, Optional

from juju.client._definitions import ApplicationStatus, MachineStatus

from cou.apps.base import Machine, OpenStackApplication
from cou.apps.factory import AppFactory
from cou.utils import juju_utils
from cou.utils.juju_utils import COUModel
from cou.utils.openstack import DATA_PLANE_CHARMS, UPGRADE_ORDER, OpenStackRelease

logger = logging.getLogger(__name__)


@dataclass
class Analysis:
    """Analyze result.

    :param model: COUModel object
    :type model: COUModel
    :param apps_control_plane: Control plane applications in the model
    :type apps_control_plane:  list[OpenStackApplication]
    :param apps_data_plane: Data plane applications in the model
    :type apps_data_plane:  list[OpenStackApplication]
    :param machines: Machines in the model
    :type machines: dict[str, Machine]
    """

    # pylint: disable=too-many-instance-attributes

    model: juju_utils.COUModel
    apps_control_plane: list[OpenStackApplication]
    apps_data_plane: list[OpenStackApplication]
    machines: dict[str, Machine]
    min_os_version_control_plane: Optional[OpenStackRelease] = None
    min_os_version_data_plane: Optional[OpenStackRelease] = None

    current_cloud_os_release: Optional[OpenStackRelease] = field(init=False)
    current_cloud_series: Optional[str] = field(init=False)

    def __post_init__(self) -> None:
        """Initialize the Analysis dataclass."""
        self.min_os_version_control_plane = self.min_os_release_apps(self.apps_control_plane)
        self.min_os_version_data_plane = self.min_os_release_apps(self.apps_data_plane)
        self.current_cloud_os_release = self._get_minimum_cloud_os_release()
        self.current_cloud_series = self._get_minimum_cloud_series()

    @staticmethod
    def is_data_plane(charm: str) -> bool:
        """Check if app belong to data plane.

        :param charm: charm name
        :type charm: str
        :return: boolean
        :rtype: bool
        """
        return charm in DATA_PLANE_CHARMS

    @classmethod
    def _split_apps(
        cls,
        apps: list[OpenStackApplication],
    ) -> tuple[list[OpenStackApplication], list[OpenStackApplication]]:
        """Split applications to control plane and data plane apps.

        :param apps: List of applications to split.
        :type apps: Iterable[OpenStackApplication]
        :return: Control plane and data plane application lists.
        :rtype: tuple[list[OpenStackApplication], list[OpenStackApplication]]
        """
        control_plane, data_plane = [], []
        for app in apps:
            if any(unit.machine.is_data_plane for unit in app.units):
                data_plane.append(app)
            else:
                control_plane.append(app)

        return control_plane, data_plane

    @classmethod
    async def create(cls, model: juju_utils.COUModel) -> Analysis:
        """Analyze the deployment before planning.

        :param model: COUModel object
        :type model: COUModel
        :return: Analysis object populated with the model applications.
        :rtype: Analysis
        """
        logger.info("Analyzing the OpenStack deployment...")
        machines = await cls.get_machines(model)
        apps = await Analysis._populate(model, machines)

        control_plane, data_plane = cls._split_apps(apps)

        return Analysis(
            model=model,
            apps_data_plane=data_plane,
            apps_control_plane=control_plane,
            machines=machines,
        )

    @classmethod
    async def _populate(
        cls, model: juju_utils.COUModel, machines: dict[str, Machine]
    ) -> list[OpenStackApplication]:
        """Analyze the applications in the model.

        Applications that must be upgraded in a specific order will be returned first, followed
        by applications that can be upgraded in any order. Applications that are not supported
        will be ignored.

        :param model: COUModel object
        :type model: COUModel
        :param machines: Machines in the model
        :type machines: dict[str, Machine]
        :return: Application objects with their respective information.
        :rtype: List[OpenStackApplication]
        """
        juju_status = await model.get_status()
        apps = {
            AppFactory.create(
                name=app,
                status=app_status,
                config=await model.get_application_config(app),
                model=model,
                charm=await model.get_charm_name(app),
                machines=cls.get_app_machines(app_status, machines),
            )
            for app, app_status in juju_status.applications.items()
            if app_status
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
        # order by charm name to have a predictable upgrade sequence of others o7k charms.
        other_o7k_apps_sorted_by_name = sorted(
            other_o7k_apps, key=lambda app: app.charm  # type: ignore
        )
        return sorted_apps_to_upgrade_in_order + other_o7k_apps_sorted_by_name  # type: ignore

    @classmethod
    async def get_machines(cls, model: COUModel) -> dict[str, Machine]:
        """Get all the machines in the model.

        :param model: COUModel object
        :type model: _type_
        :return: _description_
        :rtype: dict[str, Machine]
        """
        juju_status = await model.get_status()
        data_plane_machines = {
            unit.machine
            for app in juju_status.applications
            if cls.is_data_plane(await model.get_charm_name(app))
            for unit in app.units
        }
        machines = {}
        for machine_id, raw_machine_data in juju_status.machines.items():
            machine_data = cls.get_machine_data(raw_machine_data)
            machines[machine_id] = Machine(
                machine_id=machine_id,
                hostname=machine_data["hostname"],
                az=machine_data["az"],
                is_data_plane=id in data_plane_machines,
            )
        return machines

    @classmethod
    def get_app_machines(
        cls, app_status: ApplicationStatus, machines: dict[str, Machine]
    ) -> dict[str, Machine]:
        """Get the machines of an app.

        :param app_status: Status of the application.
        :type app_status: ApplicationStatus
        :param machines: Machines in the model
        :type machines: dict[str, Machine]
        :return: Machines in the application
        :rtype: dict[str, Machine]
        """
        return {
            unit_status.machine: machines[unit_status.machine]
            for unit_status in app_status.units.values()
        }

    @staticmethod
    def get_machine_data(machine: MachineStatus) -> dict[str, Any]:
        """Get the data of a machine.

        :param machine: Machine status from juju
        :type machine: MachineStatus
        :return: Machine data formatted
        :rtype: dict[str, Any]
        """
        hardware = dict(entry.split("=") for entry in machine["hardware"].split())
        return {"az": hardware.get("availability-zone"), "hostname": machine["hostname"]}

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
            + f"\nCurrent minimum OS release in the cloud: {self.current_cloud_os_release}\n"
            + f"\nCurrent minimum Ubuntu series in the cloud: {self.current_cloud_series}\n"
        )

    @staticmethod
    def min_os_release_apps(apps: list[OpenStackApplication]) -> Optional[OpenStackRelease]:
        """Get the minimal OpenStack release from a list of applications.

        :param apps: Applications.
        :type apps: list[OpenStackApplication]
        :return: OpenStack release.
        :rtype: Optional[OpenStackRelease]
        """
        return min((app.current_os_release for app in apps), default=None)

    def _get_minimum_cloud_os_release(self) -> Optional[OpenStackRelease]:
        """Get the current minimum OpenStack release in the cloud.

        :return: OpenStack release
        :rtype: Optional[Optional[OpenStackRelease]]
        """
        control_plane = (
            [self.min_os_version_control_plane] if self.min_os_version_control_plane else []
        )
        data_plane = [self.min_os_version_data_plane] if self.min_os_version_data_plane else []
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
