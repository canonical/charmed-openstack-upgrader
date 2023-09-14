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

from collections import OrderedDict, defaultdict

import mock
import pytest

from cou.apps.app import OpenStackApplication
from cou.apps.auxiliary import OpenStackAuxiliaryApplication
from cou.apps.subordinate import OpenStackSubordinateApplication


@pytest.fixture
def status():
    mock_keystone_ussuri = mock.MagicMock()
    mock_keystone_ussuri.series = "focal"
    mock_keystone_ussuri.charm_channel = "ussuri/stable"
    mock_keystone_ussuri.charm = "ch:amd64/focal/keystone-638"
    mock_keystone_ussuri.subordinate_to = []
    mock_units_keystone_ussuri = mock.MagicMock()
    mock_units_keystone_ussuri.workload_version = "17.0.1"
    mock_keystone_ussuri.units = OrderedDict(
        [
            ("keystone/0", mock_units_keystone_ussuri),
            ("keystone/1", mock_units_keystone_ussuri),
            ("keystone/2", mock_units_keystone_ussuri),
        ]
    )

    mock_cinder_ussuri = mock.MagicMock()
    mock_cinder_ussuri.series = "focal"
    mock_cinder_ussuri.charm_channel = "ussuri/stable"
    mock_cinder_ussuri.charm = "ch:amd64/focal/cinder-633"
    mock_cinder_ussuri.subordinate_to = []
    mock_units_cinder_ussuri = mock.MagicMock()
    mock_units_cinder_ussuri.workload_version = "16.4.2"
    mock_cinder_ussuri.units = OrderedDict(
        [
            ("cinder/0", mock_units_cinder_ussuri),
            ("cinder/1", mock_units_cinder_ussuri),
            ("cinder/2", mock_units_cinder_ussuri),
        ]
    )

    mock_keystone_ussuri_cs = mock.MagicMock()
    mock_keystone_ussuri_cs.series = "focal"
    mock_keystone_ussuri_cs.charm_channel = "ussuri/stable"
    mock_keystone_ussuri_cs.charm = "cs:amd64/focal/keystone-638"
    mock_keystone_ussuri_cs.subordinate_to = []
    mock_keystone_ussuri_cs.units = OrderedDict(
        [
            ("keystone/0", mock_units_keystone_ussuri),
            ("keystone/1", mock_units_keystone_ussuri),
            ("keystone/2", mock_units_keystone_ussuri),
        ]
    )

    mock_keystone_victoria = mock.MagicMock()
    mock_keystone_victoria.series = "focal"
    mock_keystone_victoria.charm_channel = "wallaby/stable"
    mock_keystone_victoria.charm = "ch:amd64/focal/keystone-638"
    mock_keystone_victoria.subordinate_to = []
    mock_units_keystone_victoria = mock.MagicMock()
    mock_units_keystone_victoria.workload_version = "18.1.0"
    mock_keystone_victoria.units = OrderedDict(
        [
            ("keystone/0", mock_units_keystone_victoria),
            ("keystone/1", mock_units_keystone_victoria),
            ("keystone/2", mock_units_keystone_victoria),
        ]
    )

    mock_keystone_ussuri_victoria = mock.MagicMock()
    mock_keystone_ussuri_victoria.series = "focal"
    mock_keystone_ussuri_victoria.charm_channel = "victoria/stable"
    mock_keystone_ussuri_victoria.charm = "ch:amd64/focal/keystone-638"
    mock_keystone_ussuri_victoria.subordinate_to = []
    mock_keystone_ussuri_victoria.units = OrderedDict(
        [
            ("keystone/0", mock_units_keystone_ussuri),
            ("keystone/1", mock_units_keystone_ussuri),
            ("keystone/2", mock_units_keystone_victoria),
        ]
    )

    mock_keystone_wallaby = mock.MagicMock()
    mock_keystone_wallaby.series = "focal"
    mock_keystone_wallaby.charm_channel = "wallaby/stable"
    mock_keystone_wallaby.charm = "ch:amd64/focal/keystone-638"
    mock_keystone_wallaby.subordinate_to = []
    mock_units_keystone_wallaby = mock.MagicMock()
    mock_units_keystone_wallaby.workload_version = "19.1.0"
    mock_keystone_wallaby.units = OrderedDict(
        [
            ("keystone/0", mock_units_keystone_wallaby),
            ("keystone/1", mock_units_keystone_wallaby),
            ("keystone/2", mock_units_keystone_wallaby),
        ]
    )

    mock_rmq = mock.MagicMock()
    mock_rmq.series = "focal"
    mock_units_rmq = mock.MagicMock()
    mock_rmq.charm_channel = "3.8/stable"
    mock_units_rmq.workload_version = "3.8"
    mock_rmq.charm = "ch:amd64/focal/rabbitmq-server-638"
    mock_rmq.subordinate_to = []
    mock_rmq.units = OrderedDict([("rabbitmq-server/0", mock_units_rmq)])

    mock_rmq_unknown = mock.MagicMock()
    mock_units_unknown_rmq = mock.MagicMock()
    mock_rmq_unknown.charm_channel = "80.5/stable"
    mock_units_unknown_rmq.workload_version = "80.5"
    mock_rmq_unknown.charm = "ch:amd64/focal/rabbitmq-server-638"
    mock_rmq_unknown.subordinate_to = []
    mock_rmq_unknown.units = OrderedDict([("rabbitmq-server/0", mock_units_unknown_rmq)])

    mock_unknown_app = mock.MagicMock()
    mock_units_unknown_app = mock.MagicMock()
    mock_unknown_app.charm_channel = "12.5/stable"
    mock_units_unknown_app.workload_version = "12.5"
    mock_unknown_app.charm = "ch:amd64/focal/my-app-638"
    mock_unknown_app.subordinate_to = []
    mock_unknown_app.units = OrderedDict([("my-app/0", mock_units_unknown_app)])

    # openstack related principal application without openstack origin or source
    mock_vault = mock.MagicMock()
    mock_vault.series = "focal"
    mock_units_vault = mock.MagicMock()
    mock_vault.charm_channel = "1.7/stable"
    mock_units_vault.workload_version = "1.7"
    mock_vault.charm = "ch:amd64/focal/vault-638"
    mock_vault.subordinate_to = []
    mock_vault.units = OrderedDict([("vault/0", mock_units_vault)])

    # subordinate application
    mock_mysql_router = mock.MagicMock()
    mock_mysql_router.charm_channel = "8.0/stable"
    mock_mysql_router.charm = "ch:amd64/focal/mysql-router-437"
    mock_mysql_router.subordinate_to = ["keystone"]
    mock_mysql_router.units = {}

    # OpenStack subordinate application
    mock_keystone_ldap = mock.MagicMock()
    mock_keystone_ldap.charm_channel = "ussuri/stable"
    mock_keystone_ldap.charm = "ch:amd64/focal/keystone-ldap-437"
    mock_keystone_ldap.subordinate_to = ["keystone"]
    mock_keystone_ldap.units = {}

    status = {
        "keystone_ussuri": mock_keystone_ussuri,
        "keystone_victoria": mock_keystone_victoria,
        "keystone_wallaby": mock_keystone_wallaby,
        "keystone_ussuri_victoria": mock_keystone_ussuri_victoria,
        "cinder_ussuri": mock_cinder_ussuri,
        "rabbitmq_server": mock_rmq,
        "unknown_rabbitmq_server": mock_rmq_unknown,
        "keystone_ussuri_cs": mock_keystone_ussuri_cs,
        "keystone_wallaby": mock_keystone_wallaby,
        "unknown_app": mock_unknown_app,
        "mysql_router": mock_mysql_router,
        "vault": mock_vault,
        "keystone-ldap": mock_keystone_ldap,
    }
    return status


