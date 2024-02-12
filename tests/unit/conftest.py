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
from itertools import zip_longest
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
from cou.steps.analyze import Analysis
from cou.utils.juju_utils import COUMachine
from cou.utils.openstack import OpenStackRelease

STANDARD_AZS = ["zone-1", "zone-2", "zone-3"]
HOSTNAME_PREFIX = "juju-c307f8"

KEYSTONE_UNITS = ["keystone/0", "keystone/1", "keystone/2"]
KEYSTONE_MACHINES = ["0/lxd/12", "1/lxd/12", "2/lxd/13"]
KEYSTONE_WORKLOADS = {
    "ussuri": "17.0.1",
    "victoria": "18.1.0",
    "wallaby": "19.1.0",
}

CINDER_UNITS = ["cinder/0", "cinder/1", "cinder/2"]
CINDER_MACHINES = ["0/lxd/5", "1/lxd/5", "2/lxd/5"]
CINDER_WORKLOADS = {"ussuri": "16.4.2"}

NOVA_UNITS = ["nova-compute/0", "nova-compute/1", "nova-compute/2"]
NOVA_MACHINES = ["0", "1", "2"]
NOVA_WORKLOADS = {"ussuri": "21.0.0"}

RMQ_UNITS = ["rabbitmq-server/0"]
RMQ_MACHINES = ["0/lxd/19"]
RMQ_WORKLOADS = {"3.8": "3.8"}

CEPH_MON_UNITS = ["ceph-mon/0"]
CEPH_MON_MACHINES = ["6"]

CEPH_OSD_UNITS = ["ceph-osd/0"]
CEPH_OSD_MACHINES = ["7"]

CEPH_WORKLOADS = {"octopus": "15.2.0", "pacific": "16.2.0"}

OVN_UNITS = ["ovn-central/0"]
OVN_MACHINES = ["0/lxd/7"]
OVN_WORKLOADS = {"22.03": "22.03.2", "20.03": "20.03.2"}

MYSQL_UNITS = ["mysql/0"]
MYSQL_MACHINES = ["0/lxd/7"]
MYSQL_WORKLOADS = {"8.0": "8.0"}

GLANCE_SIMPLE_UNITS = ["glance-simplestreams-sync/0"]
GLANCE_SIMPLE_MACHINES = ["4/lxd/5"]

DESIGNATE_UNITS = ["designate-bind/0", "designate-bind/1"]
DESIGNATE_MACHINES = ["1/lxd/6", "2/lxd/6"]
DESIGNATE_WORKLOADS = {"ussuri": "9.16.1"}

GNOCCHI_UNITS = ["gnocchi/0", "gnocchi/1", "gnocchi/2"]
GNOCCHI_MACHINES = ["3/lxd/6", "4/lxd/6", "5/lxd/5"]
GNOCCHI_WORKLOADS = {"ussuri": "4.3.4", "xena": "4.4.1"}

MY_APP_UNITS = ["my-app/0"]
MY_APP_MACHINES = ["0/lxd/11"]


def _generate_unit(workload_version, machine):
    unit = MagicMock(spec_set=UnitStatus())
    unit.workload_version = workload_version
    unit.machine = machine
    return unit


def _generate_units(units_machines_workloads):
    unit = MagicMock(spec_set=UnitStatus())

    ordered_units = OrderedDict()
    for unit_machine_workload in units_machines_workloads:
        unit, machine, workload = unit_machine_workload
        ordered_units[unit] = _generate_unit(workload, machine)

    return ordered_units


@pytest.fixture
def apps_machines():
    return {
        **_generate_apps_machines("keystone", KEYSTONE_MACHINES, STANDARD_AZS),
        **_generate_apps_machines("cinder", CINDER_MACHINES, STANDARD_AZS),
        **_generate_apps_machines("nova-compute", NOVA_MACHINES, STANDARD_AZS),
        **_generate_apps_machines("rmq", RMQ_MACHINES, STANDARD_AZS),
        **_generate_apps_machines("ceph-mon", CEPH_MON_MACHINES, STANDARD_AZS),
        **_generate_apps_machines("ovn-central", OVN_MACHINES, STANDARD_AZS),
        **_generate_apps_machines("mysql-innodb-cluster", MYSQL_MACHINES, STANDARD_AZS),
        **_generate_apps_machines(
            "glance-simplestreams-sync", GLANCE_SIMPLE_MACHINES, STANDARD_AZS
        ),
        **_generate_apps_machines("gnocchi", GNOCCHI_MACHINES, STANDARD_AZS),
        **_generate_apps_machines("designate-bind", DESIGNATE_MACHINES, STANDARD_AZS),
        **_generate_apps_machines("ceph-osd", CEPH_OSD_MACHINES, STANDARD_AZS),
        **_generate_apps_machines("my-app", MY_APP_MACHINES, STANDARD_AZS),
    }


