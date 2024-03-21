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
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from juju.client._definitions import UnitStatus

from cou.apps.base import OpenStackApplication
from cou.exceptions import ApplicationError, HaltUpgradePlanGeneration
from cou.steps import PreUpgradeStep, UpgradeStep
from cou.utils.openstack import OpenStackRelease
from tests.unit.utils import assert_steps


@patch("cou.apps.base.OpenStackApplication._verify_channel", return_value=None)
@patch("cou.utils.openstack.OpenStackCodenameLookup.find_compatible_versions")
def test_application_get_latest_os_version_failed(
    mock_find_compatible_versions, config, status, model
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


@pytest.mark.parametrize("config", ({}, {"enable-auto-restarts": {"value": True}}))
@patch("cou.apps.base.OpenStackApplication.channel", new_callable=PropertyMock)
@patch("cou.apps.base.OpenStackApplication._verify_channel")
def test_check_auto_restarts(_, _channel, config):
    """Test function to verify that enable-auto-restarts is disabled."""
    app_name = "app"
    app = OpenStackApplication(app_name, MagicMock(), config, MagicMock(), "", "ch", "")

    app._check_auto_restarts()


@patch("cou.apps.base.OpenStackApplication.channel", new_callable=PropertyMock)
@patch("cou.apps.base.OpenStackApplication._verify_channel")
def test_check_auto_restarts_error(*_):
    """Test function to verify that enable-auto-restarts is disabled raising error."""
    app_name = "app"
    exp_error_msg = (
        "COU does not currently support upgrading applications that disable service restarts. "
        f"Please enable charm option enable-auto-restart and rerun COU to upgrade the {app_name} "
        "application."
    )
    config = {"enable-auto-restarts": {"value": False}}
    app = OpenStackApplication(app_name, MagicMock(), config, MagicMock(), "", "ch", "")

    with pytest.raises(ApplicationError, match=exp_error_msg):
        app._check_auto_restarts()


@patch("cou.apps.base.OpenStackApplication.channel", new_callable=PropertyMock)
@patch("cou.apps.base.OpenStackApplication._verify_channel")
@patch("cou.apps.base.OpenStackApplication.apt_source_codename", new_callable=PropertyMock)
@patch("cou.apps.base.OpenStackApplication.current_os_release", new_callable=PropertyMock)
@patch(
    "cou.apps.base.OpenStackApplication.can_upgrade_current_channel",
    new_callable=PropertyMock(return_value=False),
)
def test_check_application_target(
    can_upgrade_current_channel, current_os_release, apt_source_codename, *_
):
    """Test function to verify target."""
    target = OpenStackRelease("victoria")
    release = OpenStackRelease("ussuri")
    app_name = "app"
    app = OpenStackApplication(app_name, MagicMock(), {}, MagicMock(), "", "ch", "")
    current_os_release.return_value = apt_source_codename.return_value = release

    app._check_application_target(target)


@patch("cou.apps.base.OpenStackApplication.channel", new_callable=PropertyMock)
@patch("cou.apps.base.OpenStackApplication._verify_channel")
@patch("cou.apps.base.OpenStackApplication.apt_source_codename", new_callable=PropertyMock)
@patch("cou.apps.base.OpenStackApplication.current_os_release", new_callable=PropertyMock)
@patch(
    "cou.apps.base.OpenStackApplication.can_upgrade_current_channel",
    new_callable=PropertyMock(return_value=False),
)
def test_check_application_target_error(
    can_upgrade_current_channel, current_os_release, apt_source_codename, *_
):
    """Test function to verify target raising error."""
    target = OpenStackRelease("victoria")
    app_name = "app"
    exp_error_msg = (
        f"Application '{app_name}' already configured for release equal to or greater than "
        f"{target}. Ignoring."
    )
    app = OpenStackApplication(app_name, MagicMock(), {}, MagicMock(), "", "ch", "")
    current_os_release.return_value = apt_source_codename.return_value = target

    with pytest.raises(HaltUpgradePlanGeneration, match=exp_error_msg):
        app._check_application_target(target)


@patch("cou.apps.base.OpenStackApplication._verify_channel")
@patch(
    "cou.apps.base.OpenStackApplication.can_upgrade_current_channel",
    new_callable=PropertyMock(return_value=False),
)
def test_get_refresh_charm_step_empty_can_upgrade_to(can_upgrade_current_channel, _):
    """Test function to get refresh step for charm, when can_upgrade_to is empty."""
    target = OpenStackRelease("victoria")
    app_name = "app"
    app = OpenStackApplication(app_name, MagicMock(), {}, MagicMock(), "", "ch", "")

    step = app._get_refresh_charm_step(target)

    assert step == PreUpgradeStep()


@pytest.mark.parametrize(
    "charm_config, enable, exp_description",
    [
        ({}, True, None),
        ({}, False, None),
        (
            {"action-managed-upgrade": {"value": False}},
            True,
            "Change charm config of 'my_app' 'action-managed-upgrade' to 'True'",
        ),
        ({"action-managed-upgrade": {"value": False}}, False, None),
        ({"action-managed-upgrade": {"value": True}}, True, None),
        (
            {"action-managed-upgrade": {"value": True}},
            False,
            "Change charm config of 'my_app' 'action-managed-upgrade' to 'False'",
        ),
    ],
)
def test_set_action_managed_upgrade(charm_config, enable, exp_description, model):
    charm = "app"
    app_name = "my_app"
    status = MagicMock()
    status.charm_channel = "ussuri/stable"
    if exp_description:
        # Note (rgildein): we need to set exp_step here, since we need to use model fixture
        exp_step = UpgradeStep(
            exp_description,
            coro=model.set_application_config(app_name, {"action-managed-upgrade": enable}),
        )
    else:
        exp_step = UpgradeStep()

    app = OpenStackApplication(app_name, status, charm_config, model, charm, {})
    step = app._set_action_managed_upgrade(enable)

    assert_steps(step, exp_step)
