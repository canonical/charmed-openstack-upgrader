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

from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest

from cou.apps.base import OpenStackApplication
from cou.exceptions import (
    ApplicationError,
    HaltUpgradePlanGeneration,
    MismatchedOpenStackVersions,
)
from cou.steps import PreUpgradeStep, UnitUpgradeStep, UpgradeStep
from cou.utils.juju_utils import Machine, Unit
from cou.utils.openstack import OpenStackRelease
from tests.unit.utils import assert_steps


@patch("cou.apps.base.OpenStackApplication._verify_channel", return_value=None)
def test_openstack_application_magic_functions(model):
    """Test OpenStackApplication magic functions, like __hash__, __eq__."""
    app = OpenStackApplication(
        name="test-app",
        can_upgrade_to="",
        charm="app",
        channel="stable",
        config={},
        machines={},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={},
        workload_version="1",
    )

    assert hash(app) == hash("test-app(app)")
    assert app == app
    assert app is not None
    assert app != "test-app"


@patch("cou.apps.base.OpenStackApplication._verify_channel", return_value=None)
@patch("cou.utils.openstack.OpenStackCodenameLookup.find_compatible_versions")
def test_application_get_latest_os_version_failed(mock_find_compatible_versions, model):
    charm = "app"
    app_name = "my_app"
    unit = Unit(
        name=f"{app_name}/0",
        workload_version="1",
        machine=MagicMock(spec_set=Machine),
    )
    exp_error = (
        f"'{app_name}' with workload version {unit.workload_version} has no compatible OpenStack "
        "release."
    )
    mock_find_compatible_versions.return_value = []
    app = OpenStackApplication(
        name=app_name,
        can_upgrade_to="",
        charm=charm,
        channel="stable",
        config={},
        machines={},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={f"{app_name}/0": unit},
        workload_version=unit.workload_version,
    )

    with pytest.raises(ApplicationError, match=exp_error):
        app.get_latest_os_version(unit)

    mock_find_compatible_versions.assert_called_once_with(charm, unit.workload_version)


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
    channel = "ussuri/stable"
    if exp_description:
        # Note (rgildein): we need to set exp_step here, since we need to use model fixture
        exp_step = UpgradeStep(
            description=exp_description,
            coro=model.set_application_config(app_name, {"action-managed-upgrade": enable}),
        )
    else:
        exp_step = UpgradeStep()

    app = OpenStackApplication(
        name=app_name,
        can_upgrade_to="",
        charm=charm,
        channel=channel,
        config=charm_config,
        machines={},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={},
        workload_version="1",
    )

    step = app._set_action_managed_upgrade(enable)
    assert_steps(step, exp_step)


def test_get_pause_unit_step(model):
    charm = "app"
    app_name = "my_app"
    channel = "ussuri/stable"
    machines = {"0": MagicMock(spec_set=Machine)}
    unit = Unit(
        name=f"{app_name}/0",
        workload_version="1",
        machine=machines["0"],
    )
    expected_upgrade_step = UnitUpgradeStep(
        description=f"Pause the unit: '{unit.name}'",
        coro=model.run_action(f"{unit.name}", "pause", raise_on_failure=True),
    )
    app = OpenStackApplication(
        name=app_name,
        can_upgrade_to="",
        charm=charm,
        channel=channel,
        config={},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={f"{unit.name}": unit},
        workload_version="1",
    )

    step = app._get_pause_unit_step(unit)
    assert_steps(step, expected_upgrade_step)


def test_get_resume_unit_step(model):
    charm = "app"
    app_name = "my_app"
    channel = "ussuri/stable"
    machines = {"0": MagicMock(spec_set=Machine)}
    unit = Unit(
        name=f"{app_name}/0",
        workload_version="1",
        machine=machines["0"],
    )
    expected_upgrade_step = UnitUpgradeStep(
        description=f"Resume the unit: '{unit.name}'",
        coro=model.run_action(unit.name, "resume", raise_on_failure=True),
    )
    app = OpenStackApplication(
        name=app_name,
        can_upgrade_to="",
        charm=charm,
        channel=channel,
        config={},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={f"{app_name}/0": unit},
        workload_version="1",
    )

    step = app._get_resume_unit_step(unit)
    assert_steps(step, expected_upgrade_step)


