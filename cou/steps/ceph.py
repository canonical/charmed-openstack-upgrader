# Copyright 2024 Canonical Limited
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

"""Functions for prereq steps related to ceph."""
import json
import logging

from cou.exceptions import ApplicationError, ApplicationNotFound, UnitNotFound
from cou.utils.juju_utils import Model

logger = logging.getLogger(__name__)


async def _get_leader_unit_name(model: Model) -> str:
    """Get the leader unit_name of ceph mon.

    :param model: The juju model to work with
    :type model: Model
    :return: True if noout is set, otherwise False
    :type: bool
    :raise ApplicationNotFound: if ceph-mon no founnd
    :raise UnitNotFound: if ceph-mon has no leader unit
    """
    apps = await model.get_applications()
    ceph_mon_apps = [app for app in apps.values() if app.charm == "ceph-mon"]
    if len(ceph_mon_apps) == 0:
        raise ApplicationNotFound("'ceph-mon' application not found")

    ceph_mon_units = list(ceph_mon_apps[0].units.values())
    if len(ceph_mon_units) == 0:
        raise UnitNotFound("'ceph-mon' has no units")

    for unit in ceph_mon_units:
        if unit.leader:
            return unit.name
    logger.warning("cannot find ceph-mon leader unit, using one of the unit instead.")
    return ceph_mon_units[0]


async def get_noout(model: Model, unit_name: str) -> bool:
    """Ensure ceph cluster has the noout flag unset.

    :param model: The juju model to work with
    :type model: Model
    :param unit_name: The name of the unit
    :type unit_name: str
    :return: True if noout is set, otherwise False
    :type: bool
    """
    results = await model.run_on_unit(unit_name, "ceph osd dump -f json")
    return "noout" in json.loads(results["stdout"].strip()).get("flags_set", [])


async def set_noout(model: Model, unit_name: str) -> None:
    """Set noout for ceph cluster.

    :param model: The juju model to work with
    :type model: Model
    :param unit_name: The name of the unit
    :type unit_name: str
    """
    await model.run_action(unit_name, "set-noout", raise_on_failure=True)


async def unset_noout(model: Model, unit_name: str) -> None:
    """Unset noout for ceph cluster.

    :param model: The juju model to work with
    :type model: Model
    :param unit_name: The name of the unit
    :type unit_name: str
    """
    await model.run_action(unit_name, "unset-noout", raise_on_failure=True)


async def ensure_noout(model: Model, state: bool) -> None:
    """Ensure ceph cluster has noout flag set or unset.

    :param model: The juju model to work with
    :type model: Model
    :param state: True to set noout, False to unset noout
    :type state: bool
    """
    try:
        unit_name = await _get_leader_unit_name(model)
    except (ApplicationNotFound, UnitNotFound) as e:
        logger.warning("%s, %s", str(e), "skip changing 'noout'.")
        return

    if await get_noout(model, unit_name) == state:
        logger.warning("'noout' already '%s', skip changing 'noout'", "set" if state else "unset")
        return

    if state:
        await set_noout(model, unit_name)
    else:
        await unset_noout(model, unit_name)


async def assert_noout_state(model: Model, state: bool) -> None:
    """Assert ceph cluster is set (state=True) or unset (state=False).

    :param model: The juju model to work with
    :type model: Model
    :param state: True to set noout, False to unset noout
    :type state: bool
    :raise ApplicationError: if noout is not in desired state
    """
    try:
        unit_name = await _get_leader_unit_name(model)
    except (ApplicationNotFound, UnitNotFound) as e:
        logger.warning("%s, %s", str(e), "skip verifying 'noout'.")
        return

    if await get_noout(model, unit_name) != state:
        raise ApplicationError(f"'noout' is expected to be {'set' if state else 'unset'}")
