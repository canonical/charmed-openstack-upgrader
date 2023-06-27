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

from collections import OrderedDict, defaultdict

import mock
import pytest

from cou.steps import analyze


@pytest.fixture
def status():
    mock_keystone_ch = mock.MagicMock()
    mock_keystone_ch.charm_channel = "ussuri/stable"
    mock_keystone_ch.charm = "ch:amd64/focal/keystone-638"
    mock_units_keystone = mock.MagicMock()
    mock_units_keystone.workload_version = "17.0.1"
    mock_keystone_ch.units = OrderedDict(
        [
            ("keystone/0", mock_units_keystone),
            ("keystone/1", mock_units_keystone),
            ("keystone/2", mock_units_keystone),
        ]
    )

    mock_cinder_ch = mock.MagicMock()
    mock_cinder_ch.charm_channel = "ussuri/stable"
    mock_cinder_ch.charm = "ch:amd64/focal/cinder-633"
    mock_units_cinder = mock.MagicMock()
    mock_units_cinder.workload_version = "16.4.2"
    mock_cinder_ch.units = OrderedDict(
        [
            ("cinder/0", mock_units_cinder),
            ("cinder/1", mock_units_cinder),
            ("cinder/2", mock_units_cinder),
        ]
    )

    mock_keystone_cs = mock.MagicMock()
    mock_keystone_cs.charm_channel = "ussuri/stable"
    mock_keystone_cs.charm = "cs:amd64/focal/keystone-638"
    mock_keystone_cs.units = OrderedDict(
        [
            ("keystone/0", mock_units_keystone),
            ("keystone/1", mock_units_keystone),
            ("keystone/2", mock_units_keystone),
        ]
    )

    mock_keystone_wrong_channel = mock.MagicMock()
    mock_keystone_wrong_channel.charm_channel = "latest/stable"
    mock_keystone_wrong_channel.charm = "ch:amd64/focal/keystone-638"
    mock_keystone_wrong_channel.units = OrderedDict(
        [
            ("keystone/0", mock_units_keystone),
            ("keystone/1", mock_units_keystone),
            ("keystone/2", mock_units_keystone),
        ]
    )

    mock_keystone_wallaby = mock.MagicMock()
    mock_keystone_wallaby.charm_channel = "wallaby/stable"
    mock_keystone_wallaby.charm = "ch:amd64/focal/keystone-638"
    mock_units_keystone_wallaby = mock.MagicMock()
    mock_units_keystone_wallaby.workload_version = "18.1.0"
    mock_keystone_wallaby.units = OrderedDict(
        [
            ("keystone/0", mock_units_keystone_wallaby),
            ("keystone/1", mock_units_keystone_wallaby),
            ("keystone/2", mock_units_keystone_wallaby),
        ]
    )

    mock_rmq = mock.MagicMock()
    mock_units_rmq = mock.MagicMock()
    mock_rmq.charm_channel = "3.9/stable"
    mock_units_rmq.workload_version = "3.9"
    mock_rmq.charm = "ch:amd64/focal/rabbitmq-server-638"
    mock_rmq.units = OrderedDict([("rabbitmq-server/0", mock_units_rmq)])

    status = {
        "keystone_ch": mock_keystone_ch,
        "cinder_ch": mock_cinder_ch,
        "rabbitmq_server": mock_rmq,
        "keystone_cs": mock_keystone_cs,
        "keystone_wrong_channel": mock_keystone_wrong_channel,
        "keystone_wallaby": mock_keystone_wallaby,
    }
    return status


@pytest.fixture
def full_status(status):
    mock_full_status = mock.MagicMock()
    mock_full_status.model.name = "my_model"
    mock_full_status.applications = OrderedDict(
        [
            ("keystone", status["keystone_ch"]),
            ("cinder", status["cinder_ch"]),
            ("rabbitmq_server", status["rabbitmq_server"]),
        ]
    )
    return mock_full_status


@pytest.fixture
def units():
    units_ussuri = defaultdict(dict)
    units_wallaby = defaultdict(dict)
    for unit in ["keystone/0", "keystone/1", "keystone/2"]:
        units_ussuri[unit]["os_version"] = "ussuri"
        units_ussuri[unit]["pkg_version"] = "17.0.1"
        units_wallaby[unit]["os_version"] = "wallaby"
        units_wallaby[unit]["pkg_version"] = "18.1.0"
    return {"units_ussuri": units_ussuri, "units_wallaby": units_wallaby}


@pytest.fixture
async def async_apps(mocker, status, config):
    keystone_status = status["keystone_ch"]
    cinder_status = status["cinder_ch"]
    app_config = config["openstack_ussuri"]
    mocker.patch.object(analyze.Application, "_get_openstack_release", return_value=None)
    app_keystone = await analyze.Application(
        "keystone", keystone_status, app_config, "my_model"
    ).fill()
    app_cinder = await analyze.Application("cinder", cinder_status, app_config, "my_model").fill()

    return [app_keystone, app_cinder]


@pytest.fixture
def config():
    return {
        "openstack_ussuri": {
            "openstack-origin": {"value": "distro"},
        },
        "openstack_wallaby": {"openstack-origin": {"value": "cloud:focal-wallaby"}},
    }
