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

"""Entrypoint to the 'canonical-openstack-upgrader'."""
import argparse
import logging
import logging.handlers
import sys
from typing import Any, Iterable, Optional

import pkg_resources
from halo import Halo

from cou.exceptions import COUException
from cou.logging import setup_logging
from cou.steps import UpgradeStep
from cou.steps.analyze import Analysis
from cou.steps.execute import apply_plan
from cou.steps.plan import generate_plan
from cou.utils import juju_utils

AVAILABLE_OPTIONS = "cas"
VERBOSITY_LEVEL = {0: "ERROR", 1: "WARNING", 2: "INFO", 3: "DEBUG", 4: "NOTSET"}

logger = logging.getLogger(__name__)
progress_indicator = Halo(spinner="line", placement="right")


class CapitalisedHelpFormatter(argparse.HelpFormatter):
    """Capitalize usage prefix."""

    def add_usage(
        self,
        usage: Optional[str],
        actions: Iterable[argparse.Action],
        groups: Iterable[argparse._MutuallyExclusiveGroup],
        prefix: Optional[str] = None,
    ) -> None:
        """Add usage with capitalized prefix.

        :param usage: usage message.
        :type usage: Optional[str]
        :param actions: actions.
        :type actions: Iterable[argparse.Action]
        :param groups: Arguments to be parsed.
        :type groups: Iterable[argparse._MutuallyExclusiveGroup]
        :param prefix: Arguments to be parsed.
        :type prefix: Optional[str]
        """
        if prefix is None:
            prefix = "Usage: "
        super().add_usage(usage, actions, groups, prefix)


