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

from unittest.mock import call

import pytest

from cou.apps import app as app_module
from cou.apps.app import OpenStackApplication
from cou.exceptions import (
    ApplicationError,
    HaltUpgradePlanGeneration,
    MismatchedOpenStackVersions,
    PackageUpgradeError,
)
from cou.utils.openstack import OpenStackRelease


def test_application_eq(status, config):
    """Name of the app is used as comparison between Applications objects."""
    status_keystone_1 = status["keystone_ussuri"]
    config_keystone_1 = config["openstack_ussuri"]
    status_keystone_2 = status["keystone_wallaby"]
    config_keystone_2 = config["openstack_wallaby"]
    keystone_1 = OpenStackApplication(
        "keystone", status_keystone_1, config_keystone_1, "my_model", "keystone"
    )
    keystone_2 = OpenStackApplication(
        "keystone", status_keystone_2, config_keystone_2, "my_model", "keystone"
    )
    keystone_3 = OpenStackApplication(
        "keystone_foo", status_keystone_1, config_keystone_1, "my_model", "keystone"
    )

    # keystone_1 is equal to keystone_2 because they have the same name
    # even if they have different status and config.
    assert keystone_1 == keystone_2
    # keystone_1 is different then keystone_3 even if they have same status and config.
    assert keystone_1 != keystone_3


def assert_application(
    app,
    exp_name,
    exp_series,
    exp_status,
    exp_config,
    exp_model,
    exp_charm,
    exp_charm_origin,
    exp_os_origin,
    exp_units,
    exp_channel,
    exp_current_os_release,
    exp_current_channel,
    exp_target_channel,
    exp_new_origin,
    target,
):
    target_version = OpenStackRelease(target)
    assert app.name == exp_name
    assert app.series == exp_series
    assert app.status == exp_status
    assert app.config == exp_config
    assert app.model_name == exp_model
    assert app.charm == exp_charm
    assert app.charm_origin == exp_charm_origin
    assert app.os_origin == exp_os_origin
    assert app.units == exp_units
    assert app.channel == exp_channel
    assert app.current_os_release == exp_current_os_release
    assert app.expected_current_channel == exp_current_channel
    assert app.target_channel(target_version) == exp_target_channel
    assert app.new_origin(target_version) == exp_new_origin


def test_application_ussuri(status, config, units):
    target = "victoria"
    app_status = status["keystone_ussuri"]
    app_config = config["openstack_ussuri"]
    exp_charm_origin = "ch"
    exp_os_origin = "distro"
    exp_units = units["units_ussuri"]
    exp_channel = app_status.charm_channel
    exp_series = app_status.series
    exp_current_os_release = "ussuri"
    exp_current_channel = "ussuri/stable"
    exp_target_channel = f"{target}/stable"
    exp_new_origin = f"cloud:{exp_series}-{target}"

    app = OpenStackApplication("my_keystone", app_status, app_config, "my_model", "keystone")
    assert_application(
        app,
        "my_keystone",
        exp_series,
        app_status,
        app_config,
        "my_model",
        "keystone",
        exp_charm_origin,
        exp_os_origin,
        exp_units,
        exp_channel,
        exp_current_os_release,
        exp_current_channel,
        exp_target_channel,
        exp_new_origin,
        target,
    )


def test_application_different_wl(status, config, mocker):
    """Different OpenStack Version on units if workload version is different."""
    app_status = status["keystone_ussuri_victoria"]
    app_config = config["openstack_ussuri"]

    mock_logger = mocker.patch("cou.apps.app.logger")

    app = OpenStackApplication("my_keystone", app_status, app_config, "my_model", "keystone")
    with pytest.raises(MismatchedOpenStackVersions):
        app.current_os_release
    mock_logger.error.assert_called_once()


def test_application_cs(status, config, units):
    """Test when application is from charm store."""
    target = "victoria"
    app_status = status["keystone_ussuri_cs"]
    app_config = config["openstack_ussuri"]
    exp_os_origin = "distro"
    exp_units = units["units_ussuri"]
    exp_channel = app_status.charm_channel
    exp_charm_origin = "cs"
    exp_series = app_status.series
    exp_current_os_release = "ussuri"
    exp_current_channel = "ussuri/stable"
    exp_target_channel = f"{target}/stable"
    exp_new_origin = f"cloud:{exp_series}-{target}"

    app = OpenStackApplication("my_keystone", app_status, app_config, "my_model", "keystone")
    assert_application(
        app,
        "my_keystone",
        exp_series,
        app_status,
        app_config,
        "my_model",
        "keystone",
        exp_charm_origin,
        exp_os_origin,
        exp_units,
        exp_channel,
        exp_current_os_release,
        exp_current_channel,
        exp_target_channel,
        exp_new_origin,
        target,
    )


