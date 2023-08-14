# Copyright 2023 Canonical Limited.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
from collections import OrderedDict

import pytest

from cou.apps import app as app_module
from cou.apps.app import Application


def test_application_eq(status, config):
    """Name of the app is used as comparison between Applications objects."""
    status_keystone_1 = status["keystone_ussuri"]
    config_keystone_1 = config["openstack_ussuri"]
    status_keystone_2 = status["keystone_wallaby"]
    config_keystone_2 = config["openstack_wallaby"]
    keystone_1 = Application(
        "keystone", status_keystone_1, config_keystone_1, "my_model", "keystone"
    )
    keystone_2 = Application(
        "keystone", status_keystone_2, config_keystone_2, "my_model", "keystone"
    )
    keystone_3 = Application(
        "keystone_foo", status_keystone_1, config_keystone_1, "my_model", "keystone"
    )

    # keystone_1 is equal to keystone_2 because they have the same name
    # even if they have different status and config.
    assert keystone_1 == keystone_2
    # keystone_1 is different then keystone_3 even if they have same status and config.
    assert keystone_1 != keystone_3


def assert_application(
    app: Application,
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
    exp_next_os_release,
    exp_current_channel,
    exp_next_channel,
    exp_new_origin,
    expected_os_origin_release,
    target,
):
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
    if exp_next_os_release:
        assert app.current_os_release.next_release == exp_next_os_release
    assert app.next_os_release == exp_next_os_release
    assert app.expected_current_channel == exp_current_channel
    assert app.next_channel == exp_next_channel
    assert app.new_origin(target) == exp_new_origin
    assert app.os_origin_release(target) == expected_os_origin_release


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
    exp_next_os_release = "victoria"
    exp_current_channel = "ussuri/stable"
    exp_next_channel = "victoria/stable"
    exp_new_origin = f"cloud:{exp_series}-{exp_next_os_release}"
    expected_os_origin_release = "ussuri"

    app = Application("my_keystone", app_status, app_config, "my_model", "keystone")
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
        exp_next_os_release,
        exp_current_channel,
        exp_next_channel,
        exp_new_origin,
        expected_os_origin_release,
        target,
    )
    assert app.can_generate_upgrade_plan()


def test_application_different_wl(status, config, units):
    """Different OpenStack Version on units if workload version is different."""
    target = "victoria"
    app_status = status["keystone_ussuri_victoria"]
    app_config = config["openstack_ussuri"]
    exp_charm_origin = "ch"
    exp_os_origin = "distro"
    exp_units = units["units_ussuri"]
    exp_channel = app_status.charm_channel
    exp_series = app_status.series
    exp_current_os_release = None
    exp_next_os_release = None
    exp_current_channel = None
    exp_next_channel = None
    exp_new_origin = None
    expected_os_origin_release = "ussuri"

    exp_units["keystone/2"]["os_version"] = "victoria"
    exp_units["keystone/2"]["workload_version"] = "18.1.0"

    app = Application("my_keystone", app_status, app_config, "my_model", "keystone")
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
        exp_next_os_release,
        exp_current_channel,
        exp_next_channel,
        exp_new_origin,
        expected_os_origin_release,
        target,
    )
    assert app.can_generate_upgrade_plan() is False


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
    exp_next_os_release = "victoria"
    exp_current_channel = "ussuri/stable"
    exp_next_channel = "victoria/stable"
    exp_new_origin = f"cloud:{exp_series}-{exp_next_os_release}"
    expected_os_origin_release = "ussuri"

    app = Application("my_keystone", app_status, app_config, "my_model", "keystone")
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
        exp_next_os_release,
        exp_current_channel,
        exp_next_channel,
        exp_new_origin,
        expected_os_origin_release,
        target,
    )
    assert app.can_generate_upgrade_plan()


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
    exp_next_os_release = "xena"
    exp_current_channel = "wallaby/stable"
    exp_next_channel = "xena/stable"
    exp_new_origin = f"cloud:{exp_series}-{exp_next_os_release}"
    expected_os_origin_release = "wallaby"

    app = Application("my_keystone", app_status, app_config, "my_model", "keystone")
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
        exp_next_os_release,
        exp_current_channel,
        exp_next_channel,
        exp_new_origin,
        expected_os_origin_release,
        target,
    )
    assert app.can_generate_upgrade_plan()


def test_special_app_ussuri(status, config):
    # version 3.8 on rabbitmq can be from ussuri to yoga. In that case it will be set as yoga.
    expected_units = {"rabbitmq-server/0": {"os_version": "yoga", "workload_version": "3.8"}}
    app = app_module.RabbitMQServer(
        "rabbitmq-server",
        status["rabbitmq_server"],
        config["rmq_ussuri"],
        "my_model",
        "rabbitmq-server",
    )
    assert app.units == expected_units


def test_special_app_unknown_version(status, config):
    expected_units = {"rabbitmq-server/0": {"os_version": None, "workload_version": "80.5"}}
    app = app_module.RabbitMQServer(
        "rabbitmq-server",
        status["unknown_rabbitmq_server"],
        config["rmq_ussuri"],
        "my_model",
        "rabbitmq-server",
    )
    assert app.units == expected_units


def test_application_no_openstack_origin(status):
    """Test when application doesn't have openstack-origin or source config."""
    app_status = status["keystone_wallaby"]
    app_config = {}
    app = Application("my_app", app_status, app_config, "my_model", "my_charm")
    assert app._get_os_origin() is None
    assert app.os_origin_release("xena") is None


@pytest.mark.asyncio
async def test_application_check_upgrade(status, config, mocker):
    mock_logger = mocker.patch("cou.apps.app.logger")
    app_status = status["keystone_ussuri"]
    app_config = config["openstack_ussuri"]

    # workload version changed from ussuri to victoria
    mock_status = mocker.MagicMock()
    mock_status.applications = {"my_keystone": status["keystone_victoria"]}

    mocker.patch.object(app_module, "async_get_status", return_value=mock_status)
    app = Application("my_keystone", app_status, app_config, "my_model", "keystone")
    await app.check_upgrade()
    mock_logger.error.assert_not_called()


@pytest.mark.asyncio
async def test_application_check_upgrade_fail(status, config, mocker):
    mock_logger = mocker.patch("cou.apps.app.logger")
    app_status = status["keystone_ussuri"]
    app_config = config["openstack_ussuri"]

    # workload version didn't change from ussuri to victoria
    mock_status = mocker.MagicMock()
    mock_status.applications = {"my_keystone": status["keystone_ussuri"]}

    mocker.patch.object(app_module, "async_get_status", return_value=mock_status)
    app = Application("my_keystone", app_status, app_config, "my_model", "keystone")
    await app.check_upgrade()
    mock_logger.error.assert_called_once_with(
        "App: '%s' has units: '%s' didn't upgrade to %s",
        "my_keystone",
        "keystone/0, keystone/1, keystone/2",
        "victoria",
    )


@pytest.mark.parametrize(
    "ceph_version, ceph_codename, next_ceph_codename, expected_os_version",
    [
        ("15.2.0", "octopus", "pacific", "victoria"),
        ("16.2.0", "pacific", "quincy", "xena"),
        ("17.2.0", "quincy", "quincy", "yoga"),
    ],
)
def test_ceph_application(
    mocker, ceph_version, ceph_codename, next_ceph_codename, expected_os_version
):
    mock_ceph = mocker.MagicMock()
    mock_ceph.series = "focal"
    mock_ceph.charm = "ch:amd64/focal/ceph-mon-777"
    mock_units_ceph = mocker.MagicMock()
    mock_units_ceph.workload_version = ceph_version
    mock_ceph.units = OrderedDict(
        [
            ("ceph-mon/0", mock_units_ceph),
            ("ceph-mon/1", mock_units_ceph),
            ("ceph-mon/2", mock_units_ceph),
        ]
    )
    ceph_config = {"source": {"value": f"cloud:focal-{expected_os_version}"}}
    ceph_mon = app_module.AppFactory.create(
        app_type="ceph-mon",
        name="ceph-mon",
        status=mock_ceph,
        config=ceph_config,
        model_name="my_model",
        charm="ceph",
    )
    assert ceph_mon.current_os_release == expected_os_version
    assert ceph_mon.expected_current_channel == f"{ceph_codename}/stable"
    assert ceph_mon.next_channel == f"{next_ceph_codename}/stable"


def test_ceph_application_unknown_os_release(mocker):
    mock_ceph = mocker.MagicMock()
    mock_ceph.series = "focal"
    mock_ceph.charm = "ch:amd64/focal/ceph-mon-777"
    mock_units_ceph = mocker.MagicMock()
    mock_units_ceph.workload_version = "36.2.0"
    mock_ceph.units = OrderedDict(
        [
            ("ceph-mon/0", mock_units_ceph),
            ("ceph-mon/1", mock_units_ceph),
            ("ceph-mon/2", mock_units_ceph),
        ]
    )
    ceph_config = {"source": {"value": "cloud:focal-ussuri"}}
    ceph_mon = app_module.AppFactory.create(
        app_type="ceph-mon",
        name="ceph-mon",
        status=mock_ceph,
        config=ceph_config,
        model_name="my_model",
        charm="ceph",
    )
    assert ceph_mon.current_os_release is None
    assert ceph_mon.expected_current_channel is None
    assert ceph_mon.next_channel is None