def test_get_openstack_upgrade_step(model):
    charm = "app"
    app_name = "my_app"
    channel = "ussuri/stable"
    machines = {"0": MagicMock(spec_set=Machine)}
    unit = Unit(
        name=f"{app_name}/0",
        workload_version="1",
        machine=machines["0"],
    )
    expected_upgrade_step = UnitUpgradeStep(
        description=f"Upgrade the unit: '{unit.name}'",
        coro=model.run_action(unit.name, "openstack-upgrade", raise_on_failure=True),
    )
    app = OpenStackApplication(
        name=app_name,
        can_upgrade_to="",
        charm=charm,
        channel=channel,
        config={},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={f"{app_name}/0": unit},
        workload_version="1",
    )

    step = app._get_openstack_upgrade_step(unit)
    assert_steps(step, expected_upgrade_step)


@pytest.mark.parametrize(
    "units",
    [
        [],
        [Unit(f"my_app/{unit}", MagicMock(), MagicMock()) for unit in range(1)],
        [Unit(f"my_app/{unit}", MagicMock(), MagicMock()) for unit in range(2)],
        [Unit(f"my_app/{unit}", MagicMock(), MagicMock()) for unit in range(3)],
    ],
)
@patch("cou.apps.base.upgrade_packages")
def test_get_upgrade_current_release_packages_step(mock_upgrade_packages, units, model):
    charm = "app"
    app_name = "my_app"
    channel = "ussuri/stable"
    app_units = {
        f"my_app/{unit}": Unit(f"my_app/{unit}", MagicMock(), MagicMock()) for unit in range(3)
    }

    app = OpenStackApplication(
        app_name, "", charm, channel, {}, {}, model, "ch", "focal", [], app_units, "21.0.1"
    )

    expected_calls = (
        [call(unit.name, model, None) for unit in units]
        if units
        else [call(unit.name, model, None) for unit in app_units.values()]
    )

    app._get_upgrade_current_release_packages_step(units)
    mock_upgrade_packages.assert_has_calls(expected_calls)


@pytest.mark.parametrize(
    "units",
    [
        [],
        [Unit(f"my_app/{unit}", MagicMock(), MagicMock()) for unit in range(1)],
        [Unit(f"my_app/{unit}", MagicMock(), MagicMock()) for unit in range(2)],
        [Unit(f"my_app/{unit}", MagicMock(), MagicMock()) for unit in range(3)],
    ],
)
@patch("cou.apps.base.OpenStackApplication._verify_workload_upgrade")
def test_get_reached_expected_target_step(mock_workload_upgrade, units, model):
    target = OpenStackRelease("victoria")
    mock = MagicMock()
    charm = "app"
    app_name = "my_app"
    channel = "ussuri/stable"
    app_units = {f"my_app/{unit}": Unit(f"my_app/{unit}", mock, mock) for unit in range(3)}

    app = OpenStackApplication(
        app_name, "", charm, channel, {}, {}, model, "ch", "focal", [], app_units, "21.0.1"
    )

    expected_calls = [call(target, units)] if units else [call(target, list(app.units.values()))]

    app._get_reached_expected_target_step(target, units)
    mock_workload_upgrade.assert_has_calls(expected_calls)


@pytest.mark.parametrize("config", ({}, {"enable-auto-restarts": {"value": True}}))
@patch("cou.apps.base.OpenStackApplication._verify_channel", return_value=None)
def test_check_auto_restarts(_, config):
    """Test function to verify that enable-auto-restarts is disabled."""
    app_name = "app"
    app = OpenStackApplication(
        app_name, "", app_name, "stable", config, {}, MagicMock(), "ch", "focal", [], {}, "1"
    )

    app._check_auto_restarts()


@patch("cou.apps.base.OpenStackApplication._verify_channel", return_value=None)
def test_check_auto_restarts_error(_):
    """Test function to verify that enable-auto-restarts is disabled raising error."""
    app_name = "app"
    exp_error_msg = (
        "COU does not currently support upgrading applications that disable service restarts. "
        f"Please enable charm option enable-auto-restart and rerun COU to upgrade the {app_name} "
        "application."
    )
    config = {"enable-auto-restarts": {"value": False}}
    app = OpenStackApplication(
        app_name, "", app_name, "stable", config, {}, MagicMock(), "ch", "focal", [], {}, "1"
    )

    with pytest.raises(ApplicationError, match=exp_error_msg):
        app._check_auto_restarts()


