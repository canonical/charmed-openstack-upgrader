#  Copyright 2024 Canonical Limited
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
"""Tests for AuxiliarySubordinateApplication generating plans."""
import pytest

from cou.apps.auxiliary_subordinate import (
    AuxiliarySubordinateApplication,
    OvnSubordinate,
)
from cou.utils.juju_utils import Unit
from cou.utils.openstack import OpenStackRelease
from tests.unit.utils import dedent_plan, generate_cou_machine


@pytest.mark.parametrize(
    "app_name, channel, version",
    [
        ("hacluster", "2.4/stable", "2.4"),
        ("mysql-router", "8.0/stable", "8.0"),
        ("ceph-dashboard", "octopus/stable", "17.0.1"),
    ],
)
def test_auxiliary_application_upgrade_plan(app_name, channel, version, model):
    """Testing generating upgrade plan for AuxiliaryApplication."""
    exp_plan = dedent_plan(
        f"""\
    Upgrade plan for '{app_name}' to 'victoria'
        Refresh '{app_name}' to the latest revision of '{channel}'
    """  # noqa: E501 line too long
    )
    target = OpenStackRelease("victoria")
    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
    app = AuxiliarySubordinateApplication(
        name=app_name,
        can_upgrade_to=channel,
        charm=app_name,
        channel=channel,
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"{app_name}/{i}": Unit(
                name=f"{app_name}/{i}",
                workload_version=version,
                machine=machines[f"{i}"],
            )
            for i in range(3)
        },
        workload_version=version,
    )

    plan = app.generate_upgrade_plan(target, False)

    assert str(plan) == exp_plan


def test_ovn_chassis_upgrade_plan(model):
    """Testing generating upgrade plan for AuxiliaryApplication."""
    app_name = "ovn-chassis"
    exp_plan = dedent_plan(
        f"""\
    Upgrade plan for '{app_name}' to 'victoria'
        Refresh '{app_name}' to the latest revision of '22.03/stable'
    """  # noqa: E501 line too long
    )
    target = OpenStackRelease("victoria")
    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
    app = OvnSubordinate(
        name=app_name,
        can_upgrade_to="22.03/stable",
        charm=app_name,
        channel="22.03/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"{app_name}/{i}": Unit(
                name=f"{app_name}/{i}",
                workload_version="22.03",
                machine=machines[f"{i}"],
            )
            for i in range(3)
        },
        workload_version="22.03",
    )

    plan = app.generate_upgrade_plan(target, False)

    assert str(plan) == exp_plan
