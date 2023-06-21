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

import asyncio
import collections
import logging
import os
import time
from typing import Any, Dict

from juju.model import Model

from cou.exceptions import ActionFailed, JujuError, UnitNotFound

JUJU_MAX_FRAME_SIZE = 2**30

APPS_LEFT_INTERVAL = 600

CURRENT_MODEL = None
MODEL_ALIASES: Dict[Any, Any] = {}
# A collection of model name -> libjuju models associations; use to either
# instantiate or handout a model, or start a new one.
ModelRefs: Dict[Any, Any] = {}


async def async_get_juju_model():
    """Retrieve current model.

    First check the environment for JUJU_MODEL. If this is not set, get the
    current active model.

    :returns: In focus model name
    :rtype: str
    """
    global CURRENT_MODEL
    if CURRENT_MODEL:
        return CURRENT_MODEL
    # LY: I think we should remove the KeyError handling. I don't think we
    #     should ever fall back to the model in focus because it will lead
    #     to functions being added which do not explicitly set a model and
    #     zaza will loose the ability to do concurrent runs.
    try:
        # Check the environment
        CURRENT_MODEL = os.environ["JUJU_MODEL"]
    except KeyError:
        try:
            CURRENT_MODEL = os.environ["MODEL_NAME"]
        except KeyError:
            # If unset connect get the current active model
            CURRENT_MODEL = await async_get_current_model()
    return CURRENT_MODEL


async def get_model(model_name=None):
    """Get (or create) the current model for :param:`model_name`.

    If None is passed, or there is no model_name param, then the current model
    is fetched.

    :param model_name: the juju.model.Model object to fetch
    :type model_name: Optional[str]
    :returns: juju.model.Model
    """
    if not model_name:
        model_name = await async_get_juju_model()
    return await get_model_memo(model_name)


async def get_model_memo(model_name):
    """Get the libjuju Model object for a name.

    This is memoed as the model is maintained as running in a separate
    background thread.  Thus, essentially this is a singleton for each of
    the model names.

    :param model_name: the model name to get a Model for.
    :type model_name: str
    :returns: juju.model.Model
    """
    global ModelRefs
    model = None
    if model_name in ModelRefs:
        model = ModelRefs[model_name]
        if is_model_disconnected(model):
            try:
                await model.disconnect()
            except Exception:
                pass
            model = None
            del ModelRefs[model_name]
    if model is None:
        # NOTE(tinwood): Due to
        # https://github.com/juju/python-libjuju/issues/458 set the max frame
        # size to something big to stop "RPC: Connection closed, reconnecting"
        # messages and then failures.
        model = Model(max_frame_size=JUJU_MAX_FRAME_SIZE)
        await model.connect(model_name)
        ModelRefs[model_name] = model
    return model


def is_model_disconnected(model):
    """Return True if the model is disconnected.

    :param model: the model to check
    :type model: :class:'juju.Model'
    :returns: True if disconnected
    :rtype: bool
    """
    return not (model.is_connected() and model.connection().is_open)


async def async_get_current_model():
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


async def async_get_full_juju_status(model_name=None):
    """Return the full juju status output.

    :param model_name: Name of model to query.
    :type model_name: str
    :returns: Full juju status output
    :rtype: dict
    """
    status = await async_get_status(model_name=model_name)
    return status


# A map of model names <-> last time get_status was called, and the result of
# that call.
_GET_STATUS_TIMES = {}
StatusResult = collections.namedtuple("StatusResult", ["time", "result"])


