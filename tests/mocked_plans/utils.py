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
"""Module to provide helper functions for writing mock upgrade tests."""
from pathlib import Path
from unittest.mock import AsyncMock, PropertyMock

import yaml

from cou.utils.juju_utils import Application, Machine, Model, Unit
from tests.unit.utils import dedent_plan


def get_sample_plan(source: Path) -> tuple[str, Model, str]:
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

    model = AsyncMock(spec_set=Model)

    # Note(rgildein): We need to get machines first, since they are used in Unit object.
    machines = {
        machine_id: Machine(machine["id"], machine["apps"], machine["az"])
        for app_data in data["applications"].values()
        for machine_id, machine in app_data["machines"].items()
    }
    applications = {
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
    }

    type(model).name = PropertyMock(return_value=source.stem)
    model.get_applications = AsyncMock(return_value=applications)

    return source.name, model, dedent_plan(data["plan"])


def sample_plans() -> list[tuple[str, Model, str]]:
    """Return all sample plans in a directory.

    This function return a list of tuples consisting of the filename, a cou.utils.juju_utils.Model
    object and the expected plan in string format as the value. The get_applications function of
    this Model object returns the applications read from a YAML file, from which the expected plan
    is also parsed.
    """
    directory = Path(__file__).parent / "sample_plans"

    return [get_sample_plan(sample_file) for sample_file in directory.glob("*.yaml")]
