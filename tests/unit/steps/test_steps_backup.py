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
    with patch("cou.steps.backup.utils.async_get_status") as get_status:
        retval = AsyncMock()
        retval.applications = {
            "keystone": {
                "charm": "keystone",
                "series": "focal",
                "os": "ubuntu",
                "charm-origin": "charmhub",
                "charm-name": "keystone",
                "charm-rev": 652,
                "charm-channel": "ussuri/stable",
                "exposed": False,
                "application-status": {
                    "current": "active",
                    "message": "Application Ready",
                    "since": "04 Jul 2023 18:00:52+03:00",
                },
                "relations": {
                    "cluster": ["keystone"],
                    "identity-service": [
                        "cinder",
                        "glance",
                        "neutron-api",
                        "nova-cloud-controller",
                        "placement",
                    ],
                    "shared-db": ["keystone-mysql-router"],
                },
                "units": {
                    "keystone/0": {
                        "workload-status": {
                            "current": "active",
                            "message": "Unit is ready",
                            "since": "04 Jul 2023 18:05:37+03:00",
                        },
                        "juju-status": {
                            "current": "idle",
                            "since": "06 Jul 2023 15:05:06+03:00",
                            "version": "2.9.42",
                        },
                        "leader": True,
                        "machine": "11",
                        "open-ports": ["5000/tcp"],
                        "public-address": "10.5.0.122",
                        "subordinates": {
                            "keystone-mysql-router/0": {
                                "workload-status": {
                                    "current": "active",
                                    "message": "Unit is ready",
                                    "since": "04 Jul 2023 17:53:54+03:00",
                                },
                                "juju-status": {
                                    "current": "idle",
                                    "since": "04 Jul 2023 17:53:54+03:00",
                                    "version": "2.9.42",
                                },
                                "leader": True,
                                "public-address": "10.5.0.122",
                            }
                        },
                    }
                },
                "version": "17.0.1",
                "endpoint-bindings": {
                    "": "alpha",
                    "admin": "alpha",
                    "certificates": "alpha",
                    "cluster": "alpha",
                    "domain-backend": "alpha",
                    "ha": "alpha",
                    "identity-admin": "alpha",
                    "identity-credentials": "alpha",
                    "identity-notifications": "alpha",
                    "identity-service": "alpha",
                    "internal": "alpha",
                    "keystone-fid-service-provider": "alpha",
                    "keystone-middleware": "alpha",
                    "nrpe-external-master": "alpha",
                    "public": "alpha",
                    "shared-db": "alpha",
                    "websso-trusted-dashboard": "alpha",
                },
            },
            "mysql": {
                "charm": "mysql-innodb-cluster",
                "series": "focal",
                "os": "ubuntu",
                "charm-origin": "charmhub",
                "charm-name": "mysql-innodb-cluster",
                "charm-rev": 56,
                "charm-channel": "8.0/stable",
                "charm-version": "ca6837b",
                "exposed": False,
                "application-status": {
                    "current": "active",
                    "since": "04 Jul 2023 17:52:37+03:00",
                },
                "relations": {
                    "cluster": ["mysql"],
                    "coordinator": ["mysql"],
                    "db-router": [
                        "cinder-mysql-router",
                        "glance-mysql-router",
                        "keystone-mysql-router",
                        "neutron-api-mysql-router",
                        "nova-cloud-controller-mysql-router",
                        "placement-mysql-router",
                    ],
                },
                "units": {
                    "mysql/0": {
                        "workload-status": {
                            "current": "active",
                            "since": "04 Jul 2023 17:52:37+03:00",
                        },
                        "juju-status": {
                            "current": "idle",
                            "since": "05 Jul 2023 18:54:10+03:00",
                            "version": "2.9.42",
                        },
                        "leader": True,
                        "machine": "0",
                        "public-address": "10.5.0.111",
                    }
                },
                "version": "8.0.33",
                "endpoint-bindings": {
                    "": "alpha",
                    "certificates": "alpha",
                    "cluster": "alpha",
                    "coordinator": "alpha",
                    "db-monitor": "alpha",
                    "db-router": "alpha",
                    "shared-db": "alpha",
                },
            },
        }
        get_status.return_value = retval
        app = await get_database_app()
        assert app == "mysql"


