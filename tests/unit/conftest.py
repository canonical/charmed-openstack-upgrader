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

from collections import OrderedDict
from unittest import mock

import pytest
from juju.client._definitions import ApplicationStatus, UnitStatus

from cou.apps.app import ApplicationUnit, OpenStackApplication
from cou.apps.auxiliary import OpenStackAuxiliaryApplication
from cou.apps.auxiliary_subordinate import OpenStackAuxiliarySubordinateApplication
from cou.apps.subordinate import OpenStackSubordinateApplication
from cou.utils.openstack import OpenStackRelease


def generate_unit(workload_version, machine):
    unit = mock.MagicMock(spec_set=UnitStatus())
    unit.workload_version = workload_version
    unit.machine = machine
    return unit


@pytest.fixture
def status():
    mock_keystone_ussuri = mock.MagicMock(spec_set=ApplicationStatus())
    mock_keystone_ussuri.series = "focal"
    mock_keystone_ussuri.charm_channel = "ussuri/stable"
    mock_keystone_ussuri.charm = "ch:amd64/focal/keystone-638"
    mock_keystone_ussuri.subordinate_to = []
    mock_keystone_ussuri.units = OrderedDict(
        [
            ("keystone/0", generate_unit("17.0.1", "0/lxd/12")),
            ("keystone/1", generate_unit("17.0.1", "1/lxd/12")),
            ("keystone/2", generate_unit("17.0.1", "2/lxd/13")),
        ]
    )

    mock_cinder_ussuri = mock.MagicMock(spec_set=ApplicationStatus())
    mock_cinder_ussuri.series = "focal"
    mock_cinder_ussuri.charm_channel = "ussuri/stable"
    mock_cinder_ussuri.charm = "ch:amd64/focal/cinder-633"
    mock_cinder_ussuri.subordinate_to = []
    mock_cinder_ussuri.units = OrderedDict(
        [
            ("cinder/0", generate_unit("16.4.2", "0/lxd/5")),
            ("cinder/1", generate_unit("16.4.2", "1/lxd/5")),
            ("cinder/2", generate_unit("16.4.2", "2/lxd/5")),
        ]
    )

    mock_cinder_on_nova = mock.MagicMock(spec_set=ApplicationStatus())
    mock_cinder_on_nova.series = "focal"
    mock_cinder_on_nova.charm_channel = "ussuri/stable"
    mock_cinder_on_nova.charm = "ch:amd64/focal/cinder-633"
    mock_cinder_on_nova.subordinate_to = []
    mock_cinder_on_nova.units = OrderedDict(
        [
            ("cinder/0", generate_unit("16.4.2", "0")),
            ("cinder/1", generate_unit("16.4.2", "1")),
            ("cinder/2", generate_unit("16.4.2", "2")),
        ]
    )

    mock_keystone_ussuri_cs = mock.MagicMock(spec_set=ApplicationStatus())
    mock_keystone_ussuri_cs.series = "focal"
    mock_keystone_ussuri_cs.charm_channel = "ussuri/stable"
    mock_keystone_ussuri_cs.charm = "cs:amd64/focal/keystone-638"
    mock_keystone_ussuri_cs.subordinate_to = []
    mock_keystone_ussuri_cs.units = OrderedDict(
        [
            ("keystone/0", generate_unit("17.0.1", "0/lxd/12")),
            ("keystone/1", generate_unit("17.0.1", "1/lxd/12")),
            ("keystone/2", generate_unit("17.0.1", "2/lxd/13")),
        ]
    )

    mock_keystone_victoria = mock.MagicMock(spec_set=ApplicationStatus())
    mock_keystone_victoria.series = "focal"
    mock_keystone_victoria.charm_channel = "wallaby/stable"
    mock_keystone_victoria.charm = "ch:amd64/focal/keystone-638"
    mock_keystone_victoria.subordinate_to = []
    mock_keystone_victoria.units = OrderedDict(
        [
            ("keystone/0", generate_unit("18.1.0", "0/lxd/12")),
            ("keystone/1", generate_unit("18.1.0", "1/lxd/12")),
            ("keystone/2", generate_unit("18.1.0", "2/lxd/13")),
        ]
    )

    mock_keystone_ussuri_victoria = mock.MagicMock(spec_set=ApplicationStatus())
    mock_keystone_ussuri_victoria.series = "focal"
    mock_keystone_ussuri_victoria.charm_channel = "victoria/stable"
    mock_keystone_ussuri_victoria.charm = "ch:amd64/focal/keystone-638"
    mock_keystone_ussuri_victoria.subordinate_to = []
    mock_keystone_ussuri_victoria.units = OrderedDict(
        [
            ("keystone/0", generate_unit("17.0.1", "0/lxd/12")),
            ("keystone/1", generate_unit("17.0.1", "1/lxd/12")),
            ("keystone/2", generate_unit("18.1.0", "2/lxd/13")),
        ]
    )

    mock_keystone_wallaby = mock.MagicMock(spec_set=ApplicationStatus())
    mock_keystone_wallaby.series = "focal"
    mock_keystone_wallaby.charm_channel = "wallaby/stable"
    mock_keystone_wallaby.charm = "ch:amd64/focal/keystone-638"
    mock_keystone_wallaby.subordinate_to = []
    mock_keystone_wallaby.units = OrderedDict(
        [
            ("keystone/0", generate_unit("19.1.0", "0/lxd/12")),
            ("keystone/1", generate_unit("19.1.0", "1/lxd/12")),
            ("keystone/2", generate_unit("19.1.0", "2/lxd/13")),
        ]
    )

    mock_nova_wallaby = mock.MagicMock(spec_set=ApplicationStatus())
    mock_nova_wallaby.series = "focal"
    mock_nova_wallaby.charm_channel = "wallaby/stable"
    mock_nova_wallaby.charm = "ch:amd64/focal/nova-compute-638"
    mock_nova_wallaby.subordinate_to = []
    mock_nova_wallaby.units = OrderedDict(
        [
            ("nova-compute/0", generate_unit("24.1.0", "0")),
            ("nova-compute/1", generate_unit("24.1.0", "1")),
            ("nova-compute/2", generate_unit("24.1.0", "2")),
        ]
    )

    mock_rmq = mock.MagicMock(spec_set=ApplicationStatus())
    mock_rmq.series = "focal"
    mock_rmq.charm_channel = "3.8/stable"
    mock_rmq.charm = "ch:amd64/focal/rabbitmq-server-638"
    mock_rmq.subordinate_to = []
    mock_rmq.units = OrderedDict(
        [
            (
                "rabbitmq-server/0",
                generate_unit("3.8", "0/lxd/19"),
            )
        ]
    )

    mock_rmq_unknown = mock.MagicMock(spec_set=ApplicationStatus())
    mock_rmq_unknown.charm_channel = "80.5/stable"
    mock_rmq_unknown.charm = "ch:amd64/focal/rabbitmq-server-638"
    mock_rmq_unknown.subordinate_to = []
    mock_rmq_unknown.units = OrderedDict(
        [("rabbitmq-server/0", generate_unit("80.5", "0/lxd/19"))]
    )

    mock_unknown_app = mock.MagicMock(spec_set=ApplicationStatus())
    mock_unknown_app.charm_channel = "12.5/stable"
    mock_unknown_app.charm = "ch:amd64/focal/my-app-638"
    mock_unknown_app.subordinate_to = []
    mock_unknown_app.units = OrderedDict([("my-app/0", generate_unit("12.5", "0/lxd/11"))])

    # openstack related principal application without openstack origin or source
    mock_vault = mock.MagicMock(spec_set=ApplicationStatus())
    mock_vault.series = "focal"
    mock_vault.charm_channel = "1.7/stable"
    mock_vault.charm = "ch:amd64/focal/vault-638"
    mock_vault.subordinate_to = []
    mock_vault.units = OrderedDict([("vault/0", generate_unit("1.7", "5"))])

    # auxiliary subordinate application
    mock_mysql_router = mock.MagicMock(spec_set=ApplicationStatus())
    mock_mysql_router.series = "focal"
    mock_mysql_router.charm_channel = "8.0/stable"
    mock_mysql_router.charm = "ch:amd64/focal/mysql-router-437"
    mock_mysql_router.subordinate_to = ["keystone"]
    mock_mysql_router.units = {}

    # OpenStack subordinate application
    mock_keystone_ldap = mock.MagicMock(spec_set=ApplicationStatus())
    mock_keystone_ldap.charm_channel = "ussuri/stable"
    mock_keystone_ldap.charm = "ch:amd64/focal/keystone-ldap-437"
    mock_keystone_ldap.subordinate_to = ["keystone"]
    mock_keystone_ldap.units = {}

    # OpenStack subordinate application cs
    mock_keystone_ldap_cs = mock.MagicMock(spec_set=ApplicationStatus())
    mock_keystone_ldap_cs.charm_channel = "stable"
    mock_keystone_ldap_cs.charm = "cs:amd64/focal/keystone-ldap-437"
    mock_keystone_ldap_cs.subordinate_to = ["keystone"]
    mock_keystone_ldap_cs.units = {}

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
        "keystone-ldap-cs": mock_keystone_ldap_cs,
        "nova_wallaby": mock_nova_wallaby,
        "cinder_ussuri_on_nova": mock_cinder_on_nova,
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
    units_ussuri = []
    units_wallaby = []
    units_ussuri.append(
        ApplicationUnit(
            unit="keystone/0",
            os_version=OpenStackRelease("ussuri"),
            workload_version="17.0.1",
            machine="0/lxd/12",
        )
    )
    units_ussuri.append(
        ApplicationUnit(
            unit="keystone/1",
            os_version=OpenStackRelease("ussuri"),
            workload_version="17.0.1",
            machine="1/lxd/12",
        )
    )
    units_ussuri.append(
        ApplicationUnit(
            unit="keystone/2",
            os_version=OpenStackRelease("ussuri"),
            workload_version="17.0.1",
            machine="2/lxd/13",
        )
    )
    units_wallaby.append(
        ApplicationUnit(
            unit="keystone/0",
            os_version=OpenStackRelease("wallaby"),
            workload_version="19.1.0",
            machine="0/lxd/12",
        )
    )
    units_wallaby.append(
        ApplicationUnit(
            unit="keystone/1",
            os_version=OpenStackRelease("wallaby"),
            workload_version="19.1.0",
            machine="1/lxd/12",
        )
    )
    units_wallaby.append(
        ApplicationUnit(
            unit="keystone/2",
            os_version=OpenStackRelease("wallaby"),
            workload_version="19.1.0",
            machine="2/lxd/13",
        )
    )
    return {"units_ussuri": units_ussuri, "units_wallaby": units_wallaby}


