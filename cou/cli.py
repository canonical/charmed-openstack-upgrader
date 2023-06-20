# Copyright 2023 Canonical Limited.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Entrypoint to the 'charmed openstack upgrader'."""
import argparse
import logging
import logging.handlers
import os
import pathlib
import sys
from typing import Any

from cou.steps.plan import apply_plan, dump_plan, generate_plan

HOME = os.getenv("HOME")
COU_DIR_LOG = os.getenv("COU_DIR_LOG", f"{HOME}/.local/share/cou/log")


def parse_args(args: Any) -> argparse.Namespace:
    """Parse cli arguments."""
    parser = argparse.ArgumentParser(
        description="description",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        exit_on_error=False,
    )
    parser.add_argument(
        "--dry-run",
        default=False,
        help="Do not run the upgrade just print out the steps.",
        action="store_true",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        dest="loglevel",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level",
    )
    parser.add_argument(
        "--interactive", default=True, help="Sets the interactive prompts", action="store_true"
    )

    return parser.parse_args(args)


def setup_logging(log_level: str = "INFO") -> None:
    """Do setup for logging.

    :returns: Nothing: This function is executed for its side effect
    :rtype: None
    """
    log_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    root_logger = logging.getLogger()
    root_logger.setLevel("DEBUG")

    # handler for the log file. Log level is DEBUG
    pathlib.Path(COU_DIR_LOG).mkdir(parents=True, exist_ok=True)
    log_file_handler = logging.handlers.TimedRotatingFileHandler(
        f"{COU_DIR_LOG}/cou.log", when="D", interval=1
    )
    log_file_handler.setFormatter(log_formatter)

    # handler for the console. Log level comes from the CLI
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(log_formatter)

    root_logger.addHandler(log_file_handler)
    root_logger.addHandler(console_handler)


def entrypoint() -> int:
    """Execute 'charmed-openstack-upgrade' command."""
    try:
        args = parse_args(sys.argv[1:])
        setup_logging(log_level=args.loglevel)

        upgrade_plan = generate_plan(args)
        if args.dry_run:
            dump_plan(upgrade_plan)
        else:
            apply_plan(upgrade_plan)

        return 0
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logging.error(exc)
        return 1
