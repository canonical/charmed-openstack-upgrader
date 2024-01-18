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
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from juju.client._definitions import ApplicationStatus, UnitStatus
from juju.client.client import FullStatus

from cou.apps.auxiliary import OpenStackAuxiliaryApplication
from cou.apps.auxiliary_subordinate import OpenStackAuxiliarySubordinateApplication
from cou.apps.base import ApplicationUnit, OpenStackApplication
from cou.apps.core import Keystone
from cou.apps.subordinate import OpenStackSubordinateApplication
from cou.commands import CLIargs
from cou.utils.openstack import OpenStackRelease


def generate_unit(workload_version, machine):
    unit = MagicMock(spec_set=UnitStatus())
    unit.workload_version = workload_version
    unit.machine = machine
    return unit


@pytest.fixture
def status():
    mock_keystone_ussuri = MagicMock(spec_set=ApplicationStatus())
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

    mock_keystone_bionic_ussuri = MagicMock(spec_set=ApplicationStatus())
    mock_keystone_bionic_ussuri.series = "bionic"
    mock_keystone_bionic_ussuri.charm_channel = "ussuri/stable"
    mock_keystone_bionic_ussuri.charm = "ch:amd64/bionic/keystone-638"
    mock_keystone_bionic_ussuri.subordinate_to = []
    mock_keystone_bionic_ussuri.units = OrderedDict(
        [
            ("keystone/0", generate_unit("17.0.1", "0/lxd/12")),
            ("keystone/1", generate_unit("17.0.1", "1/lxd/12")),
            ("keystone/2", generate_unit("17.0.1", "2/lxd/13")),
        ]
    )

    mock_cinder_ussuri = MagicMock(spec_set=ApplicationStatus())
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

    mock_cinder_on_nova = MagicMock(spec_set=ApplicationStatus())
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

    mock_keystone_ussuri_cs = MagicMock(spec_set=ApplicationStatus())
    mock_keystone_ussuri_cs.series = "focal"
    mock_keystone_ussuri_cs.charm_channel = "stable"
    mock_keystone_ussuri_cs.charm = "cs:amd64/focal/keystone-638"
    mock_keystone_ussuri_cs.subordinate_to = []
    mock_keystone_ussuri_cs.units = OrderedDict(
        [
            ("keystone/0", generate_unit("17.0.1", "0/lxd/12")),
            ("keystone/1", generate_unit("17.0.1", "1/lxd/12")),
            ("keystone/2", generate_unit("17.0.1", "2/lxd/13")),
        ]
    )

    mock_keystone_victoria = MagicMock(spec_set=ApplicationStatus())
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

    mock_keystone_ussuri_victoria = MagicMock(spec_set=ApplicationStatus())
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

    mock_keystone_wallaby = MagicMock(spec_set=ApplicationStatus())
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

    # gnocchi on ussuri
    mock_gnocchi_ussuri = MagicMock(spec_set=ApplicationStatus())
    mock_gnocchi_ussuri.series = "focal"
    mock_gnocchi_ussuri.charm_channel = "ussuri/stable"
    mock_gnocchi_ussuri.charm = "ch:amd64/focal/gnocchi-638"
    mock_gnocchi_ussuri.subordinate_to = []
    mock_gnocchi_ussuri.units = OrderedDict(
        [
            ("gnocchi/0", generate_unit("4.3.4", "3/lxd/6")),
            ("gnocchi/1", generate_unit("4.3.4", "4/lxd/6")),
            ("gnocchi/2", generate_unit("4.3.4", "5/lxd/5")),
        ]
    )

    # gnocchi on xena
    mock_gnocchi_xena = MagicMock(spec_set=ApplicationStatus())
    mock_gnocchi_xena.series = "focal"
    mock_gnocchi_xena.charm_channel = "xena/stable"
    mock_gnocchi_xena.charm = "ch:amd64/focal/gnocchi-638"
    mock_gnocchi_xena.subordinate_to = []
    mock_gnocchi_xena.units = OrderedDict(
        [
            ("gnocchi/0", generate_unit("4.4.1", "3/lxd/6")),
            ("gnocchi/1", generate_unit("4.4.1", "4/lxd/6")),
            ("gnocchi/2", generate_unit("4.4.1", "5/lxd/5")),
        ]
    )

    # designate-bind on ussuri
    mock_designate_bind_ussuri = MagicMock(spec_set=ApplicationStatus())
    mock_designate_bind_ussuri.series = "focal"
    mock_designate_bind_ussuri.charm_channel = "ussuri/stable"
    mock_designate_bind_ussuri.charm = "ch:amd64/focal/designate-bind-737"
    mock_designate_bind_ussuri.subordinate_to = []
    mock_designate_bind_ussuri.units = OrderedDict(
        [
            ("gnocchi/0", generate_unit("9.16.1", "1/lxd/6")),
            ("gnocchi/1", generate_unit("9.16.1", "2/lxd/6")),
        ]
    )

    mock_nova_ussuri = MagicMock(spec_set=ApplicationStatus())
    mock_nova_ussuri.series = "focal"
    mock_nova_ussuri.charm_channel = "ussuri/stable"
    mock_nova_ussuri.charm = "ch:amd64/focal/nova-compute-638"
    mock_nova_ussuri.subordinate_to = []
    mock_nova_ussuri.units = OrderedDict(
        [
            ("nova-compute/0", generate_unit("21.0.0", "0")),
            ("nova-compute/1", generate_unit("21.0.0", "1")),
            ("nova-compute/2", generate_unit("21.0.0", "2")),
        ]
    )

    mock_nova_wallaby = MagicMock(spec_set=ApplicationStatus())
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

    # glance-simplestreams-sync does not have workload_version
    mock_glance_simplestreams_sync_ussuri = MagicMock(spec_set=ApplicationStatus())
    mock_glance_simplestreams_sync_ussuri.series = "focal"
    mock_glance_simplestreams_sync_ussuri.charm_channel = "ussuri/stable"
    mock_glance_simplestreams_sync_ussuri.charm = "ch:amd64/focal/glance-simplestreams-sync-78"
    mock_glance_simplestreams_sync_ussuri.subordinate_to = []
    mock_glance_simplestreams_sync_ussuri.units = OrderedDict(
        [
            ("glance-simplestreams-sync/0", generate_unit("", "4/lxd/5")),
        ]
    )

    mock_rmq = MagicMock(spec_set=ApplicationStatus())
    mock_rmq.series = "focal"
    mock_rmq.charm_channel = "3.8/stable"
    mock_rmq.charm = "ch:amd64/focal/rabbitmq-server-638"
    mock_rmq.subordinate_to = []
    mock_rmq.units = OrderedDict([("rabbitmq-server/0", generate_unit("3.8", "0/lxd/19"))])

    mock_rmq_unknown = MagicMock(spec_set=ApplicationStatus())
    mock_rmq_unknown.series = "focal"
    mock_rmq_unknown.charm_channel = "80.5/stable"
    mock_rmq_unknown.charm = "ch:amd64/focal/rabbitmq-server-638"
    mock_rmq_unknown.subordinate_to = []
    mock_rmq_unknown.units = OrderedDict(
        [("rabbitmq-server/0", generate_unit("80.5", "0/lxd/19"))]
    )

    mock_unknown_app = MagicMock(spec_set=ApplicationStatus())
    mock_unknown_app.series = "focal"
    mock_unknown_app.charm_channel = "12.5/stable"
    mock_unknown_app.charm = "ch:amd64/focal/my-app-638"
    mock_unknown_app.subordinate_to = []
    mock_unknown_app.units = OrderedDict([("my-app/0", generate_unit("12.5", "0/lxd/11"))])

    # openstack related principal application without openstack origin or source
    mock_vault = MagicMock(spec_set=ApplicationStatus())
    mock_vault.series = "focal"
    mock_vault.charm_channel = "1.7/stable"
    mock_vault.charm = "ch:amd64/focal/vault-638"
    mock_vault.subordinate_to = []
    mock_vault.units = OrderedDict([("vault/0", generate_unit("1.7", "5"))])

    # auxiliary subordinate application
    mock_mysql_router = MagicMock(spec_set=ApplicationStatus())
    mock_mysql_router.series = "focal"
    mock_mysql_router.charm_channel = "8.0/stable"
    mock_mysql_router.charm = "ch:amd64/focal/mysql-router-437"
    mock_mysql_router.subordinate_to = ["keystone"]
    mock_mysql_router.units = {}

    # OpenStack subordinate application
    mock_keystone_ldap = MagicMock(spec_set=ApplicationStatus())
    mock_keystone_ldap.series = "focal"
    mock_keystone_ldap.charm_channel = "ussuri/stable"
    mock_keystone_ldap.charm = "ch:amd64/focal/keystone-ldap-437"
    mock_keystone_ldap.subordinate_to = ["keystone"]
    mock_keystone_ldap.units = {}

    # OpenStack subordinate application cs
    mock_keystone_ldap_cs = MagicMock(spec_set=ApplicationStatus())
    mock_keystone_ldap_cs.series = "focal"
    mock_keystone_ldap_cs.charm_channel = "stable"
    mock_keystone_ldap_cs.charm = "cs:amd64/focal/keystone-ldap-437"
    mock_keystone_ldap_cs.subordinate_to = ["keystone"]
    mock_keystone_ldap_cs.units = {}

    # ceph-mon application on ussuri
    mock_ceph_mon_ussuri = MagicMock(spec_set=ApplicationStatus())
    mock_ceph_mon_ussuri.series = "focal"
    mock_ceph_mon_ussuri.charm_channel = "octopus/stable"
    mock_ceph_mon_ussuri.charm = "ch:amd64/focal/ceph-mon-177"
    mock_ceph_mon_ussuri.subordinate_to = []
    mock_ceph_mon_ussuri.units = OrderedDict([("ceph-mon/0", generate_unit("15.2.0", "6"))])

    # ceph-mon application on xena
    mock_ceph_mon_xena = MagicMock(spec_set=ApplicationStatus())
    mock_ceph_mon_xena.series = "focal"
    mock_ceph_mon_xena.charm_channel = "pacific/stable"
    mock_ceph_mon_xena.charm = "ch:amd64/focal/ceph-mon-178"
    mock_ceph_mon_xena.subordinate_to = []
    mock_ceph_mon_xena.units = OrderedDict([("ceph-mon/0", generate_unit("16.2.0", "7"))])

    # ceph-osd application on ussuri
    mock_ceph_osd_ussuri = MagicMock(spec_set=ApplicationStatus())
    mock_ceph_osd_ussuri.series = "focal"
    mock_ceph_osd_ussuri.charm_channel = "octopus/stable"
    mock_ceph_osd_ussuri.charm = "ch:amd64/focal/ceph-osd-177"
    mock_ceph_osd_ussuri.subordinate_to = []
    mock_ceph_osd_ussuri.units = OrderedDict([("ceph-osd/0", generate_unit("15.2.0", "6"))])

    # mysql-innodb-cluster application on ussuri using 8.0
    mock_mysql_innodb_cluster_ussuri = MagicMock(spec_set=ApplicationStatus())
    mock_mysql_innodb_cluster_ussuri.series = "focal"
    mock_mysql_innodb_cluster_ussuri.charm_channel = "8.0/stable"
    mock_mysql_innodb_cluster_ussuri.charm = "ch:amd64/focal/mysql-innodb-cluster-106"
    mock_mysql_innodb_cluster_ussuri.subordinate_to = []
    mock_mysql_innodb_cluster_ussuri.units = OrderedDict(
        [("ovn-central/0", generate_unit("8.0", "0/lxd/7"))]
    )

    # ovn-central application on ussuri using 22.03
    mock_ovn_central_ussuri_22 = MagicMock(spec_set=ApplicationStatus())
    mock_ovn_central_ussuri_22.series = "focal"
    mock_ovn_central_ussuri_22.charm_channel = "22.03/stable"
    mock_ovn_central_ussuri_22.charm = "ch:amd64/focal/ovn-central-178"
    mock_ovn_central_ussuri_22.subordinate_to = []
    mock_ovn_central_ussuri_22.units = OrderedDict(
        [("ovn-central/0", generate_unit("22.03.2", "0/lxd/7"))]
    )

    # ovn-central application on ussuri using 20.03
    mock_ovn_central_ussuri_20 = MagicMock(spec_set=ApplicationStatus())
    mock_ovn_central_ussuri_20.series = "focal"
    mock_ovn_central_ussuri_20.charm_channel = "20.03/stable"
    mock_ovn_central_ussuri_20.charm = "ch:amd64/focal/ovn-central-178"
    mock_ovn_central_ussuri_20.subordinate_to = []
    mock_ovn_central_ussuri_20.units = OrderedDict(
        [("ovn-central/0", generate_unit("20.03.2", "0/lxd/7"))]
    )

    # ovn-chassis application on ussuri using 22.03
    mock_ovn_chassis_ussuri_22 = MagicMock(spec_set=ApplicationStatus())
    mock_ovn_chassis_ussuri_22.series = "focal"
    mock_ovn_chassis_ussuri_22.charm_channel = "22.03/stable"
    mock_ovn_chassis_ussuri_22.charm = "ch:amd64/focal/ovn-chassis-178"
    mock_ovn_chassis_ussuri_22.workload_version = "22.03.2"
    mock_ovn_chassis_ussuri_22.subordinate_to = ["nova-compute"]
    mock_ovn_chassis_ussuri_22.units = {}

    # ovn-chassis application on ussuri using 20.03
    mock_ovn_chassis_ussuri_20 = MagicMock(spec_set=ApplicationStatus())
    mock_ovn_chassis_ussuri_20.series = "focal"
    mock_ovn_chassis_ussuri_20.charm_channel = "20.03/stable"
    mock_ovn_chassis_ussuri_20.charm = "ch:amd64/focal/ovn-chassis-178"
    mock_ovn_chassis_ussuri_20.subordinate_to = ["nova-compute"]
    mock_ovn_chassis_ussuri_20.workload_version = "20.03.2"
    mock_ovn_chassis_ussuri_20.units = {}

    # ceph-dashboard on ussuri
    mock_ceph_dashboard_ussuri = MagicMock(spec_set=ApplicationStatus())
    mock_ceph_dashboard_ussuri.series = "focal"
    mock_ceph_dashboard_ussuri.charm_channel = "octopus/stable"
    mock_ceph_dashboard_ussuri.charm = "ch:amd64/focal/ceph-dashboard-178"
    mock_ceph_dashboard_ussuri.subordinate_to = ["ceph-mon"]
    mock_ceph_dashboard_ussuri.units = {}

    # ceph-dashboard on xena
    mock_ceph_dashboard_xena = MagicMock(spec_set=ApplicationStatus())
    mock_ceph_dashboard_xena.series = "focal"
    mock_ceph_dashboard_xena.charm_channel = "pacific/stable"
    mock_ceph_dashboard_xena.charm = "ch:amd64/focal/ceph-dashboard-178"
    mock_ceph_dashboard_xena.subordinate_to = ["ceph-mon"]
    mock_ceph_dashboard_xena.units = {}

    status = {
        "keystone_ussuri": mock_keystone_ussuri,
        "keystone_victoria": mock_keystone_victoria,
        "keystone_wallaby": mock_keystone_wallaby,
        "keystone_ussuri_victoria": mock_keystone_ussuri_victoria,
        "keystone_bionic_ussuri": mock_keystone_bionic_ussuri,
        "cinder_ussuri": mock_cinder_ussuri,
        "glance_simplestreams_sync_ussuri": mock_glance_simplestreams_sync_ussuri,
        "gnocchi_ussuri": mock_gnocchi_ussuri,
        "gnocchi_xena": mock_gnocchi_xena,
        "designate_bind_ussuri": mock_designate_bind_ussuri,
        "rabbitmq_server": mock_rmq,
        "unknown_rabbitmq_server": mock_rmq_unknown,
        "keystone_ussuri_cs": mock_keystone_ussuri_cs,
        "keystone_wallaby": mock_keystone_wallaby,
        "unknown_app": mock_unknown_app,
        "mysql_router": mock_mysql_router,
        "vault": mock_vault,
        "keystone-ldap": mock_keystone_ldap,
        "keystone-ldap-cs": mock_keystone_ldap_cs,
        "nova_ussuri": mock_nova_ussuri,
        "nova_wallaby": mock_nova_wallaby,
        "ceph-mon_ussuri": mock_ceph_mon_ussuri,
        "ceph-mon_xena": mock_ceph_mon_xena,
        "ceph_osd_ussuri": mock_ceph_osd_ussuri,
        "ceph_dashboard_ussuri": mock_ceph_dashboard_ussuri,
        "ceph_dashboard_xena": mock_ceph_dashboard_xena,
        "cinder_ussuri_on_nova": mock_cinder_on_nova,
        "mysql-innodb-cluster": mock_mysql_innodb_cluster_ussuri,
        "ovn_central_ussuri_22": mock_ovn_central_ussuri_22,
        "ovn_central_ussuri_20": mock_ovn_central_ussuri_20,
        "ovn_chassis_ussuri_22": mock_ovn_chassis_ussuri_22,
        "ovn_chassis_ussuri_20": mock_ovn_chassis_ussuri_20,
    }
    return status


@pytest.fixture
def full_status(status, model):
    mock_full_status = MagicMock()
    mock_full_status.model.name = model.name
    mock_full_status.applications = OrderedDict(
        [
            ("keystone", status["keystone_ussuri"]),
            ("cinder", status["cinder_ussuri"]),
            ("rabbitmq-server", status["rabbitmq_server"]),
            ("my_app", status["unknown_app"]),
            ("nova-compute", status["nova_ussuri"]),
            ("ceph-osd", status["ceph_osd_ussuri"]),
        ]
    )
    return mock_full_status


@pytest.fixture
def units():
    units_ussuri = []
    units_wallaby = []
    units_ussuri.append(
        ApplicationUnit(
            name="keystone/0",
            os_version=OpenStackRelease("ussuri"),
            workload_version="17.0.1",
            machine="0/lxd/12",
        )
    )
    units_ussuri.append(
        ApplicationUnit(
            name="keystone/1",
            os_version=OpenStackRelease("ussuri"),
            workload_version="17.0.1",
            machine="1/lxd/12",
        )
    )
    units_ussuri.append(
        ApplicationUnit(
            name="keystone/2",
            os_version=OpenStackRelease("ussuri"),
            workload_version="17.0.1",
            machine="2/lxd/13",
        )
    )
    units_wallaby.append(
        ApplicationUnit(
            name="keystone/0",
            os_version=OpenStackRelease("wallaby"),
            workload_version="19.1.0",
            machine="0/lxd/12",
        )
    )
    units_wallaby.append(
        ApplicationUnit(
            name="keystone/1",
            os_version=OpenStackRelease("wallaby"),
            workload_version="19.1.0",
            machine="1/lxd/12",
        )
    )
    units_wallaby.append(
        ApplicationUnit(
            name="keystone/2",
            os_version=OpenStackRelease("wallaby"),
            workload_version="19.1.0",
            machine="2/lxd/13",
        )
    )
    return {"units_ussuri": units_ussuri, "units_wallaby": units_wallaby}


