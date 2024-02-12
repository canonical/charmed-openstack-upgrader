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
import pytest

from cou.apps.auxiliary import (
    CephMonApplication,
    MysqlInnodbClusterApplication,
    OvnPrincipalApplication,
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
from cou.utils.juju_utils import COUUnit
from cou.utils.openstack import OpenStackRelease
from tests.unit.apps.utils import add_steps


def test_auxiliary_app(status, config, model, apps_machines):
    # version 3.8 on rabbitmq can be from ussuri to yoga. In that case it will be set as yoga.
    expected_units = [
        COUUnit(
            name="rabbitmq-server/0",
            os_version=OpenStackRelease("yoga"),
            workload_version="3.8",
            machine=apps_machines["rmq"]["0/lxd/19"],
        )
    ]

    app = RabbitMQServer(
        "rabbitmq-server",
        status["rabbitmq_server"],
        config["auxiliary_ussuri"],
        model,
        "rabbitmq-server",
        apps_machines["rmq"],
    )
    assert app.channel == "3.8/stable"
    assert app.is_valid_track(app.channel) is True
    assert app.os_origin == "distro"
    assert app.units == expected_units
    assert app.apt_source_codename == "ussuri"
    assert app.channel_codename == "yoga"
    assert app.is_subordinate is False
    assert app.current_os_release == "yoga"


def test_auxiliary_app_cs(status, config, model, apps_machines):
    expected_units = [
        COUUnit(
            name="rabbitmq-server/0",
            os_version=OpenStackRelease("yoga"),
            workload_version="3.8",
            machine=apps_machines["rmq"]["0/lxd/19"],
        )
    ]
    rmq_status = status["rabbitmq_server"]
    rmq_status.charm = "cs:amd64/focal/rabbitmq-server-638"
    rmq_status.charm_channel = "stable"
    app = RabbitMQServer(
        "rabbitmq-server",
        status["rabbitmq_server"],
        config["auxiliary_ussuri"],
        model,
        "rabbitmq-server",
        apps_machines["rmq"],
    )
    assert app.channel == "stable"
    assert app.is_valid_track(app.channel) is True
    assert app.os_origin == "distro"
    assert app.units == expected_units
    assert app.apt_source_codename == "ussuri"
    assert app.channel_codename == "ussuri"
    assert app.current_os_release == "yoga"


def test_auxiliary_upgrade_plan_ussuri_to_victoria_change_channel(
    status, config, model, apps_machines
):
    target = OpenStackRelease("victoria")
    app = RabbitMQServer(
        "rabbitmq-server",
        status["rabbitmq_server"],
        config["auxiliary_ussuri"],
        model,
        "rabbitmq-server",
        apps_machines["rmq"],
    )

    upgrade_plan = app.generate_upgrade_plan(target)

    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}"
    )
    expected_upgrade_package_step = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    for unit in app.status.units.keys():
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
            description=f"Check if the workload of '{app.name}' has been upgraded",
            parallel=False,
            coro=app._check_upgrade(target),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan


def test_auxiliary_upgrade_plan_ussuri_to_victoria(status, config, model, apps_machines):
    target = OpenStackRelease("victoria")
    rmq_status = status["rabbitmq_server"]
    # rabbitmq already on channel 3.9 on ussuri
    rmq_status.charm_channel = "3.9/stable"
    app = RabbitMQServer(
        "rabbitmq-server",
        rmq_status,
        config["auxiliary_ussuri"],
        model,
        "rabbitmq-server",
        apps_machines["rmq"],
    )

    upgrade_plan = app.generate_upgrade_plan(target)

    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}"
    )
    upgrade_packages = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    for unit in app.units:
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
            description=f"Check if the workload of '{app.name}' has been upgraded",
            parallel=False,
            coro=app._check_upgrade(target),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan


def test_auxiliary_upgrade_plan_ussuri_to_victoria_ch_migration(
    status, config, model, apps_machines
):
    target = OpenStackRelease("victoria")
    rmq_status = status["rabbitmq_server"]
    rmq_status.charm = "cs:amd64/focal/rabbitmq-server-638"
    rmq_status.charm_channel = "stable"
    app = RabbitMQServer(
        "rabbitmq-server",
        status["rabbitmq_server"],
        config["auxiliary_ussuri"],
        model,
        "rabbitmq-server",
        apps_machines["rmq"],
    )
    upgrade_plan = app.generate_upgrade_plan(target)
    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}",
    )
    upgrade_packages = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    for unit in app.units:
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
            description=f"Check if the workload of '{app.name}' has been upgraded",
            parallel=False,
            coro=app._check_upgrade(target),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan


