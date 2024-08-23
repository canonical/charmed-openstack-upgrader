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

from unittest.mock import AsyncMock, MagicMock, call, patch

from cou.apps.base import OpenStackApplication
from cou.apps.core import NovaCompute
from cou.steps import (
    HypervisorUpgradePlan,
    PostUpgradeStep,
    PreUpgradeStep,
    UpgradeStep,
)
from cou.steps.hypervisor import AZs, HypervisorGroup, HypervisorUpgradePlanner
from cou.utils.juju_utils import Application, Machine, SubordinateUnit, Unit
from cou.utils.openstack import OpenStackRelease
from tests.unit.utils import dedent_plan, generate_cou_machine


def _generate_app(name: str) -> MagicMock:
    app = MagicMock(spec_set=OpenStackApplication)()
    app.name = name
    app.upgrade_plan_sanity_checks = MagicMock()
    app.pre_upgrade_steps.return_value = [PreUpgradeStep(f"{name}-pre-upgrade", coro=AsyncMock())]
    app.upgrade_steps.return_value = [UpgradeStep(f"{name}-upgrade", coro=AsyncMock())]
    app.post_upgrade_steps.return_value = [
        PostUpgradeStep(f"{name}-post-upgrade", coro=AsyncMock())
    ]
    return app


def test_upgrade_plan_sanity_checks():
    """Test run app sanity checks."""
    target = OpenStackRelease("victoria")
    machines = [Machine(f"{i}", (), f"az{i}") for i in range(3)]
    app_units = {
        "app1": [Unit(f"app1/{i}", machines[i], "1") for i in range(3)],
        "app2": [Unit(f"app2/{i}", machines[i], "1") for i in range(3)],
    }
    apps = [_generate_app("app1"), _generate_app("app2"), _generate_app("app3")]
    # Note(rgildein): it contains only two apps, so app3 should be skipped
    group = HypervisorGroup("test", app_units)
    planner = HypervisorUpgradePlanner(apps, machines)

    planner._upgrade_plan_sanity_checks(target, group)

    apps[0].upgrade_plan_sanity_checks.assert_called_once_with(target, app_units["app1"])
    apps[1].upgrade_plan_sanity_checks.assert_called_once_with(target, app_units["app2"])
    apps[2].upgrade_plan_sanity_checks.assert_not_called()


def test_generate_pre_upgrade_steps():
    """Test generating of pre-upgrade steps."""
    target = OpenStackRelease("victoria")
    machines = [Machine(f"{i}", (), f"az{i}") for i in range(3)]
    app_units = {
        "app1": [Unit(f"app1/{i}", machines[i], "1") for i in range(3)],
        "app2": [Unit(f"app2/{i}", machines[i], "1") for i in range(3)],
    }
    apps = [_generate_app("app1"), _generate_app("app2"), _generate_app("app3")]
    exp_steps = apps[0].pre_upgrade_steps.return_value + apps[1].pre_upgrade_steps.return_value
    # Note(rgildein): it contains only two apps, so app3 should be skipped
    group = HypervisorGroup("test", app_units)
    planner = HypervisorUpgradePlanner(apps, machines)

    steps = planner._generate_pre_upgrade_steps(target, group)

    apps[0].pre_upgrade_steps.assert_called_once_with(target, app_units["app1"])
    apps[1].pre_upgrade_steps.assert_called_once_with(target, app_units["app2"])
    apps[2].pre_upgrade_steps.assert_not_called()

    assert steps == exp_steps


def test_generate_upgrade_steps():
    """Test generating of upgrade steps."""
    target = OpenStackRelease("victoria")
    machines = [Machine(f"{i}", (), f"az{i}") for i in range(3)]
    app_units = {
        "app1": [Unit(f"app1/{i}", machines[i], "1") for i in range(3)],
        "app2": [Unit(f"app2/{i}", machines[i], "1") for i in range(3)],
    }
    apps = [_generate_app("app1"), _generate_app("app2"), _generate_app("app3")]
    exp_steps = apps[0].upgrade_steps.return_value + apps[1].upgrade_steps.return_value
    # Note(rgildein): it contains only two apps, so app3 should be skipped
    group = HypervisorGroup("test", app_units)
    planner = HypervisorUpgradePlanner(apps, machines)

    steps = planner._generate_upgrade_steps(target, False, group)

    apps[0].upgrade_steps.assert_called_once_with(target, app_units["app1"], False)
    apps[1].upgrade_steps.assert_called_once_with(target, app_units["app2"], False)
    apps[2].upgrade_steps.assert_not_called()

    assert steps == exp_steps


