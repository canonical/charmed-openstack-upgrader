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

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from juju.errors import JujuError

from cou import cli
from cou.exceptions import COUException, HighestReleaseAchieved, TimeoutException
from cou.steps import PreUpgradeStep, UpgradePlan
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
@patch("cou.cli.COUModel")
@patch("cou.cli.generate_plan", new_callable=AsyncMock)
@patch("cou.cli.Analysis.create", new_callable=AsyncMock)
async def test_analyze_and_plan(mock_analyze, mock_generate_plan, cou_model, cli_args):
    """Test analyze_and_plan function with different model_name arguments."""
    cli_args.model_name = None
    cli_args.backup = False

    cou_model.return_value.connect.side_effect = AsyncMock()
    analysis_result = Analysis(model=cou_model, apps_control_plane=[], apps_data_plane=[])
    mock_analyze.return_value = analysis_result

    await cli.analyze_and_plan(cli_args)

    cou_model.assert_called_once_with(None)
    mock_analyze.assert_awaited_once_with(cou_model.return_value)
    mock_generate_plan.assert_awaited_once_with(analysis_result, cli_args)


@pytest.mark.asyncio
@patch("cou.cli.analyze_and_plan", new_callable=AsyncMock)
@patch("cou.cli.print_and_debug")
async def test_get_upgrade_plan(mock_print_and_debug, mock_analyze_and_plan, cli_args):
    """Test get_upgrade_plan function."""
    plan = UpgradePlan(description="Upgrade cloud from 'ussuri' to 'victoria'")
    plan.add_step(PreUpgradeStep(description="Back up MySQL databases", parallel=False))

    mock_analyze_and_plan.return_value = plan
    await cli.get_upgrade_plan(cli_args)

    mock_analyze_and_plan.assert_awaited_once_with(cli_args)
    mock_print_and_debug.assert_called_once_with(plan)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "quiet, expected_print_count",
    [
        (True, 1),
        (False, 0),
    ],
)
@patch("cou.cli.continue_upgrade", new_callable=AsyncMock)
@patch("cou.cli.analyze_and_plan", new_callable=AsyncMock)
@patch("cou.cli.apply_step")
@patch("builtins.print")
@patch("cou.cli.print_and_debug")
async def test_run_upgrade_quiet_no_prompt(
    mock_print_and_debug,
    mock_print,
    mock_apply_step,
    mock_analyze_and_plan,
    mock_continue_upgrade,
    quiet,
    expected_print_count,
    cli_args,
):
    """Test get_upgrade_plan function in either quiet or non-quiet mode without prompt."""
    mock_continue_upgrade.return_value = True
    cli_args.quiet = quiet
    cli_args.prompt = False

    plan = UpgradePlan(description="Upgrade cloud from 'ussuri' to 'victoria'")
    plan.add_step(PreUpgradeStep(description="Back up MySQL databases", parallel=False))
    mock_analyze_and_plan.return_value = plan

    await cli.run_upgrade(cli_args)

    mock_analyze_and_plan.assert_awaited_once_with(cli_args)
    mock_print_and_debug.assert_called_once_with(plan)
    mock_apply_step.assert_called_once_with(plan, False)
    mock_print.call_count == expected_print_count


@pytest.mark.asyncio
@patch("cou.cli.analyze_and_plan", new_callable=AsyncMock)
@patch("cou.cli.apply_step")
@patch("cou.cli.continue_upgrade")
async def test_run_upgrade_with_prompt_continue(
    mock_continue_upgrade,
    mock_apply_step,
    mock_analyze_and_plan,
    cli_args,
):
    cli_args.prompt = True
    cli_args.quiet = True

    plan = UpgradePlan(description="Upgrade cloud from 'ussuri' to 'victoria'")
    plan.add_step(PreUpgradeStep(description="Back up MySQL databases", parallel=False))
    mock_analyze_and_plan.return_value = plan
    mock_continue_upgrade.return_value = True

    await cli.run_upgrade(cli_args)

    mock_analyze_and_plan.assert_awaited_once_with(cli_args)
    mock_continue_upgrade.assert_awaited_once_with()
    mock_apply_step.assert_called_once_with(plan, True)


