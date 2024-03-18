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

import pytest

from cou.apps.auxiliary_subordinate import (
    AuxiliarySubordinateApplication,
    OvnSubordinate,
)
from cou.exceptions import ApplicationError
from cou.steps import ApplicationUpgradePlan, PreUpgradeStep, UpgradeStep
from cou.utils.openstack import OpenStackRelease
from tests.unit.apps.utils import add_steps


def test_auxiliary_subordinate(apps):
    app = apps["keystone_mysql_router"]
    assert app.channel == "8.0/stable"
    assert app.charm_origin == "ch"
    assert app.os_origin == ""
    assert app.apt_source_codename is None
    assert app.channel_codename == "yoga"
    assert app.current_os_release == "yoga"
    assert app.is_subordinate is True


def test_auxiliary_subordinate_upgrade_plan_to_victoria(apps, model):
    target = OpenStackRelease("victoria")
    app = apps["keystone_mysql_router"]

    upgrade_plan = app.generate_upgrade_plan(target)
    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}",
    )
    expected_plan.add_step(
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of '8.0/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "8.0/stable", switch=None),
        ),
    )

    assert upgrade_plan == expected_plan


def test_ovn_subordinate(status, model):
    app = OvnSubordinate(
        "ovn-chassis", status["ovn_chassis_focal_22"], {}, model, "ovn-chassis", {}
    )
    assert app.channel == "22.03/stable"
    assert app.os_origin == ""
    assert app.apt_source_codename is None
    assert app.channel_codename == "yoga"
    assert app.current_os_release == "yoga"
    assert app.is_subordinate is True


def test_ovn_workload_ver_lower_than_22_subordinate(status, model):
    target = OpenStackRelease("victoria")

    exp_error_msg_ovn_upgrade = (
        "OVN versions lower than 22.03 are not supported. It's necessary to upgrade "
        "OVN to 22.03 before upgrading the cloud. Follow the instructions at: "
        "https://docs.openstack.org/charm-guide/latest/project/procedures/"
        "ovn-upgrade-2203.html"
    )

    app_ovn_chassis = OvnSubordinate(
        "ovn-chassis",
        status["ovn_chassis_focal_20"],
        {},
        model,
        "ovn-chassis",
        {},
    )

    with pytest.raises(ApplicationError, match=exp_error_msg_ovn_upgrade):
        app_ovn_chassis.generate_upgrade_plan(target)


def test_ovn_subordinate_upgrade_plan(status, model):
    target = OpenStackRelease("victoria")
    app = OvnSubordinate(
        "ovn-chassis",
        status["ovn_chassis_focal_22"],
        {},
        model,
        "ovn-chassis",
        {},
    )

    upgrade_plan = app.generate_upgrade_plan(target)

    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}"
    )

    upgrade_steps = [
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of '22.03/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "22.03/stable", switch=None),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan


def test_ovn_subordinate_upgrade_plan_cant_upgrade_charm(status, model):
    # ovn chassis 22.03 is considered yoga. If it's not necessary to upgrade
    # the charm code, there is no steps to upgrade.
    target = OpenStackRelease("victoria")
    app_status = status["ovn_chassis_focal_22"]
    app_status.can_upgrade_to = ""
    app = OvnSubordinate(
        "ovn-chassis",
        app_status,
        {},
        model,
        "ovn-chassis",
        {},
    )

    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}"
    )

    upgrade_plan = app.generate_upgrade_plan(target)
    assert upgrade_plan == expected_plan
    assert str(upgrade_plan) == ""


def test_ceph_dashboard_upgrade_plan_ussuri_to_victoria(status, config, model):
    """Test when ceph version remains the same between os releases."""
    target = OpenStackRelease("victoria")
    app = AuxiliarySubordinateApplication(
        "ceph-dashboard",
        status["ceph_dashboard_octopus"],
        config["auxiliary_ussuri"],
        model,
        "ceph-dashboard",
        {},
    )

    upgrade_plan = app.generate_upgrade_plan(target)

    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}"
    )

    upgrade_steps = [
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of 'octopus/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "octopus/stable", switch=None),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan


def test_ceph_dashboard_upgrade_plan_xena_to_yoga(status, config, model):
    """Test when ceph version changes between os releases."""
    target = OpenStackRelease("yoga")
    app = AuxiliarySubordinateApplication(
        "ceph-dashboard",
        status["ceph_dashboard_pacific"],
        config["auxiliary_xena"],
        model,
        "ceph-dashboard",
        {},
    )

    upgrade_plan = app.generate_upgrade_plan(target)

    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}"
    )

    upgrade_steps = [
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of 'pacific/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "pacific/stable", switch=None),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: 'quincy/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "quincy/stable"),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan
