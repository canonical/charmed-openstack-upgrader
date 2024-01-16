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

from argparse import ArgumentParser
from unittest.mock import patch

import pytest

from cou import commands
from cou.commands import Namespace


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["-h"],
        ["--help"],
        ["help"],
        ["help", "plan"],
        ["help", "upgrade"],
        ["plan", "-h"],
        ["upgrade", "-h"],
        ["plan", "control-plane", "-h"],
        ["plan", "data-plane", "-h"],
        ["upgrade", "control-plane", "-h"],
        ["upgrade", "data-plane", "-h"],
    ],
)
def test_parse_args_help(args):
    """Test printing help messages."""
    with patch(
        "cou.commands.argparse.ArgumentParser.print_help"
    ) as mock_print_help, pytest.raises(SystemExit, match="0"):
        commands.parse_args(args)
        mock_print_help.assert_called_once()


@pytest.mark.parametrize(
    "args",
    [
        ["--quiet", "--verbose"],
        ["--quiet", "-v"],
        ["--quiet", "-vvv"],
    ],
)
def test_parse_args_quiet_verbose_exclusive(args):
    """Test that quiet and verbose options are mutually exclusive."""
    with pytest.raises(SystemExit, match="2"):
        commands.parse_args(args)


@pytest.mark.parametrize(
    "args, expected_namespace",
    [
        (
            ["plan"],
            Namespace(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["plan", "--no-backup"],
            Namespace(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=False,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["plan", "--no-backup", "--quiet"],
            Namespace(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=True,
                backup=False,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["plan", "--model=model_name"],
            Namespace(
                command="plan",
                model_name="model_name",
                verbosity=0,
                quiet=False,
                backup=True,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["plan", "control-plane"],
            Namespace(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                **{"upgrade_group": "control-plane"}
            ),
        ),
        (
            ["plan", "data-plane"],
            Namespace(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                machines=None,
                hostnames=None,
                availability_zones=None,
                **{"upgrade_group": "data-plane"}
            ),
        ),
        (
            ["plan", "control-plane", "--verbose"],
            Namespace(
                command="plan",
                model_name=None,
                verbosity=1,
                quiet=False,
                backup=True,
                **{"upgrade_group": "control-plane"}
            ),
        ),
        (
            ["plan", "data-plane", "--machine=1", "-m=2,3"],
            Namespace(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                machines=["1", "2,3"],
                hostnames=None,
                availability_zones=None,
                **{"upgrade_group": "data-plane"}
            ),
        ),
        (
            ["plan", "data-plane", "--quiet", "--availability-zone=1", "--az=2,3"],
            Namespace(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=True,
                backup=True,
                machines=None,
                hostnames=None,
                availability_zones=["1", "2,3"],
                **{"upgrade_group": "data-plane"}
            ),
        ),
        (
            ["plan", "data-plane", "--hostname=1", "-n=2,3"],
            Namespace(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                machines=None,
                hostnames=["1", "2,3"],
                availability_zones=None,
                **{"upgrade_group": "data-plane"}
            ),
        ),
    ],
)
def test_parse_args_plan(args, expected_namespace):
    """Test parsing 'plan' subcommand and its arguments/options."""
    parsed_args = commands.parse_args(args)

    assert parsed_args == expected_namespace


@pytest.mark.parametrize(
    "args, expected_namespace",
    [
        (
            ["upgrade"],
            Namespace(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["upgrade", "--no-backup"],
            Namespace(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=False,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["upgrade", "--no-backup", "--quiet"],
            Namespace(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=True,
                auto_approve=False,
                backup=False,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["upgrade", "--model=model_name"],
            Namespace(
                command="upgrade",
                model_name="model_name",
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["upgrade", "control-plane"],
            Namespace(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                **{"upgrade_group": "control-plane"}
            ),
        ),
        (
            ["upgrade", "data-plane"],
            Namespace(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                machines=None,
                hostnames=None,
                availability_zones=None,
                **{"upgrade_group": "data-plane"}
            ),
        ),
        (
            ["upgrade", "control-plane", "--verbose"],
            Namespace(
                command="upgrade",
                model_name=None,
                verbosity=1,
                quiet=False,
                auto_approve=False,
                backup=True,
                **{"upgrade_group": "control-plane"}
            ),
        ),
        (
            ["upgrade", "data-plane", "--machine=1", "-m=2,3"],
            Namespace(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                machines=["1", "2,3"],
                hostnames=None,
                availability_zones=None,
                **{"upgrade_group": "data-plane"}
            ),
        ),
        (
            ["upgrade", "data-plane", "--quiet", "--availability-zone=1", "--az=2,3"],
            Namespace(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=True,
                auto_approve=False,
                backup=True,
                machines=None,
                hostnames=None,
                availability_zones=["1", "2,3"],
                **{"upgrade_group": "data-plane"}
            ),
        ),
        (
            ["upgrade", "data-plane", "--hostname=1", "-n=2,3"],
            Namespace(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                machines=None,
                hostnames=["1", "2,3"],
                availability_zones=None,
                **{"upgrade_group": "data-plane"}
            ),
        ),
        (
            ["upgrade", "data-plane", "--auto-approve", "--hostname=1", "-n=2,3"],
            Namespace(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=True,
                backup=True,
                machines=None,
                hostnames=["1", "2,3"],
                availability_zones=None,
                **{"upgrade_group": "data-plane"}
            ),
        ),
    ],
)
def test_parse_args_upgrade(args, expected_namespace):
    """Test parsing 'run' subcommand and its arguments/options."""
    parsed_args = commands.parse_args(args)

    assert parsed_args == expected_namespace


@pytest.mark.parametrize(
    "args",
    [
        ["upgrade", "data-plane", "--machine 1", "--az 2"],
        ["upgrade", "data-plane", "--hostname 1", "-m 2"],
        ["upgrade", "data-plane", "--availability-zone 1", "-n 2"],
        ["upgrade", "data-plane", "--machine 1", "-n 2"],
        ["upgrade", "data-plane", "--az 1", "-m 2"],
        ["upgrade", "data-plane", "-m 1", "-n 2"],
    ],
)
def test_parse_args_dataplane_exclusive_options(args):
    """Test parsing mutually exclusive data-plane specific options."""
    with pytest.raises(SystemExit, match="2"):
        commands.parse_args(args)


@pytest.mark.parametrize("args", [["foo"], ["--bar"]])
def test_parse_args_raise_exception(args):
    """Test parsing unknown arguments."""
    with pytest.raises(SystemExit, match="2"):
        commands.parse_args(args)


def test_capitalize_usage_prefix():
    """Test add usage with capitalized prefix."""
    parser = ArgumentParser(formatter_class=commands.CapitalizeHelpFormatter)
    usage = parser.format_usage()

    assert usage.startswith("Usage: ")


def test_capitalize_section_title():
    """Test capitalizing option's section title."""
    parser = ArgumentParser(formatter_class=commands.CapitalizeHelpFormatter)
    help_text = parser.format_help()
    section_title = ""
    for line in help_text.splitlines():
        if line.lower().startswith("options"):
            section_title = line
            break

    assert section_title.startswith("Options")


def test_capitalize_help_message():
    """Test capitalizing help message."""
    parser = ArgumentParser(formatter_class=commands.CapitalizeHelpFormatter)
    help_message = parser.format_help()

    assert "Show this help message and exit." in help_message
