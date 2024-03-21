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
from cou.apps.channel_based import ChannelBasedApplication
from cou.steps import (
    ApplicationUpgradePlan,
    PostUpgradeStep,
    PreUpgradeStep,
    UnitUpgradeStep,
    UpgradeStep,
)
from cou.utils import app_utils
from cou.utils.openstack import OpenStackRelease


def test_application_versionless(status, config, model, apps_machines):
    app = ChannelBasedApplication(
        "glance-simplestreams-sync",
        status["glance_simplestreams_sync_focal_ussuri"],
        config["openstack_ussuri"],
        model,
        "glance-simplestreams-sync",
        apps_machines["glance-simplestreams-sync"],
    )
    assert app.current_os_release == "ussuri"
    assert app.is_versionless is True


def test_application_gnocchi_ussuri(status, config, model, apps_machines):
    app = ChannelBasedApplication(
        "gnocchi",
        status["gnocchi_focal_ussuri"],
        config["openstack_ussuri"],
        model,
        "gnocchi",
        apps_machines["gnocchi"],
    )
    assert app.current_os_release == "ussuri"
    assert app.is_versionless is False


def test_application_gnocchi_xena(status, config, model, apps_machines):
    # workload version is the same for xena and yoga, but current_os_release
    # is based on the channel.
    app = ChannelBasedApplication(
        "gnocchi",
        status["gnocchi_focal_xena"],
        config["openstack_xena"],
        model,
        "gnocchi",
        apps_machines["gnocchi"],
    )
    assert app.current_os_release == "xena"
    assert app.is_versionless is False


def test_application_designate_bind_ussuri(status, config, model, apps_machines):
    # workload version is the same from ussuri to yoga, but current_os_release
    # is based on the channel.
    app_config = config["openstack_ussuri"]
    app_config["action-managed-upgrade"] = {"value": False}
    app = ChannelBasedApplication(
        "designate-bind",
        status["designate_bind_focal_ussuri"],
        app_config,
        model,
        "designate-bind",
        apps_machines["designate-bind"],
    )
    assert app.current_os_release == "ussuri"
    assert app.is_versionless is False


def test_application_versionless_upgrade_plan_ussuri_to_victoria(
    status, config, model, apps_machines
):
    target = OpenStackRelease("victoria")
    app_config = config["openstack_ussuri"]
    # Does not have action-managed-upgrade
    app_config.pop("action-managed-upgrade")
    app = ChannelBasedApplication(
        "glance-simplestreams-sync",
        status["glance_simplestreams_sync_focal_ussuri"],
        app_config,
        model,
        "glance-simplestreams-sync",
        apps_machines["glance-simplestreams-sync"],
    )

    upgrade_plan = app.generate_upgrade_plan(target)

    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to '{target}'"
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
                app.name,
                {f"{app.origin_setting}": "cloud:focal-victoria"},
            ),
        ),
    ]

    expected_plan.add_steps(upgrade_steps)

    assert upgrade_plan == expected_plan


def test_application_gnocchi_upgrade_plan_ussuri_to_victoria(status, config, model, apps_machines):
    # Gnocchi from ussuri to victoria upgrade the workload version from 4.3.4 to 4.4.0.
    target = OpenStackRelease("victoria")
    app_config = config["openstack_ussuri"]
    app_config["action-managed-upgrade"] = {"value": False}
    app = ChannelBasedApplication(
        "gnocchi",
        status["gnocchi_focal_ussuri"],
        app_config,
        model,
        "gnocchi",
        apps_machines["gnocchi"],
    )

    upgrade_plan = app.generate_upgrade_plan(target)

    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to '{target}'"
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
            description=f"Verify that the workload of '{app.name}' has been upgraded",
            parallel=False,
            coro=app._check_upgrade(target),
        ),
    ]

    expected_plan.add_steps(upgrade_steps)

    assert upgrade_plan == expected_plan


def test_application_designate_bind_upgrade_plan_ussuri_to_victoria(
    status, config, model, apps_machines
):
    target = OpenStackRelease("victoria")
    app_config = config["openstack_ussuri"]
    app_config["action-managed-upgrade"] = {"value": False}
    app = ChannelBasedApplication(
        "designate-bind",
        status["designate_bind_focal_ussuri"],
        app_config,
        model,
        "designate-bind",
        apps_machines["designate-bind"],
    )

    upgrade_plan = app.generate_upgrade_plan(target)

    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to '{target}'"
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
            description=f"Verify that the workload of '{app.name}' has been upgraded",
            parallel=False,
            coro=app._check_upgrade(target),
        ),
    ]

    expected_plan.add_steps(upgrade_steps)

    assert upgrade_plan == expected_plan
