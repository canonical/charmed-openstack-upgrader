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
from cou.steps.plan import PlanStatus


@pytest.mark.parametrize(
    "verbosity_value, verbosity_name",
    [
        (0, "WARNING"),
        (1, "INFO"),
        (2, "DEBUG"),
        (3, "NOTSET"),
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
    [(True, 0, "CRITICAL"), (True, 5, "CRITICAL"), (False, 0, "WARNING"), (False, 2, "DEBUG")],
)
def test_get_log_level(quiet, verbosity, level):
    """Test get_log_level return value."""
    assert cli.get_log_level(quiet=quiet, verbosity=verbosity) == level


@pytest.mark.asyncio
@patch("cou.cli.Model")
@patch("cou.cli.print_and_debug")
@patch("cou.cli.generate_plan", new_callable=AsyncMock)
@patch("cou.cli.verify_cloud", new_callable=AsyncMock)
@patch("cou.cli.Analysis.create", new_callable=AsyncMock)
@patch("cou.cli.PlanStatus", spec_set=PlanStatus)
async def test_analyze_and_generate_plan(
    mock_plan_status,
    mock_analyze,
    mock_verify_cloud,
    mock_generate_plan,
    mock_print_and_debug,
    cou_model,
    cli_args,
):
    """Test analyze_and_generate_plan function."""
    cou_model.return_value.connect.side_effect = AsyncMock()
    model = await cli.get_model(cli_args)
    mock_plan_status.error_messages = []
    mock_plan_status.warning_messages = []

    await cli.analyze_and_generate_plan(model, cli_args)

    mock_analyze.assert_awaited_once()
    mock_verify_cloud.assert_awaited_once()
    mock_generate_plan.assert_awaited_once()
    mock_print_and_debug.assert_called_once()


@pytest.mark.asyncio
@patch("cou.cli.Model")
@patch("cou.cli.print_and_debug")
@patch("cou.cli.generate_plan", new_callable=AsyncMock)
@patch("cou.cli.verify_cloud", new_callable=AsyncMock)
@patch("cou.cli.Analysis.create", new_callable=AsyncMock)
@patch("cou.cli.logger")
@patch("cou.cli.PlanStatus", spec_set=PlanStatus)
async def test_analyze_and_generate_plan_with_errors(
    mock_plan_status,
    mock_logger,
    mock_analyze,
    mock_verify_cloud,
    mock_generate_plan,
    mock_print_and_debug,
    cou_model,
    cli_args,
):
    """Test analyze_and_generate_plan function with errors."""
    cou_model.return_value.connect.side_effect = AsyncMock()
    model = await cli.get_model(cli_args)
    mock_plan_status.error_messages = ["Mock error message"]
    mock_plan_status.warning_messages = []

    with pytest.raises(COUException):
        await cli.analyze_and_generate_plan(model, cli_args)

    mock_analyze.assert_awaited_once()
    mock_verify_cloud.assert_awaited_once()
    mock_print_and_debug.assert_called_once()
    mock_generate_plan.assert_awaited_once()
    mock_logger.warning.assert_not_called()
    mock_logger.error.assert_called()
    mock_logger.error.called_counts = len(mock_plan_status.error_messages)


@pytest.mark.asyncio
@patch("cou.cli.Model")
@patch("cou.cli.print_and_debug")
@patch("cou.cli.generate_plan", new_callable=AsyncMock)
@patch("cou.cli.verify_cloud", new_callable=AsyncMock)
@patch("cou.cli.Analysis.create", new_callable=AsyncMock)
@patch("cou.cli.logger")
@patch("cou.cli.PlanStatus", spec_set=PlanStatus)
async def test_analyze_and_generate_plan_with_warnings(
    mock_plan_status,
    mock_logger,
    mock_analyze,
    mock_verify_cloud,
    mock_generate_plan,
    mock_print_and_debug,
    cou_model,
    cli_args,
):
    """Test analyze_and_generate_plan function."""
    cou_model.return_value.connect.side_effect = AsyncMock()
    model = await cli.get_model(cli_args)
    mock_plan_status.error_messages = []
    mock_plan_status.warning_messages = ["Mock warning message"]

    await cli.analyze_and_generate_plan(model, cli_args)

    mock_analyze.assert_awaited_once()
    mock_verify_cloud.assert_awaited_once()
    mock_logger.error.assert_not_called()
    mock_generate_plan.assert_awaited_once()
    mock_print_and_debug.assert_called_once()
    mock_logger.warning.assert_called()
    mock_logger.warning.called_counts = len(mock_plan_status.warning_messages)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "quiet, expected_print_count",
    [
        (True, 1),
        (False, 0),
    ],
)
@patch("cou.cli.continue_upgrade", new_callable=AsyncMock)
@patch("cou.cli.apply_step")
@patch("builtins.print")
@patch("cou.cli.PlanStatus", spec_set=PlanStatus)
async def test_apply_upgrade_plan_quiet_no_prompt(
    mock_plan_status,
    mock_print,
    mock_apply_step,
    mock_continue_upgrade,
    quiet,
    expected_print_count,
    cli_args,
):
    """Test apply_upgrade_plan function in either quiet or non-quiet mode without prompt."""
    mock_continue_upgrade.return_value = True
    cli_args.quiet = quiet
    cli_args.prompt = False

    plan = UpgradePlan(description="Upgrade cloud from 'ussuri' to 'victoria'")
    plan.add_step(PreUpgradeStep(description="Back up MySQL databases", parallel=False))

    await cli.apply_upgrade_plan(plan, cli_args)

    mock_apply_step.assert_called_once()
    mock_print.call_count == expected_print_count


@pytest.mark.asyncio
@patch("cou.cli.apply_step")
@patch("cou.cli.continue_upgrade")
@patch("builtins.print")
@patch("cou.cli.PlanStatus", spec_set=PlanStatus)
async def test_apply_upgrade_plan_with_prompt_continue(
    mock_plan_status,
    mock_print,
    mock_continue_upgrade,
    mock_apply_step,
    cli_args,
):
    """Test apply_upgrade_plan function with prompt to continue."""
    cli_args.prompt = True
    cli_args.quiet = True

    plan = UpgradePlan(description="Upgrade cloud from 'ussuri' to 'victoria'")
    plan.add_step(PreUpgradeStep(description="Back up MySQL databases", parallel=False))
    mock_continue_upgrade.return_value = True

    await cli.apply_upgrade_plan(plan, cli_args)

    mock_apply_step.assert_called_once()
    mock_print.assert_called_once()
    mock_continue_upgrade.assert_awaited_once()


@pytest.mark.asyncio
@patch("cou.cli.apply_step")
@patch("cou.cli.continue_upgrade")
@patch("builtins.print")
@patch("cou.cli.PlanStatus", spec_set=PlanStatus)
async def test_apply_upgrade_plan_with_prompt_abort(
    mock_plan_status,
    mock_print,
    mock_continue_upgrade,
    mock_apply_step,
    cli_args,
):
    """Test apply_upgrade_plan function with prompt to abort."""
    cli_args.auto_approve = False
    cli_args.quiet = True

    plan = UpgradePlan(description="Upgrade cloud from 'ussuri' to 'victoria'")
    plan.add_step(PreUpgradeStep(description="Back up MySQL databases", parallel=False))
    mock_continue_upgrade.return_value = False

    await cli.apply_upgrade_plan(plan, cli_args)

    mock_apply_step.assert_not_called()
    mock_print.assert_not_called()
    mock_continue_upgrade.assert_awaited_once()


@pytest.mark.asyncio
@patch("cou.cli.apply_step")
@patch("cou.cli.continue_upgrade")
@patch("builtins.print")
@patch("cou.cli.PlanStatus", spec_set=PlanStatus)
async def test_apply_upgrade_plan_with_no_prompt(
    mock_plan_status,
    mock_print,
    mock_continue_upgrade,
    mock_apply_step,
    cli_args,
):
    """Test apply_upgrade_plan function in non-interactive mode."""
    cli_args.prompt = False
    cli_args.quiet = True

    plan = UpgradePlan(description="Upgrade cloud from 'ussuri' to 'victoria'")
    plan.add_step(PreUpgradeStep(description="Back up MySQL databases", parallel=False))

    await cli.apply_upgrade_plan(plan, cli_args)

    mock_apply_step.assert_called_once()
    mock_print.assert_called_once()
    mock_continue_upgrade.assert_not_awaited()


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
    """Test continue_upgrade function with various inputs."""
    mock_prompt_input.return_value = input_value
    result = await cli.continue_upgrade()

    assert result == expected_result


