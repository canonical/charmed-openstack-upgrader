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

"""Command line arguments parsing for 'charmed-openstack-upgrader'."""
import argparse
from typing import Iterable, Optional

import pkg_resources


class CapitalizeHelpFormatter(argparse.RawTextHelpFormatter):
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

    def start_section(self, heading: Optional[str]) -> None:
        """Capitalize the title of the options group.

        :param heading: heading of an argument group.
        :type heading: Optional[str]
        """
        if heading == "options":
            heading = "Options"
        super().start_section(heading)

    def add_argument(self, action: argparse.Action) -> None:
        """Capitalize the help message for -h/--help.

        :param action: group heading.
        :type action: argparse.Action
        """
        if action.option_strings and (
            "-h" in action.option_strings or "--help" in action.option_strings
        ):
            action.help = "Show this help message and exit."
        super().add_argument(action)


def get_subcommand_common_opts_parser() -> argparse.ArgumentParser:
    """Create a shared parser for options specific to subcommands.

    :return: a parser groups options commonly shared by subcommands
    :rtype: argparse.ArgumentParser
    """
    # Define common options for subcommands and their children commands
    subcommand_common_opts_parser = argparse.ArgumentParser(add_help=False)
    subcommand_common_opts_parser.add_argument(
        "--model",
        default=None,
        dest="model_name",
        type=str,
        help="Set the model to operate on. If unset, the model name will be determined by "
        "inspecting the environment as follows:\n"
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
        help="Increase logging verbosity in STDOUT. Multiple 'v's yield progressively "
        "more detail (up to 4).\nNote that this doesn't affect the verbosity in logfile, "
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

    return subcommand_common_opts_parser


def get_dataplane_common_opts_parser() -> argparse.ArgumentParser:
    """Create a shared parser for options specific to data-plane.

    :return: a parser groups options specific to data-plane
    :rtype: argparse.ArgumentParser
    """
    # Define options specific to data-plane child command and make them mutually exclusive
    dp_subparser = argparse.ArgumentParser(add_help=False)
    dp_upgrade_group = dp_subparser.add_mutually_exclusive_group()
    dp_upgrade_group.add_argument(
        "--machine",
        "-m",
        action="append",
        help="Specify machine id(s) to upgrade. This option accepts a single machine id as well "
        "as a stringified comma-separated list for multiple machines. This option can be used "
        "repetitively.",
        dest="machines",
        type=str,
    )
    dp_upgrade_group.add_argument(
        "--hostname",
        "-n",
        action="append",
        help="Specify machine hostnames(s) to upgrade. This option accepts a single machine "
        "hostname as well as a stringified comma-separated list for multiple machines. This "
        "option can be used repetitively.",
        dest="hostnames",
        type=str,
    )
    dp_upgrade_group.add_argument(
        "--availability-zone",
        "--az",
        action="append",
        help="Specify availability zone(s) to upgrade. This option accepts a single availability "
        "zone as well as a stringified comma-separated list for multiple AZs. This option can be "
        "used repetitively.",
        dest="availability_zones",
        type=str,
    )
    return dp_subparser


def create_plan_subparser(
    subparsers: argparse._SubParsersAction,
    subcommand_common_opts_parser: argparse.ArgumentParser,
    dp_parser: argparse.ArgumentParser,
) -> None:
    """Create and configure 'plan' subcommand parser.

    :param subparsers: subparsers that plan subparser belongs to
    :type subparsers: argparse.ArgumentParser
    :param subcommand_common_opts_parser parser groups options commonly shared by subcommands
    :type subcommand_common_opts_parser: argparse.ArgumentParser
    :param dp_parser: a parser groups options specific to data-plane
    :type dp_parser: argparse.ArgumentParser
    """
    # Arg parser for "cou plan" sub-command
    plan_parser = subparsers.add_parser(
        "plan",
        description="Show the steps COU will take to upgrade the cloud to the next release. "
        "If upgrade-group is unspecified, plan upgrade for the entire cloud",
        help="Show the steps COU will take to upgrade the cloud to the next release.",
        usage="cou plan [options]",
        parents=[subcommand_common_opts_parser],
        formatter_class=CapitalizeHelpFormatter,
    )

    # Create control-plane and data-plane child commands to plan partial upgrades
    plan_subparser = plan_parser.add_subparsers(
        title="Upgrade groups",
        dest="upgrade-group",
        help="For more information about a upgrade group, run 'cou plan <upgrade-group>' -h.",
    )
    plan_subparser.add_parser(
        "control-plane",
        description="Show the steps for upgrading the control-plane components.",
        help="Show the steps for upgrading the control-plane components.",
        usage="cou plan control-plane [options]",
        parents=[subcommand_common_opts_parser],
        formatter_class=CapitalizeHelpFormatter,
    )
    plan_subparser.add_parser(
        "data-plane",
        description="Show the steps for upgrading the data-plane components. This is possible "
        "only if control-plane has been fully upgrade. Otherwise an error will be thrown.",
        help="Show the steps for upgrading the data-plane components. This is possible "
        "only if control-plane has been fully upgrade. Otherwise an error will be thrown.",
        usage="cou plan data-plane [options]",
        parents=[subcommand_common_opts_parser, dp_parser],
        formatter_class=CapitalizeHelpFormatter,
    )


def create_run_subparser(
    subparsers: argparse._SubParsersAction,
    subcommand_common_opts_parser: argparse.ArgumentParser,
    dp_parser: argparse.ArgumentParser,
) -> None:
    """Create and configure 'run' subcommand parser.

    :param subparsers: subparsers that plan subparser belongs to
    :type subparsers: argparse.ArgumentParser
    :param subcommand_common_opts_parser parser groups options commonly shared by subcommands
    :type subcommand_common_opts_parser: argparse.ArgumentParser
    :param dp_parser: a parser groups options specific to data-plane
    :type dp_parser: argparse.ArgumentParser
    """
    # Arg parser for "cou run" sub-command and set up common options
    run_args_parser = argparse.ArgumentParser(add_help=False)
    run_args_parser.add_argument(
        "--interactive",
        help="Run upgrade with prompt.",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    run_parser = subparsers.add_parser(
        "run",
        description="Run the cloud upgrade. If upgrade-group is unspecified, perform "
        "upgrade for the entire cloud",
        help="Run the cloud upgrade.",
        usage="cou run [options]",
        parents=[subcommand_common_opts_parser, run_args_parser],
        formatter_class=CapitalizeHelpFormatter,
    )

    # Create control-plane and data-plane child commands to run partial upgrades
    run_subparser = run_parser.add_subparsers(
        title="Upgrade group",
        dest="upgrade-group",
        help="For more information about an upgrade group, run 'cou run <upgrade-group> -h'.",
    )
    run_subparser.add_parser(
        "control-plane",
        description="Run upgrade for the control-plane components.",
        help="Run upgrade for the control-plane components.",
        usage="cou plan control-plane [options]",
        parents=[subcommand_common_opts_parser, run_args_parser],
        formatter_class=CapitalizeHelpFormatter,
    )
    run_subparser.add_parser(
        "data-plane",
        description="Run upgrade for the data-plane components. This is possible only if "
        "control-plane has been fully upgrade. Otherwise an error will be thrown.",
        help="Run upgrade for the data-plane components. This is possible only if "
        "control-plane has been fully upgrade. Otherwise an error will be thrown.",
        usage="cou plan data-plane [options]",
        parents=[
            subcommand_common_opts_parser,
            dp_parser,
            run_args_parser,
        ],
        formatter_class=CapitalizeHelpFormatter,
    )


def create_subparsers(parser: argparse.ArgumentParser) -> argparse._SubParsersAction:
    """Create and configure subparsers.

    :param parsers: the top level parser to create subparsers for,
    :type parsers: argparse.ArgumentParser
    :return subparsers: configured subparsers
    :type subparsers: argparse.ArgumentParser
    """
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

    subcommand_common_opts_parser = get_subcommand_common_opts_parser()
    dp_parser = get_dataplane_common_opts_parser()
    create_plan_subparser(subparsers, subcommand_common_opts_parser, dp_parser)
    create_run_subparser(subparsers, subcommand_common_opts_parser, dp_parser)

    return subparsers


def parse_args() -> tuple[argparse.ArgumentParser, argparse._SubParsersAction]:
    """Parse cli arguments.

    :return: Arguments parser.
    :rtype: argparse.ArgumentParser
    :return: Arguments subparsers.
    :rtype: argparse._SubParsersAction
    """
    # Configure top level argparser and its options
    parser = argparse.ArgumentParser(
        description="Charmed OpenStack Upgrader (cou) is an application to upgrade a Canonical "
        "distribution of Charmed OpenStack. The application auto-detects the version of the "
        "running cloud and will propose an upgrade to the next available version.",
        formatter_class=CapitalizeHelpFormatter,
        usage="%(prog)s [options] <command>",
        exit_on_error=False,
        add_help=True,
        allow_abbrev=False,
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        default=argparse.SUPPRESS,
        help="Show version details.",
        version=pkg_resources.require("charmed_openstack_upgrader")[0].version,
    )

    # Configure subparsers for subcommands and their options
    subparsers = create_subparsers(parser)

    return parser, subparsers
