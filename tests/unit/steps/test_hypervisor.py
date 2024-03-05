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
from cou.apps.core import NovaCompute
from cou.steps import PostUpgradeStep, PreUpgradeStep, UpgradeStep
from cou.steps.hypervisor import AZs, HypervisorGroup, HypervisorUpgradePlanner
from cou.utils.juju_utils import COUApplication, COUMachine, COUUnit
from cou.utils.openstack import OpenStackRelease
from tests.unit.utils import dedent_plan, generate_cou_machine


def _generate_app() -> MagicMock:
    app = MagicMock(spec_set=OpenStackApplication)()
    app.pre_upgrade_steps.return_value = [MagicMock(spec_set=PreUpgradeStep)()]
    app.upgrade_steps.return_value = [MagicMock(spec_set=UpgradeStep)()]
    app.post_upgrade_steps.return_value = [MagicMock(spec_set=PostUpgradeStep)()]
    return app


def test_generate_pre_upgrade_steps():
    """Test generating of pre-upgrade steps."""
    target = OpenStackRelease("victoria")
    units = ["1", "2", "3"]
    machines = [COUMachine(f"{i}", (), f"az{i}") for i in range(3)]
    apps = [_generate_app() for _ in range(3)]
    planner = HypervisorUpgradePlanner(apps, machines)
    group = HypervisorGroup("test", {app.name.return_value: units for app in apps})

    planner = HypervisorUpgradePlanner(apps, machines)
    steps = planner._generate_pre_upgrade_steps(target, group)

    for step, app in zip(steps, apps):
        app.pre_upgrade_steps.assert_called_once_with(target, units=units)
        assert step == app.pre_upgrade_steps.return_value[0]  # mocked app contain single step


def test_generate_post_upgrade_steps():
    """Test generating of post-upgrade steps."""
    target = OpenStackRelease("victoria")
    units = ["1", "2", "3"]
    machines = [COUMachine(f"{i}", (), f"az{i}") for i in range(3)]
    apps = [_generate_app() for _ in range(3)]
    group = HypervisorGroup("test", {app.name.return_value: units for app in apps})

    planner = HypervisorUpgradePlanner(apps, machines)
    steps = planner._generate_post_upgrade_steps(target, group)

    for step, app in zip(steps, apps[::-1]):  # using reversed order of applications
        app.post_upgrade_steps.assert_called_once_with(target, units=units)
        assert step == app.post_upgrade_steps.return_value[0]  # mocked app contain single step


def test_hypervisor_group():
    """Test base logic of HypervisorGroup object."""
    group1 = HypervisorGroup("test", {"app1": []})
    group2 = HypervisorGroup("test", {"app2": []})
    group3 = HypervisorGroup("test", {"app1": []})

    assert group1 != group2
    assert group1 == group3
    assert group1 is not None
    assert group1 != "test"


def test_azs():
    """Test AZs as custom defaultdict object."""
    azs = AZs()
    test_unit = COUUnit("my-unit", MagicMock(spec_set=COUMachine)(), "")

    # test accessing parts of AZs
    assert azs["my-az"].name == "my-az"
    assert azs["my-az"].app_units["my-app"] == []

    # append unit to the HypervisorGroup
    azs["my-az"].app_units["my-app"].append(test_unit)
    assert azs["my-az"].app_units["my-app"] == [test_unit]


