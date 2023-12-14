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
from typing import Any, Iterable, Optional

import pkg_resources


class CapitalizeHelpFormatter(argparse.RawTextHelpFormatter):
    """Capitalize message prefix."""

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
        help="Set the model to operate on.\nIf not set, the currently active Juju model will "
        "be used.",
    )
    subcommand_common_opts_parser.add_argument(
        "--backup",
        help="Include database backup step before cloud upgrade.\n"
        "Default to enabling database backup.",
        action=argparse.BooleanOptionalAction,
        default=True,
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
        "more detail (up to 4).\nNote that by default the logfile will include standard "
        "logs from juju and websockets, as well as debug logs from all other modules. "
        "To also include the debug level logs from juju and websockets modules, use the "
        "maximum verbosity.",
    )
    group.add_argument(
        "--quiet",
        "-q",
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
        help="Specify machine id(s) to upgrade.\nThis option accepts a single machine id as well "
        "as a stringified comma-separated list of ids,\nand can be repeated multiple times.",
        dest="machines",
        type=str,
    )
    dp_upgrade_group.add_argument(
        "--hostname",
        "-n",
        action="append",
        help="Specify machine hostnames(s) to upgrade.\nThis option accepts a single hostname as "
        "well as a stringified comma-separated list of hostnames,\nand can be repeated multiple "
        "times.",
        dest="hostnames",
        type=str,
    )
    dp_upgrade_group.add_argument(
        "--availability-zone",
        "--az",
        action="append",
        help="Specify availability zone(s) to upgrade.\nThis option accepts a single "
        "availability zone as well as a stringified comma-separated list of AZs,\n"
        "and can be repeated multiple times.",
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

    :param subparsers: subparsers that 'plan' subparser belongs to
    :type subparsers: argparse.ArgumentParser
    :param subcommand_common_opts_parser: parser groups options commonly shared by subcommands
    :type subcommand_common_opts_parser: argparse.ArgumentParser
    :param dp_parser: a parser groups options specific to data-plane
    :type dp_parser: argparse.ArgumentParser
    """
    # Arg parser for "cou plan" sub-command
    plan_parser = subparsers.add_parser(
        "plan",
        description="Show the steps COU will take to upgrade the cloud to the next release.",
        # TODO(txiao): Replace the description with the following message after data-plane upgrade
        # is implemented
        # description="Show the steps COU will take to upgrade the cloud to the next release.\n"
        # "If upgrade-group is unspecified, plan upgrade for the whole cloud.",
        help="Show the steps COU will take to upgrade the cloud to the next release.",
        usage="cou plan [options]",
        parents=[subcommand_common_opts_parser],
        formatter_class=CapitalizeHelpFormatter,
    )

    # Create control-plane and data-plane child commands to plan partial upgrades
    plan_subparser = plan_parser.add_subparsers(
        title="Upgrade groups",
        dest="upgrade_group",
        help=argparse.SUPPRESS,
        # TODO(txiao): Add the following help message after data-plane upgrade is implemented
        # help="For more information about a upgrade group, run 'cou plan <upgrade-group>' -h.",
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
        description="Show the steps for upgrading the data-plane components.\nThis is possible "
        "only if control-plane has been fully upgraded,\notherwise an error will be thrown.",
        help="Show the steps for upgrading the data-plane components.\nThis is possible "
        "only if control-plane has been fully upgraded,\notherwise an error will be thrown.",
        usage="cou plan data-plane [options]",
        parents=[subcommand_common_opts_parser, dp_parser],
        formatter_class=CapitalizeHelpFormatter,
    )


def create_upgrade_subparser(
    subparsers: argparse._SubParsersAction,
    subcommand_common_opts_parser: argparse.ArgumentParser,
    dp_parser: argparse.ArgumentParser,
) -> None:
    """Create and configure 'upgrade' subcommand parser.

    :param subparsers: subparsers that 'upgrade' subparser belongs to
    :type subparsers: argparse.ArgumentParser
    :param subcommand_common_opts_parser: parser groups options commonly shared by subcommands
    :type subcommand_common_opts_parser: argparse.ArgumentParser
    :param dp_parser: a parser groups options specific to data-plane
    :type dp_parser: argparse.ArgumentParser
    """
    # Arg parser for "cou upgrade" sub-command and set up common options
    upgrade_args_parser = argparse.ArgumentParser(add_help=False)
    upgrade_args_parser.add_argument(
        "--auto-approve",
        help="Automatically approve and continue with each upgrade step without prompt.",
        action="store_true",
        dest="auto_approve",
    )
    upgrade_parser = subparsers.add_parser(
        "upgrade",
        description="Run the cloud upgrade.",
        # TODO(txiao): Replace the description with the following message after data-plane upgrade
        # is implemented
        # description="Run the cloud upgrade.\nIf upgrade-group is unspecified, "
        # "upgrade the whole cloud.",
        help="Run the cloud upgrade.",
        usage="cou upgrade [options]",
        parents=[subcommand_common_opts_parser, upgrade_args_parser],
        formatter_class=CapitalizeHelpFormatter,
    )

    # Create control-plane and data-plane child commands to run partial upgrades
    upgrade_subparser = upgrade_parser.add_subparsers(
        title="Upgrade group",
        dest="upgrade_group",
        help=argparse.SUPPRESS,
        # TODO(txiao): Add the following help message after data-plane upgrade is implemented
        # help="For more information about an upgrade group, run 'cou upgrade <upgrade-group> -h'",
    )
    upgrade_subparser.add_parser(
        "control-plane",
        description="Run upgrade for the control-plane components.",
        help="Run upgrade for the control-plane components.",
        usage="cou plan control-plane [options]",
        parents=[subcommand_common_opts_parser, upgrade_args_parser],
        formatter_class=CapitalizeHelpFormatter,
    )
    upgrade_subparser.add_parser(
        "data-plane",
        description="Run upgrade for the data-plane components.\nThis is possible only if "
        "control-plane has been fully upgraded,\notherwise an error will be thrown.",
        help="Run upgrade for the data-plane components.\nThis is possible only if "
        "control-plane has been fully upgraded,\notherwise an error will be thrown.",
        usage="cou plan data-plane [options]",
        parents=[
            subcommand_common_opts_parser,
            dp_parser,
            upgrade_args_parser,
        ],
        formatter_class=CapitalizeHelpFormatter,
    )


def create_subparsers(parser: argparse.ArgumentParser) -> argparse._SubParsersAction:
    """Create and configure subparsers.

    :param parser: the top level parser to create subparsers for,
    :type parser: argparse.ArgumentParser
    :return: configured subparsers
    :rtype: argparse._SubParsersAction
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
        choices=["plan", "upgrade"],
        type=str,
        help="A sub-command to get information of.",
    )

    subcommand_common_opts_parser = get_subcommand_common_opts_parser()
    dp_parser = get_dataplane_common_opts_parser()
    create_plan_subparser(subparsers, subcommand_common_opts_parser, dp_parser)
    create_upgrade_subparser(subparsers, subcommand_common_opts_parser, dp_parser)

    return subparsers