def test_auxiliary_upgrade_plan_unknown_track(status, config, model, apps_machines):
    rmq_status = status["rabbitmq_server"]
    # 2.0 is an unknown track
    rmq_status.charm_channel = "2.0/stable"
    with pytest.raises(ApplicationError):
        RabbitMQServer(
            "rabbitmq-server",
            status["rabbitmq_server"],
            config["auxiliary_ussuri"],
            model,
            "rabbitmq-server",
            apps_machines["rmq"],
        )


def test_auxiliary_app_unknown_version_raise_ApplicationError(
    status, config, model, apps_machines
):
    with pytest.raises(ApplicationError):
        RabbitMQServer(
            "rabbitmq-server",
            status["unknown_rabbitmq_server"],
            config["auxiliary_ussuri"],
            model,
            "rabbitmq-server",
            apps_machines["rmq"],
        )


def test_auxiliary_raise_error_unknown_series(status, config, model, apps_machines):
    app_status = status["rabbitmq_server"]
    app_status.series = "foo"
    with pytest.raises(ApplicationError):
        RabbitMQServer(
            "rabbitmq-server",
            app_status,
            config["auxiliary_ussuri"],
            model,
            "rabbitmq-server",
            apps_machines["rmq"],
        )


def test_auxiliary_raise_error_os_not_on_lookup(status, config, model, mocker, apps_machines):
    # change OpenStack release to a version that is not on openstack_to_track_mapping.csv
    mocker.patch(
        "cou.apps.core.OpenStackApplication.current_os_release",
        new_callable=mocker.PropertyMock,
        return_value=OpenStackRelease("diablo"),
    )
    app_status = status["rabbitmq_server"]
    app = RabbitMQServer(
        "rabbitmq-server",
        app_status,
        config["auxiliary_ussuri"],
        model,
        "rabbitmq-server",
        apps_machines["rmq"],
    )
    with pytest.raises(ApplicationError):
        app.possible_current_channels


def test_auxiliary_raise_halt_upgrade(status, config, model, apps_machines):
    target = OpenStackRelease("victoria")
    # source is already configured to wallaby, so the plan halt with target victoria
    app = RabbitMQServer(
        "rabbitmq-server",
        status["rabbitmq_server"],
        config["auxiliary_wallaby"],
        model,
        "rabbitmq-server",
        apps_machines["rmq"],
    )
    with pytest.raises(HaltUpgradePlanGeneration):
        app.generate_upgrade_plan(target)


def test_auxiliary_no_suitable_channel(status, config, model, apps_machines):
    # OPENSTACK_TO_TRACK_MAPPING can't find a track for rabbitmq, focal, zed.
    target = OpenStackRelease("zed")
    app_status = status["rabbitmq_server"]
    app_status.series = "focal"
    app = RabbitMQServer(
        "rabbitmq-server",
        app_status,
        config["auxiliary_wallaby"],
        model,
        "rabbitmq-server",
        apps_machines["rmq"],
    )
    with pytest.raises(ApplicationError):
        app.target_channel(target)


def test_ceph_mon_app(status, config, model, apps_machines):
    """Test the correctness of instantiating CephMonApplication."""
    app = CephMonApplication(
        "ceph-mon",
        status["ceph_mon_pacific"],
        config["auxiliary_xena"],
        model,
        "ceph-mon",
        apps_machines["ceph-mon"],
    )
    assert app.channel == "pacific/stable"
    assert app.os_origin == "cloud:focal-xena"
    assert app.units == [
        COUUnit(
            name="ceph-mon/0",
            os_version=OpenStackRelease("xena"),
            workload_version="16.2.0",
            machine=apps_machines["ceph-mon"]["6"],
        )
    ]
    assert app.apt_source_codename == "xena"
    assert app.channel_codename == "xena"
    assert app.is_subordinate is False


def test_ceph_mon_upgrade_plan_xena_to_yoga(status, config, model, apps_machines):
    """Test when ceph version changes between os releases."""
    target = OpenStackRelease("yoga")
    app = CephMonApplication(
        "ceph-mon",
        status["ceph_mon_pacific"],
        config["auxiliary_xena"],
        model,
        "ceph-mon",
        apps_machines["ceph-mon"],
    )

    upgrade_plan = app.generate_upgrade_plan(target)

    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}"
    )
    upgrade_packages = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    for unit in app.units:
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
            description="Ensure require-osd-release option matches with ceph-osd version",
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
            description=f"Check if the workload of '{app.name}' has been upgraded",
            parallel=False,
            coro=app._check_upgrade(target),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan


def test_ceph_mon_upgrade_plan_ussuri_to_victoria(
    status,
    config,
    model,
    apps_machines,
):
    """Test when ceph version remains the same between os releases."""
    target = OpenStackRelease("victoria")
    app = CephMonApplication(
        "ceph-mon",
        status["ceph_mon_octopus"],
        config["auxiliary_ussuri"],
        model,
        "ceph-mon",
        apps_machines["ceph-mon"],
    )
    upgrade_plan = app.generate_upgrade_plan(target)

    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}"
    )
    upgrade_packages = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    for unit in app.units:
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
            description="Ensure require-osd-release option matches with ceph-osd version",
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
            description=f"Check if the workload of '{app.name}' has been upgraded",
            parallel=False,
            coro=app._check_upgrade(target),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan


def test_ovn_principal(status, config, model, apps_machines):
    app = OvnPrincipalApplication(
        "ovn-central",
        status["ovn_central_22"],
        config["auxiliary_ussuri"],
        model,
        "ovn-central",
        apps_machines["ovn-central"],
    )
    assert app.channel == "22.03/stable"
    assert app.os_origin == "distro"
    assert app.apt_source_codename == "ussuri"
    assert app.channel_codename == "yoga"
    assert app.current_os_release == "yoga"
    assert app.is_subordinate is False


def test_ovn_workload_ver_lower_than_22_principal(status, config, model, apps_machines):
    target = OpenStackRelease("victoria")

    exp_error_msg_ovn_upgrade = (
        "OVN versions lower than 22.03 are not supported. It's necessary to upgrade "
        "OVN to 22.03 before upgrading the cloud. Follow the instructions at: "
        "https://docs.openstack.org/charm-guide/latest/project/procedures/"
        "ovn-upgrade-2203.html"
    )

    app_ovn_central = OvnPrincipalApplication(
        "ovn-central",
        status["ovn_central_20"],
        config["auxiliary_ussuri"],
        model,
        "ovn-central",
        apps_machines["ovn-central"],
    )

    with pytest.raises(ApplicationError, match=exp_error_msg_ovn_upgrade):
        app_ovn_central.generate_upgrade_plan(target)


@pytest.mark.parametrize("channel", ["55.7", "19.03"])
def test_ovn_no_compatible_os_release(status, config, model, channel, apps_machines):
    ovn_central_status = status["ovn_central_22"]
    ovn_central_status.charm_channel = channel
    with pytest.raises(ApplicationError):
        OvnPrincipalApplication(
            "ovn-central",
            ovn_central_status,
            config["auxiliary_ussuri"],
            model,
            "ovn-central",
            apps_machines["ovn-central"],
        )


def test_ovn_principal_upgrade_plan(status, config, model, apps_machines):
    target = OpenStackRelease("victoria")
    app = OvnPrincipalApplication(
        "ovn-central",
        status["ovn_central_22"],
        config["auxiliary_ussuri"],
        model,
        "ovn-central",
        apps_machines["ovn-central"],
    )

    upgrade_plan = app.generate_upgrade_plan(target)

    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}"
    )

    upgrade_packages = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    for unit in app.units:
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
                f"'{app.origin_setting}' to 'cloud:focal-victoria'"
            ),
            parallel=False,
            coro=model.set_application_config(
                app.name, {f"{app.origin_setting}": "cloud:focal-victoria"}
            ),
        ),
        PostUpgradeStep(
            description=f"Wait 300s for app {app.name} to reach the idle state.",
            parallel=False,
            coro=model.wait_for_active_idle(300, apps=[app.name]),
        ),
        PostUpgradeStep(
            description=f"Check if the workload of '{app.name}' has been upgraded",
            parallel=False,
            coro=app._check_upgrade(target),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan


def test_mysql_innodb_cluster_upgrade(status, config, model, apps_machines):
    target = OpenStackRelease("victoria")
    # source is already configured to wallaby, so the plan halt with target victoria
    app = MysqlInnodbClusterApplication(
        "mysql-innodb-cluster",
        status["mysql_innodb_cluster"],
        config["auxiliary_ussuri"],
        model,
        "mysql-innodb-cluster",
        apps_machines["mysql-innodb-cluster"],
    )
    upgrade_plan = app.generate_upgrade_plan(target)
    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}"
    )
    upgrade_packages = PreUpgradeStep(
        description=f"Upgrade software packages of '{app.name}' from the current APT repositories",
        parallel=True,
    )
    for unit in app.units:
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
                f"'{app.origin_setting}' to 'cloud:focal-victoria'"
            ),
            parallel=False,
            coro=model.set_application_config(
                app.name, {f"{app.origin_setting}": "cloud:focal-victoria"}
            ),
        ),
        PostUpgradeStep(
            description=f"Wait 1800s for app {app.name} to reach the idle state.",
            parallel=False,
            coro=model.wait_for_active_idle(1800, apps=[app.name]),
        ),
        PostUpgradeStep(
            description=f"Check if the workload of '{app.name}' has been upgraded",
            parallel=False,
            coro=app._check_upgrade(target),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan
