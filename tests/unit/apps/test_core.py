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
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import pytest
from juju.client._definitions import ApplicationStatus, UnitStatus

from cou.apps.base import OpenStackApplication
from cou.apps.core import Keystone, NeutronApi, NovaCompute, Swift, resume_nova_compute_unit
from cou.exceptions import (
    ActionFailed,
    ApplicationError,
    ApplicationNotSupported,
    HaltUpgradePlanGeneration,
)
from cou.steps import (
    ApplicationUpgradePlan,
    PostUpgradeStep,
    PreUpgradeStep,
    UnitUpgradeStep,
    UpgradeStep,
)
from cou.utils import app_utils
from cou.utils import nova_compute as nova_compute_utils
from cou.utils.juju_utils import SubordinateUnit, Unit
from cou.utils.openstack import OpenStackRelease
from tests.unit.utils import assert_steps, dedent_plan, generate_cou_machine


def test_application_different_wl(model):
    """The OpenStack version is considered the lowest of the units."""
    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
    units = {
        "keystone/0": Unit(
            name="keystone/0",
            workload_version="17.0.1",
            machine=machines["0"],
        ),
        "keystone/1": Unit(
            name="keystone/1",
            workload_version="17.0.1",
            machine=machines["1"],
        ),
        "keystone/2": Unit(
            name="keystone/2",
            workload_version="18.1.0",
            machine=machines["2"],
        ),
    }
    app = Keystone(
        name="keystone",
        can_upgrade_to="ussuri/stable",
        charm="keystone",
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
    assert OpenStackRelease("victoria") in app.o7k_release_units
    assert app.o7k_release == OpenStackRelease("ussuri")


@pytest.mark.asyncio
async def test_application_verify_workload_upgrade(model):
    """Test Kyestone application check successful upgrade."""
    target = OpenStackRelease("victoria")
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = Keystone(
        name="keystone",
        can_upgrade_to="ussuri/stable",
        charm="keystone",
        channel="ussuri/stable",
        config={
            "openstack-origin": {"value": "distro"},
            "action-managed-upgrade": {"value": True},
        },
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "keystone/0": Unit(
                name="keystone/0",
                workload_version="17.0.1",
                machine=machines["0"],
            )
        },
        workload_version="17.1.0",
    )

    # workload version changed from ussuri to victoria
    mock_status = AsyncMock()
    mock_app_status = MagicMock(spec_set=ApplicationStatus())
    mock_unit_status = MagicMock(spec_set=UnitStatus())
    mock_unit_status.workload_version = "18.1.0"
    mock_app_status.units = {"keystone/0": mock_unit_status}
    mock_status.return_value.applications = {"keystone": mock_app_status}
    model.get_status = mock_status

    assert await app._verify_workload_upgrade(target, app.units.values()) is None


@pytest.mark.asyncio
async def test_application_verify_workload_upgrade_fail(model):
    """Test Kyestone application check unsuccessful upgrade."""
    target = OpenStackRelease("victoria")
    exp_msg = (
        r"Unit\(s\) 'keystone/0' did not complete the upgrade to victoria. Some local processes "
        r"may still be executing; you may try re-running COU in a few minutes."
    )
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = Keystone(
        name="keystone",
        can_upgrade_to="ussuri/stable",
        charm="keystone",
        channel="ussuri/stable",
        config={
            "openstack-origin": {"value": "distro"},
            "action-managed-upgrade": {"value": True},
        },
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "keystone/0": Unit(
                name="keystone/0",
                workload_version="17.0.1",
                machine=machines["0"],
            )
        },
        workload_version="17.1.0",
    )

    # workload version didn't change from ussuri to victoria
    mock_status = AsyncMock()
    mock_app_status = MagicMock(spec_set=ApplicationStatus())
    mock_unit_status = MagicMock(spec_set=UnitStatus())
    mock_unit_status.workload_version = "17.1.0"
    mock_app_status.units = {"keystone/0": mock_unit_status}
    mock_status.return_value.applications = {"keystone": mock_app_status}
    model.get_status = mock_status

    with pytest.raises(ApplicationError, match=exp_msg):
        await app._verify_workload_upgrade(target, app.units.values())


