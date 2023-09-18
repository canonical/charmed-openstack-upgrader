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

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from cou.exceptions import UnitNotFound
from cou.steps.backup import _check_db_relations, backup, get_database_app_unit_name


@pytest.mark.asyncio
@patch("cou.steps.backup.get_database_app_unit_name", new_callable=AsyncMock)
async def test_backup(database_app_name, model):
    unit = "test-unit"
    dump_file = "dump-file"
    basedir = "basedir"
    database_app_name.return_value = unit
    model.run_action.return_value = action = MagicMock()
    action.data = {"results": {"mysqldump-file": dump_file}, "parameters": {"basedir": basedir}}

    await backup(model)

    database_app_name.assert_awaited_once_with(model)
    model.run_action.assert_awaited_once_with(unit, "mysqldump")
    model.run_on_unit.assert_has_awaits(
        [
            call(unit, f"chmod o+rx {basedir}"),
            call(unit, f"chmod o-rx {basedir}"),
        ]
    )


@pytest.mark.asyncio
async def test_get_database_app_name_negative(model):
    model.get_status.return_value = {}

    with pytest.raises(UnitNotFound):
        await get_database_app_unit_name(model)


@pytest.mark.asyncio
async def test_get_database_app_name(model):
    model.get_charm_name.return_value = "mysql-innodb-cluster"
    assert "mysql/0" == await get_database_app_unit_name(model)


def test_check_db_relations():
    app_config = {
        "relations": {
            "cluster": ["mysql"],
            "coordinator": ["mysql"],
            "db-router": [
                "cinder-mysql-router",
                "glance-mysql-router",
                "neutron-api-mysql-router",
                "nova-cloud-controller-mysql-router",
                "openstack-dashboard-mysql-router",
                "placement-mysql-router",
            ],
        }
    }
    result = _check_db_relations(app_config)
    assert not result