def test_hypervisor_azs_grouping():
    """Test HypervisorUpgradePlanner azs grouping.

    This should return 3 AZs where each has 2 machines and app1 is deployed on every
    machine and app2 is only deployed on every even machine.

    Juju status example:
    ```bash
    App                   Version  Status  Scale  Charm          Channel  Rev  Exposed  Message
    app1
    app2

    Unit                     Workload  Agent  Machine  Public address  Ports  Message
    app1/0*                  active    idle   0
    app1/1                   active    idle   1
    app1/2                   active    idle   2
    app1/3                   active    idle   3
    app1/4                   active    idle   4
    app1/5                   active    idle   5
    app2/0*                  active    idle   0
    app2/1                   active    idle   2
    app2/2                   active    idle   4

    Machine  State    Address      Inst id        Base          AZ  Message
    0        started  10.10.10.1   host0          ubuntu@22.04  az0 Running
    1        started  10.10.10.2   host1          ubuntu@22.04  az0 Running
    2        started  10.10.10.3   host2          ubuntu@22.04  az1 Running
    3        started  10.10.10.4   host3          ubuntu@22.04  az1 Running
    4        started  10.10.10.5   host4          ubuntu@22.04  az2 Running
    5        started  10.10.10.6   host5          ubuntu@22.04  az2 Running
    ```
    """
    machines = {f"{i}": COUMachine(f"{i}", (), f"az{i//2}") for i in range(6)}
    units = {
        # app1
        "app1/0": COUUnit("app1/0", machines["0"], ""),
        "app1/1": COUUnit("app1/1", machines["1"], ""),
        "app1/2": COUUnit("app1/2", machines["2"], ""),
        "app1/3": COUUnit("app1/3", machines["3"], ""),
        "app1/4": COUUnit("app1/4", machines["4"], ""),
        "app1/5": COUUnit("app1/5", machines["5"], ""),
        # app2
        "app2/0": COUUnit("app2/0", machines["0"], ""),
        "app2/1": COUUnit("app2/1", machines["2"], ""),
        "app2/2": COUUnit("app2/2", machines["4"], ""),
    }

    app1 = MagicMock(spec_set=COUApplication)()
    app1.name = "app1"
    app1.units = {name: unit for name, unit in units.items() if name.startswith("app1")}
    app2 = MagicMock(spec_set=COUApplication)()
    app2.name = "app2"
    app2.units = {name: unit for name, unit in units.items() if name.startswith("app2")}

    # passing all machines to the HypervisorUpgradePlanner
    exp_azs_all = AZs()
    exp_azs_all["az0"].app_units["app1"] = [units["app1/0"], units["app1/1"]]
    exp_azs_all["az0"].app_units["app2"] = [units["app2/0"]]
    exp_azs_all["az1"].app_units["app1"] = [units["app1/2"], units["app1/3"]]
    exp_azs_all["az1"].app_units["app2"] = [units["app2/1"]]
    exp_azs_all["az2"].app_units["app1"] = [units["app1/4"], units["app1/5"]]
    exp_azs_all["az2"].app_units["app2"] = [units["app2/2"]]

    hypervisor_planner_all = HypervisorUpgradePlanner([app1, app2], list(machines.values()))

    assert dict(hypervisor_planner_all.azs) == exp_azs_all

    # passing machine 0 to the HypervisorUpgradePlanner
    exp_azs_0 = AZs()
    exp_azs_0["az0"].app_units["app1"] = [units["app1/0"]]
    exp_azs_0["az0"].app_units["app2"] = [units["app2/0"]]

    hypervisor_planner_machine_0 = HypervisorUpgradePlanner([app1, app2], [machines["0"]])
    assert dict(hypervisor_planner_machine_0.azs) == exp_azs_0

    # passing machine 1 to the HypervisorUpgradePlanner
    exp_azs_1 = AZs()
    exp_azs_1["az0"].app_units["app1"] = [units["app1/1"]]

    hypervisor_planner_machine_1 = HypervisorUpgradePlanner([app1, app2], [machines["1"]])
    assert dict(hypervisor_planner_machine_1.azs) == exp_azs_1