@pytest.fixture
def config():
    return {
        "openstack_ussuri": {
            "openstack-origin": {"value": "distro"},
            "action-managed-upgrade": {"value": True},
        },
        "openstack_wallaby": {"openstack-origin": {"value": "cloud:focal-wallaby"}},
        "openstack_xena": {"openstack-origin": {"value": "cloud:focal-xena"}},
        "auxiliary_ussuri": {"source": {"value": "distro"}},
        "auxiliary_wallaby": {"source": {"value": "cloud:focal-wallaby"}},
        "auxiliary_xena": {"source": {"value": "cloud:focal-xena"}},
    }


async def get_status():
    """Help function to load Juju status from json file."""
    current_path = Path(__file__).parent.resolve()
    with open(current_path / "jujustatus.json", "r") as file:
        status = file.read().rstrip()

    return FullStatus.from_json(status)


async def get_charm_name(value: str):
    """Help function to get charm name."""
    return value


@pytest.fixture
def model(config):
    """Define test COUModel object."""
    model_name = "test_model"
    from cou.utils import juju_utils

    model = AsyncMock(spec_set=juju_utils.COUModel)
    type(model).name = PropertyMock(return_value=model_name)
    model.run_on_unit = AsyncMock()
    model.run_action = AsyncMock()
    model.get_charm_name = AsyncMock()
    model.get_status = AsyncMock(side_effect=get_status)
    model.get_charm_name = AsyncMock(side_effect=get_charm_name)
    model.scp_from_unit = AsyncMock()
    model.get_application_config = mock_get_app_config = AsyncMock()
    mock_get_app_config.side_effect = config.get

    return model


