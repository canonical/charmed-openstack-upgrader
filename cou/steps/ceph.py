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
from typing import Sequence

from cou.exceptions import (
    ApplicationError,
    ApplicationNotFound,
    RunUpgradeError,
    UnitNotFound,
)
from cou.utils.juju_utils import Application, Model, get_applications_by_charm_name
from cou.utils.openstack import CEPH_RELEASES

logger = logging.getLogger(__name__)


# Private functions
async def _get_required_osd_release(unit: str, model: Model) -> str:
    """Get the value of require-osd-release option on a ceph-mon unit.

    :param unit: The ceph-mon unit name where the check command runs on.
    :type unit: str
    :param model: Model object
    :type model: Model
    :return: the value of require-osd-release option
    :rtype: str
    :raises CommandRunFailed: When a command fails to run.
    """
    check_command = "ceph osd dump -f json"

    check_option_result = await model.run_on_unit(
        unit_name=unit, command=check_command, timeout=600
    )
    current_require_osd_release = json.loads(check_option_result["stdout"]).get(
        "require_osd_release", ""
    )
    logger.debug("Current require-osd-release is set to: %s", current_require_osd_release)

    return current_require_osd_release


async def _get_current_osd_release(unit: str, model: Model) -> str:
    """Get the current release of OSDs.

    The release of OSDs is parsed from the output of running `ceph versions` command
    on a ceph-mon unit.
    :param unit: The ceph-mon unit name where the check command runs on.
    :type unit: str
    :param model: Model object
    :type model: Model
    :return: the release which OSDs are on
    :rtype: str
    :raises RunUpgradeError: When an upgrade fails.
    :raises CommandRunFailed: When a command fails to run.
    """
    check_command = "ceph versions -f json"

    check_osd_result = await model.run_on_unit(unit_name=unit, command=check_command, timeout=600)

    osd_release_output = json.loads(check_osd_result["stdout"]).get("osd", None)
    # throw exception if ceph-mon doesn't contain osd release information in `ceph`
    if not osd_release_output:
        raise RunUpgradeError(f"Cannot get OSD release information on ceph-mon unit '{unit}'.")
    # throw exception if OSDs are on mismatched releases
    if len(osd_release_output) > 1:
        raise RunUpgradeError(
            f"OSDs are on mismatched releases:\n{osd_release_output}."
            "Please manually upgrade them to be on the same release before proceeding."
        )

    # get release name from "osd_release_output". Example value of "osd_release_output":
    # {'ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) octopus (stable)': 1}
    osd_release_key, *_ = osd_release_output.keys()
    current_osd_release = osd_release_key.split(" ")[4].strip()
    ceph_releases = ", ".join(CEPH_RELEASES)
    if current_osd_release not in ceph_releases:
        raise RunUpgradeError(
            f"Cannot recognize Ceph release '{current_osd_release}'. The supporting "
            f"releases are: {ceph_releases}"
        )
    logger.debug("Currently OSDs are on the '%s' release", current_osd_release)

    return current_osd_release


def _get_unit_name(ceph_mon_app: Application) -> str:
    """Get the one of the unit's name from ceph mon application.

    :param ceph_mon_app: The ceph mon application
    :type ceph_mon_app: Application
    :return: ceph-mon's unit name
    :type: str
    :raise UnitNotFound: if ceph-mon has no units
    """
    ceph_mon_units = list(ceph_mon_app.units.values())
    if not ceph_mon_units:
        raise UnitNotFound(f"'{ceph_mon_app.name}' has no units, is this a valid OpenStack cloud?")
    return ceph_mon_units[0].name


async def osd_noout(model: Model, apps: Sequence[Application], enable: bool) -> None:
    """Set or unset 'noout' for ceph cluster(s).

    Note this will set or unset 'noout' flag for all ceph clusters present in
    the model.

    :param model: The juju model to work with
    :type model: Model
    :param apps: List of Application
    :type apps: Sequence[Application]
    :param enable: True to set noout, False to unset noout
    :type enable: bool
    """
    try:
        ceph_mon_apps = get_applications_by_charm_name(apps, "ceph-mon")
    except ApplicationNotFound as e:
        logger.warning("%s", str(e))
        logger.warning("Skip changing 'noout', because there's no ceph-mon applications.")
        return

    for ceph_mon_app in ceph_mon_apps:
        try:
            ceph_mon_unit_name = _get_unit_name(ceph_mon_app)
        except UnitNotFound as e:
            logger.warning("%s", str(e))
            logger.warning(
                "Skip changing 'noout', because there's no %s units.", ceph_mon_app.name
            )
            continue

        await model.run_action(
            ceph_mon_unit_name, f"{'set' if enable else 'unset'}-noout", raise_on_failure=True
        )


async def get_osd_noout_state(model: Model, unit_name: str) -> bool:
    """Check if noout is set on ceph cluster or not.

    :param model: The juju model to work with
    :type model: Model
    :param unit_name: The name of the unit
    :type unit_name: str
    :return: True if noout is set, otherwise False
    :type: bool
    """
    results = await model.run_on_unit(unit_name, "ceph osd dump -f json")
    return "noout" in json.loads(results["stdout"].strip()).get("flags_set", [])


async def assert_osd_noout_state(model: Model, apps: Sequence[Application], state: bool) -> None:
    """Assert ceph cluster is set (state=True) or unset (state=False).

    Note this will assert 'noout' flag is in the desired state for all ceph
    clusters present in the model.

    :param model: The juju model to work with
    :type model: Model
    :param apps:List of Application
    :type apps: Sequence[Application]
    :param state: True noout is set, otherwise False
    :type state: bool
    :raise ApplicationError: if noout is not in desired state
    """
    try:
        ceph_mon_apps = get_applications_by_charm_name(apps, "ceph-mon")
    except ApplicationNotFound as e:
        logger.warning("%s", str(e))
        logger.warning("Skip verifying 'noout', because there's no ceph-mon applications.")
        return

    error = False
    for ceph_mon_app in ceph_mon_apps:
        try:
            ceph_mon_unit_name = _get_unit_name(ceph_mon_app)
        except UnitNotFound as e:
            logger.warning("%s", str(e))
            logger.warning(
                "Skip verifying 'noout', because there's no %s units.", ceph_mon_app.name
            )
            continue

        if await get_osd_noout_state(model, ceph_mon_unit_name) is not state:
            error = True
            logger.error(
                "'noout' is expected to be %s for %s",
                "set" if state else "unset",
                ceph_mon_app.name,
            )

    if error:
        raise ApplicationError("Ceph cluster's 'noout' is not in expected state.")


async def set_require_osd_release_option_on_unit(model: Model, unit_name: str) -> None:
    """Check and set the correct value for require-osd-release on one ceph-mon unit.

    This function compares the value of require-osd-release option with the
    current release of OSDs. If they are not the same, set the OSDs release as
    the value for require-osd-release.

    :param model: Model object
    :type model: Model
    :param unit_name: The name of the unit
    :type unit_name: str
    :raises CommandRunFailed: When a command fails to run.
    """
    # The current `require_osd_release` value set on the ceph-mon unit
    current_require_osd_release = await _get_required_osd_release(unit_name, model)
    # The actual release which OSDs are on
    current_running_osd_release = await _get_current_osd_release(unit_name, model)

    if current_require_osd_release != current_running_osd_release:
        set_command = f"ceph osd require-osd-release {current_running_osd_release}"
        await model.run_on_unit(unit_name=unit_name, command=set_command, timeout=600)


async def set_require_osd_release_option(model: Model, apps: Sequence[Application]) -> None:
    """Check and set the correct value for require-osd-release on all ceph-mon unit.

    This function compares the value of require-osd-release option with the
    current release of OSDs. If they are not the same, set the OSDs release as
    the value for require-osd-release.

    Note this will set 'require-osd-release' option with the current release of
    OSDs for all ceph clusters present in the model.

    :param model: Model object
    :type model: Model
    :param apps:List of Application
    :type apps: Sequence[Application]
    :raises CommandRunFailed: When a command fails to run.
    """
    try:
        ceph_mon_apps = get_applications_by_charm_name(apps, "ceph-mon")
    except ApplicationNotFound as e:
        logger.warning("%s", str(e))
        logger.warning(
            "Skip ensuring 'require-osd-release' option, because there's no ceph-mon applications."
        )
        return

    for ceph_mon_app in ceph_mon_apps:
        try:
            ceph_mon_unit_name = _get_unit_name(ceph_mon_app)
        except UnitNotFound as e:
            logger.warning("%s", str(e))
            logger.warning(
                "Skip ensuring 'require-osd-release' option, because there's no %s units.",
                ceph_mon_app.name,
            )
            continue

        await set_require_osd_release_option_on_unit(model, ceph_mon_unit_name)


def get_mon_apps(apps: Sequence[Application]) -> Sequence[Application]:
    """Get a list of ceph-mon apps in the model.

    :param apps: list of applications to search through for ceph-mon apps
    :type apps: list[Application]
    :return: list of ceph-mon applications
    :rtype: list[Application]
    """
    try:
        return get_applications_by_charm_name(apps, "ceph-mon")
    except ApplicationNotFound:
        return []


async def get_versions(model: Model, ceph_mon_unit_name: str) -> dict[str, dict[str, int]]:
    """Get from `ceph versions` for a ceph-mon unit.

    Output from `ceph versions` looks like this:

    {
      "mon": {
        "ceph version 16.2.14 (238ba602515df21ea7ffc75c88db29f9e5ef12c9) pacific (stable)": 2,
        "ceph version 16.2.15 (618f440892089921c3e944a991122ddc44e60516) pacific (stable)": 1
      },
      "mgr": {
        "ceph version 16.2.14 (238ba602515df21ea7ffc75c88db29f9e5ef12c9) pacific (stable)": 2,
        "ceph version 16.2.15 (618f440892089921c3e944a991122ddc44e60516) pacific (stable)": 1
      },
      "osd": {
        "ceph version 16.2.15 (618f440892089921c3e944a991122ddc44e60516) pacific (stable)": 18
      },
      "mds": {},
      "rgw": {
        "ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632ac146dc4) octopus (stable)": 2,
        "ceph version 16.2.14 (238ba602515df21ea7ffc75c88db29f9e5ef12c9) pacific (stable)": 1
      },
      "overall": {
        "ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632ac146dc4) octopus (stable)": 2,
        "ceph version 16.2.14 (238ba602515df21ea7ffc75c88db29f9e5ef12c9) pacific (stable)": 5,
        "ceph version 16.2.15 (618f440892089921c3e944a991122ddc44e60516) pacific (stable)": 20
      }
    }

    :param model: The juju model to work with
    :type model: Model
    :param ceph_mon_unit_name: name of a ceph-mon unit to run commands on
    :type ceph_mon_unit_name: str
    :return: ceph version information
    :rtype: dict[str, dict[str, int]]
    """
    result = await model.run_on_unit(ceph_mon_unit_name, "ceph versions")
    return json.loads(result["stdout"])
