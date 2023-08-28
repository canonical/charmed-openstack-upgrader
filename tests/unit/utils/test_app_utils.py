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

from cou.exceptions import PackageUpgradeError
from cou.utils import app_utils


@pytest.mark.asyncio
async def test_application_upgrade_packages(mocker):
    mock_logger = mocker.patch("cou.utils.app_utils.logger")

    success_result = {"Code": "0", "Stdout": "Success"}
    mock_async_run_on_unit = mocker.patch.object(
        app_utils, "async_run_on_unit", return_value=success_result
    )
    await app_utils.upgrade_packages(units=["keystone/0", "keystone/1"], model_name="my_model")

    dpkg_opts = "-o Dpkg::Options::=--force-confnew -o Dpkg::Options::=--force-confdef"
    expected_calls = [
        call(
            unit_name="keystone/0",
            command="apt-get update && "
            f"apt-get dist-upgrade {dpkg_opts} -y && "
            "apt-get autoremove -y",
            model_name="my_model",
        ),
        call(
            unit_name="keystone/1",
            command="apt-get update && "
            f"apt-get dist-upgrade {dpkg_opts} -y && "
            "apt-get autoremove -y",
            model_name="my_model",
        ),
    ]

    mock_async_run_on_unit.assert_has_calls(
        expected_calls,
    )
    assert len(mock_logger.debug.mock_calls) == 2


@pytest.mark.asyncio
async def test_application_upgrade_packages_failed(mocker):
    mock_logger = mocker.patch("cou.utils.app_utils.logger")

    failed_result = {"Code": "non-zero", "Stderr": "unexpected error"}
    mock_async_run_on_unit = mocker.patch.object(
        app_utils, "async_run_on_unit", return_value=failed_result
    )

    with pytest.raises(PackageUpgradeError):
        await app_utils.upgrade_packages(units=["keystone/0", "keystone/1"], model_name="my_model")

    dpkg_opts = "-o Dpkg::Options::=--force-confnew -o Dpkg::Options::=--force-confdef"
    mock_async_run_on_unit.assert_called_once_with(
        unit_name="keystone/0",
        command="apt-get update && "
        f"apt-get dist-upgrade {dpkg_opts} -y && "
        "apt-get autoremove -y",
        model_name="my_model",
    )
    mock_logger.error.assert_called_once_with(
        "Error upgrading package on %s: %s", "keystone/0", "unexpected error"
    )