def test_application_wallaby(status, config, units):
    target = "xena"
    exp_units = units["units_wallaby"]
    exp_charm_origin = "ch"
    app_config = config["openstack_wallaby"]
    app_status = status["keystone_wallaby"]
    exp_os_origin = "cloud:focal-wallaby"
    exp_channel = app_status.charm_channel
    exp_series = app_status.series
    exp_current_os_release = "wallaby"
    exp_current_channel = "wallaby/stable"
    exp_target_channel = f"{target}/stable"
    exp_new_origin = f"cloud:{exp_series}-{target}"

    app = OpenStackApplication("my_keystone", app_status, app_config, "my_model", "keystone")
    assert_application(
        app,
        "my_keystone",
        exp_series,
        app_status,
        app_config,
        "my_model",
        "keystone",
        exp_charm_origin,
        exp_os_origin,
        exp_units,
        exp_channel,
        exp_current_os_release,
        exp_current_channel,
        exp_target_channel,
        exp_new_origin,
        target,
    )


def test_special_app_more_than_one_compatible_os_release(status, config):
    # version 3.8 on rabbitmq can be from ussuri to yoga. In that case it will be set as yoga.
    expected_units = {"rabbitmq-server/0": {"os_version": "yoga", "workload_version": "3.8"}}
    app = OpenStackApplication(
        "rabbitmq-server",
        status["rabbitmq_server"],
        config["openstack_ussuri"],
        "my_model",
        "rabbitmq-server",
    )
    assert app.units == expected_units


def test_special_app_unknown_version_raise_ApplicationError(status, config, mocker):
    mock_logger = mocker.patch("cou.apps.app.logger")
    with pytest.raises(ApplicationError):
        OpenStackApplication(
            "rabbitmq-server",
            status["unknown_rabbitmq_server"],
            config["openstack_ussuri"],
            "my_model",
            "rabbitmq-server",
        )
    mock_logger.error.assert_called_once()


def test_application_no_openstack_origin(status):
    """Test when application doesn't have openstack-origin or source config."""
    app_status = status["vault"]
    app_config = {}
    app = OpenStackApplication("vault", app_status, app_config, "my_model", "vault")
    assert app._get_os_origin() == ""


@pytest.mark.asyncio
async def test_application_check_upgrade(status, config, mocker):
    target = "victoria"
    mock_logger = mocker.patch("cou.apps.app.logger")
    app_status = status["keystone_ussuri"]
    app_config = config["openstack_ussuri"]

    # workload version changed from ussuri to victoria
    mock_status = mocker.MagicMock()
    mock_status.applications = {"my_keystone": status["keystone_victoria"]}

    mocker.patch.object(app_module, "async_get_status", return_value=mock_status)
    app = OpenStackApplication("my_keystone", app_status, app_config, "my_model", "keystone")
    await app._check_upgrade(target)
    mock_logger.error.assert_not_called()


@pytest.mark.asyncio
async def test_application_check_upgrade_fail(status, config, mocker):
    target = "victoria"
    mock_logger = mocker.patch("cou.apps.app.logger")
    app_status = status["keystone_ussuri"]
    app_config = config["openstack_ussuri"]

    # workload version didn't change from ussuri to victoria
    mock_status = mocker.MagicMock()
    mock_status.applications = {"my_keystone": status["keystone_ussuri"]}

    mocker.patch.object(app_module, "async_get_status", return_value=mock_status)
    app = OpenStackApplication("my_keystone", app_status, app_config, "my_model", "keystone")
    with pytest.raises(ApplicationError):
        await app._check_upgrade(target)
    mock_logger.error.assert_called_once_with(
        "Units '%s' failed to upgrade to %s",
        "keystone/0, keystone/1, keystone/2",
        "victoria",
    )


