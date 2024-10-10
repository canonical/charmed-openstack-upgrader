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
import asyncio
import logging
import logging.handlers
import sys
from enum import Enum
from pathlib import Path
from signal import SIGINT, SIGTERM
from typing import Optional

from juju.errors import JujuError

from cou.commands import CLIargs, parse_args
from cou.exceptions import COUException, HighestReleaseAchieved, TimeoutException
from cou.logging import get_log_file, setup_logging
from cou.steps import UpgradePlan
from cou.steps.analyze import Analysis
from cou.steps.execute import apply_step
from cou.steps.plan import (
    PlanStatus,
    generate_plan,
    post_upgrade_sanity_checks,
    verify_cloud,
)
from cou.utils import print_and_debug, progress_indicator, prompt_input
from cou.utils.cli import interrupt_handler
from cou.utils.juju_utils import Model

AVAILABLE_OPTIONS = "cas"

logger = logging.getLogger(__name__)


class VerbosityLevel(Enum):
    """
    Enumeration of verbosity levels for logging.

    - 'WARNING': Both errors and warnings will be logged.
    - 'INFO': Errors, warnings, and general information will be logged.
    - 'DEBUG': Detailed debugging information will be logged.
    - 'NOTSET': Maximum verbosity where everything will be logged.
    """

    WARNING = 0
    INFO = 1
    DEBUG = 2
    NOTSET = 3

    @classmethod
    def _missing_(cls, value: object) -> Enum:
        """Return maximum verbosity for value larger than 3.

        :param value: value to get enum member
        :type value: object
        :return: return a member of VerbosityLevel
        :rtype: Enum
        :raises ValueError: Invalid value input.
        """
        if isinstance(value, int) and value > 3:
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
    return "CRITICAL" if quiet else VerbosityLevel(verbosity).name


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
            logger.info("Starting the upgrade.")
            return True
        case "n" | "no":
            logger.info("Exiting COU without running upgrades.")
        case _:
            print_and_debug("No valid input provided! Exiting COU without upgrades.")

    return False


async def get_model(args: CLIargs) -> Model:
    """Connect and get the juju model.

    :param args: CLI arguments
    :type args: CLIargs
    :return: Juju Model
    :rtype: Model
    """
    model = Model(args.model_name)
    progress_indicator.start(f"Connecting to '{model.name}' model...")
    await model.connect()
    logger.info("Using model: %s", model.name)
    progress_indicator.succeed(f"Connected to '{model.name}'")
    return model


async def analyze_and_generate_plan(model: Model, args: CLIargs) -> UpgradePlan:
    """Analyze the cloud and generate plan for cloud upgrade.

    :param model: The model to run on
    :type model: Model
    :param args: CLI arguments
    :type args: CLIargs
    :return: The generated upgrade plan.
    :rtype: UpgradePlan
    :raises COUException: when cloud is not ready for upgrade
    """
    progress_indicator.start("Analyzing cloud...")
    analysis_result = await Analysis.create(model, skip_apps=args.skip_apps)
    logger.info(analysis_result)
    progress_indicator.succeed()

    progress_indicator.start("Verifying cloud...")
    await verify_cloud(analysis_result, args=args)
    progress_indicator.succeed()

    progress_indicator.start("Generating upgrade plan...")
    upgrade_plan = await generate_plan(analysis_result, args)
    progress_indicator.succeed()

    print_and_debug(upgrade_plan)

    for warning in PlanStatus.warning_messages:
        logger.warning(warning)

    if errors := PlanStatus.error_messages:
        for error in errors:
            logger.error(error)
        raise COUException(
            "Running upgrades will not be possible until problems indicated in the errors "
            "are resolved"
        )

    print(
        "Please note that the actual upgrade steps could be different if the cloud state "
        "changes because the plan will be re-calculated at upgrade time."
    )

    return upgrade_plan


async def apply_upgrade_plan(upgrade_plan: UpgradePlan, args: CLIargs) -> None:
    """Apply upgrade plan to upgrade cloud.

    :param upgrade_plan: CLI arguments
    :type upgrade_plan: UpgradePlan
    :param args: CLI arguments
    :type args: CLIargs
    """
    if args.prompt and not await continue_upgrade():
        return

    # NOTE(rgildein): add handling upgrade plan canceling for SIGINT (ctrl+c) and SIGTERM
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(SIGINT, interrupt_handler, upgrade_plan, loop, 130)
    loop.add_signal_handler(SIGTERM, interrupt_handler, upgrade_plan, loop, 143)

    # don't print plan if in quiet mode
    if not args.quiet:
        print("Running cloud upgrade...")

    await apply_step(upgrade_plan, args.prompt)
    print("Upgrade completed.")


async def run_post_upgrade_sanity_check(args: CLIargs) -> None:
    """Run post upgrade sanity check.

    :param args: CLI arguments
    :type args: CLIargs
    """
    if not args.quiet:
        print("Running post upgrade sanity check...")
    model = Model(args.model_name)
    await model.connect()
    analysis_result = await Analysis.create(model, skip_apps=args.skip_apps)
    await post_upgrade_sanity_checks(analysis_result)
    print("Post upgrade sanity check completed.")


async def run_plan_subcommand(args: CLIargs) -> None:
    """Run the `plan` subcommand.

    :param args: CLI arguments
    :type args: CLIargs
    """
    model = await get_model(args)
    await analyze_and_generate_plan(model, args)


async def run_upgrade_subcommand(args: CLIargs) -> None:
    """Run the `upgrade` subcommand.

    :param args: CLI arguments
    :type args: CLIargs
    """
    model = await get_model(args)
    cloud_upgrade_plan = await analyze_and_generate_plan(model, args)
    await apply_upgrade_plan(cloud_upgrade_plan, args)


async def _run_command(args: CLIargs) -> None:
    """Run 'charmed-openstack-upgrade' command.

    :param args: CLI arguments
    :type args: CLIargs
    """
    match args.command:
        case "plan":
            await run_plan_subcommand(args)
        case "upgrade":
            await run_upgrade_subcommand(args)


def entrypoint() -> None:
    """Run the cli app.

    Only this function and parse_args() should call sys.exit.
    Other functions that find a blocking error should raise an Exception
    and let it be handled by this function.
    """
    args = parse_args(sys.argv[1:])

    log_file: Optional[Path] = None
    try:
        # disable progress indicator when in quiet mode to suppress its console output
        progress_indicator.enabled = not args.quiet
        log_level = get_log_level(quiet=args.quiet, verbosity=args.verbosity)
        log_file = get_log_file()
        setup_logging(log_file, log_level)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(_run_command(args))
    except HighestReleaseAchieved as exc:
        progress_indicator.succeed()
        print(exc)
    except TimeoutException:
        progress_indicator.fail()
        print(
            "The connection was lost.\n"
            "Check your connection or increase the timeout.\n"
            "Default timeout is 10s; to increase to 60s for example:\n"
            "$ COU_TIMEOUT=60 cou plan"
        )
        sys.exit(1)
    except COUException as exc:
        progress_indicator.fail()
        logger.error(exc)
        logger.error(
            "See the known issues at https://canonical-charmed-openstack-upgrader.readthedocs-"
            "hosted.com/en/stable/reference/known-issues/"
        )
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
        if args.command == "upgrade":
            loop.run_until_complete(run_post_upgrade_sanity_check(args))
        if log_file is not None and not args.quiet:
            print(f"Full execution log: '{log_file}'")
        progress_indicator.stop()
