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

from unittest.mock import MagicMock, call, patch

import pytest

from cou.apps.base import OpenStackApplication
from cou.exceptions import ApplicationError
from cou.steps import UnitUpgradeStep, UpgradeStep
from cou.utils.juju_utils import COUMachine, COUUnit
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


@patch("cou.apps.base.OpenStackApplication._verify_channel", return_value=None)
@patch("cou.utils.openstack.OpenStackCodenameLookup.find_compatible_versions")
def test_application_get_latest_os_version_failed(mock_find_compatible_versions, model):
    charm = "app"
    app_name = "my_app"
    unit = COUUnit(
        name=f"{app_name}/0",
        workload_version="1",
        machine=MagicMock(spec_set=COUMachine),
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
        app._get_latest_os_version(unit)

    mock_find_compatible_versions.assert_called_once_with(charm, unit.workload_version)


@pytest.mark.parametrize(
    "charm_config",
    [{"action-managed-upgrade": {"value": False}}, {"action-managed-upgrade": {"value": True}}],
)
def test_get_enable_action_managed_step(charm_config, model):
    charm = "app"
    app_name = "my_app"
    channel = "ussuri/stable"
    if charm_config["action-managed-upgrade"]["value"] is False:
        expected_upgrade_step = UpgradeStep(
            f"Change charm config of '{app_name}' 'action-managed-upgrade' to True.",
            False,
            model.set_application_config(app_name, {"action-managed-upgrade": True}),
        )
    else:
        expected_upgrade_step = UpgradeStep()

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

    step = app._get_enable_action_managed_step()
    assert_steps(step, expected_upgrade_step)


def test_get_pause_unit_step(model):
    charm = "app"
    app_name = "my_app"
    channel = "ussuri/stable"
    machines = {"0": MagicMock(spec_set=COUMachine)}
    unit = COUUnit(
        name=f"{app_name}/0",
        workload_version="1",
        machine=machines["0"],
    )
    expected_upgrade_step = UnitUpgradeStep(
        description=f"Pause the unit: '{unit.name}'.",
        coro=model.run_action(
            unit_name=f"{unit.name}", action_name="pause", raise_on_failure=True
        ),
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
    machines = {"0": MagicMock(spec_set=COUMachine)}
    unit = COUUnit(
        name=f"{app_name}/0",
        workload_version="1",
        machine=machines["0"],
    )
    expected_upgrade_step = UnitUpgradeStep(
        description=f"Resume the unit: '{unit.name}'.",
        coro=model.run_action(unit_name=unit.name, action_name="resume", raise_on_failure=True),
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
    machines = {"0": MagicMock(spec_set=COUMachine)}
    unit = COUUnit(
        name=f"{app_name}/0",
        workload_version="1",
        machine=machines["0"],
    )
    expected_upgrade_step = UnitUpgradeStep(
        description=f"Upgrade the unit: '{unit.name}'.",
        coro=model.run_action(
            unit_name=unit.name, action_name="openstack-upgrade", raise_on_failure=True
        ),
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
        [COUUnit(f"my_app/{unit}", MagicMock(), MagicMock()) for unit in range(1)],
        [COUUnit(f"my_app/{unit}", MagicMock(), MagicMock()) for unit in range(2)],
        [COUUnit(f"my_app/{unit}", MagicMock(), MagicMock()) for unit in range(3)],
    ],
)
@patch("cou.apps.base.upgrade_packages")
def test_get_upgrade_current_release_packages_step(mock_upgrade_packages, units, model):
    charm = "app"
    app_name = "my_app"
    channel = "ussuri/stable"
    app_units = {
        f"my_app/{unit}": COUUnit(f"my_app/{unit}", MagicMock(), MagicMock()) for unit in range(3)
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
        [COUUnit(f"my_app/{unit}", MagicMock(), MagicMock()) for unit in range(1)],
        [COUUnit(f"my_app/{unit}", MagicMock(), MagicMock()) for unit in range(2)],
        [COUUnit(f"my_app/{unit}", MagicMock(), MagicMock()) for unit in range(3)],
    ],
)
@patch("cou.apps.base.OpenStackApplication._verify_workload_upgrade")
def test_get_reached_expected_target_step(mock_workload_upgrade, units, model):
    target = OpenStackRelease("victoria")
    mock = MagicMock()
    charm = "app"
    app_name = "my_app"
    channel = "ussuri/stable"
    app_units = {f"my_app/{unit}": COUUnit(f"my_app/{unit}", mock, mock) for unit in range(3)}

    app = OpenStackApplication(
        app_name, "", charm, channel, {}, {}, model, "ch", "focal", [], app_units, "21.0.1"
    )

    expected_calls = [call(target, units)] if units else [call(target, list(app.units.values()))]

    app._get_reached_expected_target_step(target, units)
    mock_workload_upgrade.assert_has_calls(expected_calls)
