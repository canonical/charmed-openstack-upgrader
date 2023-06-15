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

from cou.steps import analyze


def test_application_eq(status, config, mocker):
    """Name of the app is used as comparison between Applications objects."""
    mocker.patch.object(analyze, "get_pkg_version", return_value="2:17.0.1-0ubuntu1")
    mocker.patch.object(analyze, "get_openstack_release", return_value=None)
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
def test_application(issues, status, config, mocker, units):
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
            analyze,
            "get_pkg_version",
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
        mocker.patch.object(analyze, "get_pkg_version", return_value="2:17.0.1-0ubuntu1")
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
        mocker.patch.object(analyze, "get_pkg_version", return_value="2:17.0.1-0ubuntu1")
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
        mocker.patch.object(analyze, "get_pkg_version", return_value="2:17.0.1-0ubuntu1")
        expected_os_release_units["ussuri"] = {"keystone/0", "keystone/1", "keystone/2"}
        expected_pkg_version_units["2:17.0.1-0ubuntu1"] = {
            "keystone/0",
            "keystone/1",
            "keystone/2",
        }
        expected_change_openstack_release["distro"] = {"keystone"}

    elif issues == "no_issues":
        mocker.patch.object(analyze, "get_pkg_version", return_value="2:17.0.1-0ubuntu1")
        expected_os_release_units["ussuri"] = {"keystone/0", "keystone/1", "keystone/2"}
        expected_pkg_version_units["2:17.0.1-0ubuntu1"] = {
            "keystone/0",
            "keystone/1",
            "keystone/2",
        }

    mocker.patch.object(analyze, "get_openstack_release", return_value=None)

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
    assert app.pkg_name == "keystone"
    assert app.os_release_units == expected_os_release_units
    assert app.pkg_version_units == expected_pkg_version_units

    assert app.check_os_versions_units(defaultdict(set)) == expected_upgrade_units
    assert app.check_os_channels_and_migration(defaultdict(set), defaultdict(set)) == (
        expected_change_channel,
        expected_charmhub_migration,
    )
    assert app.check_os_origin(defaultdict(set)) == expected_change_openstack_release


