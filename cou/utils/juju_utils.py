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
import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

from juju.action import Action
from juju.application import Application
from juju.client._definitions import FullStatus
from juju.client.connector import NoConnectionException
from juju.errors import JujuAgentError, JujuAppError, JujuMachineError, JujuUnitError
from juju.model import Model
from juju.unit import Unit
from macaroonbakery.httpbakery import BakeryException
from six import wraps

from cou.exceptions import (
    ActionFailed,
    ApplicationNotFound,
    TimeoutException,
    UnitNotFound,
)

JUJU_MAX_FRAME_SIZE: int = 2**30
DEFAULT_TIMEOUT: int = 60
DEFAULT_MAX_WAIT: int = 5
DEFAULT_WAIT: float = 1.1
DEFAULT_MODEL_RETRIES: int = 30
DEFAULT_MODEL_RETRY_BACKOFF = 2

CURRENT_MODEL: Optional[Model] = None

logger = logging.getLogger(__name__)


async def extract_charm_name(application_name: str, model_name: Optional[str] = None) -> str:
    """Extract the charm name from the application.

    :param application_name: Name of application
    :type application_name: str
    :param model_name: Name of model to query, defaults to None
    :type model_name: Optional[str], optional
    :return: Charm name
    :rtype: str
    """
    model = await _get_model(model_name)
    app = model.applications.get(application_name)
    if app is None:
        raise ApplicationNotFound(
            f"Application {application_name} was not found in model {model.name}."
        )

    return app.charm_name


async def get_current_model_name() -> str:
    """Get the current model.

    First check the environment for JUJU_MODEL or MODEL_NAME. If those are not set, get the
    current active model.

    :returns: Name of current model
    :rtype: str
    """
    model_name = os.environ.get("JUJU_MODEL") or os.environ.get("MODEL_NAME")
    if model_name is None:
        model_name = await _get_current_model_name_from_juju()

    return model_name


# pylint: disable=global-statement
async def _get_model(model_name: Optional[str] = None) -> Model:
    """Get (or create) the current model for :param:`model_name`.

    If None is passed, or there is no model_name param, then the current model
    is fetched.

    :param model_name: the juju.model.Model object to fetch
    :type model_name: Optional[str]
    :returns: juju.model.Model
    :rtype: Model
    """
    global CURRENT_MODEL

    model = CURRENT_MODEL
    if model is not None and _is_model_disconnected(model):
        await _disconnect(model)
        model = None

    if CURRENT_MODEL is None:
        model = Model(max_frame_size=JUJU_MAX_FRAME_SIZE)
        await model.connect(model_name)
        CURRENT_MODEL = model

    return model


# pylint: disable=broad-exception-caught
async def _disconnect(model: Optional[Model]) -> None:
    """Disconnect the model.

    :param model: the juju.model.Model object.
    :type model: Model
    """
    if model is not None:
        await model.disconnect()


def _is_model_disconnected(model: Model) -> bool:
    """Return True if the model is disconnected.

    :param model: the model to check
    :type model: :class:'juju.Model'
    :returns: True if disconnected
    :rtype: bool
    """
    return not (model.is_connected() and model.connection().is_open)


async def _get_current_model_name_from_juju() -> str:
    """Return the current active model name.

    Connect to the current active model and return its name.

    :returns: String current model name
    :rtype: str
    """
    # NOTE(tinwood): Due to https://github.com/juju/python-libjuju/issues/458
    # set the max frame size to something big to stop
    # "RPC: Connection closed, reconnecting" messages and then failures.
    model = Model(max_frame_size=JUJU_MAX_FRAME_SIZE)
    await model.connect()
    model_name = model.name
    await model.disconnect()
    return model_name


async def get_status(model_name: Optional[str] = None) -> FullStatus:
    """Return the full juju status output.

    :param model_name: Name of model to query.
    :type model_name: Optional[str]
    :returns: Full juju status output
    :rtype: FullStatus
    """
    model = await _get_model(model_name)
    return await model.get_status()


def _normalise_action_results(results: Dict[str, str]) -> Dict[str, str]:
    """Put action results in a consistent format.

    :param results: Results dictionary to process.
    :type results: Dict[str, str]
    :returns: {
        'Code': '',
        'Stderr': '',
        'Stdout': '',
        'stderr': '',
        'stdout': ''}
    :rtype: Dict[str, str]
    """
    if results:
        # In Juju 2.7 some keys are dropped from the results if their
        # value was empty. This breaks some functions downstream, so
        # ensure the keys are always present.
        for key in ["Stderr", "Stdout", "stderr", "stdout"]:
            results[key] = results.get(key, "")
        # Juju has started using a lowercase "stdout" key in new action
        # commands in recent versions. Ensure the old capatalised keys and
        # the new lowercase keys are present and point to the same value to
        # avoid breaking functions downstream.
        for key in ["stderr", "stdout"]:
            old_key = key.capitalize()
            if results.get(key) and not results.get(old_key):
                results[old_key] = results[key]
            elif results.get(old_key) and not results.get(key):
                results[key] = results[old_key]
        return results
    return {}


async def _check_action_error(action_obj: Action, model: Model, raise_on_failure: bool) -> None:
    """Check if the run action resulted in error.

    :param action_obj: Action object.
    :type action_obj: Action
    :param model: the juju.model.Model object.
    :type model: Model
    :param raise_on_failure: Boolean flag to raise on failure.
    :type raise_on_failure: bool
    :raises ActionFailed: Exception raised when action fails.
    """
    await action_obj.wait()
    if raise_on_failure and action_obj.status != "completed":
        try:
            output = await model.get_action_output(action_obj.id)
        except KeyError:
            output = None

        raise ActionFailed(action_obj, output=output)


async def run_on_unit(
    unit_name: str, command: str, model_name: Optional[str] = None, timeout: Optional[int] = None
) -> Dict[str, str]:
    """Juju run on unit.

    :param unit_name: Name of unit to match
    :type unit: str
    :param command: Command to execute
    :type command: str
    :param model_name: Name of model unit is in
    :type model_name: Optional[str]
    :param timeout: How long in seconds to wait for command to complete
    :type timeout: Optional[int]
    :returns: action.data['results'] {'Code': '', 'Stderr': '', 'Stdout': ''}
    :rtype: Dict[str, str]
    """
    model = await _get_model(model_name)
    unit = await get_unit_from_name(unit_name, model)
    action = await unit.run(command, timeout=timeout)
    results = action.data.get("results")
    return _normalise_action_results(results)


async def get_unit_from_name(
    unit_name: str, model: Optional[Model] = None, model_name: Optional[str] = None
) -> Unit:
    """Return the units that corresponds to the name in the given model.

    :param unit_name: Name of unit to match
    :type unit_name: str
    :param model: Model to perform lookup in
    :type model: Optional[Model]
    :param model_name: Name of the model to perform lookup in
    :type model_name: Optional[str]
    :returns: Unit matching given name
    :rtype: juju.unit.Unit or None
    :raises: UnitNotFound
    """
    app = unit_name.split("/")[0]
    unit = None
    if model is None:
        model = await _get_model(model_name)
    try:
        units = model.applications[app].units
    except KeyError as exc:
        raise UnitNotFound(f"Application {app} not found in model {model.name}.") from exc

    for single_unit in units:
        if single_unit.entity_id == unit_name:
            unit = single_unit
            break
    else:
        raise UnitNotFound(f"Unit {unit_name} not found in model.")

    return unit


async def get_application_config(application_name: str, model_name: Optional[str] = None) -> Dict:
    """Return application configuration.

    :param model_name: Name of model to query.
    :type model_name: Optional[str]
    :param application_name: Name of application
    :type application_name: str
    :returns: Dictionary of configuration
    :rtype: dict
    """
    model = await _get_model(model_name)
    return await model.applications[application_name].get_config()


async def run_action(
    unit_name: str,
    action_name: str,
    model_name: Optional[str] = None,
    action_params: Optional[Dict] = None,
    raise_on_failure: bool = False,
) -> Action:
    """Run action on given unit.

    :param unit_name: Name of unit to run action on
    :type unit_name: str
    :param action_name: Name of action to run
    :type action_name: str
    :param model_name: Name of model to query.
    :type model_name: Optional[str]
    :param action_params: Dictionary of config options for action
    :type action_params: Optional[Dict]
    :param raise_on_failure: Raise ActionFailed exception on failure, defaults to False
    :type raise_on_failure: bool
    :returns: Action object
    :rtype: juju.action.Action
    :raises: ActionFailed
    """
    if action_params is None:
        action_params = {}

    model = await _get_model(model_name)
    unit = await get_unit_from_name(unit_name, model)
    action_obj = await unit.run_action(action_name, **action_params)
    await _check_action_error(action_obj, model, raise_on_failure)
    return action_obj


