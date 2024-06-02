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
"""Auxiliary application class."""
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from cou.apps.auxiliary import (
    AuxiliaryApplication,
    CephMon,
    CephOsd,
    MysqlInnodbCluster,
    OVNPrincipal,
    RabbitMQServer,
)
from cou.apps.core import NovaCompute
from cou.exceptions import ApplicationError, HaltUpgradePlanGeneration
from cou.steps import (
    ApplicationUpgradePlan,
    PostUpgradeStep,
    PreUpgradeStep,
    UnitUpgradeStep,
    UpgradeStep,
)
from cou.utils import app_utils
from cou.utils.juju_utils import Unit
from cou.utils.openstack import OpenStackRelease
from tests.unit.utils import assert_steps, dedent_plan, generate_cou_machine


def test_auxiliary_app(model):
    """Test auxiliary application.

    The version 3.8 on rabbitmq can be from ussuri to yoga. In that case it will be
    set as yoga.
    """
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = RabbitMQServer(
        name="rabbitmq-server",
        can_upgrade_to="",
        charm="rabbitmq-server",
        channel="3.8/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "rabbitmq-server/0": Unit(
                name="rabbitmq-server/0",
                workload_version="3.8",
                machine=machines["0"],
            )
        },
        workload_version="3.8",
    )
    assert app.channel == "3.8/stable"
    assert app.is_valid_track(app.channel) is True
    assert app.o7k_origin == "distro"
    assert app.apt_source_codename == "ussuri"
    assert app.channel_o7k_release == "yoga"
    assert app.is_subordinate is False

    # the workload version of units are considered as yoga
    assert min(app.o7k_release_units.keys()) == "yoga"
    # application is considered as ussuri because the source is pointing to it
    assert app.o7k_release == "ussuri"


def test_auxiliary_app_cs(model):
    """Test auxiliary application from charm store."""
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = RabbitMQServer(
        name="rabbitmq-server",
        can_upgrade_to="",
        charm="rabbitmq-server",
        channel="stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="cs",
        series="focal",
        subordinate_to=[],
        units={
            "rabbitmq-server/0": Unit(
                name="rabbitmq-server/0",
                workload_version="3.8",
                machine=machines["0"],
            )
        },
        workload_version="3.8",
    )

    assert app.channel == "stable"
    assert app.is_valid_track(app.channel) is False
    assert app.o7k_origin == "distro"
    assert app.apt_source_codename == "ussuri"
    # the workload version of units are considered as yoga
    assert min(app.o7k_release_units.keys()) == "yoga"
    # application is considered as ussuri because the source is pointing to it
    assert app.channel_o7k_release == "ussuri"
    assert app.o7k_release == "ussuri"


