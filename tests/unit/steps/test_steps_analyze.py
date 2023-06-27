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

from collections import defaultdict

import pytest
import yaml

from cou import exceptions
from cou.steps import analyze
from cou.utils import juju_utils


def test_application_eq(status, config, mocker):
    """Name of the app is used as comparison between Applications objects."""
    mocker.patch.object(analyze.Application, "_get_pkg_version", return_value="2:17.0.1-0ubuntu1")
    mocker.patch.object(analyze.Application, "_get_openstack_release", return_value=None)
    status_keystone_1 = status["keystone_ch"]
    config_keystone_1 = config["openstack_ussuri"]
    status_keystone_2 = status["keystone_cs"]
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
    "issues",
    [
        "no_issues",
        "os_release_units",
        "change_channel",
        "charmhub_migration",
        "change_openstack_release",
    ],
)
@pytest.mark.asyncio
async def test_application(issues, status, config, mocker, units):
    """Test the object Application on different scenarios."""
    expected_os_release_units = defaultdict(set)
    expected_pkg_version_units = defaultdict(set)
    expected_upgrade_units = defaultdict(set)
    expected_change_channel = defaultdict(set)
    expected_charmhub_migration = defaultdict(set)
    expected_change_openstack_release = defaultdict(set)

    app_status = status["keystone_ch"]
    app_config = config["openstack_ussuri"]
    expected_charm_origin = "ch"
    expected_os_origin = "distro"
    expected_units = units["units_ussuri"]

    if issues == "os_release_units":
        # different package version for keystone/2
        mocker.patch.object(
            analyze.Application,
            "_get_pkg_version",
            side_effect=["2:17.0.1-0ubuntu1", "2:17.0.1-0ubuntu1", "2:18.1.0-0ubuntu1~cloud0"],
        )
        expected_pkg_version_units["2:17.0.1-0ubuntu1"] = {
            "keystone/0",
            "keystone/1",
        }
        expected_pkg_version_units["2:18.1.0-0ubuntu1~cloud0"] = {
            "keystone/2",
        }
        expected_units["keystone/2"]["os_version"] = "victoria"
        expected_units["keystone/2"]["pkg_version"] = "2:18.1.0-0ubuntu1~cloud0"

        expected_os_release_units["ussuri"] = {"keystone/0", "keystone/1"}
        expected_os_release_units["victoria"] = {"keystone/2"}
        expected_upgrade_units["victoria"] = {"keystone/0", "keystone/1"}

    elif issues == "change_channel":
        # application has wrong channel in status
        mocker.patch.object(
            analyze.Application, "_get_pkg_version", return_value="2:17.0.1-0ubuntu1"
        )
        expected_os_release_units["ussuri"] = {"keystone/0", "keystone/1", "keystone/2"}
        expected_pkg_version_units["2:17.0.1-0ubuntu1"] = {
            "keystone/0",
            "keystone/1",
            "keystone/2",
        }
        app_status = status["keystone_wrong_channel"]
        expected_change_channel["ussuri/stable"] = {"keystone"}

    elif issues == "charmhub_migration":
        # application is from charm store
        expected_charm_origin = "cs"
        mocker.patch.object(
            analyze.Application, "_get_pkg_version", return_value="2:17.0.1-0ubuntu1"
        )
        expected_os_release_units["ussuri"] = {"keystone/0", "keystone/1", "keystone/2"}
        expected_pkg_version_units["2:17.0.1-0ubuntu1"] = {
            "keystone/0",
            "keystone/1",
            "keystone/2",
        }
        app_status = status["keystone_cs"]
        expected_charmhub_migration["ussuri/stable"] = {"keystone"}

    elif issues == "change_openstack_release":
        # application has wrong configuration for openstack-release
        expected_os_origin = "cloud:focal-ussuri"
        app_config = {"openstack-origin": {"value": "cloud:focal-ussuri"}}
        mocker.patch.object(
            analyze.Application, "_get_pkg_version", return_value="2:17.0.1-0ubuntu1"
        )
        expected_os_release_units["ussuri"] = {"keystone/0", "keystone/1", "keystone/2"}
        expected_pkg_version_units["2:17.0.1-0ubuntu1"] = {
            "keystone/0",
            "keystone/1",
            "keystone/2",
        }
        expected_change_openstack_release["distro"] = {"keystone"}

    elif issues == "no_issues":
        mocker.patch.object(
            analyze.Application, "_get_pkg_version", return_value="2:17.0.1-0ubuntu1"
        )
        expected_os_release_units["ussuri"] = {"keystone/0", "keystone/1", "keystone/2"}
        expected_pkg_version_units["2:17.0.1-0ubuntu1"] = {
            "keystone/0",
            "keystone/1",
            "keystone/2",
        }

    mocker.patch.object(analyze.Application, "_get_openstack_release", return_value=None)

    app = await analyze.Application("keystone", app_status, app_config, "my_model").fill()
    assert app.name == "keystone"
    assert app.status == app_status
    assert app.config == app_config
    assert app.model_name == "my_model"
    assert app.charm == "keystone"
    assert app.charm_origin == expected_charm_origin
    assert app.os_origin == expected_os_origin
    assert app.units == expected_units
    assert app.channel == app_status.charm_channel
    assert app.pkg_name == "keystone"
    assert app.os_release_units == expected_os_release_units
    assert app.pkg_version_units == expected_pkg_version_units