@pytest.mark.asyncio
async def test_application_upgrade_packages(status, config, mocker):
    app_status = status["keystone_ussuri"]
    app_config = config["openstack_ussuri"]
    mocker.patch("cou.apps.app.logger")

    mock_status = mocker.MagicMock()
    mock_status.applications = {"my_keystone": status["keystone_ussuri"]}

    mocker.patch.object(app_module, "async_get_status", return_value=mock_status)
    mock_run_package_upgrade_command = mocker.patch.object(
        OpenStackApplication, "_run_package_upgrade_command"
    )
    app = OpenStackApplication("my_keystone", app_status, app_config, "my_model", "keystone")
    await app._upgrade_packages()

    dpkg_opts = "-o Dpkg::Options::=--force-confnew -o Dpkg::Options::=--force-confdef"
    expected_calls = [
        call(unit="keystone/0", command="sudo apt update"),
        call(
            unit="keystone/0",
            command=f"sudo apt full-upgrade {dpkg_opts} -y",
        ),
        call(unit="keystone/0", command="sudo apt autoremove"),
        call(unit="keystone/1", command="sudo apt update"),
        call(
            unit="keystone/1",
            command=f"sudo apt full-upgrade {dpkg_opts} -y",
        ),
        call(unit="keystone/1", command="sudo apt autoremove"),
        call(unit="keystone/2", command="sudo apt update"),
        call(
            unit="keystone/2",
            command=f"sudo apt full-upgrade {dpkg_opts} -y",
        ),
        call(unit="keystone/2", command="sudo apt autoremove"),
    ]
    mock_run_package_upgrade_command.assert_has_calls(expected_calls, any_order=True)


@pytest.mark.asyncio
async def test_run_package_upgrade_command(mocker):
    mock_logger = mocker.patch("cou.apps.app.logger")
    mock_status = mocker.MagicMock()
    mock_config = mocker.MagicMock()

    app = OpenStackApplication("my_keystone", mock_status, mock_config, "my_model", "keystone")
    success_result = {"Code": "0", "Stdout": "Success"}
    mock_async_run_on_unit = mocker.patch.object(
        app_module, "async_run_on_unit", return_value=success_result
    )
    await app._run_package_upgrade_command(unit="keystone/0", command="sudo apt update")
    mock_logger.info.assert_called_once_with("Running '%s' on %s", "sudo apt update", "keystone/0")
    mock_async_run_on_unit.assert_called_once_with(
        unit_name="keystone/0", command="sudo apt update", model_name="my_model"
    )
    mock_logger.debug.assert_called_once_with("Success")


@pytest.mark.asyncio
async def test_run_package_upgrade_command_failed(mocker):
    mock_logger = mocker.patch("cou.apps.app.logger")
    mock_status = mocker.MagicMock()
    mock_config = mocker.MagicMock()

    app = OpenStackApplication("my_keystone", mock_status, mock_config, "my_model", "keystone")
    failed_result = {"Code": "non-zero", "Stderr": "unexpected error"}
    mock_async_run_on_unit = mocker.patch.object(
        app_module, "async_run_on_unit", return_value=failed_result
    )

    with pytest.raises(PackageUpgradeError):
        await app._run_package_upgrade_command(unit="keystone/0", command="sudo apt update")

    mock_logger.info.assert_called_once_with("Running '%s' on %s", "sudo apt update", "keystone/0")
    mock_async_run_on_unit.assert_called_once_with(
        unit_name="keystone/0", command="sudo apt update", model_name="my_model"
    )
    mock_logger.error.assert_called_once_with(
        "Error upgrading package on %s: %s", "keystone/0", "unexpected error"
    )


def assert_plan_description(upgrade_plan, steps_description):
    assert len(upgrade_plan.sub_steps) == len(steps_description)
    sub_steps_check = zip(upgrade_plan.sub_steps, steps_description)
    for sub_step, description in sub_steps_check:
        assert sub_step.description == description


