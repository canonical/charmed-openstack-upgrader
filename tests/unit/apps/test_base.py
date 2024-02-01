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

from unittest.mock import MagicMock

import pytest
from juju.client._definitions import ApplicationStatus

from cou.apps.base import ApplicationUnit, OpenStackApplication
from cou.steps import UpgradeStep


@pytest.mark.parametrize(
    "charm_config",
    [{"action-managed-upgrade": {"value": False}}, {"action-managed-upgrade": {"value": True}}],
)
def test_get_enable_action_managed_plan(charm_config, model):
    charm = "app"
    app_name = "my_app"
    status = MagicMock(spec_set=ApplicationStatus())
    status.charm_channel = "ussuri/stable"

    expected_upgrade_step = UpgradeStep(
        f"Change charm config of '{app_name}' 'action-managed-upgrade' to True.",
        False,
        model.set_application_config(app_name, {"action-managed-upgrade": True}),
    )
    if charm_config["action-managed-upgrade"]["value"]:
        expected_upgrade_step = UpgradeStep()

    app = OpenStackApplication(app_name, status, charm_config, model, charm, {})

    assert app._get_enable_action_managed_plan() == expected_upgrade_step


def test_get_pause_unit(model):
    charm = "app"
    app_name = "my_app"
    status = MagicMock(spec_set=ApplicationStatus())
    status.charm_channel = "ussuri/stable"

    unit = ApplicationUnit("my_app/0", MagicMock(), MagicMock(), MagicMock())

    expected_upgrade_step = UpgradeStep(
        f"Pause the unit: '{unit.name}'.", False, model.run_action("my_app/0", "pause")
    )

    app = OpenStackApplication(app_name, status, {}, model, charm, {})
    assert app._get_pause_unit(unit) == expected_upgrade_step


def test_get_resume_unit(model):
    charm = "app"
    app_name = "my_app"
    status = MagicMock(spec_set=ApplicationStatus())
    status.charm_channel = "ussuri/stable"

    unit = ApplicationUnit("my_app/0", MagicMock(), MagicMock(), MagicMock())

    expected_upgrade_step = UpgradeStep(
        f"Resume the unit: '{unit.name}'.", False, model.run_action(unit.name, "resume")
    )

    app = OpenStackApplication(app_name, status, {}, model, charm, {})
    assert app._get_resume_unit(unit) == expected_upgrade_step