def test_app_factory_registered_ceph_charms():
    ceph_charms = app_module.CHARM_TYPES["ceph"]
    for ceph_charm in ceph_charms:
        assert ceph_charm in app_module.AppFactory.apps_type.keys()


def assert_plan_description(upgrade_plan, steps_description):
    assert len(upgrade_plan.sub_steps) == len(steps_description)
    sub_steps_check = zip(upgrade_plan.sub_steps, steps_description)
    for sub_step, description in sub_steps_check:
        assert sub_step.description == description


def test_upgrade_plan_ussuri_to_victoria(status, config):
    app_status = status["keystone_ussuri"]
    app_config = config["openstack_ussuri"]
    app = Application("my_keystone", app_status, app_config, "my_model", "keystone")
    upgrade_plan = app.generate_upgrade_plan(app.next_os_release)
    steps_description = [
        "Refresh 'my_keystone' to the latest revision of 'ussuri/stable'",
        "Change charm config of 'my_keystone' 'action-managed-upgrade' to False.",
        "Refresh 'my_keystone' to the new channel: 'victoria/stable'",
        "Change charm config of 'my_keystone' 'openstack-origin' to 'cloud:focal-victoria'",
        "Check if workload of 'my_keystone' has upgraded",
    ]
    assert upgrade_plan.description == "Upgrade plan for 'my_keystone' from: ussuri to victoria"
    assert_plan_description(upgrade_plan, steps_description)


def test_upgrade_plan_ussuri_to_victoria_ch_migration(status, config):
    app_status = status["keystone_ussuri_cs"]
    app_config = config["openstack_ussuri"]
    app = Application("my_keystone", app_status, app_config, "my_model", "keystone")
    upgrade_plan = app.generate_upgrade_plan(app.next_os_release)
    steps_description = [
        "Migration of 'my_keystone' from charmstore to charmhub",
        "Change charm config of 'my_keystone' 'action-managed-upgrade' to False.",
        "Refresh 'my_keystone' to the new channel: 'victoria/stable'",
        "Change charm config of 'my_keystone' 'openstack-origin' to 'cloud:focal-victoria'",
        "Check if workload of 'my_keystone' has upgraded",
    ]
    assert upgrade_plan.description == "Upgrade plan for 'my_keystone' from: ussuri to victoria"
    assert_plan_description(upgrade_plan, steps_description)


def test_cant_generate_upgrade_plan(status, config, mocker):
    mock_logger = mocker.patch("cou.apps.app.logger")
    app_status = status["keystone_ussuri_victoria"]
    app_config = config["openstack_ussuri"]
    app = Application("my_keystone", app_status, app_config, "my_model", "keystone")
    upgrade_plan = app.generate_upgrade_plan("victoria")
    assert upgrade_plan is None
    assert mock_logger.warning.call_count == 3


def test_upgrade_plan_change_current_channel(status, config):
    app_status = status["keystone_ussuri"]
    app_config = config["openstack_ussuri"]
    # channel it's neither the expected as current channel as ussuri/stable or
    # next_channel victoria/stable
    app_status.charm_channel = "foo/stable"
    app = Application("my_keystone", app_status, app_config, "my_model", "keystone")
    upgrade_plan = app.generate_upgrade_plan(app.next_os_release)

    steps_description = [
        "Changing 'my_keystone' channel from: 'foo/stable' to: 'ussuri/stable'",
        "Change charm config of 'my_keystone' 'action-managed-upgrade' to False.",
        "Refresh 'my_keystone' to the new channel: 'victoria/stable'",
        "Change charm config of 'my_keystone' 'openstack-origin' to 'cloud:focal-victoria'",
        "Check if workload of 'my_keystone' has upgraded",
    ]

    assert_plan_description(upgrade_plan, steps_description)