@pytest.fixture
def full_status(status):
    mock_full_status = mock.MagicMock()
    mock_full_status.model.name = "my_model"
    mock_full_status.applications = OrderedDict(
        [
            ("keystone", status["keystone_ussuri"]),
            ("cinder", status["cinder_ussuri"]),
            ("rabbitmq-server", status["rabbitmq_server"]),
            ("my_app", status["unknown_app"]),
        ]
    )
    return mock_full_status


@pytest.fixture
def units():
    units_ussuri = defaultdict(dict)
    units_wallaby = defaultdict(dict)
    for unit in ["keystone/0", "keystone/1", "keystone/2"]:
        units_ussuri[unit]["os_version"] = "ussuri"
        units_ussuri[unit]["workload_version"] = "17.0.1"
        units_wallaby[unit]["os_version"] = "wallaby"
        units_wallaby[unit]["workload_version"] = "19.1.0"
    return {"units_ussuri": units_ussuri, "units_wallaby": units_wallaby}


@pytest.fixture
def apps(status, config):
    keystone_ussuri_status = status["keystone_ussuri"]
    keystone_wallaby_status = status["keystone_wallaby"]
    cinder_ussuri_status = status["cinder_ussuri"]
    rmq_status = status["rabbitmq_server"]
    keystone_ldap_status = status["keystone-ldap"]

    keystone_ussuri = OpenStackApplication(
        "keystone", keystone_ussuri_status, config["openstack_ussuri"], "my_model", "keystone"
    )
    keystone_wallaby = OpenStackApplication(
        "keystone", keystone_wallaby_status, config["openstack_wallaby"], "my_model", "keystone"
    )
    cinder_ussuri = OpenStackApplication(
        "cinder", cinder_ussuri_status, config["openstack_ussuri"], "my_model", "cinder"
    )
    rmq_ussuri = OpenStackAuxiliaryApplication(
        "rabbitmq-server", rmq_status, config["auxiliary_ussuri"], "my_model", "rabbitmq-server"
    )
    rmq_wallaby = OpenStackAuxiliaryApplication(
        "rabbitmq-server", rmq_status, config["auxiliary_wallaby"], "my_model", "rabbitmq-server"
    )
    keystone_ldap = OpenStackSubordinateApplication(
        "keystone-ldap", keystone_ldap_status, {}, "my_model", "keystone-ldap"
    )

    return {
        "keystone_ussuri": keystone_ussuri,
        "keystone_wallaby": keystone_wallaby,
        "cinder_ussuri": cinder_ussuri,
        "rmq_ussuri": rmq_ussuri,
        "rmq_wallaby": rmq_wallaby,
        "keystone_ldap": keystone_ldap,
    }


@pytest.fixture
def config():
    return {
        "openstack_ussuri": {
            "openstack-origin": {"value": "distro"},
            "action-managed-upgrade": {"value": True},
        },
        "openstack_wallaby": {"openstack-origin": {"value": "cloud:focal-wallaby"}},
        "auxiliary_ussuri": {"source": {"value": "distro"}},
        "auxiliary_wallaby": {"source": {"value": "cloud:focal-wallaby"}},
    }
