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

from cou.apps.auxiliary_subordinate import OvnSubordinateApplication
from cou.exceptions import ApplicationError
from cou.steps import UpgradeStep
from tests.unit.apps.utils import add_steps


def test_auxiliary_subordinate(apps):
    app = apps["keystone_mysql_router"]
    assert app.channel == "8.0/stable"
    assert app.charm_origin == "ch"
    assert app.os_origin == ""
    assert app.apt_source_codename is None
    assert app.channel_codename == "yoga"
    assert app.current_os_release == "yoga"


def test_auxiliary_subordinate_upgrade_plan_to_victoria(apps, model):
    target = "victoria"
    app = apps["keystone_mysql_router"]

    upgrade_plan = app.generate_upgrade_plan(target)
    expected_plan = UpgradeStep(
        description=f"Upgrade plan for '{app.name}' to {target}",
        parallel=False,
        function=None,
    )
    expected_plan.add_step(
        UpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of '8.0/stable'",
            parallel=False,
            function=model.upgrade_charm,
            application_name=app.name,
            channel="8.0/stable",
            switch=None,
        ),
    )

    assert upgrade_plan == expected_plan


def test_ovn_subordinate(status, model):
    app = OvnSubordinateApplication(
        "ovn-chassis",
        status["ovn_chassis_ussuri_22"],
        {},
        model,
        "ovn-chassis",
    )
    assert app.channel == "22.03/stable"
    assert app.os_origin == ""
    assert app.apt_source_codename is None
    assert app.channel_codename == "yoga"
    assert app.current_os_release == "yoga"


def test_ovn_workload_ver_lower_than_22_subordinate(status, model):
    target = "victoria"

    exp_error_msg_ovn_upgrade = (
        "OVN versions lower than 22.03 are not supported. It's necessary to upgrade "
        "OVN to 22.03 before upgrading the cloud. Follow the instructions at: "
        "https://docs.openstack.org/charm-guide/latest/project/procedures/"
        "ovn-upgrade-2203.html"
    )

    app_ovn_chassis = OvnSubordinateApplication(
        "ovn-chassis",
        status["ovn_chassis_ussuri_20"],
        {},
        model,
        "ovn-chassis",
    )

    with pytest.raises(ApplicationError, match=exp_error_msg_ovn_upgrade):
        app_ovn_chassis.generate_upgrade_plan(target)


def test_ovn_subordinate_upgrade_plan(status, model):
    target = "victoria"
    app = OvnSubordinateApplication(
        "ovn-chassis",
        status["ovn_chassis_ussuri_22"],
        {},
        model,
        "ovn-chassis",
    )

    upgrade_plan = app.generate_upgrade_plan(target)

    expected_plan = UpgradeStep(
        description=f"Upgrade plan for '{app.name}' to {target}",
        parallel=False,
        function=None,
    )

    upgrade_steps = [
        UpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of '22.03/stable'",
            parallel=False,
            function=model.upgrade_charm,
            application_name=app.name,
            channel="22.03/stable",
            switch=None,
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan
