# Copyright 2023 Canonical Limited.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import pytest

from cou.steps import analyze
from cou.steps.analyze import Analysis


def test_application_eq(status, config):
    """Name of the app is used as comparison between Applications objects."""
    status_keystone_1 = status["keystone_ussuri"]
    config_keystone_1 = config["openstack_ussuri"]
    status_keystone_2 = status["keystone_wallaby"]
    config_keystone_2 = config["openstack_wallaby"]
    keystone_1 = analyze.Application("keystone", status_keystone_1, config_keystone_1, "my_model")
    keystone_2 = analyze.Application("keystone", status_keystone_2, config_keystone_2, "my_model")
    keystone_3 = analyze.Application(
        "keystone_foo", status_keystone_1, config_keystone_1, "my_model"
    )

    # keystone_1 is equal to keystone_2 because they have the same name
    # even if they have different status and config.
    assert keystone_1 == keystone_2
    # keystone_1 is different then keystone_3 even if they have same status and config.
    assert keystone_1 != keystone_3


@pytest.mark.parametrize(
    "condition",
    [
        "keystone_ussuri",
        "keystone_ussuri_different_wl_version",
        "keystone_ussuri_cs",
        "keystone_wallaby",
    ],
)
@pytest.mark.asyncio
async def test_application(condition, status, config, mocker, units):
    """Test the object Application on different scenarios."""
    if "ussuri" in condition:
        app_status = status["keystone_ussuri"]
        app_config = config["openstack_ussuri"]
        expected_charm_origin = "ch"
        expected_os_origin = "distro"
        expected_units = units["units_ussuri"]

    if condition == "keystone_ussuri_different_wl_version":
        # different workload version for keystone/2
        mock_unit_2 = mocker.MagicMock()
        mock_unit_2.workload_version = "18.1.0"
        app_status.units["keystone/2"] = mock_unit_2

        expected_units["keystone/2"]["os_version"] = "victoria"
        expected_units["keystone/2"]["workload_version"] = "18.1.0"

    elif condition == "keystone_ussuri_cs":
        # application is from charm store
        expected_charm_origin = "cs"
        app_status = status["keystone_ussuri_cs"]

    elif condition == "keystone_wallaby":
        expected_units = units["units_wallaby"]
        expected_charm_origin = "ch"
        app_config = config["openstack_wallaby"]
        app_status = status["keystone_wallaby"]
        expected_os_origin = "cloud:focal-wallaby"

    app = analyze.Application("keystone", app_status, app_config, "my_model")
    assert app.name == "keystone"
    assert app.status == app_status
    assert app.config == app_config
    assert app.model_name == "my_model"
    assert app.charm == "keystone"
    assert app.charm_origin == expected_charm_origin
    assert app.os_origin == expected_os_origin
    assert app.units == expected_units
    assert app.channel == app_status.charm_channel


@pytest.mark.asyncio
async def test_analysis_dump(mocker, apps):
    """Test analysis dump."""
    expected_result = (
        "keystone:\n"
        "  model_name: my_model\n"
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
        "  model_name: my_model\n"
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
    )

    mocker.patch.object(analyze.Analysis, "_populate", return_value=apps)
    result = await analyze.Analysis.create()
    assert str(result) == expected_result


def test_application_no_openstack_origin(status):
    """Test when application doesn't have openstack-origin or source config."""
    app_status = status["keystone_wallaby"]
    app_config = {}
    app = analyze.Application("keystone", app_status, app_config, "my_model")
    assert app._get_os_origin() == ""


@pytest.mark.asyncio
async def test_generate_model(mocker, full_status, config):
    mocker.patch.object(analyze, "async_get_status", return_value=full_status)
    mocker.patch.object(
        analyze, "async_get_application_config", return_value=config["openstack_ussuri"]
    )
    # Initially, 3 applications are in the status (keystone, cinder and rabbitmq-server)
    assert len(full_status.applications) == 3
    apps = await Analysis._populate()
    assert len(apps) == 3
    assert {app.charm for app in apps} == {"keystone", "cinder", "rabbitmq-server"}


@pytest.mark.asyncio
async def test_analysis(mocker, apps):
    """Test analysis function."""
    expected_result = analyze.Analysis(apps=apps)
    mocker.patch.object(analyze.Analysis, "_populate", return_value=apps)

    result = await Analysis.create()
    assert result == expected_result