def test_auxiliary_upgrade_plan_ussuri_to_victoria_change_channel(model):
    """Test auxiliary upgrade plan from Ussuri to Victoria with change of channel."""
    target = OpenStackRelease("victoria")
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = RabbitMQServer(
        name="rabbitmq-server",
        can_upgrade_to="3.9/stable",
        charm="rabbitmq-server",
        channel="3.8/stable",
        config={
            "source": {"value": "distro"},
            "enable-auto-restarts": {"value": True},
        },
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "rabbitmq-server/0": Unit(
                name="rabbitmq-server/0",
                workload_version="3.8",
                machine=machines["0"],
            )
        },
        workload_version="3.8",
    )

    expected_plan = ApplicationUpgradePlan(f"Upgrade plan for '{app.name}' to '{target}'")
    expected_upgrade_package_step = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    expected_upgrade_package_step.add_steps(
        UnitUpgradeStep(
            description=f"Upgrade software packages on unit '{unit}'",
            parallel=False,
            coro=app_utils.upgrade_packages(unit, model, None),
        )
        for unit in app.units.keys()
    )

    upgrade_steps = [
        expected_upgrade_package_step,
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of '3.8/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "3.8/stable"),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' from '3.8/stable' to the new channel: '3.9/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "3.9/stable"),
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
            description=f"Wait for up to 2400s for model '{model.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_active_idle(2400, apps=None),
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


def test_auxiliary_upgrade_plan_ussuri_to_victoria(model):
    """Test auxiliary upgrade plan from Ussuri to Victoria."""
    target = OpenStackRelease("victoria")
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = RabbitMQServer(
        name="rabbitmq-server",
        can_upgrade_to="3.9/stable",
        charm="rabbitmq-server",
        channel="3.9/stable",
        config={
            "source": {"value": "distro"},
            "enable-auto-restarts": {"value": True},
        },
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "rabbitmq-server/0": Unit(
                name="rabbitmq-server/0",
                workload_version="3.9",
                machine=machines["0"],
            )
        },
        workload_version="3.9",
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
            description=f"Refresh '{app.name}' to the latest revision of '3.9/stable'",
            coro=model.upgrade_charm(app.name, "3.9/stable"),
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
            coro=model.wait_for_active_idle(2400, apps=None),
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


def test_auxiliary_upgrade_plan_ussuri_to_victoria_ch_migration(model):
    """Test auxiliary upgrade plan from Ussuri to Victoria with migration to charmhub."""
    target = OpenStackRelease("victoria")
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = RabbitMQServer(
        name="rabbitmq-server",
        can_upgrade_to="cs:rabbitmq-server",
        charm="rabbitmq-server",
        channel="stable",
        config={
            "source": {"value": "distro"},
            "enable-auto-restarts": {"value": True},
        },
        machines=machines,
        model=model,
        origin="cs",
        series="focal",
        subordinate_to=[],
        units={
            "rabbitmq-server/0": Unit(
                name="rabbitmq-server/0",
                workload_version="3.8",
                machine=machines["0"],
            )
        },
        workload_version="3.8",
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
            f"Migrate '{app.name}' from charmstore to charmhub",
            coro=model.upgrade_charm(app.name, "3.9/stable", switch="ch:rabbitmq-server"),
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
            coro=model.wait_for_active_idle(2400, apps=None),
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


def test_rabbitmq_server_upgrade_plan_ussuri_to_victoria_auto_restart_False(model):
    """Test rabbitmq server upgrade plan from Ussuri to Victoria with enable_auto_restart=False."""
    target = OpenStackRelease("victoria")
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = RabbitMQServer(
        name="rabbitmq-server",
        can_upgrade_to="3.9/stable",
        charm="rabbitmq-server",
        channel="3.9/stable",
        config={
            "source": {"value": "distro"},
            "enable-auto-restarts": {"value": False},
        },
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "rabbitmq-server/0": Unit(
                name="rabbitmq-server/0",
                workload_version="3.9",
                machine=machines["0"],
            ),
        },
        workload_version="3.9",
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
            description=f"Refresh '{app.name}' to the latest revision of '3.9/stable'",
            coro=model.upgrade_charm(app.name, "3.9/stable"),
        ),
    ]
    upgrade_steps += [
        PreUpgradeStep(
            description="Auto restarts is disabled, will"
            f" execute run-deferred-hooks for unit: '{unit.name}'",
            coro=model.run_action(unit.name, "run-deferred-hooks", raise_on_failure=True),
        )
        for unit in app.units.values()
    ]
    upgrade_steps += [
        PreUpgradeStep(
            description=f"Wait for up to 2400s for app '{app.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_active_idle(2400, apps=[app.name]),
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
            description=f"Wait for up to 2400s for app '{app.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_active_idle(2400, apps=[app.name]),
        ),
    ]
    upgrade_steps += [
        PostUpgradeStep(
            description="Auto restarts is disabled, will"
            f" execute run-deferred-hooks for unit: '{unit.name}'",
            coro=model.run_action(unit.name, "run-deferred-hooks", raise_on_failure=True),
        )
        for unit in app.units.values()
    ]
    upgrade_steps += [
        PostUpgradeStep(
            description=f"Wait for up to 2400s for model '{model.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_active_idle(2400, apps=None),
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


def test_auxiliary_upgrade_plan_unknown_track(model):
    """Test auxiliary upgrade plan with unknown track."""
    channel = "2.0/stable"
    exp_msg = (
        f"Channel: {channel} for charm 'rabbitmq-server' on series 'focal' is not supported by "
        "COU. Please take a look at the documentation: "
        "https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html "
        "to see if you are using the right track."
    )
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = RabbitMQServer(
        name="rabbitmq-server",
        can_upgrade_to="3.9/stable",
        charm="rabbitmq-server",
        channel=channel,
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "rabbitmq-server/0": Unit(
                name="rabbitmq-server/0",
                workload_version="3.8",
                machine=machines["0"],
            )
        },
        workload_version="3.8",
    )

    with pytest.raises(ApplicationError, match=exp_msg):
        app._check_channel()


def test_auxiliary_app_unknown_version_raise_ApplicationError(model):
    """Test auxiliary application with unknown workload version."""
    version = "80.5"
    charm = "rabbitmq-server"
    exp_msg = f"'{charm}' with workload version {version} has no compatible OpenStack release."

    machines = {"0": generate_cou_machine("0", "az-0")}
    unit = Unit(name=f"{charm}/0", workload_version=version, machine=machines["0"])
    app = RabbitMQServer(
        name=charm,
        can_upgrade_to="3.8/stable",
        charm=charm,
        channel="3.8/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={unit.name: unit},
        workload_version=version,
    )

    with pytest.raises(ApplicationError, match=exp_msg):
        app.get_latest_o7k_version(unit)


def test_auxiliary_raise_error_unknown_series(model):
    """Test auxiliary application with unknown series."""
    series = "foo"
    channel = "3.8/stable"
    exp_msg = "Series 'foo' is not supported by COU."
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = RabbitMQServer(
        name="rabbitmq-server",
        can_upgrade_to="3.9/stable",
        charm="rabbitmq-server",
        channel=channel,
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series=series,
        subordinate_to=[],
        units={
            "rabbitmq-server/0": Unit(
                name="rabbitmq-server/0",
                workload_version="3.8",
                machine=machines["0"],
            )
        },
        workload_version="3.8",
    )
    with pytest.raises(ApplicationError, match=exp_msg):
        app._check_channel()


@patch("cou.apps.core.OpenStackApplication.o7k_release")
def test_auxiliary_raise_error_o7k_not_on_lookup(o7k_release, model):
    """Test auxiliary upgrade plan with os release not in lookup table.

    Using OpenStack release version that is not on openstack_to_track_mapping.csv table.
    """
    o7k_release.return_value = OpenStackRelease("diablo")
    exp_error_msg = (
        "Channel: 3.8/stable for charm 'rabbitmq-server' on series 'focal' is not supported by "
        "COU. Please take a look at the documentation: "
        "https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html to see if you "
        "are using the right track."
    )
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = RabbitMQServer(
        name="rabbitmq-server",
        can_upgrade_to="",
        charm="rabbitmq-server",
        channel="3.8/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "rabbitmq-server/0": Unit(
                name="rabbitmq-server/0",
                workload_version="3.8",
                machine=machines["0"],
            )
        },
        workload_version="3.8",
    )

    with pytest.raises(ApplicationError, match=exp_error_msg):
        app._check_channel()