async def async_get_status(model_name=None, interval=4.0, refresh=True):
    """Return the full status, but share calls between different asyncs.

    Return the full status for the model_name (current model is None), but no
    faster than interval time, which is a default of 4 seconds.  If refresh is
    True, then this function waits until the interval is exceeded, and then
    returns the refreshed status.  This is the default.  If refresh is False,
    then the function immediately returns with the cached information.

    This is to enable multiple co-routines to access the status information
    without making multiple calls to Juju which all essentially will return
    identical information.

    Note that this is NOT thread-safe, but is async safe.  i.e. multiple
    different co-operating async futures can call this (in the same thread) and
    all access the same status.

    :param model_name: Name of model to query.
    :type model_name: str
    :param interval: The minimum time between calls to get_status
    :type interval: float
    :param refresh: Force a refresh; do not used cached results
    :type refresh: bool
    :returns: dictionary of juju status
    :rtype: dict
    """
    key = str(model_name)
    model = None

    async def _update_status_result(key):
        nonlocal model
        if model is None:
            model = await get_model(model_name)
        status = StatusResult(time.time(), await model.get_status())
        _GET_STATUS_TIMES[key] = status
        return status.result

    try:
        last = _GET_STATUS_TIMES[key]
    except KeyError:
        return await _update_status_result(key)
    now = time.time()
    if last.time + interval <= now:
        # we need to refresh the status time, so let's do that.
        return await _update_status_result(key)
    # otherwise, if we need a refreshed version, then we have to wait;
    if refresh:
        # wait until the min interval is exceeded, and then grab a copy.
        await asyncio.sleep((last.time + interval) - now)
        # now get the status.
        # By passing refresh=False, this WILL return a cached status if another
        # co-routine has already refreshed it.
        return await async_get_status(model_name, interval, refresh=False)
    # Not refreshing, so return the cached version
    return last.result


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
    model = await get_model(model_name)
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
            model = await get_model(model_name)
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
    model = await get_model(model_name)
    return await model.applications[application_name].get_config()


async def async_get_lead_unit_name(application_name, model_name=None):
    """Return name of unit with leader status for given application.

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :returns: Name of unit with leader status
    :rtype: str
    :raises: zaza.utilities.exceptions.JujuError
    """
    return (await async_get_lead_unit(application_name, model_name)).entity_id


async def async_get_lead_unit(application_name, model_name=None):
    """Return the leader unit for a given application.

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :returns: Name of unit with leader status
    :raises: zaza.utilities.exceptions.JujuError
    """
    model = await get_model(model_name)
    for unit in model.applications[application_name].units:
        is_leader = await unit.is_leader_from_status()
        if is_leader:
            return unit
    raise JujuError("No leader found for application {}".format(application_name))


async def async_run_action_on_leader(
    application_name, action_name, model_name=None, action_params=None, raise_on_failure=False
):
    """Run action on lead unit of the given application.

    :param model_name: Name of model to query.
    :type model_name: str
    :param application_name: Name of application
    :type application_name: str
    :param action_name: Name of action to run
    :type action_name: str
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

    model = await get_model(model_name)
    for unit in model.applications[application_name].units:
        is_leader = await unit.is_leader_from_status()
        if is_leader:
            action_obj = await unit.run_action(action_name, **action_params)
            await action_obj.wait()
            if raise_on_failure and action_obj.status != "completed":
                try:
                    output = await model.get_action_output(action_obj.id)
                except KeyError:
                    output = None
                raise ActionFailed(action_obj, output=output)
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
    model = await get_model(model_name)
    unit = await async_get_unit_from_name(unit_name, model)
    await unit.scp_from(source, destination, user=user, proxy=proxy, scp_opts=scp_opts)


async def async_run_on_leader(application_name, command, model_name=None, timeout=None):
    """Juju run on leader unit.

    :param application_name: Application to match
    :type application_name: str
    :param command: Command to execute
    :type command: str
    :param model_name: Name of model unit is in
    :type model_name: str
    :param timeout: How long in seconds to wait for command to complete
    :type timeout: int
    :returns: action.data['results'] {'Code': '', 'Stderr': '', 'Stdout': ''}
    :rtype: dict
    """
    model = await get_model(model_name)
    for unit in model.applications[application_name].units:
        is_leader = await unit.is_leader_from_status()
        if is_leader:
            action = await unit.run(command, timeout=timeout)
            results = action.data.get("results")
            return _normalise_action_results(results)


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
    model = await get_model(model_name)
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
