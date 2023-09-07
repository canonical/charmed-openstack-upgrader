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

from cou.apps.auxiliary import OpenStackAuxiliaryApplication
from cou.exceptions import ApplicationError, HaltUpgradePlanGeneration
from cou.utils.openstack import OpenStackRelease
from tests.unit.apps.utils import assert_plan_description


def test_auxiliary_app(status, config):
    # version 3.8 on rabbitmq can be from ussuri to yoga. In that case it will be set as yoga.
    target = "victoria"
    expected_units = {"rabbitmq-server/0": {"os_version": "yoga", "workload_version": "3.8"}}
    app = OpenStackAuxiliaryApplication(
        "rabbitmq-server",
        status["rabbitmq_server"],
        config["auxiliary_ussuri"],
        "my_model",
        "rabbitmq-server",
        "rabbitmq-server",
    )
    assert app.channel == "3.8/stable"
    assert app.os_origin == "distro"
    assert app.units == expected_units
    assert app.os_origin_from_apt_sources(OpenStackRelease(target)) == "ussuri"


def test_auxiliary_upgrade_plan_ussuri_to_victoria(status, config):
    target = "victoria"
    app = OpenStackAuxiliaryApplication(
        "rabbitmq-server",
        status["rabbitmq_server"],
        config["auxiliary_ussuri"],
        "my_model",
        "rabbitmq-server",
        "rabbitmq-server",
    )

    plan = app.generate_upgrade_plan(target)

    steps_description = [
        f"Upgrade software packages of '{app.name}' from the current APT repositories",
        f"Refresh '{app.name}' to the latest revision of '3.8/stable'",
        f"Change charm config of '{app.name}' 'source' to 'cloud:focal-victoria'",
        f"Check if the workload of '{app.name}' has been upgraded",
    ]

    assert_plan_description(plan, steps_description)


def test_auxiliary_upgrade_plan_ussuri_to_victoria_ch_migration(status, config):
    target = "victoria"
    rmq_status = status["rabbitmq_server"]
    rmq_status.charm = "cs:amd64/focal/rabbitmq-server-638"
    app = OpenStackAuxiliaryApplication(
        "rabbitmq-server",
        status["rabbitmq_server"],
        config["auxiliary_ussuri"],
        "my_model",
        "rabbitmq-server",
        "rabbitmq-server",
    )
    plan = app.generate_upgrade_plan(target)

    steps_description = [
        f"Upgrade software packages of '{app.name}' from the current APT repositories",
        f"Migration of '{app.name}' from charmstore to charmhub",
        f"Change charm config of '{app.name}' 'source' to 'cloud:focal-victoria'",
        f"Check if the workload of '{app.name}' has been upgraded",
    ]

    assert_plan_description(plan, steps_description)


def test_auxiliary_upgrade_plan_channel_different_expected(status, config, mocker):
    mock_logger = mocker.patch("cou.apps.auxiliary.logger")
    target = "victoria"
    rmq_status = status["rabbitmq_server"]
    rmq_status.charm_channel = "3.6/stable"
    app = OpenStackAuxiliaryApplication(
        "rabbitmq-server",
        status["rabbitmq_server"],
        config["auxiliary_ussuri"],
        "my_model",
        "rabbitmq-server",
        "rabbitmq-server",
    )
    plan = app.generate_upgrade_plan(target)

    steps_description = [
        f"Upgrade software packages of '{app.name}' from the current APT repositories",
        f"Upgrade '{app.name}' to the new channel: '3.8/stable'",
        f"Change charm config of '{app.name}' 'source' to 'cloud:focal-victoria'",
        f"Check if the workload of '{app.name}' has been upgraded",
    ]

    assert_plan_description(plan, steps_description)
    mock_logger.warning.assert_called_once_with(
        "'%s' has the channel set to: %s which is different from the expected channel: %s",
        app.name,
        app.channel,
        app.expected_current_channel,
    )


def test_auxiliary_app_unknown_version_raise_ApplicationError(status, config):
    with pytest.raises(ApplicationError):
        OpenStackAuxiliaryApplication(
            "rabbitmq-server",
            status["unknown_rabbitmq_server"],
            config["auxiliary_ussuri"],
            "my_model",
            "rabbitmq-server",
            "rabbitmq-server",
        )


def test_auxiliary_raise_error_unknown_track(status, config):
    target = OpenStackRelease("victoria")
    app_status = status["rabbitmq_server"]
    app_status.series = "foo"
    app = OpenStackAuxiliaryApplication(
        "rabbitmq-server",
        app_status,
        config["auxiliary_ussuri"],
        "my_model",
        "rabbitmq-server",
        "rabbitmq-server",
    )
    with pytest.raises(ApplicationError):
        app.expected_current_channel

    with pytest.raises(ApplicationError):
        app.target_channel(target)


def test_auxiliary_raise_halt_upgrade(status, config):
    target = "victoria"
    # source is already configured to wallaby, so the plan halt with target victoria
    app = OpenStackAuxiliaryApplication(
        "rabbitmq-server",
        status["rabbitmq_server"],
        config["auxiliary_wallaby"],
        "my_model",
        "rabbitmq-server",
        "rabbitmq-server",
    )
    with pytest.raises(HaltUpgradePlanGeneration):
        app.generate_upgrade_plan(target)
