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
from cou.exceptions import HaltUpgradePlanGeneration
from cou.steps import UpgradeStep
from cou.utils.openstack import OpenStackRelease
from tests.unit.apps.utils import add_steps

logger = logging.getLogger(__name__)


def test_post_init(status, model):
    app_status = status["keystone-ldap"]
    app = OpenStackSubordinateApplication(
        "my_keystone_ldap", app_status, {}, model, "keystone-ldap"
    )
    assert app.channel == "ussuri/stable"
    assert app.charm_origin == "ch"
    assert app.os_origin == ""


def test_current_os_release(status, model):
    app_status = status["keystone-ldap"]
    app = OpenStackSubordinateApplication(
        "my_keystone_ldap", app_status, {}, model, "keystone-ldap"
    )
    assert app.current_os_release == OpenStackRelease("ussuri")


def test_generate_upgrade_plan(status, model):
    target = "victoria"
    app_status = status["keystone-ldap"]
    app = OpenStackSubordinateApplication(
        "my_keystone_ldap", app_status, {}, model, "keystone-ldap"
    )
    upgrade_plan = app.generate_upgrade_plan(target)

    expected_plan = UpgradeStep(
        description=f"Upgrade plan for '{app.name}' to {target}",
        parallel=False,
        function=None,
    )
    upgrade_steps = [
        UpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of 'ussuri/stable'",
            parallel=False,
            function=model.upgrade_charm,
            application_name=app.name,
            channel="ussuri/stable",
            switch=None,
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: 'victoria/stable'",
            parallel=False,
            function=model.upgrade_charm,
            application_name=app.name,
            channel="victoria/stable",
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan


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
def test_channel_setter_valid(status, model, channel):
    app_status = status["keystone-ldap"]
    app = OpenStackSubordinateApplication(
        "my_keystone_ldap", app_status, {}, model, "keystone-ldap"
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
def test_channel_setter_invalid(status, model, channel):
    app_status = status["keystone-ldap"]
    app = OpenStackSubordinateApplication(
        "my_keystone_ldap", app_status, {}, model, "keystone-ldap"
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
def test_generate_plan_ch_migration(status, model, channel):
    target = "wallaby"
    app_status = status["keystone-ldap-cs"]
    app = OpenStackSubordinateApplication(
        "my_keystone_ldap", app_status, {}, model, "keystone-ldap"
    )

    app.channel = channel
    upgrade_plan = app.generate_upgrade_plan(target)

    expected_plan = UpgradeStep(
        description=f"Upgrade plan for '{app.name}' to {target}",
        parallel=False,
        function=None,
    )
    upgrade_steps = [
        UpgradeStep(
            description=f"Migration of '{app.name}' from charmstore to charmhub",
            parallel=False,
            function=model.upgrade_charm,
            application_name=app.name,
            channel="ussuri/stable",
            switch="ch:keystone-ldap",
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: 'wallaby/stable'",
            parallel=False,
            function=model.upgrade_charm,
            application_name=app.name,
            channel="wallaby/stable",
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan


@pytest.mark.parametrize(
    "from_os, to_os",
    [
        (["ussuri", "victoria"]),
        (["victoria", "wallaby"]),
        (["wallaby", "xena"]),
        (["xena", "yoga"]),
    ],
)
def test_generate_plan_from_to(status, model, from_os, to_os):
    app_status = status["keystone-ldap"]
    app = OpenStackSubordinateApplication(
        "my_keystone_ldap", app_status, {}, model, "keystone-ldap"
    )

    app.channel = f"{from_os}/stable"
    upgrade_plan = app.generate_upgrade_plan(to_os)

    expected_plan = UpgradeStep(
        description=f"Upgrade plan for '{app.name}' to {to_os}",
        parallel=False,
        function=None,
    )
    upgrade_steps = [
        UpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of '{from_os}/stable'",
            parallel=False,
            function=model.upgrade_charm,
            application_name=app.name,
            channel=f"{from_os}/stable",
            switch=None,
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: '{to_os}/stable'",
            parallel=False,
            function=model.upgrade_charm,
            application_name=app.name,
            channel=f"{to_os}/stable",
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan


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
def test_generate_plan_in_same_version(status, model, from_to):
    app_status = status["keystone-ldap"]
    app = OpenStackSubordinateApplication(
        "my_keystone_ldap", app_status, {}, model, "keystone-ldap"
    )

    app.channel = f"{from_to}/stable"
    with pytest.raises(HaltUpgradePlanGeneration):
        app.generate_upgrade_plan(from_to)
