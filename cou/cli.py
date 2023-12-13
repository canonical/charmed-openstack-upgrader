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

"""Entrypoint for 'charmed-openstack-upgrader'."""
import argparse
import asyncio
import logging
import logging.handlers
import sys
from enum import Enum
from signal import SIGINT, SIGTERM
from typing import Optional

from juju.errors import JujuError

from cou.commands import parse_args
from cou.exceptions import COUException, HighestReleaseAchieved, TimeoutException
from cou.logging import setup_logging
from cou.steps import UpgradePlan
from cou.steps.analyze import Analysis
from cou.steps.execute import apply_step
from cou.steps.plan import generate_plan, manually_upgrade_data_plane
from cou.utils import print_and_debug, progress_indicator, prompt_input
from cou.utils.cli import interrupt_handler
from cou.utils.juju_utils import COUModel

AVAILABLE_OPTIONS = "cas"

logger = logging.getLogger(__name__)


class VerbosityLevel(Enum):
    """
    Enumeration of verbosity levels for logging.

    - 'ERROR': Only errors will be logged.
    - 'WARNING': Both errors and warnings will be logged.
    - 'INFO': Errors, warnings, and general information will be logged.
    - 'DEBUG': Detailed debugging information will be logged.
    - 'NOTSET': Maximum verbosity where everything will be logged.
    """

    ERROR = 0
    WARNING = 1
    INFO = 2
    DEBUG = 3
    NOTSET = 4

    @classmethod
    def _missing_(cls, value: object) -> Enum:
        """Return maximum verbosity for value larger than 4.

        :param value: value to get enum member
        :type value: object
        :return: return a member of VerbosityLevel
        :rtype: Enum
        :raises ValueError: Invalid value input.
        """
        if isinstance(value, int) and value > 4:
            return cls.NOTSET
        raise ValueError(f"{value} is not a valid member of VerbosityLevel.")


def get_log_level(quiet: bool = False, verbosity: int = 0) -> str:
    """Get a log level based on input options.

    :param quiet: Whether to run COU in quiet mode.
    :type quiet: bool
    :param verbosity: Verbosity level based on user's input.
    :type verbosity: int
    :return: Log level.
    :rtype: str
    """
    if quiet:
        return "CRITICAL"
    return VerbosityLevel(verbosity).name


async def continue_upgrade() -> bool:
    """Determine whether to continue with the upgrade based on user input.

    :return: Boolean value indicate whether to continue with the upgrade.
    :rtype: bool
    """
    input_value = await prompt_input(
        ["Would you like to start the upgrade?", "Continue"], separator=" ", default="n"
    )

    match input_value:
        case "y" | "yes":
            logger.info("Start the upgrade.")
            return True
        case "n" | "no":
            logger.info("Exiting COU without running upgrades.")
        case _:
            print_and_debug("No valid input provided! Exiting COU without upgrades.")

    return False


async def analyze_and_plan(
    model_name: Optional[str], backup_database: bool
) -> tuple[Analysis, UpgradePlan]:
    """Analyze cloud and generate the upgrade plan with steps.

    :param model_name: Model name inputted by user.
    :type model_name: Optional[str]
    :param backup_database: Whether to create database backup before upgrade.
    :type backup_database: bool
    :return: Generated analyses and upgrade plan.
    :rtype: tuple[Analysis, UpgradePlan]
    """
    model = COUModel(model_name)
    progress_indicator.start(f"Connecting to '{model.name}' model...")
    await model.connect()
    logger.info("Using model: %s", model.name)
    progress_indicator.succeed(f"Connected to '{model.name}'")

    progress_indicator.start("Analyzing cloud...")
    analysis_result = await Analysis.create(model)
    logger.info(analysis_result)
    progress_indicator.succeed()

    progress_indicator.start("Generating upgrade plan...")
    upgrade_plan = await generate_plan(analysis_result, backup_database)
    progress_indicator.succeed()

    return analysis_result, upgrade_plan


async def get_upgrade_plan(model_name: Optional[str], backup_database: bool) -> None:
    """Get upgrade plan and print to console.

    :param model_name: Model name inputted by user.
    :type model_name: Optional[str]
    :param backup_database: Whether to create database backup before upgrade.
    :type backup_database: bool
    """
    analysis_result, upgrade_plan = await analyze_and_plan(model_name, backup_database)
    print_and_debug(upgrade_plan)
    manually_upgrade_data_plane(analysis_result)
    print(
        "Please note that the actually upgrade steps could be different if the cloud state "
        "changes because the plan will be re-calculated at upgrade time."
    )


async def run_upgrade(
    model_name: Optional[str],
    backup_database: bool,
    interactive: bool,
    quiet: bool,
) -> None:
    """Run cloud upgrade.

    :param model_name: Model name inputted by user.
    :type model_name: Optional[str]
    :param backup_database: Whether to create database backup before upgrade.
    :type backup_database: bool
    :param interactive: Whether to run upgrade interactively.
    :type interactive: bool
    :param quiet: Whether to run upgrade in quiet mode.
    :type quiet: bool
    """
    analysis_result, upgrade_plan = await analyze_and_plan(model_name, backup_database)
    print_and_debug(upgrade_plan)

    if interactive and not await continue_upgrade():
        return

    # NOTE(rgildein): add handling upgrade plan canceling for SIGINT (ctrl+c) and SIGTERM
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(SIGINT, interrupt_handler, upgrade_plan, loop, 130)
    loop.add_signal_handler(SIGTERM, interrupt_handler, upgrade_plan, loop, 143)

    # don't print plan if in quiet mode
    if not quiet:
        print("Running cloud upgrade...")

    await apply_step(upgrade_plan, interactive)
    manually_upgrade_data_plane(analysis_result)
    print("Upgrade completed.")


async def _run_command(args: argparse.Namespace) -> None:
    """Run 'charmed-openstack-upgrade' command.

    :param args: CLI arguments
    :type args: argparse.Namespace
    """
    match args.command:
        case "plan":
            await get_upgrade_plan(args.model_name, args.backup)
        case "run":
            await run_upgrade(args.model_name, args.backup, args.interactive, args.quiet)


def entrypoint() -> None:
    """Execute 'charmed-openstack-upgrade' command."""
    try:
        args = parse_args(sys.argv[1:])

        # disable progress indicator when in quiet mode to suppress its console output
        progress_indicator.enabled = not args.quiet
        log_level = get_log_level(quiet=args.quiet, verbosity=args.verbosity)
        setup_logging(log_level)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(_run_command(args))
    except HighestReleaseAchieved as exc:
        print(exc)
        sys.exit(0)
    except TimeoutException:
        progress_indicator.fail()
        print("The connection was lost. Check your connection or increase the timeout.")
        sys.exit(1)
    except COUException as exc:
        progress_indicator.fail()
        logger.error(exc)
        sys.exit(1)
    except JujuError as exc:
        progress_indicator.fail()
        logger.error("Error occurred in Juju's Python library.")
        logger.error(exc)
        sys.exit(1)
    except KeyboardInterrupt as exc:
        # NOTE(rgildein): if spinner_id is not None it means that indicator was not finished
        if progress_indicator.spinner_id is not None:
            progress_indicator.fail()
        print(str(exc) or "charmed-openstack-upgrader has been terminated")
        sys.exit(getattr(exc, "exit_code", 130))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Unexpected error occurred.")
        logger.exception(exc)
        sys.exit(2)
    finally:
        progress_indicator.stop()