def test_hypervisor_upgrade_plan(model):
    """Testing generating hypervisors upgrade plan."""
    target = OpenStackRelease("victoria")
    exp_plan = dedent_plan(
        """
    Upgrading all applications deployed on machines with hypervisor.
        Upgrade plan for 'az-0' to victoria
            Upgrade software packages of 'cinder' from the current APT repositories
                Upgrade software packages on unit cinder/0
            Refresh 'cinder' to the latest revision of 'ussuri/stable'
            Upgrade software packages of 'nova-compute' from the current APT repositories
                Upgrade software packages on unit nova-compute/0
            Refresh 'nova-compute' to the latest revision of 'ussuri/stable'
            Change charm config of 'cinder' 'action-managed-upgrade' to True
            Upgrade 'cinder' to the new channel: 'victoria/stable'
            Change charm config of 'cinder' 'openstack-origin' to 'cloud:focal-victoria'
            Upgrade plan for units: cinder/0
                Upgrade plan for unit: cinder/0
                    Pause the unit: 'cinder/0'.
                    Upgrade the unit: 'cinder/0'.
                    Resume the unit: 'cinder/0'.
            Change charm config of 'nova-compute' 'action-managed-upgrade' to True
            Upgrade 'nova-compute' to the new channel: 'victoria/stable'
            Change charm config of 'nova-compute' 'source' to 'cloud:focal-victoria'
            Upgrade plan for units: nova-compute/0
                Upgrade plan for unit: nova-compute/0
                    Disable nova-compute scheduler from unit: 'nova-compute/0'.
                    Check if unit nova-compute/0 has no VMs running before upgrading.
                    ├── Pause the unit: 'nova-compute/0'.
                    ├── Upgrade the unit: 'nova-compute/0'.
                    ├── Resume the unit: 'nova-compute/0'.
                    Enable nova-compute scheduler from unit: 'nova-compute/0'.
            Wait 1800s for model test_model to reach the idle state.
            Check if the workload of 'nova-compute' has been upgraded on units: nova-compute/0
            Wait 300s for app cinder to reach the idle state.
            Check if the workload of 'cinder' has been upgraded on units: cinder/0
        Upgrade plan for 'az-1' to victoria
            Upgrade software packages of 'nova-compute' from the current APT repositories
                Upgrade software packages on unit nova-compute/1
            Refresh 'nova-compute' to the latest revision of 'ussuri/stable'
            Change charm config of 'nova-compute' 'action-managed-upgrade' to True
            Upgrade 'nova-compute' to the new channel: 'victoria/stable'
            Change charm config of 'nova-compute' 'source' to 'cloud:focal-victoria'
            Upgrade plan for units: nova-compute/1
                Upgrade plan for unit: nova-compute/1
                    Disable nova-compute scheduler from unit: 'nova-compute/1'.
                    Check if unit nova-compute/1 has no VMs running before upgrading.
                    ├── Pause the unit: 'nova-compute/1'.
                    ├── Upgrade the unit: 'nova-compute/1'.
                    ├── Resume the unit: 'nova-compute/1'.
                    Enable nova-compute scheduler from unit: 'nova-compute/1'.
            Wait 1800s for model test_model to reach the idle state.
            Check if the workload of 'nova-compute' has been upgraded on units: nova-compute/1
        Upgrade plan for 'az-2' to victoria
            Upgrade software packages of 'nova-compute' from the current APT repositories
                Upgrade software packages on unit nova-compute/2
            Refresh 'nova-compute' to the latest revision of 'ussuri/stable'
            Change charm config of 'nova-compute' 'action-managed-upgrade' to True
            Upgrade 'nova-compute' to the new channel: 'victoria/stable'
            Change charm config of 'nova-compute' 'source' to 'cloud:focal-victoria'
            Upgrade plan for units: nova-compute/2
                Upgrade plan for unit: nova-compute/2
                    Disable nova-compute scheduler from unit: 'nova-compute/2'.
                    Check if unit nova-compute/2 has no VMs running before upgrading.
                    ├── Pause the unit: 'nova-compute/2'.
                    ├── Upgrade the unit: 'nova-compute/2'.
                    ├── Resume the unit: 'nova-compute/2'.
                    Enable nova-compute scheduler from unit: 'nova-compute/2'.
            Wait 1800s for model test_model to reach the idle state.
            Check if the workload of 'nova-compute' has been upgraded on units: nova-compute/2
    """
    )
    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
    cinder = OpenStackApplication(
        name="cinder",
        can_upgrade_to="ussuri/stable",
        charm="cinder",
        channel="ussuri/stable",
        config={
            "openstack-origin": {"value": "distro"},
            "action-managed-upgrade": {"value": False},
        },
        machines={"0": machines["0"]},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "cinder/0": COUUnit(
                name="cinder/0",
                workload_version="16.4.2",
                machine=machines["0"],
            )
        },
        workload_version="16.4.2",
    )
    nova_compute = NovaCompute(
        name="nova-compute",
        can_upgrade_to="ussuri/stable",
        charm="nova-compute",
        channel="ussuri/stable",
        config={"source": {"value": "distro"}, "action-managed-upgrade": {"value": False}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"nova-compute/{unit}": COUUnit(
                name=f"nova-compute/{unit}",
                workload_version="21.0.0",
                machine=machines[f"{unit}"],
            )
            for unit in range(3)
        },
        workload_version="21.0.0",
    )

    planner = HypervisorUpgradePlanner([cinder, nova_compute], list(machines.values()))
    plan = planner.generate_upgrade_plan(target, False)

    assert str(plan) == exp_plan


