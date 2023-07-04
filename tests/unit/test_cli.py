from argparse import ArgumentError
from unittest.mock import MagicMock, patch

import pytest

from cou.cli import entrypoint, parse_args, setup_logging


def test_parse_args():
    args = ["--dry-run", "--log-level", "DEBUG", "--interactive"]
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

        result = await entrypoint()

        assert result == 1
        mock_generate_plan.assert_called_once()


@pytest.mark.asyncio
async def test_entrypoint_dry_run():
    with patch("cou.cli.parse_args") as mock_parse_args, patch("cou.cli.setup_logging"), patch(
        "cou.cli.generate_plan"
    ), patch("cou.cli.dump_plan") as mock_dump_plan, patch("cou.cli.apply_plan"), patch(
        "cou.cli.Analysis.create"
    ):
        mock_parse_args.return_value = MagicMock()
        mock_parse_args.return_value.dry_run = True

        result = await entrypoint()

        assert result == 0
        mock_dump_plan.assert_called_once()


@pytest.mark.asyncio
async def test_entrypoint_real_run():
    with patch("cou.cli.parse_args") as mock_parse_args, patch("cou.cli.setup_logging"), patch(
        "cou.cli.generate_plan"
    ), patch("cou.cli.dump_plan"), patch("cou.cli.apply_plan") as mock_apply_plan, patch(
        "cou.cli.Analysis.create"
    ):
        mock_parse_args.return_value = MagicMock()
        mock_parse_args.return_value.dry_run = False

        result = await entrypoint()

        assert result == 0
        mock_apply_plan.assert_called_once()
