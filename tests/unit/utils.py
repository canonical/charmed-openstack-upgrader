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

from juju.client.client import FullStatus

from cou.steps import BaseStep
from cou.utils.juju_utils import Application, Machine, Unit


def assert_steps(step_1: BaseStep, step_2: BaseStep) -> None:
    """Compare two steps and raise exception if they are different."""
    msg = f"\n{step_1}!=\n{step_2}"
    assert step_1 == step_2, msg


def generate_cou_machine(
    machine_id: str, az: str | None = None, apps_charms: tuple = tuple(tuple())
) -> MagicMock:
    machine = MagicMock(spec_set=Machine)()
    machine.machine_id = machine_id
    machine.az = az
    machine.apps_charms = apps_charms
    return machine


def dedent_plan(plan: str) -> str:
    """Dedent the string plan."""
    result = dedent(plan)
    result = result.replace("    ", "\t")  # replace 4 spaces with tap
    return result


def get_applications(
    charm_name: str, app_count: int = 1, unit_count: int = 1
) -> list[Application]:
    """Get mocked applications."""
    apps = []
    for i in range(app_count):
        app = MagicMock(spec_set=Application)()
        app.name = f"{charm_name}-{i}"
        app.charm = charm_name
        app.config = {}
        units = {}
        for j in range(unit_count):
            unit = MagicMock(spec_set=Unit)()
            unit.name = f"{charm_name}-{i}/{j}"
            units[unit.name] = unit
        app.units = units
        apps.append(app)
    return apps


def get_status():
    """Help function to load Juju status from json file."""
    current_path = Path(__file__).parent.resolve()
    with open(current_path / "jujustatus.json", "r") as file:
        status = file.read().rstrip()

    return FullStatus.from_json(status)


async def get_charm_name(value: str):
    """Help function to get charm name."""
    return value