def test_upgrade_plan_ussuri_to_victoria(model):
    """Test generate plan to upgrade Keystone from Ussuri to Victoria."""
    target = OpenStackRelease("victoria")
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = Keystone(
        name="keystone",
        can_upgrade_to="ussuri/stable",
        charm="keystone",
        channel="ussuri/stable",
        config={
            "openstack-origin": {"value": "distro"},
            "action-managed-upgrade": {"value": True},
        },
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"keystone/{unit}": Unit(
                name=f"keystone/{unit}",
                workload_version="17.0.1",
                machine=machines["0"],
            )
            for unit in range(3)
        },
        workload_version="17.1.0",
    )
    expected_plan = ApplicationUpgradePlan(f"Upgrade plan for '{app.name}' to '{target}'")
    upgrade_packages = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    upgrade_packages.add_steps(
        UnitUpgradeStep(
            description=f"Upgrade software packages on unit '{unit.name}'",
            coro=app_utils.upgrade_packages(unit.name, model, None),
        )
        for unit in app.units.values()
    )

    upgrade_steps = [
        upgrade_packages,
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of 'ussuri/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "ussuri/stable"),
        ),
        PreUpgradeStep(
            description=f"Wait for up to {app.charm_refresh_timeout}s for app '{app.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_idle(app.charm_refresh_timeout, apps=[app.name]),
        ),
        UpgradeStep(
            description=f"Change charm config of '{app.name}' 'action-managed-upgrade' "
            "from 'True' to 'False'",
            parallel=False,
            coro=model.set_application_config(app.name, {"action-managed-upgrade": str(False)}),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' from 'ussuri/stable' to the new channel: "
            "'victoria/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "victoria/stable"),
        ),
        UpgradeStep(
            description=f"Wait for up to {app.charm_refresh_timeout}s for app '{app.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_idle(app.charm_refresh_timeout, apps=[app.name]),
        ),
        UpgradeStep(
            description=f"Change charm config of '{app.name}' "
            f"'{app.origin_setting}' to 'cloud:focal-victoria'",
            parallel=False,
            coro=model.set_application_config(
                app.name, {f"{app.origin_setting}": "cloud:focal-victoria"}
            ),
        ),
        PostUpgradeStep(
            description=f"Wait for up to 2400s for model '{model.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_idle(2400, apps=None),
        ),
        PostUpgradeStep(
            description=f"Verify that the workload of '{app.name}' has been upgraded on units: "
            f"{', '.join([unit for unit in app.units.keys()])}",
            parallel=False,
            coro=app._verify_workload_upgrade(target, list(app.units.values())),
        ),
    ]
    expected_plan.add_steps(upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)
    assert_steps(upgrade_plan, expected_plan)


def test_upgrade_plan_ussuri_to_victoria_ch_migration(model):
    """Test generate plan to upgrade Keystone from Ussuri to Victoria with charmhub migration."""
    target = OpenStackRelease("victoria")
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = Keystone(
        name="keystone",
        can_upgrade_to="ussuri/stable",
        charm="keystone",
        channel="ussuri/stable",
        config={
            "openstack-origin": {"value": "distro"},
            "action-managed-upgrade": {"value": True},
        },
        machines=machines,
        model=model,
        origin="cs",
        series="focal",
        subordinate_to=[],
        units={
            f"keystone/{unit}": Unit(
                name=f"keystone/{unit}",
                workload_version="17.0.1",
                machine=machines["0"],
            )
            for unit in range(3)
        },
        workload_version="17.1.0",
    )
    expected_plan = ApplicationUpgradePlan(f"Upgrade plan for '{app.name}' to '{target}'")
    upgrade_packages = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    upgrade_packages.add_steps(
        UnitUpgradeStep(
            description=f"Upgrade software packages on unit '{unit.name}'",
            coro=app_utils.upgrade_packages(unit.name, model, None),
        )
        for unit in app.units.values()
    )

    upgrade_steps = [
        upgrade_packages,
        PreUpgradeStep(
            description=f"Migrate '{app.name}' from charmstore to charmhub",
            parallel=False,
            coro=model.upgrade_charm(app.name, "ussuri/stable", switch="ch:keystone"),
        ),
        PreUpgradeStep(
            description=f"Wait for up to 1200s for app '{app.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_idle(1200, apps=[app.name]),
        ),
        UpgradeStep(
            description=f"Change charm config of '{app.name}' 'action-managed-upgrade' "
            "from 'True' to 'False'",
            parallel=False,
            coro=model.set_application_config(app.name, {"action-managed-upgrade": str(False)}),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' from 'ussuri/stable' to the new channel: "
            "'victoria/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "victoria/stable"),
        ),
        UpgradeStep(
            description=f"Wait for up to {app.charm_refresh_timeout}s for app '{app.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_idle(app.charm_refresh_timeout, apps=[app.name]),
        ),
        UpgradeStep(
            description=f"Change charm config of '{app.name}' "
            f"'{app.origin_setting}' to 'cloud:focal-victoria'",
            parallel=False,
            coro=model.set_application_config(
                app.name, {f"{app.origin_setting}": "cloud:focal-victoria"}
            ),
        ),
        PostUpgradeStep(
            description=f"Wait for up to 2400s for model '{model.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_idle(2400, apps=None),
        ),
        PostUpgradeStep(
            description=f"Verify that the workload of '{app.name}' has been upgraded on units: "
            f"{', '.join([unit for unit in app.units.keys()])}",
            parallel=False,
            coro=app._verify_workload_upgrade(target, list(app.units.values())),
        ),
    ]
    expected_plan.add_steps(upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)
    assert_steps(upgrade_plan, expected_plan)


