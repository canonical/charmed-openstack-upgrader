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
from unittest.mock import MagicMock, patch

import pytest

from cou.apps.auxiliary import (
    AuxiliaryApplication,
    CephMon,
    MysqlInnodbCluster,
    OvnPrincipal,
    RabbitMQServer,
)
from cou.exceptions import ApplicationError, HaltUpgradePlanGeneration
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


def test_auxiliary_app(model):
    """Test auxiliary application.

    The version 3.8 on rabbitmq can be from ussuri to yoga. In that case it will be
    set as yoga.
    """
    machines = {"0": MagicMock(spec_set=COUMachine)}
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
            "rabbitmq-server/0": COUUnit(
                name="rabbitmq-server/0",
                workload_version="3.8",
                machine=machines["0"],
            )
        },
        workload_version="3.8",
    )
    assert app.channel == "3.8/stable"
    assert app.is_valid_track(app.channel) is True
    assert app.os_origin == "distro"
    assert app.apt_source_codename == "ussuri"
    assert app.channel_codename == "yoga"
    assert app.is_subordinate is False
    assert app.current_os_release == "yoga"


def test_auxiliary_app_cs(model):
    """Test auxiliary application from charm store."""
    machines = {"0": MagicMock(spec_set=COUMachine)}
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
            "rabbitmq-server/0": COUUnit(
                name="rabbitmq-server/0",
                workload_version="3.8",
                machine=machines["0"],
            )
        },
        workload_version="3.8",
    )

    assert app.channel == "stable"
    assert app.is_valid_track(app.channel) is True
    assert app.os_origin == "distro"
    assert app.apt_source_codename == "ussuri"
    assert app.channel_codename == "ussuri"
    assert app.current_os_release == "yoga"


def test_auxiliary_upgrade_plan_ussuri_to_victoria_change_channel(model):
    """Test auxiliary upgrade plan from Ussuri to Victoria with change of channel."""
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = RabbitMQServer(
        name="rabbitmq-server",
        can_upgrade_to="3.9/stable",
        charm="rabbitmq-server",
        channel="3.8/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "rabbitmq-server/0": COUUnit(
                name="rabbitmq-server/0",
                workload_version="3.8",
                machine=machines["0"],
            )
        },
        workload_version="3.8",
    )

    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}"
    )
    expected_upgrade_package_step = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    for unit in app.units.keys():
        expected_upgrade_package_step.add_step(
            UnitUpgradeStep(
                description=f"Upgrade software packages on unit {unit}",
                parallel=False,
                coro=app_utils.upgrade_packages(unit, model, None),
            )
        )

    upgrade_steps = [
        expected_upgrade_package_step,
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of '3.8/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "3.8/stable", switch=None),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: '3.9/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "3.9/stable"),
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
            description=f"Wait 1800s for model {model.name} to reach the idle state.",
            parallel=False,
            coro=model.wait_for_active_idle(1800, apps=None),
        ),
        PostUpgradeStep(
            description=(
                f"Check if the workload of '{app.name}' has been upgraded on units: "
                f"{', '.join([unit for unit in app.units.keys()])}"
            ),
            parallel=False,
            coro=app._verify_workload_upgrade(target, app.units.values()),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)
    assert_steps(upgrade_plan, expected_plan)


def test_auxiliary_upgrade_plan_ussuri_to_victoria(model):
    """Test auxiliary upgrade plan from Ussuri to Victoria."""
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = RabbitMQServer(
        name="rabbitmq-server",
        can_upgrade_to="3.9/stable",
        charm="rabbitmq-server",
        channel="3.9/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "rabbitmq-server/0": COUUnit(
                name="rabbitmq-server/0",
                workload_version="3.9",
                machine=machines["0"],
            )
        },
        workload_version="3.9",
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
            description=f"Refresh '{app.name}' to the latest revision of '3.9/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "3.9/stable", switch=None),
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
            description=f"Wait 1800s for model {model.name} to reach the idle state.",
            parallel=False,
            coro=model.wait_for_active_idle(1800, apps=None),
        ),
        PostUpgradeStep(
            description=(
                f"Check if the workload of '{app.name}' has been upgraded on units: "
                f"{', '.join([unit for unit in app.units.keys()])}"
            ),
            parallel=False,
            coro=app._verify_workload_upgrade(target, app.units.values()),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)

    assert_steps(upgrade_plan, expected_plan)