def _generate_apps_machines(charm, machines, azs):
    hostnames = [f"{HOSTNAME_PREFIX}-{machine}" for machine in machines]
    machines_hostnames_azs = zip(machines, hostnames, azs)
    return {
        charm: {
            machine_id: COUMachine(machine_id=machine_id, hostname=hostname, az=az)
            for machine_id, hostname, az in machines_hostnames_azs
        }
    }


@pytest.fixture
def status():
    return {
        **generate_keystone_status(),
        **generate_cinder_status(),
        **generate_nova_status(),
        **generate_rmq_status(),
        **generate_ceph_mon_status(),
        **generate_ceph_osd_status(),
        **generate_ovn_central_status(),
        **generate_mysql_innodb_cluster_status(),
        **generate_glance_simplestreams_sync_status(),
        **generate_gnocchi_status(),
        **generate_ovn_chassis_status(),
        **generate_ceph_dashboard_status(),
        **generate_keystone_ldap_status(),
        **generate_designate_bind_status(),
        **generate_mysql_router_status(),
        **generate_my_app(),
    }


def generate_keystone_status():
    mock_keystone_focal_ussuri = _generate_status(
        "focal",
        "ussuri/stable",
        "ch:amd64/focal/keystone-638",
        [],
        KEYSTONE_UNITS,
        KEYSTONE_MACHINES,
        KEYSTONE_WORKLOADS["ussuri"],
    )

    mock_keystone_focal_victoria = _generate_status(
        "focal",
        "wallaby/stable",
        "ch:amd64/focal/keystone-638",
        [],
        KEYSTONE_UNITS,
        KEYSTONE_MACHINES,
        KEYSTONE_WORKLOADS["victoria"],
    )

    mock_keystone_focal_wallaby = _generate_status(
        "focal",
        "wallaby/stable",
        "ch:amd64/focal/keystone-638",
        [],
        KEYSTONE_UNITS,
        KEYSTONE_MACHINES,
        KEYSTONE_WORKLOADS["wallaby"],
    )

    return {
        "keystone_focal_ussuri": mock_keystone_focal_ussuri,
        "keystone_focal_victoria": mock_keystone_focal_victoria,
        "keystone_focal_wallaby": mock_keystone_focal_wallaby,
    }


def generate_cinder_status():
    mock_cinder_focal_ussuri = _generate_status(
        "focal",
        "ussuri/stable",
        "ch:amd64/focal/cinder-633",
        [],
        CINDER_UNITS,
        CINDER_MACHINES,
        CINDER_WORKLOADS["ussuri"],
    )
    return {"cinder_focal_ussuri": mock_cinder_focal_ussuri}


def generate_nova_status():
    mock_nova_focal_ussuri = _generate_status(
        "focal",
        "ussuri/stable",
        "ch:amd64/focal/nova-compute-638",
        [],
        NOVA_UNITS,
        NOVA_MACHINES,
        NOVA_WORKLOADS["ussuri"],
    )
    return {"nova_focal_ussuri": mock_nova_focal_ussuri}


def generate_rmq_status():
    mock_rmq = _generate_status(
        "focal",
        "3.8/stable",
        "ch:amd64/focal/rabbitmq-server-638",
        [],
        RMQ_UNITS,
        RMQ_MACHINES,
        RMQ_WORKLOADS["3.8"],
    )
    mock_rmq_unknown = _generate_status(
        "focal",
        "80.5/stable",
        "ch:amd64/focal/rabbitmq-server-638",
        [],
        RMQ_UNITS,
        RMQ_MACHINES,
        "80.5",
    )

    return {"rabbitmq_server": mock_rmq, "unknown_rabbitmq_server": mock_rmq_unknown}


def generate_ceph_mon_status():
    mock_ceph_mon_octopus = _generate_status(
        "focal",
        "octopus/stable",
        "ch:amd64/focal/ceph-mon-178",
        [],
        CEPH_MON_UNITS,
        CEPH_MON_MACHINES,
        CEPH_WORKLOADS["octopus"],
    )
    mock_ceph_mon_pacific = _generate_status(
        "focal",
        "pacific/stable",
        "ch:amd64/focal/ceph-mon-178",
        [],
        CEPH_MON_UNITS,
        CEPH_MON_MACHINES,
        CEPH_WORKLOADS["pacific"],
    )
    return {"ceph_mon_octopus": mock_ceph_mon_octopus, "ceph_mon_pacific": mock_ceph_mon_pacific}


def generate_ceph_osd_status():
    mock_ceph_osd_octopus = _generate_status(
        "focal",
        "octopus/stable",
        "ch:amd64/focal/ceph-osd-177",
        [],
        CEPH_OSD_UNITS,
        CEPH_OSD_MACHINES,
        CEPH_WORKLOADS["octopus"],
    )
    return {"ceph_osd_octopus": mock_ceph_osd_octopus}


def generate_ovn_central_status():
    mock_ovn_central_20 = _generate_status(
        "focal",
        "20.03/stable",
        "ch:amd64/focal/ovn-central-178",
        [],
        OVN_UNITS,
        OVN_MACHINES,
        OVN_WORKLOADS["20.03"],
    )
    mock_ovn_central_22 = _generate_status(
        "focal",
        "22.03/stable",
        "ch:amd64/focal/ovn-central-178",
        [],
        OVN_UNITS,
        OVN_MACHINES,
        OVN_WORKLOADS["22.03"],
    )
    return {"ovn_central_20": mock_ovn_central_20, "ovn_central_22": mock_ovn_central_22}


def generate_mysql_innodb_cluster_status():
    mock_mysql_innodb_cluster = _generate_status(
        "focal",
        "8.0/stable",
        "ch:amd64/focal/mysql-innodb-cluster-106",
        [],
        MYSQL_UNITS,
        MYSQL_MACHINES,
        MYSQL_WORKLOADS["8.0"],
    )
    return {"mysql_innodb_cluster": mock_mysql_innodb_cluster}


def generate_glance_simplestreams_sync_status():
    mock_glance_simplestreams_sync_focal_ussuri = _generate_status(
        "focal",
        "ussuri/stable",
        "ch:amd64/focal/glance-simplestreams-sync-78",
        [],
        GLANCE_SIMPLE_UNITS,
        GLANCE_SIMPLE_MACHINES,
        "",  # there is no workload version for glance-simplestreams-sync
    )
    return {"glance_simplestreams_sync_focal_ussuri": mock_glance_simplestreams_sync_focal_ussuri}


def generate_designate_bind_status():
    mock_designate_bind_focal_ussuri = _generate_status(
        "focal",
        "ussuri/stable",
        "ch:amd64/focal/designate-bind-737",
        [],
        DESIGNATE_UNITS,
        DESIGNATE_MACHINES,
        DESIGNATE_WORKLOADS["ussuri"],
    )
    return {
        "designate_bind_focal_ussuri": mock_designate_bind_focal_ussuri,
    }


def generate_gnocchi_status():
    mock_gnocchi_focal_ussuri = _generate_status(
        "focal",
        "ussuri/stable",
        "ch:amd64/focal/gnocchi-638",
        [],
        GNOCCHI_UNITS,
        GNOCCHI_MACHINES,
        GNOCCHI_WORKLOADS["ussuri"],
    )
    mock_gnocchi_focal_xena = _generate_status(
        "focal",
        "xena/stable",
        "ch:amd64/focal/gnocchi-638",
        [],
        GNOCCHI_UNITS,
        GNOCCHI_MACHINES,
        GNOCCHI_WORKLOADS["xena"],
    )
    return {
        "gnocchi_focal_ussuri": mock_gnocchi_focal_ussuri,
        "gnocchi_focal_xena": mock_gnocchi_focal_xena,
    }


def generate_ovn_chassis_status():
    mock_ovn_chassis_focal_22 = _generate_status(
        "focal",
        "22.03/stable",
        "ch:amd64/focal/ovn-chassis-178",
        ["nova-compute"],
        [],
        [],
        OVN_WORKLOADS["22.03"],
    )
    mock_ovn_chassis_focal_20 = _generate_status(
        "focal",
        "20.03/stable",
        "ch:amd64/focal/ovn-chassis-178",
        ["nova-compute"],
        [],
        [],
        OVN_WORKLOADS["20.03"],
    )
    return {
        "ovn_chassis_focal_20": mock_ovn_chassis_focal_20,
        "ovn_chassis_focal_22": mock_ovn_chassis_focal_22,
    }


def generate_keystone_ldap_status():
    mock_keystone_ldap_focal_ussuri = _generate_status(
        "focal",
        "ussuri/stable",
        "ch:amd64/focal/keystone-ldap-437",
        ["keystone"],
        [],
        [],
        "",
    )
    return {"keystone_ldap_focal_ussuri": mock_keystone_ldap_focal_ussuri}


def generate_ceph_dashboard_status():
    mock_ceph_dashboard_octopus = _generate_status(
        "focal",
        "octopus/stable",
        "ch:amd64/focal/ceph-dashboard-178",
        ["ceph-mon"],
        [],
        [],
        CEPH_WORKLOADS["octopus"],
    )
    mock_ceph_dashboard_pacific = _generate_status(
        "focal",
        "pacific/stable",
        "ch:amd64/focal/ceph-dashboard-178",
        ["ceph-mon"],
        [],
        [],
        CEPH_WORKLOADS["pacific"],
    )
    return {
        "ceph_dashboard_octopus": mock_ceph_dashboard_octopus,
        "ceph_dashboard_pacific": mock_ceph_dashboard_pacific,
    }


def generate_mysql_router_status():
    mock_mysql_router = _generate_status(
        "focal", "8.0/stable", "ch:amd64/focal/mysql-router-437", ["keystone"], [], [], ""
    )
    return {"mysql_router": mock_mysql_router}


def generate_my_app():
    mock_my_app = _generate_status(
        "focal",
        "12.5/stable",
        "ch:amd64/focal/my-app-638",
        [],
        MY_APP_UNITS,
        MY_APP_MACHINES,
        "12.5",
    )
    return {"my_app": mock_my_app}


def _generate_status(
    series, charm_channel, charm, subordinate_to, units, machines, workload_version
):
    app_mock = MagicMock(spec_set=ApplicationStatus())
    app_mock.series = series
    app_mock.charm_channel = charm_channel
    app_mock.charm = charm
    app_mock.subordinate_to = subordinate_to
    # subordinates get workload version from the application
    if subordinate_to:
        app_mock.workload_version = workload_version

    units_machines_workloads = zip_longest(
        units, machines, [workload_version], fillvalue=workload_version
    )
    app_mock.units = _generate_units(units_machines_workloads)
    return app_mock


@pytest.fixture
def full_status(status, model):
    mock_full_status = MagicMock()
    mock_full_status.model.name = model.name
    mock_full_status.applications = OrderedDict(
        [
            ("keystone", status["keystone_focal_ussuri"]),
            ("cinder", status["cinder_focal_ussuri"]),
            ("rabbitmq-server", status["rabbitmq_server"]),
            ("my_app", status["my_app"]),
            ("nova-compute", status["nova_focal_ussuri"]),
            ("ceph-osd", status["ceph_osd_octopus"]),
        ]
    )
    return mock_full_status


