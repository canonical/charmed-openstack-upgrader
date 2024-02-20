# Copyright 2024 Canonical Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Test hypervisor package."""

from unittest.mock import MagicMock

from cou.apps.base import OpenStackApplication
from cou.steps import PostUpgradeStep, PreUpgradeStep, UpgradeStep
from cou.steps.hypervisor import HypervisorUpgradePlanner
from cou.utils.openstack import OpenStackRelease


def _generate_app() -> MagicMock:
    app = MagicMock(spec_set=OpenStackApplication)()
    app.pre_upgrade_steps.return_value = [MagicMock(spec_set=PreUpgradeStep)()]
    app.upgrade_steps.return_value = [MagicMock(spec_set=UpgradeStep)()]
    app.post_upgrade_steps.return_value = [MagicMock(spec_set=PostUpgradeStep)()]
    return app


def test_generate_pre_upgrade_plan():
    """Test generating of pre-upgrade steps."""
    target = OpenStackRelease("victoria")
    apps = [_generate_app() for _ in range(3)]

    planner = HypervisorUpgradePlanner(apps)

    steps = planner._generate_pre_upgrade_plan(target)

    for step, app in zip(steps, apps):
        app.pre_upgrade_steps.assert_called_once_with(target, units=None)
        assert step == app.pre_upgrade_steps.return_value[0]  # mocked app contain single step


def test_generate_post_upgrade_plan():
    """Test generating of post-upgrade steps."""
    target = OpenStackRelease("victoria")
    apps = [_generate_app() for _ in range(3)]
    planner = HypervisorUpgradePlanner(apps)

    steps = planner._generate_post_upgrade_plan(target)

    for step, app in zip(steps, apps[::-1]):  # using reversed order of applications
        app.post_upgrade_steps.assert_called_once_with(target, units=None)
        assert step == app.post_upgrade_steps.return_value[0]  # mocked app contain single step
