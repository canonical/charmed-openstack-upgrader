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
"""Subordinate application class."""
import logging
from unittest.mock import MagicMock

import pytest

from cou.apps.subordinate import SubordinateApplication
from cou.exceptions import ApplicationError
from cou.steps import ApplicationUpgradePlan, PreUpgradeStep, UpgradeStep
from cou.utils.juju_utils import Machine
from cou.utils.openstack import OpenStackRelease
from tests.unit.utils import assert_steps

logger = logging.getLogger(__name__)


def test_current_os_release(model):
    """Test current_os_release for SubordinateApplication."""
    machines = {"0": MagicMock(spec_set=Machine)}
    app = SubordinateApplication(
        name="keystone-ldap",
        can_upgrade_to="ussuri/stable",
        charm="keystone-ldap",
        channel="ussuri/stable",
        config={},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=["nova-compute"],
        units={},
        workload_version="18.1.0",
    )

    assert app.current_os_release == OpenStackRelease("ussuri")


def test_generate_upgrade_plan(model):
    """Test generate upgrade plan for SubordinateApplication."""
    target = OpenStackRelease("victoria")
    machines = {"0": MagicMock(spec_set=Machine)}
    app = SubordinateApplication(
        name="keystone-ldap",
        can_upgrade_to="ussuri/stable",
        charm="keystone-ldap",
        channel="ussuri/stable",
        config={},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=["nova-compute"],
        units={},
        workload_version="18.1.0",
    )
    expected_plan = ApplicationUpgradePlan(f"Upgrade plan for '{app.name}' to '{target}'")
    upgrade_steps = [
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of 'ussuri/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "ussuri/stable"),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: 'victoria/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "victoria/stable"),
        ),
    ]
    expected_plan.add_steps(upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)
    assert_steps(upgrade_plan, expected_plan)


@pytest.mark.parametrize(
    "channel",
    [
        "ussuri/stable",
        "victoria/stable",
        "xena/stable",
        "yoga/stable",
        "wallaby/stable",
        "wallaby/edge",
    ],
)
def test_channel_valid(model, channel):
    """Test successful validation of channel upgrade plan for SubordinateApplication."""
    machines = {"0": MagicMock(spec_set=Machine)}
    app = SubordinateApplication(
        name="keystone-ldap",
        can_upgrade_to=channel,
        charm="keystone-ldap",
        channel=channel,
        config={},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=["nova-compute"],
        units={},
        workload_version="18.1.0",
    )

    assert app.channel == channel


@pytest.mark.parametrize(
    "channel",
    [
        "focal/edge",
        "latest/edge",
        "something/stable",
    ],
)
def test_channel_setter_invalid(model, channel):
    """Test unsuccessful validation of channel upgrade plan for SubordinateApplication."""
    machines = {"0": MagicMock(spec_set=Machine)}
    app = SubordinateApplication(
        name="keystone-ldap",
        can_upgrade_to=channel,
        charm="keystone-ldap",
        channel=channel,
        config={},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=["nova-compute"],
        units={},
        workload_version="18.1.0",
    )

    with pytest.raises(ApplicationError):
        app._check_channel()


@pytest.mark.parametrize(
    "channel",
    [
        "stable",
        "edge",
        "candidate",
    ],
)
def test_generate_plan_ch_migration(model, channel):
    """Test generate upgrade plan for SubordinateApplication with charmhub migration."""
    target = OpenStackRelease("wallaby")
    machines = {"0": MagicMock(spec_set=Machine)}
    app = SubordinateApplication(
        name="keystone-ldap",
        can_upgrade_to="wallaby/stable",
        charm="keystone-ldap",
        channel=f"ussuri/{channel}",
        config={},
        machines=machines,
        model=model,
        origin="cs",
        series="focal",
        subordinate_to=["nova-compute"],
        units={},
        workload_version="18.1.0",
    )
    expected_plan = ApplicationUpgradePlan(f"Upgrade plan for '{app.name}' to '{target}'")
    upgrade_steps = [
        PreUpgradeStep(
            description=f"Migrate '{app.name}' from charmstore to charmhub",
            parallel=False,
            coro=model.upgrade_charm(app.name, "ussuri/stable", switch="ch:keystone-ldap"),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: 'wallaby/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, "wallaby/stable"),
        ),
    ]
    expected_plan.add_steps(upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)
    assert_steps(upgrade_plan, expected_plan)


@pytest.mark.parametrize(
    "from_os, to_os",
    [
        (["ussuri", "victoria"]),
        (["victoria", "wallaby"]),
        (["wallaby", "xena"]),
        (["xena", "yoga"]),
    ],
)
def test_generate_plan_from_to(model, from_os, to_os):
    """Test generate upgrade plan for SubordinateApplication from to version."""
    target = OpenStackRelease(to_os)
    machines = {"0": MagicMock(spec_set=Machine)}
    app = SubordinateApplication(
        name="keystone-ldap",
        can_upgrade_to=f"{to_os}/stable",
        charm="keystone-ldap",
        channel=f"{from_os}/stable",
        config={},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=["nova-compute"],
        units={},
        workload_version="18.1.0",
    )
    expected_plan = ApplicationUpgradePlan(f"Upgrade plan for '{app.name}' to '{to_os}'")
    upgrade_steps = [
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of '{from_os}/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, f"{from_os}/stable"),
        ),
        UpgradeStep(
            description=f"Upgrade '{app.name}' to the new channel: '{to_os}/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, f"{to_os}/stable"),
        ),
    ]
    expected_plan.add_steps(upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)
    assert_steps(upgrade_plan, expected_plan)


@pytest.mark.parametrize(
    "from_to",
    [
        "ussuri",
        "victoria",
        "wallaby",
        "xena",
        "yoga",
    ],
)
def test_generate_plan_in_same_version(model, from_to):
    """Test generate upgrade plan for SubordinateApplication in same version."""
    target = OpenStackRelease(from_to)
    machines = {"0": MagicMock(spec_set=Machine)}
    app = SubordinateApplication(
        name="keystone-ldap",
        can_upgrade_to=f"{from_to}/stable",
        charm="keystone-ldap",
        channel=f"{from_to}/stable",
        config={},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=["nova-compute"],
        units={},
        workload_version="18.1.0",
    )
    expected_plan = ApplicationUpgradePlan(f"Upgrade plan for '{app.name}' to '{from_to}'")
    upgrade_steps = [
        PreUpgradeStep(
            description=f"Refresh '{app.name}' to the latest revision of '{from_to}/stable'",
            parallel=False,
            coro=model.upgrade_charm(app.name, f"{from_to}/stable"),
        ),
    ]
    expected_plan.add_steps(upgrade_steps)

    upgrade_plan = app.generate_upgrade_plan(target, False)
    assert_steps(upgrade_plan, expected_plan)
