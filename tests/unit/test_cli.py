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

from argparse import ArgumentError
from unittest.mock import MagicMock, call, patch

import pytest

from cou.cli import entrypoint, parse_args, setup_logging
from cou.exceptions import COUException, UnitNotFound
from cou.steps import UpgradeStep


@pytest.mark.parametrize(
    "args, expected_run, expected_loglevel, expected_interactive",
    [
        (["--run", "--log-level", "DEBUG", "--no-interactive"], True, "DEBUG", False),
        (["--run", "--log-level", "warning"], True, "WARNING", True),
        (["--log-level", "debug"], False, "DEBUG", True),
    ],
)
def test_parse_args(args, expected_run, expected_loglevel, expected_interactive):
    parsed_args = parse_args(args)
    assert parsed_args.run == expected_run
    assert parsed_args.loglevel == expected_loglevel
    assert parsed_args.interactive == expected_interactive


@pytest.mark.parametrize(
    "args, exception", [(["--log-level=DDD"], ArgumentError), (["--foo"], SystemExit)]
)
def test_parse_args_raise_exception(args, exception):
    with pytest.raises(exception):
        parse_args(args)


def test_setup_logging():
    with patch("cou.cli.logging") as mock_logging:
        log_file_handler = MagicMock()
        console_handler = MagicMock()
        mock_root_logger = mock_logging.getLogger.return_value
        mock_logging.FileHandler.return_value = log_file_handler
        mock_logging.StreamHandler.return_value = console_handler
        setup_logging("INFO")
        mock_root_logger.addHandler.assert_any_call(log_file_handler)
        mock_root_logger.addHandler.assert_any_call(console_handler)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception, exp_exitcode",
    [
        (Exception("An error occurred"), "2"),
        (COUException("Caught error"), "1"),
        (UnitNotFound("Unit not found"), "1"),
    ],
)
async def test_entrypoint_with_exception(mocker, exception, exp_exitcode):
    mocker.patch("cou.cli.parse_args")
    mocker.patch("cou.cli.setup_logging")
    mocker.patch("cou.utils.juju_utils.COUModel.check_model_name", side_effect=exception)

    with pytest.raises(SystemExit, match=exp_exitcode):
        await entrypoint()


@pytest.mark.asyncio
async def test_entrypoint_dry_run(mocker):
    plan = UpgradeStep(description="Top level plan", parallel=False, function=None)
    plan.add_step(UpgradeStep(description="backup mysql databases", parallel=False, function=None))

    mock_parse_args = mocker.patch("cou.cli.parse_args")
    mock_parse_args.return_value.run = False
    mocker.patch("cou.cli.setup_logging")
    mocker.patch("cou.utils.juju_utils.COUModel.check_model_name")
    mock_analysis_create = mocker.patch("cou.cli.Analysis.create")
    mocker.patch("cou.cli.generate_plan", return_value=plan)
    mock_apply_plan = mocker.patch("cou.cli.apply_plan")
    mock_print = mocker.patch("builtins.print")

    await entrypoint()
    mock_print.assert_has_calls([call(mock_analysis_create.return_value), call(plan)])
    mock_apply_plan.assert_not_called()


@pytest.mark.asyncio
async def test_entrypoint_real_run(mocker):
    plan = UpgradeStep(description="Top level plan", parallel=False, function=None)
    plan.add_step(UpgradeStep(description="backup mysql databases", parallel=False, function=None))

    mock_parse_args = mocker.patch("cou.cli.parse_args")
    mock_parse_args.return_value.run = True
    mocker.patch("cou.cli.setup_logging")
    mocker.patch("cou.utils.juju_utils.COUModel.check_model_name")
    mock_analysis_create = mocker.patch("cou.cli.Analysis.create")
    mocker.patch("cou.cli.generate_plan", return_value=plan)
    mock_apply_plan = mocker.patch("cou.cli.apply_plan")
    mock_print = mocker.patch("builtins.print")

    await entrypoint()
    mock_print.assert_called_once_with(mock_analysis_create.return_value)
    mock_apply_plan.assert_called_once_with(plan, mock_parse_args.return_value.interactive)
