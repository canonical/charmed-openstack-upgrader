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

from unittest.mock import call

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
async def test_application_upgrade_packages_with_hold(model):
    model.run_on_unit.return_value = {"Code": "0", "Stdout": "Success"}

    await app_utils.upgrade_packages(
        units=["keystone/0", "keystone/1"], model=model, packages_to_hold=["package1", "package2"]
    )

    dpkg_opts = "-o Dpkg::Options::=--force-confnew -o Dpkg::Options::=--force-confdef"
    expected_calls = [
        call(
            unit_name="keystone/0",
            command="sudo apt-mark hold package1 package2 && apt-get update && "
            f"apt-get dist-upgrade {dpkg_opts} -y && "
            "apt-get autoremove -y ; sudo apt-mark unhold package1 package2",
            timeout=600,
        ),
        call(
            unit_name="keystone/1",
            command="sudo apt-mark hold package1 package2 && apt-get update && "
            f"apt-get dist-upgrade {dpkg_opts} -y && "
            "apt-get autoremove -y ; sudo apt-mark unhold package1 package2",
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
    "current_release_value, target_release_value",
    [
        ("octopus", "pacific"),
        ("pacific", "quincy"),
    ],
)
async def test_set_require_osd_release_option_different_releases(
    model, current_release_value, target_release_value
):
    check_result = f"""
        crush_version 7
        require_min_compat_client luminous
        min_compat_client jewel
        require_osd_release {current_release_value}
        stretch_mode_enabled false
        foo bar test
    """
    model.run_on_unit.side_effect = [
        {"Code": "0", "Stdout": check_result},
        {"Code": "0", "Stdout": "Success"},
    ]

    await app_utils.set_require_osd_release_option(
        unit="ceph-mon/0", model=model, ceph_release=target_release_value
    )

    expected_calls = [
        call(
            unit_name="ceph-mon/0",
            command="ceph osd dump",
            timeout=600,
        ),
        call(
            unit_name="ceph-mon/0",
            command=f"ceph osd require-osd-release {target_release_value}",
            timeout=600,
        ),
    ]

    model.run_on_unit.assert_has_awaits(expected_calls)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "current_release_value, target_release_value",
    [
        ("octopus", "octopus"),
        ("pacific", "pacific"),
    ],
)
async def test_set_require_osd_release_option_same_release(
    model, current_release_value, target_release_value
):
    check_result = f"""
        crush_version 7
        require_min_compat_client luminous
        min_compat_client jewel
        require_osd_release {current_release_value}
        foo bar test
    """
    model.run_on_unit.side_effect = [
        {"Code": "0", "Stdout": check_result},
        {"Code": "0", "Stdout": "Success"},
    ]

    await app_utils.set_require_osd_release_option(
        unit="ceph-mon/0", model=model, ceph_release=target_release_value
    )

    model.run_on_unit.assert_called_once_with(
        unit_name="ceph-mon/0",
        command="ceph osd dump",
        timeout=600,
    )


@pytest.mark.asyncio
async def test_set_require_osd_release_option_check_unsuccessful(model):
    exp_error_msg = (
        "Cannot determine the current value of require_osd_release on ceph-mon unit 'ceph-mon/0'."
    )
    model.run_on_unit.return_value = {"Code": "non-zero", "Stderr": "error"}

    with pytest.raises(RunUpgradeError, match=exp_error_msg):
        await app_utils.set_require_osd_release_option(
            unit="ceph-mon/0", model=model, ceph_release="pacific"
        )

    model.run_on_unit.assert_called_once_with(
        unit_name="ceph-mon/0",
        command="ceph osd dump",
        timeout=600,
    )


@pytest.mark.asyncio
async def test_set_require_osd_release_option_check_error(model):
    exp_error_msg = (
        "Cannot determine the current value of require_osd_release on ceph-mon unit 'ceph-mon/0'."
    )
    model.run_on_unit.side_effect = JujuError("error")

    with pytest.raises(RunUpgradeError, match=exp_error_msg):
        await app_utils.set_require_osd_release_option(
            unit="ceph-mon/0", model=model, ceph_release="pacific"
        )

    model.run_on_unit.assert_called_once_with(
        unit_name="ceph-mon/0",
        command="ceph osd dump",
        timeout=600,
    )


@pytest.mark.asyncio
async def test_set_require_osd_release_option_set_unsuccessful(model):
    current_release_value = "octopus"
    target_release_value = "pacific"
    check_result = f"""
        crush_version 7
        require_min_compat_client luminous
        min_compat_client jewel
        require_osd_release {current_release_value}
        foo bar test
    """
    exp_error_msg = (
        f"Cannot set '{target_release_value}' to "
        "require_osd_release on ceph-mon unit 'ceph-mon/0'."
    )
    model.run_on_unit.side_effect = [
        {"Code": "0", "Stdout": check_result},
        {"Code": "non-zero", "Stderr": "error"},
    ]

    with pytest.raises(RunUpgradeError, match=exp_error_msg):
        await app_utils.set_require_osd_release_option(
            unit="ceph-mon/0", model=model, ceph_release=target_release_value
        )

    expected_calls = [
        call(
            unit_name="ceph-mon/0",
            command="ceph osd dump",
            timeout=600,
        ),
        call(
            unit_name="ceph-mon/0",
            command=f"ceph osd require-osd-release {target_release_value}",
            timeout=600,
        ),
    ]

    model.run_on_unit.assert_has_awaits(expected_calls)


@pytest.mark.asyncio
async def test_set_require_osd_release_option_set_error(model):
    current_release_value = "octopus"
    target_release_value = "pacific"
    check_result = f"""
        crush_version 7
        require_min_compat_client luminous
        min_compat_client jewel
        require_osd_release {current_release_value}
        foo bar test
    """
    exp_error_msg = (
        f"Cannot set '{target_release_value}' to "
        "require_osd_release on ceph-mon unit 'ceph-mon/0'."
    )
    model.run_on_unit.side_effect = [
        {"Code": "0", "Stdout": check_result},
        JujuError("error"),
    ]

    with pytest.raises(RunUpgradeError, match=exp_error_msg):
        await app_utils.set_require_osd_release_option(
            unit="ceph-mon/0", model=model, ceph_release=target_release_value
        )

    expected_calls = [
        call(
            unit_name="ceph-mon/0",
            command="ceph osd dump",
            timeout=600,
        ),
        call(
            unit_name="ceph-mon/0",
            command=f"ceph osd require-osd-release {target_release_value}",
            timeout=600,
        ),
    ]

    model.run_on_unit.assert_has_awaits(expected_calls)
