from unittest.mock import AsyncMock, patch

import pytest

from cou.steps.backup import _check_db_relations, backup, get_database_app


@pytest.mark.asyncio
async def test_backup():
    with patch("cou.steps.backup.logging.info") as log, patch(
        "cou.steps.backup.utils"
    ) as utils, patch("cou.steps.backup.get_database_app"):
        utils.async_run_action_on_leader = AsyncMock()
        utils.async_run_on_leader = AsyncMock()
        utils.async_scp_from_unit = AsyncMock()
        utils.async_get_lead_unit_name = AsyncMock()
        utils.async_get_unit_from_name = AsyncMock()

        await backup()
        assert log.call_count == 5


@pytest.mark.asyncio
async def test_get_database_app():
    with patch("cou.steps.backup.get_upgrade_candidates") as upgrade_candidates:
        upgrade_candidates.return_value = {
            "mysql": {
                "charm": "mysql-innodb-cluster",
                "series": "focal",
                "os": "ubuntu",
                "charm-origin": "charmhub",
                "charm-name": "mysql-innodb-cluster",
                "charm-rev": 43,
                "charm-channel": "8.0/stable",
                "charm-version": "13004be",
                "can-upgrade-to": "ch:amd64/focal/mysql-innodb-cluster-56",
                "relations": {
                    "cluster": ["mysql"],
                    "coordinator": ["mysql"],
                    "db-router": [
                        "cinder-mysql-router",
                        "glance-mysql-router",
                        "keystone-mysql-router",
                        "neutron-api-mysql-router",
                        "nova-cloud-controller-mysql-router",
                        "openstack-dashboard-mysql-router",
                        "placement-mysql-router",
                    ],
                },
            }
        }
        app = await get_database_app()
        assert app == "mysql"


@pytest.mark.asyncio
async def test_get_database_app_negative():
    with patch("cou.steps.backup.get_upgrade_candidates") as upgrade_candidates:
        upgrade_candidates.return_value = {
            "mysql": {
                "charm": "percona",
                "relations": {
                    "cluster": ["percona"],
                    "coordinator": ["percona"],
                    "db-router": [
                        "placement-mysql-router",
                    ],
                },
            }
        }
        app = await get_database_app()
        assert app is None


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
