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

from cou.apps.channel_based import ChannelBasedApplication
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


def test_application_versionless(model):
    """Test application without version."""
    machines = {"0": MagicMock(spec_set=COUMachine)}
    units = {
        "glance-simplestreams-sync/0": COUUnit(
            name="glance-simplestreams-sync/0",
            workload_version="",
            machine=machines["0"],
        )
    }
    app = ChannelBasedApplication(
        name="glance-simplestreams-sync",
        can_upgrade_to="",
        charm="glance-simplestreams-sync",
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
        units=units,
        workload_version="",
    )

    assert app.current_os_release == "ussuri"
    assert app.is_versionless is True
    assert app.unit_max_os_version(units["glance-simplestreams-sync/0"]) == app.channel_codename


def test_application_gnocchi_ussuri(model):
    """Test the Gnocchi ChannelBasedApplication with Ussuri."""
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = ChannelBasedApplication(
        name="gnocchi",
        can_upgrade_to="",
        charm="gnocchi",
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
            "gnocchi/0": COUUnit(
                name="gnocchi/0",
                workload_version="4.3.4",
                machine=machines["0"],
            )
        },
        workload_version="4.3.4",
    )

    assert app.current_os_release == "ussuri"
    assert app.is_versionless is False


def test_application_gnocchi_xena(model):
    """Test the Gnocchi ChannelBasedApplication with Xena.

    The workload version is the same for xena and yoga, but current_os_release is based on
    the channel.
    """
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = ChannelBasedApplication(
        name="gnocchi",
        can_upgrade_to="",
        charm="gnocchi",
        channel="xena/stable",
        config={"openstack-origin": {"value": "cloud:focal-xena"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "gnocchi/0": COUUnit(
                name="gnocchi/0",
                workload_version="4.4.1",
                machine=machines["0"],
            )
        },
        workload_version="4.4.1",
    )

    assert app.current_os_release == "xena"
    assert app.is_versionless is False


def test_application_designate_bind_ussuri(model):
    """Test the Designate-bind ChannelBasedApplication with Ussuri.

    The workload version is the same from ussuri to yoga, but current_os_release is based on
    the channel.
    """
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = ChannelBasedApplication(
        name="designate-bind",
        can_upgrade_to="",
        charm="designate-bind",
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
            "designate-bind/0": COUUnit(
                name="designate-bind/0",
                workload_version="9.16.1",
                machine=machines["0"],
            )
        },
        workload_version="9.16.1",
    )

    assert app.current_os_release == "ussuri"
    assert app.is_versionless is False


def test_application_versionless_upgrade_plan_ussuri_to_victoria(model):
    """Test generating plan for glance-simplestreams-sync (ChannelBasedApplication)."""
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = ChannelBasedApplication(
        name="glance-simplestreams-sync",
        can_upgrade_to="ussuri/stable",
        charm="glance-simplestreams-sync",
        channel="ussuri/stable",
        config={"openstack-origin": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "glance-simplestreams-sync/0": COUUnit(
                name="glance-simplestreams-sync/0",
                workload_version="",
                machine=machines["0"],
            )
        },
        workload_version="",
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
                app.name,
                {f"{app.origin_setting}": "cloud:focal-victoria"},
            ),
        ),
    ]

    add_steps(expected_plan, upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)

    assert_steps(upgrade_plan, expected_plan)


def test_application_gnocchi_upgrade_plan_ussuri_to_victoria(model):
    """Test generating plan for Gnocchi (ChannelBasedApplication).

    Updating Gnocchi from ussuri to victoria increases the workload version from 4.3.4 to 4.4.0.
    """
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = ChannelBasedApplication(
        name="gnocchi",
        can_upgrade_to="ussuri/stable",
        charm="gnocchi",
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
            "gnocchi/0": COUUnit(
                name="gnocchi/0",
                workload_version="4.3.4",
                machine=machines["0"],
            )
        },
        workload_version="4.3.4",
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
                app.name,
                {f"{app.origin_setting}": "cloud:focal-victoria"},
            ),
        ),
        PostUpgradeStep(
            description=f"Wait 300s for app {app.name} to reach the idle state.",
            parallel=False,
            coro=model.wait_for_active_idle(300, apps=[app.name]),
        ),
        PostUpgradeStep(
            description=(
                f"Check if the workload of '{app.name}' has been upgraded on units: "
                f"{', '.join([unit for unit in app.units.keys()])}"
            ),
            parallel=False,
            coro=app._verify_workload_upgrade(target, list(app.units.values())),
        ),
    ]

    add_steps(expected_plan, upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)

    assert_steps(upgrade_plan, expected_plan)


def test_application_designate_bind_upgrade_plan_ussuri_to_victoria(model):
    """Test generating plan for Designate-bind (ChannelBasedApplication)."""
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = ChannelBasedApplication(
        name="designate-bind",
        can_upgrade_to="ussuri/stable",
        charm="designate-bind",
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
            "designate-bind/0": COUUnit(
                name="designate-bind/0",
                workload_version="9.16.1",
                machine=machines["0"],
            )
        },
        workload_version="9.16.1",
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
                app.name,
                {f"{app.origin_setting}": "cloud:focal-victoria"},
            ),
        ),
        PostUpgradeStep(
            description=f"Wait 300s for app {app.name} to reach the idle state.",
            parallel=False,
            coro=model.wait_for_active_idle(300, apps=[app.name]),
        ),
        PostUpgradeStep(
            description=(
                f"Check if the workload of '{app.name}' has been upgraded on units: "
                f"{', '.join([unit for unit in app.units.keys()])}"
            ),
            parallel=False,
            coro=app._verify_workload_upgrade(target, list(app.units.values())),
        ),
    ]

    add_steps(expected_plan, upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)

    assert_steps(upgrade_plan, expected_plan)
