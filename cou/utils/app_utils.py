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
from typing import Optional

from cou.exceptions import RunUpgradeError
from cou.utils.juju_utils import Model
from cou.utils.openstack import CEPH_RELEASES

logger = logging.getLogger(__name__)


async def upgrade_packages(unit: str, model: Model, packages_to_hold: Optional[list]) -> None:
    """Run package updates and upgrades on each unit of an Application.

    :param unit: Unit name where the package upgrade runs on.
    :type unit: str
    :param model: Model object
    :type model: Model
    :param packages_to_hold: A list of packages to put on hold during package upgrade.
    :type packages_to_hold: Optional[list]
    :raises CommandRunFailed: When a command fails to run.
    """
    dpkg_opts = "-o Dpkg::Options::=--force-confnew -o Dpkg::Options::=--force-confdef"
    command = f"apt-get update && apt-get dist-upgrade {dpkg_opts} -y && apt-get autoremove -y"
    if packages_to_hold:
        packages = " ".join(packages_to_hold)
        command = f"apt-mark hold {packages} && {command} ; apt-mark unhold {packages}"

    await model.run_on_unit(unit_name=unit, command=command, timeout=600)


async def set_require_osd_release_option(
    expected_ceph_release: str, unit: str, model: Model
) -> None:
    """Check and set the correct value for require-osd-release on a ceph-mon unit.

    This function compares the value of require-osd-release option with the expected release
    ceph release. If they are not the same, set the OSDs release as the value for
    require-osd-release.
    As a pre-upgrade step when upgrading ceph-mon, the expected release should match with the
    expected current channel because ceph components are not upgraded yet, whereas as a post
    upgrade of ceph-osd, it should match with the target because all ceph components should be
    already upgraded.

    :param expected_ceph_release: The expected ceph release of the cloud.
    :type expected_ceph_release: str
    :param unit: The ceph-mon unit name where the check command runs on.
    :type unit: str
    :param model: Model object
    :type model: Model
    :raises CommandRunFailed: When a command fails to run.
    """
    # The current `require_osd_release` value set on the ceph-mon unit
    current_require_osd_release = await _get_required_osd_release(unit, model)

    await _validate_ceph_component_versions(unit, model)

    if current_require_osd_release != expected_ceph_release:
        set_command = f"ceph osd require-osd-release {expected_ceph_release}"
        await model.run_on_unit(unit_name=unit, command=set_command, timeout=600)


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
    current_require_osd_release = json.loads(check_option_result["Stdout"]).get(
        "require_osd_release", ""
    )
    logger.debug("Current require-osd-release is set to: %s", current_require_osd_release)

    return current_require_osd_release


async def _validate_ceph_component_versions(unit: str, model: Model) -> None:
    """Validate all ceph components in the cloud.

    Before upgrading any ceph component or after upgrading all components, ceph should have a
    single release.

    :param unit: The ceph-mon unit name where the validation happens.
    :type unit: str
    :param model: Model object
    :type model: Model
    :raises RunUpgradeError: When ceph components are not as expected.
    """
    ceph_components_releases = await _get_ceph_components_releases(unit, model)
    if "osd" not in ceph_components_releases:
        raise RunUpgradeError(f"Cannot get OSD release information on ceph-mon unit '{unit}'.")
    for ceph_component, ceph_releases in ceph_components_releases.items():
        if len(ceph_releases) > 1:
            raise RunUpgradeError(
                f"{ceph_component} are on mismatched releases:\n{ceph_releases}."
                "Please manually upgrade them to be on the same release before proceeding."
            )
        if not ceph_releases.issubset(CEPH_RELEASES):
            raise RunUpgradeError(
                f"Cannot recognize Ceph release '{ceph_releases - set(CEPH_RELEASES)}'. "
                f"The supporting releases are {CEPH_RELEASES}"
            )


async def _get_ceph_components_releases(unit: str, model: Model) -> dict[str, set[str]]:
    """Get the current release of OSDs.

    The release of OSDs is parsed from the output of running `ceph versions` command
    on a ceph-mon unit.
    :param unit: The ceph-mon unit name where the check command runs on.
    :type unit: str
    :param model: Model object
    :type model: Model
    :return: the release which ceph components are
    :rtype: str
    :raises RunUpgradeError: When an upgrade fails.
    :raises CommandRunFailed: When a command fails to run.
    """
    check_command = "ceph versions -f json"

    check_osd_result = await model.run_on_unit(unit_name=unit, command=check_command, timeout=600)

    return _format_ceph_version(json.loads(check_osd_result["Stdout"]))


def _format_ceph_version(ceph_versions: dict[str, dict]) -> dict[str, set[str]]:
    """Format the ceph output.

    :param ceph_versions: Ceph versions of all components
    :type ceph_versions: dict[str, dict]
    :return: Formatted ceph components versions. E.g: {"osd": {pacific}, "mon": pacific}
    :rtype: dict[str, set[str]]
    """
    output_dict = {}
    for ceph_service, ceph_version in ceph_versions.items():
        releases = set()
        for version in ceph_version.keys():
            # Example value of a version on a ceph component:
            # {'ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) octopus (stable)': 1}
            ceph_release = version.split(" ")[4].strip()
            releases.add(ceph_release)

        output_dict[ceph_service] = releases
    return output_dict
