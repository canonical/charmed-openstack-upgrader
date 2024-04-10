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

from unittest.mock import MagicMock

import pytest

from cou.apps.auxiliary_subordinate import (
    AuxiliarySubordinateApplication,
    OVNSubordinate,
)
from cou.exceptions import ApplicationError, HaltUpgradePlanGeneration
from cou.steps import ApplicationUpgradePlan, PreUpgradeStep, UpgradeStep
from cou.utils.juju_utils import Machine
from cou.utils.openstack import OpenStackRelease
from tests.unit.utils import assert_steps


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

    assert app.channel == "8.0/stable"
    assert app.origin == "ch"
    assert app.os_origin == ""
    assert app.apt_source_codename is None
    assert app.channel_codename == "yoga"
    assert app.current_os_release == "yoga"
    assert app.is_subordinate is True


def test_auxiliary_subordinate_upgrade_plan_to_victoria(model):
    """Test auxiliary subordinate application upgrade plan to victoria."""
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=Machine)}
    app = AuxiliarySubordinateApplication(
        name="keystone-mysql-router",
        can_upgrade_to="8.0/stable",
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

    expected_plan = ApplicationUpgradePlan(f"Upgrade plan for '{app.name}' to '{target}'")
    expected_plan.add_step(
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of '8.0/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "8.0/stable"),
        ),
    )

    upgrade_plan = app.generate_upgrade_plan(target, False)

    assert_steps(upgrade_plan, expected_plan)


def test_ovn_subordinate(model):
    """Test the correctness of instantiating OVNSubordinate."""
    machines = {"0": MagicMock(spec_set=Machine)}
    app = OVNSubordinate(
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

    assert app.channel == "22.03/stable"
    assert app.os_origin == ""
    assert app.apt_source_codename is None
    assert app.channel_codename == "yoga"
    assert app.current_os_release == "yoga"
    assert app.is_subordinate is True


def test_ovn_workload_ver_lower_than_22_subordinate(model):
    """Test the OVNSubordinate with lower version than 22."""
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=Machine)}
    exp_msg = (
        "OVN versions lower than 22.03 are not supported. It's necessary to upgrade "
        "OVN to 22.03 before upgrading the cloud. Follow the instructions at: "
        "https://docs.openstack.org/charm-guide/latest/project/procedures/"
        "ovn-upgrade-2203.html"
    )
    app = OVNSubordinate(
        name="ovn-chassis",
        can_upgrade_to="22.03/stable",
        charm="ovn-chassis",
        channel="20.03/stable",
        config={"enable-version-pinning": {"value": False}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=["nova-compute"],
        units={},
        workload_version="20.3",
    )

    with pytest.raises(ApplicationError, match=exp_msg):
        app.generate_upgrade_plan(target, False)


def test_ovn_version_pinning_subordinate(model):
    """Test the OVNSubordinate when enable-version-pinning is set to True."""
    charm = "ovn-chassis"
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=Machine)}
    exp_msg = f"Cannot upgrade '{charm}'. 'enable-version-pinning' must be set to 'false'."
    app = OVNSubordinate(
        name=charm,
        can_upgrade_to="",
        charm=charm,
        channel="22.03/stable",
        config={"enable-version-pinning": {"value": True}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=["nova-compute"],
        units={},
        workload_version="22.3",
    )

    with pytest.raises(ApplicationError, match=exp_msg):
        app.generate_upgrade_plan(target, False)


def test_ovn_subordinate_upgrade_plan(model):
    """Test generating plan for OVNSubordinate."""
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=Machine)}
    app = OVNSubordinate(
        name="ovn-chassis",
        can_upgrade_to="22.03/stable",
        charm="ovn-chassis",
        channel="22.03/stable",
        config={"enable-version-pinning": {"value": False}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=["nova-compute"],
        units={},
        workload_version="22.3",
    )

    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to '{target}'"
    )
    upgrade_steps = [
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of '22.03/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "22.03/stable"),
        )
    ]
    expected_plan.add_steps(upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)

    assert_steps(upgrade_plan, expected_plan)


def test_ovn_subordinate_upgrade_plan_cant_upgrade_charm(model):
    """Test generating plan for OVNSubordinate failing.

    The ovn chassis 22.03 is considered yoga. If it's not necessary to upgrade the charm code,
    there is no steps to upgrade.
    """
    exp_msg = (
        "Application 'ovn-chassis' already configured for release equal to or greater than "
        "victoria. Ignoring."
    )
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=Machine)}
    app = OVNSubordinate(
        name="ovn-chassis",
        can_upgrade_to="",
        charm="ovn-chassis",
        channel="22.03/stable",
        config={"enable-version-pinning": {"value": False}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=["nova-compute"],
        units={},
        workload_version="22.3",
    )

    with pytest.raises(HaltUpgradePlanGeneration, match=exp_msg):
        app.generate_upgrade_plan(target, False)


def test_ceph_dashboard_upgrade_plan_ussuri_to_victoria(model):
    """Test when ceph version remains the same between os releases."""
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=Machine)}
    app = AuxiliarySubordinateApplication(
        name="ceph-dashboard",
        can_upgrade_to="octopus/stable",
        charm="ceph-dashboard",
        channel="octopus/stable",
        config={},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=["nova-compute"],
        units={},
        workload_version="15.2.0",
    )

    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to '{target}'"
    )
    upgrade_steps = [
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of 'octopus/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "octopus/stable"),
        )
    ]

    expected_plan.add_steps(upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)

    assert_steps(upgrade_plan, expected_plan)


def test_ceph_dashboard_upgrade_plan_xena_to_yoga(model):
    """Test when ceph version changes between os releases."""
    target = OpenStackRelease("yoga")
    machines = {"0": MagicMock(spec_set=Machine)}
    app = AuxiliarySubordinateApplication(
        name="ceph-dashboard",
        can_upgrade_to="pacific/stable",
        charm="ceph-dashboard",
        channel="pacific/stable",
        config={},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=["nova-compute"],
        units={},
        workload_version="16.2.0",
    )

    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to '{target}'"
    )

    upgrade_steps = [
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of 'pacific/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "pacific/stable"),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: 'quincy/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "quincy/stable"),
        ),
    ]
    expected_plan.add_steps(upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)

    assert_steps(upgrade_plan, expected_plan)
