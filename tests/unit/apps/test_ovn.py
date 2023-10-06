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
"""Tests of the ovn application classes."""

import pytest

from cou.apps.ovn import OvnPrincipalApplication, OvnSubordinateApplication
from cou.exceptions import ApplicationError
from cou.steps import UpgradeStep
from cou.utils import app_utils
from cou.utils.openstack import OpenStackRelease
from tests.unit.apps.utils import add_steps


def test_ovn_principal(status, config, model):
    app = OvnPrincipalApplication(
        "ovn-central",
        status["ovn_central_ussuri_22"],
        config["auxiliary_ussuri"],
        model,
        "ovn-central",
    )
    assert app.channel == "22.03/stable"
    assert app.os_origin == "distro"
    assert app.apt_source_codename == "ussuri"
    assert app.channel_codename == "yoga"
    assert app.current_os_release == "yoga"


def test_ovn_subordinate(status, model):
    app = OvnSubordinateApplication(
        "ovn-chassis",
        status["ovn_chassis_ussuri_22"],
        {},
        model,
        "ovn-chassis",
    )
    assert app.channel == "22.03/stable"
    assert app.os_origin == ""
    assert app.apt_source_codename == "yoga"
    assert app.channel_codename == "yoga"
    assert app.current_os_release == "yoga"


def test_ovn_workload_ver_lower_than_22_principal(status, config, model):
    target = "victoria"

    exp_error_msg_ovn_upgrade = (
        "OVN versions lower than 22.03 are not supported. It's necessary to upgrade "
        "OVN to 22.03 before upgrading the cloud. Follow the instructions at: "
        "https://docs.openstack.org/charm-guide/latest/project/procedures/"
        "ovn-upgrade-2203.html"
    )

    app_ovn_central = OvnPrincipalApplication(
        "ovn-central",
        status["ovn_central_ussuri_20"],
        config["auxiliary_ussuri"],
        model,
        "ovn-central",
    )

    with pytest.raises(ApplicationError, match=exp_error_msg_ovn_upgrade):
        app_ovn_central.generate_upgrade_plan(target)


def test_ovn_workload_ver_lower_than_22_subordinate(status, model):
    target = "victoria"

    exp_error_msg_ovn_upgrade = (
        "OVN versions lower than 22.03 are not supported. It's necessary to upgrade "
        "OVN to 22.03 before upgrading the cloud. Follow the instructions at: "
        "https://docs.openstack.org/charm-guide/latest/project/procedures/"
        "ovn-upgrade-2203.html"
    )

    app_ovn_chassis = OvnSubordinateApplication(
        "ovn-chassis",
        status["ovn_chassis_ussuri_20"],
        {},
        model,
        "ovn-chassis",
    )

    with pytest.raises(ApplicationError, match=exp_error_msg_ovn_upgrade):
        app_ovn_chassis.generate_upgrade_plan(target)


@pytest.mark.parametrize("channel", ["55.7", "19.03"])
def test_ovn_no_compatible_os_release(status, config, model, channel):
    ovn_central_status = status["ovn_central_ussuri_22"]
    ovn_central_status.charm_channel = channel
    app = OvnPrincipalApplication(
        "ovn-central",
        ovn_central_status,
        config["auxiliary_ussuri"],
        model,
        "ovn-central",
    )
    with pytest.raises(
        ApplicationError,
        match=(
            f"'{app.charm}' cannot identify suitable OpenStack release codename "
            f"for channel: '{app.channel}'"
        ),
    ):
        app.channel_codename


def test_ovn_principal_upgrade_plan(status, config, model):
    target = "victoria"
    app = OvnPrincipalApplication(
        "ovn-central",
        status["ovn_central_ussuri_22"],
        config["auxiliary_ussuri"],
        model,
        "ovn-central",
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
            description=f"Refresh '{app.name}' to the latest revision of '22.03/stable'",
            parallel=False,
            function=model.upgrade_charm,
            application_name=app.name,
            channel="22.03/stable",
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
            description=f"Check if the workload of '{app.name}' has been upgraded",
            parallel=False,
            function=app._check_upgrade,
            target=OpenStackRelease(target),
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan


def test_ovn_subordinate_upgrade_plan(status, model):
    target = "victoria"
    app = OvnSubordinateApplication(
        "ovn-chassis",
        status["ovn_chassis_ussuri_22"],
        {},
        model,
        "ovn-chassis",
    )

    upgrade_plan = app.generate_upgrade_plan(target)

    expected_plan = UpgradeStep(
        description=f"Upgrade plan for '{app.name}' to {target}",
        parallel=False,
        function=None,
    )

    upgrade_steps = [
        UpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of '22.03/stable'",
            parallel=False,
            function=model.upgrade_charm,
            application_name=app.name,
            channel="22.03/stable",
            switch=None,
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan
