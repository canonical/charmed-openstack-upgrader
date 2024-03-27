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
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from juju.client._definitions import ApplicationStatus, UnitStatus

from cou.apps.base import OpenStackApplication
from cou.apps.core import Keystone, NovaCompute
from cou.exceptions import ApplicationError, HaltUpgradePlanGeneration
from cou.steps import (
    ApplicationUpgradePlan,
    PostUpgradeStep,
    PreUpgradeStep,
    UnitUpgradeStep,
    UpgradeStep,
)
from cou.utils import app_utils
from cou.utils import nova_compute as nova_compute_utils
from cou.utils.juju_utils import Machine, Unit
from cou.utils.openstack import OpenStackRelease
from tests.unit.utils import assert_steps, dedent_plan, generate_cou_machine


def test_application_different_wl(model):
    """The OpenStack version is considered the lowest of the units."""
    machines = {
        "0": MagicMock(spec_set=Machine),
        "1": MagicMock(spec_set=Machine),
        "2": MagicMock(spec_set=Machine),
    }
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
    assert OpenStackRelease("victoria") in app.os_release_units
    assert app.current_os_release == OpenStackRelease("ussuri")


def test_application_no_origin_config(model):
    """Test Keystone application without origin."""
    machines = {"0": MagicMock(spec_set=Machine)}
    app = Keystone(
        name="keystone",
        can_upgrade_to="ussuri/stable",
        charm="keystone",
        channel="ussuri/stable",
        config={},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "keystone/0": Unit(
                name="keystone/0",
                workload_version="18.0.1",
                machine=machines["0"],
            )
        },
        workload_version="18.1.0",
    )

    assert app.os_origin == ""
    assert app.apt_source_codename is None


def test_application_empty_origin_config(model):
    """Test Keystone application with empty origin."""
    machines = {"0": MagicMock(spec_set=Machine)}
    app = Keystone(
        name="keystone",
        can_upgrade_to="ussuri/stable",
        charm="keystone",
        channel="ussuri/stable",
        config={"source": {"value": ""}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "keystone/0": Unit(
                name="keystone/0",
                workload_version="18.0.1",
                machine=machines["0"],
            )
        },
        workload_version="18.1.0",
    )

    assert app.apt_source_codename is None


def test_application_unexpected_channel(model):
    """Test Keystone application with unexpected channel."""
    target = OpenStackRelease("xena")
    exp_msg = (
        "'keystone' has unexpected channel: 'ussuri/stable' for the current workload version "
        "and OpenStack release: 'wallaby'. Possible channels are: wallaby/stable"
    )
    machines = {"0": MagicMock(spec_set=Machine)}
    app = Keystone(
        name="keystone",
        can_upgrade_to="ussuri/stable",
        charm="keystone",
        channel="ussuri/stable",
        config={"source": {"value": ""}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "keystone/0": Unit(
                name="keystone/0",
                workload_version="19.0.1",
                machine=machines["0"],
            )
        },
        workload_version="19.1.0",
    )

    with pytest.raises(ApplicationError, match=exp_msg):
        app.generate_upgrade_plan(target, False)


@pytest.mark.parametrize(
    "source_value",
    ["ppa:myteam/ppa", "cloud:xenial-proposed/ocata", "http://my.archive.com/ubuntu main"],
)
def test_application_unknown_source(source_value, model):
    """Test Keystone application with unknown source."""
    machines = {"0": MagicMock(spec_set=Machine)}
    exp_msg = f"'keystone' has an invalid 'source': {source_value}"
    app = Keystone(
        name="keystone",
        can_upgrade_to="ussuri/stable",
        charm="keystone",
        channel="ussuri/stable",
        config={"source": {"value": source_value}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "keystone/0": Unit(
                name="keystone/0",
                workload_version="19.0.1",
                machine=machines["0"],
            )
        },
        workload_version="19.1.0",
    )

    with pytest.raises(ApplicationError, match=exp_msg):
        app.apt_source_codename


@pytest.mark.asyncio
async def test_application_verify_workload_upgrade(model):
    """Test Kyestone application check successful upgrade."""
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=Machine)}
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
    exp_msg = "Cannot upgrade units 'keystone/0' to victoria."
    machines = {"0": MagicMock(spec_set=Machine)}
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
    machines = {"0": MagicMock(spec_set=Machine)}
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
            coro=model.upgrade_charm(app.name, "ussuri/stable", switch=None),
        ),
        UpgradeStep(
            description=f"Change charm config of '{app.name}' 'action-managed-upgrade' to 'False'",
            parallel=False,
            coro=model.set_application_config(app.name, {"action-managed-upgrade": False}),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: 'victoria/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "victoria/stable"),
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
            description=f"Wait for up to 1800s for model '{model.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_active_idle(1800, apps=None),
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
    machines = {"0": MagicMock(spec_set=Machine)}
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
        UpgradeStep(
            description=f"Change charm config of '{app.name}' 'action-managed-upgrade' to 'False'",
            parallel=False,
            coro=model.set_application_config(app.name, {"action-managed-upgrade": False}),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: 'victoria/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "victoria/stable"),
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
            description=f"Wait for up to 1800s for model '{model.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_active_idle(1800, apps=None),
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


def test_upgrade_plan_channel_on_next_os_release(model):
    """Test generate plan to upgrade Keystone from Ussuri to Victoria with updated channel.

    The app channel it's already on next OpenStack release.
    """
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=Machine)}
    app = Keystone(
        name="keystone",
        can_upgrade_to="victoria/stable",
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
            description=f"Change charm config of '{app.name}' 'action-managed-upgrade' to 'False'",
            parallel=False,
            coro=model.set_application_config(app.name, {"action-managed-upgrade": False}),
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
            description=f"Wait for up to 1800s for model '{model.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_active_idle(1800, apps=None),
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
    machines = {"0": MagicMock(spec_set=Machine)}
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
            coro=model.upgrade_charm(app.name, "ussuri/stable", switch=None),
        ),
        UpgradeStep(
            description=f"Change charm config of '{app.name}' 'action-managed-upgrade' to 'False'",
            parallel=False,
            coro=model.set_application_config(app.name, {"action-managed-upgrade": False}),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: 'victoria/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "victoria/stable"),
        ),
        PostUpgradeStep(
            description=f"Wait for up to 1800s for model '{model.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_active_idle(1800, apps=None),
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
    machines = {"0": MagicMock(spec_set=Machine)}
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
    machines = {"0": MagicMock(spec_set=Machine)}
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
            coro=model.upgrade_charm(app.name, "ussuri/stable", switch=None),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: 'victoria/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "victoria/stable"),
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
            description=f"Wait for up to 1800s for model '{model.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_active_idle(1800, apps=None),
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


@pytest.mark.parametrize("force", [True, False])
# add_step check if the step added is from BaseStep, so the return is an empty UnitUpgradeStep
@patch("cou.apps.core.NovaCompute._get_enable_scheduler_step", return_value=UnitUpgradeStep())
@patch("cou.apps.core.NovaCompute._get_resume_unit_step", return_value=UnitUpgradeStep())
@patch("cou.apps.core.NovaCompute._get_openstack_upgrade_step", return_value=UnitUpgradeStep())
@patch("cou.apps.core.NovaCompute._get_pause_unit_step", return_value=UnitUpgradeStep())
@patch("cou.apps.core.NovaCompute._get_empty_hypervisor_step", return_value=UnitUpgradeStep())
@patch("cou.apps.core.NovaCompute._get_disable_scheduler_step", return_value=UnitUpgradeStep())
def test_nova_compute_get_unit_upgrade_steps(
    mock_disable,
    mock_empty,
    mock_pause,
    mock_upgrade,
    mock_resume,
    mock_enable,
    model,
    force,
):
    app = _generate_nova_compute_app(model)
    unit = app.units["nova-compute/0"]

    app._get_unit_upgrade_steps(unit, force)

    mock_disable.assert_called_once_with(unit)
    if force:
        mock_empty.assert_not_called()
    else:
        mock_empty.assert_called_once_with(unit)

    mock_pause.assert_called_once_with(unit, not force)
    mock_upgrade.assert_called_once_with(unit, not force)
    mock_resume.assert_called_once_with(unit, not force)
    mock_enable.assert_called_once_with(unit)


def test_nova_compute_get_empty_hypervisor_step(model):
    app = _generate_nova_compute_app(model)
    units = list(app.units.values())
    unit = units[0]

    expected_step = UpgradeStep(
        description=f"Verify that unit '{unit.name}' has no VMs running",
        coro=nova_compute_utils.verify_empty_hypervisor(unit, model),
    )
    assert app._get_empty_hypervisor_step(unit) == expected_step


def test_nova_compute_get_enable_scheduler_step(model):
    app = _generate_nova_compute_app(model)
    units = list(app.units.values())
    unit = units[0]

    expected_step = UpgradeStep(
        description=f"Enable nova-compute scheduler from unit: '{unit.name}'",
        coro=model.run_action(unit_name=unit.name, action_name="enable", raise_on_failure=True),
    )
    assert app._get_enable_scheduler_step(unit) == expected_step


def test_nova_compute_get_disable_scheduler_step(model):
    app = _generate_nova_compute_app(model)
    units = list(app.units.values())
    unit = units[0]

    expected_step = UpgradeStep(
        description=f"Disable nova-compute scheduler from unit: '{unit.name}'",
        coro=model.run_action(unit_name=unit.name, action_name="disable", raise_on_failure=True),
    )
    assert app._get_disable_scheduler_step(unit) == expected_step


def _generate_nova_compute_app(model):
    """Generate NovaCompute class."""
    charm = app_name = "nova-compute"
    channel = "ussuri/stable"

    units = {
        f"nova-compute/{unit_num}": Unit(f"nova-compute/{unit_num}", MagicMock(), MagicMock())
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
        Upgrade software packages of 'nova-compute' from the current APT repositories
            Upgrade software packages on unit 'nova-compute/0'
            Upgrade software packages on unit 'nova-compute/1'
            Upgrade software packages on unit 'nova-compute/2'
        Refresh 'nova-compute' to the latest revision of 'ussuri/stable'
        Change charm config of 'nova-compute' 'action-managed-upgrade' to 'True'
        Upgrade 'nova-compute' to the new channel: 'victoria/stable'
        Change charm config of 'nova-compute' 'source' to 'cloud:focal-victoria'
        Upgrade plan for units: nova-compute/0, nova-compute/1, nova-compute/2
            Upgrade plan for unit 'nova-compute/0'
                Disable nova-compute scheduler from unit: 'nova-compute/0'
                Verify that unit 'nova-compute/0' has no VMs running
                ├── Pause the unit: 'nova-compute/0'
                ├── Upgrade the unit: 'nova-compute/0'
                ├── Resume the unit: 'nova-compute/0'
                Enable nova-compute scheduler from unit: 'nova-compute/0'
            Upgrade plan for unit 'nova-compute/1'
                Disable nova-compute scheduler from unit: 'nova-compute/1'
                Verify that unit 'nova-compute/1' has no VMs running
                ├── Pause the unit: 'nova-compute/1'
                ├── Upgrade the unit: 'nova-compute/1'
                ├── Resume the unit: 'nova-compute/1'
                Enable nova-compute scheduler from unit: 'nova-compute/1'
            Upgrade plan for unit 'nova-compute/2'
                Disable nova-compute scheduler from unit: 'nova-compute/2'
                Verify that unit 'nova-compute/2' has no VMs running
                ├── Pause the unit: 'nova-compute/2'
                ├── Upgrade the unit: 'nova-compute/2'
                ├── Resume the unit: 'nova-compute/2'
                Enable nova-compute scheduler from unit: 'nova-compute/2'
        Wait for up to 1800s for model 'test_model' to reach the idle state
        Verify that the workload of 'nova-compute' has been upgraded on units: nova-compute/0, nova-compute/1, nova-compute/2
    """  # noqa: E501 line too long
    )
    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
    units = {
        f"nova-compute/{unit}": Unit(
            name=f"nova-compute/{unit}",
            workload_version="21.0.0",
            machine=machines[f"{unit}"],
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
        Upgrade software packages of 'nova-compute' from the current APT repositories
            Upgrade software packages on unit 'nova-compute/0'
        Refresh 'nova-compute' to the latest revision of 'ussuri/stable'
        Change charm config of 'nova-compute' 'action-managed-upgrade' to 'True'
        Upgrade 'nova-compute' to the new channel: 'victoria/stable'
        Change charm config of 'nova-compute' 'source' to 'cloud:focal-victoria'
        Upgrade plan for units: nova-compute/0
            Upgrade plan for unit 'nova-compute/0'
                Disable nova-compute scheduler from unit: 'nova-compute/0'
                Verify that unit 'nova-compute/0' has no VMs running
                ├── Pause the unit: 'nova-compute/0'
                ├── Upgrade the unit: 'nova-compute/0'
                ├── Resume the unit: 'nova-compute/0'
                Enable nova-compute scheduler from unit: 'nova-compute/0'
        Wait for up to 1800s for model 'test_model' to reach the idle state
        Verify that the workload of 'nova-compute' has been upgraded on units: nova-compute/0
    """
    )
    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
    units = {
        f"nova-compute/{unit}": Unit(
            name=f"nova-compute/{unit}",
            workload_version="21.0.0",
            machine=machines[f"{unit}"],
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
            Upgrade software packages on unit 'cinder/0'
            Upgrade software packages on unit 'cinder/1'
            Upgrade software packages on unit 'cinder/2'
        Refresh 'cinder' to the latest revision of 'ussuri/stable'
        Upgrade 'cinder' to the new channel: 'victoria/stable'
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
            Upgrade software packages on unit 'cinder/0'
        Refresh 'cinder' to the latest revision of 'ussuri/stable'
        Change charm config of 'cinder' 'action-managed-upgrade' to 'True'
        Upgrade 'cinder' to the new channel: 'victoria/stable'
        Change charm config of 'cinder' 'openstack-origin' to 'cloud:focal-victoria'
        Upgrade plan for units: cinder/0
            Upgrade plan for unit 'cinder/0'
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