def test_upgrade_plan_channel_on_next_os_release(status, config, mocker):
    mock_logger = mocker.patch("cou.apps.app.logger")
    app_status = status["keystone_ussuri"]
    app_config = config["openstack_ussuri"]
    # channel it's already on next OpenStack release
    app_status.charm_channel = "victoria/stable"
    app = Application("my_keystone", app_status, app_config, "my_model", "keystone")
    upgrade_plan = app.generate_upgrade_plan(app.next_os_release)

    # no sub-step for refresh current channel or next channel
    steps_description = [
        "Change charm config of 'my_keystone' 'action-managed-upgrade' to False.",
        "Change charm config of 'my_keystone' 'openstack-origin' to 'cloud:focal-victoria'",
        "Check if workload of 'my_keystone' has upgraded",
    ]

    assert_plan_description(upgrade_plan, steps_description)
    mock_logger.warning.assert_called_once_with(
        "App: %s already has the channel set for the next OpenStack version %s",
        "my_keystone",
        "victoria",
    )


def test_upgrade_plan_origin_already_on_next_openstack_release(status, config, mocker):
    mock_logger = mocker.patch("cou.apps.app.logger")
    app_status = status["keystone_ussuri"]
    app_config = config["openstack_ussuri"]
    # openstack-origin already configured for next OpenStack release
    app_config["openstack-origin"]["value"] = "cloud:focal-victoria"
    app = Application("my_keystone", app_status, app_config, "my_model", "keystone")
    upgrade_plan = app.generate_upgrade_plan(app.next_os_release)
    steps_description = [
        "Refresh 'my_keystone' to the latest revision of 'ussuri/stable'",
        "Change charm config of 'my_keystone' 'action-managed-upgrade' to False.",
        "Refresh 'my_keystone' to the new channel: 'victoria/stable'",
        "Check if workload of 'my_keystone' has upgraded",
    ]
    assert len(upgrade_plan.sub_steps) == len(steps_description)
    sub_steps_check = zip(upgrade_plan.sub_steps, steps_description)
    for sub_step, description in sub_steps_check:
        assert sub_step.description == description
    mock_logger.warning.assert_called_once_with(
        "App: %s already have %s set to %s",
        "my_keystone",
        "openstack-origin",
        "cloud:focal-victoria",
    )


def test_upgrade_plan_application_already_upgraded(status, config, mocker):
    target = "victoria"
    mock_logger = mocker.patch("cou.apps.app.logger")
    app_status = status["keystone_wallaby"]
    app_config = config["openstack_wallaby"]
    app = Application("my_keystone", app_status, app_config, "my_model", "keystone")
    # victoria is lesser than wallaby, so application should not generate a plan.
    upgrade_plan = app.generate_upgrade_plan(target)
    mock_logger.warning.assert_called_once_with(
        "Application: '%s' already on a newer version than %s. Aborting upgrade.",
        "my_keystone",
        target,
    )
    assert upgrade_plan is None


def test_upgrade_plan_special_no_new_channel(status):
    target = "victoria"
    app_status = status["rabbitmq_server"]
    # os_origin_release will be considered as the previous OpenStack version from target
    app_config = {"source": {"value": ""}}
    app = app_module.RabbitMQServer(
        "rabbitmq-server", app_status, app_config, "my_model", "rabbitmq-server"
    )
    upgrade_plan = app.generate_upgrade_plan(target)
    # no refresh to next channel
    steps_description = [
        "Refresh 'rabbitmq-server' to the latest revision of '3.8/stable'",
        "Change charm config of 'rabbitmq-server' 'source' to 'cloud:focal-victoria'",
        "Check if workload of 'rabbitmq-server' has upgraded",
    ]
    assert app.os_origin_release(target) == "ussuri"
    assert upgrade_plan.description == "Upgrade plan for 'rabbitmq-server' to: victoria"
    assert_plan_description(upgrade_plan, steps_description)


def test_upgrade_plan_special_new_channel(status):
    target = "wallaby"
    app_status = status["ceph_mon_victoria"]
    app_config = {"source": {"value": "cloud:focal-victoria"}}
    app = app_module.Ceph("ceph-mon", app_status, app_config, "my_model", "ceph-mon")
    upgrade_plan = app.generate_upgrade_plan(target)
    # refresh to next channel
    steps_description = [
        "Refresh 'ceph-mon' to the latest revision of 'octopus/stable'",
        "Refresh 'ceph-mon' to the new channel: 'pacific/stable'",
        "Change charm config of 'ceph-mon' 'source' to 'cloud:focal-wallaby'",
        "Check if workload of 'ceph-mon' has upgraded",
    ]
    assert upgrade_plan.description == "Upgrade plan for 'ceph-mon' to: wallaby"
    assert_plan_description(upgrade_plan, steps_description)