@pytest.mark.asyncio
@pytest.mark.parametrize("command", ["plan", "upgrade", "other1", "other2"])
@patch("cou.cli.get_model")
@patch("cou.cli.analyze_and_generate_plan")
@patch("cou.cli.apply_upgrade_plan")
async def test_run_command(
    mock_apply_upgrade_plan, mock_analyze_and_generate_plan, mock_get_model, command, cli_args
):
    """Test run command function."""
    cli_args.command = command

    await cli._run_command(cli_args)

    if command == "plan":
        mock_analyze_and_generate_plan.assert_awaited_once()
        mock_apply_upgrade_plan.assert_not_called()
    elif command == "upgrade":
        mock_analyze_and_generate_plan.assert_awaited_once()
        mock_apply_upgrade_plan.assert_awaited_once()


@patch("cou.cli.print")
@patch("cou.cli.progress_indicator")
@patch("cou.cli.run_post_upgrade_sanity_check")
@patch("cou.cli.sys")
@patch("cou.cli.parse_args")
@patch("cou.cli.get_log_file")
@patch("cou.cli.get_log_level")
@patch("cou.cli.setup_logging")
@patch("cou.cli._run_command")
def test_entrypoint(
    mock_run_command,
    mock_setup_logging,
    mock_get_log_level,
    mock_get_log_file,
    mock_parse_args,
    mock_sys,
    mock_run_post_upgrade_sanity_check,
    mock_indicator,
    mock_print,
):
    """Test successful entrypoint execution."""
    mock_sys.argv = ["cou", "upgrade"]
    args = mock_parse_args.return_value
    args.command = "upgrade"
    args.quiet = False

    cli.entrypoint()

    mock_parse_args.assert_called_once_with(["upgrade"])
    mock_get_log_level.assert_called_once_with(quiet=args.quiet, verbosity=args.verbosity)
    mock_setup_logging.assert_called_once_with(
        mock_get_log_file.return_value,
        mock_get_log_level.return_value,
    )
    mock_run_command.assert_awaited_once_with(args)
    mock_run_post_upgrade_sanity_check.await_count == 2
    mock_print.assert_called_once_with(
        f"Full execution log: '{mock_get_log_file.return_value}'",
    )
    mock_indicator.stop.assert_called_once()


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
def test_entrypoint_failure_validation_error(mock_run_command, mock_indicator):
    """Test COUException exception during entrypoint execution."""
    mock_run_command.side_effect = COUException

    with pytest.raises(SystemExit, match="1"):
        cli.entrypoint()

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

    mock_print.assert_any_call(message or "charmed-openstack-upgrader has been terminated")
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "quiet, expected_print_count",
    [
        (True, 1),
        (False, 2),
    ],
)
@patch("builtins.print")
@patch("cou.cli.Model")
@patch("cou.cli.post_upgrade_sanity_checks", new_callable=AsyncMock)
@patch("cou.cli.Analysis", new_callable=AsyncMock)
@patch("cou.cli.PlanStatus", spec_set=PlanStatus)
async def test_run_run_post_upgrade_sanity_check(
    mock_plan_status,
    mock_analyze,
    mock_post_upgrade_sanity_checks,
    cou_model,
    mock_print,
    quiet,
    expected_print_count,
    cli_args,
):
    """Test run_post_upgrade_sanity_check function in either quiet or non-quiet mode."""
    cli_args.quiet = quiet

    cou_model.return_value.connect.side_effect = AsyncMock()
    analysis_result = Analysis(model=cou_model, apps=[])
    mock_analyze.return_value = analysis_result

    mock_plan_status.error_messages = []
    mock_plan_status.warning_messages = []

    await cli.run_post_upgrade_sanity_check(cli_args)

    mock_post_upgrade_sanity_checks.assert_called_once()
    mock_print.call_count == expected_print_count
