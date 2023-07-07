# mypy: disable-error-code="no-untyped-def"
# Copyright 2018 Canonical Ltd.
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

import logging
import os
import re
from typing import Optional

from juju.client._definitions import FullStatus
from juju.model import Model

from cou.exceptions import ActionFailed, UnitNotFound

JUJU_MAX_FRAME_SIZE = 2**30

CURRENT_MODEL_NAME: Optional[str] = None
CURRENT_MODEL: Optional[Model] = None


# remove when fixed: https://github.com/juju/python-libjuju/issues/888
def extract_charm_name_from_url(charm_url):
    """Extract the charm name from the charm url.

    E.g. Extract 'heat' from local:bionic/heat-12

    :param charm_url: Name of model to query.
    :type charm_url: str
    :returns: Charm name
    :rtype: str
    """
    charm_name = re.sub(r"-\d+$", "", charm_url.split("/")[-1])
    return charm_name.split(":")[-1]


async def async_get_current_model_name():
    """Retrieve current model.

    First check the environment for JUJU_MODEL. If this is not set, get the
    current active model.

    :returns: In focus model name
    :rtype: str
    """
    global CURRENT_MODEL_NAME
    if CURRENT_MODEL_NAME:
        return CURRENT_MODEL_NAME
    try:
        # Check the environment
        CURRENT_MODEL_NAME = os.environ["JUJU_MODEL"]
    except KeyError:
        try:
            CURRENT_MODEL_NAME = os.environ["MODEL_NAME"]
        except KeyError:
            # If unset connect get the current active model
            CURRENT_MODEL_NAME = await _async_get_current_model_name_from_juju()
    return CURRENT_MODEL_NAME


async def _async_get_model(model_name=None) -> Model:
    """Get (or create) the current model for :param:`model_name`.

    If None is passed, or there is no model_name param, then the current model
    is fetched.

    :param model_name: the juju.model.Model object to fetch
    :type model_name: Optional[str]
    :returns: juju.model.Model
    """
    global CURRENT_MODEL
    global CURRENT_MODEL_NAME

    if model_name is not None and model_name != CURRENT_MODEL_NAME:
        await _disconnect(CURRENT_MODEL_NAME)
        CURRENT_MODEL_NAME = model_name

    model = CURRENT_MODEL
    if model is not None and _is_model_disconnected(model):
        await _disconnect(model)
        model = None
    if CURRENT_MODEL is None:
        model = Model(max_frame_size=JUJU_MAX_FRAME_SIZE)
        await model.connect(model_name)
        CURRENT_MODEL = model
    return model


async def _disconnect(model: Model):
    if model is not None:
        try:
            await model.disconnect()
        except Exception:
            pass


def _is_model_disconnected(model):
    """Return True if the model is disconnected.

    :param model: the model to check
    :type model: :class:'juju.Model'
    :returns: True if disconnected
    :rtype: bool
    """
    return not (model.is_connected() and model.connection().is_open)


async def _async_get_current_model_name_from_juju():
    """Return the current active model name.

    Connect to the current active model and return its name.

    :returns: String curenet model name
    :rtype: str
    """
    # NOTE(tinwood): Due to https://github.com/juju/python-libjuju/issues/458
    # set the max frame size to something big to stop
    # "RPC: Connection closed, reconnecting" messages and then failures.
    model = Model(max_frame_size=JUJU_MAX_FRAME_SIZE)
    await model.connect()
    model_name = model.info.name
    await model.disconnect()
    return model_name


async def async_get_status(model_name=None) -> FullStatus:
    """Return the full juju status output.

    :param model_name: Name of model to query.
    :type model_name: str
    :returns: Full juju status output
    :rtype: dict
    """
    model = await _async_get_model(model_name)
    return await model.get_status()


def _normalise_action_results(results):
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
    else:
        return {}


async def _check_action_error(action_obj, model, raise_on_failure):
    await action_obj.wait()
    if raise_on_failure and action_obj.status != "completed":
        try:
            output = await model.get_action_output(action_obj.id)
        except KeyError:
            output = None
        raise ActionFailed(action_obj, output=output)


