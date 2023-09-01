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
from cou.exceptions import ApplicationError
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
    assert plan.description == "Upgrade my_keystone_ldap"

    assert (
        plan.sub_steps[0].description
        == "Refresh 'my_keystone_ldap' to the latest revision of 'ussuri/stable'"
    )
    assert (
        plan.sub_steps[1].description
        == "Upgrade 'my_keystone_ldap' to the new channel: 'victoria/stable'"
    )


def test_try_getting_channel(status):
    app_status = status["keystone-ldap"]
    app = OpenStackSubordinateApplication(
        "my_keystone_ldap", app_status, {}, "my_model", "keystone-ldap"
    )

    assert app._try_getting_channel("ussuri/stable") == "ussuri/stable"

    with pytest.raises(ApplicationError):
        app._try_getting_channel("focal/stable")

    with pytest.raises(ApplicationError):
        app._try_getting_channel("latest/stable")
