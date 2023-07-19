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
    mock_keystone_ussuri = mock.MagicMock()
    mock_keystone_ussuri.charm_channel = "ussuri/stable"
    mock_keystone_ussuri.charm = "ch:amd64/focal/keystone-638"
    mock_units_keystone_ussuri = mock.MagicMock()
    mock_units_keystone_ussuri.workload_version = "17.0.1"
    mock_keystone_ussuri.units = OrderedDict(
        [
            ("keystone/0", mock_units_keystone_ussuri),
            ("keystone/1", mock_units_keystone_ussuri),
            ("keystone/2", mock_units_keystone_ussuri),
        ]
    )

    mock_cinder_ussuri = mock.MagicMock()
    mock_cinder_ussuri.charm_channel = "ussuri/stable"
    mock_cinder_ussuri.charm = "ch:amd64/focal/cinder-633"
    mock_units_cinder_ussuri = mock.MagicMock()
    mock_units_cinder_ussuri.workload_version = "16.4.2"
    mock_cinder_ussuri.units = OrderedDict(
        [
            ("cinder/0", mock_units_cinder_ussuri),
            ("cinder/1", mock_units_cinder_ussuri),
            ("cinder/2", mock_units_cinder_ussuri),
        ]
    )

    mock_keystone_ussuri_cs = mock.MagicMock()
    mock_keystone_ussuri_cs.charm_channel = "ussuri/stable"
    mock_keystone_ussuri_cs.charm = "cs:amd64/focal/keystone-638"
    mock_keystone_ussuri_cs.units = OrderedDict(
        [
            ("keystone/0", mock_units_keystone_ussuri),
            ("keystone/1", mock_units_keystone_ussuri),
            ("keystone/2", mock_units_keystone_ussuri),
        ]
    )

    mock_keystone_wallaby = mock.MagicMock()
    mock_keystone_wallaby.charm_channel = "wallaby/stable"
    mock_keystone_wallaby.charm = "ch:amd64/focal/keystone-638"
    mock_units_keystone_wallaby = mock.MagicMock()
    mock_units_keystone_wallaby.workload_version = "19.1.0"
    mock_keystone_wallaby.units = OrderedDict(
        [
            ("keystone/0", mock_units_keystone_wallaby),
            ("keystone/1", mock_units_keystone_wallaby),
            ("keystone/2", mock_units_keystone_wallaby),
        ]
    )

    mock_rmq = mock.MagicMock()
    mock_units_rmq = mock.MagicMock()
    mock_rmq.charm_channel = "3.8/stable"
    mock_units_rmq.workload_version = "3.8"
    mock_rmq.charm = "ch:amd64/focal/rabbitmq-server-638"
    mock_rmq.units = OrderedDict([("rabbitmq-server/0", mock_units_rmq)])

    mock_rmq_unknown = mock.MagicMock()
    mock_units_unknown_rmq = mock.MagicMock()
    mock_rmq_unknown.charm_channel = "80.5/stable"
    mock_units_unknown_rmq.workload_version = "80.5"
    mock_rmq_unknown.charm = "ch:amd64/focal/rabbitmq-server-638"
    mock_rmq_unknown.units = OrderedDict([("rabbitmq-server/0", mock_units_unknown_rmq)])

    status = {
        "keystone_ussuri": mock_keystone_ussuri,
        "cinder_ussuri": mock_cinder_ussuri,
        "rabbitmq_server": mock_rmq,
        "unknown_rabbitmq_server": mock_rmq_unknown,
        "keystone_ussuri_cs": mock_keystone_ussuri_cs,
        "keystone_wallaby": mock_keystone_wallaby,
    }
    return status


@pytest.fixture
def full_status(status):
    mock_full_status = mock.MagicMock()
    mock_full_status.model.name = "my_model"
    mock_full_status.applications = OrderedDict(
        [
            ("keystone", status["keystone_ussuri"]),
            ("cinder", status["cinder_ussuri"]),
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
        units_ussuri[unit]["workload_version"] = "17.0.1"
        units_wallaby[unit]["os_version"] = "wallaby"
        units_wallaby[unit]["workload_version"] = "19.1.0"
    return {"units_ussuri": units_ussuri, "units_wallaby": units_wallaby}


@pytest.fixture
def apps(status, config):
    keystone_status = status["keystone_ussuri"]
    cinder_status = status["cinder_ussuri"]
    app_config = config["openstack_ussuri"]
    app_keystone = analyze.Application("keystone", keystone_status, app_config, "my_model")
    app_cinder = analyze.Application("cinder", cinder_status, app_config, "my_model")

    return [app_keystone, app_cinder]


@pytest.fixture
def config():
    return {
        "openstack_ussuri": {
            "openstack-origin": {"value": "distro"},
        },
        "openstack_wallaby": {"openstack-origin": {"value": "cloud:focal-wallaby"}},
    }