def test_generate_post_upgrade_steps():
    """Test generating of post-upgrade steps."""
    target = OpenStackRelease("victoria")
    machines = [Machine(f"{i}", (), f"az{i}") for i in range(3)]
    app_units = {
        "app1": [Unit(f"app1/{i}", machines[i], "1") for i in range(3)],
        "app2": [Unit(f"app2/{i}", machines[i], "1") for i in range(3)],
    }
    apps = [_generate_app("app1"), _generate_app("app2"), _generate_app("app3")]
    exp_steps = apps[0].post_upgrade_steps.return_value + apps[1].post_upgrade_steps.return_value
    # Note(rgildein): it contains only two apps, so app3 should be skipped
    group = HypervisorGroup("test", app_units)
    planner = HypervisorUpgradePlanner(apps, machines)

    steps = planner._generate_post_upgrade_steps(target, group)

    apps[0].post_upgrade_steps.assert_called_once_with(target, units=app_units["app1"])
    apps[1].post_upgrade_steps.assert_called_once_with(target, units=app_units["app2"])
    apps[2].post_upgrade_steps.assert_not_called()

    assert steps == exp_steps


@patch("cou.steps.hypervisor.HypervisorUpgradePlanner.get_azs")
@patch("cou.steps.hypervisor.HypervisorUpgradePlanner._upgrade_plan_sanity_checks")
@patch("cou.steps.hypervisor.HypervisorUpgradePlanner._generate_pre_upgrade_steps")
@patch("cou.steps.hypervisor.HypervisorUpgradePlanner._generate_upgrade_steps")
@patch("cou.steps.hypervisor.HypervisorUpgradePlanner._generate_post_upgrade_steps")
def test_generate_upgrade_plan(
    post_upgrade_steps, upgrade_steps, pre_upgrade_steps, sanity_checks, get_azs
):
    """Test generating upgrade plan with hypervisors upgrade planer."""
    target = OpenStackRelease("victoria")
    group1 = MagicMock(spec_set=HypervisorGroup)()
    group2 = MagicMock(spec_set=HypervisorGroup)()
    get_azs.return_value = {"az0": group1, "az1": group2}
    # Note(rgildein): We need to define return value, because plan will not add empty steps.
    pre_upgrade_steps.return_value = [PreUpgradeStep("pre-upgrade", coro=AsyncMock())]
    upgrade_steps.return_value = [UpgradeStep("upgrade", coro=AsyncMock())]
    post_upgrade_steps.return_value = [PostUpgradeStep("post-upgrade", coro=AsyncMock())]

    # Note(rgildein): We do not need to provide apps or machines, since everything is mocked.
    planner = HypervisorUpgradePlanner([], [])

    plan = planner.generate_upgrade_plan(target, False)

    sanity_checks.assert_has_calls([call(target, group1), call(target, group2)])
    pre_upgrade_steps.assert_has_calls([call(target, group1), call(target, group2)])
    upgrade_steps.assert_has_calls([call(target, False, group1), call(target, False, group2)])
    post_upgrade_steps.assert_has_calls([call(target, group1), call(target, group2)])

    assert plan.description == "Upgrading all applications deployed on machines with hypervisor."
    assert len(plan.sub_steps) == 2
    assert isinstance(plan.sub_steps[0], HypervisorUpgradePlan)
    assert plan.sub_steps[0].description == f"Upgrade plan for [] in '{group1.name}' to '{target}'"
    assert (
        plan.sub_steps[0].sub_steps
        == pre_upgrade_steps.return_value
        + upgrade_steps.return_value
        + post_upgrade_steps.return_value
    )


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
    test_unit = Unit("my-unit", MagicMock(spec_set=Machine)(), "")

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
    target = OpenStackRelease("victoria")
    machines = {f"{i}": Machine(f"{i}", (), f"az{i // 2}") for i in range(6)}
    units = {
        # app1
        "app1/0": Unit("app1/0", machines["0"], ""),
        "app1/1": Unit("app1/1", machines["1"], ""),
        "app1/2": Unit("app1/2", machines["2"], ""),
        "app1/3": Unit("app1/3", machines["3"], ""),
        "app1/4": Unit("app1/4", machines["4"], ""),
        "app1/5": Unit("app1/5", machines["5"], ""),
        # app2
        "app2/0": Unit("app2/0", machines["0"], ""),
        "app2/1": Unit("app2/1", machines["2"], ""),
        "app2/2": Unit("app2/2", machines["4"], ""),
    }

    app1 = MagicMock(spec_set=Application)()
    app1.name = "app1"
    app1.units = {name: unit for name, unit in units.items() if name.startswith("app1")}
    app1.get_latest_o7k_version.return_value = OpenStackRelease("ussuri")

    app2 = MagicMock(spec_set=Application)()
    app2.name = "app2"
    app2.units = {name: unit for name, unit in units.items() if name.startswith("app2")}
    app2.get_latest_o7k_version.return_value = OpenStackRelease("ussuri")

    # passing all machines to the HypervisorUpgradePlanner
    exp_azs_all = AZs()
    exp_azs_all["az0"].app_units["app1"] = [units["app1/0"], units["app1/1"]]
    exp_azs_all["az0"].app_units["app2"] = [units["app2/0"]]
    exp_azs_all["az1"].app_units["app1"] = [units["app1/2"], units["app1/3"]]
    exp_azs_all["az1"].app_units["app2"] = [units["app2/1"]]
    exp_azs_all["az2"].app_units["app1"] = [units["app1/4"], units["app1/5"]]
    exp_azs_all["az2"].app_units["app2"] = [units["app2/2"]]

    hypervisor_planner_all = HypervisorUpgradePlanner([app1, app2], list(machines.values()))

    assert dict(hypervisor_planner_all.get_azs(target)) == exp_azs_all

    # passing machine 0 to the HypervisorUpgradePlanner
    exp_azs_0 = AZs()
    exp_azs_0["az0"].app_units["app1"] = [units["app1/0"]]
    exp_azs_0["az0"].app_units["app2"] = [units["app2/0"]]

    hypervisor_planner_machine_0 = HypervisorUpgradePlanner([app1, app2], [machines["0"]])
    assert dict(hypervisor_planner_machine_0.get_azs(target)) == exp_azs_0

    # passing machine 1 to the HypervisorUpgradePlanner
    exp_azs_1 = AZs()
    exp_azs_1["az0"].app_units["app1"] = [units["app1/1"]]

    hypervisor_planner_machine_1 = HypervisorUpgradePlanner([app1, app2], [machines["1"]])
    assert dict(hypervisor_planner_machine_1.get_azs(target)) == exp_azs_1


