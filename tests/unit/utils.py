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
from textwrap import dedent
from unittest.mock import MagicMock

from cou.steps import BaseStep
from cou.utils.juju_utils import Machine


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
