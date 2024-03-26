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

from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from cou.commands import CLIargs
from cou.steps.analyze import Analysis
from tests.unit.utils import get_charm_name, get_sample_plan, get_status


@pytest.fixture
def model():
    """Define test Model object."""
    model_name = "test_model"
    from cou.utils import juju_utils

    model = AsyncMock(spec_set=juju_utils.Model)
    type(model).name = PropertyMock(return_value=model_name)
    model.run_on_unit = AsyncMock()
    model.run_action = AsyncMock()
    model.get_charm_name = AsyncMock()
    model.get_status = AsyncMock(side_effect=get_status)
    model.get_charm_name = AsyncMock(side_effect=get_charm_name)
    model.scp_from_unit = AsyncMock()
    model.set_application_config = AsyncMock()
    model.get_application_config = AsyncMock()

    return model


@pytest.fixture(scope="session", autouse=True)
def cou_data(tmp_path_factory):
    cou_test = tmp_path_factory.mktemp("cou_test")
    with patch("cou.utils.COU_DATA", cou_test):
        yield


@pytest.fixture
def cli_args() -> MagicMock:
    """Magic Mock of the COU CLIargs.

    :return: MagicMock of the COU CLIargs got from the cli.
    :rtype: MagicMock
    """
    # spec_set needs an instantiated class to be strict with the fields.
    return MagicMock(spec_set=CLIargs(command="plan"))()


@pytest.fixture
def sample_plans(model) -> Generator[tuple[Analysis, str], None, None]:
    """Fixture that returns all sample plans in a directory."""
    directory = Path(__file__).parent / "sample_plans"
    sample_plans = [
        get_sample_plan(model, sample_file) for sample_file in directory.glob("*.yaml")
    ]
    model.get_applications = AsyncMock(side_effect=[apps for apps, _, _ in sample_plans])
    return [(Analysis.create(model), exp_plan, file) for _, exp_plan, file in sample_plans]