def test_auxiliary_upgrade_plan_ussuri_to_victoria_ch_migration(model):
    """Test auxiliary upgrade plan from Ussuri to Victoria with migration to charmhub."""
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = RabbitMQServer(
        name="rabbitmq-server",
        can_upgrade_to="3.9/stable",
        charm="rabbitmq-server",
        channel="stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="cs",
        series="focal",
        subordinate_to=[],
        units={
            "rabbitmq-server/0": COUUnit(
                name="rabbitmq-server/0",
                workload_version="3.8",
                machine=machines["0"],
            )
        },
        workload_version="3.8",
    )

    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}",
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
            coro=model.upgrade_charm(app.name, "3.9/stable", switch="ch:rabbitmq-server"),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: '3.9/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "3.9/stable"),
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
            description=f"Wait 1800s for model {model.name} to reach the idle state.",
            parallel=False,
            coro=model.wait_for_active_idle(1800, apps=None),
        ),
        PostUpgradeStep(
            description=(
                f"Check if the workload of '{app.name}' has been upgraded on units: "
                f"{', '.join([unit for unit in app.units.keys()])}"
            ),
            parallel=False,
            coro=app._verify_workload_upgrade(target, app.units.values()),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)

    assert_steps(upgrade_plan, expected_plan)


def test_auxiliary_upgrade_plan_unknown_track(model):
    """Test auxiliary upgrade plan with unknown track."""
    channel = "2.0/stable"
    exp_msg = (
        f"Channel: {channel} for charm 'rabbitmq-server' on series 'focal' is currently "
        "not supported in this tool. Please take a look at the documentation: "
        "https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html "
        "to see if you are using the right track."
    )
    machines = {"0": MagicMock(spec_set=COUMachine)}
    with pytest.raises(ApplicationError, match=exp_msg):
        RabbitMQServer(
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
                "rabbitmq-server/0": COUUnit(
                    name="rabbitmq-server/0",
                    workload_version="3.8",
                    machine=machines["0"],
                )
            },
            workload_version="3.8",
        )


def test_auxiliary_app_unknown_version_raise_ApplicationError(model):
    """Test auxiliary upgrade plan with unknown version."""
    version = "80.5"
    charm = "rabbitmq-server"
    exp_msg = f"'{charm}' with workload version {version} has no compatible OpenStack release."

    machines = {"0": MagicMock(spec_set=COUMachine)}
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
        units={
            f"{charm}/0": COUUnit(
                name=f"{charm}/0",
                workload_version=version,
                machine=machines["0"],
            )
        },
        workload_version=version,
    )
    with pytest.raises(ApplicationError, match=exp_msg):
        app.unit_max_os_version(app.units[f"{charm}/0"])


def test_auxiliary_raise_error_unknown_series(model):
    """Test auxiliary upgrade plan with unknown series."""
    series = "foo"
    channel = "3.8/stable"
    exp_msg = (
        f"Channel: {channel} for charm 'rabbitmq-server' on series '{series}' is currently "
        "not supported in this tool. Please take a look at the documentation: "
        "https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html "
        "to see if you are using the right track."
    )
    machines = {"0": MagicMock(spec_set=COUMachine)}
    with pytest.raises(ApplicationError, match=exp_msg):
        RabbitMQServer(
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
                "rabbitmq-server/0": COUUnit(
                    name="rabbitmq-server/0",
                    workload_version="3.8",
                    machine=machines["0"],
                )
            },
            workload_version="3.8",
        )


@patch("cou.apps.core.OpenStackApplication.current_os_release")
def test_auxiliary_raise_error_os_not_on_lookup(current_os_release, model):
    """Test auxiliary upgrade plan with os release not in lookup table.

    Using OpenStack release version that is not on openstack_to_track_mapping.csv table.
    """
    current_os_release.return_value = OpenStackRelease("diablo")

    machines = {"0": MagicMock(spec_set=COUMachine)}
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
            "rabbitmq-server/0": COUUnit(
                name="rabbitmq-server/0",
                workload_version="3.8",
                machine=machines["0"],
            )
        },
        workload_version="3.8",
    )

    with pytest.raises(ApplicationError):
        app.possible_current_channels


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
    machines = {"0": MagicMock(spec_set=COUMachine)}
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
            f"{charm}/0": COUUnit(
                name=f"{charm}/0",
                workload_version="3.8",
                machine=machines["0"],
            )
        },
        workload_version="3.8",
    )

    with pytest.raises(HaltUpgradePlanGeneration, match=exp_msg):
        app.generate_upgrade_plan(target, False)


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
    machines = {"0": MagicMock(spec_set=COUMachine)}
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
            f"{charm}/0": COUUnit(
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
    machines = {"0": MagicMock(spec_set=COUMachine)}
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
            f"{charm}/0": COUUnit(
                name=f"{charm}/0",
                workload_version="16.2.0",
                machine=machines["0"],
            )
        },
        workload_version="16.2.0",
    )

    assert app.channel == "pacific/stable"
    assert app.os_origin == "cloud:focal-xena"
    assert app.unit_max_os_version(app.units[f"{charm}/0"]) == OpenStackRelease("xena")
    assert app.apt_source_codename == "xena"
    assert app.channel_codename == "xena"
    assert app.is_subordinate is False


