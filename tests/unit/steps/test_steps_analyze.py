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
from textwrap import dedent
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cou.apps.auxiliary import RabbitMQServer
from cou.apps.base import OpenStackApplication
from cou.apps.core import Keystone
from cou.steps import analyze
from cou.steps.analyze import Analysis
from cou.utils.juju_utils import COUApplication, COUMachine, COUUnit
from cou.utils.openstack import OpenStackRelease
from tests.unit.utils import generate_cou_machine


def test_analysis_dump(model):
    """Test analysis dump."""
    expected_result = dedent(
        """\
        Control Plane:
        keystone:
          model_name: test_model
          can_upgrade_to: ussuri/stable
          charm: keystone
          channel: ussuri/stable
          config:
            source:
              value: distro
          origin: ch
          series: focal
          subordinate_to: []
          workload_version: 17.0.1
          units:
            keystone/0:
              name: keystone/0
              machine: '0'
              workload_version: 17.0.1
              os_version: ussuri
            keystone/1:
              name: keystone/1
              machine: '1'
              workload_version: 17.0.1
              os_version: ussuri
            keystone/2:
              name: keystone/2
              machine: '2'
              workload_version: 17.0.1
              os_version: ussuri
          machines:
            '0':
              id: '0'
              apps: !!python/tuple []
              az: null
            '1':
              id: '1'
              apps: !!python/tuple []
              az: null
            '2':
              id: '2'
              apps: !!python/tuple []
              az: null

        cinder:
          model_name: test_model
          can_upgrade_to: ussuri/stable
          charm: cinder
          channel: ussuri/stable
          config:
            source:
              value: distro
          origin: ch
          series: focal
          subordinate_to: []
          workload_version: 16.4.2
          units:
            cinder/0:
              name: cinder/0
              machine: '0'
              workload_version: 16.4.2
              os_version: ussuri
            cinder/1:
              name: cinder/1
              machine: '1'
              workload_version: 16.4.2
              os_version: ussuri
            cinder/2:
              name: cinder/2
              machine: '2'
              workload_version: 16.4.2
              os_version: ussuri
          machines:
            '0':
              id: '0'
              apps: !!python/tuple []
              az: null
            '1':
              id: '1'
              apps: !!python/tuple []
              az: null
            '2':
              id: '2'
              apps: !!python/tuple []
              az: null

        rabbitmq-server:
          model_name: test_model
          can_upgrade_to: 3.8/stable
          charm: rabbitmq-server
          channel: 3.8/stable
          config:
            source:
              value: distro
          origin: ch
          series: focal
          subordinate_to: []
          workload_version: '3.8'
          units:
            rabbitmq-server/0:
              name: rabbitmq-server/0
              machine: '0'
              workload_version: '3.8'
              os_version: yoga
          machines:
            '0':
              id: '0'
              apps: !!python/tuple []
              az: null
        Data Plane:

        Current minimum OS release in the cloud: ussuri

        Current minimum Ubuntu series in the cloud: focal
        """
    )
    machines = {f"{i}": generate_cou_machine(f"{i}") for i in range(3)}
    keystone = Keystone(
        name="keystone",
        can_upgrade_to="ussuri/stable",
        charm="keystone",
        channel="ussuri/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"keystone/{unit}": COUUnit(
                name=f"keystone/{unit}", workload_version="17.0.1", machine=machines[f"{unit}"]
            )
            for unit in range(3)
        },
        workload_version="17.0.1",
    )
    rabbitmq_server = RabbitMQServer(
        name="rabbitmq-server",
        can_upgrade_to="3.8/stable",
        charm="rabbitmq-server",
        channel="3.8/stable",
        config={"source": {"value": "distro"}},
        machines={"0": machines["0"]},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "rabbitmq-server/0": COUUnit(
                name="rabbitmq-server/0",
                workload_version="3.8",
                machine=machines["0"],
            )
        },
        workload_version="3.8",
    )
    cinder = OpenStackApplication(
        name="cinder",
        can_upgrade_to="ussuri/stable",
        charm="cinder",
        channel="ussuri/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"cinder/{unit}": COUUnit(
                name=f"cinder/{unit}",
                workload_version="16.4.2",
                machine=machines[f"{unit}"],
            )
            for unit in range(3)
        },
        workload_version="16.4.2",
    )
    result = analyze.Analysis(
        model=model,
        apps_control_plane=[keystone, cinder, rabbitmq_server],
        apps_data_plane=[],
    )

    assert str(result) == expected_result


@pytest.mark.asyncio
@patch("cou.apps.factory.AppFactory.create")
async def test_populate_model(mock_create, model):
    """Test Analysis population of model."""

    def mock_app(name: str) -> MagicMock:
        app = MagicMock(spec_set=COUApplication)()
        app.name = name
        app.charm = name
        return app

    juju_apps = ["keystone", "cinder", "rabbitmq-server", "my-app", "ceph-osd", "nova-compute"]
    model.get_applications.return_value = {app: mock_app(app) for app in juju_apps}
    # simulate app factory returning None for custom app
    mock_create.side_effect = lambda app: None if app.name == "my-app" else app

    apps = await Analysis._populate(model)
    assert len(apps) == 5
    # apps are on the UPGRADE_ORDER sequence
    assert [app.charm for app in apps] == [
        "rabbitmq-server",
        "keystone",
        "cinder",
        "nova-compute",
        "ceph-osd",
    ]