def test_upgrade_plan_ussuri_to_victoria(status, config):
    target = "victoria"
    app_status = status["keystone_ussuri"]
    app_config = config["openstack_ussuri"]
    app = OpenStackApplication("my_keystone", app_status, app_config, "my_model", "keystone")
    upgrade_plan = app.generate_upgrade_plan(target)
    steps_description = [
        "Upgrade software packages of 'my_keystone' to the latest in 'ussuri' release",
        "Refresh 'my_keystone' to the latest revision of 'ussuri/stable'",
        "Change charm config of 'my_keystone' 'action-managed-upgrade' to False.",
        "Upgrade 'my_keystone' to the new channel: 'victoria/stable'",
        "Change charm config of 'my_keystone' 'openstack-origin' to 'cloud:focal-victoria'",
        "Check if the workload of 'my_keystone' has been upgraded",
    ]
    assert upgrade_plan.description == "Upgrade plan for 'my_keystone' from: ussuri to victoria"
    assert_plan_description(upgrade_plan, steps_description)


def test_upgrade_plan_ussuri_to_victoria_ch_migration(status, config):
    target = "victoria"
    app_status = status["keystone_ussuri_cs"]
    app_config = config["openstack_ussuri"]
    app = OpenStackApplication("my_keystone", app_status, app_config, "my_model", "keystone")
    upgrade_plan = app.generate_upgrade_plan(target)
    steps_description = [
        "Upgrade software packages of 'my_keystone' to the latest in 'ussuri' release",
        "Migration of 'my_keystone' from charmstore to charmhub",
        "Change charm config of 'my_keystone' 'action-managed-upgrade' to False.",
        "Upgrade 'my_keystone' to the new channel: 'victoria/stable'",
        "Change charm config of 'my_keystone' 'openstack-origin' to 'cloud:focal-victoria'",
        "Check if the workload of 'my_keystone' has been upgraded",
    ]
    assert upgrade_plan.description == "Upgrade plan for 'my_keystone' from: ussuri to victoria"
    assert_plan_description(upgrade_plan, steps_description)


def test_upgrade_plan_change_current_channel(mocker, status, config):
    target = "victoria"
    mock_logger = mocker.patch("cou.apps.app.logger")
    app_status = status["keystone_ussuri"]
    app_config = config["openstack_ussuri"]
    # channel it's neither the expected as current channel as ussuri/stable or
    # target_channel victoria/stable
    app_status.charm_channel = "foo/stable"
    app = OpenStackApplication("my_keystone", app_status, app_config, "my_model", "keystone")
    upgrade_plan = app.generate_upgrade_plan(target)

    steps_description = [
        "Upgrade software packages of 'my_keystone' to the latest in 'ussuri' release",
        "Changing 'my_keystone' channel from: 'foo/stable' to: 'ussuri/stable'",
        "Change charm config of 'my_keystone' 'action-managed-upgrade' to False.",
        "Upgrade 'my_keystone' to the new channel: 'victoria/stable'",
        "Change charm config of 'my_keystone' 'openstack-origin' to 'cloud:focal-victoria'",
        "Check if the workload of 'my_keystone' has been upgraded",
    ]

    mock_logger.debug.assert_called_once_with(
        "The current channel does not exist or is unexpectedly formatted"
    )

    assert_plan_description(upgrade_plan, steps_description)


def test_upgrade_plan_channel_on_next_os_release(status, config, mocker):
    target = "victoria"
    mock_logger = mocker.patch("cou.apps.app.logger")
    app_status = status["keystone_ussuri"]
    app_config = config["openstack_ussuri"]
    # channel it's already on next OpenStack release
    app_status.charm_channel = "victoria/stable"
    app = OpenStackApplication("my_keystone", app_status, app_config, "my_model", "keystone")
    upgrade_plan = app.generate_upgrade_plan(target)

    # no sub-step for refresh current channel or next channel
    steps_description = [
        "Upgrade software packages of 'my_keystone' to the latest in 'ussuri' release",
        "Change charm config of 'my_keystone' 'action-managed-upgrade' to False.",
        "Change charm config of 'my_keystone' 'openstack-origin' to 'cloud:focal-victoria'",
        "Check if the workload of 'my_keystone' has been upgraded",
    ]

    assert_plan_description(upgrade_plan, steps_description)
    mock_logger.info.assert_called_once_with(
        (
            "Skipping charm refresh for %s, its channel is already set "
            "to %s.release than target %s"
        ),
        app.name,
        app.channel,
        target,
    )