def test_ceph_mon_upgrade_plan_xena_to_yoga(model):
    """Test when ceph version changes between os releases."""
    target = OpenStackRelease("yoga")
    charm = "ceph-mon"
    machines = {"0": MagicMock(spec_set=COUMachine)}
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
            f"{charm}/0": COUUnit(
                name=f"{charm}/0",
                workload_version="16.2.0",
                machine=machines["0"],
            )
        },
        workload_version="16.2.0",
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
            description=f"Refresh '{app.name}' to the latest revision of 'pacific/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "pacific/stable", switch=None),
        ),
        PreUpgradeStep(
            description="Ensure the 'require-osd-release' option matches the 'ceph-osd' version",
            parallel=False,
            coro=app_utils.set_require_osd_release_option("ceph-mon/0", model),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: 'quincy/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "quincy/stable"),
        ),
        UpgradeStep(
            description=(
                f"Change charm config of '{app.name}' "
                f"'{app.origin_setting}' to 'cloud:focal-yoga'"
            ),
            parallel=False,
            coro=model.set_application_config(
                app.name, {f"{app.origin_setting}": "cloud:focal-yoga"}
            ),
        ),
        PostUpgradeStep(
            description=f"Wait 1800s for model {model.name} to reach the idle state.",
            parallel=False,
            coro=model.wait_for_active_idle(1800, apps=None),
        ),
        PostUpgradeStep(
            description=(
                f"Check if the workload of '{app.name}' has been upgraded on units: "
                f"{', '.join([unit for unit in app.units.keys()])}"
            ),
            parallel=False,
            coro=app._verify_workload_upgrade(target, app.units.values()),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)

    assert_steps(upgrade_plan, expected_plan)


def test_ceph_mon_upgrade_plan_ussuri_to_victoria(model):
    """Test when ceph version remains the same between os releases."""
    target = OpenStackRelease("victoria")
    charm = "ceph-mon"
    machines = {"0": MagicMock(spec_set=COUMachine)}
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
            f"{charm}/0": COUUnit(
                name=f"{charm}/0",
                workload_version="15.2.0",
                machine=machines["0"],
            )
        },
        workload_version="15.2.0",
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
            description=f"Refresh '{app.name}' to the latest revision of 'octopus/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "octopus/stable", switch=None),
        ),
        PreUpgradeStep(
            description="Ensure the 'require-osd-release' option matches the 'ceph-osd' version",
            parallel=False,
            coro=app_utils.set_require_osd_release_option("ceph-mon/0", model),
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
            description=(
                f"Check if the workload of '{app.name}' has been upgraded on units: "
                f"{', '.join([unit for unit in app.units.keys()])}"
            ),
            parallel=False,
            coro=app._verify_workload_upgrade(target, app.units.values()),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)

    assert_steps(upgrade_plan, expected_plan)


def test_ovn_principal(model):
    """Test the correctness of instantiating OvnPrincipal."""
    charm = "ovn-central"
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = OvnPrincipal(
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
            f"{charm}/0": COUUnit(
                name=f"{charm}/0",
                workload_version="22.03",
                machine=machines["0"],
            )
        },
        workload_version="22.03",
    )
    assert app.channel == "22.03/stable"
    assert app.os_origin == "distro"
    assert app.apt_source_codename == "ussuri"
    assert app.channel_codename == "yoga"
    assert app.current_os_release == "yoga"
    assert app.is_subordinate is False


def test_ovn_workload_ver_lower_than_22_principal(model):
    """Test the OvnPrincipal with lower version than 22."""
    target = OpenStackRelease("victoria")
    charm = "ovn-central"
    exp_msg = (
        "OVN versions lower than 22.03 are not supported. It's necessary to upgrade "
        "OVN to 22.03 before upgrading the cloud. Follow the instructions at: "
        "https://docs.openstack.org/charm-guide/latest/project/procedures/"
        "ovn-upgrade-2203.html"
    )
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = OvnPrincipal(
        name=charm,
        can_upgrade_to="22.03/stable",
        charm=charm,
        channel="20.03/stable",
        config={"source": {"value": "distro"}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"{charm}/0": COUUnit(
                name=f"{charm}/0",
                workload_version="20.03.2",
                machine=machines["0"],
            )
        },
        workload_version="20.03.2",
    )

    with pytest.raises(ApplicationError, match=exp_msg):
        app.generate_upgrade_plan(target, False)