def test_auxiliary_raise_halt_upgrade(model):
    """Test auxiliary upgrade plan halt the upgrade.

    The source is already configured to wallaby, so the plan halt with target victoria
    """
    target = OpenStackRelease("victoria")
    charm = "rabbitmq-server"
    exp_msg = (
        f"Application '{charm}' already configured for release equal to or greater than {target}. "
        "Ignoring."
    )
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = RabbitMQServer(
        name=charm,
        can_upgrade_to="",
        charm=charm,
        channel="3.8/stable",
        config={"source": {"value": "cloud:focal-wallaby"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"{charm}/0": Unit(
                name=f"{charm}/0",
                workload_version="3.8",
                machine=machines["0"],
            )
        },
        workload_version="3.8",
    )

    with pytest.raises(HaltUpgradePlanGeneration, match=exp_msg):
        app.generate_upgrade_plan(target, False)


def test_auxiliary_no_origin_setting_raise_halt_upgrade(model):
    """Test auxiliary without origin setting raise halt the plan if necessary."""
    target = OpenStackRelease("victoria")
    charm = "vault"
    exp_msg = (
        f"Application '{charm}' already configured for release equal to or greater than {target}. "
        "Ignoring."
    )
    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
    app = AuxiliaryApplication(
        name=charm,
        # no channel to refresh
        can_upgrade_to="",
        charm=charm,
        channel="1.7/stable",
        # no origin setting
        config={},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"{charm}/0": Unit(
                name=f"{charm}/0",
                workload_version="1.7",
                machine=machines["0"],
            ),
            f"{charm}/1": Unit(
                name=f"{charm}/1",
                workload_version="1.7",
                machine=machines["1"],
            ),
            f"{charm}/2": Unit(
                name=f"{charm}/2",
                workload_version="1.7",
                machine=machines["2"],
            ),
        },
        workload_version="1.7",
    )

    # current OpenStack release is bigger than target
    assert app.o7k_release == OpenStackRelease("yoga")

    with pytest.raises(HaltUpgradePlanGeneration, match=exp_msg):
        app._check_application_target(target)