@pytest.fixture
def apps(status, config):
    keystone_ussuri_status = status["keystone_ussuri"]
    keystone_wallaby_status = status["keystone_wallaby"]
    cinder_ussuri_status = status["cinder_ussuri"]
    rmq_status = status["rabbitmq_server"]
    keystone_ldap_status = status["keystone-ldap"]
    nova_wallaby_status = status["nova_wallaby"]
    cinder_on_nova_status = status["cinder_ussuri_on_nova"]

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
    keystone_mysql_router = OpenStackAuxiliarySubordinateApplication(
        "keystone-mysql-router", status["mysql_router"], {}, "my_model", "mysql-router"
    )

    nova_wallaby = OpenStackSubordinateApplication(
        "nova-compute", nova_wallaby_status, {}, "my_model", "nova-compute"
    )

    cinder_on_nova = OpenStackSubordinateApplication(
        "cinder", cinder_on_nova_status, {}, "my_model", "cinder"
    )
    return {
        "keystone_ussuri": keystone_ussuri,
        "keystone_wallaby": keystone_wallaby,
        "cinder_ussuri": cinder_ussuri,
        "rmq_ussuri": rmq_ussuri,
        "rmq_wallaby": rmq_wallaby,
        "keystone_ldap": keystone_ldap,
        "nova_wallaby": nova_wallaby,
        "keystone_mysql_router": keystone_mysql_router,
        "cinder_on_nova": cinder_on_nova,
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
