#  Copyright 2023 Canonical Limited
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
import json
from unittest.mock import AsyncMock, call, patch

import pytest

from cou.exceptions import RunUpgradeError
from cou.utils import app_utils


@pytest.mark.asyncio
async def test_application_upgrade_packages(model):
    model.run_on_unit.return_value = {"return-code": "0", "stdout": "Success"}
    units = ["keystone/0", "keystone/1"]

    for unit in units:
        await app_utils.upgrade_packages(unit=unit, model=model, packages_to_hold=None)

    dpkg_opts = "-o Dpkg::Options::=--force-confnew -o Dpkg::Options::=--force-confdef"
    expected_calls = [
        call(
            unit_name="keystone/0",
            command="apt-get update && "
            f"apt-get dist-upgrade {dpkg_opts} -y && "
            "apt-get autoremove -y",
            timeout=600,
        ),
        call(
            unit_name="keystone/1",
            command="apt-get update && "
            f"apt-get dist-upgrade {dpkg_opts} -y && "
            "apt-get autoremove -y",
            timeout=600,
        ),
    ]

    model.run_on_unit.assert_has_awaits(expected_calls)


@pytest.mark.asyncio
async def test_application_upgrade_packages_with_hold(model):
    model.run_on_unit.return_value = {"return-code": "0", "stdout": "Success"}
    units = ["keystone/0", "keystone/1"]

    for unit in units:
        await app_utils.upgrade_packages(
            unit=unit, model=model, packages_to_hold=["package1", "package2"]
        )

    dpkg_opts = "-o Dpkg::Options::=--force-confnew -o Dpkg::Options::=--force-confdef"
    expected_calls = [
        call(
            unit_name="keystone/0",
            command="apt-mark hold package1 package2 && apt-get update && "
            f"apt-get dist-upgrade {dpkg_opts} -y && "
            "apt-get autoremove -y ; apt-mark unhold package1 package2",
            timeout=600,
        ),
        call(
            unit_name="keystone/1",
            command="apt-mark hold package1 package2 && apt-get update && "
            f"apt-get dist-upgrade {dpkg_opts} -y && "
            "apt-get autoremove -y ; apt-mark unhold package1 package2",
            timeout=600,
        ),
    ]

    model.run_on_unit.assert_has_awaits(expected_calls)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "current_required_osd_release, current_osd_release",
    [
        ("nautilus", "octopus"),
        ("octopus", "pacific"),
        ("pacific", "quincy"),
    ],
)
@patch("cou.utils.app_utils._get_required_osd_release", new_callable=AsyncMock)
@patch("cou.utils.app_utils._get_current_osd_release", new_callable=AsyncMock)
async def test_set_require_osd_release_option_different_releases(
    mock_get_current_osd_release,
    mock_get_required_osd_release,
    model,
    current_required_osd_release,
    current_osd_release,
):
    mock_get_required_osd_release.return_value = current_required_osd_release
    mock_get_current_osd_release.return_value = current_osd_release
    model.run_on_unit.return_value = {"return-code": "0", "stdout": "Success"}

    await app_utils.set_require_osd_release_option(unit="ceph-mon/0", model=model)

    model.run_on_unit.assert_called_once_with(
        unit_name="ceph-mon/0",
        command=f"ceph osd require-osd-release {current_osd_release}",
        timeout=600,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "current_required_osd_release, current_osd_release",
    [
        ("octopus", "octopus"),
        ("pacific", "pacific"),
    ],
)
@patch("cou.utils.app_utils._get_required_osd_release", new_callable=AsyncMock)
@patch("cou.utils.app_utils._get_current_osd_release", new_callable=AsyncMock)
async def test_set_require_osd_release_option_same_release(
    mock_get_current_osd_release,
    mock_get_required_osd_release,
    model,
    current_required_osd_release,
    current_osd_release,
):
    mock_get_required_osd_release.return_value = current_required_osd_release
    mock_get_current_osd_release.return_value = current_osd_release

    await app_utils.set_require_osd_release_option(unit="ceph-mon/0", model=model)

    assert not model.run_on_unit.called


@pytest.mark.asyncio
async def test_get_required_osd_release(model):
    expected_current_release = "octopus"
    check_result = """
        {"crush_version":7,"min_compat_client":"jewel","require_osd_release":"octopus"}
    """
    model.run_on_unit.return_value = {"return-code": "0", "stdout": check_result}
    actual_current_release = await app_utils._get_required_osd_release(
        unit="ceph-mon/0", model=model
    )

    model.run_on_unit.assert_called_once_with(
        unit_name="ceph-mon/0",
        command="ceph osd dump -f json",
        timeout=600,
    )
    assert actual_current_release == expected_current_release


@pytest.mark.asyncio
async def test_get_current_osd_release(model):
    expected_osd_release = "octopus"
    check_output = """
    {
        "mon": {
            "ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) octopus (stable)": 1
        },
        "mgr": {
            "ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) octopus (stable)": 1
        },
        "osd": {
            "ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) %s (stable)": 3
        },
        "mds": {},
        "overall": {
            "ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) octopus (stable)": 5
        }
    }
    """ % (
        expected_osd_release
    )
    model.run_on_unit.return_value = {"return-code": "0", "stdout": check_output}
    actual_osd_release = await app_utils._get_current_osd_release(unit="ceph-mon/0", model=model)

    model.run_on_unit.assert_called_once_with(
        unit_name="ceph-mon/0",
        command="ceph versions -f json",
        timeout=600,
    )

    assert actual_osd_release == expected_osd_release


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "osd_release_output, error_message",
    [
        (
            {},  # OSDs release information is empty
            "Cannot get OSD release information on ceph-mon unit 'ceph-mon/0'.",
        ),
        (
            {
                "ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) octopus (stable)": 2,
                "ceph version 16.2.13 (8a82819d84cf884bd39c17e3236e0632) pacific (stable)": 1,
            },  # mismatched OSD releases
            "OSDs are on mismatched releases:\n",
        ),
        (
            {
                "ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) invalid (stable)": 3,
            },  # unsupported OSD releases
            "Cannot recognize Ceph release 'invalid'. The supporting "
            "releases are: octopus, pacific, quincy",
        ),
    ],
)
async def test_get_current_osd_release_unsuccessful(model, osd_release_output, error_message):
    check_output = """
    {
        "mon": {
            "ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) octopus (stable)": 1
        },
        "mgr": {
            "ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) octopus (stable)": 1
        },
        "osd": %s,
        "mds": {},
        "overall": {
            "ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) octopus (stable)": 5
        }
    }
    """ % (
        json.dumps(osd_release_output)
    )
    model.run_on_unit.return_value = {"return-code": "0", "stdout": check_output}
    with pytest.raises(RunUpgradeError, match=error_message):
        await app_utils._get_current_osd_release(unit="ceph-mon/0", model=model)

    model.run_on_unit.assert_called_once_with(
        unit_name="ceph-mon/0",
        command="ceph versions -f json",
        timeout=600,
    )
