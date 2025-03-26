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

from argparse import ArgumentParser, ArgumentTypeError
from unittest.mock import ANY, patch

import pytest

from cou import commands
from cou.commands import CLIargs


@pytest.mark.parametrize("auto_approve, expected_result", [(True, False), (False, True)])
def test_cliargs_prompt(auto_approve, expected_result):
    args = CLIargs(command="foo", auto_approve=auto_approve)
    assert args.prompt is expected_result


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
        ["plan", "hypervisors", "-h"],
        ["upgrade", "control-plane", "-h"],
        ["upgrade", "data-plane", "-h"],
        ["upgrade", "hypervisors", "-h"],
    ],
)
# NOTE: When we update to use python > 3.10,
# use the wraps arg to patch (`wraps=ArgumentParser.exit`)
# and remove the side_effect to the exit mock.
# Likewise for patching ArgumentParser.error.
# With python <= 3.10, we can't use autospec with wraps:
# https://github.com/python/cpython/issues/75988
@patch(
    "cou.commands.argparse.ArgumentParser.print_help",
    autospec=True,
)
@patch("cou.commands.argparse.ArgumentParser.exit", autospec=True)
def test_parse_args_help(mock_exit, mock_print_help, args):
    """Test printing help messages."""
    mock_exit.side_effect = SystemExit
    with pytest.raises(SystemExit):
        commands.parse_args(args)
    mock_print_help.assert_called_once()
    mock_exit.assert_called_once_with(ANY)


@pytest.mark.parametrize(
    "args",
    [
        ["plan", "--quiet", "--verbose"],
        ["upgrade", "--quiet", "-v"],
        ["plan", "--quiet", "-vvv"],
    ],
)
@patch("cou.commands.argparse.ArgumentParser.error", autospec=True)
def test_parse_args_quiet_verbose_exclusive(mock_error, args):
    """Test that quiet and verbose options are mutually exclusive."""
    mock_error.side_effect = SystemExit
    with pytest.raises(SystemExit):
        commands.parse_args(args)

    mock_error.assert_called_once_with(
        ANY, "argument --verbose/-v: not allowed with argument --quiet/-q"
    )