def test_upgrade_plan_channel_on_next_o7k_release(model):
    """Test generate plan to upgrade Keystone from Ussuri to Victoria with updated channel.

    The app channel it's already on next OpenStack release.
    """
    target = OpenStackRelease("victoria")
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = Keystone(
        name="keystone",
        can_upgrade_to="",
        charm="keystone",
        channel="victoria/stable",
        config={
            "openstack-origin": {"value": "distro"},
            "action-managed-upgrade": {"value": True},
        },
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"keystone/{unit}": Unit(
                name=f"keystone/{unit}",
                workload_version="17.0.1",
                machine=machines["0"],
            )
            for unit in range(3)
        },
        workload_version="17.1.0",
    )
    expected_plan = ApplicationUpgradePlan(f"Upgrade plan for '{app.name}' to '{target}'")
    # no sub-step for refresh current channel or next channel
    upgrade_packages = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    upgrade_packages.add_steps(
        UnitUpgradeStep(
            description=f"Upgrade software packages on unit '{unit.name}'",
            coro=app_utils.upgrade_packages(unit.name, model, None),
        )
        for unit in app.units.values()
    )

    upgrade_steps = [
        upgrade_packages,
        UpgradeStep(
            description=f"Change charm config of '{app.name}' 'action-managed-upgrade' "
            "from 'True' to 'False'",
            parallel=False,
            coro=model.set_application_config(app.name, {"action-managed-upgrade": str(False)}),
        ),
        UpgradeStep(
            description=f"Change charm config of '{app.name}' "
            f"'{app.origin_setting}' to 'cloud:focal-victoria'",
            parallel=False,
            coro=model.set_application_config(
                app.name, {f"{app.origin_setting}": "cloud:focal-victoria"}
            ),
        ),
        PostUpgradeStep(
            description=f"Wait for up to 2400s for model '{model.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_idle(2400, apps=None),
        ),
        PostUpgradeStep(
            description=f"Verify that the workload of '{app.name}' has been upgraded on units: "
            f"{', '.join([unit for unit in app.units.keys()])}",
            parallel=False,
            coro=app._verify_workload_upgrade(target, list(app.units.values())),
        ),
    ]
    expected_plan.add_steps(upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)
    assert_steps(upgrade_plan, expected_plan)


def test_upgrade_plan_origin_already_on_next_openstack_release(model):
    """Test generate plan to upgrade Keystone from Ussuri to Victoria with origin changed.

    The app config option openstack-origin it's already on next OpenStack release.
    """
    target = OpenStackRelease("victoria")
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = Keystone(
        name="keystone",
        can_upgrade_to="ussuri/stable",
        charm="keystone",
        channel="ussuri/stable",
        config={
            "openstack-origin": {"value": "cloud:focal-victoria"},
            "action-managed-upgrade": {"value": True},
        },
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"keystone/{unit}": Unit(
                name=f"keystone/{unit}",
                workload_version="17.0.1",
                machine=machines["0"],
            )
            for unit in range(3)
        },
        workload_version="17.1.0",
    )
    expected_plan = ApplicationUpgradePlan(f"Upgrade plan for '{app.name}' to '{target}'")
    upgrade_packages = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    upgrade_packages.add_steps(
        UnitUpgradeStep(
            description=f"Upgrade software packages on unit '{unit.name}'",
            coro=app_utils.upgrade_packages(unit.name, model, None),
        )
        for unit in app.units.values()
    )

    upgrade_steps = [
        upgrade_packages,
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of 'ussuri/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "ussuri/stable"),
        ),
        PreUpgradeStep(
            description=f"Wait for up to {app.charm_refresh_timeout}s for app '{app.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_idle(app.charm_refresh_timeout, apps=[app.name]),
        ),
        UpgradeStep(
            description=f"Change charm config of '{app.name}' 'action-managed-upgrade' "
            "from 'True' to 'False'",
            parallel=False,
            coro=model.set_application_config(app.name, {"action-managed-upgrade": str(False)}),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' from 'ussuri/stable' to the new channel: "
            "'victoria/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "victoria/stable"),
        ),
        UpgradeStep(
            description=f"Wait for up to {app.charm_refresh_timeout}s for app '{app.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_idle(app.charm_refresh_timeout, apps=[app.name]),
        ),
        PostUpgradeStep(
            description=f"Wait for up to 2400s for model '{model.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_idle(2400, apps=None),
        ),
        PostUpgradeStep(
            description=f"Verify that the workload of '{app.name}' has been upgraded on units: "
            f"{', '.join([unit for unit in app.units.keys()])}",
            parallel=False,
            coro=app._verify_workload_upgrade(target, list(app.units.values())),
        ),
    ]
    expected_plan.add_steps(upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)
    assert_steps(upgrade_plan, expected_plan)


