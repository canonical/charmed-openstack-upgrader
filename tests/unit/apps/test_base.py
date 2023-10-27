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

from cou.apps.base import OpenStackApplication
from cou.steps import UpgradeStep
from cou.utils import app_utils
from cou.utils.openstack import OpenStackRelease
from tests.unit.apps.utils import add_steps


def test_application_versionless(status, config, model):
    app = OpenStackApplication(
        "glance-simplestreams-sync",
        status["glance_simplestreams_sync_ussuri"],
        config["openstack_ussuri"],
        model,
        "glance-simplestreams-sync",
    )
    assert app.is_versionless is True
    assert app.is_os_channel_based is True


def test_application_versionless_upgrade_plan_ussuri_to_victoria(status, config, model):
    target = OpenStackRelease("victoria")
    app_config = config["openstack_ussuri"]
    # Does not have action-managed-upgrade
    app_config.pop("action-managed-upgrade")
    app = OpenStackApplication(
        "glance-simplestreams-sync",
        status["glance_simplestreams_sync_ussuri"],
        app_config,
        model,
        "glance-simplestreams-sync",
    )

    upgrade_plan = app.generate_upgrade_plan(target)

    expected_plan = UpgradeStep(
        description=f"Upgrade plan for '{app.name}' to {target}",
        parallel=False,
    )

    upgrade_steps = [
        UpgradeStep(
            description=(
                f"Upgrade software packages of '{app.name}' from the current APT repositories"
            ),
            parallel=False,
            coro=app_utils.upgrade_packages(app.status.units.keys(), model, None),
        ),
        UpgradeStep(
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
