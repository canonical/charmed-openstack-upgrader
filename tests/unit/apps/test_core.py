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
from unittest.mock import AsyncMock, MagicMock

import pytest
from juju.client._definitions import ApplicationStatus, UnitStatus

from cou.apps.core import Keystone
from cou.exceptions import (
    ApplicationError,
    HaltUpgradePlanGeneration,
    MismatchedOpenStackVersions,
)
from cou.steps import (
    ApplicationUpgradePlan,
    PostUpgradeStep,
    PreUpgradeStep,
    UnitUpgradeStep,
    UpgradeStep,
)
from cou.utils import app_utils
from cou.utils.juju_utils import COUMachine, COUUnit
from cou.utils.openstack import OpenStackRelease
from tests.unit.apps.utils import add_steps
from tests.unit.utils import assert_steps


def test_application_different_wl(model):
    """Different OpenStack Version on units if workload version is different."""
    exp_error_msg = (
        "Units of application keystone are running mismatched OpenStack versions: "
        r"'ussuri': \['keystone\/0', 'keystone\/1'\], 'victoria': \['keystone\/2'\]. "
        "This is not currently handled."
    )

    machines = {
        "0": MagicMock(spec_set=COUMachine),
        "1": MagicMock(spec_set=COUMachine),
        "2": MagicMock(spec_set=COUMachine),
    }
    units = {
        "keystone/0": COUUnit(
            name="keystone/0",
            workload_version="17.0.1",
            machine=machines["0"],
        ),
        "keystone/1": COUUnit(
            name="keystone/1",
            workload_version="17.0.1",
            machine=machines["1"],
        ),
        "keystone/2": COUUnit(
            name="keystone/2",
            workload_version="18.1.0",
            machine=machines["2"],
        ),
    }
    app = Keystone(
        name="keystone",
        can_upgrade_to=["ussuri/stable"],
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

    with pytest.raises(MismatchedOpenStackVersions, match=exp_error_msg):
        app.current_os_release


def test_application_no_origin_config(model):
    """Test Keystone application without origin."""
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = Keystone(
        name="keystone",
        can_upgrade_to=["ussuri/stable"],
        charm="keystone",
        channel="ussuri/stable",
        config={},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "keystone/0": COUUnit(
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
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = Keystone(
        name="keystone",
        can_upgrade_to=["ussuri/stable"],
        charm="keystone",
        channel="ussuri/stable",
        config={"source": {"value": ""}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "keystone/0": COUUnit(
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
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = Keystone(
        name="keystone",
        can_upgrade_to=["ussuri/stable"],
        charm="keystone",
        channel="ussuri/stable",
        config={"source": {"value": ""}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "keystone/0": COUUnit(
                name="keystone/0",
                workload_version="19.0.1",
                machine=machines["0"],
            )
        },
        workload_version="19.1.0",
    )

    with pytest.raises(ApplicationError, match=exp_msg):
        app.generate_upgrade_plan(target)


@pytest.mark.parametrize(
    "source_value",
    ["ppa:myteam/ppa", "cloud:xenial-proposed/ocata", "http://my.archive.com/ubuntu main"],
)
def test_application_unknown_source(source_value, model):
    """Test Keystone application with unknown source."""
    machines = {"0": MagicMock(spec_set=COUMachine)}
    exp_msg = f"'keystone' has an invalid 'source': {source_value}"
    app = Keystone(
        name="keystone",
        can_upgrade_to=["ussuri/stable"],
        charm="keystone",
        channel="ussuri/stable",
        config={"source": {"value": source_value}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "keystone/0": COUUnit(
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
async def test_application_check_upgrade(model):
    """Test Kyestone application check successful upgrade."""
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = Keystone(
        name="keystone",
        can_upgrade_to=["ussuri/stable"],
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
            "keystone/0": COUUnit(
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

    await app._check_upgrade(target)


@pytest.mark.asyncio
async def test_application_check_upgrade_fail(model):
    """Test Kyestone application check unsuccessful upgrade."""
    target = OpenStackRelease("victoria")
    exp_msg = "Cannot upgrade units 'keystone/0' to victoria."
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = Keystone(
        name="keystone",
        can_upgrade_to=["ussuri/stable"],
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
            "keystone/0": COUUnit(
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
        await app._check_upgrade(target)


def test_upgrade_plan_ussuri_to_victoria(model):
    """Test generate plan to upgrade Keystone from Ussuri to Victoria."""
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = Keystone(
        name="keystone",
        can_upgrade_to=["ussuri/stable"],
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
            f"keystone/{unit}": COUUnit(
                name=f"keystone/{unit}",
                workload_version="17.0.1",
                machine=machines["0"],
            )
            for unit in range(3)
        },
        workload_version="17.1.0",
    )
    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}"
    )
    upgrade_packages = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    for unit in app.units.values():
        upgrade_packages.add_step(
            UnitUpgradeStep(
                description=f"Upgrade software packages on unit {unit.name}",
                coro=app_utils.upgrade_packages(unit.name, model, None),
            )
        )

    upgrade_steps = [
        upgrade_packages,
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of 'ussuri/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "ussuri/stable", switch=None),
        ),
        UpgradeStep(
            description=f"Change charm config of '{app.name}' 'action-managed-upgrade' to False.",
            parallel=False,
            coro=model.set_application_config(app.name, {"action-managed-upgrade": False}),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: 'victoria/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "victoria/stable"),
        ),
        UpgradeStep(
            description=(
                f"Change charm config of '{app.name}' "
                f"'{app.origin_setting}' to 'cloud:focal-victoria'"
            ),
            parallel=False,
            coro=model.set_application_config(
                app.name, {f"{app.origin_setting}": "cloud:focal-victoria"}
            ),
        ),
        PostUpgradeStep(
            description=f"Wait 1800s for model {model.name} to reach the idle state.",
            parallel=False,
            coro=model.wait_for_active_idle(1800, apps=None),
        ),
        PostUpgradeStep(
            description=f"Check if the workload of '{app.name}' has been upgraded",
            parallel=False,
            coro=app._check_upgrade(target),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target)
    assert_steps(upgrade_plan, expected_plan)


def test_upgrade_plan_ussuri_to_victoria_ch_migration(model):
    """Test generate plan to upgrade Keystone from Ussuri to Victoria with charmhub migration."""
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = Keystone(
        name="keystone",
        can_upgrade_to=["ussuri/stable"],
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
            f"keystone/{unit}": COUUnit(
                name=f"keystone/{unit}",
                workload_version="17.0.1",
                machine=machines["0"],
            )
            for unit in range(3)
        },
        workload_version="17.1.0",
    )
    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}"
    )
    upgrade_packages = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    for unit in app.units.values():
        upgrade_packages.add_step(
            UnitUpgradeStep(
                description=f"Upgrade software packages on unit {unit.name}",
                coro=app_utils.upgrade_packages(unit.name, model, None),
            )
        )

    upgrade_steps = [
        upgrade_packages,
        PreUpgradeStep(
            description=f"Migration of '{app.name}' from charmstore to charmhub",
            parallel=False,
            coro=model.upgrade_charm(app.name, "ussuri/stable", switch="ch:keystone"),
        ),
        UpgradeStep(
            description=f"Change charm config of '{app.name}' 'action-managed-upgrade' to False.",
            parallel=False,
            coro=model.set_application_config(app.name, {"action-managed-upgrade": False}),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: 'victoria/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "victoria/stable"),
        ),
        UpgradeStep(
            description=(
                f"Change charm config of '{app.name}' "
                f"'{app.origin_setting}' to 'cloud:focal-victoria'"
            ),
            parallel=False,
            coro=model.set_application_config(
                app.name, {f"{app.origin_setting}": "cloud:focal-victoria"}
            ),
        ),
        PostUpgradeStep(
            description=f"Wait 1800s for model {model.name} to reach the idle state.",
            parallel=False,
            coro=model.wait_for_active_idle(1800, apps=None),
        ),
        PostUpgradeStep(
            description=f"Check if the workload of '{app.name}' has been upgraded",
            parallel=False,
            coro=app._check_upgrade(target),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target)
    assert_steps(upgrade_plan, expected_plan)


def test_upgrade_plan_channel_on_next_os_release(model):
    """Test generate plan to upgrade Keystone from Ussuri to Victoria with updated channel.

    The app channel it's already on next OpenStack release.
    """
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = Keystone(
        name="keystone",
        can_upgrade_to=["victoria/stable"],
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
            f"keystone/{unit}": COUUnit(
                name=f"keystone/{unit}",
                workload_version="17.0.1",
                machine=machines["0"],
            )
            for unit in range(3)
        },
        workload_version="17.1.0",
    )
    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}"
    )
    # no sub-step for refresh current channel or next channel
    upgrade_packages = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    for unit in app.units.values():
        upgrade_packages.add_step(
            UnitUpgradeStep(
                description=f"Upgrade software packages on unit {unit.name}",
                coro=app_utils.upgrade_packages(unit.name, model, None),
            )
        )

    upgrade_steps = [
        upgrade_packages,
        UpgradeStep(
            description=f"Change charm config of '{app.name}' 'action-managed-upgrade' to False.",
            parallel=False,
            coro=model.set_application_config(app.name, {"action-managed-upgrade": False}),
        ),
        UpgradeStep(
            description=(
                f"Change charm config of '{app.name}' "
                f"'{app.origin_setting}' to 'cloud:focal-victoria'"
            ),
            parallel=False,
            coro=model.set_application_config(
                app.name, {f"{app.origin_setting}": "cloud:focal-victoria"}
            ),
        ),
        PostUpgradeStep(
            description=f"Wait 1800s for model {model.name} to reach the idle state.",
            parallel=False,
            coro=model.wait_for_active_idle(1800, apps=None),
        ),
        PostUpgradeStep(
            description=f"Check if the workload of '{app.name}' has been upgraded",
            parallel=False,
            coro=app._check_upgrade(target),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target)
    assert_steps(upgrade_plan, expected_plan)


def test_upgrade_plan_origin_already_on_next_openstack_release(model):
    """Test generate plan to upgrade Keystone from Ussuri to Victoria with origin changed.

    The app config option openstack-origin it's already on next OpenStack release.
    """
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = Keystone(
        name="keystone",
        can_upgrade_to=["ussuri/stable"],
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
            f"keystone/{unit}": COUUnit(
                name=f"keystone/{unit}",
                workload_version="17.0.1",
                machine=machines["0"],
            )
            for unit in range(3)
        },
        workload_version="17.1.0",
    )
    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}"
    )
    upgrade_packages = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    for unit in app.units.values():
        upgrade_packages.add_step(
            UnitUpgradeStep(
                description=f"Upgrade software packages on unit {unit.name}",
                coro=app_utils.upgrade_packages(unit.name, model, None),
            )
        )

    upgrade_steps = [
        upgrade_packages,
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of 'ussuri/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "ussuri/stable", switch=None),
        ),
        UpgradeStep(
            description=f"Change charm config of '{app.name}' 'action-managed-upgrade' to False.",
            parallel=False,
            coro=model.set_application_config(app.name, {"action-managed-upgrade": False}),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: 'victoria/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "victoria/stable"),
        ),
        PostUpgradeStep(
            description=f"Wait 1800s for model {model.name} to reach the idle state.",
            parallel=False,
            coro=model.wait_for_active_idle(1800, apps=None),
        ),
        PostUpgradeStep(
            description=f"Check if the workload of '{app.name}' has been upgraded",
            parallel=False,
            coro=app._check_upgrade(target),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target)
    assert_steps(upgrade_plan, expected_plan)


def test_upgrade_plan_application_already_upgraded(model):
    """Test generate plan to upgrade Keystone from Victoria to Victoria."""
    exp_error_msg = (
        "Application 'keystone' already configured for release equal or greater "
        "than victoria. Ignoring."
    )
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = Keystone(
        name="keystone",
        can_upgrade_to=[],
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
            f"keystone/{unit}": COUUnit(
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
        app.generate_upgrade_plan(target)


def test_upgrade_plan_application_already_disable_action_managed(model):
    """Test generate plan to upgrade Keystone with managed upgrade disabled."""
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = Keystone(
        name="keystone",
        can_upgrade_to=["ussuri/stable"],
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
            f"keystone/{unit}": COUUnit(
                name=f"keystone/{unit}",
                workload_version="17.0.1",
                machine=machines["0"],
            )
            for unit in range(3)
        },
        workload_version="17.1.0",
    )
    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}"
    )
    upgrade_packages = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    for unit in app.units.values():
        upgrade_packages.add_step(
            UnitUpgradeStep(
                description=f"Upgrade software packages on unit {unit.name}",
                coro=app_utils.upgrade_packages(unit.name, model, None),
            )
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
            description=(
                f"Change charm config of '{app.name}' "
                f"'{app.origin_setting}' to 'cloud:focal-victoria'"
            ),
            parallel=False,
            coro=model.set_application_config(
                app.name, {f"{app.origin_setting}": "cloud:focal-victoria"}
            ),
        ),
        PostUpgradeStep(
            description=f"Wait 1800s for model {model.name} to reach the idle state.",
            parallel=False,
            coro=model.wait_for_active_idle(1800, apps=None),
        ),
        PostUpgradeStep(
            description=f"Check if the workload of '{app.name}' has been upgraded",
            parallel=False,
            coro=app._check_upgrade(target),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target)
    assert_steps(upgrade_plan, expected_plan)
