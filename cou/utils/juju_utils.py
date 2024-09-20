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

"""Juju utilities for charmed-openstack-upgrader."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, List, Optional, Sequence

from juju.action import Action
from juju.application import Application as JujuApplication
from juju.client._definitions import ApplicationStatus, Base, FullStatus
from juju.client.connector import NoConnectionException
from juju.client.jujudata import FileJujuData
from juju.errors import JujuAppError, JujuConnectionError, JujuError, JujuUnitError
from juju.model import Model as JujuModel
from juju.unit import Unit as JujuUnit
from juju.utils import get_version_series
from macaroonbakery.httpbakery import BakeryException
from six import wraps

from cou.exceptions import (
    ActionFailed,
    ApplicationError,
    ApplicationNotFound,
    CommandRunFailed,
    TimeoutException,
    UnitNotFound,
    WaitForApplicationsTimeout,
)
from cou.utils.openstack import is_charm_supported

# Increase Juju websocket connection MAX_FRAME_SIZE to 1024MiB to stop
# "RPC: Connection closed, reconnecting" errors and then a failure in the log.
# See https://github.com/juju/python-libjuju/issues/458 for more details
JUJU_MAX_FRAME_SIZE: int = 2**30
DEFAULT_TIMEOUT: int = int(os.environ.get("COU_TIMEOUT", 10))
DEFAULT_MAX_WAIT: int = 5
DEFAULT_WAIT: float = 1.1
DEFAULT_MODEL_RETRIES: int = int(os.environ.get("COU_MODEL_RETRIES", 5))
DEFAULT_MODEL_RETRY_BACKOFF: int = int(os.environ.get("COU_MODEL_RETRY_BACKOFF", 2))
DEFAULT_MODEL_IDLE_PERIOD: int = 30

logger = logging.getLogger(__name__)


def _convert_base_to_series(base: Base) -> str:
    """Convert base to series.

    :param base: Base object
    :type base: juju.client._definitions.Base
    :return: converted channel to series, e.g. 20.04 -> focal
    :rtype: str
    """
    version, *_ = base.channel.split("/")
    return get_version_series(version)


def retry(
    function: Optional[Callable] = None,
    timeout: int = DEFAULT_TIMEOUT,
    no_retry_exceptions: tuple = (),
) -> Callable:
    """Retry function for usage in Model.

    :param function: function to be wrapped
    :type function: Optional[Callable]
    :param timeout: timeout in seconds
    :type timeout: int
    :param no_retry_exceptions: tuple of exception on which function will not be retried
    :type no_retry_exceptions: tuple
    :return: wrapped function
    :rtype: Callable
    """

    def _wrapper(func: Callable) -> Callable:  # pylint: disable=W9011
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:  # pylint: disable=W9011
            attempt: int = 0
            start_time = datetime.now()
            while (datetime.now() - start_time).seconds <= timeout:
                try:
                    return await func(*args, **kwargs)
                except (TimeoutException, *no_retry_exceptions):
                    # raising exception if no_retry_exception happen or TimeoutException
                    raise
                except Exception:  # pylint: disable=broad-exception-caught
                    logger.info("function %s failed [%d]", func.__name__, attempt, exc_info=True)
                    await asyncio.sleep(DEFAULT_WAIT**attempt)
                    attempt += 1

            # if while loop ends, it means we reached the timeout
            raise TimeoutException(f"function {func.__name__} timed out after {timeout}s")

        return wrapper

    if function is not None:
        return _wrapper(function)

    return _wrapper


@dataclass(frozen=True)
class Machine:
    """Representation of a juju machine."""

    machine_id: str
    apps_charms: tuple[tuple[str, str], ...]
    az: Optional[str] = None  # simple deployments may not have azs


@dataclass(frozen=True)
class SubordinateUnit:
    """Representation of a single unit of subordinate unit."""

    name: str
    charm: str

    def __repr__(self) -> str:
        """App representation.

        :return: Name of the application
        :rtype: str
        """
        return self.name


@dataclass(frozen=True)
class Unit:
    """Representation of a single unit of application."""

    name: str
    machine: Machine
    workload_version: str
    subordinates: List[SubordinateUnit] = field(default_factory=lambda: [], compare=False)

    def __repr__(self) -> str:
        """App representation.

        :return: Name of the application
        :rtype: str
        """
        return self.name


@dataclass(frozen=True)
class Application:
    """Representation of a single application."""

    # pylint: disable=too-many-instance-attributes

    name: str
    can_upgrade_to: str
    charm: str
    channel: str
    config: dict[str, Any]
    machines: dict[str, Machine]
    model: Model
    origin: str
    series: str
    subordinate_to: list[str]
    units: dict[str, Unit]
    workload_version: str
    actions: dict[str, str] = field(default_factory=lambda: {}, compare=False)

    @property
    def is_subordinate(self) -> bool:
        """Check if application is subordinate.

        :return: True if subordinate, False otherwise.
        :rtype: bool
        """
        return bool(self.subordinate_to)

    @property
    def is_from_charm_store(self) -> bool:
        """Check if application comes from charm store.

        :return: True if comes, False otherwise.
        :rtype: bool
        """
        return self.origin == "cs"


class Model:
    """COU model object.

    This version of the model provides better waiting for the model to turn idle, auto-reconnection
    and some other required features for COU.
    """

    def __init__(self, name: Optional[str]):
        """COU Model initialization with name and juju.model.Model."""
        self._juju_data = FileJujuData()
        self._model = JujuModel(max_frame_size=JUJU_MAX_FRAME_SIZE, jujudata=self.juju_data)
        self._name = name

    @property
    def connected(self) -> bool:
        """Check if model is connected."""
        try:
            connection = self._model.connection()
            return connection is not None and connection.is_open
        except NoConnectionException:
            return False

    @property
    def juju_data(self) -> FileJujuData:
        """Juju data."""
        return self._juju_data

    @property
    def name(self) -> str:
        """Return model name."""
        if self.connected:
            return self._model.name

        if self._name is None:
            self._name = self.juju_data.current_model(model_only=True)

        return self._name

    @retry(no_retry_exceptions=(ActionFailed,))
    async def _get_waited_action_object(self, action: Action, raise_on_failure: bool) -> Action:
        """Get waited action object.

        To access action data from the returned action object, use `action_obj.data`, which
        contains action parameters, results, status, and metadata. Alternatively, it is possible
        to access action results directly with `action_obj.results`.

        :param action: Action object
        :type: Action
        :param raise_on_failure: Whether to raise ActionFailed exception on failure, defaults
                                 to False
        :type raise_on_failure: bool
        :return: the awaited action object
        :rtype: Action
        :raises ActionFailed: When the application status is in error (it's not 'completed').
        """
        action_obj = await action.wait()
        if raise_on_failure and action_obj.status != "completed":
            logger.error("action %s failed", action_obj)
            raise ActionFailed(action)

        return action_obj

    async def _get_application(self, name: str) -> JujuApplication:
        """Get juju.application.Application from model.

        :param name: Name of application
        :type name: str
        :raises ApplicationNotFound: When application is not found in the model.
        :return: Application
        :rtype: JujuApplication
        """
        model = await self._get_model()
        app = model.applications.get(name)
        if app is None:
            raise ApplicationNotFound(f"Application {name} was not found in model {model.name}.")

        return app

    async def _get_machines(self) -> dict[str, Machine]:
        """Get all the machines in the model.

        :return: Dictionary of the machines found in the model. E.g: {'0': Machine0}
        :rtype: dict[str, Machine]
        """
        model = await self._get_model()

        return {
            machine.id: Machine(
                machine_id=machine.id,
                apps_charms=self._get_machine_apps_and_charms(machine.id),
                az=machine.hardware_characteristics.get("availability-zone"),
            )
            for machine in model.machines.values()
        }

    def _get_machine_apps_and_charms(self, machine_id: int) -> tuple[tuple[str, str], ...]:
        """Get machine apps amd charm names.

        :param machine_id: Machine id.
        :type machine_id: int
        :return: Tuple of tuple contains app name and charm name.
        :rtype: tuple[tuple[str, str], ...]
        """
        return tuple(
            (str(unit.application), str(self._model.applications[unit.application].charm_name))
            for unit in self._model.units.values()
            if unit.machine.id == machine_id
        )

    async def _get_model(self) -> JujuModel:
        """Get juju.model.Model and make sure that it is connected.

        :return: Model
        :rtype: JujuModel
        """
        if not self.connected:
            await self.connect()

        return self._model

    async def _get_supported_apps(self) -> list[str]:
        """Get all applications supported by COU deployed in model.

        :return: List of applications names supported by COU
        :rtype: list[str]
        """
        model = await self._get_model()
        return [
            name for name, app in model.applications.items() if is_charm_supported(app.charm_name)
        ]

    async def get_unit(self, name: str) -> JujuUnit:
        """Get juju.unit.unit from model.

        :param name: Name of unit
        :type name: str
        :raises UnitNotFound: When unit is not found in the model.
        :return: Unit
        :rtype: JujuUnit
        """
        model = await self._get_model()
        unit = model.units.get(name)
        if unit is None:
            raise UnitNotFound(f"Unit {name} was not found in model {model.name}.")

        return unit

    @retry(no_retry_exceptions=(BakeryException, JujuConnectionError))
    async def connect(self) -> None:
        """Make sure that model is connected."""
        await self._model.disconnect()
        await self._model.connect(
            model_name=self._name,
            retries=DEFAULT_MODEL_RETRIES,
            retry_backoff=DEFAULT_MODEL_RETRY_BACKOFF,
        )

    @retry
    async def get_applications(self) -> dict[str, Application]:
        """Return list of applications with all relevant information.

        :returns: list of application with all information
        :rtype: list[Application]
        """
        model = await self._get_model()
        # note(rgildein): We get the applications from the Juju status, since we can get more
        #                 information the status than from objects. e.g. workload_version for unit
        full_status = await self.get_status()
        machines = await self._get_machines()

        return {
            app: Application(
                name=app,
                can_upgrade_to=status.can_upgrade_to,
                charm=model.applications[app].charm_name,
                channel=status.charm_channel,
                config=await model.applications[app].get_config(),
                machines={
                    unit.machine.id: machines[unit.machine.id]
                    for unit in model.applications[app].units
                },
                model=self,
                origin=status.charm.split(":")[0],
                series=_convert_base_to_series(status.base),
                subordinate_to=status.subordinate_to,
                units={
                    name: Unit(
                        name,
                        machines[unit.machine],
                        unit.workload_version,
                        [
                            SubordinateUnit(
                                subordinate,
                                model.applications[subordinate.split("/")[0]].charm_name,
                            )
                            for subordinate, subordinate_unit in unit.subordinates.items()
                        ],
                    )
                    for name, unit in status.units.items()
                },
                workload_version=status.workload_version,
                actions=await model.applications[app].get_actions(),
            )
            for app, status in full_status.applications.items()
        }

    @retry(no_retry_exceptions=(ApplicationNotFound,))
    async def get_application_config(self, name: str) -> dict:
        """Return application configuration.

        :param name: Name of application
        :type name: str
        :returns: Dictionary of configuration
        :rtype: dict
        :raises: ApplicationNotFound
        """
        app = await self._get_application(name)
        return await app.get_config()

    async def get_charm_name(self, application_name: str) -> str:
        """Get the charm name from the application.

        :param application_name: Name of application
        :type application_name: str
        :raises ApplicationError: if charm_name is None
        :return: Charm name
        :rtype: str
        """
        app = await self._get_application(application_name)
        if app.charm_name is None:
            raise ApplicationError(f"Cannot obtain charm_name for {application_name}")

        return app.charm_name

    @retry
    async def get_status(self) -> FullStatus:
        """Return the full juju status output.

        :returns: Full juju status output
        :rtype: FullStatus
        """
        model = await self._get_model()
        return await model.get_status()

    async def _dispatch_update_status_hook(self, unit_name: str) -> None:
        """Use dispatch to run the update-status hook.

        Legacy and reactive charm allows the operators to directly run hooks
        inside the charm code directly; while the operator framework uses
        ./dispatch script to dispatch the hooks. This method use dispatch to
        run the hook.

        :param unit_name: Name of the unit to run update-status hook
        :type unit_name: str
        :raises CommandRunFailed: When update-status hook failed
        """
        await self.run_on_unit(unit_name, "JUJU_DISPATCH_PATH=hooks/update-status ./dispatch")

    async def _run_update_status_hook(self, unit_name: str) -> None:
        """Run the update-status hook directly.

        Legacy and reactive charm allows the operators to directly run hooks
        inside the charm code directly; while the operator framework uses
        ./dispatch script to dispatch the hooks. This method run the hook
        directly.

        :param unit_name: Name of the unit to run update-status hook
        :type unit_name: str
        :raises CommandRunFailed: When update-status hook failed
        """
        await self.run_on_unit(unit_name, "hooks/update-status")

    async def update_status(self, unit_name: str) -> None:
        """Run the update_status hook on the given unit.

        :param unit_name: Name of the unit to run update-status hook
        :type unit_name: str
        :raises CommandRunFailed: When update-status hook failed
        """
        # For charm written in operator framework
        try:
            await self._dispatch_update_status_hook(unit_name)
        except CommandRunFailed as e:
            if "No such file or directory" not in str(e):
                raise e
        else:
            return

        # For charm written in legacy / reactive framework
        try:
            await self._run_update_status_hook(unit_name)
        except CommandRunFailed as e:
            if "No such file or directory" not in str(e):
                raise e
        else:
            return

        logger.debug("Skipped updating status: file does not exist")

    # NOTE (rgildein): There is no need to add retry here, because we don't want to repeat
    # `unit.run_action(...)` and the rest of the function is covered by retry.
    async def run_action(
        self,
        unit_name: str,
        action_name: str,
        action_params: Optional[dict] = None,
        raise_on_failure: bool = False,
    ) -> Action:
        """Run action on given unit.

        :param unit_name: Name of unit to run action on
        :type unit_name: str
        :param action_name: Name of action to run
        :type action_name: str
        :param action_params: Dictionary of config options for action, defaults to None
        :type action_params: Optional[dict], optional
        :param raise_on_failure: Raise ActionFailed exception on failure, defaults to False
        :type raise_on_failure: bool
        :raises UnitNotFound: When a valid unit cannot be found.
        :raises ActionFailed: When the application status is in error (it's not 'completed').
        :return: When status is different from "completed"
        :rtype: Action
        """
        action_params = action_params or {}
        unit = await self.get_unit(unit_name)
        action = await unit.run_action(action_name, **action_params)
        action_obj = await self._get_waited_action_object(action, raise_on_failure)
        return action_obj

    # NOTE (rgildein): There is no need to add retry here, because we don't want to repeat
    # `unit.run(...)` and the rest of the function is static.
    async def run_on_unit(
        self, unit_name: str, command: str, timeout: Optional[int] = None
    ) -> dict[str, str]:
        """Juju run on unit.

        :param unit_name: Name of unit to match
        :type unit_name: str
        :param command: Command to execute
        :type command: str
        :param timeout: How long in seconds to wait for command to complete
        :type timeout: Optional[int]
        :returns: action.results {'return-code': 0, 'stderr': '', 'stdout': ''}
        :rtype: dict[str, str]
        :raises UnitNotFound: When a valid unit cannot be found.
        :raises CommandRunFailed: When a command fails to run.
        """
        logger.debug("Running '%s' on '%s'", command, unit_name)

        unit = await self.get_unit(unit_name)
        action = await unit.run(command, timeout=timeout, block=True)
        results = action.results
        logger.debug("results: %s", results)

        if results["return-code"] != 0:
            raise CommandRunFailed(cmd=command, result=results)

        return results

    @retry(no_retry_exceptions=(ApplicationNotFound,))
    async def set_application_config(self, name: str, configuration: dict[str, str]) -> None:
        """Set application configuration.

        :param name: Name of application
        :type name: str
        :param configuration: Dictionary of configuration setting(s)
        :type configuration: dict[str, Any]
        """
        app = await self._get_application(name)
        await app.set_config(configuration)

    # pylint: disable=too-many-arguments
    @retry(no_retry_exceptions=(UnitNotFound,))
    async def scp_from_unit(
        self,
        unit_name: str,
        source: str,
        destination: str,
        user: str = "ubuntu",
        proxy: bool = False,
        scp_opts: str = "",
    ) -> None:
        """Transfer files from unit_name.

        :param unit_name: Name of unit to scp from
        :type unit_name: str
        :param source: Remote path of file(s) to transfer
        :type source: str
        :param destination: Local destination of transferred files
        :type source: str
        :param user: Remote username, defaults to ubuntu
        :type source: str
        :param proxy: Proxy through the Juju API server, defaults to False
        :type proxy: bool
        :param scp_opts: Additional options to the scp command, defaults to ""
        :type scp_opts: str
        :raises: UnitNotFound
        """
        unit = await self.get_unit(unit_name)
        await unit.scp_from(source, destination, user=user, proxy=proxy, scp_opts=scp_opts)

    # pylint: disable=too-many-arguments
    @retry(
        no_retry_exceptions=(
            ApplicationNotFound,
            NotImplementedError,
            ValueError,
            JujuError,
        )
    )
    async def upgrade_charm(
        self,
        application_name: str,
        channel: Optional[str] = None,
        force_series: bool = False,
        force_units: bool = False,
        path: Optional[str] = None,
        revision: Optional[int] = None,
        switch: Optional[str] = None,
    ) -> None:
        """
        Upgrade the given charm.

        :param application_name: Name of application on this side of relation
        :type application_name: str
        :param channel: Channel to use when getting the charm from the charm store,
                        e.g. 'development'
        :type channel: str
        :param force_series: Upgrade even if series of deployed application is not
                            supported by the new charm
        :type force_series: bool
        :param force_units: Upgrade all units immediately, even if in error state
        :type force_units: bool
        :param path: Upgrade to a charm located at path
        :type path: str
        :param revision: Explicit upgrade revision
        :type revision: int
        :param switch: Crossgrade charm url
        :type switch: str
        :raises: ApplicationNotFound
        """
        app = await self._get_application(application_name)
        await app.upgrade_charm(
            channel=channel,
            force_series=force_series,
            force_units=force_units,
            path=path,
            revision=revision,
            switch=switch,
        )

    async def wait_for_idle(
        self,
        timeout: int,
        status: str = "active",
        idle_period: int = DEFAULT_MODEL_IDLE_PERIOD,
        apps: Optional[list[str]] = None,
        raise_on_blocked: bool = False,
        raise_on_error: bool = True,
    ) -> None:
        """Wait for application(s) to reach target idle state.

        If no applications are provided, this function will wait for all COU-related applications.

        :param timeout: How long (in seconds) to wait for the bundle settles before raising an
                        WaitForApplicationsTimeout.
        :type timeout: int
        :param status: The status to wait for.
        :type status: str
        :param idle_period: How long (in seconds) statuses of all apps need to be `idle`. This
                            delay is used to ensure that any pending hooks have a chance to start
                            to avoid false positives.
        :type idle_period: int
        :param apps: Applications to wait, defaults to None
        :type apps: Optional[list[str]]
        :param raise_on_blocked: If any unit or app going into "blocked" status immediately raises
                                 WaitForApplicationsTimeout, defaults to False.
        :type raise_on_blocked: bool
        :param raise_on_error: If any unit or app going into "error" status immediately raises
                                 WaitForApplicationsTimeout, defaults to True.
        :type raise_on_error: bool
        """
        if apps is None:
            apps = await self._get_supported_apps()

        @retry(timeout=timeout, no_retry_exceptions=(WaitForApplicationsTimeout,))
        @wraps(self.wait_for_idle)
        async def _wait_for_idle() -> None:
            # NOTE(rgildein): Defining wrapper so we can use retry with proper timeout
            model = await self._get_model()
            try:
                # NOTE(rgildein): Use asyncio.gather because we always go through the application
                # list (apps will never be None) and libjuju is very slow here.
                # https://github.com/juju/python-libjuju/issues/1055
                await asyncio.gather(
                    *(
                        model.wait_for_idle(
                            apps=[app],
                            timeout=timeout,
                            idle_period=idle_period,
                            raise_on_blocked=raise_on_blocked,
                            raise_on_error=raise_on_error,
                            status=status,
                        )
                        for app in apps
                    )
                )
            except (asyncio.exceptions.TimeoutError, JujuAppError, JujuUnitError) as error:
                # NOTE(rgildein): Catching TimeoutError raised as exception when wait_for_idle
                # reached timeout. Also adding two spaces to make it more user friendly.
                # example:
                # Timed out waiting for model:
                #   rabbitmq-server/0 [idle] active: Unit is ready
                #   neutron-api/0 [idle] active: Unit is ready
                #   glance/0 [idle] active: Unit is ready
                #   cinder/0 [idle] active: Unit is ready
                msg = str(error).replace("\n", "\n  ", 1)
                raise WaitForApplicationsTimeout(msg) from error

        await _wait_for_idle()

    async def resolve_all(self) -> None:
        """Resolve all the units in the model if they are in error status."""
        model = await self._get_model()
        for _, juju_app in model.applications.items():
            for unit in juju_app.units:
                if unit.workload_status == "error":
                    await unit.resolved(retry=True)

    async def get_application_names(self, charm_name: str) -> list[str]:
        """Get application name by charm name.

        :param charm_name: charm name of application
        :type charm_name: str
        :return: ApplicationStatus object
        :rtype: ApplicationStatus
        :raises ApplicationNotFound: When charm is not found in the model.
        """
        app_names = []
        model = await self._get_model()
        for app_name, app in model.applications.items():
            if app.charm_name == charm_name:
                app_names.append(app_name)
        if not app_names:
            raise ApplicationNotFound(f"Cannot find '{charm_name}' charm in model '{self.name}'.")
        return app_names

    async def get_application_status(self, app_name: str) -> ApplicationStatus:
        """Get ApplicationStatus by charm name.

        :param app_name: name of application
        :type app_name: str
        :return: ApplicationStatus object
        :rtype: ApplicationStatus
        :raises ApplicationNotFound: When application is not found in the model.
        """
        model = await self._get_model()
        status = await model.get_status(filters=[app_name])
        for name, app in status.applications.items():
            if name == app_name:
                return app
        raise ApplicationNotFound(f"Cannot find '{app_name}' in model '{self.name}'.")


def get_applications_by_charm_name(
    apps: Sequence[Application], charm_name: str
) -> Sequence[Application]:
    """Get all applications based on the charm name.

    :param apps: List of Application
    :type apps: Sequence[Application]
    :param charm_name: The charm name
    :type charm_name: str
    :return: A list of Application filtered by charm name
    :type: Sequence[Application]
    :raise ApplicationNotFound: When cannot find a valid application with that name
    """
    filtered_apps = [app for app in apps if app.charm == charm_name]
    if not filtered_apps:
        raise ApplicationNotFound(f"Application with '{charm_name}' not found")
    return filtered_apps