@patch("cou.apps.base.OpenStackApplication._verify_channel", return_value=None)
@patch("cou.apps.base.OpenStackApplication.apt_source_codename", new_callable=PropertyMock)
@patch("cou.apps.base.OpenStackApplication.current_os_release", new_callable=PropertyMock)
def test_check_application_target(current_os_release, apt_source_codename, _):
    """Test function to verify target."""
    target = OpenStackRelease("victoria")
    release = OpenStackRelease("ussuri")
    app_name = "app"
    app = OpenStackApplication(
        app_name, "", app_name, "stable", {}, {}, MagicMock(), "ch", "focal", [], {}, "1"
    )
    current_os_release.return_value = apt_source_codename.return_value = release

    app._check_application_target(target)


@patch("cou.apps.base.OpenStackApplication._verify_channel", return_value=None)
@patch("cou.apps.base.OpenStackApplication.apt_source_codename", new_callable=PropertyMock)
@patch("cou.apps.base.OpenStackApplication.current_os_release", new_callable=PropertyMock)
def test_check_application_target_can_upgrade(current_os_release, apt_source_codename, _):
    """Test function to verify target."""
    target = OpenStackRelease("victoria")
    release = OpenStackRelease("ussuri")
    app_name = "app"
    app = OpenStackApplication(
        app_name, "stable", app_name, "stable", {}, {}, MagicMock(), "ch", "focal", [], {}, "1"
    )
    current_os_release.return_value = apt_source_codename.return_value = release

    app._check_application_target(target)


@patch("cou.apps.base.OpenStackApplication._verify_channel", return_value=None)
@patch("cou.apps.base.OpenStackApplication.apt_source_codename", new_callable=PropertyMock)
@patch("cou.apps.base.OpenStackApplication.current_os_release", new_callable=PropertyMock)
def test_check_application_target_error(current_os_release, apt_source_codename, _):
    """Test function to verify target raising error."""
    target = OpenStackRelease("victoria")
    app_name = "app"
    exp_error_msg = (
        f"Application '{app_name}' already configured for release equal to or greater than "
        f"{target}. Ignoring."
    )
    app = OpenStackApplication(
        app_name, "", app_name, "stable", {}, {}, MagicMock(), "ch", "focal", [], {}, "1"
    )
    current_os_release.return_value = apt_source_codename.return_value = target

    with pytest.raises(HaltUpgradePlanGeneration, match=exp_error_msg):
        app._check_application_target(target)


@patch("cou.apps.base.OpenStackApplication.os_release_units", new_callable=PropertyMock)
def test_check_mismatched_versions_exception(mock_os_release_units, model):
    """Raise exception if workload version is different on units of a control-plane application."""
    exp_error_msg = (
        "Units of application my-app are running mismatched OpenStack versions: "
        r"'ussuri': \['my-app\/0', 'my-app\/1'\], 'victoria': \['my-app\/2'\]. "
        "This is not currently handled."
    )

    machines = {
        "0": MagicMock(spec_set=Machine),
        "1": MagicMock(spec_set=Machine),
        "2": MagicMock(spec_set=Machine),
    }
    units = {
        "my-app/0": Unit(
            name="my-app/0",
            workload_version="17.0.1",
            machine=machines["0"],
        ),
        "my-app/1": Unit(
            name="my-app/1",
            workload_version="17.0.1",
            machine=machines["1"],
        ),
        "my-app/2": Unit(
            name="my-app/2",
            workload_version="18.1.0",
            machine=machines["2"],
        ),
    }

    mock_os_release_units.return_value = {
        OpenStackRelease("ussuri"): ["my-app/0", "my-app/1"],
        OpenStackRelease("victoria"): ["my-app/2"],
    }

    app = OpenStackApplication(
        name="my-app",
        can_upgrade_to="ussuri/stable",
        charm="my-app",
        channel="ussuri/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units=units,
        workload_version="18.1.0",
    )

    with pytest.raises(MismatchedOpenStackVersions, match=exp_error_msg):
        app._check_mismatched_versions(None)

    # if units are passed, it doesn't raise exception
    assert app._check_mismatched_versions([units["my-app/0"]]) is None


