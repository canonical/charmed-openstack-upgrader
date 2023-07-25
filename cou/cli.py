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

"""Entrypoint to the 'charmed-openstack-upgrader'."""
import argparse
import logging
import logging.handlers
import os
import pathlib
import sys
from datetime import datetime
from typing import Any

from colorama import Fore, Style

from cou.steps import UpgradeStep
from cou.steps.analyze import Analysis
from cou.steps.plan import generate_plan
from cou.utils import juju_utils as utils

COU_DIR_LOG = pathlib.Path(os.getenv("COU_DATA", ""), "log")
AVAILABLE_OPTIONS = "cas"

logger = logging.getLogger(__name__)


def parse_args(args: Any) -> argparse.Namespace:
    """Parse cli arguments.

    :param args: Arguments to be parsed.
    :type args: Any
    :return: Arguments parsed to the cli execution.
    :rtype: argparse.Namespace
    """
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
        type=str.upper,
        help="Set the logging level",
    )
    parser.add_argument(
        "--model",
        default=None,
        dest="model_name",
        help="Set the model to operate on.",
    )
    parser.add_argument("--interactive", default=True, help="Sets the interactive prompts")

    return parser.parse_args(args)


def setup_logging(log_level: str = "INFO") -> None:
    """Do setup for logging.

    :returns: Nothing: This function is executed for its side effect
    :rtype: None
    """
    log_formatter_file = logging.Formatter(
        fmt="%(asctime)s [%(name)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    log_formatter_console = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    root_logger = logging.getLogger()
    root_logger.setLevel("DEBUG")

    # handler for the log file. Log level is DEBUG
    time_stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    file_name = f"{COU_DIR_LOG}/cou-{time_stamp}.log"
    pathlib.Path(COU_DIR_LOG).mkdir(parents=True, exist_ok=True)
    log_file_handler = logging.FileHandler(file_name)
    log_file_handler.setFormatter(log_formatter_file)

    # handler for the console. Log level comes from the CLI
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(log_formatter_console)
    # just cou logs on console
    console_handler.addFilter(logging.Filter(__package__))

    root_logger.addHandler(log_file_handler)
    root_logger.addHandler(console_handler)
    logger.info("Logs of this execution can be found at %s", file_name)


def prompt(parameter: str) -> str:
    """Generate eye-catching prompt.

    :param parameter: String to show at the prompt with the user options.
    :type parameter: str
    :return: Colored prompt string with the user options.
    :rtype: str
    """

    def bold(text: str) -> str:
        return Style.RESET_ALL + Fore.RED + Style.BRIGHT + text + Style.RESET_ALL

    def normal(text: str) -> str:
        return Style.RESET_ALL + Fore.RED + text + Style.RESET_ALL

    return (
        normal(parameter + " (")
        + bold("c")
        + normal(")ontinue/(")
        + bold("a")
        + normal(")bort/(")
        + bold("s")
        + normal(")kip:")
    )


async def apply_plan(upgrade_plan: UpgradeStep) -> None:
    """Apply the plan for upgrade.

    :param upgrade_plan: Plan to be executed on steps.
    :type upgrade_plan: UpgradeStep
    """
    result = "X"
    while result.casefold() not in AVAILABLE_OPTIONS:
        result = input(prompt(upgrade_plan.description)).casefold()
        match result:
            case "c":
                await upgrade_plan.run()
                for sub_step in upgrade_plan.sub_steps:
                    await apply_plan(sub_step)
            case "a":
                logger.info("Aborting plan")
                sys.exit(1)
            case "s":
                logger.info("Skipped")
            case _:
                logger.info("No valid input provided!")


async def entrypoint() -> None:
    """Execute 'charmed-openstack-upgrade' command."""
    try:
        args = parse_args(sys.argv[1:])

        setup_logging(log_level=args.loglevel)

        model_name = await utils.async_set_current_model_name(args.model_name)
        logger.info("Setting current model name: %s", model_name)

        analysis_result = await Analysis.create()
        print(analysis_result)
        upgrade_plan = await generate_plan(analysis_result)
        if args.dry_run:
            print(upgrade_plan)
        else:
            await apply_plan(upgrade_plan)

    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.exception(exc)
        sys.exit(1)