def test_auxiliary_no_suitable_channel(model):
    """Test auxiliary upgrade plan not suitable channel.

    The OPENSTACK_TO_TRACK_MAPPING can't find a track for rabbitmq, focal, zed.
    """
    target = OpenStackRelease("zed")
    charm = "rabbitmq-server"
    exp_msg = (
        f"Cannot find a suitable '{charm}' charm channel for {target} on series 'focal'. "
        "Please take a look at the documentation: "
        "https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html"
    )
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = RabbitMQServer(
        name=charm,
        can_upgrade_to="",
        charm=charm,
        channel="3.8/stable",
        config={"source": {"value": "cloud:focal-wallaby"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"{charm}/0": Unit(
                name=f"{charm}/0",
                workload_version="3.8",
                machine=machines["0"],
            )
        },
        workload_version="3.8",
    )

    with pytest.raises(ApplicationError, match=exp_msg):
        app.target_channel(target)


def test_ceph_mon_app(model):
    """Test the correctness of instantiating CephMon."""
    charm = "ceph-mon"
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = CephMon(
        name=charm,
        can_upgrade_to="",
        charm=charm,
        channel="pacific/stable",
        config={"source": {"value": "cloud:focal-xena"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"{charm}/0": Unit(
                name=f"{charm}/0",
                workload_version="16.2.0",
                machine=machines["0"],
            )
        },
        workload_version="16.2.0",
    )

    assert app.channel == "pacific/stable"
    assert app.o7k_origin == "cloud:focal-xena"
    assert app.get_latest_o7k_version(app.units[f"{charm}/0"]) == OpenStackRelease("xena")
    assert app.apt_source_codename == "xena"
    assert app.channel_o7k_release == "xena"
    assert app.is_subordinate is False


def test_ceph_mon_upgrade_plan_xena_to_yoga(model):
    """Test when ceph version changes between os releases."""
    target = OpenStackRelease("yoga")
    charm = "ceph-mon"
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = CephMon(
        name=charm,
        can_upgrade_to="quincy/stable",
        charm=charm,
        channel="pacific/stable",
        config={"source": {"value": "cloud:focal-xena"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"{charm}/0": Unit(
                name=f"{charm}/0",
                workload_version="16.2.0",
                machine=machines["0"],
            )
        },
        workload_version="16.2.0",
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
            description=f"Refresh '{app.name}' to the latest revision of 'pacific/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "pacific/stable"),
        ),
        PreUpgradeStep(
            description="Ensure that the 'require-osd-release' option matches the 'ceph-osd' "
            "version",
            parallel=False,
            coro=app_utils.set_require_osd_release_option("ceph-mon/0", model),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' from 'pacific/stable' "
            "to the new channel: 'quincy/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "quincy/stable"),
        ),
        UpgradeStep(
            description=f"Change charm config of '{app.name}' "
            f"'{app.origin_setting}' to 'cloud:focal-yoga'",
            parallel=False,
            coro=model.set_application_config(
                app.name, {f"{app.origin_setting}": "cloud:focal-yoga"}
            ),
        ),
        PostUpgradeStep(
            description=f"Wait for up to 2400s for model '{model.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_active_idle(2400, apps=None),
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


def test_ceph_mon_upgrade_plan_ussuri_to_victoria(model):
    """Test when ceph version remains the same between os releases."""
    target = OpenStackRelease("victoria")
    charm = "ceph-mon"
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = CephMon(
        name=charm,
        can_upgrade_to="quincy/stable",
        charm=charm,
        channel="octopus/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"{charm}/0": Unit(
                name=f"{charm}/0",
                workload_version="15.2.0",
                machine=machines["0"],
            )
        },
        workload_version="15.2.0",
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
            description=f"Refresh '{app.name}' to the latest revision of 'octopus/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "octopus/stable"),
        ),
        PreUpgradeStep(
            "Ensure that the 'require-osd-release' option matches the 'ceph-osd' version",
            parallel=False,
            coro=app_utils.set_require_osd_release_option("ceph-mon/0", model),
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
            coro=model.wait_for_active_idle(2400, apps=None),
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


def test_ovn_principal(model):
    """Test the correctness of instantiating OVNPrincipal."""
    charm = "ovn-central"
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = OVNPrincipal(
        name=charm,
        can_upgrade_to="22.06/stable",
        charm=charm,
        channel="22.03/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"{charm}/0": Unit(
                name=f"{charm}/0",
                workload_version="22.03",
                machine=machines["0"],
            )
        },
        workload_version="22.03",
    )
    assert app.channel == "22.03/stable"
    assert app.o7k_origin == "distro"
    assert app.apt_source_codename == "ussuri"
    assert app.channel_o7k_release == "yoga"
    assert app.o7k_release == "ussuri"
    assert app.is_subordinate is False


def test_ovn_workload_ver_lower_than_22_principal(model):
    """Test the OVNPrincipal with lower version than 22."""
    target = OpenStackRelease("victoria")
    charm = "ovn-central"
    exp_msg = (
        "OVN versions lower than 22.03 are not supported. It's necessary to upgrade "
        "OVN to 22.03 before upgrading the cloud. Follow the instructions at: "
        "https://docs.openstack.org/charm-guide/latest/project/procedures/"
        "ovn-upgrade-2203.html"
    )
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = OVNPrincipal(
        name=charm,
        can_upgrade_to="22.03/stable",
        charm=charm,
        channel="20.03/stable",
        config={"source": {"value": "distro"}, "enable-version-pinning": {"value": False}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"{charm}/0": Unit(
                name=f"{charm}/0",
                workload_version="20.03.2",
                machine=machines["0"],
            )
        },
        workload_version="20.03.2",
    )

    with pytest.raises(ApplicationError, match=exp_msg):
        app.generate_upgrade_plan(target, False)


def test_ovn_version_pinning_principal(model):
    """Test the OVNPrincipal when enable-version-pinning is set to True."""
    target = OpenStackRelease("victoria")
    charm = "ovn-dedicated-chassis"
    exp_msg = f"Cannot upgrade '{charm}'. 'enable-version-pinning' must be set to 'false'."
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = OVNPrincipal(
        name=charm,
        can_upgrade_to="22.03/stable",
        charm=charm,
        channel="22.03/stable",
        config={"source": {"value": "distro"}, "enable-version-pinning": {"value": True}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"{charm}/0": Unit(
                name=f"{charm}/0",
                workload_version="22.03.2",
                machine=machines["0"],
            )
        },
        workload_version="22.03.2",
    )

    with pytest.raises(ApplicationError, match=exp_msg):
        app.upgrade_plan_sanity_checks(target, list(app.units.values()))


@pytest.mark.parametrize("channel", ["55.7", "19.03"])
def test_ovn_no_compatible_o7k_release(channel, model):
    """Test the OVNPrincipal with not compatible os release."""
    charm = "ovn-central"
    machines = {"0": generate_cou_machine("0", "az-0")}
    exp_msg = (
        f"Channel: {channel} for charm '{charm}' on series 'focal' is not supported by COU. "
        "Please take a look at the documentation: "
        "https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html "
        "to see if you are using the right track."
    )

    with pytest.raises(ApplicationError, match=exp_msg):
        app = OVNPrincipal(
            name=charm,
            can_upgrade_to="quincy/stable",
            charm=charm,
            channel=channel,
            config={"source": {"value": "distro"}},
            machines=machines,
            model=model,
            origin="ch",
            series="focal",
            subordinate_to=[],
            units={
                f"{charm}/0": Unit(
                    name=f"{charm}/0",
                    workload_version="22.03",
                    machine=machines["0"],
                )
            },
            workload_version="22.03",
        )
        app._check_channel()


@pytest.mark.parametrize(
    "app, config",
    [
        (
            "ovn-dedicated-chassis",
            {"source": {"value": "distro"}, "enable-version-pinning": {"value": False}},
        ),
        # ovn-central doesn't have enable-version-pinning configuration
        ("ovn-central", {"source": {"value": "distro"}}),
    ],
)
def test_ovn_check_version_pinning_version_pinning_config_False(app, config, model):
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = OVNPrincipal(
        name=app,
        can_upgrade_to="",
        charm=app,
        channel="22.03/stable",
        config=config,
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"{app}/0": Unit(
                name=f"{app}/0",
                workload_version="22.03",
                machine=machines["0"],
            )
        },
        workload_version="22.03",
    )
    assert app._check_version_pinning() is None


