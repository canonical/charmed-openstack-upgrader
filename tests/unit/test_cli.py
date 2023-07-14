from argparse import ArgumentError
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cou.cli import apply_plan, entrypoint, parse_args, prompt, setup_logging
from cou.steps import UpgradeStep


def test_parse_args():
    args = ["--dry-run", "--log-level", "DEBUG", "--interactive", "true"]
    parsed_args = parse_args(args)
    assert parsed_args.dry_run
    assert parsed_args.loglevel == "DEBUG"
    assert parsed_args.interactive

    with pytest.raises(ArgumentError):
        args = parse_args(["--dry-run", "--log-level=DDD"])


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
    ) as mock_generate_plan, patch("cou.cli.apply_plan"), patch("cou.cli.Analysis.create"):
        mock_generate_plan.side_effect = Exception("An error occurred")

        with pytest.raises(SystemExit) as exitcode:
            result = await entrypoint()
            assert exitcode.value == 1
            assert not result
        mock_generate_plan.assert_called_once()


@pytest.mark.asyncio
async def test_entrypoint_dry_run():
    plan = UpgradeStep(description="Top level plan", parallel=False, function=None)
    plan.add_step(UpgradeStep(description="backup mysql databases", parallel=False, function=None))

    with patch("cou.cli.parse_args") as mock_parse_args, patch("cou.cli.setup_logging"), patch(
        "cou.cli.generate_plan"
    ) as mock_generate_plan, patch("cou.cli.apply_plan"), patch("cou.cli.Analysis.create"), patch(
        "builtins.print"
    ) as mock_print:
        mock_parse_args.return_value = MagicMock()
        mock_parse_args.return_value.dry_run = True

        mock_generate_plan.return_value = plan

        result = await entrypoint()
        mock_print.assert_called_with(plan)

        assert not result


@pytest.mark.asyncio
async def test_entrypoint_real_run():
    with patch("cou.cli.parse_args") as mock_parse_args, patch("cou.cli.setup_logging"), patch(
        "cou.cli.generate_plan"
    ), patch("cou.cli.apply_plan") as mock_apply_plan, patch("cou.cli.Analysis.create"):
        mock_parse_args.return_value = MagicMock()
        mock_parse_args.return_value.dry_run = False

        result = await entrypoint()

        assert not result
        mock_apply_plan.assert_called_once()


@pytest.mark.asyncio
async def test_apply_plan_continue():
    upgrade_plan = AsyncMock()
    upgrade_plan.description = "Test Plan"
    upgrade_plan.run = AsyncMock()
    sub_step = AsyncMock()
    sub_step.description = "Test Plan"
    upgrade_plan.sub_steps = [sub_step]

    with patch("cou.cli.input") as mock_input, patch("cou.cli.sys") as mock_sys:
        mock_input.return_value = "C"
        await apply_plan(upgrade_plan)

        mock_input.assert_called_with(prompt("Test Plan"))
        assert upgrade_plan.run.call_count == 1
        assert sub_step.run.call_count == 1
        mock_sys.exit.assert_not_called()


@pytest.mark.asyncio
async def test_apply_plan_abort():
    upgrade_plan = AsyncMock()
    upgrade_plan.description = "Test Plan"

    with patch("cou.cli.input") as mock_input:
        mock_input.return_value = "a"
        with pytest.raises(SystemExit):
            await apply_plan(upgrade_plan)

        mock_input.assert_called_once_with(prompt("Test Plan"))
        upgrade_plan.function.assert_not_called()


@pytest.mark.asyncio
async def test_apply_plan_nonsense():
    upgrade_plan = MagicMock()
    upgrade_plan.description = "Test Plan"

    with pytest.raises(SystemExit):
        with patch("cou.cli.input") as mock_input, patch("cou.cli.logging.info") as log:
            mock_input.side_effect = ["x", "a"]
            await apply_plan(upgrade_plan)

            log.assert_called_once_with("No valid input provided!")
            mock_input.assert_called_once_with(prompt("Test Plan"))
            upgrade_plan.function.assert_not_called()


@pytest.mark.asyncio
async def test_apply_plan_skip():
    upgrade_plan = MagicMock()
    upgrade_plan.description = "Test Plan"
    sub_step = MagicMock()
    sub_step.description = sub_step
    upgrade_plan.sub_steps = [sub_step]

    with patch("cou.cli.input") as mock_input, patch("cou.cli.sys") as mock_sys:
        mock_input.return_value = "s"
        await apply_plan(upgrade_plan)

        upgrade_plan.function.assert_not_called()
        mock_sys.exit.assert_not_called()
