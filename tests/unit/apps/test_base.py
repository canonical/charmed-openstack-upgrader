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
from tests.unit.utils import assert_steps, generate_cou_machine


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
    assert repr(app) == "test-app"


@patch("cou.utils.openstack.OpenStackCodenameLookup.find_compatible_versions")
def test_application_get_latest_o7k_version_failed(mock_find_compatible_versions, model):
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
        app.get_latest_o7k_version(unit)

    mock_find_compatible_versions.assert_called_once_with(charm, unit.workload_version)


@pytest.mark.parametrize(
    "charm_config, enable, exp_description",
    [
        ({}, True, None),
        ({}, False, None),
        (
            {"action-managed-upgrade": {"value": False}},
            True,
            "Change charm config of 'my_app' 'action-managed-upgrade' from 'False' to 'True'",
        ),
        ({"action-managed-upgrade": {"value": False}}, False, None),
        ({"action-managed-upgrade": {"value": True}}, True, None),
        (
            {"action-managed-upgrade": {"value": True}},
            False,
            "Change charm config of 'my_app' 'action-managed-upgrade' from 'True' to 'False'",
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
            coro=model.set_application_config(app_name, {"action-managed-upgrade": str(enable)}),
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


@pytest.mark.parametrize("origin", ["cs", "ch"])
@pytest.mark.parametrize("channel", ["stable", "latest/stable", "ussuri/stable"])
def test_check_channel(channel, origin):
    """Test function to verify validity of the charm channel."""
    name = "app"
    channel = channel
    series = "focal"
    app = OpenStackApplication(
        name, "", name, channel, {}, {}, MagicMock(), origin, series, [], {}, [], "1"
    )

    app._check_channel()


def test_check_channel_error():
    """Test function to verify validity of the charm channel when it's not valid."""
    name = "app"
    channel = "unknown/stable"
    series = "focal"
    exp_error_msg = (
        f"Channel: {channel} for charm '{name}' on series '{series}' is not supported by COU. "
        "Please take a look at the documentation: "
        "https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html to see if you "
        "are using the right track."
    )
    app = OpenStackApplication(
        name, "", name, channel, {}, {}, MagicMock(), "ch", series, [], {}, "1"
    )

    with pytest.raises(ApplicationError, match=exp_error_msg):
        app._check_channel()


@pytest.mark.parametrize("config", ({}, {"enable-auto-restarts": {"value": True}}))
def test_check_auto_restarts(config):
    """Test function to verify that enable-auto-restarts is disabled."""
    app_name = "app"
    app = OpenStackApplication(
        app_name, "", app_name, "stable", config, {}, MagicMock(), "ch", "focal", [], {}, "1"
    )

    app._check_auto_restarts()


def test_check_auto_restarts_error():
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


@patch("cou.apps.base.OpenStackApplication.apt_source_codename", new_callable=PropertyMock)
@patch("cou.apps.base.OpenStackApplication.o7k_release", new_callable=PropertyMock)
def test_check_application_target(o7k_release, apt_source_codename):
    """Test function to verify target."""
    target = OpenStackRelease("victoria")
    release = OpenStackRelease("ussuri")
    app_name = "app"
    app = OpenStackApplication(
        app_name, "", app_name, "stable", {}, {}, MagicMock(), "ch", "focal", [], {}, "1"
    )
    o7k_release.return_value = apt_source_codename.return_value = release

    app._check_application_target(target)


@patch("cou.apps.base.OpenStackApplication.apt_source_codename", new_callable=PropertyMock)
@patch("cou.apps.base.OpenStackApplication.o7k_release", new_callable=PropertyMock)
def test_check_application_target_can_upgrade(o7k_release, apt_source_codename):
    """Test function to verify target."""
    target = OpenStackRelease("victoria")
    release = OpenStackRelease("ussuri")
    app_name = "app"
    app = OpenStackApplication(
        app_name, "stable", app_name, "stable", {}, {}, MagicMock(), "ch", "focal", [], {}, "1"
    )
    o7k_release.return_value = apt_source_codename.return_value = release

    app._check_application_target(target)


@patch("cou.apps.base.OpenStackApplication.apt_source_codename", new_callable=PropertyMock)
@patch("cou.apps.base.OpenStackApplication.o7k_release", new_callable=PropertyMock)
def test_check_application_target_error(o7k_release, apt_source_codename):
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
    o7k_release.return_value = apt_source_codename.return_value = target

    with pytest.raises(HaltUpgradePlanGeneration, match=exp_error_msg):
        app._check_application_target(target)


@patch("cou.apps.base.OpenStackApplication.o7k_release_units", new_callable=PropertyMock)
def test_check_mismatched_versions_exception(mock_o7k_release_units, model):
    """Raise exception if workload version is different on units of a control-plane application."""
    exp_error_msg = (
        "Units of application my-app are running mismatched OpenStack versions: "
        r"'ussuri': \['my-app\/0', 'my-app\/1'\], 'victoria': \['my-app\/2'\]. "
        "This is not currently handled."
    )

    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
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

    mock_o7k_release_units.return_value = {
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
        app._check_mismatched_versions()


@patch("cou.apps.base.OpenStackApplication.o7k_release_units", new_callable=PropertyMock)
def test_check_mismatched_versions_with_nova_compute(mock_o7k_release_units, model):
    """Not raise exception if workload version is different, but is colocated with nova-compute."""
    machines = {
        f"{i}": generate_cou_machine(
            f"{i}", f"az-{i}", (("my-app", "app"), ("nova-compute-kvm-sriov", "nova-compute"))
        )
        for i in range(3)
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

    mock_o7k_release_units.return_value = {
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

    assert app._check_mismatched_versions() is None


@patch("cou.apps.base.OpenStackApplication.o7k_release_units", new_callable=PropertyMock)
def test_check_mismatched_versions(mock_o7k_release_units, model):
    """Test that no exceptions is raised if units of the app have the same OpenStack version."""
    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
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
            workload_version="17.0.1",
            machine=machines["2"],
        ),
    }

    mock_o7k_release_units.return_value = {
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
        workload_version="17.0.1",
    )

    assert app._check_mismatched_versions() is None


@patch("cou.apps.base.OpenStackApplication.o7k_release", new_callable=PropertyMock)
def test_get_charmhub_migration_step(o7k_release, model):
    """Switch applications installed from charm store to a charmhub channel."""
    target = OpenStackRelease("victoria")
    o7k_release.return_value = OpenStackRelease("ussuri")

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
    assert app._get_charmhub_migration_step(target) == PreUpgradeStep(
        f"Migrate '{app.name}' from charmstore to charmhub",
        coro=model.upgrade_charm(
            app.name, app.expected_current_channel(target), switch=f"ch:{app.charm}"
        ),
    )


@pytest.mark.parametrize("channel", ["stable", "latest/stable"])
@patch("cou.apps.base.OpenStackApplication.o7k_release", new_callable=PropertyMock)
def test_get_change_channel_possible_downgrade_step(o7k_release, model, channel):
    """Test possible downgrade scenario.

    Applications using 'stable' or 'latest/stable' should be switched to a
    release-specific channel.
    """
    o7k_release.return_value = OpenStackRelease("ussuri")
    target = OpenStackRelease("victoria")

    app = OpenStackApplication(
        name="app",
        can_upgrade_to="",
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

    description = (
        f"WARNING: Changing '{app.name}' channel from {app.channel} to "
        "ussuri/stable. This may be a charm downgrade, which is generally not supported."
    )

    assert app._get_change_channel_possible_downgrade_step(
        target, app.expected_current_channel(target)
    ) == PreUpgradeStep(
        description=description,
        coro=model.upgrade_charm(app.name, app.expected_current_channel(target)),
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
@patch("cou.apps.base.OpenStackApplication._get_change_channel_possible_downgrade_step")
@patch("cou.apps.base.OpenStackApplication._get_charmhub_migration_step")
def test_get_refresh_charm_step_skip(
    mock_ch_migration, mock_possible_downgrade_step, mock_refresh_current_channel, model
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
    assert app._get_refresh_charm_steps(target) == []
    mock_ch_migration.assert_not_called()
    mock_possible_downgrade_step.assert_not_called()
    mock_refresh_current_channel.assert_not_called()


@patch("cou.apps.base.OpenStackApplication._get_refresh_current_channel_step")
@patch("cou.apps.base.OpenStackApplication._get_change_channel_possible_downgrade_step")
@patch(
    "cou.apps.base.OpenStackApplication._get_charmhub_migration_step",
)
def test_get_refresh_charm_step_refresh_current_channel(
    mock_ch_migration, mock_possible_downgrade_step, mock_refresh_current_channel, model
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
    upgrade_step = PreUpgradeStep(
        f"Refresh '{app.name}' to the latest revision of '{app.channel}'",
        coro=model.upgrade_charm(app.name, app.channel),
    )
    mock_refresh_current_channel.return_value = upgrade_step

    expected_result = [
        upgrade_step,
        UpgradeStep(
            description=f"Wait for up to 300s for app '{app.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_idle(300, apps=[app.name]),
        ),
    ]

    assert app._get_refresh_charm_steps(target) == expected_result

    mock_ch_migration.assert_not_called()
    mock_possible_downgrade_step.assert_not_called()
    mock_refresh_current_channel.assert_called_once()


@patch("cou.apps.base.OpenStackApplication._get_refresh_current_channel_step")
@patch("cou.apps.base.OpenStackApplication._get_change_channel_possible_downgrade_step")
@patch("cou.apps.base.OpenStackApplication._get_charmhub_migration_step")
@patch("cou.apps.base.OpenStackApplication.o7k_release", new_callable=PropertyMock)
def test_get_refresh_charm_step_change_to_openstack_channels(
    o7k_release,
    mock_ch_migration,
    mock_possible_downgrade_step,
    mock_refresh_current_channel,
    model,
):
    """Expect a pre-upgrade step for application that needs to change to OpenStack channel."""
    o7k_release.return_value = OpenStackRelease("ussuri")
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

    description = (
        "WARNING: Changing 'app' channel from 'latest/stable' to 'ussuri/stable'. "
        "This may be a charm downgrade, which is generally not supported.",
    )

    coro = model.upgrade_charm(app.name, app.expected_current_channel)
    upgrade_step = PreUpgradeStep(description=description, coro=coro)
    mock_possible_downgrade_step.return_value = upgrade_step

    expected_steps = [
        upgrade_step,
        UpgradeStep(
            description=f"Wait for up to 300s for app '{app.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_idle(300, apps=[app.name]),
        ),
    ]

    assert app._get_refresh_charm_steps(target) == expected_steps

    mock_ch_migration.assert_not_called()
    mock_possible_downgrade_step.assert_called_once_with(target, "ussuri/stable")
    mock_refresh_current_channel.assert_not_called()


@patch("cou.apps.base.OpenStackApplication._get_refresh_current_channel_step")
@patch("cou.apps.base.OpenStackApplication._get_change_channel_possible_downgrade_step")
@patch("cou.apps.base.OpenStackApplication._get_charmhub_migration_step")
@patch("cou.apps.base.OpenStackApplication.o7k_release", new_callable=PropertyMock)
def test_get_refresh_charm_step_charmhub_migration(
    o7k_release,
    mock_ch_migration,
    mock_possible_downgrade_step,
    mock_refresh_current_channel,
    model,
):
    """Expect a pre-upgrade step for application that needs to migrate to charmhub."""
    o7k_release.return_value = OpenStackRelease("ussuri")
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
    migrate_step = PreUpgradeStep(
        f"Migrate '{app.name}' from charmstore to charmhub",
        coro=model.upgrade_charm(app.name, app.expected_current_channel, switch=f"ch:{app.charm}"),
    )
    mock_ch_migration.return_value = migrate_step

    expected_result = [
        migrate_step,
        UpgradeStep(
            description=f"Wait for up to 300s for app '{app.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_idle(300, apps=[app.name]),
        ),
    ]

    assert app._get_refresh_charm_steps(target) == expected_result

    mock_ch_migration.assert_called_once()
    mock_possible_downgrade_step.assert_not_called()
    mock_refresh_current_channel.assert_not_called()


@pytest.mark.parametrize(
    "config, exp_result",
    [
        ({"source": {"value": "cloud:focal-victoria"}}, "victoria"),
        ({"openstack-origin": {"value": "cloud:focal-wallaby"}}, "wallaby"),
        ({"source": {"value": "cloud:focal-xena"}}, "xena"),
    ],
)
def test_extract_from_uca_source(model, config, exp_result):
    """Test extraction from uca sources."""
    app = OpenStackApplication(
        name="app",
        can_upgrade_to="",
        charm="app",
        channel=f"{exp_result}/stable",
        config=config,
        machines={},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={},
        workload_version="1",
    )
    assert app._extract_from_uca_source() == exp_result


@pytest.mark.parametrize("wrong_uca", ["cloud:focal-foo", "cloud:focal"])
def test_extract_from_uca_source_raise(wrong_uca, model):
    """Test extraction from uca sources raises ApplicationError with invalid value."""
    app = OpenStackApplication(
        name="app",
        can_upgrade_to="",
        charm="app",
        channel="ussuri/stable",
        config={"source": {"value": wrong_uca}},
        machines={},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={},
        workload_version="1",
    )
    exp_msg = f"'app' has an invalid 'source': {wrong_uca}"
    with pytest.raises(ApplicationError, match=exp_msg):
        app._extract_from_uca_source()


@pytest.mark.parametrize(
    "config, exp_result",
    [
        ({"source": {"value": "distro"}}, "ussuri"),
        ({"openstack-origin": {"value": "cloud:focal-victoria"}}, "victoria"),
        ({"source": {"value": "cloud:focal-wallaby"}}, "wallaby"),
    ],
)
def test_apt_source_codename(config, exp_result, model):
    """Test application with empty or without origin setting."""
    machines = {"0": MagicMock(spec_set=Machine)}

    app = OpenStackApplication(
        name="app",
        can_upgrade_to="",
        charm="app",
        channel="ussuri/stable",
        config=config,
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "app/0": Unit(
                name="app/0",
                workload_version="1",
                machine=machines["0"],
            )
        },
        workload_version="1",
    )

    app.apt_source_codename == exp_result


@pytest.mark.parametrize(
    "config",
    [
        {"source": {"value": ""}},
        {},
    ],
)
@patch("cou.apps.base.OpenStackApplication.o7k_release", new_callable=PropertyMock)
def test_apt_source_codename_empty_or_without_origin_setting(mock_o7k_release, config, model):
    """Test application with empty or without origin setting."""
    # apt_source_codename will have OpenStack release considering the workload version.
    exp_result = OpenStackRelease("ussuri")
    mock_o7k_release.return_value = exp_result
    machines = {"0": MagicMock(spec_set=Machine)}

    app = OpenStackApplication(
        name="app",
        can_upgrade_to="",
        charm="app",
        channel="ussuri/stable",
        config=config,
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "app/0": Unit(
                name="app/0",
                workload_version="1",
                machine=machines["0"],
            )
        },
        workload_version="1",
    )

    app.apt_source_codename == exp_result


@pytest.mark.parametrize(
    "source_value",
    ["ppa:my-team/ppa", "http://my.archive.com/ubuntu main"],
)
def test_apt_source_codename_unknown_source(source_value, model):
    """Test application with unknown origin setting."""
    machines = {"0": MagicMock(spec_set=Machine)}
    exp_msg = f"'app' has an invalid 'source': {source_value}"
    app = OpenStackApplication(
        name="app",
        can_upgrade_to="",
        charm="app",
        channel="ussuri/stable",
        config={"source": {"value": source_value}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "app/0": Unit(
                name="app/0",
                workload_version="1",
                machine=machines["0"],
            )
        },
        workload_version="1",
    )

    with pytest.raises(ApplicationError, match=exp_msg):
        app.apt_source_codename


@pytest.mark.parametrize(
    "channel, origin, exp_result",
    [
        ("latest/stable", "ch", True),
        ("ussuri/stable", "ch", False),
        ("stable", "cs", True),
        ("latest/edge", "ch", False),
        ("foo/stable", "ch", False),
    ],
)
def test_need_crossgrade(model, channel, origin, exp_result):
    """Test if application need a crossgrade."""
    app = OpenStackApplication(
        name="app",
        can_upgrade_to="",
        charm="app",
        channel=channel,
        config={},
        machines={},
        model=model,
        origin=origin,
        series="focal",
        subordinate_to=[],
        units={},
        workload_version="1",
    )

    assert app.need_crossgrade is exp_result


@pytest.mark.parametrize(
    "channel, origin", [("latest/stable", "ch"), ("latest", "cs"), ("victoria/stable", "ch")]
)
@patch("cou.apps.base.OpenStackApplication.o7k_release", new_callable=PropertyMock)
def test_expected_current_channel(mock_o7k_release, model, channel, origin):
    """Expected current channel is based on the OpenStack release of the workload version."""
    mock_o7k_release.return_value = OpenStackRelease("victoria")
    target = OpenStackRelease("wallaby")

    app = OpenStackApplication(
        name="app",
        can_upgrade_to="",
        charm="app",
        channel=channel,
        config={},
        machines={},
        model=model,
        origin=origin,
        series="focal",
        subordinate_to=[],
        units={},
        workload_version="1",
    )

    # expected_current_channel is indifferent if the charm needs crossgrade
    assert app.expected_current_channel(target) == "victoria/stable"