@pytest.mark.asyncio
async def test_get_database_app_negative():
    with patch("cou.steps.backup.utils.async_get_status") as get_status:
        retval = AsyncMock()
        retval.applications = {
            "keystone": {
                "charm": "keystone",
                "series": "focal",
                "os": "ubuntu",
                "charm-origin": "charmhub",
                "charm-name": "keystone",
                "charm-rev": 652,
                "charm-channel": "ussuri/stable",
                "exposed": False,
                "application-status": {
                    "current": "active",
                    "message": "Application Ready",
                    "since": "04 Jul 2023 18:00:52+03:00",
                },
                "relations": {
                    "cluster": ["keystone"],
                    "identity-service": [
                        "cinder",
                        "glance",
                        "neutron-api",
                        "nova-cloud-controller",
                        "placement",
                    ],
                    "shared-db": ["keystone-mysql-router"],
                },
                "units": {
                    "keystone/0": {
                        "workload-status": {
                            "current": "active",
                            "message": "Unit is ready",
                            "since": "04 Jul 2023 18:05:37+03:00",
                        },
                        "juju-status": {
                            "current": "idle",
                            "since": "06 Jul 2023 15:05:06+03:00",
                            "version": "2.9.42",
                        },
                        "leader": True,
                        "machine": "11",
                        "open-ports": ["5000/tcp"],
                        "public-address": "10.5.0.122",
                        "subordinates": {
                            "keystone-mysql-router/0": {
                                "workload-status": {
                                    "current": "active",
                                    "message": "Unit is ready",
                                    "since": "04 Jul 2023 17:53:54+03:00",
                                },
                                "juju-status": {
                                    "current": "idle",
                                    "since": "04 Jul 2023 17:53:54+03:00",
                                    "version": "2.9.42",
                                },
                                "leader": True,
                                "public-address": "10.5.0.122",
                            }
                        },
                    }
                },
                "version": "17.0.1",
                "endpoint-bindings": {
                    "": "alpha",
                    "admin": "alpha",
                    "certificates": "alpha",
                    "cluster": "alpha",
                    "domain-backend": "alpha",
                    "ha": "alpha",
                    "identity-admin": "alpha",
                    "identity-credentials": "alpha",
                    "identity-notifications": "alpha",
                    "identity-service": "alpha",
                    "internal": "alpha",
                    "keystone-fid-service-provider": "alpha",
                    "keystone-middleware": "alpha",
                    "nrpe-external-master": "alpha",
                    "public": "alpha",
                    "shared-db": "alpha",
                    "websso-trusted-dashboard": "alpha",
                },
            },
            "mysql": {
                "charm": "mysql-innodb-cluster",
                "series": "focal",
                "os": "ubuntu",
                "charm-origin": "charmhub",
                "charm-name": "mysql-innodb-cluster",
                "charm-rev": 56,
                "charm-channel": "8.0/stable",
                "charm-version": "ca6837b",
                "exposed": False,
                "application-status": {
                    "current": "active",
                    "since": "04 Jul 2023 17:52:37+03:00",
                },
                "relations": {
                    "cluster": ["mysql"],
                    "coordinator": ["mysql"],
                    "db-router": [
                        "cinder-mysql-router",
                        "glance-mysql-router",
                        "neutron-api-mysql-router",
                        "nova-cloud-controller-mysql-router",
                        "placement-mysql-router",
                    ],
                },
                "units": {
                    "mysql/0": {
                        "workload-status": {
                            "current": "active",
                            "since": "04 Jul 2023 17:52:37+03:00",
                        },
                        "juju-status": {
                            "current": "idle",
                            "since": "05 Jul 2023 18:54:10+03:00",
                            "version": "2.9.42",
                        },
                        "leader": True,
                        "machine": "0",
                        "public-address": "10.5.0.111",
                    }
                },
                "version": "8.0.33",
                "endpoint-bindings": {
                    "": "alpha",
                    "certificates": "alpha",
                    "cluster": "alpha",
                    "coordinator": "alpha",
                    "db-monitor": "alpha",
                    "db-router": "alpha",
                    "shared-db": "alpha",
                },
            },
        }
        get_status.return_value = retval
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