def parse_args(args: Any) -> argparse.Namespace:  # pylint: disable=inconsistent-return-statements
    """Parse cli arguments.

    :param args: Arguments parser.
    :type args: Any
    :return: argparse.Namespace
    :rtype: argparse.Namespace
    :raises argparse.ArgumentError: Unexpected arguments input.
    """
    # Configure top level argparser and its options
    parser = argparse.ArgumentParser(
        description="Charmed OpenStack Upgrader (cou) is an application to upgrade\na Canonical "
        "distribution of Charmed OpenStack.\nThe application auto-detects the version of the "
        "running cloud\nand will propose an upgrade to the next available version.",
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

    # It no sub-commands or options are given, print help message and exit
    if len(args) == 0 or (len(args) == 1 and args[0] == "help"):
        parser.print_help()
        parser.exit()

    try:
        parsed_args = parser.parse_args(args)

        # print help messages for an available sub-command
        if parsed_args.command == "help":
            match parsed_args.subcommand:
                case "plan":
                    subparsers.choices["plan"].print_help()
                case "upgrade":
                    subparsers.choices["upgrade"].print_help()
            parser.exit()

        return parsed_args
    except argparse.ArgumentError as exc:
        parser.error(
            message=f"Error parsing arguments: {exc}\nSee 'cou help' for more information."
        )
