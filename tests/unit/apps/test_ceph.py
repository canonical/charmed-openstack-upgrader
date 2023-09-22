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
from cou.apps.ceph import CephMonApplication
from tests.unit.apps.utils import assert_plan_description


def test_ceph_mon_app(status, config, model):
    """Test the correctness of instantiating CephMonApplication."""
    expected_units = {"ceph-mon/0": {"os_version": "xena", "workload_version": "16.2.0"}}
    app = CephMonApplication(
        "ceph-mon",
        status["ceph-mon_xena"],
        config["auxiliary_xena"],
        model,
        "ceph-mon",
    )
    assert app.channel == "pacific/stable"
    assert app.os_origin == "cloud:focal-xena"
    assert app.units == expected_units
    assert app.apt_source_codename == "xena"
    assert app.channel_codename == "xena"


def test_test_ceph_mon_upgrade_plan_xena_to_yoga(status, config, model):
    """Test when ceph version changes between os releases."""
    target = "yoga"
    app = CephMonApplication(
        "ceph-mon",
        status["ceph-mon_xena"],
        config["auxiliary_xena"],
        model,
        "ceph-mon",
    )

    plan = app.generate_upgrade_plan(target)

    steps_description = [
        f"Upgrade software packages of '{app.name}' from the current APT repositories",
        f"Refresh '{app.name}' to the latest revision of 'pacific/stable'",
        "Ensure require-osd-release option on ceph-mon units correctly set to 'pacific'",
        "Upgrade 'ceph-mon' to the new channel: 'quincy/stable'",
        f"Change charm config of '{app.name}' 'source' to 'cloud:focal-yoga'",
        f"Check if the workload of '{app.name}' has been upgraded",
        "Ensure require-osd-release option on ceph-mon units correctly set to 'quincy'",
    ]

    assert_plan_description(plan, steps_description)


def test_ceph_mon_upgrade_plan_ussuri_to_victoria(status, config, model):
    """Test when ceph version remains the same between os releases."""
    target = "victoria"
    app = CephMonApplication(
        "ceph-mon",
        status["ceph-mon_ussuri"],
        config["auxiliary_ussuri"],
        model,
        "ceph-mon",
    )
    plan = app.generate_upgrade_plan(target)

    steps_description = [
        f"Upgrade software packages of '{app.name}' from the current APT repositories",
        f"Refresh '{app.name}' to the latest revision of 'octopus/stable'",
        "Ensure require-osd-release option on ceph-mon units correctly set to 'octopus'",
        f"Change charm config of '{app.name}' 'source' to 'cloud:focal-victoria'",
        f"Check if the workload of '{app.name}' has been upgraded",
        "Ensure require-osd-release option on ceph-mon units correctly set to 'octopus'",
    ]

    assert_plan_description(plan, steps_description)