def test_upgrade_plan_application_already_upgraded(model):
    """Test generate plan to upgrade Keystone from Victoria to Victoria."""
    exp_error_msg = (
        "Application 'keystone' already configured for release equal to or greater "
        "than victoria. Ignoring."
    )
    target = OpenStackRelease("victoria")
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = Keystone(
        name="keystone",
        can_upgrade_to="",
        charm="keystone",
        channel="wallaby/stable",
        config={
            "openstack-origin": {"value": "cloud:focal-wallaby"},
            "action-managed-upgrade": {"value": True},
        },
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"keystone/{unit}": Unit(
                name=f"keystone/{unit}",
                workload_version="19.0.1",
                machine=machines["0"],
            )
            for unit in range(3)
        },
        workload_version="19.1.0",
    )

    # victoria is lesser than wallaby, so application should not generate a plan.
    with pytest.raises(HaltUpgradePlanGeneration, match=exp_error_msg):
        app.generate_upgrade_plan(target, False)


def test_upgrade_plan_application_already_disable_action_managed(model):
    """Test generate plan to upgrade Keystone with managed upgrade disabled."""
    target = OpenStackRelease("victoria")
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = Keystone(
        name="keystone",
        can_upgrade_to="ussuri/stable",
        charm="keystone",
        channel="ussuri/stable",
        config={
            "openstack-origin": {"value": "distro"},
            "action-managed-upgrade": {"value": False},
        },
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"keystone/{unit}": Unit(
                name=f"keystone/{unit}",
                workload_version="17.0.1",
                machine=machines["0"],
            )
            for unit in range(3)
        },
        workload_version="17.1.0",
    )
    expected_plan = ApplicationUpgradePlan(f"Upgrade plan for '{app.name}' to '{target}'")
    upgrade_packages = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    upgrade_packages.add_steps(
        UnitUpgradeStep(
            description=f"Upgrade software packages on unit '{unit.name}'",
            coro=app_utils.upgrade_packages(unit.name, model, None),
        )
        for unit in app.units.values()
    )

    upgrade_steps = [
        upgrade_packages,
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of 'ussuri/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "ussuri/stable"),
        ),
        PreUpgradeStep(
            description=f"Wait for up to {app.charm_refresh_timeout}s for app '{app.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_idle(app.charm_refresh_timeout, apps=[app.name]),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' from 'ussuri/stable' to the new channel: "
            "'victoria/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "victoria/stable"),
        ),
        UpgradeStep(
            description=f"Wait for up to {app.charm_refresh_timeout}s for app '{app.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_idle(app.charm_refresh_timeout, apps=[app.name]),
        ),
        UpgradeStep(
            description=f"Change charm config of '{app.name}' "
            f"'{app.origin_setting}' to 'cloud:focal-victoria'",
            parallel=False,
            coro=model.set_application_config(
                app.name, {f"{app.origin_setting}": "cloud:focal-victoria"}
            ),
        ),
        PostUpgradeStep(
            description=f"Wait for up to 2400s for model '{model.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_idle(2400, apps=None),
        ),
        PostUpgradeStep(
            description=f"Verify that the workload of '{app.name}' has been upgraded on units: "
            f"{', '.join([unit for unit in app.units.keys()])}",
            parallel=False,
            coro=app._verify_workload_upgrade(target, list(app.units.values())),
        ),
    ]
    expected_plan.add_steps(upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)
    assert_steps(upgrade_plan, expected_plan)


@patch("cou.apps.base.OpenStackApplication._get_refresh_charm_steps")
@patch("cou.apps.base.OpenStackApplication._get_upgrade_current_release_packages_step")
@patch("cou.apps.core.NovaCompute._get_disable_scheduler_step")
def test_nova_compute_pre_upgrade_steps(
    mock_disable, mock_upgrade_package, mock_refresh_charm, model
):
    app = _generate_nova_compute_app(model)
    target = OpenStackRelease("victoria")
    units = list(app.units.values())

    app.pre_upgrade_steps(target, units)
    mock_disable.assert_called_once_with(units)
    mock_upgrade_package.assert_called_once_with(units)
    mock_refresh_charm.assert_called_once_with(target)


@patch("cou.apps.base.OpenStackApplication._get_wait_step")
@patch("cou.apps.base.OpenStackApplication._get_reached_expected_target_step")
@patch("cou.apps.core.NovaCompute._get_enable_scheduler_step")
def test_nova_compute_post_upgrade_steps(mock_enable, mock_expected_target, mock_wait_step, model):
    app = _generate_nova_compute_app(model)
    target = OpenStackRelease("victoria")
    units = list(app.units.values())

    app.post_upgrade_steps(target, units)
    mock_enable.assert_called_once_with(units)
    mock_expected_target.assert_called_once_with(target, units)
    mock_wait_step.assert_called_once_with()