@pytest.fixture
def apps(status, config, model):
    keystone_ussuri_status = status["keystone_ussuri"]
    keystone_wallaby_status = status["keystone_wallaby"]
    cinder_ussuri_status = status["cinder_ussuri"]
    rmq_status = status["rabbitmq_server"]
    keystone_ldap_status = status["keystone-ldap"]
    keystone_bionic_ussuri_status = status["keystone_bionic_ussuri"]

    keystone_ussuri = Keystone(
        "keystone", keystone_ussuri_status, config["openstack_ussuri"], model, "keystone"
    )
    keystone_wallaby = Keystone(
        "keystone", keystone_wallaby_status, config["openstack_wallaby"], model, "keystone"
    )
    keystone_bionic_ussuri = OpenStackApplication(
        "keystone", keystone_bionic_ussuri_status, config["openstack_ussuri"], model, "keystone"
    )
    cinder_ussuri = OpenStackApplication(
        "cinder", cinder_ussuri_status, config["openstack_ussuri"], model, "cinder"
    )
    rmq_ussuri = OpenStackAuxiliaryApplication(
        "rabbitmq-server", rmq_status, config["auxiliary_ussuri"], model, "rabbitmq-server"
    )
    rmq_wallaby = OpenStackAuxiliaryApplication(
        "rabbitmq-server", rmq_status, config["auxiliary_wallaby"], model, "rabbitmq-server"
    )
    keystone_ldap = OpenStackSubordinateApplication(
        "keystone-ldap", keystone_ldap_status, {}, model, "keystone-ldap"
    )
    keystone_mysql_router = OpenStackAuxiliarySubordinateApplication(
        "keystone-mysql-router", status["mysql_router"], {}, model, "mysql-router"
    )
    nova_ussuri = OpenStackApplication(
        "nova-compute", status["nova_ussuri"], config["openstack_ussuri"], model, "nova-compute"
    )
    return {
        "keystone_ussuri": keystone_ussuri,
        "keystone_wallaby": keystone_wallaby,
        "keystone_bionic_ussuri": keystone_bionic_ussuri,
        "cinder_ussuri": cinder_ussuri,
        "rmq_ussuri": rmq_ussuri,
        "rmq_wallaby": rmq_wallaby,
        "keystone_ldap": keystone_ldap,
        "nova_ussuri": nova_ussuri,
        "keystone_mysql_router": keystone_mysql_router,
    }


@pytest.fixture(scope="session", autouse=True)
def cou_data(tmp_path_factory):
    cou_test = tmp_path_factory.mktemp("cou_test")
    with patch("cou.utils.COU_DATA", cou_test):
        yield


@pytest.fixture
def cli_args() -> MagicMock:
    """Magic Mock of the COU CLIargs.

    :return: MagicMock of the COU CLIargs got from the cli.
    :rtype: MagicMock
    """
    # spec_set needs an instantiated class to be strict with the fields.
    return MagicMock(spec_set=CLIargs(command="plan"))()