@patch("cou.apps.base.OpenStackApplication.os_release_units", new_callable=PropertyMock)
def test_check_mismatched_versions(mock_os_release_units, model):
    """Test that no exceptions is raised if units of the app have the same OpenStack version."""
    machines = {
        "0": MagicMock(spec_set=Machine),
        "1": MagicMock(spec_set=Machine),
        "2": MagicMock(spec_set=Machine),
    }
    units = {
        "my-app/0": Unit(
            name="my-app/0",
            workload_version="17.0.1",
            machine=machines["0"],
        ),
        "my-app/1": Unit(
            name="my-app/1",
            workload_version="17.0.1",
            machine=machines["1"],
        ),
        "my-app/2": Unit(
            name="my-app/2",
            workload_version="18.1.0",
            machine=machines["2"],
        ),
    }

    mock_os_release_units.return_value = {
        OpenStackRelease("ussuri"): ["my-app/0", "my-app/1", "my-app/2"],
    }

    app = OpenStackApplication(
        name="my-app",
        can_upgrade_to="ussuri/stable",
        charm="my-app",
        channel="ussuri/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units=units,
        workload_version="18.1.0",
    )

    assert app._check_mismatched_versions([units["my-app/0"]]) is None


@patch("cou.apps.base.OpenStackApplication.current_os_release", new_callable=PropertyMock)
def test_get_charmhub_migration_step(current_os_release, model):
    """Switch applications installed from charm store to a charmhub channel."""
    current_os_release.return_value = OpenStackRelease("ussuri")

    app = OpenStackApplication(
        name="app",
        can_upgrade_to="",
        charm="app",
        channel="ussuri/stable",
        config={},
        machines={},
        model=model,
        origin="cs",
        series="focal",
        subordinate_to=[],
        units={},
        workload_version="1",
    )
    assert app._get_charmhub_migration_step() == PreUpgradeStep(
        f"Migrate '{app.name}' from charmstore to charmhub",
        coro=model.upgrade_charm(app.name, app.expected_current_channel, switch=f"ch:{app.charm}"),
    )


@patch("cou.apps.base.OpenStackApplication.current_os_release", new_callable=PropertyMock)
def test_get_change_to_openstack_channels_step(current_os_release, model):
    """Applications using latest/stable should be switched to a release-specific channel."""
    current_os_release.return_value = OpenStackRelease("ussuri")

    app = OpenStackApplication(
        name="app",
        can_upgrade_to="",
        charm="app",
        channel="latest/stable",
        config={},
        machines={},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={},
        workload_version="1",
    )
    assert app._get_change_to_openstack_channels_step() == PreUpgradeStep(
        f"WARNING: Changing '{app.name}' channel from {app.channel} to "
        f"{app.expected_current_channel}. This may be a charm downgrade, "
        "which is generally not supported.",
        coro=model.upgrade_charm(app.name, app.expected_current_channel),
    )


def test_get_refresh_current_channel_step(model):
    """Expect a pre-upgrade step for application that needs to refresh the current channel."""
    app = OpenStackApplication(
        name="app",
        can_upgrade_to="ch:amd64/focal/my-app-723",
        charm="app",
        channel="ussuri/stable",
        config={},
        machines={},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={},
        workload_version="1",
    )
    expected_result = PreUpgradeStep(
        f"Refresh '{app.name}' to the latest revision of '{app.channel}'",
        coro=model.upgrade_charm(app.name, app.channel),
    )

    assert app._get_refresh_current_channel_step() == expected_result


@patch("cou.apps.base.OpenStackApplication._get_refresh_current_channel_step")
@patch("cou.apps.base.OpenStackApplication._get_change_to_openstack_channels_step")
@patch("cou.apps.base.OpenStackApplication._get_charmhub_migration_step")
def test_get_refresh_charm_step_skip(
    mock_ch_migration, mock_change_os_channels, mock_refresh_current_channel, model
):
    """Expect an empty pre-upgrade step for application that does not need to refresh."""
    target = OpenStackRelease("victoria")

    app = OpenStackApplication(
        name="app",
        can_upgrade_to="",
        charm="app",
        channel="ussuri/stable",
        config={},
        machines={},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={},
        workload_version="1",
    )
    assert app._get_refresh_charm_step(target) == PreUpgradeStep()
    mock_ch_migration.assert_not_called()
    mock_change_os_channels.assert_not_called()
    mock_refresh_current_channel.assert_not_called()


@patch("cou.apps.base.OpenStackApplication._get_refresh_current_channel_step")
@patch("cou.apps.base.OpenStackApplication._get_change_to_openstack_channels_step")
@patch(
    "cou.apps.base.OpenStackApplication._get_charmhub_migration_step",
)
def test_get_refresh_charm_step_refresh_current_channel(
    mock_ch_migration, mock_change_os_channels, mock_refresh_current_channel, model
):
    """Expect a pre-upgrade step for application that needs to refresh current channel."""
    target = OpenStackRelease("victoria")

    app = OpenStackApplication(
        name="app",
        can_upgrade_to="ch:amd64/focal/my-app-723",
        charm="app",
        channel="ussuri/stable",
        config={},
        machines={},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={},
        workload_version="1",
    )
    expected_result = PreUpgradeStep(
        f"Refresh '{app.name}' to the latest revision of '{app.channel}'",
        coro=model.upgrade_charm(app.name, app.channel),
    )
    mock_refresh_current_channel.return_value = expected_result

    assert app._get_refresh_charm_step(target) == expected_result

    mock_ch_migration.assert_not_called()
    mock_change_os_channels.assert_not_called()
    mock_refresh_current_channel.assert_called_once()


