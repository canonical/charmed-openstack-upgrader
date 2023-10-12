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

from cou.apps.app import ApplicationUnit
from cou.apps.auxiliary import RabbitMQServer
from cou.exceptions import ApplicationError, HaltUpgradePlanGeneration
from cou.steps import UpgradeStep
from cou.utils import app_utils
from cou.utils.openstack import OpenStackRelease
from tests.unit.apps.utils import add_steps


def test_auxiliary_app(status, config, model):
    # version 3.8 on rabbitmq can be from ussuri to yoga. In that case it will be set as yoga.
    expected_units = [
        ApplicationUnit(
            name="rabbitmq-server/0",
            os_version=OpenStackRelease("yoga"),
            workload_version="3.8",
            machine="0/lxd/19",
        )
    ]

    app = RabbitMQServer(
        "rabbitmq-server",
        status["rabbitmq_server"],
        config["auxiliary_ussuri"],
        model,
        "rabbitmq-server",
    )
    assert app.channel == "3.8/stable"
    assert app.os_origin == "distro"
    assert app.units == expected_units
    assert app.apt_source_codename == "ussuri"
    assert app.channel_codename == "yoga"


def test_auxiliary_upgrade_plan_ussuri_to_victoria_change_channel(status, config, model):
    target = "victoria"
    app = RabbitMQServer(
        "rabbitmq-server",
        status["rabbitmq_server"],
        config["auxiliary_ussuri"],
        model,
        "rabbitmq-server",
    )

    upgrade_plan = app.generate_upgrade_plan(target)

    expected_plan = UpgradeStep(
        description=f"Upgrade plan for '{app.name}' to {target}",
        parallel=False,
        function=None,
    )
    upgrade_steps = [
        UpgradeStep(
            description=(
                f"Upgrade software packages of '{app.name}' from the current APT repositories"
            ),
            parallel=False,
            function=app_utils.upgrade_packages,
            units=app.status.units.keys(),
            model=model,
        ),
        UpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of '3.8/stable'",
            parallel=False,
            function=model.upgrade_charm,
            application_name=app.name,
            channel="3.8/stable",
            switch=None,
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: '3.9/stable'",
            parallel=False,
            function=model.upgrade_charm,
            application_name=app.name,
            channel="3.9/stable",
        ),
        UpgradeStep(
            description=(
                f"Change charm config of '{app.name}' "
                f"'{app.origin_setting}' to 'cloud:focal-victoria'"
            ),
            parallel=False,
            function=model.set_application_config,
            name=app.name,
            configuration={f"{app.origin_setting}": "cloud:focal-victoria"},
        ),
        UpgradeStep(
            description=f"Wait (300 s) for model {model.name} to reach the idle state.",
            parallel=False,
            function=model.wait_for_idle,
            timeout=300,
            apps=None,
        ),
        UpgradeStep(
            description=f"Check if the workload of '{app.name}' has been upgraded",
            parallel=False,
            function=app._check_upgrade,
            target=OpenStackRelease(target),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan


def test_auxiliary_upgrade_plan_ussuri_to_victoria(status, config, model):
    target = "victoria"
    rmq_status = status["rabbitmq_server"]
    # rabbitmq already on channel 3.9 on ussuri
    rmq_status.charm_channel = "3.9/stable"
    app = RabbitMQServer(
        "rabbitmq-server",
        rmq_status,
        config["auxiliary_ussuri"],
        model,
        "rabbitmq-server",
    )

    upgrade_plan = app.generate_upgrade_plan(target)

    expected_plan = UpgradeStep(
        description=f"Upgrade plan for '{app.name}' to {target}",
        parallel=False,
        function=None,
    )
    upgrade_steps = [
        UpgradeStep(
            description=(
                f"Upgrade software packages of '{app.name}' from the current APT repositories"
            ),
            parallel=False,
            function=app_utils.upgrade_packages,
            units=app.status.units.keys(),
            model=model,
        ),
        UpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of '3.9/stable'",
            parallel=False,
            function=model.upgrade_charm,
            application_name=app.name,
            channel="3.9/stable",
            switch=None,
        ),
        UpgradeStep(
            description=(
                f"Change charm config of '{app.name}' "
                f"'{app.origin_setting}' to 'cloud:focal-victoria'"
            ),
            parallel=False,
            function=model.set_application_config,
            name=app.name,
            configuration={f"{app.origin_setting}": "cloud:focal-victoria"},
        ),
        UpgradeStep(
            description=f"Wait (300 s) for model {model.name} to reach the idle state.",
            parallel=False,
            function=model.wait_for_idle,
            timeout=300,
            apps=None,
        ),
        UpgradeStep(
            description=f"Check if the workload of '{app.name}' has been upgraded",
            parallel=False,
            function=app._check_upgrade,
            target=OpenStackRelease(target),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan


def test_auxiliary_upgrade_plan_ussuri_to_victoria_ch_migration(status, config, model):
    target = "victoria"
    rmq_status = status["rabbitmq_server"]
    rmq_status.charm = "cs:amd64/focal/rabbitmq-server-638"
    rmq_status.charm_channel = "stable"
    app = RabbitMQServer(
        "rabbitmq-server",
        status["rabbitmq_server"],
        config["auxiliary_ussuri"],
        model,
        "rabbitmq-server",
    )
    upgrade_plan = app.generate_upgrade_plan(target)
    expected_plan = UpgradeStep(
        description=f"Upgrade plan for '{app.name}' to {target}",
        parallel=False,
        function=None,
    )
    upgrade_steps = [
        UpgradeStep(
            description=(
                f"Upgrade software packages of '{app.name}' from the current APT repositories"
            ),
            parallel=False,
            function=app_utils.upgrade_packages,
            units=app.status.units.keys(),
            model=model,
        ),
        UpgradeStep(
            description=f"Migration of '{app.name}' from charmstore to charmhub",
            parallel=False,
            function=model.upgrade_charm,
            application_name=app.name,
            channel="3.9/stable",
            switch="ch:rabbitmq-server",
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: '3.9/stable'",
            parallel=False,
            function=model.upgrade_charm,
            application_name=app.name,
            channel="3.9/stable",
        ),
        UpgradeStep(
            description=(
                f"Change charm config of '{app.name}' "
                f"'{app.origin_setting}' to 'cloud:focal-victoria'"
            ),
            parallel=False,
            function=model.set_application_config,
            name=app.name,
            configuration={f"{app.origin_setting}": "cloud:focal-victoria"},
        ),
        UpgradeStep(
            description=f"Wait (300 s) for model {model.name} to reach the idle state.",
            parallel=False,
            function=model.wait_for_idle,
            timeout=300,
            apps=None,
        ),
        UpgradeStep(
            description=f"Check if the workload of '{app.name}' has been upgraded",
            parallel=False,
            function=app._check_upgrade,
            target=OpenStackRelease(target),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan


def test_auxiliary_upgrade_plan_unknown_track(status, config, model):
    target = "victoria"
    rmq_status = status["rabbitmq_server"]
    # 2.0 is an unknown track
    rmq_status.charm_channel = "2.0/stable"
    app = RabbitMQServer(
        "rabbitmq-server",
        status["rabbitmq_server"],
        config["auxiliary_ussuri"],
        model,
        "rabbitmq-server",
    )
    with pytest.raises(ApplicationError):
        app.generate_upgrade_plan(target)


def test_auxiliary_app_unknown_version_raise_ApplicationError(status, config, model):
    with pytest.raises(ApplicationError):
        RabbitMQServer(
            "rabbitmq-server",
            status["unknown_rabbitmq_server"],
            config["auxiliary_ussuri"],
            model,
            "rabbitmq-server",
        )


def test_auxiliary_raise_error_unknown_track(status, config, model):
    target = OpenStackRelease("victoria")
    app_status = status["rabbitmq_server"]
    app_status.series = "foo"
    app = RabbitMQServer(
        "rabbitmq-server",
        app_status,
        config["auxiliary_ussuri"],
        model,
        "rabbitmq-server",
    )
    with pytest.raises(ApplicationError):
        app.possible_current_channels

    with pytest.raises(ApplicationError):
        app.target_channel(target)


def test_auxiliary_raise_halt_upgrade(status, config, model):
    target = "victoria"
    # source is already configured to wallaby, so the plan halt with target victoria
    app = RabbitMQServer(
        "rabbitmq-server",
        status["rabbitmq_server"],
        config["auxiliary_wallaby"],
        model,
        "rabbitmq-server",
    )
    with pytest.raises(HaltUpgradePlanGeneration):
        app.generate_upgrade_plan(target)