def test_ovn_check_version_pinning_version_pinning_config_True(model):
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = OVNPrincipal(
        name="ovn-dedicated-chassis",
        can_upgrade_to="",
        charm="ovn-dedicated-chassis",
        channel="22.03/stable",
        config={"source": {"value": "distro"}, "enable-version-pinning": {"value": True}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "ovn-dedicated-chassis/0": Unit(
                name="ovn-dedicated-chassis/0",
                workload_version="22.03",
                machine=machines["0"],
            )
        },
        workload_version="22.03",
    )
    exp_msg = f"Cannot upgrade '{app.name}'. 'enable-version-pinning' must be set to 'false'."
    with pytest.raises(ApplicationError, match=exp_msg):
        app._check_version_pinning()


def test_ovn_principal_upgrade_plan(model):
    """Test generating plan for OVNPrincipal."""
    target = OpenStackRelease("victoria")
    charm = "ovn-dedicated-chassis"
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = OVNPrincipal(
        name=charm,
        can_upgrade_to="22.06/stable",
        charm=charm,
        channel="22.03/stable",
        config={"source": {"value": "distro"}, "enable-version-pinning": {"value": False}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"{charm}/0": Unit(
                name=f"{charm}/0",
                workload_version="22.03",
                machine=machines["0"],
            )
        },
        workload_version="22.03",
    )

    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to '{target}'"
    )

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
            description=f"Refresh '{app.name}' to the latest revision of '22.03/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "22.03/stable"),
        ),
        UpgradeStep(
            description=f"Change charm config of '{app.name}' "
            f"'{app.origin_setting}' to 'cloud:focal-{target}'",
            parallel=False,
            coro=model.set_application_config(
                app.name, {f"{app.origin_setting}": f"cloud:focal-{target}"}
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


def test_mysql_innodb_cluster_upgrade(model):
    """Test generating plan for MysqlInnodbCluster."""
    target = OpenStackRelease("victoria")
    charm = "mysql-innodb-cluster"
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = MysqlInnodbCluster(
        name=charm,
        can_upgrade_to="9.0",
        charm=charm,
        channel="8.0/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"{charm}/0": Unit(
                name=f"{charm}/0",
                workload_version="8.0",
                machine=machines["0"],
            )
        },
        workload_version="8.0",
    )

    expected_plan = ApplicationUpgradePlan(f"Upgrade plan for '{app.name}' to '{target}'")
    upgrade_packages = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    upgrade_packages.add_steps(
        UnitUpgradeStep(
            description=f"Upgrade software packages on unit '{unit.name}'",
            coro=app_utils.upgrade_packages(unit.name, model, ["mysql-server-core-8.0"]),
        )
        for unit in app.units.values()
    )

    upgrade_steps = [
        upgrade_packages,
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of '8.0/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "8.0/stable"),
        ),
        UpgradeStep(
            description=f"Change charm config of '{app.name}' "
            f"'{app.origin_setting}' to 'cloud:focal-{target}'",
            parallel=False,
            coro=model.set_application_config(
                app.name, {f"{app.origin_setting}": f"cloud:focal-{target}"}
            ),
        ),
        PostUpgradeStep(
            description=f"Wait for up to 2400s for app '{app.name}' to reach the idle state",
            parallel=False,
            coro=model.wait_for_active_idle(2400, apps=[app.name]),
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


@pytest.mark.parametrize("target", [OpenStackRelease("victoria")])
@patch("cou.apps.auxiliary.AuxiliaryApplication.pre_upgrade_steps")
def test_ceph_osd_pre_upgrade_steps(mock_pre_upgrade_steps, target, model):
    """Test Ceph-osd pre upgrade steps."""
    mock_pre_upgrade_steps.return_value = [MagicMock(spec_set=UpgradeStep)()]
    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
    app = CephOsd(
        name="ceph-osd",
        can_upgrade_to="octopus/stable",
        charm="ceph-osd",
        channel="octopus/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"ceph-osd/{i}": Unit(
                name=f"ceph-osd/{i}",
                workload_version="15.2.0",
                machine=machines[f"{i}"],
            )
            for i in range(3)
        },
        workload_version="15.2.0",
    )
    steps = app.pre_upgrade_steps(target, None)

    assert steps == [
        PreUpgradeStep(
            description="Verify that all 'nova-compute' units has been upgraded",
            coro=app._verify_nova_compute(target),
        ),
        *mock_pre_upgrade_steps.return_value,
    ]
    mock_pre_upgrade_steps.assert_called_once_with(target, None)


