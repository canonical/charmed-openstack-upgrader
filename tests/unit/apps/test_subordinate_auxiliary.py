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

from cou.apps.subordinate_auxiliary import OpenStackAuxiliarySubordinateApplication
from cou.steps import UpgradeStep
from cou.utils.openstack import OpenStackRelease
from tests.unit.apps.utils import assert_plan_description


def test_auxiliary_subordinate(status):
    app = OpenStackAuxiliarySubordinateApplication(
        "keystone-mysql-router", status["mysql_router"], {}, "my_model", "mysql-router"
    )
    assert app.channel == "8.0/stable"
    assert app.charm_origin == "ch"
    assert app.os_origin == ""
    assert app.apt_source_codename is None
    assert app.channel_codename == "yoga"
    assert app.current_os_release == "yoga"


def test_subordinate_auxiliary_upgrade_plan_to_victoria(status):
    target = "victoria"
    app = OpenStackAuxiliarySubordinateApplication(
        "keystone-mysql-router", status["mysql_router"], {}, "my_model", "mysql-router"
    )

    plan = app.generate_upgrade_plan(target)

    steps_description = [
        f"Refresh '{app.name}' to the latest revision of '8.0/stable'",
    ]

    assert_plan_description(plan, steps_description)


def test_subordinate_auxiliary_upgrade_charm(status, mocker):
    target = "victoria"
    app = OpenStackAuxiliarySubordinateApplication(
        "keystone-mysql-router", status["mysql_router"], {}, "my_model", "mysql-router"
    )
    # currently there is no auxiliary subordinate charm that needs to change charm
    # channel in the same ubuntu series. That is why we need to mock this situation.
    mocker.patch(
        (
            "cou.apps.subordinate_auxiliary.OpenStackAuxiliarySubordinateApplication."
            "_get_upgrade_charm_plan"
        ),
        return_value=UpgradeStep(
            (
                f"Upgrade '{app.name}' to the new channel: "
                f"'{app.target_channel(OpenStackRelease(target))}'"
            ),
            False,
            None,
        ),
    )
    steps_description = [
        f"Refresh '{app.name}' to the latest revision of '8.0/stable'",
        (
            f"Upgrade '{app.name}' to the new channel: "
            f"'{app.target_channel(OpenStackRelease(target))}'"
        ),
    ]
    plan = app.generate_upgrade_plan(target)
    assert_plan_description(plan, steps_description)