@pytest.mark.asyncio
@patch.object(analyze.Analysis, "_populate", new_callable=AsyncMock)
@patch.object(
    analyze.Analysis,
    "_split_apps",
)
async def test_analysis_create(mock_split_apps, mock_populate, model):
    """Test analysis object creation."""
    machines = {"0": MagicMock(spec_set=COUMachine)}
    keystone = Keystone(
        name="keystone",
        can_upgrade_to="ussuri/stable",
        charm="keystone",
        channel="ussuri/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "keystone/0": COUUnit(
                name="keystone/0",
                workload_version="17.1.0",
                machine=machines["0"],
            )
        },
        workload_version="17.1.0",
    )
    rabbitmq_server = RabbitMQServer(
        name="rabbitmq-server",
        can_upgrade_to="3.8/stable",
        charm="rabbitmq-server",
        channel="3.8/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "rabbitmq-server/0": COUUnit(
                name="rabbitmq-server/0",
                workload_version="3.8",
                machine=machines["0"],
            )
        },
        workload_version="3.8",
    )
    cinder = OpenStackApplication(
        name="cinder",
        can_upgrade_to="ussuri/stable",
        charm="cinder",
        channel="ussuri/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "cinder/0": COUUnit(
                name="cinder/0",
                workload_version="16.4.2",
                machine=machines["0"],
            )
        },
        workload_version="16.4.2",
    )
    exp_apps = [keystone, rabbitmq_server, cinder]
    mock_populate.return_value = exp_apps
    mock_split_apps.return_value = exp_apps, []

    result = await Analysis.create(model=model)

    assert result.model == model
    assert result.apps_control_plane == exp_apps
    assert result.apps_data_plane == []
    assert result.min_os_version_control_plane == OpenStackRelease("ussuri")
    assert result.min_os_version_data_plane is None
    assert result.current_cloud_os_release == "ussuri"
    assert result.current_cloud_series == "focal"


@pytest.mark.asyncio
async def test_analysis_detect_current_cloud_os_release_different_releases(model):
    machines = {"0": MagicMock(spec_set=COUMachine)}
    keystone = Keystone(
        name="keystone",
        can_upgrade_to="wallaby/stable",
        charm="keystone",
        channel="wallaby/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "keystone/0": COUUnit(
                name="keystone/0",
                workload_version="19.1.0",
                machine=machines["0"],
            )
        },
        workload_version="19.1.0",
    )
    rabbitmq_server = RabbitMQServer(
        name="rabbitmq-server",
        can_upgrade_to="3.8/stable",
        charm="rabbitmq-server",
        channel="3.8/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "rabbitmq-server/0": COUUnit(
                name="rabbitmq-server/0",
                workload_version="3.8",
                machine=machines["0"],
            )
        },
        workload_version="3.8",
    )
    cinder = OpenStackApplication(
        name="cinder",
        can_upgrade_to="ussuri/stable",
        charm="cinder",
        channel="ussuri/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "cinder/0": COUUnit(
                name="cinder/0",
                workload_version="16.4.2",
                machine=machines["0"],
            )
        },
        workload_version="16.4.2",
    )
    result = analyze.Analysis(
        model=model,
        apps_control_plane=[rabbitmq_server, keystone, cinder],
        apps_data_plane=[],
    )

    # current_cloud_os_release takes the minimum OpenStack version
    assert result.current_cloud_os_release == "ussuri"


@pytest.mark.asyncio
async def test_analysis_detect_current_cloud_series_different_series(model):
    """Check current_cloud_series getting lowest series in apps."""
    machines = {"0": MagicMock(spec_set=COUMachine)}
    keystone = Keystone(
        name="keystone",
        can_upgrade_to="ussuri/stable",
        charm="keystone",
        channel="ussuri/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "keystone/0": COUUnit(
                name="keystone/0",
                workload_version="17.1.0",
                machine=machines["0"],
            )
        },
        workload_version="17.1.0",
    )
    rabbitmq_server = RabbitMQServer(
        name="rabbitmq-server",
        can_upgrade_to="3.8/stable",
        charm="rabbitmq-server",
        channel="3.8/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "rabbitmq-server/0": COUUnit(
                name="rabbitmq-server/0",
                workload_version="3.8",
                machine=machines["0"],
            )
        },
        workload_version="3.8",
    )
    cinder = OpenStackApplication(
        name="cinder",
        can_upgrade_to="ussuri/stable",
        charm="cinder",
        channel="ussuri/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="bionic",  # change cinder to Bionic series
        subordinate_to=[],
        units={
            "cinder/0": COUUnit(
                name="cinder/0",
                workload_version="16.4.2",
                machine=machines["0"],
            )
        },
        workload_version="16.4.2",
    )
    result = analyze.Analysis(
        model=model,
        apps_control_plane=[rabbitmq_server, keystone, cinder],
        apps_data_plane=[],
    )

    assert result.current_cloud_os_release == "ussuri"
    assert result.current_cloud_series == "bionic"


def _app(name, units):
    app = MagicMock(spec_set=OpenStackApplication).return_value
    app.charm = name
    app.units = units
    return app


def _unit(machine_id):
    unit = MagicMock(spec_set=COUUnit).return_value
    unit.machine = COUMachine(machine_id, "zone-1")
    return unit


@pytest.mark.parametrize(
    "exp_control_plane, exp_data_plane",
    [
        (
            [_app("keystone", {"0": _unit("0"), "1": _unit("1"), "2": _unit("2")})],
            [
                _app("ceph-osd", {"3": _unit("3"), "4": _unit("4"), "5": _unit("5")}),
                _app("swift-proxy", {"6": _unit("6")}),
                _app("swift-storage", {"7": _unit("7")}),
            ],
        ),
        (
            [],
            [
                _app("nova-compute", {"0": _unit("0"), "1": _unit("1"), "2": _unit("2")}),
                _app("keystone", {"0": _unit("0"), "1": _unit("1"), "2": _unit("2")}),
                _app("ceph-osd", {"3": _unit("3"), "4": _unit("4"), "5": _unit("5")}),
                _app("swift-proxy", {"6": _unit("6")}),
                _app("swift-storage", {"7": _unit("7")}),
            ],
        ),
        (
            [_app("keystone", {"6": _unit("6"), "7": _unit("7"), "8": _unit("8")})],
            [
                _app("nova-compute", {"0": _unit("0"), "1": _unit("1"), "2": _unit("2")}),
                _app("ceph-osd", {"3": _unit("3"), "4": _unit("4"), "5": _unit("5")}),
                _app("swift-proxy", {"9": _unit("9")}),
                _app("swift-storage", {"10": _unit("10")}),
            ],
        ),
    ],
)
def test_split_apps(exp_control_plane, exp_data_plane):
    all_apps = exp_control_plane + exp_data_plane
    control_plane, data_plane = Analysis._split_apps(all_apps)
    assert exp_control_plane == control_plane
    assert exp_data_plane == data_plane


@pytest.mark.asyncio
async def test_analysis_machines(model):
    """Test splitting of dataplane and control plane machines."""
    machines = {
        "0": MagicMock(spec_set=COUMachine),
        "1": MagicMock(spec_set=COUMachine),
        "2": MagicMock(spec_set=COUMachine),
        "3": MagicMock(spec_set=COUMachine),
        "4": MagicMock(spec_set=COUMachine),
        "5": MagicMock(spec_set=COUMachine),
    }
    keystone = Keystone(
        name="keystone",
        can_upgrade_to="ussuri/stable",
        charm="keystone",
        channel="ussuri/stable",
        config={"source": {"value": "distro"}},
        machines={"3": machines["3"]},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "keystone/0": COUUnit(
                name="keystone/0",
                workload_version="17.1.0",
                machine=machines["3"],
            )
        },
        workload_version="17.1.0",
    )
    rabbitmq_server = RabbitMQServer(
        name="rabbitmq-server",
        can_upgrade_to="3.8/stable",
        charm="rabbitmq-server",
        channel="3.8/stable",
        config={"source": {"value": "distro"}},
        machines={"4": machines["4"]},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "rabbitmq-server/0": COUUnit(
                name="rabbitmq-server/0",
                workload_version="3.8",
                machine=machines["4"],
            )
        },
        workload_version="3.8",
    )
    cinder = OpenStackApplication(
        name="cinder",
        can_upgrade_to="ussuri/stable",
        charm="cinder",
        channel="ussuri/stable",
        config={"source": {"value": "distro"}},
        machines={"5": machines["5"]},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "cinder/0": COUUnit(
                name="cinder/0",
                workload_version="16.4.2",
                machine=machines["5"],
            )
        },
        workload_version="16.4.2",
    )
    nova_compute = OpenStackApplication(
        name="nova-compute",
        can_upgrade_to="ussuri/stable",
        charm="nova-compute",
        channel="ussuri/stable",
        config={"source": {"value": "distro"}},
        machines={f"{i}": machines[f"{i}"] for i in range(3)},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"nova-compute/{unit}": COUUnit(
                name=f"nova-compute/{unit}",
                workload_version="21.0.0",
                machine=machines[f"{unit}"],
            )
            for unit in range(3)
        },
        workload_version="21.0.0",
    )

    result = analyze.Analysis(
        model=model,
        apps_control_plane=[rabbitmq_server, keystone, cinder],
        apps_data_plane=[nova_compute],
    )

    expected_control_plane_machines = {f"{i}": machines[f"{i}"] for i in range(3, 6)}  # 3, 4, 5
    expected_data_plane_machines = {f"{i}": machines[f"{i}"] for i in range(3)}  # 0, 1, 2

    assert result.control_plane_machines == expected_control_plane_machines
    assert result.data_plane_machines == expected_data_plane_machines
    assert result.machines == {**expected_control_plane_machines, **expected_data_plane_machines}