def test_application_to_dict(mocker, status, config):
    """Test that the yaml output is as expected."""
    expected_output = {
        "keystone": {
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
    mocker.patch.object(analyze, "get_pkg_version", return_value="2:17.0.1-0ubuntu1")
    mocker.patch.object(analyze, "get_openstack_release", return_value=None)
    app = analyze.Application("keystone", app_status, app_config, "my_model")
    assert app.to_dict() == expected_output


def test_application_invalid_charm_name(mocker, status, config):
    """Assert that raises error if charm name is invalid."""
    mocker.patch.object(analyze.re, "match", return_value=None)
    with pytest.raises(analyze.InvalidCharmNameError):
        analyze.Application(
            "keystone", status["keystone_ch"], config["openstack_ussuri"], "my_model"
        )


@pytest.mark.parametrize(
    "issues",
    [
        "no_issues",
        "change_openstack_release",
    ],
)
def test_application_bigger_than_wallaby(issues, mocker, status, config, units):
    """Test when openstack-release package is available."""
    expected_os_release_units = defaultdict(set)
    expected_pkg_version_units = defaultdict(set)
    expected_upgrade_units = defaultdict(set)
    expected_change_channel = defaultdict(set)
    expected_charmhub_migration = defaultdict(set)
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
    mocker.patch.object(analyze, "get_openstack_release", return_value="wallaby")
    mocker.patch.object(analyze, "get_pkg_version", return_value="2:18.1.0-0ubuntu1~cloud0")
    expected_os_release_units["wallaby"] = {"keystone/0", "keystone/1", "keystone/2"}

    app = analyze.Application("keystone", app_status, app_config, "my_model")
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

    assert app.check_os_versions_units(defaultdict(set)) == expected_upgrade_units
    assert app.charm_origin == expected_charm_origin
    assert app.check_os_channels_and_migration(defaultdict(set), defaultdict(set)) == (
        expected_change_channel,
        expected_charmhub_migration,
    )
    assert app.check_os_origin(defaultdict(set)) == expected_change_openstack_release


def test_application_no_openstack_origin(mocker, status):
    """Test when application doesn't have openstack-origin or source config."""
    app_status = status["keystone_wallaby"]
    app_config = {}
    mocker.patch.object(analyze, "get_openstack_release", return_value="wallaby")
    mocker.patch.object(analyze, "get_pkg_version", return_value="2:18.1.0-0ubuntu1~cloud0")
    app = analyze.Application("keystone", app_status, app_config, "my_model")
    assert app.get_os_origin() == ""


def test_get_openstack_release(mocker):
    """Test function get_openstack_release."""
    # normal output
    mock_run = mocker.patch.object(
        analyze.model, "run_on_unit", return_value={"Stdout": "wallaby"}
    )
    assert analyze.get_openstack_release("keystone/0") == "wallaby"
    assert mock_run.called_with("keystone/0", None, 20)

    # no output
    mock_run = mocker.patch.object(analyze.model, "run_on_unit", return_value={"Stdout": ""})
    assert analyze.get_openstack_release("keystone/0") == ""
    assert mock_run.called_with("keystone/0", None, 20)

    # raises CommandRunFailed
    mock_run = mocker.patch.object(
        analyze.model, "run_on_unit", side_effect=analyze.model.CommandRunFailed("cmd", {})
    )
    assert analyze.get_openstack_release("keystone/0") is None
    assert mock_run.called_with("keystone/0", None, 20)


def test_get_pkg_version(mocker):
    """Test function get_pkg_version."""
    mocker.patch.object(analyze.model, "run_on_unit", return_value={"Stdout": "2:17.0.1-0ubuntu1"})
    assert analyze.get_pkg_version("keystone/0", "keystone") == "2:17.0.1-0ubuntu1"


def test_generate_model(mocker, full_status, config):
    mocker.patch.object(analyze, "get_full_juju_status", return_value=full_status)
    mocker.patch.object(
        analyze.model, "get_application_config", return_value=config["openstack_ussuri"]
    )
    mocker.patch.object(analyze, "get_openstack_release", return_value=None)
    mocker.patch.object(
        analyze,
        "get_pkg_version",
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
    apps = analyze.generate_model()
    # rabbitmq-server is filtered from supported openstack charms.
    assert len(apps) == 2
    assert {app.charm for app in apps} == {"keystone", "cinder"}


@pytest.mark.parametrize(
    "issues",
    [
        "no_issues",
        "more_than_one_os_version",
    ],
)
def test_check_upgrade_charms(issues):
    """Test check_upgrade_charms function."""
    expected_upgrade_charms = defaultdict(set)
    os_versions = defaultdict(set)
    if issues == "no_issues":
        os_versions["ussuri"] = {"keystone", "cinder"}
        expected_upgrade_charms["victoria"] = {"keystone", "cinder"}
    elif issues == "more_than_one_os_version":
        os_versions["ussuri"] = {"keystone"}
        os_versions["victoria"] = {"cinder"}
        expected_upgrade_charms["victoria"] = {"keystone"}
    result = analyze.check_upgrade_charms(os_versions)
    assert result == expected_upgrade_charms


def test_analyze(mocker, apps):
    """Test analyze function."""
    upgrade_charms = defaultdict(set)
    upgrade_charms["victoria"] = {"cinder", "keystone"}
    expected_result = analyze.Analyze(
        defaultdict(set), upgrade_charms, defaultdict(set), defaultdict(set), defaultdict(set)
    )
    expected_outputs = {}
    for app in apps:
        expected_outputs.update(app.to_dict())
    mocker.patch.object(analyze, "generate_model", return_value=apps)
    mock_log_result = mocker.patch.object(analyze, "log_result")

    result = analyze.analyze()
    mock_log_result.assert_called_once_with(expected_result, expected_outputs)
    assert result == expected_result


def test_log_result(mocker, outputs):
    """Test log_result function."""
    expected_string = (
        'keystone:\n  channel: "\x1b[31mussuri/stable\x1b[0m \x1b[34m->\x1b[0m '
        '\x1b[32mvictoria/stable\x1b[0m"\n  charm_origin: "\x1b[31mcs\x1b[0m'
        ' \x1b[34m->\x1b[0m \x1b[32mch\x1b[0m"\n  model_name: my_model\n  '
        'os_origin: "\x1b[31mdistro\x1b[0m \x1b[34m->\x1b[0m \x1b[32mcloud:focal-wallaby\x1b[0m"\n'
        "  pkg_name: keystone\n  units:\n    keystone/0:\n      "
        'os_version: "\x1b[31mussuri\x1b[0m \x1b[34m->\x1b[0m \x1b[32mvictoria\x1b[0m"\n'
        '      pkg_version: 2:17.0.1-0ubuntu1\n    keystone/1:\n      os_version: "\x1b[3'
        '1mussuri\x1b[0m \x1b[34m->\x1b[0m \x1b[32mvictoria\x1b[0m"\n'
        "      pkg_version: 2:17.0.1-0ubuntu1\n    keystone/2:\n      os_version: ussuri\n"
        "      pkg_version: 2:17.0.1-0ubuntu1\n"
    )
    upgrade_units = defaultdict(set)
    upgrade_units["victoria"] = {"keystone/0", "keystone/1"}
    change_channel = defaultdict(set)
    change_channel["victoria/stable"] = {"keystone"}
    change_openstack_release = defaultdict(set)
    change_openstack_release["cloud:focal-wallaby"] = {"keystone"}
    upgrade_charms = defaultdict(set)
    upgrade_charms["victoria"] = {"keystone"}
    result = analyze.Analyze(
        upgrade_units, defaultdict(set), change_channel, change_channel, change_openstack_release
    )
    mock_log = mocker.patch.object(analyze.logging, "info")
    analyze.log_result(result, outputs)
    mock_log.assert_called_with("\n%s", expected_string)


def test_log_result_upgrade_charm(mocker, outputs):
    """Test log_result function for upgrade_charm."""
    expected_string = (
        'keystone:\n  channel: "\x1b[31mussuri/stable\x1b[0m \x1b[34m->\x1b[0m '
        '\x1b[32mvictoria/stable\x1b[0m"\n  charm_origin: "\x1b[31mcs\x1b[0m \x1b[34m'
        '->\x1b[0m \x1b[32mch\x1b[0m"\n  model_name: my_model\n  os_origin: "\x1b[31m'
        'distro\x1b[0m \x1b[34m->\x1b[0m \x1b[32mcloud:focal-wallaby\x1b[0m"\n  pkg_name:'
        ' keystone\n  units:\n    keystone/0:\n      os_version: "\x1b[31mussuri\x1b[0m \x1b[34m->'
        '\x1b[0m \x1b[32mvictoria\x1b[0m"\n      pkg_version: 2:17.0.1-0ubuntu1\n    keystone/1:\n'
        '      os_version: "\x1b[31mussuri\x1b[0m \x1b[34m->\x1b[0m \x1b[32mvictoria\x1b[0m"\n'
        "      pkg_version: 2:17.0.1-0ubuntu1\n    keystone/2:\n      "
        'os_version: "\x1b[31mussuri\x1b[0m \x1b[34m->\x1b[0m \x1b[32mvictoria\x1b[0m"\n'
        "      pkg_version: 2:17.0.1-0ubuntu1\n"
    )
    upgrade_charms = defaultdict(set)
    upgrade_charms["victoria"] = {"keystone"}
    change_channel = defaultdict(set)
    change_channel["victoria/stable"] = {"keystone"}
    change_openstack_release = defaultdict(set)
    change_openstack_release["cloud:focal-wallaby"] = {"keystone"}
    upgrade_charms = defaultdict(set)
    upgrade_charms["victoria"] = {"keystone"}
    result = analyze.Analyze(
        defaultdict(set), upgrade_charms, change_channel, change_channel, change_openstack_release
    )
    mock_log = mocker.patch.object(analyze.logging, "info")
    analyze.log_result(result, outputs)
    mock_log.assert_called_with("\n%s", expected_string)
