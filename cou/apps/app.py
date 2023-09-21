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

"""Application class."""
from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from io import StringIO
from typing import Any, Optional

from juju.client._definitions import ApplicationStatus
from ruamel.yaml import YAML

from cou.exceptions import (
    ApplicationError,
    HaltUpgradePlanGeneration,
    MismatchedOpenStackVersions,
)
from cou.steps import UpgradeStep
from cou.utils import app_utils
from cou.utils.juju_utils import COUModel
from cou.utils.openstack import (
    DISTRO_TO_OPENSTACK_MAPPING,
    OpenStackCodenameLookup,
    OpenStackRelease,
    is_charm_supported,
)

logger = logging.getLogger(__name__)


class AppFactory:
    """Factory class for Application objects."""

    charms: dict[str, type[OpenStackApplication]] = {}

    @classmethod
    def create(
        cls,
        name: str,
        status: ApplicationStatus,
        config: dict,
        model: COUModel,
        charm: str,
    ) -> Optional[OpenStackApplication]:
        """Create the OpenStackApplication or registered subclasses.

        Applications Subclasses registered with the "register_application"
        decorator can be instantiated and used with their customized methods.
        :param name: Name of the application
        :type name: str
        :param status: Status of the application
        :type status: ApplicationStatus
        :param config: Configuration of the application
        :type config: dict
        :param model: COUModel object
        :type model: COUModel
        :param charm: Name of the charm
        :type charm: str
        :return: The OpenStackApplication class or None if not supported.
        :rtype: Optional[OpenStackApplication]
        """
        # pylint: disable=too-many-arguments
        if is_charm_supported(charm):
            app_class = cls.charms.get(charm, OpenStackApplication)
            return app_class(name=name, status=status, config=config, model=model, charm=charm)
        logger.debug(
            "'%s' is not a supported OpenStack related application and will be ignored.",
            name,
        )
        return None

    @classmethod
    def register_application(
        cls, charms: list[str]
    ) -> Callable[[type[OpenStackApplication]], type[OpenStackApplication]]:
        """Register Application subclasses.

        Use this method as decorator to register Applications that
        cannot be described appropriately by the OpenStackApplication class.

        Example:
        ceph_charms = ["ceph-mon", "ceph-fs", "ceph-radosgw", "ceph-osd"]

        @AppFactory.register_application(ceph_charms)
        class Ceph(OpenStackApplication):
            pass
        This is registering the charms "ceph-mon", "ceph-fs", "ceph-radosgw", "ceph-osd"
        to the Ceph class.

        :param charms: List of charms names.
        :type charms: list[str]
        :return: The decorated class. E.g: the Ceph class in the example above.
        :rtype: Callable[[type[OpenStackApplication]], type[OpenStackApplication]]
        """

        def decorator(application: type[OpenStackApplication]) -> type[OpenStackApplication]:
            for charm in charms:
                cls.charms[charm] = application
            return application

        return decorator


@dataclass
class OpenStackApplication:
    """Representation of a charmed OpenStack application in the deployment.

    :param name: Name of the application
    :type name: str
    :param status: Status of the application.
    :type status: ApplicationStatus
    :param config: Configuration of the application.
    :type config: dict
    :param model: COUModel object
    :type model: COUModel
    :param charm: Name of the charm.
    :type charm: str
    :param charm_origin: Origin of the charm (local, ch, cs and etc.), defaults to ""
    :type charm_origin: str, defaults to ""
    :param os_origin: OpenStack origin of the application. E.g: cloud:focal-wallaby, defaults to ""
    :type os_origin: str, defaults to ""
    :param origin_setting: "source" or "openstack-origin" of the charm configuration.
        Return None if not present
    :type origin_setting: Optional[str], defaults to None
    :param channel: Channel that the charm tracks. E.g: "ussuri/stable", defaults to ""
    :type channel: str, defaults to ""
    :param units: Units representation of an application.
        E.g: {"keystone/0": {'os_version': 'victoria', 'workload_version': '2:18.1'}}
    :type units: defaultdict[str, dict]
    :raises ApplicationError: When there are no compatible OpenStack release for the
        workload version.
    :raises MismatchedOpenStackVersions: When units part of this application are running mismatched
        OpenStack versions.
    :raises HaltUpgradePlanGeneration: When the class halts the upgrade plan generation.
    :raises ApplicationUpgradeError: When the application upgrade fails.
    """

    # pylint: disable=too-many-instance-attributes

    name: str
    status: ApplicationStatus
    config: dict
    model: COUModel
    charm: str
    charm_origin: str = ""
    os_origin: str = ""
    origin_setting: Optional[str] = None
    units: defaultdict[str, dict] = field(default_factory=lambda: defaultdict(dict))

    def __post_init__(self) -> None:
        """Initialize the Application dataclass."""
        self.channel = self.status.charm_channel
        self.charm_origin = self.status.charm.split(":")[0]
        self.os_origin = self._get_os_origin()
        # subordinates don't have units
        units = getattr(self.status, "units", {})
        for unit in units.keys():
            workload_version = self.status.units[unit].workload_version
            self.units[unit]["workload_version"] = workload_version
            compatible_os_versions = OpenStackCodenameLookup.find_compatible_versions(
                self.charm, workload_version
            )
            # NOTE(gabrielcocenza) get the latest compatible OpenStack version.
            if compatible_os_versions:
                unit_os_version = max(compatible_os_versions)
                self.units[unit]["os_version"] = unit_os_version
            else:
                raise ApplicationError(
                    f"'{self.name}' with workload version {workload_version} has no compatible "
                    "OpenStack release in the lookup."
                )

    def __hash__(self) -> int:
        """Hash magic method for Application.

        :return: Unique hash identifier for Application object.
        :rtype: int
        """
        return hash(f"{self.name}{self.charm}")

    def __eq__(self, other: Any) -> bool:
        """Equal magic method for Application.

        :param other: Application object to compare.
        :type other: Any
        :return: True if equal False if different.
        :rtype: bool
        """
        return other.name == self.name and other.charm == self.charm

    def __str__(self) -> str:
        """Dump as string.

        :return: Summary representation of an Application.
        :rtype: str
        """
        summary = {
            self.name: {
                "model_name": self.model.name,
                "charm": self.charm,
                "charm_origin": self.charm_origin,
                "os_origin": self.os_origin,
                "channel": self.channel,
                "units": {
                    unit: {
                        "workload_version": details.get("workload_version", ""),
                        "os_version": str(details.get("os_version")),
                    }
                    for unit, details in self.units.items()
                },
            }
        }
        yaml = YAML()
        with StringIO() as stream:
            yaml.dump(summary, stream)
            return stream.getvalue()

    @property
    def expected_current_channel(self) -> str:
        """Return the expected current channel based on the current OpenStack release.

        Note that this is not necessarily equal to the "channel" property since it is
        determined based on the workload version.
        :return: The expected current channel for the application. E.g: ussuri/stable
        :rtype: str
        """
        return f"{self.current_os_release.codename}/stable"

    def target_channel(self, target: OpenStackRelease) -> str:
        """Return the appropriate channel for the passed OpenStack target.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: The next channel for the application. E.g: victoria/stable
        :rtype: str
        """
        return f"{target.codename}/stable"

    @property
    def series(self) -> str:
        """Ubuntu series of the application.

        :return: Ubuntu series of application. E.g: focal
        :rtype: str
        """
        return self.status.series

    @property
    def current_os_release(self) -> OpenStackRelease:
        """Current OpenStack Release of the application.

        :raises MismatchedOpenStackVersions: When units part of this application are
        running mismatched OpenStack versions.
        :return: OpenStackRelease object
        :rtype: OpenStackRelease
        """
        os_versions = {unit_values["os_version"] for unit_values in self.units.values()}

        if len(os_versions) == 1:
            return os_versions.pop()
        # NOTE (gabrielcocenza) on applications that use single-unit or paused-single-unit
        # upgrade methods, more than one version can be found.
        raise MismatchedOpenStackVersions(
            f"Units of application {self.name} are running mismatched OpenStack versions: "
            f"{os_versions}. This is not currently handled."
        )

    @property
    def apt_source_codename(self) -> Optional[OpenStackRelease]:
        """Identify the OpenStack release set on "openstack-origin" or "source" config.

        :raises ApplicationError: If os_origin_parsed is not a valid OpenStack release or os_origin
            is in an unexpected format (ppa, url, etc).
        :return: OpenStackRelease object or None if the app doesn't have os_origin config.
        :rtype: Optional[OpenStackRelease]
        """
        os_origin_parsed: Optional[str]
        # that means that the charm doesn't have "source" or "openstack-origin" config.
        if self.origin_setting is None:
            return None

        # Ex: "cloud:focal-ussuri" will result in "ussuri"
        if self.os_origin.startswith("cloud"):
            *_, os_origin_parsed = self.os_origin.rsplit("-", maxsplit=1)
            try:
                return OpenStackRelease(os_origin_parsed)
            except ValueError as exc:
                raise ApplicationError(
                    f"'{self.name}' has an invalid '{self.origin_setting}': {self.os_origin}"
                ) from exc

        elif self.os_origin == "distro":
            # find the OpenStack release based on ubuntu series
            os_origin_parsed = DISTRO_TO_OPENSTACK_MAPPING[self.series]
            return OpenStackRelease(os_origin_parsed)

        elif self.os_origin == "":
            return None

        else:
            # probably because user set a ppa or an url
            raise ApplicationError(
                f"'{self.name}' has an invalid '{self.origin_setting}': {self.os_origin}"
            )

    @property
    def channel_codename(self) -> OpenStackRelease:
        """Identify the OpenStack release set in the charm channel.

        :return: OpenStackRelease object
        :rtype: OpenStackRelease
        """
        try:
            # get the OpenStack release from the channel track of the application.
            os_track_release_channel = OpenStackRelease(self.channel.split("/", maxsplit=1)[0])
        except ValueError:
            logger.debug(
                "The current channel of '%s' does not exist or is unexpectedly formatted",
                self.name,
            )
            os_track_release_channel = self.current_os_release
        return os_track_release_channel

    def new_origin(self, target: OpenStackRelease) -> str:
        """Return the new openstack-origin or source configuration.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Repository from which to install.
        :rtype: str
        """
        return f"cloud:{self.series}-{target.codename}"

    def _get_os_origin(self) -> str:
        """Get application configuration for openstack-origin or source.

        :return: Configuration parameter of the charm to set OpenStack origin.
            E.g: cloud:focal-wallaby
        :rtype: str
        """
        for origin in ("openstack-origin", "source"):
            if self.config.get(origin):
                self.origin_setting = origin
                return self.config[origin].get("value", "")

        logger.warning("Failed to get origin for %s, no origin config found", self.name)
        return ""

    async def _check_upgrade(self, target: OpenStackRelease) -> None:
        """Check if an application has upgraded its workload version.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :raises ApplicationError: When the workload version of the charm doesn't upgrade.
        """
        status = await self.model.get_status()
        app_status = status.applications.get(self.name)
        units_not_upgraded = []
        for unit in app_status.units.keys():
            workload_version = app_status.units[unit].workload_version
            compatible_os_versions = OpenStackCodenameLookup.find_compatible_versions(
                self.charm, workload_version
            )
            if target not in compatible_os_versions:
                units_not_upgraded.append(unit)

        if units_not_upgraded:
            units_not_upgraded_string = ", ".join(units_not_upgraded)
            raise ApplicationError(
                f"Cannot upgrade units '{units_not_upgraded_string}' to {target}."
            )

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
        ]

    def upgrade_plan(self, target: OpenStackRelease) -> list[Optional[UpgradeStep]]:
        """Upgrade planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :raises HaltUpgradePlanGeneration: When the application halt the upgrade plan generation.
        :return: Plan that will add upgrade as sub steps.
        :rtype: list[Optional[UpgradeStep]]
        """
        if self.current_os_release >= target and self.apt_source_codename >= target:
            msg = (
                f"Application '{self.name}' already configured for release equal or greater "
                f"than {target}. Ignoring."
            )
            logger.info(msg)
            raise HaltUpgradePlanGeneration(msg)

        return [
            self._get_disable_action_managed_plan(),
            self._get_upgrade_charm_plan(target),
            self._get_workload_upgrade_plan(target),
        ]

    def post_upgrade_plan(self, target: OpenStackRelease) -> list[UpgradeStep]:
        """Post Upgrade planning.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :return: Plan that will add post upgrade as sub steps.
        :rtype: list[UpgradeStep]
        """
        return [self._get_reached_expected_target_plan(target)]

    def generate_upgrade_plan(self, target: str) -> UpgradeStep:
        """Generate full upgrade plan for an Application.

        :param target: OpenStack codename to upgrade.
        :type target: str
        :return: Full upgrade plan if the Application is able to generate it.
        :rtype: UpgradeStep
        """
        target_version = OpenStackRelease(target)
        upgrade_steps = UpgradeStep(
            description=f"Upgrade plan for '{self.name}' to {target}",
            parallel=False,
            function=None,
        )
        all_steps = (
            self.pre_upgrade_plan(target_version)
            + self.upgrade_plan(target_version)
            + self.post_upgrade_plan(target_version)
        )
        for step in all_steps:
            if step:
                upgrade_steps.add_step(step)
        return upgrade_steps

    def _get_upgrade_current_release_packages_plan(self, parallel: bool = False) -> UpgradeStep:
        """Get Plan for upgrading software packages to the latest of the current release.

        :param parallel: Parallel running, defaults to False
        :type parallel: bool, optional
        :return plan: Plan for upgrading software packages to the latest of the current release.
        :type plan: UpgradeStep
        """
        dpkg_opts = "-o Dpkg::Options::=--force-confnew -o Dpkg::Options::=--force-confdef"
        command = f"apt-get update && apt-get dist-upgrade {dpkg_opts} -y && apt-get autoremove -y"

        return UpgradeStep(
            description=(
                f"Upgrade software packages of '{self.name}' from the current APT repositories"
            ),
            parallel=parallel,
            function=app_utils.run_on_all_units,
            units=self.status.units.keys(),
            model=self.model,
            command=command,
        )

    def _get_refresh_charm_plan(
        self, target: OpenStackRelease, parallel: bool = False
    ) -> Optional[UpgradeStep]:
        """Get plan for refreshing the current channel.

        This function also identifies if charm comes from charmstore and in that case,
        makes the migration.
        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param parallel: Parallel running, defaults to False
        :type parallel: bool, optional
        :return: Plan for refreshing the charm.
        :rtype: Optional[UpgradeStep]
        """
        switch = None
        description = (
            f"Changing '{self.name}' channel from: '{self.channel}' "
            f"to: '{self.expected_current_channel}'"
        )

        if self.charm_origin == "cs":
            description = f"Migration of '{self.name}' from charmstore to charmhub"
            switch = f"ch:{self.charm}"
        elif self.channel == self.expected_current_channel:
            description = (
                f"Refresh '{self.name}' to the latest revision of "
                f"'{self.expected_current_channel}'"
            )
        elif self.channel_codename >= target:
            logger.info(
                "Skipping charm refresh for %s, its channel is already set to %s.",
                self.name,
                self.channel,
            )
            return None

        return UpgradeStep(
            description=description,
            parallel=parallel,
            function=self.model.upgrade_charm,
            application_name=self.name,
            channel=self.expected_current_channel,
            model=self.model,
            switch=switch,
        )

    def _get_upgrade_charm_plan(
        self, target: OpenStackRelease, parallel: bool = False
    ) -> Optional[UpgradeStep]:
        """Get plan for upgrading the charm.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param parallel: Parallel running, defaults to False
        :type parallel: bool, optional
        :return: Plan for upgrading the charm.
        :rtype: Optional[UpgradeStep]
        """
        if self.channel != self.target_channel(target):
            return UpgradeStep(
                description=(
                    f"Upgrade '{self.name}' to the new channel: '{self.target_channel(target)}'"
                ),
                parallel=parallel,
                function=self.model.upgrade_charm,
                application_name=self.name,
                channel=self.target_channel(target),
                model=self.model,
            )
        return None

    def _get_disable_action_managed_plan(self, parallel: bool = False) -> Optional[UpgradeStep]:
        """Get plan to disable action-managed-upgrade.

        This is used to upgrade as "all-in-one" strategy.

        :param parallel: Parallel running, defaults to False
        :type parallel: bool, optional
        :return: Plan to disable action-managed-upgrade
        :rtype: Optional[UpgradeStep]
        """
        if self.config.get("action-managed-upgrade", {}).get("value", False):
            return UpgradeStep(
                description=(
                    f"Change charm config of '{self.name}' " "'action-managed-upgrade' to False."
                ),
                parallel=parallel,
                function=self.model.set_application_config,
                application_name=self.name,
                configuration={"action-managed-upgrade": False},
                model=self.model,
            )
        return None

    def _get_workload_upgrade_plan(
        self, target: OpenStackRelease, parallel: bool = False
    ) -> Optional[UpgradeStep]:
        """Get workload upgrade plan by changing openstack-origin or source.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param parallel: Parallel running, defaults to False
        :type parallel: bool, optional
        :return: Workload upgrade plan
        :rtype: Optional[UpgradeStep]
        """
        if self.os_origin != self.new_origin(target):
            return UpgradeStep(
                description=(
                    f"Change charm config of '{self.name}' "
                    f"'{self.origin_setting}' to '{self.new_origin(target)}'"
                ),
                parallel=parallel,
                function=self.model.set_application_config,
                application_name=self.name,
                configuration={self.origin_setting: self.new_origin(target)},
                model=self.model,
            )
        logger.warning(
            "Not triggering the workload upgrade of app %s: %s already set to %s",
            self.name,
            self.origin_setting,
            self.new_origin(target),
        )
        return None

    def _get_reached_expected_target_plan(
        self, target: OpenStackRelease, parallel: bool = False
    ) -> UpgradeStep:
        """Get plan to check if application workload has been upgraded.

        :param target: OpenStack release as target to upgrade.
        :type target: OpenStackRelease
        :param parallel: Parallel running, defaults to False
        :type parallel: bool, optional
        :return: Plan to check if application workload has been upgraded
        :rtype: UpgradeStep
        """
        return UpgradeStep(
            description=f"Check if the workload of '{self.name}' has been upgraded",
            parallel=parallel,
            function=self._check_upgrade,
            target=target,
        )
