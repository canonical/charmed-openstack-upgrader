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
import logging
from collections.abc import Iterable
from typing import Optional

from juju.errors import JujuError

from cou.exceptions import CommandRunFailed, RunUpgradeError
from cou.utils.juju_utils import COUModel

logger = logging.getLogger(__name__)


async def upgrade_packages(
    units: Iterable[str], model: COUModel, packages_to_hold: Optional[list] = None
) -> None:
    """Run package updates and upgrades on each unit of an Application.

    :param units: The list of unit names where the package upgrade runs on.
    :type units: Iterable[str]
    :param model: COUModel object
    :type model: COUModel
    :param packages_to_hold: A list of packages to put on hold during package upgrade.
    :type packages_to_hold: Optional[list]
    :raises RunUpgradeError: When an upgrade fails.
    """
    dpkg_opts = "-o Dpkg::Options::=--force-confnew -o Dpkg::Options::=--force-confdef"
    command = f"apt-get update && apt-get dist-upgrade {dpkg_opts} -y && apt-get autoremove -y"
    if packages_to_hold:
        packages = " ".join(packages_to_hold)
        command = f"sudo apt-mark hold {packages} && {command} && sudo apt-mark unhold {packages}"

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


async def set_require_osd_release_option(unit: str, model: COUModel, ceph_release: str) -> None:
    """Check and set correct value for require-osd-release on a ceph-mon unit.

    :param unit: The ceph-mon unit name where the check command runs on.
    :type unit: str
    :param model: COUModel object
    :type model: COUModel
    :param ceph_release: The ceph release to set for require-osd-release.
    :type ceph_release: str
    :raises RunUpgradeError: When an upgrade fails.
    """
    current_require_osd_release = ""
    check_command = "ceph osd dump"
    logger.debug("Running '%s' on '%s'", check_command, unit)

    try:
        check_result = await model.run_on_unit(unit_name=unit, command=check_command, timeout=600)
        if str(check_result["Code"]) == "0":
            logger.debug(check_result["Stdout"])

            dump_output = check_result["Stdout"].strip().splitlines()
            for line in dump_output:
                if line.strip().startswith("require_osd_release"):
                    current_require_osd_release = line.split()[1]
            logger.debug("Current require-osd-release is set to: %s", current_require_osd_release)
        else:
            raise RunUpgradeError(
                "Cannot determine the current value of "
                f"require_osd_release on ceph-mon unit '{unit}'."
            ) from CommandRunFailed(cmd=check_command, result=check_result)

    except JujuError as exc:
        raise RunUpgradeError(
            f"Cannot determine the current value of require_osd_release on ceph-mon unit '{unit}'."
        ) from exc

    if current_require_osd_release != ceph_release:
        set_command = f"ceph osd require-osd-release {ceph_release}"
        logger.debug("Running '%s' on '%s'", set_command, unit)
        try:
            set_result = await model.run_on_unit(unit_name=unit, command=set_command, timeout=600)
            if str(set_result["Code"]) == "0":
                logger.debug(set_result["Stdout"])
            else:
                raise RunUpgradeError(
                    f"Cannot set '{ceph_release}' to require_osd_release "
                    f"on ceph-mon unit '{unit}'."
                ) from CommandRunFailed(cmd=set_command, result=set_result)

        except JujuError as exc:
            raise RunUpgradeError(
                f"Cannot set '{ceph_release}' to require_osd_release on ceph-mon unit '{unit}'."
            ) from exc