def test_hypervisor_azs_grouping_units_different_o7k_release():
    """Test HypervisorUpgradePlanner azs grouping.

    This should return 2 AZs because az0 already got upgraded.

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
    target = OpenStackRelease("victoria")
    machines = {f"{i}": Machine(f"{i}", (), f"az{i // 2}") for i in range(6)}
    units = {
        # app1
        "app1/0": Unit("app1/0", machines["0"], ""),
        "app1/1": Unit("app1/1", machines["1"], ""),
        "app1/2": Unit("app1/2", machines["2"], ""),
        "app1/3": Unit("app1/3", machines["3"], ""),
        "app1/4": Unit("app1/4", machines["4"], ""),
        "app1/5": Unit("app1/5", machines["5"], ""),
        # app2
        "app2/0": Unit("app2/0", machines["0"], ""),
        "app2/1": Unit("app2/1", machines["2"], ""),
        "app2/2": Unit("app2/2", machines["4"], ""),
    }

    app1 = MagicMock(spec_set=Application)()
    app1.name = "app1"
    app1.units = {name: unit for name, unit in units.items() if name.startswith("app1")}

    def side_effect_app1(value):
        o7k_release = {
            "app1/0": OpenStackRelease("victoria"),
            "app1/1": OpenStackRelease("victoria"),
            "app1/2": OpenStackRelease("victoria"),
            "app1/3": OpenStackRelease("ussuri"),
            "app1/4": OpenStackRelease("ussuri"),
            "app1/5": OpenStackRelease("ussuri"),
        }
        return o7k_release[value.name]

    app1.get_latest_o7k_version.side_effect = side_effect_app1

    app2 = MagicMock(spec_set=Application)()
    app2.name = "app2"
    app2.units = {name: unit for name, unit in units.items() if name.startswith("app2")}

    def side_effect_app2(value):
        o7k_release = {
            "app2/0": OpenStackRelease("victoria"),
            "app2/1": OpenStackRelease("ussuri"),
            "app2/2": OpenStackRelease("ussuri"),
        }
        return o7k_release[value.name]

    app2.get_latest_o7k_version.side_effect = side_effect_app2

    # passing all machines to the HypervisorUpgradePlanner
    exp_azs_all = AZs()
    exp_azs_all["az1"].app_units["app1"] = [units["app1/3"]]
    exp_azs_all["az1"].app_units["app2"] = [units["app2/1"]]
    exp_azs_all["az2"].app_units["app1"] = [units["app1/4"], units["app1/5"]]
    exp_azs_all["az2"].app_units["app2"] = [units["app2/2"]]

    hypervisor_planner_all = HypervisorUpgradePlanner([app1, app2], list(machines.values()))

    assert dict(hypervisor_planner_all.get_azs(target)) == exp_azs_all

    # passing machine 0 to the HypervisorUpgradePlanner
    exp_azs_0 = AZs()

    hypervisor_planner_machine_0 = HypervisorUpgradePlanner([app1, app2], [machines["0"]])
    assert dict(hypervisor_planner_machine_0.get_azs(target)) == exp_azs_0

    # passing machine 1 to the HypervisorUpgradePlanner
    exp_azs_1 = AZs()

    hypervisor_planner_machine_1 = HypervisorUpgradePlanner([app1, app2], [machines["1"]])
    assert dict(hypervisor_planner_machine_1.get_azs(target)) == exp_azs_1


def test_hypervisor_upgrade_plan(model):
    """Testing generating hypervisors upgrade plan."""
    target = OpenStackRelease("victoria")
    exp_plan = dedent_plan(
        """\
    Upgrading all applications deployed on machines with hypervisor.
        Upgrade plan for [cinder/0, nova-compute/0] in 'az-0' to 'victoria'
            Upgrade software packages of 'cinder' from the current APT repositories
                Ψ Upgrade software packages on unit 'cinder/0'
            Refresh 'cinder' to the latest revision of 'ussuri/stable'
            Wait for up to 300s for app 'cinder' to reach the idle state
            Disable nova-compute scheduler from unit: 'nova-compute/0'
            Upgrade software packages of 'nova-compute' from the current APT repositories
                Ψ Upgrade software packages on unit 'nova-compute/0'
            Refresh 'nova-compute' to the latest revision of 'ussuri/stable'
            Wait for up to 2400s for model 'test_model' to reach the idle state
            Change charm config of 'cinder' 'action-managed-upgrade' from 'False' to 'True'
            Upgrade 'cinder' from 'ussuri/stable' to the new channel: 'victoria/stable'
            Wait for up to 300s for app 'cinder' to reach the idle state
            Change charm config of 'cinder' 'openstack-origin' to 'cloud:focal-victoria'
            Upgrade plan for units: cinder/0
                Ψ Upgrade plan for unit 'cinder/0'
                    Pause the unit: 'cinder/0'
                    Upgrade the unit: 'cinder/0'
                    Resume the unit: 'cinder/0'
            Change charm config of 'nova-compute' 'action-managed-upgrade' from 'False' to 'True'
            Upgrade 'nova-compute' from 'ussuri/stable' to the new channel: 'victoria/stable'
            Wait for up to 2400s for model 'test_model' to reach the idle state
            Change charm config of 'nova-compute' 'source' to 'cloud:focal-victoria'
            Upgrade plan for units: nova-compute/0
                Ψ Upgrade plan for unit 'nova-compute/0'
                    Verify that unit 'nova-compute/0' has no VMs running
                    ├── Pause the unit: 'nova-compute/0'
                    ├── Upgrade the unit: 'nova-compute/0'
                    ├── Resume the unit: 'nova-compute/0'
            Wait for up to 300s for app 'cinder' to reach the idle state
            Verify that the workload of 'cinder' has been upgraded on units: cinder/0
            Enable nova-compute scheduler from unit: 'nova-compute/0'
            Restart service ceilometer-agent-compute for subordinate unit: 'ceilometer-agent/0'
            Wait for up to 2400s for model 'test_model' to reach the idle state
            Verify that the workload of 'nova-compute' has been upgraded on units: nova-compute/0
        Upgrade plan for [nova-compute/1] in 'az-1' to 'victoria'
            Disable nova-compute scheduler from unit: 'nova-compute/1'
            Upgrade software packages of 'nova-compute' from the current APT repositories
                Ψ Upgrade software packages on unit 'nova-compute/1'
            Refresh 'nova-compute' to the latest revision of 'ussuri/stable'
            Wait for up to 2400s for model 'test_model' to reach the idle state
            Change charm config of 'nova-compute' 'action-managed-upgrade' from 'False' to 'True'
            Upgrade 'nova-compute' from 'ussuri/stable' to the new channel: 'victoria/stable'
            Wait for up to 2400s for model 'test_model' to reach the idle state
            Change charm config of 'nova-compute' 'source' to 'cloud:focal-victoria'
            Upgrade plan for units: nova-compute/1
                Ψ Upgrade plan for unit 'nova-compute/1'
                    Verify that unit 'nova-compute/1' has no VMs running
                    ├── Pause the unit: 'nova-compute/1'
                    ├── Upgrade the unit: 'nova-compute/1'
                    ├── Resume the unit: 'nova-compute/1'
            Enable nova-compute scheduler from unit: 'nova-compute/1'
            Restart service ceilometer-agent-compute for subordinate unit: 'ceilometer-agent/1'
            Wait for up to 2400s for model 'test_model' to reach the idle state
            Verify that the workload of 'nova-compute' has been upgraded on units: nova-compute/1
        Upgrade plan for [nova-compute/2] in 'az-2' to 'victoria'
            Disable nova-compute scheduler from unit: 'nova-compute/2'
            Upgrade software packages of 'nova-compute' from the current APT repositories
                Ψ Upgrade software packages on unit 'nova-compute/2'
            Refresh 'nova-compute' to the latest revision of 'ussuri/stable'
            Wait for up to 2400s for model 'test_model' to reach the idle state
            Change charm config of 'nova-compute' 'action-managed-upgrade' from 'False' to 'True'
            Upgrade 'nova-compute' from 'ussuri/stable' to the new channel: 'victoria/stable'
            Wait for up to 2400s for model 'test_model' to reach the idle state
            Change charm config of 'nova-compute' 'source' to 'cloud:focal-victoria'
            Upgrade plan for units: nova-compute/2
                Ψ Upgrade plan for unit 'nova-compute/2'
                    Verify that unit 'nova-compute/2' has no VMs running
                    ├── Pause the unit: 'nova-compute/2'
                    ├── Upgrade the unit: 'nova-compute/2'
                    ├── Resume the unit: 'nova-compute/2'
            Enable nova-compute scheduler from unit: 'nova-compute/2'
            Restart service ceilometer-agent-compute for subordinate unit: 'ceilometer-agent/2'
            Wait for up to 2400s for model 'test_model' to reach the idle state
            Verify that the workload of 'nova-compute' has been upgraded on units: nova-compute/2
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
        subordinate_units=[],
        units={
            "cinder/0": Unit(
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
        subordinate_units=[],
        units={
            f"nova-compute/{unit}": Unit(
                name=f"nova-compute/{unit}",
                workload_version="21.0.0",
                machine=machines[f"{unit}"],
                subordinates=[
                    SubordinateUnit(name=f"ceilometer-agent/{unit}", charm="ceilometer-agent")
                ],
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
        """\
    Upgrading all applications deployed on machines with hypervisor.
        Upgrade plan for [cinder/0, nova-compute/0] in 'az-0' to 'victoria'
            Upgrade software packages of 'cinder' from the current APT repositories
                Ψ Upgrade software packages on unit 'cinder/0'
            Refresh 'cinder' to the latest revision of 'ussuri/stable'
            Wait for up to 300s for app 'cinder' to reach the idle state
            Disable nova-compute scheduler from unit: 'nova-compute/0'
            Upgrade software packages of 'nova-compute' from the current APT repositories
                Ψ Upgrade software packages on unit 'nova-compute/0'
            Refresh 'nova-compute' to the latest revision of 'ussuri/stable'
            Wait for up to 2400s for model 'test_model' to reach the idle state
            Change charm config of 'cinder' 'action-managed-upgrade' from 'False' to 'True'
            Upgrade 'cinder' from 'ussuri/stable' to the new channel: 'victoria/stable'
            Wait for up to 300s for app 'cinder' to reach the idle state
            Change charm config of 'cinder' 'openstack-origin' to 'cloud:focal-victoria'
            Upgrade plan for units: cinder/0
                Ψ Upgrade plan for unit 'cinder/0'
                    Pause the unit: 'cinder/0'
                    Upgrade the unit: 'cinder/0'
                    Resume the unit: 'cinder/0'
            Change charm config of 'nova-compute' 'action-managed-upgrade' from 'False' to 'True'
            Upgrade 'nova-compute' from 'ussuri/stable' to the new channel: 'victoria/stable'
            Wait for up to 2400s for model 'test_model' to reach the idle state
            Change charm config of 'nova-compute' 'source' to 'cloud:focal-victoria'
            Upgrade plan for units: nova-compute/0
                Ψ Upgrade plan for unit 'nova-compute/0'
                    Verify that unit 'nova-compute/0' has no VMs running
                    ├── Pause the unit: 'nova-compute/0'
                    ├── Upgrade the unit: 'nova-compute/0'
                    ├── Resume the unit: 'nova-compute/0'
            Wait for up to 300s for app 'cinder' to reach the idle state
            Verify that the workload of 'cinder' has been upgraded on units: cinder/0
            Enable nova-compute scheduler from unit: 'nova-compute/0'
            Restart service ceilometer-agent-compute for subordinate unit: 'ceilometer-agent/0'
            Wait for up to 2400s for model 'test_model' to reach the idle state
            Verify that the workload of 'nova-compute' has been upgraded on units: nova-compute/0
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
        subordinate_units=[],
        units={
            "cinder/0": Unit(
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
        subordinate_units=[],
        units={
            f"nova-compute/{unit}": Unit(
                name=f"nova-compute/{unit}",
                workload_version="21.0.0",
                machine=machines[f"{unit}"],
                subordinates=[
                    SubordinateUnit(name=f"ceilometer-agent/{unit}", charm="ceilometer-agent"),
                ],
            )
            for unit in range(3)
        },
        workload_version="21.0.0",
    )

    planner = HypervisorUpgradePlanner([cinder, nova_compute], [machines["0"]])
    plan = planner.generate_upgrade_plan(target, False)

    assert str(plan) == exp_plan


def test_hypervisor_upgrade_plan_some_units_upgraded(model):
    """Testing generating hypervisors upgrade plan partially upgraded."""
    target = OpenStackRelease("victoria")
    exp_plan = dedent_plan(
        """\
    Upgrading all applications deployed on machines with hypervisor.
        Upgrade plan for [cinder/1] in 'az-1' to 'victoria'
            Upgrade software packages of 'cinder' from the current APT repositories
                Ψ Upgrade software packages on unit 'cinder/1'
            Upgrade plan for units: cinder/1
                Ψ Upgrade plan for unit 'cinder/1'
                    Pause the unit: 'cinder/1'
                    Upgrade the unit: 'cinder/1'
                    Resume the unit: 'cinder/1'
            Wait for up to 300s for app 'cinder' to reach the idle state
            Verify that the workload of 'cinder' has been upgraded on units: cinder/1
        Upgrade plan for [cinder/2, nova-compute/2] in 'az-2' to 'victoria'
            Upgrade software packages of 'cinder' from the current APT repositories
                Ψ Upgrade software packages on unit 'cinder/2'
            Disable nova-compute scheduler from unit: 'nova-compute/2'
            Upgrade software packages of 'nova-compute' from the current APT repositories
                Ψ Upgrade software packages on unit 'nova-compute/2'
            Upgrade plan for units: cinder/2
                Ψ Upgrade plan for unit 'cinder/2'
                    Pause the unit: 'cinder/2'
                    Upgrade the unit: 'cinder/2'
                    Resume the unit: 'cinder/2'
            Upgrade plan for units: nova-compute/2
                Ψ Upgrade plan for unit 'nova-compute/2'
                    Verify that unit 'nova-compute/2' has no VMs running
                    ├── Pause the unit: 'nova-compute/2'
                    ├── Upgrade the unit: 'nova-compute/2'
                    ├── Resume the unit: 'nova-compute/2'
            Wait for up to 300s for app 'cinder' to reach the idle state
            Verify that the workload of 'cinder' has been upgraded on units: cinder/2
            Enable nova-compute scheduler from unit: 'nova-compute/2'
            Restart service ceilometer-agent-compute for subordinate unit: 'ceilometer-agent/2'
            Wait for up to 2400s for model 'test_model' to reach the idle state
            Verify that the workload of 'nova-compute' has been upgraded on units: nova-compute/2
    """
    )
    machines = {
        f"{i}": generate_cou_machine(f"{i}", f"az-{i}", ("nova-compute", "cinder"))
        for i in range(3)
    }
    # cinder/0 already upgraded
    cinder = OpenStackApplication(
        name="cinder",
        can_upgrade_to="",
        charm="cinder",
        channel="victoria/stable",
        config={
            "openstack-origin": {"value": "cloud:focal-victoria"},
            "action-managed-upgrade": {"value": True},
        },
        machines={"0": machines["0"]},
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        subordinate_units=[],
        units={
            "cinder/0": Unit(
                name="cinder/0",
                workload_version="17.4.2",
                machine=machines["0"],
            ),
            "cinder/1": Unit(
                name="cinder/1",
                workload_version="16.4.2",
                machine=machines["1"],
            ),
            "cinder/2": Unit(
                name="cinder/2",
                workload_version="16.4.2",
                machine=machines["2"],
            ),
        },
        workload_version="17.4.2",
    )
    # nova-compute/0 and nova-compute/1 already upgraded
    nova_compute = NovaCompute(
        name="nova-compute",
        can_upgrade_to="",
        charm="nova-compute",
        channel="victoria/stable",
        config={
            "openstack-origin": {"value": "cloud:focal-victoria"},
            "action-managed-upgrade": {"value": True},
        },
        machines=machines,
        model=model,
        origin="ch",
        series="focal",
        subordinate_to=[],
        subordinate_units=[],
        units={
            "nova-compute/0": Unit(
                name="nova-compute/0",
                workload_version="22.0.0",
                machine=machines["0"],
                subordinates=[
                    SubordinateUnit(name="ceilometer-agent/0", charm="ceilometer-agent")
                ],
            ),
            "nova-compute/1": Unit(
                name="nova-compute/1",
                workload_version="22.0.0",
                machine=machines["1"],
                subordinates=[
                    SubordinateUnit(name="ceilometer-agent/1", charm="ceilometer-agent")
                ],
            ),
            "nova-compute/2": Unit(
                name="nova-compute/2",
                workload_version="21.0.0",
                machine=machines["2"],
                subordinates=[
                    SubordinateUnit(name="ceilometer-agent/2", charm="ceilometer-agent")
                ],
            ),
        },
        workload_version="22.0.0",
    )

    planner = HypervisorUpgradePlanner([cinder, nova_compute], list(machines.values()))
    plan = planner.generate_upgrade_plan(target, False)

    assert str(plan) == exp_plan
