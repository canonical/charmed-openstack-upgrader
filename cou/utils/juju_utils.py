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
from datetime import datetime
from typing import Any, Callable, Optional

from juju.action import Action
from juju.application import Application
from juju.client._definitions import FullStatus
from juju.client.connector import NoConnectionException
from juju.model import Model
from juju.unit import Unit
from macaroonbakery.httpbakery import BakeryException
from six import wraps

from cou.exceptions import (
    ActionFailed,
    ApplicationError,
    ApplicationNotFound,
    TimeoutException,
    UnitNotFound,
)

JUJU_MAX_FRAME_SIZE: int = 2**30
DEFAULT_TIMEOUT: int = 60
DEFAULT_MAX_WAIT: int = 5
DEFAULT_WAIT: float = 1.1
DEFAULT_MODEL_RETRIES: int = 30
DEFAULT_MODEL_RETRY_BACKOFF: int = 2
DEFAULT_MODEL_IDLE_PERIOD: int = 30

logger = logging.getLogger(__name__)


def _normalize_action_results(results: dict[str, str]) -> dict[str, str]:
    """Unify action results format.

    :param results: Results dictionary to process.
    :type results: dict[str, str]
    :returns: {
        'Code': '',
        'Stderr': '',
        'Stdout': '',
        'stderr': '',
        'stdout': ''}
    :rtype: dict[str, str]
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


def retry(
    function: Optional[Callable] = None,
    timeout: int = DEFAULT_TIMEOUT,
    no_retry_exceptions: tuple = (),
) -> Callable:
    """Retry function for usage in COUModel.

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
                    logger.debug("function %s failed [%d]", func.__name__, attempt, exc_info=True)
                    await asyncio.sleep(DEFAULT_WAIT**attempt)
                    attempt += 1

            # if while loop ends, it means we reached the timeout
            raise TimeoutException(f"function {func.__name__} timed out after {timeout}s")

        return wrapper

    if function is not None:
        return _wrapper(function)

    return _wrapper


class COUModel:
    """COU model object.

    This version of the model provides better waiting for the model to turn idle, auto-reconnection
    and some other required features for COU.
    """

    def __init__(self, name: Optional[str]):
        """COU Model initialization with name and juju.model.Model."""
        self._model = Model(max_frame_size=JUJU_MAX_FRAME_SIZE)
        self._name = name

    @staticmethod
    async def create(name: Optional[str]) -> "COUModel":
        """Create COUModel object and connect it to model.

        :param name: Name of the model.
        :type name: Optional[str]
        :return: COUModel object.
        :rtype: COUModel
        """
        model = COUModel(name)
        await model._connect()  # pylint: disable=protected-access
        return model

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
        if self._name is None:
            self._name = self._model.name

        return self._name

    @retry(no_retry_exceptions=(BakeryException,))
    async def _connect(self) -> None:
        """Make sure that model is connected."""
        await self._model.disconnect()
        await self._model.connect(
            model_name=self._name,
            retries=DEFAULT_MODEL_RETRIES,
            retry_backoff=DEFAULT_MODEL_RETRY_BACKOFF,
        )

    async def _get_application(self, name: str) -> Application:
        """Get juju.application.Application from model.

        :param name: Name of application
        :type name: str
        :raises ApplicationNotFound: When Application is not found in the model.
        :return: Application
        :rtype: Application
        """
        model = await self._get_model()
        app = model.applications.get(name)
        if app is None:
            raise ApplicationNotFound(f"Application {name} was not found in model {model.name}.")

        return app

    async def _get_model(self) -> Model:
        """Get juju.model.Model and make sure that it is connected.

        :return: Model
        :rtype: Model
        """
        if not self.connected:
            await self._connect()

        return self._model

    async def _get_unit(self, name: str) -> Unit:
        """Get juju.unit.unit from model.

        :param name: Name of unit
        :type name: str
        :raises UnitNotFound: When unit is not found in the model.
        :return: Unit
        :rtype: Unit
        """
        model = await self._get_model()
        unit = model.units.get(name)
        if unit is None:
            raise UnitNotFound(f"Unit {name} was not found in model {model.name}.")

        return unit

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
        :type raise_on_failure: bool, optional
        :raises ActionFailed: _description_
        :return: When status is different from "completed"
        :rtype: Action
        """
        action_params = action_params or {}
        unit = await self._get_unit(unit_name)
        action = await unit.run_action(action_name, **action_params)
        result = await action.wait()
        if raise_on_failure:
            model = await self._get_model()
            status = await model.get_action_status(uuid_or_prefix=action.entity_id)
            if status != "completed":
                output = await model.get_action_output(action.entity_id)
                raise ActionFailed(action, output=output)

        return result

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
        :returns: action.data['results'] {'Code': '', 'Stderr': '', 'Stdout': ''}
        :rtype: dict[str, str]
        :raises: UnitNotFound
        :raises: ActionFailed
        """
        unit = await self._get_unit(unit_name)
        action = await unit.run(command, timeout=timeout)
        results = action.data.get("results")
        return _normalize_action_results(results)

    async def set_application_config(self, name: str, configuration: dict[str, Any]) -> None:
        """Set application configuration.

        :param name: Name of application
        :type name: str
        :param configuration: Dictionary of configuration setting(s)
        :type configuration: dict[str, Any]
        """
        app = await self._get_application(name)
        await app.set_config(configuration)

    # pylint: disable=too-many-arguments
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
        unit = await self._get_unit(unit_name)
        await unit.scp_from(source, destination, user=user, proxy=proxy, scp_opts=scp_opts)

    # pylint: disable=too-many-arguments
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

    async def wait_for_idle(self, timeout: int, apps: Optional[list[str]] = None) -> None:
        """Wait for model to reach an idle state.

        :param timeout: Timeout in seconds.
        :type timeout: int
        :param apps: Applications to wait, defaults to None
        :type apps: Optional[list[str]], optional
        """
        model = await self._get_model()
        await model.wait_for_idle(
            apps=apps, timeout=timeout, idle_period=DEFAULT_MODEL_IDLE_PERIOD
        )
