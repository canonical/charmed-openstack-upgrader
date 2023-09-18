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

import argparse
from unittest.mock import AsyncMock, patch

import pytest

from cou import cli
from cou.exceptions import COUException, UnitNotFound
from cou.steps import UpgradeStep
from cou.steps.analyze import Analysis


@pytest.mark.parametrize(
    "verbosity_value, verbosity_name",
    [
        (0, "ERROR"),
        (1, "WARNING"),
        (2, "INFO"),
        (3, "DEBUG"),
        (4, "NOTSET"),
        (5, "NOTSET"),
        (10, "NOTSET"),
    ],
)
def test_verbosity_level(verbosity_value, verbosity_name):
    """Test VerbosityLevel Enum class."""
    level = cli.VerbosityLevel(verbosity_value)
    assert level.name == verbosity_name


@pytest.mark.parametrize(
    "verbosity_value, exception", [(-1, ValueError), ("UNEXPECTED", ValueError)]
)
def test_verbosity_level_exception(verbosity_value, exception):
    """Test VerbosityLevel Enum class with invalid inputs."""
    with pytest.raises(exception):
        cli.VerbosityLevel(verbosity_value)


@pytest.mark.parametrize(
    "quiet, verbosity, level",
    [(True, 0, "CRITICAL"), (True, 5, "CRITICAL"), (False, 0, "ERROR"), (False, 2, "INFO")],
)
def test_get_log_level(quiet, verbosity, level):
    """Test get_log_level return value."""
    assert cli.get_log_level(quiet=quiet, verbosity=verbosity) == level


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model_name, expected_call_count",
    [("model_name", 0), ("", 1), (None, 1)],
)
@patch("cou.cli.juju_utils.get_current_model_name", new_callable=AsyncMock)
@patch("cou.cli.generate_plan", new_callable=AsyncMock)
@patch("cou.cli.Analysis.create", new_callable=AsyncMock)
async def test_analyze_and_plan(
    mock_analyze, mock_generate_plan, mock_get_current_model_name, model_name, expected_call_count
):
    """Test analyze_and_plan function with different model_name arguments."""
    mock_get_current_model_name.return_value = model_name
    analysis_result = Analysis(model_name=model_name, apps_control_plane=[], apps_data_plane=[])
    mock_analyze.return_value = analysis_result

    await cli.analyze_and_plan(model_name)

    assert mock_get_current_model_name.call_count == expected_call_count
    mock_analyze.assert_awaited_once_with(model_name)
    mock_generate_plan.assert_awaited_once_with(analysis_result)


@pytest.mark.asyncio
@patch("cou.cli.analyze_and_plan", new_callable=AsyncMock)
@patch("cou.cli.logger")
async def test_get_upgrade_plan(mock_logger, mock_analyze_and_plan):
    """Test get_upgrade_plan function."""
    plan = UpgradeStep(description="Top level plan", parallel=False, function=None)
    plan.add_step(UpgradeStep(description="backup mysql databases", parallel=False, function=None))

    mock_analyze_and_plan.return_value = plan
    await cli.get_upgrade_plan()

    mock_analyze_and_plan.assert_awaited_once()
    mock_logger.info.assert_called_once_with(plan)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "quiet, expected_print_count",
    [
        (True, 1),
        (False, 0),
    ],
)
@patch("cou.cli.analyze_and_plan", new_callable=AsyncMock)
@patch("cou.cli.apply_plan")
@patch("builtins.print")
@patch("cou.cli.logger")
async def test_run_upgrade_quiet(
    mock_logger, mock_print, mock_apply_plan, mock_analyze_and_plan, quiet, expected_print_count
):
    """Test get_upgrade_plan function in either quiet or non-quiet mode."""
    plan = UpgradeStep(description="Top level plan", parallel=False, function=None)
    plan.add_step(UpgradeStep(description="backup mysql databases", parallel=False, function=None))
    mock_analyze_and_plan.return_value = plan

    await cli.run_upgrade(quiet=quiet)

    mock_analyze_and_plan.assert_called_once()
    mock_logger.info.assert_called_once_with(plan)
    mock_apply_plan.assert_called_once_with(plan, True)
    mock_print.call_count == expected_print_count


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "interactive, progress_indication_count",
    [
        (False, 1),
        (True, 0),
    ],
)
@patch("cou.cli.analyze_and_plan", new_callable=AsyncMock)
@patch("cou.cli.apply_plan")
@patch("cou.cli.progress_indicator")
@patch("cou.cli.logger")
async def test_run_upgrade_interactive(
    mock_logger,
    mock_progress_indicator,
    mock_apply_plan,
    mock_analyze_and_plan,
    interactive,
    progress_indication_count,
):
    """Test get_upgrade_plan function in either interactive or non-interactive mode."""
    plan = UpgradeStep(description="Top level plan", parallel=False, function=None)
    plan.add_step(UpgradeStep(description="backup mysql databases", parallel=False, function=None))
    mock_analyze_and_plan.return_value = plan

    await cli.run_upgrade(interactive=interactive)

    mock_analyze_and_plan.assert_called_once()
    mock_logger.info.assert_called_once_with(plan)
    mock_apply_plan.assert_called_once_with(plan, interactive)
    assert mock_progress_indicator.start.call_count == progress_indication_count
    assert mock_progress_indicator.succeed.call_count == progress_indication_count


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "command, function_call",
    [
        ("run", "cou.cli.run_upgrade"),
        ("plan", "cou.cli.get_upgrade_plan"),
    ],
)
async def test_entrypoint_commands(mocker, command, function_call):
    """Test entrypoint with different commands."""
    mocker.patch(
        "cou.cli.parse_args",
        return_value=argparse.Namespace(
            quiet=False, command=command, verbosity=0, model_name=None, interactive=True
        ),
    )
    mocker.patch("cou.cli.analyze_and_plan")
    mocker.patch("cou.cli.setup_logging")
    mocker.patch("cou.cli.apply_plan")
    mocker.patch("cou.cli.Analysis.create")

    with patch(function_call, new=AsyncMock()) as mock_function:
        await cli.entrypoint()
        mock_function.assert_awaited_once()


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
    """Test entrypoint when exceptions are raised."""
    mocker.patch(
        "cou.cli.parse_args",
        return_value=argparse.Namespace(quiet=False, command="plan", verbosity=0, model_name=None),
    )
    mocker.patch("cou.cli.analyze_and_plan", side_effect=exception)
    mocker.patch("cou.cli.setup_logging")

    with pytest.raises(SystemExit, match=exp_exitcode):
        await cli.entrypoint()