@pytest.mark.asyncio
async def test_ceph_osd_verify_nova_compute_no_app(model):
    """Test Ceph-osd verifying all nova computes."""
    target = OpenStackRelease("victoria")
    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
    app = CephOsd(
        name="ceph-osd",
        can_upgrade_to="octopus/stable",
        charm="ceph-osd",
        channel="octopus/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"ceph-osd/{i}": Unit(
                name=f"ceph-osd/{i}",
                workload_version="15.2.0",
                machine=machines[f"{i}"],
            )
            for i in range(3)
        },
        workload_version="15.2.0",
    )
    model.get_applications.return_value = {"ceph-osd": app}

    await app._verify_nova_compute(target)

    model.get_applications.assert_awaited_once_with()


@patch("cou.apps.base.OpenStackApplication.generate_upgrade_plan")
def test_auxiliary_upgrade_by_unit(mock_super, model):
    """Test generating plan with units doesn't create unit Upgrade steps."""
    target = OpenStackRelease("victoria")
    charm = "my-app"
    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
    app = AuxiliaryApplication(
        name=charm,
        can_upgrade_to="1.7/stable",
        charm=charm,
        channel="1.7/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"{charm}/0": Unit(
                name=f"{charm}/0",
                workload_version="1.7",
                machine=machines["0"],
            ),
            f"{charm}/1": Unit(
                name=f"{charm}/1",
                workload_version="1.7",
                machine=machines["1"],
            ),
            f"{charm}/2": Unit(
                name=f"{charm}/2",
                workload_version="1.7",
                machine=machines["2"],
            ),
        },
        workload_version="1.7",
    )

    app.generate_upgrade_plan(target, False, [app.units[f"{charm}/0"]])

    # Parent class was called with units=None even that units were passed to the
    # Auxiliary app, meaning that will create all-in-one upgrade strategy
    mock_super.assert_called_with(target, False, None)