@pytest.mark.parametrize("force", [True, False])
# add_step check if the step added is from BaseStep, so the return is an empty UnitUpgradeStep
@patch("cou.apps.core.NovaCompute._get_resume_unit_step", return_value=UnitUpgradeStep())
@patch("cou.apps.core.NovaCompute._get_openstack_upgrade_step", return_value=UnitUpgradeStep())
@patch("cou.apps.core.NovaCompute._get_pause_unit_step", return_value=UnitUpgradeStep())
@patch("cou.apps.core.NovaCompute._get_empty_hypervisor_step", return_value=UnitUpgradeStep())
def test_nova_compute_get_unit_upgrade_steps(
    mock_empty,
    mock_pause,
    mock_upgrade,
    mock_resume,
    model,
    force,
):
    app = _generate_nova_compute_app(model)
    unit = app.units["nova-compute/0"]

    app._get_unit_upgrade_steps(unit, force)

    if force:
        mock_empty.assert_not_called()
    else:
        mock_empty.assert_called_once_with(unit)

    mock_pause.assert_called_once_with(unit, not force)
    mock_upgrade.assert_called_once_with(unit, not force)
    mock_resume.assert_called_once_with(unit, not force)


def test_nova_compute_get_empty_hypervisor_step(model):
    app = _generate_nova_compute_app(model)
    units = list(app.units.values())
    unit = units[0]

    expected_step = UpgradeStep(
        description=f"Verify that unit '{unit.name}' has no VMs running",
        coro=nova_compute_utils.verify_empty_hypervisor(unit, model),
    )
    assert app._get_empty_hypervisor_step(unit) == expected_step


@pytest.mark.parametrize(
    "units",
    [
        [f"nova-compute/{unit}" for unit in range(1)],
        [f"nova-compute/{unit}" for unit in range(2)],
        [f"nova-compute/{unit}" for unit in range(3)],
    ],
)
def test_nova_compute_get_enable_scheduler_step(model, units):
    """Enable the scheduler on selected units."""
    app = _generate_nova_compute_app(model)
    units_selected = [app.units[unit] for unit in units]

    expected_step = [
        PostUpgradeStep(
            description=f"Enable nova-compute scheduler from unit: '{unit.name}'",
            coro=model.run_action(
                unit_name=unit.name, action_name="enable", raise_on_failure=True
            ),
        )
        for unit in units_selected
    ]
    assert app._get_enable_scheduler_step(units_selected) == expected_step


def test_nova_compute_get_enable_scheduler_step_no_units(model):
    """Enable the scheduler on all units if no units are passed."""
    app = _generate_nova_compute_app(model)

    expected_step = [
        PostUpgradeStep(
            description=f"Enable nova-compute scheduler from unit: '{unit.name}'",
            coro=model.run_action(
                unit_name=unit.name, action_name="enable", raise_on_failure=True
            ),
        )
        for unit in app.units.values()
    ]
    assert app._get_enable_scheduler_step(None) == expected_step


@pytest.mark.parametrize(
    "units",
    [
        [f"nova-compute/{unit}" for unit in range(1)],
        [f"nova-compute/{unit}" for unit in range(2)],
        [f"nova-compute/{unit}" for unit in range(3)],
    ],
)
def test_nova_compute_get_disable_scheduler_step(model, units):
    """Disable the scheduler on selected units."""
    app = _generate_nova_compute_app(model)
    units_selected = [app.units[unit] for unit in units]

    expected_step = [
        PreUpgradeStep(
            description=f"Disable nova-compute scheduler from unit: '{unit.name}'",
            coro=model.run_action(
                unit_name=unit.name, action_name="disable", raise_on_failure=True
            ),
        )
        for unit in units_selected
    ]
    assert app._get_disable_scheduler_step(units_selected) == expected_step


def test_nova_compute_get_disable_scheduler_step_no_units(model):
    """Disable the scheduler on selected units."""
    app = _generate_nova_compute_app(model)
    expected_step = [
        PreUpgradeStep(
            description=f"Disable nova-compute scheduler from unit: '{unit.name}'",
            coro=model.run_action(
                unit_name=unit.name, action_name="disable", raise_on_failure=True
            ),
        )
        for unit in app.units.values()
    ]
    assert app._get_disable_scheduler_step(None) == expected_step


def _generate_nova_compute_app(model):
    """Generate NovaCompute class."""
    charm = app_name = "nova-compute"
    channel = "ussuri/stable"

    units = {
        f"nova-compute/{unit_num}": Unit(
            f"nova-compute/{unit_num}",
            MagicMock(),
            "21.0.1",
            [SubordinateUnit("ceilometer-agent/{unit_num}", "ceilometer-agent")],
        )
        for unit_num in range(3)
    }
    app = NovaCompute(
        app_name, "", charm, channel, {}, {}, model, "cs", "focal", [], units, "21.0.1"
    )

    return app


