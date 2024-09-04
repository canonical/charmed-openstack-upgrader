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

from cou.utils import app_utils


@pytest.mark.asyncio
async def test_application_upgrade_packages(model):
    model.run_on_unit.return_value = {"return-code": 0, "stdout": "Success"}
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
    model.run_on_unit.return_value = {"return-code": 0, "stdout": "Success"}
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