@pytest.fixture
def units(apps_machines):
    units_ussuri = []
    units_wallaby = []
    units_ussuri.append(
        ApplicationUnit(
            name="keystone/0",
            os_version=OpenStackRelease("ussuri"),
            workload_version="17.0.1",
            machine=apps_machines["keystone"]["0/lxd/12"],
        )
    )
    units_ussuri.append(
        ApplicationUnit(
            name="keystone/1",
            os_version=OpenStackRelease("ussuri"),
            workload_version="17.0.1",
            machine=apps_machines["keystone"]["1/lxd/12"],
        )
    )
    units_ussuri.append(
        ApplicationUnit(
            name="keystone/2",
            os_version=OpenStackRelease("ussuri"),
            workload_version="17.0.1",
            machine=apps_machines["keystone"]["2/lxd/13"],
        )
    )
    units_wallaby.append(
        ApplicationUnit(
            name="keystone/0",
            os_version=OpenStackRelease("wallaby"),
            workload_version="19.1.0",
            machine=apps_machines["keystone"]["0/lxd/12"],
        )
    )
    units_wallaby.append(
        ApplicationUnit(
            name="keystone/1",
            os_version=OpenStackRelease("wallaby"),
            workload_version="19.1.0",
            machine=apps_machines["keystone"]["1/lxd/12"],
        )
    )
    units_wallaby.append(
        ApplicationUnit(
            name="keystone/2",
            os_version=OpenStackRelease("wallaby"),
            workload_version="19.1.0",
            machine=apps_machines["keystone"]["2/lxd/13"],
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
def model(config, apps_machines):
    """Define test COUModel object."""
    machines = {}
    for sub_machines in apps_machines.values():
        machines = {**machines, **sub_machines}
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
    model.set_application_config = AsyncMock()
    model.get_application_config = mock_get_app_config = AsyncMock()
    mock_get_app_config.side_effect = config.get
    model.get_machines = machines

    return model


@pytest.fixture
def analysis_result(model, apps):
    """Generate a simple analysis result to be used on unit-tests."""
    return Analysis(
        model=model,
        apps_control_plane=[apps["keystone_focal_ussuri"]],
        apps_data_plane=[apps["nova_focal_ussuri"]],
    )


@pytest.fixture
def apps(status, config, model, apps_machines):
    keystone_focal_ussuri_status = status["keystone_focal_ussuri"]
    keystone_focal_wallaby_status = status["keystone_focal_wallaby"]
    cinder_focal_ussuri_status = status["cinder_focal_ussuri"]
    rmq_status = status["rabbitmq_server"]
    keystone_ldap_focal_ussuri_status = status["keystone_ldap_focal_ussuri"]

    keystone_ussuri = Keystone(
        "keystone",
        keystone_focal_ussuri_status,
        config["openstack_ussuri"],
        model,
        "keystone",
        apps_machines["keystone"],
    )
    keystone_wallaby = Keystone(
        "keystone",
        keystone_focal_wallaby_status,
        config["openstack_wallaby"],
        model,
        "keystone",
        apps_machines["keystone"],
    )
    cinder_ussuri = OpenStackApplication(
        "cinder",
        cinder_focal_ussuri_status,
        config["openstack_ussuri"],
        model,
        "cinder",
        apps_machines["cinder"],
    )
    rmq = OpenStackAuxiliaryApplication(
        "rabbitmq-server",
        rmq_status,
        config["auxiliary_ussuri"],
        model,
        "rabbitmq-server",
        apps_machines["rmq"],
    )
    rmq_wallaby = OpenStackAuxiliaryApplication(
        "rabbitmq-server",
        rmq_status,
        config["auxiliary_wallaby"],
        model,
        "rabbitmq-server",
        apps_machines["rmq"],
    )
    keystone_ldap = OpenStackSubordinateApplication(
        "keystone-ldap", keystone_ldap_focal_ussuri_status, {}, model, "keystone-ldap", {}
    )
    keystone_mysql_router = OpenStackAuxiliarySubordinateApplication(
        "keystone-mysql-router", status["mysql_router"], {}, model, "mysql-router", {}
    )
    nova_focal_ussuri = OpenStackApplication(
        "nova-compute",
        status["nova_focal_ussuri"],
        config["openstack_ussuri"],
        model,
        "nova-compute",
        apps_machines["nova-compute"],
    )

    return {
        "keystone_focal_ussuri": keystone_ussuri,
        "keystone_focal_wallaby": keystone_wallaby,
        "cinder_focal_ussuri": cinder_ussuri,
        "rmq": rmq,
        "rmq_wallaby": rmq_wallaby,
        "keystone_ldap_focal_ussuri": keystone_ldap,
        "nova_focal_ussuri": nova_focal_ussuri,
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


def generate_mock_machine(machine_id, hostname, az):
    mock_machine = MagicMock(spec_set=COUMachine(machine_id, hostname, az))
    mock_machine.machine_id = machine_id
    mock_machine.hostname = hostname
    mock_machine.az = az
    return mock_machine
