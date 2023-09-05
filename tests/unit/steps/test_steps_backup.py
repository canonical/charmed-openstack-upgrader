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

import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import mock
import pytest
from juju.client._definitions import FullStatus

from cou.exceptions import UnitNotFound
from cou.steps.backup import _check_db_relations, backup, get_database_app_unit_name


@pytest.mark.asyncio
async def test_backup():
    with patch("cou.steps.backup.logger") as log, patch("cou.steps.backup.utils") as utils, patch(
        "cou.steps.backup.get_database_app_unit_name"
    ) as database_app_name:
        database_app_name.return_value = "test"
        utils.async_run_action = AsyncMock()
        utils.async_run_on_unit = AsyncMock()
        utils.async_scp_from_unit = AsyncMock()
        utils.async_get_unit_from_name = AsyncMock()
        utils.async_get_current_model_name = AsyncMock()

        await backup(None)
        assert log.info.call_count == 5


@pytest.mark.asyncio
async def test_get_database_app_name_negative(mocker):
    get_model = mocker.patch("cou.utils.juju_utils._get_model")
    get_model.return_value = model = mock.MagicMock()
    model.applications.get.return_value = app = mock.MagicMock()
    app.charm_name.return_value = "mysql"

    get_status = mocker.patch("cou.steps.backup.utils.async_get_status")
    current_path = Path(os.path.dirname(os.path.realpath(__file__)))
    with open(Path.joinpath(current_path, "jujustatus.json"), "r") as file:
        data = file.read().rstrip()

    status = FullStatus.from_json(data)
    status.applications["mysql"].relations = {}
    get_status.return_value = status

    with pytest.raises(UnitNotFound):
        await get_database_app_unit_name()


@pytest.mark.asyncio
async def test_get_database_app_name(mocker):
    charm_name = mocker.patch("cou.utils.juju_utils.extract_charm_name")
    charm_name.return_value = "mysql-innodb-cluster"
    with patch("cou.steps.backup.utils.async_get_status") as get_status:
        current_path = Path(os.path.dirname(os.path.realpath(__file__)))
        with open(Path.joinpath(current_path, "jujustatus.json"), "r") as file:
            data = file.read().rstrip()

        status = FullStatus.from_json(data)
        get_status.return_value = status

        assert "mysql/0" == await get_database_app_unit_name()


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