@pytest.mark.parametrize(
    "args, expected_cliargs",
    [
        (
            ["plan"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=False,
                archive_batch_size=1000,
                archive=True,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["plan", "--no-backup"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=False,
                force=False,
                archive_batch_size=1000,
                archive=True,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["plan", "--no-backup", "--quiet"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=True,
                backup=False,
                force=False,
                archive_batch_size=1000,
                archive=True,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["plan", "--no-backup", "--quiet", "--force"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=True,
                backup=False,
                force=True,
                archive_batch_size=1000,
                archive=True,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["plan", "--no-archive"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=False,
                archive_batch_size=1000,
                archive=False,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["plan", "--archive"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=False,
                archive_batch_size=1000,
                archive=True,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["plan", "--purge"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=False,
                purge=True,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["plan", "--purge", "--purge-before-date", "2000-01-02"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=False,
                purge=True,
                purge_before="2000-01-02",
                **{"upgrade_group": None}
            ),
        ),
        (
            ["plan", "--purge", "--purge-before-date", "2000-01-02 03:04"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=False,
                purge=True,
                purge_before="2000-01-02 03:04",
                **{"upgrade_group": None}
            ),
        ),
        (
            ["plan", "--purge", "--purge-before-date", "2000-01-02 03:04:05"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=False,
                purge=True,
                purge_before="2000-01-02 03:04:05",
                **{"upgrade_group": None}
            ),
        ),
        (
            ["plan", "--archive-batch-size", "564"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=False,
                archive_batch_size=564,
                archive=True,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["plan", "--model=model_name"],
            CLIargs(
                command="plan",
                model_name="model_name",
                verbosity=0,
                quiet=False,
                backup=True,
                force=False,
                archive_batch_size=1000,
                archive=True,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["plan", "control-plane"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=False,
                archive_batch_size=1000,
                archive=True,
                **{"upgrade_group": "control-plane"}
            ),
        ),
        (
            ["plan", "data-plane"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=False,
                archive_batch_size=1000,
                archive=True,
                machines=None,
                availability_zones=None,
                **{"upgrade_group": "data-plane"}
            ),
        ),
        (
            ["plan", "hypervisors"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=False,
                archive_batch_size=1000,
                archive=True,
                machines=None,
                availability_zones=None,
                **{"upgrade_group": "hypervisors"}
            ),
        ),
        (
            ["plan", "data-plane", "--force"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=True,
                archive_batch_size=1000,
                archive=True,
                machines=None,
                availability_zones=None,
                **{"upgrade_group": "data-plane"}
            ),
        ),
        (
            ["plan", "hypervisors", "--force"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=True,
                archive_batch_size=1000,
                archive=True,
                machines=None,
                availability_zones=None,
                **{"upgrade_group": "hypervisors"}
            ),
        ),
        (
            ["plan", "control-plane", "--verbose"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=1,
                quiet=False,
                backup=True,
                force=False,
                archive_batch_size=1000,
                archive=True,
                **{"upgrade_group": "control-plane"}
            ),
        ),
        (
            ["plan", "hypervisors", "--machine=1", "-m=2,3"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=False,
                archive_batch_size=1000,
                archive=True,
                machines={"1", "2", "3"},
                availability_zones=None,
                **{"upgrade_group": "hypervisors"}
            ),
        ),
        (
            ["plan", "hypervisors", "--machine=1", "-m=2,3", "--force"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=True,
                archive_batch_size=1000,
                archive=True,
                machines={"1", "2", "3"},
                availability_zones=None,
                **{"upgrade_group": "hypervisors"}
            ),
        ),
        (
            ["plan", "hypervisors", "--quiet", "--availability-zone=1", "--az=2,3"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=True,
                backup=True,
                force=False,
                archive_batch_size=1000,
                archive=True,
                machines=None,
                availability_zones={"1", "2", "3"},
                **{"upgrade_group": "hypervisors"}
            ),
        ),
        (
            ["plan", "hypervisors", "--force", "--quiet", "--availability-zone=1", "--az=2,3"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=True,
                backup=True,
                force=True,
                archive_batch_size=1000,
                archive=True,
                machines=None,
                availability_zones={"1", "2", "3"},
                **{"upgrade_group": "hypervisors"}
            ),
        ),
        (
            # repetitive machine 3
            ["plan", "hypervisors", "--machine=1,2,3", "--force", "-m=3,4"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=True,
                archive_batch_size=1000,
                archive=True,
                machines={"1", "2", "3", "4"},
                availability_zones=None,
                **{"upgrade_group": "hypervisors"}
            ),
        ),
    ],
)
def test_parse_args_plan(args, expected_cliargs):
    """Test parsing 'plan' subcommand and its arguments/options."""
    parsed_args = commands.parse_args(args)

    assert parsed_args == expected_cliargs


@pytest.mark.parametrize(
    "args, expected_cliargs",
    [
        (
            ["upgrade"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=False,
                archive_batch_size=1000,
                archive=True,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["upgrade", "--no-backup"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=False,
                force=False,
                archive_batch_size=1000,
                archive=True,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["upgrade", "--no-backup", "--quiet"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=True,
                auto_approve=False,
                backup=False,
                force=False,
                archive_batch_size=1000,
                archive=True,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["upgrade", "--force", "--no-backup", "--quiet"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=True,
                auto_approve=False,
                backup=False,
                force=True,
                archive_batch_size=1000,
                archive=True,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["upgrade", "--no-archive"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=False,
                archive_batch_size=1000,
                archive=False,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["upgrade", "--archive"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=False,
                archive_batch_size=1000,
                archive=True,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["upgrade", "--archive-batch-size", "564"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=False,
                archive_batch_size=564,
                archive=True,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["upgrade", "--purge"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=False,
                purge=True,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["upgrade", "--purge", "--purge-before-date", "2000-01-02 03:04:05"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=False,
                purge=True,
                purge_before="2000-01-02 03:04:05",
                **{"upgrade_group": None}
            ),
        ),
        (
            ["upgrade", "--model=model_name"],
            CLIargs(
                command="upgrade",
                model_name="model_name",
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=False,
                archive_batch_size=1000,
                archive=True,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["upgrade", "control-plane"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=False,
                archive_batch_size=1000,
                archive=True,
                **{"upgrade_group": "control-plane"}
            ),
        ),
        (
            ["upgrade", "control-plane", "--force"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=True,
                archive_batch_size=1000,
                archive=True,
                **{"upgrade_group": "control-plane"}
            ),
        ),
        (
            ["upgrade", "data-plane"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=False,
                archive_batch_size=1000,
                archive=True,
                machines=None,
                availability_zones=None,
                **{"upgrade_group": "data-plane"}
            ),
        ),
        # NOTE(gabrielcocenza) Without the argparse.SUPPRESS, this sequence
        # wouldn't be possible.
        (
            ["upgrade", "--force", "data-plane"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=True,
                archive_batch_size=1000,
                archive=True,
                machines=None,
                availability_zones=None,
                **{"upgrade_group": "data-plane"}
            ),
        ),
        (
            ["upgrade", "--no-backup", "data-plane"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=False,
                force=False,
                archive_batch_size=1000,
                archive=True,
                machines=None,
                availability_zones=None,
                **{"upgrade_group": "data-plane"}
            ),
        ),
        (
            ["upgrade", "--model", "my_model", "data-plane"],
            CLIargs(
                command="upgrade",
                model_name="my_model",
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=False,
                archive_batch_size=1000,
                archive=True,
                machines=None,
                availability_zones=None,
                **{"upgrade_group": "data-plane"}
            ),
        ),
        (
            ["upgrade", "control-plane", "--verbose"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=1,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=False,
                archive_batch_size=1000,
                archive=True,
                **{"upgrade_group": "control-plane"}
            ),
        ),
        (
            ["upgrade", "--verbose", "control-plane"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=1,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=False,
                archive_batch_size=1000,
                archive=True,
                **{"upgrade_group": "control-plane"}
            ),
        ),
        (
            ["upgrade", "hypervisors", "--machine=1", "-m=2,3"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=False,
                archive_batch_size=1000,
                archive=True,
                machines={"1", "2", "3"},
                availability_zones=None,
                **{"upgrade_group": "hypervisors"}
            ),
        ),
        (
            ["upgrade", "hypervisors", "--machine=1", "-m=2,3", "--force"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=True,
                archive_batch_size=1000,
                archive=True,
                machines={"1", "2", "3"},
                availability_zones=None,
                **{"upgrade_group": "hypervisors"}
            ),
        ),
        (
            ["upgrade", "hypervisors", "--quiet", "--availability-zone=1", "--az=2,3"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=True,
                auto_approve=False,
                backup=True,
                force=False,
                archive_batch_size=1000,
                archive=True,
                machines=None,
                availability_zones={"1", "2", "3"},
                **{"upgrade_group": "hypervisors"}
            ),
        ),
        (
            ["upgrade", "--quiet", "hypervisors", "--availability-zone=1", "--az=2,3"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=True,
                auto_approve=False,
                backup=True,
                force=False,
                archive_batch_size=1000,
                archive=True,
                machines=None,
                availability_zones={"1", "2", "3"},
                **{"upgrade_group": "hypervisors"}
            ),
        ),
        (
            ["upgrade", "hypervisors", "--force", "--quiet", "--availability-zone=1", "--az=2,3"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=True,
                auto_approve=False,
                backup=True,
                force=True,
                archive_batch_size=1000,
                archive=True,
                machines=None,
                availability_zones={"1", "2", "3"},
                **{"upgrade_group": "hypervisors"}
            ),
        ),
        (
            # repetitive machine 3
            [
                "upgrade",
                "hypervisors",
                "--auto-approve",
                "--force",
                "--machine=1, 2, 3",
                "-m=3, 4",
            ],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=True,
                backup=True,
                force=True,
                archive_batch_size=1000,
                archive=True,
                machines={"1", "2", "3", "4"},
                availability_zones=None,
                **{"upgrade_group": "hypervisors"}
            ),
        ),
    ],
)
def test_parse_args_upgrade(args, expected_cliargs):
    """Test parsing 'run' subcommand and its arguments/options."""
    parsed_args = commands.parse_args(args)

    assert parsed_args == expected_cliargs


@patch("cou.commands.argparse.ArgumentParser.error", autospec=True)
def test_parse_args_hypervisors_exclusive_options(mock_error):
    """Test parsing mutually exclusive hypervisors specific options."""
    mock_error.side_effect = SystemExit
    with pytest.raises(SystemExit):
        commands.parse_args(["upgrade", "hypervisors", "--machine", "1", "--az", "2"])
    mock_error.assert_called_once_with(
        ANY, "argument --availability-zone/--az: not allowed with argument --machine/-m"
    )


@patch("cou.commands.argparse.ArgumentParser.error", autospec=True)
def test_parse_args_hypervisors_exclusive_options_reverse_order(mock_error):
    """Test parsing mutually exclusive hypervisors specific options (reverse order)."""
    mock_error.side_effect = SystemExit
    with pytest.raises(SystemExit):
        commands.parse_args(["upgrade", "hypervisors", "--az", "1", "-m", "2"])
    mock_error.assert_called_once_with(
        ANY, "argument --machine/-m: not allowed with argument --availability-zone/--az"
    )


@pytest.mark.parametrize(
    "args",
    [
        ["foo"],
        ["upgrade", "--archive-batch-size", "asdf"],
        ["plan", "--archive-batch-size", "asdf"],
        ["upgrade", "--archive-batch-size", "-4"],
        ["plan", "--archive-batch-size", "-4"],
        ["upgrade", "--archive-batch-size", "0"],
        ["plan", "--archive-batch-size", "0"],
        ["plan", "--purge_before", "2000-01-02"],
        ["plan", "--purge_before", "2000-01-02 03:04"],
        ["plan", "--purge_before", "2000-01-02 03:04:05"],
        ["upgrade", "--skip-apps", "vault keystone"],
        ["plan", "--skip_apps", "vault keystone"],
    ],
)
def test_parse_invalid_args(args):
    """Generic test for various invalid sets of args."""
    with pytest.raises(SystemExit, match="2"):
        commands.parse_args(args)


@pytest.mark.parametrize(
    "args",
    [
        ["--bar"],
        ["plan", "data-plane", "--machine 1"],
        ["plan", "data-plane", "--availability-zone zone-1"],
        ["upgrade", "data-plane", "--machine 1"],
        ["upgrade", "data-plane", "--availability-zone zone-1"],
    ],
)
@patch("cou.commands.argparse.ArgumentParser.error", autospec=True)
def test_parse_args_raise_exception(mock_error, args):
    """Test parsing unknown arguments."""
    mock_error.side_effect = SystemExit
    with pytest.raises(SystemExit):
        commands.parse_args(args)
    mock_error.assert_called_once()
    assert "unrecognized arguments" in str(mock_error.call_args)


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


@pytest.mark.parametrize(
    "val",
    [
        "2000-01-0203:04",
        "2000-01-0203:04:05",
        "2000-01-02 03:04:05 something-wrong",
    ],
)
def test_purge_before_arg_invalid(val):
    """Verify --purge-before validator handles error cases."""
    with pytest.raises(ArgumentTypeError):
        commands.purge_before_arg(val)


@pytest.mark.parametrize(
    "val",
    [
        "2000-01-02",
        "2000-01-02 03:04",
        "2000-01-02 03:04:05",
    ],
)
def test_purge_before_arg_valid(val):
    """Verify --purge-before validator handles valid cases."""
    result = commands.purge_before_arg(val)
    assert val == result


@patch("cou.commands.argparse.ArgumentParser.error", autospec=True)
@patch("cou.commands.setattr")
def test_purge_before_argument_missing_dependency(mock_setattr, mock_error):
    mock_error.side_effect = SystemExit
    with pytest.raises(SystemExit):
        commands.parse_args(["plan", "--purge-before-date", "2000-01-02"])
    mock_error.assert_called_once_with(ANY, "\n--purge-before-date requires --purge")


@patch("cou.commands.setattr")
def test_skip_apps(mock_setattr):
    args = commands.parse_args(["upgrade", "--skip-apps", "vault", "vault", "vault"])
    args.skip_apps == ["vault", "vault", "vault"]


@patch("cou.commands.argparse.ArgumentParser.error", autospec=True)
@patch("cou.commands.setattr")
def test_skip_apps_failed(mock_setattr, mock_error):
    mock_error.side_effect = SystemExit
    with pytest.raises(SystemExit):
        commands.parse_args(["upgrade", "--skip-apps", "vault", "keystone"])
    mock_error.assert_called_once_with(
        ANY, "argument --skip-apps: invalid choice: 'keystone' (choose from 'vault')"
    )