# pylint: disable=too-many-arguments
async def scp_from_unit(
    unit_name: str,
    source: str,
    destination: str,
    model_name: Optional[str] = None,
    user: str = "ubuntu",
    proxy: bool = False,
    scp_opts: str = "",
) -> None:
    """Transfer files from unit_name in model_name.

    :param model_name: Name of model unit is in
    :type model_name:  Optional[str]
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
    """
    model = await _get_model(model_name)
    unit = await get_unit_from_name(unit_name, model)
    await unit.scp_from(source, destination, user=user, proxy=proxy, scp_opts=scp_opts)


# pylint: disable=too-many-arguments
async def upgrade_charm(
    application_name: str,
    channel: Optional[str] = None,
    force_series: bool = False,
    force_units: bool = False,
    path: Optional[str] = None,
    resources: Optional[Dict] = None,
    revision: Optional[int] = None,
    switch: Optional[str] = None,
    model_name: Optional[str] = None,
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
    :param path: Uprade to a charm located at path
    :type path: str
    :param resources: Dictionary of resource name/filepath pairs
    :type resources: dict
    :param revision: Explicit upgrade revision
    :type revision: int
    :param switch: Crossgrade charm url
    :type switch: str
    :param model_name: Name of model to operate on
    :type model_name: str
    """
    model = await _get_model(model_name)
    app = model.applications[application_name]
    await app.upgrade_charm(
        channel=channel,
        force_series=force_series,
        force_units=force_units,
        path=path,
        resources=resources,
        revision=revision,
        switch=switch,
    )


async def set_application_config(
    application_name: str, configuration: Dict[str, str], model_name: Optional[str] = None
) -> None:
    """Set application configuration.

    :param application_name: Name of application
    :type application_name: str
    :param configuration: Dictionary of configuration setting(s)
    :type configuration: Dict[str,str]
    :param model_name: Name of model to query.
    :type model_name: Optional[str]
    """
    model = await _get_model(model_name)
    return await model.applications[application_name].set_config(configuration)


# pylint: disable=too-few-public-methods
class JujuWaiter:
    """Enhanced version of wait_for_idle.

    Usage:
        JujuWaiter(model).wait(120)
    """

    # Total wait timeout. After this timeout TimeoutException is raised
    DEFAULT_TIMEOUT: int = 3600

    # Model should be idle for MODEL_IDLE_PERIOD consecutive seconds to be counted as idle.
    MODEL_IDLE_PERIOD: int = 30

    # At each iteration juju will wait JUJU_IDLE_TIMEOUT seconds
    JUJU_IDLE_TIMEOUT: int = 40

    def __init__(self, model: Model):
        """Initialize.

        :param model: model to wait
        :type model: Model
        """
        self.model = model
        self.model_name = self.model.name
        self.timeout = timedelta(seconds=JujuWaiter.DEFAULT_TIMEOUT)
        self.start_time = datetime.now()
        self.log = logging.getLogger(self.__class__.__name__)

    async def wait(self, timeout_seconds: int = DEFAULT_TIMEOUT) -> None:
        """Wait for model to stabilize.

        :param timeout_seconds: wait model till timeout_seconds. If passed raise TimeoutException
        :type timeout_seconds: int
        :return: None
        :raises TimeoutException: if timeout_seconds passed.
        :raises JujuMachineError: if it has a machine exception
        :raises JujuAgentError: if it has an agent exception
        :raises JujuUnitError: if it has unit exception
        :raises JujuAppError: if it has application exception
        """
        self.start_time = datetime.now()
        if timeout_seconds:
            self.timeout = timedelta(seconds=timeout_seconds)
        self.log.debug("Waiting to stabilize in %s seconds", self.timeout)

        while True:
            await self._ensure_model_connected()
            try:
                await self.model.wait_for_idle(
                    idle_period=JujuWaiter.MODEL_IDLE_PERIOD,
                    timeout=JujuWaiter.JUJU_IDLE_TIMEOUT,
                )
                self.log.debug(
                    "Model %s is idle for %s seconds.",
                    self.model.info.name,
                    JujuWaiter.MODEL_IDLE_PERIOD,
                )
                return
            except (
                JujuMachineError,
                JujuAgentError,
                JujuUnitError,
                JujuAppError,
            ):
                raise
            except Exception:
                # We do not care exceptions other than Juju(Machine|Agent|Unit|App)Error because
                # when juju connection is dropped you can have wide range of exceptions depending
                # on the case
                self.log.debug("Unknown error while waiting to stabilize.", exc_info=True)

            self._check_time()

    async def _ensure_model_connected(self) -> None:
        """Ensure that the model is connected.

        :raises TimeoutException: if timeout occurs
        """
        while _is_model_disconnected(self.model):
            await _disconnect(self.model)
            try:
                self._check_time()
                await self.model.connect_model(self.model_name)
            except TimeoutException:
                raise
            except Exception:
                self.log.debug(
                    "Model has unexpected exception while connecting, retrying", exc_info=True
                )

    def _check_time(self) -> None:
        """Check time.

        :raises TimeoutException: if timeout occurs
        """
        if datetime.now() - self.start_time > self.timeout:
            self.log.debug("Model %s is not idle after %d seconds.", self.model_name, self.timeout)
            raise TimeoutException(
                f"Model {self.model_name} has not stabilized after {self.timeout} seconds."
            )


def retry(
    function: Optional[Callable] = None,
    timeout: int = DEFAULT_TIMEOUT,
    no_retry_exception: Optional[tuple] = None,
) -> Callable:
    """Retry function for usage in COUModel.

    :param function: function to wrapped
    :type function: Optional[Callable]
    :param timeout: timeout in seconds
    :type timeout: int
    :param no_retry_exception: tuple of exception on which function will not be retried
    :type no_retry_exception: Optional[tuple]
    :return: wrapped function
    :rtype: Callable
    """
    ignored_exceptions = (TimeoutException, *(no_retry_exception or ()))

    def _wrapper(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt: int = 0
            start_time = datetime.now()
            while (datetime.now() - start_time).seconds <= timeout:
                try:
                    return await func(*args, **kwargs)
                except ignored_exceptions:
                    # raising exception if no_retry_exception happen or TimeoutException
                    raise
                except Exception:
                    logger.debug("function %s failed [%d]", func.__name__, attempt, exc_info=True)
                    await asyncio.sleep(DEFAULT_WAIT**attempt)
                    attempt += 1

            # if while loop ends, it means we reached the timeout
            raise TimeoutException(f"function {func.__name__} rich timeout {timeout}s")

        return wrapper

    if function is not None:
        return _wrapper(function)

    return _wrapper


class COUModel:
    """COU model object.

    This version of the model provides better waiting for the model to turn idle, auto-reconnection
    and some other required features for COU.
    """

    def __init__(self, name: str):
        """COU Model initialization with model_name compared to original juju.model.Model."""
        self._model = Model(max_frame_size=JUJU_MAX_FRAME_SIZE)
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
    def name(self) -> str:
        """Return model name."""
        return self._name

    @retry(no_retry_exception=(BakeryException,))
    async def _connect(self) -> None:
        """Make sure that model is connected."""
        await self._model.disconnect()
        await self._model.connect(
            model_name=self.name,
            retries=DEFAULT_MODEL_RETRIES,
            retry_backoff=DEFAULT_MODEL_RETRY_BACKOFF,
        )

    async def _get_application(self, name: str) -> Application:
        """Get juju.application.Application from model.

        :return: Application
        :rtype: Application
        :raises: ApplicationNotFound
        """
        model = await self._get_model()
        app = model.applications.get(name)
        if app is None:
            raise ApplicationNotFound(f"Application {name} was not found in model {model.name}.")

        return app

    async def _get_model(self) -> Model:
        """Get juju.model.Model and make sure that's it's connected."""
        if not self.connected:
            await self._connect()

        return self._model

    async def _get_unit(self, name: str) -> Unit:
        """Get juju.unit.unit from model.

        :return: Unit
        :rtype: Unit
        :raises: UnitNotFound
        """
        model = await self._get_model()
        unit = model.units.get(name)
        if unit is None:
            raise UnitNotFound(f"Unit {name} was not found in model {model.name}.")

        return unit

    async def get_application_config(self, name: str) -> Dict:
        """Return application configuration.

        :param name: Name of application
        :type name: str
        :returns: Dictionary of configuration
        :rtype: dict
        :raises: ApplicationNotFound
        """
        app = await self._get_application(name)
        return await app.get_config()

    async def get_charm_name(self, application_name: str) -> Optional[str]:
        """Get the charm name from the application.

        :param application_name: Name of application
        :type application_name: str
        :return: Charm name
        :rtype: Optional[str]
        :raises: ApplicationNotFound
        """
        app = await self._get_application(application_name)
        return app.charm_name

    async def get_status(self) -> FullStatus:
        """Return the full juju status output.

        :returns: Full juju status output
        :rtype: FullStatus
        """
        model = await self._get_model()
        return await model.get_status()

    async def run_action(
        self,
        unit_name: str,
        action_name: str,
        action_params: Optional[Dict] = None,
        raise_on_failure: bool = False,
    ) -> Action:
        """Run action on given unit.

        :param unit_name: Name of unit to run action on
        :type unit_name: str
        :param action_name: Name of action to run
        :type action_name: str
        :param action_params: Dictionary of config options for action
        :type action_params: Optional[Dict]
        :param raise_on_failure: Raise ActionFailed exception on failure, defaults to False
        :type raise_on_failure: bool
        :returns: Action object
        :rtype: juju.action.Action
        :raises: UnitNotFound
        :raises: ActionFailed
        """
        action_params = action_params or {}
        unit = await self._get_unit(unit_name)
        action = await unit.run_action(action_name, **action_params)
        await action.wait()
        if raise_on_failure and action.status != "completed":
            output = await action.model.get_action_output(action.id)
            raise ActionFailed(action, output=output)

        return action

    async def run_on_unit(
        self, unit_name: str, command: str, timeout: Optional[int] = None
    ) -> Dict[str, str]:
        """Juju run on unit.

        :param unit_name: Name of unit to match
        :type unit: str
        :param command: Command to execute
        :type command: str
        :param model_name: Name of model unit is in
        :type model_name: Optional[str]
        :param timeout: How long in seconds to wait for command to complete
        :type timeout: Optional[int]
        :returns: action.data['results'] {'Code': '', 'Stderr': '', 'Stdout': ''}
        :rtype: Dict[str, str]
        :raises: UnitNotFound
        :raises: ActionFailed
        """
        unit = await self._get_unit(unit_name)
        action = await unit.run(command, timeout=timeout)
        results = action.data.get("results")
        return _normalise_action_results(results)

    async def set_application_config(self, name: str, configuration: Dict[str, str]) -> None:
        """Set application configuration.

        :param name: Name of application
        :type name: str
        :param configuration: Dictionary of configuration setting(s)
        :type configuration: Dict[str,str]
        :param model_name: Name of model to query.
        :type model_name: Optional[str]
        """
        app = await self._get_application(name)
        await app.set_config(configuration)

    async def scp_from_unit(
        self,
        unit_name: str,
        source: str,
        destination: str,
        user: str = "ubuntu",
        proxy: bool = False,
        scp_opts: str = "",
    ) -> None:
        """Transfer files from unit_name in model_name.

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
        unit = await self._get_unit(unit_name)
        await unit.scp_from(source, destination, user=user, proxy=proxy, scp_opts=scp_opts)

    async def upgrade_charm(
        self,
        application_name: str,
        channel: Optional[str] = None,
        force_series: bool = False,
        force_units: bool = False,
        path: Optional[str] = None,
        resources: Optional[Dict] = None,
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
        :param path: Uprade to a charm located at path
        :type path: str
        :param resources: Dictionary of resource name/filepath pairs
        :type resources: dict
        :param revision: Explicit upgrade revision
        :type revision: int
        :param switch: Crossgrade charm url
        :type switch: str
        :param model_name: Name of model to operate on
        :type model_name: str
        :raises: ApplicationNotFound
        """
        app = await self._get_application(application_name)
        await app.upgrade_charm(
            channel=channel,
            force_series=force_series,
            force_units=force_units,
            path=path,
            resources=resources,
            revision=revision,
            switch=switch,
        )

    async def wait_for_idle(self, timeout: int, apps: Optional[list[str]] = None) -> None:
        """Wait for model to rich idle state."""
        model = await self._get_model()
        wait = retry(model.wait_for_idle, timeout=timeout)
        await wait(
            apps=apps,
            idle_period=JujuWaiter.MODEL_IDLE_PERIOD,
            timeout=JujuWaiter.JUJU_IDLE_TIMEOUT,
        )
