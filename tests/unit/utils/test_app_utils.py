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

from cou.exceptions import ApplicationUpgradeError
from cou.utils import app_utils


@pytest.mark.asyncio
async def test_application_run_on_all_units(mocker):
    dpkg_opts = "-o Dpkg::Options::=--force-confnew -o Dpkg::Options::=--force-confdef"
    command = f"apt-get update && apt-get dist-upgrade {dpkg_opts} -y && apt-get autoremove -y"

    mock_logger = mocker.patch("cou.utils.app_utils.logger")

    success_result = {"Code": "0", "Stdout": "Success"}
    mock_run_on_unit = mocker.patch(
        "cou.utils.juju_utils.run_on_unit", return_value=success_result
    )
    await app_utils.run_on_all_units(
        units=["keystone/0", "keystone/1"], model_name="my_model", command=command
    )

    expected_calls = [
        call(
            unit_name="keystone/0",
            command=command,
            model_name="my_model",
            timeout=600,
        ),
        call(
            unit_name="keystone/1",
            command=command,
            model_name="my_model",
            timeout=600,
        ),
    ]

    mock_run_on_unit.assert_has_calls(
        expected_calls,
    )
    assert len(mock_logger.debug.mock_calls) == 2


@pytest.mark.asyncio
async def test_application_run_on_all_units_unsuccessful(mocker):
    exp_error_msg = "Cannot upgrade application: operation on keystone/0 failed."
    dpkg_opts = "-o Dpkg::Options::=--force-confnew -o Dpkg::Options::=--force-confdef"
    command = f"apt-get update && apt-get dist-upgrade {dpkg_opts} -y && apt-get autoremove -y"

    failed_result = {"Code": "non-zero", "Stderr": "error"}
    mock_run_on_unit = mocker.patch("cou.utils.juju_utils.run_on_unit", return_value=failed_result)

    with pytest.raises(ApplicationUpgradeError, match=exp_error_msg):
        await app_utils.run_on_all_units(
            units=["keystone/0", "keystone/1"], model_name="my_model", command=command
        )

    mock_run_on_unit.assert_called_once_with(
        unit_name="keystone/0",
        command=command,
        model_name="my_model",
        timeout=600,
    )


@pytest.mark.asyncio
async def test_application_run_on_all_units_error(mocker):
    side_effect = JujuError("error")
    exp_error_msg = "Cannot upgrade application: operation on keystone/0 failed."
    dpkg_opts = "-o Dpkg::Options::=--force-confnew -o Dpkg::Options::=--force-confdef"
    command = f"apt-get update && apt-get dist-upgrade {dpkg_opts} -y && apt-get autoremove -y"
    mock_run_on_unit = mocker.patch("cou.utils.juju_utils.run_on_unit", side_effect=side_effect)

    with pytest.raises(ApplicationUpgradeError, match=exp_error_msg):
        await app_utils.run_on_all_units(
            units=["keystone/0", "keystone/1"], model_name="my_model", command=command
        )

    mock_run_on_unit.assert_called_once_with(
        unit_name="keystone/0",
        command=command,
        model_name="my_model",
        timeout=600,
    )