def test_nova_compute_upgrade_plan(model):
    """Testing generating nova-compute upgrade plan."""
    target = OpenStackRelease("victoria")
    exp_plan = dedent_plan(
        """\
    Upgrade plan for 'nova-compute' to 'victoria'
        Disable nova-compute scheduler from unit: 'nova-compute/0'
        Disable nova-compute scheduler from unit: 'nova-compute/1'
        Disable nova-compute scheduler from unit: 'nova-compute/2'
        Upgrade software packages of 'nova-compute' from the current APT repositories
            Ψ Upgrade software packages on unit 'nova-compute/0'
            Ψ Upgrade software packages on unit 'nova-compute/1'
            Ψ Upgrade software packages on unit 'nova-compute/2'
        Refresh 'nova-compute' to the latest revision of 'ussuri/stable'
        Wait for up to 300s for app 'nova-compute' to reach the idle state
        Change charm config of 'nova-compute' 'action-managed-upgrade' from 'False' to 'True'
        Upgrade 'nova-compute' from 'ussuri/stable' to the new channel: 'victoria/stable'
        Wait for up to 300s for app 'nova-compute' to reach the idle state
        Change charm config of 'nova-compute' 'source' to 'cloud:focal-victoria'
        Upgrade plan for units: nova-compute/0, nova-compute/1, nova-compute/2
            Ψ Upgrade plan for unit 'nova-compute/0'
                Verify that unit 'nova-compute/0' has no VMs running
                ├── Pause the unit: 'nova-compute/0'
                ├── Upgrade the unit: 'nova-compute/0'
                ├── Resume the unit: 'nova-compute/0'
            Ψ Upgrade plan for unit 'nova-compute/1'
                Verify that unit 'nova-compute/1' has no VMs running
                ├── Pause the unit: 'nova-compute/1'
                ├── Upgrade the unit: 'nova-compute/1'
                ├── Resume the unit: 'nova-compute/1'
            Ψ Upgrade plan for unit 'nova-compute/2'
                Verify that unit 'nova-compute/2' has no VMs running
                ├── Pause the unit: 'nova-compute/2'
                ├── Upgrade the unit: 'nova-compute/2'
                ├── Resume the unit: 'nova-compute/2'
        Enable nova-compute scheduler from unit: 'nova-compute/0'
        Enable nova-compute scheduler from unit: 'nova-compute/1'
        Enable nova-compute scheduler from unit: 'nova-compute/2'
        Wait for up to 2400s for model 'test_model' to reach the idle state
        Verify that the workload of 'nova-compute' has been upgraded on units: nova-compute/0, nova-compute/1, nova-compute/2
    """  # noqa: E501 line too long
    )
    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
    units = {
        f"nova-compute/{unit}": Unit(
            name=f"nova-compute/{unit}",
            workload_version="21.0.0",
            machine=machines[f"{unit}"],
            subordinates=[
                SubordinateUnit(name=f"ceilometer-agent/{unit}", charm="ceilometer-agent"),
            ],
        )
        for unit in range(3)
    }
    nova_compute = NovaCompute(
        name="nova-compute",
        can_upgrade_to="ussuri/stable",
        charm="nova-compute",
        channel="ussuri/stable",
        config={"source": {"value": "distro"}, "action-managed-upgrade": {"value": False}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units=units,
        workload_version="21.0.0",
    )

    plan = nova_compute.generate_upgrade_plan(target, False)
    assert str(plan) == exp_plan


def test_nova_compute_upgrade_plan_single_unit(model):
    """Testing generating nova-compute upgrade plan for single unit."""
    target = OpenStackRelease("victoria")
    exp_plan = dedent_plan(
        """\
    Upgrade plan for 'nova-compute' to 'victoria'
        Disable nova-compute scheduler from unit: 'nova-compute/0'
        Upgrade software packages of 'nova-compute' from the current APT repositories
            Ψ Upgrade software packages on unit 'nova-compute/0'
        Refresh 'nova-compute' to the latest revision of 'ussuri/stable'
        Wait for up to 300s for app 'nova-compute' to reach the idle state
        Change charm config of 'nova-compute' 'action-managed-upgrade' from 'False' to 'True'
        Upgrade 'nova-compute' from 'ussuri/stable' to the new channel: 'victoria/stable'
        Wait for up to 300s for app 'nova-compute' to reach the idle state
        Change charm config of 'nova-compute' 'source' to 'cloud:focal-victoria'
        Upgrade plan for units: nova-compute/0
            Ψ Upgrade plan for unit 'nova-compute/0'
                Verify that unit 'nova-compute/0' has no VMs running
                ├── Pause the unit: 'nova-compute/0'
                ├── Upgrade the unit: 'nova-compute/0'
                ├── Resume the unit: 'nova-compute/0'
        Enable nova-compute scheduler from unit: 'nova-compute/0'
        Wait for up to 2400s for model 'test_model' to reach the idle state
        Verify that the workload of 'nova-compute' has been upgraded on units: nova-compute/0
    """
    )
    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
    units = {
        f"nova-compute/{unit}": Unit(
            name=f"nova-compute/{unit}",
            workload_version="21.0.0",
            machine=machines[f"{unit}"],
            subordinates=[
                SubordinateUnit(name=f"ceilometer-agent/{unit}", charm="ceilometer-agent"),
            ],
        )
        for unit in range(3)
    }
    nova_compute = NovaCompute(
        name="nova-compute",
        can_upgrade_to="ussuri/stable",
        charm="nova-compute",
        channel="ussuri/stable",
        config={"source": {"value": "distro"}, "action-managed-upgrade": {"value": False}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units=units,
        workload_version="21.0.0",
    )

    plan = nova_compute.generate_upgrade_plan(target, False, units=[units["nova-compute/0"]])

    assert str(plan) == exp_plan


def test_cinder_upgrade_plan(model):
    """Testing generating cinder upgrade plan."""
    target = OpenStackRelease("victoria")
    exp_plan = dedent_plan(
        """\
    Upgrade plan for 'cinder' to 'victoria'
        Upgrade software packages of 'cinder' from the current APT repositories
            Ψ Upgrade software packages on unit 'cinder/0'
            Ψ Upgrade software packages on unit 'cinder/1'
            Ψ Upgrade software packages on unit 'cinder/2'
        Refresh 'cinder' to the latest revision of 'ussuri/stable'
        Wait for up to 300s for app 'cinder' to reach the idle state
        Upgrade 'cinder' from 'ussuri/stable' to the new channel: 'victoria/stable'
        Wait for up to 300s for app 'cinder' to reach the idle state
        Change charm config of 'cinder' 'openstack-origin' to 'cloud:focal-victoria'
        Wait for up to 300s for app 'cinder' to reach the idle state
        Verify that the workload of 'cinder' has been upgraded on units: \
cinder/0, cinder/1, cinder/2
    """
    )
    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
    units = {
        f"cinder/{i}": Unit(
            name=f"cinder/{i}",
            workload_version="16.4.2",
            machine=machines[f"{i}"],
        )
        for i in range(3)
    }
    cinder = OpenStackApplication(
        name="cinder",
        can_upgrade_to="ussuri/stable",
        charm="cinder",
        channel="ussuri/stable",
        config={
            "openstack-origin": {"value": "distro"},
            "action-managed-upgrade": {"value": False},
        },
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units=units,
        workload_version="16.4.2",
    )

    plan = cinder.generate_upgrade_plan(target, False)

    assert str(plan) == exp_plan


def test_cinder_upgrade_plan_single_unit(model):
    """Testing generating cinder upgrade plan."""
    target = OpenStackRelease("victoria")
    exp_plan = dedent_plan(
        """\
    Upgrade plan for 'cinder' to 'victoria'
        Upgrade software packages of 'cinder' from the current APT repositories
            Ψ Upgrade software packages on unit 'cinder/0'
        Refresh 'cinder' to the latest revision of 'ussuri/stable'
        Wait for up to 300s for app 'cinder' to reach the idle state
        Change charm config of 'cinder' 'action-managed-upgrade' from 'False' to 'True'
        Upgrade 'cinder' from 'ussuri/stable' to the new channel: 'victoria/stable'
        Wait for up to 300s for app 'cinder' to reach the idle state
        Change charm config of 'cinder' 'openstack-origin' to 'cloud:focal-victoria'
        Upgrade plan for units: cinder/0
            Ψ Upgrade plan for unit 'cinder/0'
                Pause the unit: 'cinder/0'
                Upgrade the unit: 'cinder/0'
                Resume the unit: 'cinder/0'
        Wait for up to 300s for app 'cinder' to reach the idle state
        Verify that the workload of 'cinder' has been upgraded on units: cinder/0
    """
    )
    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
    units = {
        f"cinder/{i}": Unit(
            name=f"cinder/{i}",
            workload_version="16.4.2",
            machine=machines[f"{i}"],
        )
        for i in range(3)
    }
    cinder = OpenStackApplication(
        name="cinder",
        can_upgrade_to="ussuri/stable",
        charm="cinder",
        channel="ussuri/stable",
        config={
            "openstack-origin": {"value": "distro"},
            "action-managed-upgrade": {"value": False},
        },
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units=units,
        workload_version="16.4.2",
    )

    plan = cinder.generate_upgrade_plan(target, False, [units["cinder/0"]])

    assert str(plan) == exp_plan


def test_swift_application_not_supported(model):
    """Test Swift application raising ApplicationNotSupported error."""
    target = OpenStackRelease("victoria")
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = Swift(
        name="swift-proxy",
        can_upgrade_to="ussuri/stable",
        charm="swift-proxy",
        channel="ussuri/stable",
        config={},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "swift-proxy/0": Unit(
                name="swift-proxy/0",
                workload_version="2.25.0",
                machine=machines["0"],
            )
        },
        workload_version="2.25.0",
    )

    exp_error = (
        "'swift-proxy' application is not currently supported by COU. Please manually "
        "upgrade it."
    )

    with pytest.raises(ApplicationNotSupported, match=exp_error):
        app.generate_upgrade_plan(target, False)


def test_core_wrong_channel(model):
    """Test when an OpenStack charm is with a channel that doesn't match the workload version."""
    target = OpenStackRelease("victoria")
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = Keystone(
        name="keystone",
        can_upgrade_to="",
        charm="keystone",
        channel="wallaby/stable",
        config={
            "openstack-origin": {"value": "distro"},
            "action-managed-upgrade": {"value": True},
        },
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "keystone/0": Unit(
                name="keystone/0",
                workload_version="17.0.1",
                machine=machines["0"],
            )
        },
        workload_version="17.1.0",
    )

    # plan will raise exception because the channel is on wallaby and was expected to be on ussuri
    # or victoria. The user will need manual intervention
    with pytest.raises(ApplicationError, match=".*unexpected channel.*"):
        app.generate_upgrade_plan(target, force=False)


