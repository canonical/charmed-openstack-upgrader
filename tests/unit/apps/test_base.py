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

from unittest.mock import MagicMock, patch

import pytest
from juju.client._definitions import ApplicationStatus, UnitStatus

from cou.apps.base import ApplicationUnit, OpenStackApplication
from cou.exceptions import ApplicationError
from cou.steps import UnitUpgradeStep, UpgradeStep


@patch("cou.apps.base.OpenStackApplication._verify_channel", return_value=None)
@patch("cou.utils.openstack.OpenStackCodenameLookup.find_compatible_versions")
def test_application_get_latest_os_version_failed(
    mock_find_compatible_versions, config, status, model, apps_machines
):
    charm = "app"
    app_name = "my_app"
    unit = MagicMock(spec_set=UnitStatus())
    unit.workload_version = "15.0.1"
    exp_error = (
        f"'{app_name}' with workload version {unit.workload_version} has no compatible OpenStack "
        "release."
    )
    mock_find_compatible_versions.return_value = []

    app = OpenStackApplication(app_name, MagicMock(), MagicMock(), MagicMock(), charm, {})

    with pytest.raises(ApplicationError, match=exp_error):
        app._get_latest_os_version(unit)

    mock_find_compatible_versions.assert_called_once_with(charm, unit.workload_version)


@pytest.mark.parametrize(
    "charm_config",
    [{"action-managed-upgrade": {"value": False}}, {"action-managed-upgrade": {"value": True}}],
)
def test_get_enable_action_managed_step(charm_config, model):
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

    assert app._get_enable_action_managed_step() == expected_upgrade_step


def test_get_pause_unit_step(model):
    charm = "app"
    app_name = "my_app"
    status = MagicMock(spec_set=ApplicationStatus())
    status.charm_channel = "ussuri/stable"

    unit = ApplicationUnit("my_app/0", MagicMock(), MagicMock(), MagicMock())

    expected_upgrade_step = UnitUpgradeStep(
        description=f"Pause the unit: '{unit.name}'.",
        coro=model.run_action(unit_name="my_app/0", action_name="pause", raise_on_failure=True),
    )

    app = OpenStackApplication(app_name, status, {}, model, charm, {})
    assert app._get_pause_unit_step(unit) == expected_upgrade_step


def test_get_resume_unit_step(model):
    charm = "app"
    app_name = "my_app"
    status = MagicMock(spec_set=ApplicationStatus())
    status.charm_channel = "ussuri/stable"

    unit = ApplicationUnit("my_app/0", MagicMock(), MagicMock(), MagicMock())

    expected_upgrade_step = UnitUpgradeStep(
        description=f"Resume the unit: '{unit.name}'.",
        coro=model.run_action(unit_name=unit.name, action_name="resume", raise_on_failure=True),
    )

    app = OpenStackApplication(app_name, status, {}, model, charm, {})
    assert app._get_resume_unit_step(unit) == expected_upgrade_step