async def async_run_on_unit(unit_name, command, model_name=None, timeout=None):
    """Juju run on unit.

    :param model_name: Name of model unit is in
    :type model_name: str
    :param unit_name: Name of unit to match
    :type unit: str
    :param command: Command to execute
    :type command: str
    :param timeout: How long in seconds to wait for command to complete
    :type timeout: int
    :returns: action.data['results'] {'Code': '', 'Stderr': '', 'Stdout': ''}
    :rtype: dict
    """
    model = await _async_get_model(model_name)
    unit = await async_get_unit_from_name(unit_name, model)
    action = await unit.run(command, timeout=timeout)
    results = action.data.get("results")
    return _normalise_action_results(results)


async def async_get_unit_from_name(unit_name, model=None, model_name=None):
    """Return the units that corresponds to the name in the given model.

    :param unit_name: Name of unit to match
    :type unit_name: str
    :param model: Model to perform lookup in
    :type model: model.Model()
    :param model_name: Name of the model to perform lookup in
    :type model_name: string
    :returns: Unit matching given name
    :rtype: juju.unit.Unit or None
    :raises: UnitNotFound
    """
    app = unit_name.split("/")[0]
    unit = None
    try:
        if model is None:
            model = await _async_get_model(model_name)
        units = model.applications[app].units
    except KeyError:
        msg = "Application: {} does not exist in current model".format(app)
        logging.error(msg)
        raise UnitNotFound(unit_name)
    for u in units:
        if u.entity_id == unit_name:
            unit = u
            break
    else:
        raise UnitNotFound(unit_name)
    return unit


async def async_get_application_config(application_name, model_name=None):
    """Return application configuration.

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :returns: Dictionary of configuration
    :rtype: dict
    """
    model = await _async_get_model(model_name)
    return await model.applications[application_name].get_config()


async def async_run_action(
    unit_name, action_name, model_name=None, action_params=None, raise_on_failure=False
):
    """Run action on given unit.

    :param unit_name: Name of unit to run action on
    :type unit_name: str
    :param action_name: Name of action to run
    :type action_name: str
    :param model_name: Name of model to query.
    :type model_name: str
    :param action_params: Dictionary of config options for action
    :type action_params: dict
    :param raise_on_failure: Raise ActionFailed exception on failure
    :type raise_on_failure: bool
    :returns: Action object
    :rtype: juju.action.Action
    :raises: ActionFailed
    """
    if action_params is None:
        action_params = {}

    model = await _async_get_model(model_name)
    unit = await async_get_unit_from_name(unit_name, model)
    action_obj = await unit.run_action(action_name, **action_params)
    await _check_action_error(action_obj, model, raise_on_failure)
    return action_obj


async def async_scp_from_unit(
    unit_name, source, destination, model_name=None, user="ubuntu", proxy=False, scp_opts=""
):
    """Transfer files from unit_name in model_name.

    :param model_name: Name of model unit is in
    :type model_name: str
    :param unit_name: Name of unit to scp from
    :type unit_name: str
    :param source: Remote path of file(s) to transfer
    :type source: str
    :param destination: Local destination of transferred files
    :type source: str
    :param user: Remote username
    :type source: str
    :param proxy: Proxy through the Juju API server
    :type proxy: bool
    :param scp_opts: Additional options to the scp command
    :type scp_opts: str
    """
    model = await _async_get_model(model_name)
    unit = await async_get_unit_from_name(unit_name, model)
    await unit.scp_from(source, destination, user=user, proxy=proxy, scp_opts=scp_opts)


async def async_upgrade_charm(
    application_name,
    channel=None,
    force_series=False,
    force_units=False,
    path=None,
    resources=None,
    revision=None,
    switch=None,
    model_name=None,
):
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
    model = await _async_get_model(model_name)
    app = model.applications[application_name]
    await app.upgrade_charm(
        channel=channel,
        force_series=force_series,
        force_units=force_units,
        local_charm_path=path,
        resources=resources,
        revision=revision,
        switch=switch,
    )


async def async_set_application_config(application_name, configuration, model_name=None):
    """Set application configuration.

    NOTE: At the time of this writing python-libjuju requires all values passed
    to `set_config` to be `str`.
    https://github.com/juju/python-libjuju/issues/388

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :param configuration: Dictionary of configuration setting(s)
    :type configuration: Dict[str,str]
    """
    model = await get_model(model_name)
    return await model.applications[application_name].set_config(configuration)


