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
import json
import logging
import os
import shlex
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, List, Optional, Sequence

import jubilant
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

DEFAULT_TIMEOUT: int = int(os.environ.get("COU_TIMEOUT", 10))
DEFAULT_MAX_WAIT: int = 5
DEFAULT_WAIT: float = 1.1
DEFAULT_MODEL_RETRIES: int = int(os.environ.get("COU_MODEL_RETRIES", 5))
DEFAULT_MODEL_RETRY_BACKOFF: int = int(os.environ.get("COU_MODEL_RETRY_BACKOFF", 2))
DEFAULT_MODEL_IDLE_PERIOD: int = 30

_VERSION_SERIES_MAP: dict[str, str] = {
    "18.04": "bionic",
    "20.04": "focal",
    "22.04": "jammy",
    "24.04": "noble",
}

logger = logging.getLogger(__name__)


def _convert_base_to_series(base: jubilant.statustypes.FormattedBase) -> str:
    """Convert base to series.

    :param base: FormattedBase object
    :type base: jubilant.statustypes.FormattedBase
    :return: converted channel to series, e.g. 20.04 -> focal
    :rtype: str
    """
    version, *_ = base.channel.split("/")
    return _VERSION_SERIES_MAP.get(version, version)


def _parse_availability_zone(hardware: str) -> Optional[str]:
    """Parse availability zone from hardware string.

    :param hardware: Hardware string from juju status, e.g.
        "arch=amd64 availability-zone=nova"
    :type hardware: str
    :return: Availability zone if present, else None
    :rtype: Optional[str]
    """
    for part in hardware.split():
        if part.startswith("availability-zone="):
            return part.split("=", 1)[1]
    return None


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

    def _wrapper(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
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


class JubilantModelMixin:

    @staticmethod
    def _get_error_callable(
        raise_on_error: bool, raise_on_blocked: bool
    ) -> Callable[[jubilant.Status], bool]:
        def callable(status: jubilant.Status, *apps: str) -> bool:
            any_error: bool = True
            any_blocked: bool = True
            if raise_on_error:
                any_error = jubilant.any_error(status, *apps)
            if raise_on_blocked:
                any_blocked = jubilant.any_blocked(status, *apps)
            return any_error and any_blocked

        return callable

    @staticmethod
    def _get_ready_callable(target_status: str) -> Callable[[jubilant.Status], bool]:
        def callable(status: jubilant.Status, *apps: str) -> bool:
            check_workload_status_func = jubilant.all_active
            if target_status == "blocked":
                check_workload_status_func = jubilant.all_blocked
            elif target_status == "maintenance":
                check_workload_status_func = jubilant.all_maintenance
            elif target_status == "waiting":
                check_workload_status_func = jubilant.all_waiting
            elif target_status == "error":
                check_workload_status_func = jubilant.all_error
            return check_workload_status_func(status, *apps) and jubilant.all_agents_idle(
                status, *apps
            )

        return callable

    async def wait_for_idle(  # pylint: disable=too-many-arguments,too-many-positional-arguments
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

        # jubilant init only init the python object, no connection is created.
        # so it's safy to init every time.
        _juju = jubilant.Juju(model=self._juju.model, wait_timeout=timeout)

        ready_callable = self._get_ready_callable(status)
        error_callable = self._get_error_callable(raise_on_error, raise_on_blocked)

        @retry(timeout=timeout, no_retry_exceptions=(WaitForApplicationsTimeout,))
        @wraps(self.wait_for_idle)
        async def _wait_for_idle(*apps: str) -> None:
            try:
                _juju.wait(
                    ready=lambda status: ready_callable(status, *apps),
                    error=lambda status: error_callable(status, *apps),
                    successes=10,
                )
            except (TimeoutError, jubilant.WaitError) as error:
                raise WaitForApplicationsTimeout(str(error)) from error

        tasks = [_wait_for_idle(*apps)]
        await asyncio.gather(*tasks)


class Model(JubilantModelMixin):
    """COU model object.

    This version of the model provides better waiting for the model to turn idle, auto-reconnection
    and some other required features for COU.
    """

    def __init__(self, name: Optional[str]):
        """COU Model initialization with name and jubilant.Juju."""
        self._name = name
        self._juju = jubilant.Juju(model=name)

    @property
    def connected(self) -> bool:
        """Check if model is accessible."""
        try:
            self._juju.show_model()
            return True
        except Exception:  # pylint: disable=broad-exception-caught
            return False

    @property
    def name(self) -> str:
        """Return model name."""
        if self._name is not None:
            return self._name
        return self._juju.show_model().short_name

    async def connect(self) -> None:
        """Validate the model is accessible.

        In jubilant, connections are established implicitly per CLI call.
        This method validates accessibility and caches the model name.
        """
        model_info = self._juju.show_model()
        if self._name is None:
            self._name = model_info.short_name

    def _get_machine_apps_and_charms(
        self, machine_id: str, status: jubilant.Status
    ) -> tuple[tuple[str, str], ...]:
        """Get machine apps and charm names.

        :param machine_id: Machine id.
        :type machine_id: str
        :param status: Jubilant Status object.
        :type status: jubilant.Status
        :return: Tuple of tuple contains app name and charm name.
        :rtype: tuple[tuple[str, str], ...]
        """
        return tuple(
            (app_name, app_status.charm_name)
            for app_name, app_status in status.apps.items()
            for unit_status in app_status.units.values()
            if unit_status.machine == machine_id
        )

    async def _get_machines(self, status: jubilant.Status) -> dict[str, Machine]:
        """Get all the machines in the model.

        :param status: Optional pre-fetched jubilant Status. Fetched if not provided.
        :type status: Optional[jubilant.Status]
        :return: Dictionary of the machines found in the model. E.g: {'0': Machine0}
        :rtype: dict[str, Machine]
        """
        return {
            machine_id: Machine(
                machine_id=machine_id,
                apps_charms=self._get_machine_apps_and_charms(machine_id, status),
                az=_parse_availability_zone(machine_status.hardware),
            )
            for machine_id, machine_status in status.machines.items()
        }

    async def _get_supported_apps(self) -> list[str]:
        """Get all applications supported by COU deployed in model.

        :return: List of applications names supported by COU
        :rtype: list[str]
        """
        status = self._juju.status()
        return [
            app_name
            for app_name, app_status in status.apps.items()
            if is_charm_supported(app_status.charm_name)
        ]

    async def get_unit(self, name: str) -> jubilant.statustypes.UnitStatus:
        """Get jubilant UnitStatus from model.

        :param name: Name of unit
        :type name: str
        :raises UnitNotFound: When unit is not found in the model.
        :return: UnitStatus
        :rtype: jubilant.statustypes.UnitStatus
        """
        status = self._juju.status()
        for app_status in status.apps.values():
            if name in app_status.units:
                return app_status.units[name]
        raise UnitNotFound(f"Unit {name} was not found in model {self.name}.")

    @retry
    async def get_applications(self) -> dict[str, Application]:
        """Return list of applications with all relevant information.

        :returns: list of application with all information
        :rtype: list[Application]
        """
        status = await self.get_status()
        machines = await self._get_machines(status)

        result = {}
        for app_name, app_status in status.apps.items():
            config = json.loads(self._juju.cli("config", app_name, "--format", "json")).get(
                "settings", {}
            )

            try:
                actions_stdout = self._juju.cli("actions", app_name, "--format", "json")
                actions_raw = json.loads(actions_stdout) if actions_stdout.strip() else {}
                actions = {
                    k: v.get("description", "") if isinstance(v, dict) else str(v)
                    for k, v in actions_raw.items()
                }
            except (jubilant.CLIError, json.JSONDecodeError, ValueError):
                actions = {}

            app_machines = {}
            for unit_status in app_status.units.values():
                machine_id = unit_status.machine
                if machine_id and machine_id in machines:
                    app_machines[machine_id] = machines[machine_id]

            units = {
                unit_name: Unit(
                    name=unit_name,
                    machine=machines.get(unit_status.machine, Machine(unit_status.machine, ())),
                    workload_version=unit_status.workload_status.version,
                    subordinates=[
                        SubordinateUnit(
                            sub_name,
                            status.apps[sub_name.split("/")[0]].charm_name,
                        )
                        for sub_name in unit_status.subordinates
                    ],
                )
                for unit_name, unit_status in app_status.units.items()
            }

            series = _convert_base_to_series(app_status.base) if app_status.base else ""

            result[app_name] = Application(
                name=app_name,
                can_upgrade_to=app_status.can_upgrade_to,
                charm=app_status.charm,
                channel=app_status.charm_channel,
                config=config,
                machines=app_machines,
                model=self,
                origin=app_status.charm_origin,
                series=series,
                subordinate_to=app_status.subordinate_to,
                units=units,
                workload_version=app_status.version,
                actions=actions,
            )

        return result

    @retry(no_retry_exceptions=(ApplicationNotFound,))
    async def get_application_config(self, name: str) -> dict:
        """Return application configuration.

        :param name: Name of application
        :type name: str
        :returns: Dictionary of configuration
        :rtype: dict
        :raises: ApplicationNotFound
        """
        try:
            return json.loads(self._juju.cli("config", name, "--format", "json")).get(
                "settings", {}
            )
        except jubilant.CLIError as e:
            raise ApplicationNotFound(
                f"Application {name} was not found in model {self.name}."
            ) from e

    async def get_charm_name(self, application_name: str) -> str:
        """Get the charm name from the application.

        :param application_name: Name of application
        :type application_name: str
        :raises ApplicationError: if charm_name is None or app not found
        :return: Charm name
        :rtype: str
        """
        status = self._juju.status()
        app = status.apps.get(application_name)
        if app is None or not app.charm_name:
            raise ApplicationError(f"Cannot obtain charm_name for {application_name}")
        return app.charm_name

    @retry
    async def get_status(self) -> jubilant.Status:
        """Return the full juju status output.

        :returns: Full juju status output
        :rtype: jubilant.Status
        """
        return self._juju.status()

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
    # `juju.run(...)` and the rest of the function is covered by retry.
    async def run_action(
        self,
        unit_name: str,
        action_name: str,
        action_params: Optional[dict] = None,
        raise_on_failure: bool = False,
    ) -> jubilant.Task:
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
        :raises ActionFailed: When the action status is in error (it's not 'completed').
        :return: Task result
        :rtype: jubilant.Task
        """
        action_params = action_params or {}
        try:
            task = self._juju.run(unit_name, action_name, params=action_params or None)
        except jubilant.TaskError as e:
            if raise_on_failure:
                raise ActionFailed(e.task) from e
            return e.task
        return task

    # NOTE (rgildein): There is no need to add retry here, because we don't want to repeat
    # `juju.exec(...)` and the rest of the function is static.
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
        :returns: dict {'return-code': 0, 'stderr': '', 'stdout': ''}
        :rtype: dict[str, str]
        :raises UnitNotFound: When a valid unit cannot be found.
        :raises CommandRunFailed: When a command fails to run.
        """
        logger.debug("Running '%s' on '%s'", command, unit_name)

        try:
            task = self._juju.exec(command, unit=unit_name, wait=timeout)
        except jubilant.TaskError as e:
            result = {
                "return-code": e.task.return_code,
                "stdout": e.task.stdout,
                "stderr": e.task.stderr,
            }
            raise CommandRunFailed(cmd=command, result=result) from e

        results = {
            "return-code": task.return_code,
            "stdout": task.stdout,
            "stderr": task.stderr,
        }
        logger.debug("results: %s", results)
        return results

    @retry(no_retry_exceptions=(ApplicationNotFound,))
    async def set_application_config(self, name: str, configuration: dict[str, str]) -> None:
        """Set application configuration.

        :param name: Name of application
        :type name: str
        :param configuration: Dictionary of configuration setting(s)
        :type configuration: dict[str, Any]
        """
        self._juju.config(name, configuration)

    @retry(no_retry_exceptions=(UnitNotFound,))
    async def scp_from_unit(  # pylint: disable=too-many-arguments,too-many-positional-arguments
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
        scp_options = shlex.split(scp_opts) if scp_opts else []
        remote_path = (
            f"{user}@{unit_name}:{source}" if user != "ubuntu" else f"{unit_name}:{source}"
        )
        self._juju.scp(remote_path, destination, scp_options=scp_options)

    @retry(
        no_retry_exceptions=(
            ApplicationNotFound,
            NotImplementedError,
            ValueError,
            jubilant.CLIError,
        )
    )
    async def upgrade_charm(  # pylint: disable=too-many-arguments,too-many-positional-arguments
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
        if switch is not None:
            args = ["refresh", application_name, "--switch", switch]
            if channel is not None:
                args.extend(["--channel", channel])
            if force_series or force_units:
                args.extend(["--force", "--force-base", "--force-units"])
            self._juju.cli(*args)
        else:
            self._juju.refresh(
                application_name,
                channel=channel,
                force=force_series or force_units,
                path=path,
                revision=revision,
            )

    async def resolve_all(self) -> None:
        """Resolve all the units in the model if they are in error status."""
        self._juju.cli("resolve", "--all")

    async def get_application_names(self, charm_name: str) -> list[str]:
        """Get application name by charm name.

        :param charm_name: charm name of application
        :type charm_name: str
        :return: List of application names with that charm
        :rtype: list[str]
        :raises ApplicationNotFound: When charm is not found in the model.
        """
        status = self._juju.status()
        app_names = [
            app_name
            for app_name, app_status in status.apps.items()
            if app_status.charm_name == charm_name
        ]
        if not app_names:
            raise ApplicationNotFound(f"Cannot find '{charm_name}' charm in model '{self.name}'.")
        return app_names

    async def get_application_status(self, app_name: str) -> jubilant.statustypes.AppStatus:
        """Get AppStatus by application name.

        :param app_name: name of application
        :type app_name: str
        :return: AppStatus object
        :rtype: jubilant.statustypes.AppStatus
        :raises ApplicationNotFound: When application is not found in the model.
        """
        status = self._juju.status()
        app = status.apps.get(app_name)
        if app is None:
            raise ApplicationNotFound(f"Cannot find '{app_name}' in model '{self.name}'.")
        return app


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