def test_hypervisor_upgrade_plan_single_machine(model):
    """Testing generating hypervisors upgrade plan for just a single machine.

    This test simulate the plan generation if the user uses cou plan hypervisors --machine 0
    """
    target = OpenStackRelease("victoria")
    exp_plan = dedent_plan(
        """
    Upgrading all applications deployed on machines with hypervisor.
        Upgrade plan for 'az-0' to victoria
            Upgrade software packages of 'cinder' from the current APT repositories
                Upgrade software packages on unit cinder/0
            Refresh 'cinder' to the latest revision of 'ussuri/stable'
            Upgrade software packages of 'nova-compute' from the current APT repositories
                Upgrade software packages on unit nova-compute/0
            Refresh 'nova-compute' to the latest revision of 'ussuri/stable'
            Change charm config of 'cinder' 'action-managed-upgrade' to True
            Upgrade 'cinder' to the new channel: 'victoria/stable'
            Change charm config of 'cinder' 'openstack-origin' to 'cloud:focal-victoria'
            Change charm config of 'nova-compute' 'action-managed-upgrade' to True
            Upgrade 'nova-compute' to the new channel: 'victoria/stable'
            Change charm config of 'nova-compute' 'source' to 'cloud:focal-victoria'
            Upgrade plan for units: nova-compute/0
                Upgrade plan for unit: nova-compute/0
                    Disable nova-compute scheduler from unit: 'nova-compute/0'.
                    Check if unit nova-compute/0 has no VMs running before upgrading.
                    ├── Pause the unit: 'nova-compute/0'.
                    ├── Upgrade the unit: 'nova-compute/0'.
                    ├── Resume the unit: 'nova-compute/0'.
                    Enable nova-compute scheduler from unit: 'nova-compute/0'.
            Wait 1800s for model test_model to reach the idle state.
            Check if the workload of 'nova-compute' has been upgraded on units: nova-compute/0
            Wait 300s for app cinder to reach the idle state.
            Check if the workload of 'cinder' has been upgraded on units: cinder/0
    """
    )
    machines = {f"{i}": generate_cou_machine(f"{i}", f"az-{i}") for i in range(3)}
    cinder = OpenStackApplication(
        name="cinder",
        can_upgrade_to="ussuri/stable",
        charm="cinder",
        channel="ussuri/stable",
        config={
            "openstack-origin": {"value": "distro"},
            "action-managed-upgrade": {"value": False},
        },
        machines={"0": machines["0"]},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            "cinder/0": COUUnit(
                name="cinder/0",
                workload_version="16.4.2",
                machine=machines["0"],
            )
        },
        workload_version="16.4.2",
    )
    nova_compute = NovaCompute(
        name="nova-compute",
        can_upgrade_to="ussuri/stable",
        charm="nova-compute",
        channel="ussuri/stable",
        config={"source": {"value": "distro"}, "action-managed-upgrade": {"value": False}},
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        units={
            f"nova-compute/{unit}": COUUnit(
                name=f"nova-compute/{unit}",
                workload_version="21.0.0",
                machine=machines[f"{unit}"],
            )
            for unit in range(3)
        },
        workload_version="21.0.0",
    )

    planner = HypervisorUpgradePlanner([cinder, nova_compute], [machines["0"]])
    plan = planner.generate_upgrade_plan(target, False)

    assert str(plan) == exp_plan