def units_with_wl_status_state(model, state):
    """Return a list of unit which have a matching workload status.

    :returns: Units in error state
    :rtype: [juju.Unit, ...]
    """
    matching_units = []
    for unit in model.units.values():
        wl_status = unit.workload_status
        if wl_status == state:
            matching_units.append(unit)
    return matching_units


async def block_until_auto_reconnect_model(
    *conditions, model=None, aconditions=None, timeout=None, wait_period=0.5
):
    """Async block on the model until conditions met.

    This function doesn't use model.block_until() which unfortunately raises
    websockets.exceptions.ConnectionClosed if the connections gets closed,
    which seems to happen quite frequently.  This funtion blocks until the
    conditions are met or a timeout occurs, and reconnects the model if it
    becomes disconnected.

    Note that conditions are just passed as an unamed list in the function call
    to make it work more like the more simple 'block_until' function.

    Note: conditions must capture libjuju objects in closures as the model may
    change if it is disconnected. The closures should refetch the juju objects
    from the model as needed.

    :param model: the model to use
    :type model: :class:'juju.Model()'
    :param conditions: a list of callables that need to evaluate to True.
    :type conditions: [List[Callable[[:class:'juju.Model()'], bool]]]
    :param aconditions: an optional list of async callables that need to
        evaluate to True.
    :type aconditions:
        Optional[List[AsyncCallable[[:class:'juju.Model()'], bool]]]
    :param timeout: the timeout to wait for the block on.
    :type timeout: float
    :param wait_period: The time to sleep between checking the conditions.
    :type wait_period: float
    :raises: TimeoutError if the conditions never match (assuming timeout is
        not None).
    """
    assert model is not None, "model can't be None in " "block_until_auto_reconnect_model()"
    aconditions = aconditions or []

    def _done():
        return all(c() for c in conditions)

    async def _adone():
        evaluated = []
        # note Python 3.5 doesn't support async comprehensions; do it the old
        # fashioned way.
        for c in aconditions:
            evaluated.append(await c())
            if is_model_disconnected(model):
                return False
        return all(evaluated)

    async def _block():
        while True:
            # reconnect if disconnected, as the conditions still need to be
            # checked.
            await ensure_model_connected(model)
            result = _done()
            aresult = await _adone()
            if all((not is_model_disconnected(model), result, aresult)):
                return
            else:
                await asyncio.sleep(wait_period)

    # finally wait for all the conditions to be true
    await asyncio.wait_for(_block(), timeout)


async def ensure_model_connected(model):
    """Ensure that the model is connected.

    If model is disconnected then reconnect it.

    :param model: the model to check
    :type model: :class:'juju.Model'
    """
    if is_model_disconnected(model):
        model_name = model.info.name
        logging.warning(
            "model: %s has disconnected, forcing full disconnection " "and then reconnecting ...",
            model_name,
        )
        try:
            await model.disconnect()
        except Exception:
            # We don't care if disconnect fails; we're much more
            # interested in re-connecting, and this is just to clean up
            # anything that might be left over (i.e.
            # model.is_connected() might be true, but
            # model.connection().is_open may be false
            pass
        logging.warning("Attempting to reconnect model %s", model_name)
        await model.connect_model(model_name)


async def async_block_until_all_units_idle(
    model_name=None, timeout=2700, ignore_hard_errors=False
):
    """Block until all units in the given model are idle.

    An example accessing this function via its sync wrapper::

        block_until_all_units_idle('modelname')

    :param model_name: Name of model to query.
    :type model_name: str
    :param timeout: Time to wait for status to be achieved
    :type timeout: float
    :param ignore_hard_deploy_error: Whether to ignore charms going into an
                                     error state.
    :type ignore_hard_deploy_error: Boolean
    """
    model = await get_model(model_name)
    await block_until_auto_reconnect_model(
        lambda: units_with_wl_status_state(model, "error") or model.all_units_idle(),
        model=model,
        timeout=timeout,
    )
    errored_units = units_with_wl_status_state(model, "error")
    if errored_units:
        if ignore_hard_errors:
            logging.warning("Units {} in error state. ".format(errored_units))
        else:
            raise UnitError(errored_units)