@pytest.mark.parametrize("channel", ["55.7", "19.03"])
def test_ovn_no_compatible_os_release(channel, model):
    """Test the OvnPrincipal with not compatible os release."""
    charm = "ovn-central"
    machines = {"0": MagicMock(spec_set=COUMachine)}
    exp_msg = (
        f"Channel: {channel} for charm '{charm}' on series 'focal' is currently "
        "not supported in this tool. Please take a look at the documentation: "
        "https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html "
        "to see if you are using the right track."
    )

    with pytest.raises(ApplicationError, match=exp_msg):
        OvnPrincipal(
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
                f"{charm}/0": COUUnit(
                    name=f"{charm}/0",
                    workload_version="22.03",
                    machine=machines["0"],
                )
            },
            workload_version="22.03",
        )


def test_ovn_principal_upgrade_plan(model):
    """Test generating plan for OvnPrincipal."""
    target = OpenStackRelease("victoria")
    charm = "ovn-central"
    machines = {"0": MagicMock(spec_set=COUMachine)}
    app = OvnPrincipal(
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
            f"{charm}/0": COUUnit(
                name=f"{charm}/0",
                workload_version="22.03",
                machine=machines["0"],
            )
        },
        workload_version="22.03",
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
            description=f"Refresh '{app.name}' to the latest revision of '22.03/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "22.03/stable", switch=None),
        ),
        UpgradeStep(
            description=(
                f"Change charm config of '{app.name}' "
                f"'{app.origin_setting}' to 'cloud:focal-{target}'"
            ),
            parallel=False,
            coro=model.set_application_config(
                app.name, {f"{app.origin_setting}": f"cloud:focal-{target}"}
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
            coro=app._verify_workload_upgrade(target, app.units.values()),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)

    assert_steps(upgrade_plan, expected_plan)


def test_mysql_innodb_cluster_upgrade(model):
    """Test generating plan for MysqlInnodbCluster."""
    target = OpenStackRelease("victoria")
    charm = "mysql-innodb-cluster"
    machines = {"0": MagicMock(spec_set=COUMachine)}
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
            f"{charm}/0": COUUnit(
                name=f"{charm}/0",
                workload_version="8.0",
                machine=machines["0"],
            )
        },
        workload_version="8.0",
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
                coro=app_utils.upgrade_packages(unit.name, model, ["mysql-server-core-8.0"]),
            )
        )

    upgrade_steps = [
        upgrade_packages,
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of '8.0/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "8.0/stable", switch=None),
        ),
        UpgradeStep(
            description=(
                f"Change charm config of '{app.name}' "
                f"'{app.origin_setting}' to 'cloud:focal-{target}'"
            ),
            parallel=False,
            coro=model.set_application_config(
                app.name, {f"{app.origin_setting}": f"cloud:focal-{target}"}
            ),
        ),
        PostUpgradeStep(
            description=f"Wait 1800s for app {app.name} to reach the idle state.",
            parallel=False,
            coro=model.wait_for_active_idle(1800, apps=[app.name]),
        ),
        PostUpgradeStep(
            description=(
                f"Check if the workload of '{app.name}' has been upgraded on units: "
                f"{', '.join([unit for unit in app.units.keys()])}"
            ),
            parallel=False,
            coro=app._verify_workload_upgrade(target, app.units.values()),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)

    assert_steps(upgrade_plan, expected_plan)


@patch("cou.apps.base.OpenStackApplication.generate_upgrade_plan")
def test_auxiliary_upgrade_by_unit(mock_super, model):
    """Test generating plan with units doesn't create unit Upgrade steps."""
    target = OpenStackRelease("victoria")
    charm = "vault"
    machines = {
        "0": MagicMock(spec_set=COUMachine),
        "1": MagicMock(spec_set=COUMachine),
        "2": MagicMock(spec_set=COUMachine),
    }
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
            f"{charm}/0": COUUnit(
                name=f"{charm}/0",
                workload_version="1.7",
                machine=machines["0"],
            ),
            f"{charm}/1": COUUnit(
                name=f"{charm}/1",
                workload_version="1.7",
                machine=machines["1"],
            ),
            f"{charm}/2": COUUnit(
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
