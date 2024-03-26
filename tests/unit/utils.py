# Copyright 2023 Canonical Limited
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
"""Module to provide helper for writing unit tests."""
from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock

import yaml
from juju.client.client import FullStatus

from cou.apps.base import OpenStackApplication
from cou.steps import BaseStep
from cou.utils.juju_utils import Application, Machine, Model, Unit


def assert_steps(step_1: BaseStep, step_2: BaseStep) -> None:
    """Compare two steps and raise exception if they are different."""
    msg = f"\n{step_1}!=\n{step_2}"
    assert step_1 == step_2, msg


def generate_cou_machine(machine_id: str, az: str | None = None) -> MagicMock:
    machine = MagicMock(spec_set=Machine)()
    machine.machine_id = machine_id
    machine.az = az
    machine.apps = tuple()
    return machine


def dedent_plan(plan: str) -> str:
    """Dedent the string plan."""
    result = dedent(plan)
    result = result.replace("    ", "\t")  # replace 4 spaces with tap
    return result


def get_status():
    """Help function to load Juju status from json file."""
    current_path = Path(__file__).parent.resolve()
    with open(current_path / "jujustatus.json", "r") as file:
        status = file.read().rstrip()

    return FullStatus.from_json(status)


async def get_charm_name(value: str):
    """Help function to get charm name."""
    return value


def get_sample_plan(
    model: Model, source: Path
) -> tuple[dict[str, OpenStackApplication], str, Path]:
    """Help function to get dict of Applications and expected upgrade plan from file.

    This function can load applications from yaml format, where each app is string representation
    of OpenStackApplication (str(OpenStackApplication), see OpenStackApplication.__str__).

    applications:
      <app_1_name>:
        model_name: ...
        can_upgrade_to: ...
        ...
      <app_1_name>:
        model_name: ...
        can_upgrade_to: ...
        ...
    plan: |
      ...
    """
    with open(source, "r") as file:
        data = yaml.load(file, Loader=yaml.Loader)

    # Note(rgildein): We need to get machines first, since they are used in Unit object.
    machines = {
        machine_id: Machine(machine["id"], machine["apps"], machine["az"])
        for app_data in data["applications"].values()
        for machine_id, machine in app_data["machines"].items()
    }

    return (
        {
            name: Application(
                name=name,
                can_upgrade_to=app_data["can_upgrade_to"],
                charm=app_data["charm"],
                channel=app_data["channel"],
                config=app_data["config"],
                machines={machine_id: machines[machine_id] for machine_id in app_data["machines"]},
                model=model,
                origin=app_data["origin"],
                series=app_data["series"],
                subordinate_to=app_data["subordinate_to"],
                units={
                    name: Unit(name, machines[unit["machine"]], unit["workload_version"])
                    for name, unit in app_data["units"].items()
                },
                workload_version=app_data["workload_version"],
            )
            for name, app_data in data["applications"].items()
        },
        dedent_plan(data["plan"]),
        source,
    )
