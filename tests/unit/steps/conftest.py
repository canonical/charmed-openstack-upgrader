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

from collections import OrderedDict

import mock
import pytest


@pytest.fixture
def status():
    mock_keystone_ch = mock.MagicMock()
    mock_keystone_ch.base = {"channel": "ussuri/stable"}
    mock_keystone_ch.charm = "ch:amd64/focal/keystone-638"
    mock_keystone_ch.units = OrderedDict(
        [("keystone/0", {}), ("keystone/1", {}), ("keystone/2", {})]
    )

    mock_keystone_cs = mock.MagicMock()
    mock_keystone_cs.base = {"channel": "ussuri/stable"}
    mock_keystone_cs.charm = "cs:amd64/focal/keystone-638"
    mock_keystone_cs.units = OrderedDict(
        [("keystone/0", {}), ("keystone/1", {}), ("keystone/2", {})]
    )

    mock_keystone_wrong_channel = mock.MagicMock()
    mock_keystone_wrong_channel.base = {"channel": "latest/stable"}
    mock_keystone_wrong_channel.charm = "ch:amd64/focal/keystone-638"
    mock_keystone_wrong_channel.units = OrderedDict(
        [("keystone/0", {}), ("keystone/1", {}), ("keystone/2", {})]
    )

    status = {
        "keystone_ch": mock_keystone_ch,
        "keystone_cs": mock_keystone_cs,
        "keystone_wrong_channel": mock_keystone_wrong_channel,
    }
    return status


@pytest.fixture
def config():
    return {
        "keystone": {
            "openstack-origin": {"value": "distro"},
        },
        "keystone_wrong_os_origin": {"value": "cloud:focal-ussuri"},
    }
