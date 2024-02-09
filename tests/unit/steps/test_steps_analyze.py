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
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cou.apps.base import ApplicationUnit, OpenStackApplication
from cou.steps import analyze
from cou.steps.analyze import Analysis
from cou.utils.juju_utils import COUMachine


def test_analysis_dump(apps, model):
    """Test analysis dump."""
    expected_result = (
        "Control Plane:\n"
        "keystone:\n"
        "  model_name: test_model\n"
        "  charm: keystone\n"
        "  charm_origin: ch\n"
        "  os_origin: distro\n"
        "  channel: ussuri/stable\n"
        "  units:\n"
        "    keystone/0:\n"
        "      workload_version: 17.0.1\n"
        "      os_version: ussuri\n"
        "    keystone/1:\n"
        "      workload_version: 17.0.1\n"
        "      os_version: ussuri\n"
        "    keystone/2:\n"
        "      workload_version: 17.0.1\n"
        "      os_version: ussuri\n"
        "\n"
        "cinder:\n"
        "  model_name: test_model\n"
        "  charm: cinder\n"
        "  charm_origin: ch\n"
        "  os_origin: distro\n"
        "  channel: ussuri/stable\n"
        "  units:\n"
        "    cinder/0:\n"
        "      workload_version: 16.4.2\n"
        "      os_version: ussuri\n"
        "    cinder/1:\n"
        "      workload_version: 16.4.2\n"
        "      os_version: ussuri\n"
        "    cinder/2:\n"
        "      workload_version: 16.4.2\n"
        "      os_version: ussuri\n"
        "\n"
        "rabbitmq-server:\n"
        "  model_name: test_model\n"
        "  charm: rabbitmq-server\n"
        "  charm_origin: ch\n"
        "  os_origin: distro\n"
        "  channel: 3.8/stable\n"
        "  units:\n"
        "    rabbitmq-server/0:\n"
        "      workload_version: '3.8'\n"
        "      os_version: yoga\n"
        "Data Plane:\n"
        "\nCurrent minimum OS release in the cloud: ussuri\n"
        "\nCurrent minimum Ubuntu series in the cloud: focal\n"
    )
    result = analyze.Analysis(
        model=model,
        apps_control_plane=[
            apps["keystone_focal_ussuri"],
            apps["cinder_focal_ussuri"],
            apps["rmq"],
        ],
        apps_data_plane=[],
    )
    assert str(result) == expected_result


@pytest.mark.asyncio
async def test_populate_model(full_status, config, model, apps_machines):
    model.get_status = AsyncMock(return_value=full_status)
    model.get_application_config = AsyncMock(return_value=config["openstack_ussuri"])

    machines = {}
    for sub_dict in apps_machines.values():
        machines.update(sub_dict)

    model.get_machines = AsyncMock(return_value=machines)

    # Initially, 6 applications are in the status: keystone, cinder, rabbitmq-server, my-app,
    # ceph-osd and nova-compute. my-app it's not on the lookup table, so won't be instantiated.
    assert len(full_status.applications) == 6
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
async def test_analysis_create(mock_populate, apps, model):
    """Test analysis object."""
    exp_apps = [apps["keystone_focal_ussuri"], apps["cinder_focal_ussuri"], apps["rmq"]]
    expected_result = analyze.Analysis(
        model=model, apps_control_plane=exp_apps, apps_data_plane=[]
    )
    mock_populate.return_value = exp_apps

    result = await Analysis.create(model=model)

    assert result == expected_result


@pytest.mark.asyncio
async def test_analysis_detect_current_cloud_os_release_different_releases(apps, model):
    result = analyze.Analysis(
        model=model,
        apps_control_plane=[
            apps["rmq"],
            apps["keystone_focal_wallaby"],
            apps["cinder_focal_ussuri"],
        ],
        apps_data_plane=[],
    )

    # current_cloud_os_release takes the minimum OpenStack version
    assert result.current_cloud_os_release == "ussuri"


@pytest.mark.asyncio
async def test_analysis_detect_current_cloud_os_release_same_release(apps, model):
    result = analyze.Analysis(
        model=model,
        apps_control_plane=[apps["cinder_focal_ussuri"], apps["keystone_focal_ussuri"]],
        apps_data_plane=[],
    )

    # current_cloud_os_release takes the minimum OpenStack version
    assert result.current_cloud_os_release == "ussuri"


@pytest.mark.asyncio
async def test_analysis_detect_current_cloud_series_same_series(apps, model):
    result = analyze.Analysis(
        model=model,
        apps_control_plane=[
            apps["rmq"],
            apps["keystone_focal_wallaby"],
            apps["cinder_focal_ussuri"],
        ],
        apps_data_plane=[],
    )

    # current_cloud_series takes the minimum Ubuntu series
    assert result.current_cloud_series == "focal"


@pytest.mark.asyncio
async def test_analysis_detect_current_cloud_series_different_series(apps, model):
    # change keystone to bionic
    keystone_bionic_ussuri = apps["keystone_focal_ussuri"]
    keystone_bionic_ussuri.status.series = "bionic"

    result = analyze.Analysis(
        model=model,
        apps_control_plane=[apps["cinder_focal_ussuri"], keystone_bionic_ussuri],
        apps_data_plane=[],
    )

    # current_cloud_series takes the minimum Ubuntu series
    assert result.current_cloud_series == "bionic"


def _app(name, units):
    app = MagicMock(spec_set=OpenStackApplication).return_value
    app.charm = name
    app.units = units
    return app


def _unit(machine_id):
    unit = MagicMock(spec_set=ApplicationUnit).return_value
    unit.machine = COUMachine(machine_id, "juju-efc45", "zone-1")
    return unit


@pytest.mark.parametrize(
    "exp_control_plane, exp_data_plane",
    [
        (
            [_app("keystone", [_unit("0"), _unit("1"), _unit("2")])],
            [_app("ceph-osd", [_unit("3"), _unit("4"), _unit("5")])],
        ),
        (
            [],
            [
                _app("nova-compute", [_unit("0"), _unit("1"), _unit("2")]),
                _app("keystone", [_unit("0"), _unit("1"), _unit("2")]),
                _app("ceph-osd", [_unit("3"), _unit("4"), _unit("5")]),
            ],
        ),
        (
            [_app("keystone", [_unit("6"), _unit("7"), _unit("8")])],
            [
                _app("nova-compute", [_unit("0"), _unit("1"), _unit("2")]),
                _app("ceph-osd", [_unit("3"), _unit("4"), _unit("5")]),
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
async def test_analysis_machines(apps, model, apps_machines):
    result = analyze.Analysis(
        model=model,
        apps_control_plane=[
            apps["rmq"],
            apps["keystone_focal_wallaby"],
            apps["cinder_focal_ussuri"],
        ],
        apps_data_plane=[apps["nova_focal_ussuri"]],
    )

    expected_control_plane_machines = {
        **apps_machines["rmq"],
        **apps_machines["keystone"],
        **apps_machines["cinder"],
    }

    expected_data_plane_machines = {**apps_machines["nova-compute"]}

    assert result.control_plane_machines == expected_control_plane_machines
    assert result.data_plane_machines == expected_data_plane_machines
    assert result.machines == {**expected_control_plane_machines, **expected_data_plane_machines}
