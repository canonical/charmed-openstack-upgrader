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

from cou.apps.channel_based import OpenStackChannelBasedApplication
from cou.steps import (
    ApplicationUpgradePlan,
    PostUpgradeStep,
    PreUpgradeStep,
    UpgradeStep,
)
from cou.utils import app_utils
from cou.utils.openstack import OpenStackRelease
from tests.unit.apps.utils import add_steps


def test_application_versionless(status, config, model):
    app = OpenStackChannelBasedApplication(
        "glance-simplestreams-sync",
        status["glance_simplestreams_sync_ussuri"],
        config["openstack_ussuri"],
        model,
        "glance-simplestreams-sync",
    )
    assert app.current_os_release == "ussuri"
    assert app.is_versionless is True


def test_application_gnocchi_ussuri(status, config, model):
    app = OpenStackChannelBasedApplication(
        "gnocchi",
        status["gnocchi_ussuri"],
        config["openstack_ussuri"],
        model,
        "gnocchi",
    )
    assert app.current_os_release == "ussuri"
    assert app.is_versionless is False


def test_application_gnocchi_xena(status, config, model):
    # workload version is the same for xena and yoga, but current_os_release
    # is based on the channel.
    app = OpenStackChannelBasedApplication(
        "gnocchi",
        status["gnocchi_xena"],
        config["openstack_xena"],
        model,
        "gnocchi",
    )
    assert app.current_os_release == "xena"
    assert app.is_versionless is False


def test_application_designate_bind_ussuri(status, config, model):
    # workload version is the same from ussuri to yoga, but current_os_release
    # is based on the channel.
    app_config = config["openstack_ussuri"]
    app_config["action-managed-upgrade"] = {"value": False}
    app = OpenStackChannelBasedApplication(
        "designate-bind",
        status["designate_bind_ussuri"],
        app_config,
        model,
        "designate-bind",
    )
    assert app.current_os_release == "ussuri"
    assert app.is_versionless is False


def test_application_versionless_upgrade_plan_ussuri_to_victoria(status, config, model):
    target = OpenStackRelease("victoria")
    app_config = config["openstack_ussuri"]
    # Does not have action-managed-upgrade
    app_config.pop("action-managed-upgrade")
    app = OpenStackChannelBasedApplication(
        "glance-simplestreams-sync",
        status["glance_simplestreams_sync_ussuri"],
        app_config,
        model,
        "glance-simplestreams-sync",
    )

    upgrade_plan = app.generate_upgrade_plan(target)

    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}"
    )

    upgrade_steps = [
        PreUpgradeStep(
            description=(
                f"Upgrade software packages of '{app.name}' from the current APT repositories"
            ),
            parallel=False,
            coro=app_utils.upgrade_packages(app.status.units.keys(), model, None),
        ),
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

    assert upgrade_plan == expected_plan


def test_application_gnocchi_upgrade_plan_ussuri_to_victoria(status, config, model):
    # Gnocchi from ussuri to victoria upgrade the workload version from 4.3.4 to 4.4.0.
    target = OpenStackRelease("victoria")
    app_config = config["openstack_ussuri"]
    app_config["action-managed-upgrade"] = {"value": False}
    app = OpenStackChannelBasedApplication(
        "gnocchi",
        status["gnocchi_ussuri"],
        app_config,
        model,
        "gnocchi",
    )

    upgrade_plan = app.generate_upgrade_plan(target)

    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}"
    )

    upgrade_steps = [
        PreUpgradeStep(
            description=(
                f"Upgrade software packages of '{app.name}' from the current APT repositories"
            ),
            parallel=False,
            coro=app_utils.upgrade_packages(app.status.units.keys(), model, None),
        ),
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
            coro=model.wait_for_idle(300, [app.name]),
        ),
        PostUpgradeStep(
            description=f"Check if the workload of '{app.name}' has been upgraded",
            parallel=False,
            coro=app._check_upgrade(target),
        ),
    ]

    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan


def test_application_designate_bind_upgrade_plan_ussuri_to_victoria(status, config, model):
    target = OpenStackRelease("victoria")
    app_config = config["openstack_ussuri"]
    app_config["action-managed-upgrade"] = {"value": False}
    app = OpenStackChannelBasedApplication(
        "designate-bind",
        status["designate_bind_ussuri"],
        app_config,
        model,
        "designate-bind",
    )

    upgrade_plan = app.generate_upgrade_plan(target)

    expected_plan = ApplicationUpgradePlan(
        description=f"Upgrade plan for '{app.name}' to {target}"
    )

    upgrade_steps = [
        PreUpgradeStep(
            description=(
                f"Upgrade software packages of '{app.name}' from the current APT repositories"
            ),
            parallel=False,
            coro=app_utils.upgrade_packages(app.status.units.keys(), model, None),
        ),
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
            coro=model.wait_for_idle(300, [app.name]),
        ),
        PostUpgradeStep(
            description=f"Check if the workload of '{app.name}' has been upgraded",
            parallel=False,
            coro=app._check_upgrade(target),
        ),
    ]

    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan
