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
from juju.errors import JujuError

from cou.exceptions import RunUpgradeError
from cou.utils import app_utils


@pytest.mark.asyncio
async def test_application_upgrade_packages(model):
    model.run_on_unit.return_value = {"Code": "0", "Stdout": "Success"}

    await app_utils.upgrade_packages(units=["keystone/0", "keystone/1"], model=model)

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
async def test_application_upgrade_packages_unsuccessful(model):
    exp_error_msg = "Cannot upgrade packages on keystone/0."
    model.run_on_unit.return_value = {"Code": "non-zero", "Stderr": "error"}

    with pytest.raises(RunUpgradeError, match=exp_error_msg):
        await app_utils.upgrade_packages(units=["keystone/0", "keystone/1"], model=model)

    dpkg_opts = "-o Dpkg::Options::=--force-confnew -o Dpkg::Options::=--force-confdef"
    model.run_on_unit.assert_called_once_with(
        unit_name="keystone/0",
        command=f"apt-get update && apt-get dist-upgrade {dpkg_opts} -y && apt-get autoremove -y",
        timeout=600,
    )


@pytest.mark.asyncio
async def test_application_upgrade_packages_error(model):
    exp_error_msg = "Cannot upgrade packages on keystone/0."
    model.run_on_unit.side_effect = JujuError("error")

    with pytest.raises(RunUpgradeError, match=exp_error_msg):
        await app_utils.upgrade_packages(units=["keystone/0", "keystone/1"], model=model)

    dpkg_opts = "-o Dpkg::Options::=--force-confnew -o Dpkg::Options::=--force-confdef"
    model.run_on_unit.assert_called_once_with(
        unit_name="keystone/0",
        command=f"apt-get update && apt-get dist-upgrade {dpkg_opts} -y && apt-get autoremove -y",
        timeout=600,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "current_required_osd_release, current_osd_release",
    [
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
    model.run_on_unit.return_value = {"Code": "0", "Stdout": "Success"}

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
@patch("cou.utils.app_utils._get_required_osd_release", new_callable=AsyncMock)
@patch("cou.utils.app_utils._get_current_osd_release", new_callable=AsyncMock)
async def test_set_require_osd_release_option_set_unsuccessful(
    mock_get_current_osd_release, mock_get_required_osd_release, model
):
    current_required_osd_release = "octopus"
    current_osd_release = "pacific"
    mock_get_required_osd_release.return_value = current_required_osd_release
    mock_get_current_osd_release.return_value = current_osd_release

    exp_error_msg = (
        f"Cannot set '{current_osd_release}' to "
        "require_osd_release on ceph-mon unit 'ceph-mon/0'."
    )
    model.run_on_unit.return_value = {"Code": "1", "Stderr": "error"}

    with pytest.raises(RunUpgradeError, match=exp_error_msg):
        await app_utils.set_require_osd_release_option(unit="ceph-mon/0", model=model)

    model.run_on_unit.assert_called_once_with(
        unit_name="ceph-mon/0",
        command=f"ceph osd require-osd-release {current_osd_release}",
        timeout=600,
    )


@pytest.mark.asyncio
@patch("cou.utils.app_utils._get_required_osd_release", new_callable=AsyncMock)
@patch("cou.utils.app_utils._get_current_osd_release", new_callable=AsyncMock)
async def test_set_require_osd_release_option_set_error(
    mock_get_current_osd_release, mock_get_required_osd_release, model
):
    current_required_osd_release = "octopus"
    current_osd_release = "pacific"
    mock_get_required_osd_release.return_value = current_required_osd_release
    mock_get_current_osd_release.return_value = current_osd_release

    exp_error_msg = (
        f"Cannot set '{current_osd_release}' to "
        "require_osd_release on ceph-mon unit 'ceph-mon/0'."
    )
    model.run_on_unit.side_effect = JujuError("error")

    with pytest.raises(RunUpgradeError, match=exp_error_msg):
        await app_utils.set_require_osd_release_option(unit="ceph-mon/0", model=model)

    expected_calls = [
        call(
            unit_name="ceph-mon/0",
            command=f"ceph osd require-osd-release {current_osd_release}",
            timeout=600,
        ),
    ]

    model.run_on_unit.assert_has_awaits(expected_calls)


@pytest.mark.asyncio
async def test_get_required_osd_release(model):
    expected_current_release = "octopus"
    check_result = f"""
        crush_version 7
        require_min_compat_client luminous
        min_compat_client jewel
        require_osd_release {expected_current_release}
        foo bar test
    """
    model.run_on_unit.return_value = {"Code": "0", "Stdout": check_result}
    actual_current_release = await app_utils._get_required_osd_release(
        unit="ceph-mon/0", model=model
    )

    model.run_on_unit.assert_called_once_with(
        unit_name="ceph-mon/0",
        command="ceph osd dump",
        timeout=600,
    )
    assert actual_current_release == expected_current_release


@pytest.mark.asyncio
async def test_get_required_osd_release_unsuccessful(model):
    exp_error_msg = (
        "Cannot determine the current value of require_osd_release on ceph-mon unit 'ceph-mon/0'."
    )
    model.run_on_unit.return_value = {"Code": "non-zero", "Stderr": "error"}

    with pytest.raises(RunUpgradeError, match=exp_error_msg):
        await app_utils._get_required_osd_release(unit="ceph-mon/0", model=model)

    model.run_on_unit.assert_called_once_with(
        unit_name="ceph-mon/0",
        command="ceph osd dump",
        timeout=600,
    )


@pytest.mark.asyncio
async def test_get_required_osd_release_error(model):
    exp_error_msg = (
        "Cannot determine the current value of require_osd_release on ceph-mon unit 'ceph-mon/0'."
    )
    model.run_on_unit.side_effect = JujuError("error")

    with pytest.raises(RunUpgradeError, match=exp_error_msg):
        await app_utils._get_required_osd_release(unit="ceph-mon/0", model=model)

    model.run_on_unit.assert_called_once_with(
        unit_name="ceph-mon/0",
        command="ceph osd dump",
        timeout=600,
    )


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
    model.run_on_unit.return_value = {"Code": "0", "Stdout": check_output}
    actual_osd_release = await app_utils._get_current_osd_release(unit="ceph-mon/0", model=model)

    model.run_on_unit.assert_called_once_with(
        unit_name="ceph-mon/0",
        command="ceph versions",
        timeout=600,
    )

    assert actual_osd_release == expected_osd_release


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stdout_code, osd_release_output, error_message",
    [
        (
            "1",  # non-zero return code
            {"ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) octopus (stable)": 3},
            "Cannot get the current release of OSDs from ceph-mon unit 'ceph-mon/0'.",
        ),
        (
            "0",
            {},  # OSDs release information is empty
            "Cannot get OSD release information on ceph-mon unit 'ceph-mon/0'.",
        ),
        (
            "0",
            {
                "ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) octopus (stable)": 2,
                "ceph version 16.2.13 (8a82819d84cf884bd39c17e3236e0632) pacific (stable)": 1,
            },  # mismatched OSD releases
            "OSDs are on mismatched releases:\n",
        ),
    ],
)
async def test_get_current_osd_release_unsuccessful(
    model, stdout_code, osd_release_output, error_message
):
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
    model.run_on_unit.return_value = {"Code": stdout_code, "Stdout": check_output}
    with pytest.raises(RunUpgradeError, match=error_message):
        await app_utils._get_current_osd_release(unit="ceph-mon/0", model=model)

    model.run_on_unit.assert_called_once_with(
        unit_name="ceph-mon/0",
        command="ceph versions",
        timeout=600,
    )


@pytest.mark.asyncio
async def test_get_current_osd_release_error(model):
    exp_error_msg = "Cannot get the current release of OSDs from ceph-mon unit 'ceph-mon/0'."
    model.run_on_unit.side_effect = JujuError("error")

    with pytest.raises(RunUpgradeError, match=exp_error_msg):
        await app_utils._get_current_osd_release(unit="ceph-mon/0", model=model)

    model.run_on_unit.assert_called_once_with(
        unit_name="ceph-mon/0",
        command="ceph versions",
        timeout=600,
    )