@pytest.mark.asyncio
@patch("cou.cli.analyze_and_plan", new_callable=AsyncMock)
@patch("cou.cli.apply_step")
@patch("cou.cli.continue_upgrade")
async def test_run_upgrade_with_prompt_abort(
    mock_continue_upgrade,
    mock_apply_step,
    mock_analyze_and_plan,
    cli_args,
):
    cli_args.auto_approve = False
    cli_args.quiet = True

    plan = UpgradePlan(description="Upgrade cloud from 'ussuri' to 'victoria'")
    plan.add_step(PreUpgradeStep(description="Back up MySQL databases", parallel=False))
    mock_analyze_and_plan.return_value = plan
    mock_continue_upgrade.return_value = False

    await cli.run_upgrade(cli_args)

    mock_analyze_and_plan.assert_awaited_once_with(cli_args)
    mock_continue_upgrade.assert_awaited_once_with()
    mock_apply_step.assert_not_awaited()


@pytest.mark.asyncio
@patch("cou.cli.analyze_and_plan", new_callable=AsyncMock)
@patch("cou.cli.apply_step")
@patch("cou.cli.continue_upgrade", new_callable=AsyncMock)
async def test_run_upgrade_with_no_prompt(
    mock_continue_upgrade,
    mock_apply_step,
    mock_analyze_and_plan,
    cli_args,
):
    cli_args.prompt = False
    cli_args.quiet = True

    plan = UpgradePlan(description="Upgrade cloud from 'ussuri' to 'victoria'")
    plan.add_step(PreUpgradeStep(description="Back up MySQL databases", parallel=False))
    mock_analyze_and_plan.return_value = plan

    await cli.run_upgrade(cli_args)

    mock_analyze_and_plan.assert_awaited_once_with(cli_args)
    mock_continue_upgrade.assert_not_awaited()
    mock_apply_step.assert_called_once_with(plan, False)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "input_value,expected_result",
    [
        ["y", True],
        ["yes", True],
        ["n", False],
        ["no", False],
        ["x", False],  # invalid input
    ],
)
@patch("cou.cli.prompt_input")
async def test_continue_upgrade(
    mock_prompt_input,
    input_value,
    expected_result,
):
    mock_prompt_input.return_value = input_value
    result = await cli.continue_upgrade()

    assert result == expected_result


@pytest.mark.asyncio
@pytest.mark.parametrize("command", ["plan", "other1", "other2"])
@patch("cou.cli.get_upgrade_plan")
@patch("cou.cli.run_upgrade")
async def test_run_command(mock_run_upgrade, mock_get_upgrade_plan, command, cli_args):
    """Test run command function."""
    cli_args.command = command

    await cli._run_command(cli_args)

    if command == "plan":
        mock_get_upgrade_plan.assert_awaited_once_with(cli_args)
        mock_run_upgrade.assert_not_called()
    else:
        mock_run_upgrade.assert_not_called()
        mock_get_upgrade_plan.assert_not_called()


@pytest.mark.asyncio
@patch("cou.cli.get_upgrade_plan")
@patch("cou.cli.run_upgrade")
async def test_run_command_upgrade(mock_run_upgrade, mock_get_upgrade_plan, cli_args):
    """Test run command function."""
    cli_args.command = "upgrade"

    with pytest.raises(RuntimeError, match="This version of COU does not support it."):
        await cli._run_command(cli_args)

    mock_get_upgrade_plan.assert_not_called()
    mock_run_upgrade.assert_not_called()


@patch("cou.cli.sys")
@patch("cou.cli.parse_args")
@patch("cou.cli.get_log_level")
@patch("cou.cli.setup_logging")
@patch("cou.cli._run_command")
def test_entrypoint(
    mock_run_command, mock_setup_logging, mock_get_log_level, mock_parse_args, mock_sys
):
    """Test successful entrypoint execution."""
    mock_sys.argv = ["cou", "upgrade"]

    cli.entrypoint()

    mock_parse_args.assert_called_once_with(["upgrade"])
    args = mock_parse_args.return_value
    mock_get_log_level.assert_called_once_with(quiet=args.quiet, verbosity=args.verbosity)
    mock_setup_logging.assert_called_once_with(mock_get_log_level.return_value)
    mock_run_command.assert_awaited_once_with(args)


