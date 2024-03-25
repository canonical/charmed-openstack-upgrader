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
"""Tests of the Auxiliary Subordinate application class."""

from unittest.mock import MagicMock, patch

import pytest

from cou.apps.auxiliary_subordinate import (
    AuxiliarySubordinateApplication,
    OvnSubordinate,
)
from cou.exceptions import ApplicationError
from cou.utils.juju_utils import Machine
from cou.utils.openstack import OpenStackRelease


def test_auxiliary_subordinate(model):
    """Test auxiliary subordinate application."""
    machines = {"0": MagicMock(spec_set=Machine)}
    app = AuxiliarySubordinateApplication(
        name="keystone-mysql-router",
        can_upgrade_to="",
        charm="mysql-router",
        channel="8.0/stable",
        config={},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=["keystone"],
        units={},
        workload_version="8.0",
    )

    assert app.channel_codename == "yoga"
    assert app.current_os_release == "yoga"


def test_ovn_subordinate(model):
    """Test the correctness of instantiating OvnSubordinate."""
    machines = {"0": MagicMock(spec_set=Machine)}
    app = OvnSubordinate(
        name="ovn-chassis",
        can_upgrade_to="22.03/stable",
        charm="ovn-chassis",
        channel="22.03/stable",
        config={},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=["nova-compute"],
        units={},
        workload_version="22.3",
    )

    assert app.channel_codename == "yoga"
    assert app.current_os_release == "yoga"


@patch("cou.apps.base.OpenStackApplication.pre_upgrade_steps")
def test_ovn_workload_ver_lower_than_22_subordinate(_, model):
    """Test the OvnSubordinate with lower version than 22."""
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=Machine)}
    exp_msg = (
        "OVN versions lower than 22.03 are not supported. It's necessary to upgrade "
        "OVN to 22.03 before upgrading the cloud. Follow the instructions at: "
        "https://docs.openstack.org/charm-guide/latest/project/procedures/"
        "ovn-upgrade-2203.html"
    )
    app = OvnSubordinate(
        name="ovn-chassis",
        can_upgrade_to="22.03/stable",
        charm="ovn-chassis",
        channel="20.03/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=["nova-compute"],
        units={},
        workload_version="20.3",
    )

    with pytest.raises(ApplicationError, match=exp_msg):
        app.pre_upgrade_steps(target, False)
