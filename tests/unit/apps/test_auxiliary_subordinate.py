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

from tests.unit.apps.utils import assert_plan_description


def test_auxiliary_subordinate(apps):
    app = apps["keystone_mysql_router"]
    assert app.channel == "8.0/stable"
    assert app.charm_origin == "ch"
    assert app.os_origin == ""
    assert app.apt_source_codename is None
    assert app.channel_codename == "yoga"
    assert app.current_os_release == "yoga"


def test_auxiliary_subordinate_upgrade_plan_to_victoria(apps):
    target = "victoria"
    app = apps["keystone_mysql_router"]

    plan = app.generate_upgrade_plan(target)

    steps_description = [
        f"Refresh '{app.name}' to the latest revision of '8.0/stable'",
    ]

    assert_plan_description(plan, steps_description)