@patch("cou.cli.progress_indicator")
@patch("cou.cli.parse_args", new=MagicMock())
@patch("cou.cli.get_log_level", new=MagicMock())
@patch("cou.cli.setup_logging", new=MagicMock())
@patch("cou.cli._run_command")
def test_entrypoint_highest_release(mock_run_command, mock_indicator):
    """Test TimeoutException exception during entrypoint execution."""
    mock_run_command.side_effect = HighestReleaseAchieved

    cli.entrypoint()

    mock_indicator.succeed.assert_called_once_with()
    mock_indicator.stop.assert_called_once_with()


@patch("cou.cli.progress_indicator")
@patch("cou.cli.parse_args", new=MagicMock())
@patch("cou.cli.get_log_level", new=MagicMock())
@patch("cou.cli.setup_logging", new=MagicMock())
@patch("cou.cli._run_command")
def test_entrypoint_failure_timeout(mock_run_command, mock_indicator):
    """Test TimeoutException exception during entrypoint execution."""
    mock_run_command.side_effect = TimeoutException

    with pytest.raises(SystemExit, match="1"):
        cli.entrypoint()

    mock_indicator.fail.assert_called_once_with()
    mock_indicator.stop.assert_called_once_with()


@patch("cou.cli.progress_indicator")
@patch("cou.cli.parse_args", new=MagicMock())
@patch("cou.cli.get_log_level", new=MagicMock())
@patch("cou.cli.setup_logging", new=MagicMock())
@patch("cou.cli._run_command")
def test_entrypoint_failure_cou_exception(mock_run_command, mock_indicator):
    """Test COUException exception during entrypoint execution."""
    mock_run_command.side_effect = COUException

    with pytest.raises(SystemExit, match="1"):
        cli.entrypoint()

    mock_indicator.fail.assert_called_once_with()
    mock_indicator.stop.assert_called_once_with()


@patch("cou.cli.progress_indicator")
@patch("cou.cli.parse_args", new=MagicMock())
@patch("cou.cli.get_log_level", new=MagicMock())
@patch("cou.cli.setup_logging", new=MagicMock())
@patch("cou.cli._run_command")
def test_entrypoint_failure_juju_error(mock_run_command, mock_indicator):
    """Test JujuError exception during entrypoint execution."""
    mock_run_command.side_effect = JujuError

    with pytest.raises(SystemExit, match="1"):
        cli.entrypoint()

    mock_indicator.fail.assert_called_once_with()
    mock_indicator.stop.assert_called_once_with()


@patch("cou.cli.print")
@patch("cou.cli.progress_indicator")
@patch("cou.cli.parse_args", new=MagicMock())
@patch("cou.cli.get_log_level", new=MagicMock())
@patch("cou.cli.setup_logging", new=MagicMock())
@patch("cou.cli._run_command")
@pytest.mark.parametrize("message", ["test", "", "test2"])
def test_entrypoint_failure_keyboard_interrupt(
    mock_run_command, mock_indicator, mock_print, message
):
    """Test KeyboardInterrupt exception during entrypoint execution."""
    mock_run_command.side_effect = KeyboardInterrupt(message)

    with pytest.raises(SystemExit, match="130"):
        cli.entrypoint()

    mock_print.assert_called_once_with(message or "charmed-openstack-upgrader has been terminated")
    mock_indicator.fail.assert_called_once_with()
    mock_indicator.stop.assert_called_once_with()


@patch("cou.cli.progress_indicator")
@patch("cou.cli.parse_args", new=MagicMock())
@patch("cou.cli.get_log_level", new=MagicMock())
@patch("cou.cli.setup_logging", new=MagicMock())
@patch("cou.cli._run_command")
@pytest.mark.parametrize("exception", [ValueError, KeyError, RuntimeError])
def test_entrypoint_failure_unexpected_exception(mock_run_command, mock_indicator, exception):
    """Test Exception exception during entrypoint execution."""
    mock_run_command.side_effect = exception

    with pytest.raises(SystemExit, match="2"):
        cli.entrypoint()

    mock_indicator.stop.assert_called_once_with()
