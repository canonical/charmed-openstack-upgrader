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

from cou.apps.app import Application


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

    app = Application("keystone", app_status, app_config, "my_model")
    assert app.name == "keystone"
    assert app.status == app_status
    assert app.config == app_config
    assert app.model_name == "my_model"
    assert app.charm == "keystone"
    assert app.charm_origin == expected_charm_origin
    assert app.os_origin == expected_os_origin
    assert app.units == expected_units
    assert app.channel == app_status.charm_channel


@pytest.mark.parametrize(
    "condition",
    ["rabbitmq_server", "unknown_rabbitmq_server"],
)
def test_app_more_than_one_compatible_os_release(condition, status, config):
    expected_units = defaultdict(dict)
    # version 3.8 on rabbitmq can be from ussuri to yoga. In that case it will be set as yoga.
    if condition == "rabbitmq_server":
        expected_units["rabbitmq-server/0"]["os_version"] = "yoga"
        expected_units["rabbitmq-server/0"]["workload_version"] = "3.8"
    # unknown version of rabbitmq
    elif condition == "unknown_rabbitmq_server":
        expected_units["rabbitmq-server/0"]["os_version"] = ""
        expected_units["rabbitmq-server/0"]["workload_version"] = "80.5"

    app = Application("rabbitmq-server", status[condition], config["openstack_ussuri"], "my_model")
    assert app.units == expected_units


def test_application_no_openstack_origin(status):
    """Test when application doesn't have openstack-origin or source config."""
    app_status = status["keystone_wallaby"]
    app_config = {}
    app = Application("my_app", app_status, app_config, "my_model")
    assert app._get_os_origin() == ""
