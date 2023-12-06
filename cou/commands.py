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


def get_common_opts_parser() -> argparse.ArgumentParser:
    """Create a shared parser for options specific to subcommands.

    :return: a parser groups options commonly shared by subcommands
    :rtype: argparse.ArgumentParser
    """
    # Define common options for subcommands and their children commands
    common_opts_parser = argparse.ArgumentParser(add_help=False)
    common_opts_parser.add_argument(
        "--model",
        default=None,
        dest="model_name",
        type=str,
        help="Set the model to operate on.\nIf not set, the currently active Juju model will "
        "be used.",
    )
    common_opts_parser.add_argument(
        "--backup",
        help="Include database backup step before cloud upgrade.\n"
        "Default to enabling database backup.",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    common_opts_parser.add_argument(
        "--interactive",
        help="Run upgrade with prompt.\nThis option should be used with '--run' option.",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    common_opts_parser.add_argument(
        "--parallel",
        help="Run upgrade steps in parallel where possible.\nThis option should be used "
        "with '--run' option.",
        default=False,
        action="store_true",
    )

    # quiet and verbose options are mutually exclusive
    verbosity_group = common_opts_parser.add_mutually_exclusive_group()
    verbosity_group.add_argument(
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
    verbosity_group.add_argument(
        "--quiet",
        "-q",
        default=False,
        action="store_true",
        dest="quiet",
        help="Disable output in STDOUT.",
    )

    # run and dry-run options are mutually exclusive
    action_group = common_opts_parser.add_mutually_exclusive_group()
    action_group.add_argument(
        "--run",
        default=False,
        action="store_true",
        dest="run",
        help="Proceed with the upgrade after the plan is generated.",
    )
    action_group.add_argument(
        "--dry-run",
        default=False,
        action="store_true",
        dest="dry_run",
        help="Generate upgrade plan and exit.",
    )

    return common_opts_parser


def create_controlplane_subparser(
    subparsers: argparse._SubParsersAction,
    common_opts_parser: argparse.ArgumentParser,
) -> None:
    """Create and configure 'plan' subcommand parser.

    :param subparsers: subparsers that plan subparser belongs to
    :type subparsers: argparse.ArgumentParser
    :param common_opts_parser: parser groups options commonly shared across commands
    :type common_opts_parser: argparse.ArgumentParser
    """
    # Arg parser for "cou control-plane" sub-command
    subparsers.add_parser(
        "control-plane",
        description="Run the control-plane upgrade.",
        help="Run the control-plane upgrade.",
        usage="cou control-plane [options]",
        parents=[common_opts_parser],
        formatter_class=CapitalizeHelpFormatter,
    )


def create_dataplane_subparser(
    subparsers: argparse._SubParsersAction,
    common_opts_parser: argparse.ArgumentParser,
) -> None:
    """Create and configure 'run' subcommand parser.

    :param subparsers: subparsers that plan subparser belongs to
    :type subparsers: argparse.ArgumentParser
    :param common_opts_parser: parser groups options commonly shared across commands
    :type common_opts_parser: argparse.ArgumentParser
    """
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

    subparsers.add_parser(
        "data-plane",
        description="Run the data-plane upgrade.",
        help="Run the data-plane upgrade.",
        usage="cou data-plane [options]",
        parents=[common_opts_parser, dp_subparser],
        formatter_class=CapitalizeHelpFormatter,
    )


def create_subparsers(
    parser: argparse.ArgumentParser, common_opts_parser: argparse.ArgumentParser
) -> argparse._SubParsersAction:
    """Create and configure subparsers.

    :param parser: the top level parser to create subparsers for
    :type parser: argparse.ArgumentParser
    :param common_opts_parser: parser groups options commonly shared across commands
    :type common_opts_parser: argparse.ArgumentParser
    :return: configured subparsers
    :rtype: argparse._SubParsersAction
    """
    # Configure subcommand parser
    subparsers = parser.add_subparsers(
        title="Sub-commands",
        dest="command",
        help="For more information about a sub-command, run 'cou help <sub-command>'.",
    )

    # Arg parser for "cou help" sub-command
    help_parser = subparsers.add_parser(
        "help",
        usage="cou help [sub-command]",
    )
    help_parser.add_argument(
        "subcommand",
        nargs="?",
        # TODO(txiao): Add data-plane to the choices when its upgrade is supported
        choices=["control-plane", "all"],
        default="all",
        type=str,
        help="A sub-command to get information of.",
    )

    create_controlplane_subparser(subparsers, common_opts_parser)
    # TODO(txiao): Call `create_dataplane_subparser` function when data-plane upgrade is supported
    # create_dataplane_subparser(subparsers, common_opts_parser)

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
    common_opts_parser = get_common_opts_parser()
    parser = argparse.ArgumentParser(
        description="Charmed OpenStack Upgrader (cou) is an application to upgrade\na Canonical "
        "distribution of Charmed OpenStack.\nThe application auto-detects the version of the "
        "running cloud\nand will propose an upgrade to the next available version.",
        formatter_class=CapitalizeHelpFormatter,
        usage="%(prog)s [options] <sub-command>",
        exit_on_error=False,
        add_help=True,
        allow_abbrev=False,
        parents=[common_opts_parser],
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
    subparsers = create_subparsers(parser, common_opts_parser)

    try:
        parsed_args = parser.parse_args(args)

        # print help messages for an available sub-command
        if parsed_args.command == "help":
            match parsed_args.subcommand:
                case "control-plane":
                    subparsers.choices["control-plane"].print_help()
                # TODO(txiao): Enable help message for data-plane
                # case "data-plane":
                #     subparsers.choices["data-plane"].print_help()
                case "all":
                    parser.print_help()
            parser.exit()

        return parsed_args
    except argparse.ArgumentError as exc:
        parser.error(
            message=f"Error parsing arguments: {exc}\nSee 'cou help' for more information."
        )
