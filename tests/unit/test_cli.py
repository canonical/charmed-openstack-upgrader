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
from unittest.mock import MagicMock, patch

import pytest

from cou.cli import entrypoint, parse_args, setup_logging
from cou.steps import UpgradeStep


@pytest.mark.parametrize(
    "args, expected_run, expected_loglevel, expected_non_interactive",
    [
        (["--run", "--log-level", "DEBUG", "--non-interactive"], True, "DEBUG", True),
        (["--run", "--log-level", "warning"], True, "WARNING", False),
        (["--log-level", "debug"], False, "DEBUG", False),
    ],
)
def test_parse_args(args, expected_run, expected_loglevel, expected_non_interactive):
    parsed_args = parse_args(args)
    assert parsed_args.run == expected_run
    assert parsed_args.loglevel == expected_loglevel
    assert parsed_args.non_interactive == expected_non_interactive


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
async def test_entrypoint_with_exception():
    with patch("cou.cli.parse_args"), patch("cou.cli.setup_logging"), patch(
        "cou.cli.generate_plan"
    ) as mock_generate_plan, patch("cou.steps.execute.SerialExecutor.execute"), patch(
        "cou.cli.Analysis.create"
    ):
        mock_generate_plan.side_effect = Exception("An error occurred")

        with pytest.raises(SystemExit) as exitcode:
            result = await entrypoint()
            assert exitcode.value == 1
            assert not result
        mock_generate_plan.assert_called_once()


@pytest.mark.asyncio
async def test_entrypoint_dry_run(mocker):
    plan = UpgradeStep(description="Top level plan", parallel=False, function=None)
    plan.add_step(UpgradeStep(description="backup mysql databases", parallel=False, function=None))

    mock_parse_args = mocker.patch("cou.cli.parse_args")
    mock_parse_args.return_value.run = False
    mocker.patch("cou.cli.setup_logging")
    mocker.patch("cou.cli.generate_plan", return_value=plan)
    mock_apply_plan = mocker.patch("cou.steps.execute.SerialExecutor.execute")
    mocker.patch("cou.cli.Analysis.create")
    mock_print = mocker.patch("builtins.print")

    result = await entrypoint()
    mock_print.assert_called_with(plan)
    mock_apply_plan.assert_not_called()

    assert not result


@pytest.mark.asyncio
async def test_entrypoint_real_run():
    with patch("cou.cli.parse_args") as mock_parse_args, patch("cou.cli.setup_logging"), patch(
        "cou.cli.generate_plan"
    ), patch("cou.steps.execute.SerialExecutor.execute") as mock_apply_plan, patch(
        "cou.cli.Analysis.create"
    ):
        mock_parse_args.return_value = MagicMock()
        mock_parse_args.return_value.run = True

        result = await entrypoint()

        assert not result
        mock_apply_plan.assert_called_once()