def test_upgrade_plan_origin_already_on_next_openstack_release(status, config, mocker):
    target = "victoria"
    mock_logger = mocker.patch("cou.apps.app.logger")
    app_status = status["keystone_ussuri"]
    app_config = config["openstack_ussuri"]
    # openstack-origin already configured for next OpenStack release
    app_config["openstack-origin"]["value"] = "cloud:focal-victoria"
    app = OpenStackApplication("my_keystone", app_status, app_config, "my_model", "keystone")
    upgrade_plan = app.generate_upgrade_plan(target)
    steps_description = [
        "Upgrade software packages of 'my_keystone' to the latest in 'ussuri' release",
        "Refresh 'my_keystone' to the latest revision of 'ussuri/stable'",
        "Change charm config of 'my_keystone' 'action-managed-upgrade' to False.",
        "Upgrade 'my_keystone' to the new channel: 'victoria/stable'",
        "Check if the workload of 'my_keystone' has been upgraded",
    ]
    assert len(upgrade_plan.sub_steps) == len(steps_description)
    sub_steps_check = zip(upgrade_plan.sub_steps, steps_description)
    for sub_step, description in sub_steps_check:
        assert sub_step.description == description
    mock_logger.warning.assert_called_once_with(
        "Not triggering the workload upgrade of app %s: %s already set to %s",
        app.name,
        "openstack-origin",
        f"cloud:focal-{target}",
    )


def test_upgrade_plan_application_already_upgraded(status, config, mocker):
    target = "victoria"
    mock_logger = mocker.patch("cou.apps.app.logger")
    app_status = status["keystone_wallaby"]
    app_config = config["openstack_wallaby"]
    app = OpenStackApplication("my_keystone", app_status, app_config, "my_model", "keystone")
    # victoria is lesser than wallaby, so application should not generate a plan.
    with pytest.raises(HaltUpgradePlanGeneration):
        app.generate_upgrade_plan(target)
    mock_logger.info.assert_called_once_with(
        "Application: '%s' already running %s that is equal or greater version than %s. Ignoring.",
        app.name,
        str(app.current_os_release),
        target,
    )


def test_upgrade_plan_application_already_disable_action_managed(status, config):
    target = "victoria"
    app_status = status["keystone_ussuri"]
    app_config = config["openstack_ussuri"]
    app_config["action-managed-upgrade"]["value"] = False
    app = OpenStackApplication(
        "my_keystone",
        app_status,
        app_config,
        "my_model",
        "keystone",
    )
    upgrade_plan = app.generate_upgrade_plan(target)
    steps_description = [
        "Upgrade software packages of 'my_keystone' to the latest in 'ussuri' release",
        "Refresh 'my_keystone' to the latest revision of 'ussuri/stable'",
        "Upgrade 'my_keystone' to the new channel: 'victoria/stable'",
        "Change charm config of 'my_keystone' 'openstack-origin' to 'cloud:focal-victoria'",
        "Check if the workload of 'my_keystone' has been upgraded",
    ]
    assert upgrade_plan.description == "Upgrade plan for 'my_keystone' from: ussuri to victoria"
    assert_plan_description(upgrade_plan, steps_description)


def test_app_factory_create_subordinate_charm(mocker, status):
    # subordinate charms are not instantiated
    mock_logger = mocker.patch("cou.apps.app.logger")
    mysql_router = app_module.AppFactory.create(
        name="keystone-mysql-router",
        status=status["mysql_router"],
        config=mocker.MagicMock(),
        model_name="my_model",
        charm="mysql-router",
    )
    assert mysql_router is None
    mock_logger.warning.assert_called_once_with(
        "'%s' is a subordinate application and it's not currently supported for upgrading",
        "keystone-mysql-router",
    )


def test_app_factory_not_supported_openstack_charm(mocker):
    mock_logger = mocker.patch("cou.apps.app.logger")
    my_app = app_module.AppFactory.create(
        name="my-app",
        status=mocker.MagicMock(),
        config=mocker.MagicMock(),
        model_name="my_model",
        charm="my-app",
    )
    assert my_app is None
    assert mock_logger.debug.called_once_with(
        "'%s' is not a supported OpenStack related application and will be ignored.",
        "my-app",
    )


def test_app_factory_register(status):
    @app_module.AppFactory.register_application(["vault"])
    class Vault:
        def __init__(self, name, status, config, model_name, charm):
            pass

    assert "vault" in app_module.AppFactory.apps_type
    vault = app_module.AppFactory.create("vault", status["vault"], {}, "my_model", "vault")
    assert isinstance(vault, Vault)
