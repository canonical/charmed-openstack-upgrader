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

"""Application utilities."""
import json
import logging
from collections.abc import Iterable

from juju.errors import JujuError
from packaging.version import Version

from cou.exceptions import ApplicationError, CommandRunFailed, RunUpgradeError
from cou.utils.juju_utils import COUModel

logger = logging.getLogger(__name__)


async def upgrade_packages(units: Iterable[str], model: COUModel) -> None:
    """Run package updates and upgrades on each unit of an Application.

    :param units: The list of unit names where the package upgrade runs on.
    :type units: Iterable[str]
    :param model: COUModel object
    :type model: COUModel
    :raises RunUpgradeError: When an upgrade fails.
    """
    dpkg_opts = "-o Dpkg::Options::=--force-confnew -o Dpkg::Options::=--force-confdef"
    command = f"apt-get update && apt-get dist-upgrade {dpkg_opts} -y && apt-get autoremove -y"

    for unit in units:
        logger.info("Running '%s' on '%s'", command, unit)

        try:
            result = await model.run_on_unit(unit_name=unit, command=command, timeout=600)
            if str(result["Code"]) == "0":
                logger.debug(result["Stdout"])
            else:
                raise RunUpgradeError(f"Cannot upgrade packages on {unit}.") from CommandRunFailed(
                    cmd=command, result=result
                )

        except JujuError as exc:
            raise RunUpgradeError(f"Cannot upgrade packages on {unit}.") from exc


async def set_require_osd_release_option(unit: str, model: COUModel) -> None:
    """Check and set the correct value for require-osd-release on a ceph-mon unit.

    This function compares the value of require-osd-release option with the current release
    of OSDs. If they are not the same, set the OSDs release as the value for
    require-osd-release.
    :param unit: The ceph-mon unit name where the check command runs on.
    :type unit: str
    :param model: COUModel object
    :type model: COUModel
    :raises RunUpgradeError: When an upgrade fails.
    """
    # The current `require_osd_release` value set on the ceph-mon unit
    current_require_osd_release = await _get_required_osd_release(unit, model)
    # The actual release which OSDs are on
    current_running_osd_release = await _get_current_osd_release(unit, model)

    if current_require_osd_release != current_running_osd_release:
        set_command = f"ceph osd require-osd-release {current_running_osd_release}"
        logger.debug("Running '%s' on '%s'", set_command, unit)
        try:
            set_result = await model.run_on_unit(unit_name=unit, command=set_command, timeout=600)
            if str(set_result["Code"]) == "0":
                logger.debug(set_result["Stdout"])
            else:
                raise RunUpgradeError(
                    f"Cannot set '{current_running_osd_release}' to require_osd_release "
                    f"on ceph-mon unit '{unit}'."
                ) from CommandRunFailed(cmd=set_command, result=set_result)

        except JujuError as exc:
            raise RunUpgradeError(
                f"Cannot set '{current_running_osd_release}' to require_osd_release on "
                f"ceph-mon unit '{unit}'."
            ) from exc


def validate_ovn_support(version: str) -> None:
    """Validate COU OVN support.

    COU does not support upgrade clouds with OVN version lower than 22.03.

    :param version: Version of the OVN.
    :type version: str
    :raises ApplicationError: When workload version is lower than 22.03.0.
    """
    if Version(version) < Version("22.03.0"):
        raise ApplicationError(
            (
                "OVN versions lower than 22.03 are not supported. It's necessary to upgrade "
                "OVN to 22.03 before upgrading the cloud. Follow the instructions at: "
                "https://docs.openstack.org/charm-guide/latest/project/procedures/"
                "ovn-upgrade-2203.html"
            )
        )


# Private functions
async def _get_required_osd_release(unit: str, model: COUModel) -> str:
    """Get the value of require-osd-release option on a ceph-mon unit.

    :param unit: The ceph-mon unit name where the check command runs on.
    :type unit: str
    :param model: COUModel object
    :type model: COUModel
    :return: True if the value of require-osd-release is the same as the release of OSDs;
    False otherwise.
    :rtype: bool
    :raises RunUpgradeError: When an upgrade fails.
    """
    current_require_osd_release = ""
    check_command = "ceph osd dump"
    logger.debug("Running '%s' on '%s'", check_command, unit)

    try:
        check_option_result = await model.run_on_unit(
            unit_name=unit, command=check_command, timeout=600
        )
        if str(check_option_result["Code"]) == "0":
            logger.debug(check_option_result["Stdout"])

            dump_output = check_option_result["Stdout"].strip().splitlines()
            for line in dump_output:
                if line.strip().startswith("require_osd_release"):
                    current_require_osd_release = line.split()[1]
            logger.debug("Current require-osd-release is set to: %s", current_require_osd_release)
        else:
            raise RunUpgradeError(
                "Cannot determine the current value of "
                f"require_osd_release on ceph-mon unit '{unit}'."
            ) from CommandRunFailed(cmd=check_command, result=check_option_result)

    except JujuError as exc:
        raise RunUpgradeError(
            f"Cannot determine the current value of require_osd_release on ceph-mon unit '{unit}'."
        ) from exc

    return current_require_osd_release


async def _get_current_osd_release(unit: str, model: COUModel) -> str:
    """Get the current release of OSDs.

    The release of OSDs is parsed from the output of running `ceph versions` command
    on a ceph-mon unit.
    :param unit: The ceph-mon unit name where the check command runs on.
    :type unit: str
    :param model: COUModel object
    :type model: COUModel
    :return: True if the value of require-osd-release is the same as the release of OSDs;
    False otherwise.
    :rtype: bool
    :raises RunUpgradeError: When an upgrade fails.
    """
    check_command = "ceph versions"
    logger.debug("Running '%s' on '%s'", check_command, unit)

    try:
        check_osd_result = await model.run_on_unit(
            unit_name=unit, command=check_command, timeout=600
        )
        if str(check_osd_result["Code"]) == "0":
            logger.debug(check_osd_result["Stdout"])

            osd_release_output = json.loads(check_osd_result["Stdout"])["osd"]
            # throw exception if ceph-mon doesn't contain osd release information in `ceph`
            if len(osd_release_output) == 0:
                raise RunUpgradeError(
                    f"Cannot get OSD release information on ceph-mon unit '{unit}'."
                )
            # throw exception if OSDs are on mismatched releases
            if len(osd_release_output) > 1:
                raise RunUpgradeError(
                    f"OSDs are on mismatched releases:\n{osd_release_output}."
                    "Please manually upgrade them to be on the same release before proceeding."
                )

            # get release name from "osd_release_output". Example value of "osd_release_output":
            # {'ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) octopus (stable)': 1}
            osd_release_key = list(osd_release_output.keys())[0]
            current_osd_release = osd_release_key.split(")", maxsplit=1)[-1].split("(")[0].strip()
            logger.debug("Currently OSDs are on the '%s' release", current_osd_release)

            return current_osd_release

        raise RunUpgradeError(
            f"Cannot get the current release of OSDs from ceph-mon unit '{unit}'."
        ) from CommandRunFailed(cmd=check_command, result=check_osd_result)

    except JujuError as exc:
        raise RunUpgradeError(
            f"Cannot get the current release of OSDs from ceph-mon unit '{unit}'."
        ) from exc
