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

from cou.apps.channel_based import ChannelBasedApplication
from cou.steps import (
    ApplicationUpgradePlan,
    PostUpgradeStep,
    PreUpgradeStep,
    UnitUpgradeStep,
    UpgradeStep,
)
from cou.utils import app_utils
from cou.utils.juju_utils import Machine, Unit
from cou.utils.openstack import OpenStackRelease
from tests.unit.utils import assert_steps, dedent_plan


def test_application_versionless(model):
    """Test application without version."""
    machines = {"0": MagicMock(spec_set=Machine)}
    units = {
        "glance-simplestreams-sync/0": Unit(
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
    assert app.get_latest_os_version(units["glance-simplestreams-sync/0"]) == app.channel_codename


def test_channel_based_application_latest_stable(model):
    """Test channel based application using latest/stable channel."""
    target = OpenStackRelease("wallaby")

    exp_plan = dedent_plan(
        """\
        Upgrade plan for 'glance-simplestreams-sync' to 'wallaby'
            Upgrade software packages of 'glance-simplestreams-sync' from the current APT repositories
                Upgrade software packages on unit 'glance-simplestreams-sync/0'
            WARNING: Changing 'glance-simplestreams-sync' channel from latest/stable to victoria/stable. \
This may be a charm downgrade, which is generally not supported.
            Upgrade 'glance-simplestreams-sync' to the new channel: 'wallaby/stable'
            Change charm config of 'glance-simplestreams-sync' 'openstack-origin' to 'cloud:focal-wallaby'
    """  # noqa: E501 line too long
    )

    machines = {"0": MagicMock(spec_set=Machine)}
    units = {
        "glance-simplestreams-sync/0": Unit(
            name="glance-simplestreams-sync/0",
            workload_version="",
            machine=machines["0"],
        )
    }
    app = ChannelBasedApplication(
        name="glance-simplestreams-sync",
        can_upgrade_to="",
        charm="glance-simplestreams-sync",
        channel="latest/stable",
        config={
            "openstack-origin": {"value": "distro"},
        },
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units=units,
        workload_version="",
    )
    # app is considered as ussuri because it's using latest/stable, but it won't be considered when
    # calculating the cloud minimum OpenStack release. It will refresh the charm channel to
    # whatever the minimum version of other components are.
    assert app.current_os_release == "ussuri"
    plan = app.generate_upgrade_plan(target, False)
    assert str(plan) == exp_plan


def test_application_gnocchi_ussuri(model):
    """Test the Gnocchi ChannelBasedApplication with Ussuri."""
    machines = {"0": MagicMock(spec_set=Machine)}
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
            "gnocchi/0": Unit(
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
    machines = {"0": MagicMock(spec_set=Machine)}
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
            "gnocchi/0": Unit(
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
    machines = {"0": MagicMock(spec_set=Machine)}
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
            "designate-bind/0": Unit(
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
    machines = {"0": MagicMock(spec_set=Machine)}
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
            "glance-simplestreams-sync/0": Unit(
                name="glance-simplestreams-sync/0",
                workload_version="",
                machine=machines["0"],
            )
        },
        workload_version="",
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
    ]

    expected_plan.add_steps(upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)

    assert_steps(upgrade_plan, expected_plan)


def test_application_gnocchi_upgrade_plan_ussuri_to_victoria(model):
    """Test generating plan for Gnocchi (ChannelBasedApplication).

    Updating Gnocchi from ussuri to victoria increases the workload version from 4.3.4 to 4.4.0.
    """
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=Machine)}
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
            "gnocchi/0": Unit(
                name="gnocchi/0",
                workload_version="4.3.4",
                machine=machines["0"],
            )
        },
        workload_version="4.3.4",
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
                app.name,
                {f"{app.origin_setting}": "cloud:focal-victoria"},
            ),
        ),
        PostUpgradeStep(
            description=f"Wait for up to 300s for app '{app.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_active_idle(300, apps=[app.name]),
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


def test_application_designate_bind_upgrade_plan_ussuri_to_victoria(model):
    """Test generating plan for Designate-bind (ChannelBasedApplication)."""
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=Machine)}
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
            "designate-bind/0": Unit(
                name="designate-bind/0",
                workload_version="9.16.1",
                machine=machines["0"],
            )
        },
        workload_version="9.16.1",
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
            description=f"Wait for up to 300s for app '{app.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_active_idle(300, apps=[app.name]),
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


@pytest.mark.parametrize(
    "channel, origin, release_target, exp_current_channel",
    [
        # using latest/stable will always be N-1 from the target
        ("latest/stable", "ch", "victoria", "ussuri/stable"),
        ("latest/stable", "ch", "wallaby", "victoria/stable"),
        ("latest/stable", "ch", "xena", "wallaby/stable"),
        ("latest/stable", "ch", "yoga", "xena/stable"),
        # from charmstore will always be N-1 from the target
        ("latest", "cs", "victoria", "ussuri/stable"),
        ("latest", "cs", "wallaby", "victoria/stable"),
        ("latest", "cs", "xena", "wallaby/stable"),
        ("latest", "cs", "yoga", "xena/stable"),
        # when using release channel will always point to the channel track
        ("ussuri/stable", "ch", "victoria", "ussuri/stable"),
        ("victoria/stable", "ch", "wallaby", "victoria/stable"),
        ("wallaby/stable", "ch", "xena", "wallaby/stable"),
        ("xena/stable", "ch", "yoga", "xena/stable"),
    ],
)
def test_expected_current_channel_channel_based(
    model, channel, origin, release_target, exp_current_channel
):
    """Test expected current channel for channel base apps."""
    target = OpenStackRelease(release_target)
    app = ChannelBasedApplication(
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

    # expected_current_channel changes if the charm needs crossgrade
    assert app.expected_current_channel(target) == exp_current_channel
