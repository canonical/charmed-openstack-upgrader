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
"""Tests of the ceph application class."""

from cou.apps.app import ApplicationUnit
from cou.apps.ceph import CephMonApplication
from cou.steps import UpgradeStep
from cou.utils import app_utils
from cou.utils.openstack import OpenStackRelease
from tests.unit.apps.utils import add_steps


def test_ceph_mon_app(status, config, model):
    """Test the correctness of instantiating CephMonApplication."""
    app = CephMonApplication(
        "ceph-mon",
        status["ceph-mon_xena"],
        config["auxiliary_xena"],
        model,
        "ceph-mon",
    )
    assert app.channel == "pacific/stable"
    assert app.os_origin == "cloud:focal-xena"
    assert app.units == [
        ApplicationUnit(
            name="ceph-mon/0",
            os_version=OpenStackRelease("xena"),
            workload_version="16.2.0",
            machine="7",
        )
    ]
    assert app.apt_source_codename == "xena"
    assert app.channel_codename == "xena"


def test_test_ceph_mon_upgrade_plan_xena_to_yoga(
    status,
    config,
    model,
):
    """Test when ceph version changes between os releases."""
    target = "yoga"
    app = CephMonApplication(
        "ceph-mon",
        status["ceph-mon_xena"],
        config["auxiliary_xena"],
        model,
        "ceph-mon",
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
            description=f"Refresh '{app.name}' to the latest revision of 'pacific/stable'",
            parallel=False,
            function=model.upgrade_charm,
            application_name=app.name,
            channel="pacific/stable",
            switch=None,
        ),
        UpgradeStep(
            description=(
                "Ensure require-osd-release option on ceph-mon units correctly set to 'pacific'"
            ),
            parallel=False,
            function=app_utils.set_require_osd_release_option,
            unit="ceph-mon/0",
            model=model,
            ceph_release="pacific",
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: 'quincy/stable'",
            parallel=False,
            function=model.upgrade_charm,
            application_name=app.name,
            channel="quincy/stable",
        ),
        UpgradeStep(
            description=(
                f"Change charm config of '{app.name}' "
                f"'{app.origin_setting}' to 'cloud:focal-yoga'"
            ),
            parallel=False,
            function=model.set_application_config,
            name=app.name,
            configuration={f"{app.origin_setting}": "cloud:focal-yoga"},
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
        UpgradeStep(
            description=(
                "Ensure require-osd-release option on ceph-mon units correctly set to 'quincy'"
            ),
            parallel=False,
            function=app_utils.set_require_osd_release_option,
            unit="ceph-mon/0",
            model=model,
            ceph_release="quincy",
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan


def test_ceph_mon_upgrade_plan_ussuri_to_victoria(
    status,
    config,
    model,
):
    """Test when ceph version remains the same between os releases."""
    target = "victoria"
    app = CephMonApplication(
        "ceph-mon",
        status["ceph-mon_ussuri"],
        config["auxiliary_ussuri"],
        model,
        "ceph-mon",
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
            description=f"Refresh '{app.name}' to the latest revision of 'octopus/stable'",
            parallel=False,
            function=model.upgrade_charm,
            application_name=app.name,
            channel="octopus/stable",
            switch=None,
        ),
        UpgradeStep(
            description=(
                "Ensure require-osd-release option on ceph-mon units correctly set to 'octopus'"
            ),
            parallel=False,
            function=app_utils.set_require_osd_release_option,
            unit="ceph-mon/0",
            model=model,
            ceph_release="octopus",
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
        UpgradeStep(
            description=(
                "Ensure require-osd-release option on ceph-mon units correctly set to 'octopus'"
            ),
            parallel=False,
            function=app_utils.set_require_osd_release_option,
            unit="ceph-mon/0",
            model=model,
            ceph_release="octopus",
        ),
    ]
    add_steps(expected_plan, upgrade_steps)

    assert upgrade_plan == expected_plan
