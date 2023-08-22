#  Copyright 2023 Canonical Limited
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import pytest

from cou.apps.app import Application
from cou.exceptions import MismatchedOpenStackVersions


def test_application_eq(status, config):
    """Name of the app is used as comparison between Applications objects."""
    status_keystone_1 = status["keystone_ussuri"]
    config_keystone_1 = config["openstack_ussuri"]
    status_keystone_2 = status["keystone_wallaby"]
    config_keystone_2 = config["openstack_wallaby"]
    keystone_1 = Application("keystone", status_keystone_1, config_keystone_1, "my_model")
    keystone_2 = Application("keystone", status_keystone_2, config_keystone_2, "my_model")
    keystone_3 = Application("keystone_foo", status_keystone_1, config_keystone_1, "my_model")

    # keystone_1 is equal to keystone_2 because they have the same name
    # even if they have different status and config.
    assert keystone_1 == keystone_2
    # keystone_1 is different then keystone_3 even if they have same status and config.
    assert keystone_1 != keystone_3


def assert_application(
    app,
    exp_name,
    exp_series,
    exp_status,
    exp_config,
    exp_model,
    exp_charm,
    exp_charm_origin,
    exp_os_origin,
    exp_units,
    exp_channel,
    exp_current_os_release,
):
    assert app.name == exp_name
    assert app.series == exp_series
    assert app.status == exp_status
    assert app.config == exp_config
    assert app.model_name == exp_model
    assert app.charm == exp_charm
    assert app.charm_origin == exp_charm_origin
    assert app.os_origin == exp_os_origin
    assert app.units == exp_units
    assert app.channel == exp_channel
    assert app.current_os_release == exp_current_os_release


def test_application_ussuri(status, config, units):
    app_status = status["keystone_ussuri"]
    app_config = config["openstack_ussuri"]
    exp_charm_origin = "ch"
    exp_os_origin = "distro"
    exp_units = units["units_ussuri"]
    exp_channel = app_status.charm_channel
    exp_series = app_status.series
    exp_current_os_release = "ussuri"

    app = Application("my_keystone", app_status, app_config, "my_model")
    assert_application(
        app,
        "my_keystone",
        exp_series,
        app_status,
        app_config,
        "my_model",
        "keystone",
        exp_charm_origin,
        exp_os_origin,
        exp_units,
        exp_channel,
        exp_current_os_release,
    )


def test_application_different_wl(status, config, units, mocker):
    """Different OpenStack Version on units if workload version is different."""
    app_status = status["keystone_ussuri"]
    app_config = config["openstack_ussuri"]

    mock_unit_2 = mocker.MagicMock()
    mock_unit_2.workload_version = "18.1.0"
    app_status.units["keystone/2"] = mock_unit_2

    mock_logger = mocker.patch("cou.apps.app.logger")

    app = Application("my_keystone", app_status, app_config, "my_model")
    with pytest.raises(MismatchedOpenStackVersions):
        app.current_os_release
        mock_logger.error.assert_called_once


def test_application_cs(status, config, units):
    """Test when application is from charm store."""
    app_status = status["keystone_ussuri_cs"]
    app_config = config["openstack_ussuri"]
    exp_os_origin = "distro"
    exp_units = units["units_ussuri"]
    exp_channel = app_status.charm_channel
    exp_charm_origin = "cs"
    exp_series = app_status.series
    exp_current_os_release = "ussuri"

    app = Application("my_keystone", app_status, app_config, "my_model")
    assert_application(
        app,
        "my_keystone",
        exp_series,
        app_status,
        app_config,
        "my_model",
        "keystone",
        exp_charm_origin,
        exp_os_origin,
        exp_units,
        exp_channel,
        exp_current_os_release,
    )


def test_application_wallaby(status, config, units):
    exp_units = units["units_wallaby"]
    exp_charm_origin = "ch"
    app_config = config["openstack_wallaby"]
    app_status = status["keystone_wallaby"]
    exp_os_origin = "cloud:focal-wallaby"
    exp_channel = app_status.charm_channel
    exp_series = app_status.series
    exp_current_os_release = "wallaby"

    app = Application("my_keystone", app_status, app_config, "my_model")
    assert_application(
        app,
        "my_keystone",
        exp_series,
        app_status,
        app_config,
        "my_model",
        "keystone",
        exp_charm_origin,
        exp_os_origin,
        exp_units,
        exp_channel,
        exp_current_os_release,
    )


def test_application_subordinate(status):
    app_status = status["mysql_router"]
    app_config = {"source": {"value": "distro"}}
    app = Application("mysql_router", app_status, app_config, "my_model")
    assert app.current_os_release is None
    assert app.units == {}


def test_special_app_more_than_one_compatible_os_release(status, config):
    # version 3.8 on rabbitmq can be from ussuri to yoga. In that case it will be set as yoga.
    expected_units = {"rabbitmq-server/0": {"os_version": "yoga", "workload_version": "3.8"}}
    app = Application(
        "rabbitmq-server", status["rabbitmq_server"], config["openstack_ussuri"], "my_model"
    )
    assert app.units == expected_units


def test_special_app_unknown_version(status, config, mocker):
    expected_units = {"rabbitmq-server/0": {"os_version": None, "workload_version": "80.5"}}
    mock_logger = mocker.patch("cou.apps.app.logger")
    app = Application(
        "rabbitmq-server",
        status["unknown_rabbitmq_server"],
        config["openstack_ussuri"],
        "my_model",
    )
    assert app.units == expected_units
    mock_logger.warning.assert_called_once_with(
        "No compatible OpenStack versions were found to %s with workload version %s",
        "rabbitmq-server",
        "80.5",
    )


def test_application_no_openstack_origin(status):
    """Test when application doesn't have openstack-origin or source config."""
    app_status = status["keystone_wallaby"]
    app_config = {}
    app = Application("my_app", app_status, app_config, "my_model")
    assert app._get_os_origin() == ""