@pytest.mark.asyncio
async def test_application_to_dict(mocker, status, config):
    """Test that the yaml output is as expected."""
    expected_output = {
        "keystone": {
            "charm": "keystone",
            "model_name": "my_model",
            "charm_origin": "ch",
            "os_origin": "distro",
            "channel": "ussuri/stable",
            "pkg_name": "keystone",
            "units": {
                "keystone/0": {
                    "pkg_version": "2:17.0.1-0ubuntu1",
                    "os_version": "ussuri",
                },
                "keystone/1": {
                    "pkg_version": "2:17.0.1-0ubuntu1",
                    "os_version": "ussuri",
                },
                "keystone/2": {
                    "pkg_version": "2:17.0.1-0ubuntu1",
                    "os_version": "ussuri",
                },
            },
        }
    }
    app_status = status["keystone_ch"]
    app_config = config["openstack_ussuri"]
    mocker.patch.object(analyze.Application, "_get_pkg_version", return_value="2:17.0.1-0ubuntu1")
    mocker.patch.object(analyze.Application, "_get_openstack_release", return_value=None)
    app = await analyze.Application("keystone", app_status, app_config, "my_model").fill()
    assert str(app) == yaml.dump(expected_output)
    assert app.to_dict() == expected_output


@pytest.mark.asyncio
async def test_analysis_dump(mocker, async_apps):
    """Test analysis dump."""
    expected_result = (
        "keystone:\n"
        "  channel: ussuri/stable\n"
        "  charm: keystone\n"
        "  charm_origin: ch\n"
        "  model_name: my_model\n"
        "  os_origin: distro\n"
        "  pkg_name: keystone\n"
        "  units:\n"
        "    keystone/0:\n"
        "      os_version: ussuri\n"
        "      pkg_version: 2:17.0.1-0ubuntu1~cloud0\n"
        "    keystone/1:\n"
        "      os_version: ussuri\n"
        "      pkg_version: 2:17.0.1-0ubuntu1~cloud0\n"
        "    keystone/2:\n"
        "      os_version: ussuri\n"
        "      pkg_version: 2:17.0.1-0ubuntu1~cloud0\n"
        "\n"
        "cinder:\n"
        "  channel: ussuri/stable\n"
        "  charm: cinder\n"
        "  charm_origin: ch\n"
        "  model_name: my_model\n"
        "  os_origin: distro\n"
        "  pkg_name: cinder-common\n"
        "  units:\n"
        "    cinder/0:\n"
        "      os_version: ussuri\n"
        "      pkg_version: 2:16.4.2-0ubuntu2.2~cloud0\n"
        "    cinder/1:\n"
        "      os_version: ussuri\n"
        "      pkg_version: 2:16.4.2-0ubuntu2.2~cloud0\n"
        "    cinder/2:\n"
        "      os_version: ussuri\n"
        "      pkg_version: 2:16.4.2-0ubuntu2.2~cloud0\n"
    )
    apps = await async_apps
    result = analyze.Analysis(apps=apps)
    mocker.patch.object(analyze, "generate_model", return_value=apps)

    result = await analyze.analyze()
    assert result.dump() == expected_result


@pytest.mark.asyncio
async def test_application_invalid_charm_name(mocker, status, config):
    """Assert that raises error if charm name is invalid."""
    mocker.patch.object(juju_utils.re, "match", return_value=None)
    with pytest.raises(exceptions.InvalidCharmNameError):
        await analyze.Application(
            "keystone", status["keystone_ch"], config["openstack_ussuri"], "my_model"
        ).fill()


@pytest.mark.parametrize(
    "issues",
    [
        "no_issues",
        "change_openstack_release",
    ],
)
@pytest.mark.asyncio
async def test_application_bigger_than_wallaby(issues, mocker, status, config, units):
    """Test when openstack-release package is available."""
    expected_os_release_units = defaultdict(set)
    expected_pkg_version_units = defaultdict(set)
    expected_change_openstack_release = defaultdict(set)

    expected_units = units["units_wallaby"]
    expected_pkg_version_units["2:18.1.0-0ubuntu1~cloud0"] = {
        "keystone/0",
        "keystone/1",
        "keystone/2",
    }

    if issues == "no_issues":
        app_config = config["openstack_wallaby"]

    elif issues == "change_openstack_release":
        # application has wrong configuration for openstack-release
        app_config = {"openstack-origin": {"value": "cloud:focal-victoria"}}
        expected_change_openstack_release["cloud:focal-wallaby"] = {"keystone"}

    app_status = status["keystone_wallaby"]
    expected_charm_origin = "ch"
    mocker.patch.object(analyze.Application, "_get_openstack_release", return_value="wallaby")
    mocker.patch.object(
        analyze.Application, "_get_pkg_version", return_value="2:18.1.0-0ubuntu1~cloud0"
    )
    expected_os_release_units["wallaby"] = {"keystone/0", "keystone/1", "keystone/2"}

    app = await analyze.Application("keystone", app_status, app_config, "my_model").fill()
    assert app.name == "keystone"
    assert app.status == app_status
    assert app.model_name == "my_model"
    assert app.config == app_config
    assert app.charm == "keystone"
    assert app.units == expected_units
    assert app.channel == app_status.charm_channel
    assert app.pkg_name == "keystone"
    assert app.os_release_units == expected_os_release_units
    assert app.pkg_version_units == expected_pkg_version_units

    assert app.charm_origin == expected_charm_origin


def test_application_no_openstack_origin(mocker, status):
    """Test when application doesn't have openstack-origin or source config."""
    app_status = status["keystone_wallaby"]
    app_config = {}
    mocker.patch.object(analyze.Application, "_get_openstack_release", return_value="wallaby")
    mocker.patch.object(
        analyze.Application, "_get_pkg_version", return_value="2:18.1.0-0ubuntu1~cloud0"
    )
    app = analyze.Application("keystone", app_status, app_config, "my_model")
    assert app._get_os_origin() == ""


@pytest.mark.asyncio
async def test_get_openstack_release(mocker):
    """Test function get_openstack_release."""
    # normal output
    mock_run = mocker.patch.object(
        analyze, "async_run_on_unit", return_value={"Stdout": "wallaby"}
    )

    keystone_1 = analyze.Application("keystone", "", "", "")
    assert await keystone_1._get_openstack_release("keystone/0") == "wallaby"
    assert mock_run.called_with("keystone/0", None, 20)

    # no output
    mock_run = mocker.patch.object(analyze, "async_run_on_unit", return_value={"Stdout": ""})
    assert await keystone_1._get_openstack_release("keystone/0") == ""
    assert mock_run.called_with("keystone/0", None, 20)

    # raises CommandRunFailed
    mock_run = mocker.patch.object(
        analyze, "async_run_on_unit", side_effect=analyze.CommandRunFailed("cmd", {})
    )
    assert await keystone_1._get_openstack_release("keystone/0") is None
    assert mock_run.called_with("keystone/0", None, 20)


@pytest.mark.asyncio
async def test_get_pkg_version(mocker):
    """Test function get_pkg_version."""
    mocker.patch.object(analyze, "async_run_on_unit", return_value={"Stdout": "2:17.0.1-0ubuntu1"})
    keystone_1 = analyze.Application("keystone", "", "", "")
    assert await keystone_1._get_pkg_version("keystone/0", "keystone") == "2:17.0.1-0ubuntu1"


@pytest.mark.asyncio
async def test_generate_model(mocker, full_status, config):
    mocker.patch.object(analyze, "async_get_full_juju_status", return_value=full_status)
    mocker.patch.object(
        analyze, "async_get_application_config", return_value=config["openstack_ussuri"]
    )
    mocker.patch.object(analyze.Application, "_get_openstack_release", return_value=None)
    mocker.patch.object(
        analyze.Application,
        "_get_pkg_version",
        side_effect=[
            "2:17.0.1-0ubuntu1~cloud0",  # keystone units
            "2:17.0.1-0ubuntu1~cloud0",
            "2:17.0.1-0ubuntu1~cloud0",
            "2:16.4.2-0ubuntu2.2~cloud0",  # cinder units
            "2:16.4.2-0ubuntu2.2~cloud0",
            "2:16.4.2-0ubuntu2.2~cloud0",
            "",  # rabbitmq-server unit
        ],
    )
    # Initially, 3 applications are in the status (keystone, cinder and rabbitmq-server)
    assert len(full_status.applications) == 3
    apps = await analyze.generate_model()
    # rabbitmq-server is filtered from supported openstack charms.
    assert len(apps) == 2
    assert {app.charm for app in apps} == {"keystone", "cinder"}


@pytest.mark.asyncio
async def test_analysis(mocker, async_apps):
    """Test analysis function."""
    apps = await async_apps
    expected_result = analyze.Analysis(apps=apps)
    mocker.patch.object(analyze, "generate_model", return_value=apps)

    result = await analyze.analyze()
    assert result == expected_result
