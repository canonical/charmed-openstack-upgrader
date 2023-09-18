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
"""Subordinate application class."""
import logging

import pytest

from cou.apps.subordinate import OpenStackSubordinateApplication
from cou.utils.openstack import OpenStackRelease

logger = logging.getLogger(__name__)


def test_post_init(status):
    app_status = status["keystone-ldap"]
    app = OpenStackSubordinateApplication(
        "my_keystone_ldap", app_status, {}, "my_model", "keystone-ldap"
    )
    assert app.channel == "ussuri/stable"
    assert app.charm_origin == "ch"
    assert app.os_origin == ""


def test_current_os_release(status):
    app_status = status["keystone-ldap"]
    app = OpenStackSubordinateApplication(
        "my_keystone_ldap", app_status, {}, "my_model", "keystone-ldap"
    )
    assert app.current_os_release == OpenStackRelease("ussuri")


def test_generate_upgrade_plan(status):
    app_status = status["keystone-ldap"]
    app = OpenStackSubordinateApplication(
        "my_keystone_ldap", app_status, {}, "my_model", "keystone-ldap"
    )
    plan = app.generate_upgrade_plan("victoria")
    assert plan.description == "Upgrade plan for 'my_keystone_ldap' to victoria"

    assert (
        plan.sub_steps[0].description
        == "Refresh 'my_keystone_ldap' to the latest revision of 'ussuri/stable'"
    )
    assert (
        plan.sub_steps[1].description
        == "Upgrade 'my_keystone_ldap' to the new channel: 'victoria/stable'"
    )


@pytest.mark.parametrize(
    "channel",
    [
        "ussuri/stable",
        "victoria/stable",
        "xena/stable",
        "yoga/stable",
        "wallaby/stable",
        "wallaby/edge",
    ],
)
def test_channel_setter_valid(status, channel):
    app_status = status["keystone-ldap"]
    app = OpenStackSubordinateApplication(
        "my_keystone_ldap", app_status, {}, "my_model", "keystone-ldap"
    )

    app.channel = channel
    assert app.channel == channel


@pytest.mark.parametrize(
    "channel",
    [
        "focal/edge",
        "latest/edge",
        "latest/stable",
        "something/stable",
    ],
)
def test_channel_setter_invalid(status, channel):
    app_status = status["keystone-ldap"]
    app = OpenStackSubordinateApplication(
        "my_keystone_ldap", app_status, {}, "my_model", "keystone-ldap"
    )

    app.channel = channel
    assert app.channel == "ussuri/stable"


@pytest.mark.parametrize(
    "channel",
    [
        "stable",
        "edge",
        "candidate",
    ],
)
def test_generate_plan_ch_migration(status, channel):
    app_status = status["keystone-ldap-cs"]
    app = OpenStackSubordinateApplication(
        "my_keystone_ldap", app_status, {}, "my_model", "keystone-ldap"
    )

    app.channel = channel
    plan = app.generate_upgrade_plan("wallaby")
    assert str(plan) == (
        "Upgrade plan for 'my_keystone_ldap' to wallaby\n"
        "\tMigration of 'my_keystone_ldap' from charmstore to charmhub\n"
        "\tUpgrade 'my_keystone_ldap' to the new channel: 'wallaby/stable'\n"
    )


@pytest.mark.parametrize(
    "from_os, to_os",
    [
        (["ussuri", "victoria"]),
        (["victoria", "wallaby"]),
        (["wallaby", "xena"]),
        (["xena", "yoga"]),
    ],
)
def test_generate_plan_from_to(status, from_os, to_os):
    app_status = status["keystone-ldap"]
    app = OpenStackSubordinateApplication(
        "my_keystone_ldap", app_status, {}, "my_model", "keystone-ldap"
    )

    app.channel = f"{from_os}/stable"
    plan = app.generate_upgrade_plan(to_os)
    assert str(plan) == (
        f"Upgrade plan for 'my_keystone_ldap' to {to_os}\n"
        f"\tRefresh 'my_keystone_ldap' to the latest revision of '{from_os}/stable'\n"
        f"\tUpgrade 'my_keystone_ldap' to the new channel: '{to_os}/stable'\n"
    )


@pytest.mark.parametrize(
    "from_to",
    [
        "ussuri",
        "victoria",
        "wallaby",
        "xena",
        "yoga",
    ],
)
def test_generate_plan_in_same_version(status, from_to):
    app_status = status["keystone-ldap"]
    app = OpenStackSubordinateApplication(
        "my_keystone_ldap", app_status, {}, "my_model", "keystone-ldap"
    )

    app.channel = f"{from_to}/stable"
    plan = app.generate_upgrade_plan(from_to)
    assert str(plan) == (
        f"Upgrade plan for 'my_keystone_ldap' to {from_to}\n"
        f"\tRefresh 'my_keystone_ldap' to the latest revision of '{from_to}/stable'\n"
    )