@pytest.mark.asyncio
@patch("cou.utils.openstack.OpenStackCodenameLookup.find_compatible_versions")
async def test_ceph_osd_verify_nova_compute_pass(mock_lookup, model):
    """Test Ceph-osd verifying all nova computes."""
    target = OpenStackRelease("victoria")
    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
    mock_lookup.return_value = [target]
    nova_compute = MagicMock(spec_set=NovaCompute)()
    nova_compute.charm = "nova-compute"
    nova_compute.units = {"nova-compute/0": Unit("nova-compute/0", None, "22.0.0")}
    app = CephOsd(
        name="ceph-osd",
        can_upgrade_to="octopus/stable",
        charm="ceph-osd",
        channel="octopus/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"ceph-osd/{i}": Unit(
                name=f"ceph-osd/{i}",
                workload_version="17.0.1",
                machine=machines[f"{i}"],
            )
            for i in range(3)
        },
        workload_version="17.0.1",
    )
    model.get_applications.return_value = {"ceph-osd": app, "nova-compute": nova_compute}

    await app._verify_nova_compute(target)

    model.get_applications.assert_awaited_once_with()
    mock_lookup.assert_any_call("nova-compute", "22.0.0")


@pytest.mark.asyncio
@patch("cou.utils.openstack.OpenStackCodenameLookup.find_compatible_versions")
async def test_ceph_osd_verify_nova_compute_fail(mock_lookup, model):
    """Test Ceph-osd verifying all nova computes."""
    mock_lookup.return_value = [OpenStackRelease("ussuri")]
    target = OpenStackRelease("victoria")
    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
    nova_compute = MagicMock(spec_set=NovaCompute)()
    nova_compute.charm = "nova-compute"
    nova_compute.units = {"nova-compute/0": Unit("nova-compute/0", None, "22.0.0")}
    app = CephOsd(
        name="ceph-osd",
        can_upgrade_to="octopus/stable",
        charm="ceph-osd",
        channel="octopus/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"ceph-osd/{i}": Unit(
                name=f"ceph-osd/{i}",
                workload_version="17.0.1",
                machine=machines[f"{i}"],
            )
            for i in range(3)
        },
        workload_version="17.0.1",
    )
    model.get_applications.return_value = {"ceph-osd": app, "nova-compute": nova_compute}

    with pytest.raises(ApplicationError, match=f"Units 'nova-compute/0' did not reach {target}."):
        await app._verify_nova_compute(target)


