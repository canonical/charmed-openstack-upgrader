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
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from juju.client.client import FullStatus

from cou.commands import CLIargs


def get_status():
    """Help function to load Juju status from json file."""
    current_path = Path(__file__).parent.resolve()
    with open(current_path / "jujustatus.json", "r") as file:
        status = file.read().rstrip()

    return FullStatus.from_json(status)


async def get_charm_name(value: str):
    """Help function to get charm name."""
    return value


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