@pytest.mark.asyncio
async def test_resume_nova_compute_success(model):
    """Verify that the success case resumes without calling workarounds."""
    model.run_action.return_value = Mock(status="completed")
    unit = Unit(
        name="nova-compute/0",
        machine=generate_cou_machine("0", "az-0"),
        workload_version="21.2.4",
        subordinates=[SubordinateUnit(name="ceilometer-agent/0", charm="ceilometer-agent")],
    )

    await resume_nova_compute_unit(model, unit)

    model.run_action.assert_awaited_once_with("nova-compute/0", "resume", raise_on_failure=False)
    model.run_on_unit.assert_not_awaited()
    model.update_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_resume_nova_compute_unknown_failure(model):
    """Verify that the unknown failure case bails out."""
    model.run_action.return_value = Mock(
        status="failed", safe_data={"message": "it crashed and we don't know why"}
    )
    unit = Unit(
        name="nova-compute/0",
        machine=generate_cou_machine("0", "az-0"),
        workload_version="21.2.4",
        subordinates=[SubordinateUnit(name="ceilometer-agent/0", charm="ceilometer-agent")],
    )

    with pytest.raises(ActionFailed, match="it crashed and we don't know why"):
        await resume_nova_compute_unit(model, unit)

    model.run_action.assert_awaited_once_with("nova-compute/0", "resume", raise_on_failure=False)
    model.run_on_unit.assert_not_awaited()
    model.update_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_resume_nova_compute_ceilometer_failure(model):
    """Verify that the ceilometer failure case performs the workaround."""
    model.run_action.return_value = Mock(
        status="failed",
        safe_data={
            "message": (
                "Action resume failed: Couldn't resume: "
                "ceilometer-agent-compute didn't resume cleanly.; "
                "Services not running that should be: ceilometer-agent-compute"
            ),
        },
    )
    unit = Unit(
        name="nova-compute/0",
        machine=generate_cou_machine("0", "az-0"),
        workload_version="21.2.4",
        subordinates=[SubordinateUnit(name="ceilometer-agent/0", charm="ceilometer-agent")],
    )

    await resume_nova_compute_unit(model, unit)

    model.run_action.assert_awaited_once_with("nova-compute/0", "resume", raise_on_failure=False)
    model.run_on_unit.assert_awaited_once_with(
        "nova-compute/0", "sudo systemctl restart ceilometer-agent-compute"
    )
    model.update_status.has_awaits(call("nova-compute/0"), call("ceilometer-agent/0"))
    assert model.update_status.await_count == 2


@pytest.mark.asyncio
@patch("cou.apps.base.OpenStackApplication._verify_nova_compute")
@patch("cou.apps.base.OpenStackApplication._get_refresh_charm_steps")
@patch("cou.apps.base.OpenStackApplication._get_upgrade_current_release_packages_step")
async def test_neutron_api_pre_upgrade_steps(
    mock_upgrade_package, mock_refresh_charm, mock_verify_nova_compute, model
):
    """Test neutron api pre upgrade steps verifying all nova computes."""
    target = OpenStackRelease("wallaby")
    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
    units = (
        {
            f"neutron-api/{i}": Unit(
                name=f"neutron-api/{i}",
                workload_version="17.0.0",
                machine=machines[f"{i}"],
            )
            for i in range(3)
        },
    )
    app = NeutronApi(
        name="neutron-api",
        can_upgrade_to="wallaby/stable",
        charm="neutron-api",
        channel="victoria/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units=units,
        workload_version="17.0.0",
    )
    app.pre_upgrade_steps(target, units)

    mock_verify_nova_compute.assert_called_once_with(target)
    mock_upgrade_package.assert_called_once_with(units)
    mock_refresh_charm.assert_called_once_with(target)