def test_ceph_osd_upgrade_plan(model):
    """Testing generating ceph-osd upgrade plan."""
    exp_plan = dedent_plan(
        """\
    Upgrade plan for 'ceph-osd' to 'victoria'
        Verify that all 'nova-compute' units has been upgraded
        Upgrade software packages of 'ceph-osd' from the current APT repositories
            Ψ Upgrade software packages on unit 'ceph-osd/0'
            Ψ Upgrade software packages on unit 'ceph-osd/1'
            Ψ Upgrade software packages on unit 'ceph-osd/2'
        Refresh 'ceph-osd' to the latest revision of 'octopus/stable'
        Change charm config of 'ceph-osd' 'source' to 'cloud:focal-victoria'
        Wait for up to 300s for app 'ceph-osd' to reach the idle state
        Verify that the workload of 'ceph-osd' has been upgraded on units: ceph-osd/0, ceph-osd/1, ceph-osd/2
    """  # noqa: E501 line too long
    )
    target = OpenStackRelease("victoria")
    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
    ceph_osd = CephOsd(
        name="ceph-osd",
        can_upgrade_to="octopus/stable",
        charm="ceph-osd",
        channel="octopus/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"ceph-osd/{i}": Unit(
                name=f"ceph-osd/{i}",
                workload_version="15.2.0",
                machine=machines[f"{i}"],
            )
            for i in range(3)
        },
        workload_version="15.2.0",
    )

    plan = ceph_osd.generate_upgrade_plan(target, False)

    assert str(plan) == exp_plan


@pytest.mark.parametrize(
    "can_upgrade_to, compatible_o7k_releases, exp_result",
    [
        (
            "ch:amd64/focal/my-app-723",
            [OpenStackRelease("ussuri"), OpenStackRelease("victoria")],
            True,
        ),
        (
            "ch:amd64/focal/my-app-723",
            [OpenStackRelease("victoria")],
            True,
        ),
        # compatible_o7k_releases bigger than target
        (
            "ch:amd64/focal/my-app-723",
            [OpenStackRelease("wallaby"), OpenStackRelease("xena")],
            False,
        ),
        (
            "",
            [OpenStackRelease("ussuri"), OpenStackRelease("victoria")],
            False,
        ),
    ],
)
@patch("cou.apps.auxiliary.TRACK_TO_OPENSTACK_MAPPING")
def test_need_current_channel_refresh_auxiliary(
    mock_track_o7k_mapping, model, can_upgrade_to, compatible_o7k_releases, exp_result
):
    mock_track_o7k_mapping.__getitem__.return_value = compatible_o7k_releases
    target = OpenStackRelease("victoria")
    app_name = "app"
    app = AuxiliaryApplication(
        app_name, can_upgrade_to, app_name, "3.9/stable", {}, {}, model, "ch", "focal", [], {}, "1"
    )
    assert app._need_current_channel_refresh(target) is exp_result


@pytest.mark.parametrize(
    "channel, origin",
    [
        ("latest/stable", "ch"),
        ("latest", "cs"),
        ("octopus/stable", "ch"),
        ("pacific/stable", "ch"),
    ],
)
@patch("cou.apps.base.OpenStackApplication.o7k_release", new_callable=PropertyMock)
def test_expected_current_channel_auxiliary(mock_o7k_release, model, channel, origin):
    """Expected current channel is based on the OpenStack release of the workload version."""
    target = OpenStackRelease("wallaby")
    mock_o7k_release.return_value = OpenStackRelease("victoria")
    ceph_osd = CephOsd(
        name="ceph-osd",
        can_upgrade_to="octopus/stable",
        charm="ceph-osd",
        channel=channel,
        config={},
        machines={},
        model=model,
        origin=origin,
        series="focal",
        subordinate_to=[],
        units={},
        workload_version="15.2.0",
    )
    # expected_current_channel is indifferent if the charm needs crossgrade
    assert ceph_osd.expected_current_channel(target) == "octopus/stable"


def test_auxiliary_wrong_channel(model):
    """Test when an auxiliary charm is with a channel that doesn't match the workload version."""
    target = OpenStackRelease("victoria")
    charm = "ceph-mon"
    machines = {"0": generate_cou_machine("0", "az-0")}
    app = CephMon(
        name=charm,
        can_upgrade_to="",
        charm=charm,
        channel="quincy/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"{charm}/0": Unit(
                name=f"{charm}/0",
                workload_version="15.2.0",
                machine=machines["0"],
            )
        },
        workload_version="15.2.0",
    )

    # plan will raise exception because the channel is on quincy and was expected to be on octopus
    # or pacific. The user will need manual intervention

    exp_msg = (
        r"^The 'ceph-mon' application is using channel 'quincy/stable'\. Channels supported during"
        r" this transition: '(octopus/stable)', '(octopus/stable)'\. "
        r"Manual intervention is required\.$"
    )

    with pytest.raises(ApplicationError, match=exp_msg):
        app.generate_upgrade_plan(target, force=False)