@patch("cou.apps.base.OpenStackApplication._get_refresh_current_channel_step")
@patch("cou.apps.base.OpenStackApplication._get_change_to_openstack_channels_step")
@patch("cou.apps.base.OpenStackApplication._get_charmhub_migration_step")
@patch("cou.apps.base.OpenStackApplication.current_os_release", new_callable=PropertyMock)
def test_get_refresh_charm_step_change_to_openstack_channels(
    current_os_release,
    mock_ch_migration,
    mock_change_os_channels,
    mock_refresh_current_channel,
    model,
):
    """Expect a pre-upgrade step for application that needs to change to OpenStack channel."""
    current_os_release.return_value = OpenStackRelease("ussuri")
    target = OpenStackRelease("victoria")

    app = OpenStackApplication(
        name="app",
        can_upgrade_to="",
        charm="app",
        channel="latest/stable",
        config={},
        machines={},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={},
        workload_version="1",
    )
    expected_result = PreUpgradeStep(
        f"WARNING: Changing '{app.name}' channel from {app.channel} to "
        f"{app.expected_current_channel}. This may be a charm downgrade, "
        "which is generally not supported.",
        coro=model.upgrade_charm(app.name, app.expected_current_channel),
    )

    mock_change_os_channels.return_value = expected_result

    assert app._get_refresh_charm_step(target) == expected_result

    mock_ch_migration.assert_not_called()
    mock_change_os_channels.assert_called_once()
    mock_refresh_current_channel.assert_not_called()


@patch("cou.apps.base.OpenStackApplication._get_refresh_current_channel_step")
@patch("cou.apps.base.OpenStackApplication._get_change_to_openstack_channels_step")
@patch("cou.apps.base.OpenStackApplication._get_charmhub_migration_step")
@patch("cou.apps.base.OpenStackApplication.current_os_release", new_callable=PropertyMock)
def test_get_refresh_charm_step_charmhub_migration(
    current_os_release,
    mock_ch_migration,
    mock_change_os_channels,
    mock_refresh_current_channel,
    model,
):
    """Expect a pre-upgrade step for application that needs to migrate to charmhub."""
    current_os_release.return_value = OpenStackRelease("ussuri")
    target = OpenStackRelease("victoria")

    app = OpenStackApplication(
        name="app",
        can_upgrade_to="",
        charm="app",
        channel="stable",
        config={},
        machines={},
        model=model,
        origin="cs",
        series="focal",
        subordinate_to=[],
        units={},
        workload_version="1",
    )
    expected_result = PreUpgradeStep(
        f"Migrate '{app.name}' from charmstore to charmhub",
        coro=model.upgrade_charm(app.name, app.expected_current_channel, switch=f"ch:{app.charm}"),
    )
    mock_ch_migration.return_value = expected_result

    assert app._get_refresh_charm_step(target) == expected_result

    mock_ch_migration.assert_called_once()
    mock_change_os_channels.assert_not_called()
    mock_refresh_current_channel.assert_not_called()


@pytest.mark.parametrize(
    "can_upgrade_to, channel, exp_result",
    [
        ("", "ussuri/stable", False),
        ("ch:amd64/focal/my-app-723", "ussuri/stable", True),
        ("ch:amd64/focal/my-app-723", "victoria/stable", True),
        # when channel_codename is bigger than target it's not necessary to refresh
        ("ch:amd64/focal/my-app-723", "wallaby/stable", False),
        ("", "wallaby/stable", False),
    ],
)
def test_need_current_channel_refresh(model, can_upgrade_to, channel, exp_result):
    """Test when the application needs to refresh."""
    target = OpenStackRelease("victoria")

    app = OpenStackApplication(
        name="app",
        can_upgrade_to=can_upgrade_to,
        charm="app",
        channel=channel,
        config={},
        machines={},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={},
        workload_version="1",
    )
    assert app._need_current_channel_refresh(target) is exp_result