def parse_args(args: Any) -> argparse.Namespace:
    """Parse cli arguments.

    :param args: Arguments to be parsed.
    :type args: Any
    :return: Arguments parsed to the cli execution.
    :rtype: argparse.Namespace
    """
    # Configure top level argparser and its options
    parser = argparse.ArgumentParser(
        description="Canonical OpenStack Upgrader(cou) is an application to upgrade Canonical "
        "OpenStack cloud. Application identifies the lowest OpenStack version on the components and "
        "upgrade to the next version.",
        formatter_class=CapitalisedHelpFormatter,
        usage="%(prog)s [options] <command>",
        exit_on_error=False,
        add_help=False,
        allow_abbrev=False,
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        default=argparse.SUPPRESS,
        help="Show version details.",
        version=pkg_resources.require("canonical_openstack_upgrader")[0].version,
    )
    parser.add_argument(
        "--help",
        "-h",
        action="help",
        default=argparse.SUPPRESS,
        help="Show this help message and exit.",
    )

    # Configure subcommand parser
    subparsers = parser.add_subparsers(
        title="Commands",
        dest="command",
        help="For more information about a command, run 'cou help <command>'.",
    )

    # Arg parser for "cou help" sub-command
    help_parser = subparsers.add_parser(
        "help",
        usage="cou help [command]",
    )
    help_parser.add_argument(
        "subcommand",
        nargs="?",
        choices=["plan", "run", "all"],
        default="all",
        type=str,
        help="A sub-command to get information of.",
    )

    # Define common options for subcommands and their child commands
    subcommand_common_opts_parser = argparse.ArgumentParser(add_help=False)
    subcommand_common_opts_parser.add_argument(
        "--model",
        default=None,
        dest="model_name",
        type=str,
        help="Set the model to operate on. If not set it gets the model name in this order:\n"
        "  1 - Environment variable JUJU_MODEL,"
        "  2 - Environment variable MODEL_NAME,"
        "  3 - Current active juju model",
    )
    subcommand_common_opts_parser.add_argument(
        "--parallel",
        help="Run upgrade steps in parallel where possible.",
        default=False,
        action="store_true",
    )

    # quiet and verbose options are mutually exclusive
    group = subcommand_common_opts_parser.add_mutually_exclusive_group()
    group.add_argument(
        "--verbose",
        "-v",
        default=0,
        action="count",
        dest="verbosity",
        help="Increase logging verbosity in STDOUT. Repeat the 'v' in the short option "
        "for more detail. Maximum verbosity is obtained with 4 (or more) "
        "v's, i.e. -vvvv. \nNote that this doesn't affect the verbosity in logfile, "
        "which will always have the maximum verbosity.",
    )
    group.add_argument(
        "--quiet",
        "-q",
        default=False,
        action="store_true",
        dest="quiet",
        help="Disable output in STDOUT.",
    )

    # Define options specific to data-plane child command and make them mutually exclusive
    dp_subparser = argparse.ArgumentParser(add_help=False)
    dp_upgrade_group = dp_subparser.add_mutually_exclusive_group()
    dp_upgrade_group.add_argument(
        "--machine",
        "-m",
        action="append",
        help="Specify machines ids to upgrade.",
        dest="machines",
    )
    dp_upgrade_group.add_argument(
        "--hostname",
        "-n",
        action="append",
        help="Specify machine hostnames to upgrade.",
        dest="hostnames",
    )
    dp_upgrade_group.add_argument(
        "--availability-zone",
        "--az",
        action="append",
        help="Specify availability zones to upgrade.",
        dest="availability_zones",
    )

    # Arg parser for "cou plan" sub-command
    plan_parser = subparsers.add_parser(
        "plan",
        description="Show the steps for upgrading the cloud to the next release.",
        help="Show the steps for upgrading the cloud to the next release.",
        usage="cou plan [options]",
        parents=[subcommand_common_opts_parser],
        formatter_class=CapitalisedHelpFormatter,
    )

    # Create control-plane and data-plane child commands to plan partial upgrades
    plan_subparser = plan_parser.add_subparsers(
        title="Upgrade group",
        dest="upgrade-group",
        help="For more information about a upgrade group, run 'cou plan <upgrade-group>' -h.",
    )
    plan_subparser.add_parser(
        "control-plane",
        description="Show the steps for upgrading the control-plane components.",
        help="Show the steps for upgrading the control-plane components.",
        usage="cou plan control-plane [options]",
        parents=[subcommand_common_opts_parser],
        formatter_class=CapitalisedHelpFormatter,
    )

    plan_subparser.add_parser(
        "data-plane",
        description="Show the steps for upgrading the data-plane components.",
        help="Show the steps for upgrading the data-plane components.",
        usage="cou plan data-plane [options]",
        parents=[subcommand_common_opts_parser, dp_subparser],
        formatter_class=CapitalisedHelpFormatter,
    )

    # Arg parser for "cou run" sub-command and set up common options
    run_args_parser = argparse.ArgumentParser(add_help=False)
    run_args_parser.add_argument(
        "--interactive",
        help="Run upgrade with prompt.",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    run_args_parser.add_argument(
        "--i-really-mean-it",
        help="Run upgrade steps even if they are considered as risky operations (e.g. upgrading "
        "data-plane nodes with non-empty computes).",
        action="store_true",
        default=False,
    )
    run_parser = subparsers.add_parser(
        "run",
        description="Run the cloud upgrade.",
        help="Run the cloud upgrade.",
        usage="cou run [options]",
        parents=[subcommand_common_opts_parser, run_args_parser],
        formatter_class=CapitalisedHelpFormatter,
    )

    # Create control-plane and data-plane child commands to run partial upgrades
    run_subparser = run_parser.add_subparsers(
        title="Upgrade group",
        dest="upgrade-group",
        help="For more information about a upgrade group, run 'cou run <upgrade-group> -h'.",
    )
    run_subparser.add_parser(
        "control-plane",
        description="Run upgrade for the control-plane components.",
        help="Run upgrade for the control-plane components.",
        usage="cou plan control-plane [options]",
        parents=[subcommand_common_opts_parser, run_args_parser],
        formatter_class=CapitalisedHelpFormatter,
    )
    run_subparser.add_parser(
        "data-plane",
        description="Run upgrade for the data-plane components.",
        help="Run upgrade for the data-plane components.",
        usage="cou plan data-plane [options]",
        parents=[
            subcommand_common_opts_parser,
            dp_subparser,
            run_args_parser,
        ],
        formatter_class=CapitalisedHelpFormatter,
    )

    # It no sub-commands or options are given, print help message and exit
    if len(sys.argv[1:]) == 0:
        parser.print_help()
        sys.exit(0)

    try:
        parsed_args = parser.parse_args(args)

        # print help messages for an available sub-command
        if parsed_args.command == "help":
            match parsed_args.subcommand:
                case "run":
                    run_parser.print_help()
                case "plan":
                    plan_parser.print_help()
                case "all":
                    parser.print_help()
            sys.exit(0)

        return parsed_args
    except argparse.ArgumentError as exc:
        print(f"Error parsing arguments: {exc}\n")
        print("See 'cou help' for more information.")
        sys.exit(1)


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
    return VERBOSITY_LEVEL[min(verbosity, 4)]


async def analyze_and_plan(model_name: Optional[str] = None) -> UpgradeStep:
    """Analyze cloud and generate the upgrade plan with steps.

    :param model_name: Model name inputted by user.
    :type model_name: Optional[str]
    :return: Generated upgrade plan.
    :rtype: UpgradeStep
    """
    model_name = model_name or await juju_utils.get_current_model_name()
    logger.info("Using model: %s", model_name)

    progress_indicator.start("Analyzing cloud...")
    analysis_result = await Analysis.create(model_name)
    progress_indicator.succeed()
    logger.info(analysis_result)

    progress_indicator.start("Generating upgrade plan...")
    upgrade_plan = await generate_plan(analysis_result)
    progress_indicator.succeed()

    return upgrade_plan


async def get_upgrade_plan(model_name: Optional[str] = None) -> None:
    """Get upgrade plan and print to console.

    :param model_name: Model name inputted by user.
    :type model_name: Optional[str]
    """
    upgrade_plan = await analyze_and_plan(model_name)
    logger.info(upgrade_plan)
    print(upgrade_plan)  # print plan to console even in quiet mode


async def run_upgrade(
    model_name: Optional[str] = None, interactive: bool = True, quiet: bool = False
) -> None:
    """Run cloud upgrade.

    :param model_name: Model name inputted by user.
    :type model_name: Optional[str]
    :param interactive: Whether to run upgrade interactively.
    :type interactive: bool
    :param quiet: Whether to run upgrade in quiet mode.
    :type quiet: bool
    """
    upgrade_plan = await analyze_and_plan(model_name)
    logger.info(upgrade_plan)

    # don't print plan if in quiet mode
    if not quiet:
        print(upgrade_plan)

    if not interactive:
        progress_indicator.start("Running cloud upgrade...")
        await apply_plan(upgrade_plan, interactive)
        progress_indicator.succeed()
    else:
        await apply_plan(upgrade_plan, interactive)
    print("Upgrade completed.")


async def entrypoint() -> None:
    """Execute 'canonical-openstack-upgrade' command."""
    try:
        args = parse_args(sys.argv[1:])
        # disable progress indicator when in quite mode to suppress its console output
        progress_indicator.enabled = not args.quiet

        progress_indicator.start("Configuring logging...")  # non-persistent progress output
        setup_logging(log_level=get_log_level(quiet=args.quiet, verbosity=args.verbosity))
        progress_indicator.stop()

        match args.command:
            case "plan":
                await get_upgrade_plan(model_name=args.model_name)
            case "run":
                await run_upgrade(
                    model_name=args.model_name, interactive=args.interactive, quiet=args.quiet
                )
    except COUException as exc:
        progress_indicator.fail()
        logger.error(exc)
        sys.exit(1)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Unexpected error occurred")
        logger.exception(exc)
        sys.exit(2)
    finally:
        progress_indicator.stop()
