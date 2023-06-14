import unittest
from argparse import ArgumentError
from unittest.mock import MagicMock, patch

import pytest

from cou.cli import entrypoint, parse_args, setup_logging


class CliTestCase(unittest.TestCase):
    def test_parse_args(self):
        args = ["--dry-run", "--log-level", "DEBUG", "--interactive"]
        parsed_args = parse_args(args)
        self.assertTrue(parsed_args.dry_run)
        self.assertEqual(parsed_args.loglevel, "DEBUG")
        self.assertTrue(parsed_args.interactive)

        with pytest.raises(ArgumentError):
            args = parse_args(["--dry-run", "--log-level=DDD"])

    def test_setup_logging(self):
        with patch("cou.cli.logging") as mock_logging:
            mock_logging.INFO = "INFO"
            handlers = MagicMock()
            handlers.return_value = False
            mock_logging.getLogger.return_value.hasHandlers = handlers
            setup_logging("INFO")
            mock_logger = mock_logging.getLogger.return_value
            mock_console_handler = mock_logging.StreamHandler.return_value
            mock_logger.setLevel.assert_called_once_with(mock_logging.INFO)
            mock_logger.hasHandlers.assert_called_once()
            mock_logging.StreamHandler.assert_called_once()
            mock_console_handler.setFormatter.assert_called_once()

    def test_entrypoint_with_exception(self):
        with patch("cou.cli.parse_args"), patch("cou.cli.setup_logging"), patch(
            "cou.cli.generate_plan"
        ) as mock_generate_plan, patch("cou.cli.apply_plan"), patch("cou.cli.analyze"):
            mock_generate_plan.side_effect = Exception("An error occurred")

            result = entrypoint()

            self.assertEqual(result, 1)
            mock_generate_plan.assert_called_once()

    def test_entrypoint_dry_run(self):
        with patch("cou.cli.parse_args") as mock_parse_args, patch("cou.cli.setup_logging"), patch(
            "cou.cli.generate_plan"
        ), patch("cou.cli.dump_plan") as mock_dump_plan, patch("cou.cli.apply_plan"), patch(
            "cou.cli.analyze"
        ):
            mock_parse_args.return_value = MagicMock()
            mock_parse_args.return_value.dry_run = True

            result = entrypoint()

            self.assertEqual(result, 0)
            mock_dump_plan.assert_called_once()

    def test_entrypoint_real_run(self):
        with patch("cou.cli.parse_args") as mock_parse_args, patch("cou.cli.setup_logging"), patch(
            "cou.cli.generate_plan"
        ), patch("cou.cli.dump_plan"), patch("cou.cli.apply_plan") as mock_apply_plan, patch(
            "cou.cli.analyze"
        ):
            mock_parse_args.return_value = MagicMock()
            mock_parse_args.return_value.dry_run = False

            result = entrypoint()

            self.assertEqual(result, 0)
            mock_apply_plan.assert_called_once()
