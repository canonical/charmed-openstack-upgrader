#  Copyright 2023 Canonical Limited
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
from typing import Optional
from unittest.mock import patch

import pytest

from cou.utils import SmartHalo, prompt_input
from cou.utils.text_styler import bold, normal


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "default_choice_input,input_value,expected_output",
    [
        ["", "y", "y"],
        ["", "Y", "y"],
        ["y", "n", "n"],
        ["n", "", "n"],
    ],
)
@patch("cou.utils.ainput")
async def test_prompt_input(mock_input, default_choice_input, input_value, expected_output):
    mock_input.return_value = input_value
    actual_output = await prompt_input(
        ["test prompt message", "Continue"], default=default_choice_input
    )

    assert actual_output == expected_output


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "default_choice_input,expected_continue,expected_abort",
    [
        ["", "y", "n"],
        ["y", "Y", "n"],
        ["Y", "Y", "n"],
        ["n", "y", "N"],
        ["N", "y", "N"],
    ],
)
@patch("cou.utils.ainput")
async def test_prompt_input_default_choice(
    mock_input, default_choice_input, expected_continue, expected_abort
):
    message = (
        normal("\n")
        + normal("test prompt message")
        + normal("\n")
        + normal("Continue")
        + normal(" (")
        + bold(expected_continue)
        + normal("/")
        + bold(expected_abort)
        + normal("): ")
    )
    await prompt_input(["test prompt message", "Continue"], default=default_choice_input)

    mock_input.assert_awaited_once_with(message)


@pytest.fixture
def fake_halo(mocker):
    return mocker.patch("cou.utils.Halo", autospec=True)


@pytest.mark.parametrize(
    "method, args, expected_call",
    [
        ("start", ("Loading...",), "start"),  # start with text
        ("start", (None,), "start"),  # start without text
        ("stop", (), "stop"),
        ("info", ("Info...",), "info"),
        ("succeed", ("Success!",), "succeed"),  # succeed with text
        ("succeed", (None,), "succeed"),  # succeed without text
        ("fail", (), "fail"),
        ("stop_and_persist", ("Saved!",), "stop_and_persist"),
    ],
)
def test_smart_halo_behavior_tty(
    mocker,
    fake_halo,
    method: str,
    args: tuple,
    expected_call: Optional[str],
):
    mocker.patch("sys.stdout.isatty", return_value=True)
    halo_instance = fake_halo.return_value

    halo = SmartHalo()

    getattr(halo, method)(*args)

    getattr(halo_instance, expected_call).assert_called_once_with(*[arg for arg in args])


@pytest.mark.parametrize(
    "method, args",
    [
        ("start", ("Loading...",)),  # start with text
        ("start", (None,)),  # start without text
        ("stop", ()),
        ("info", ("Info...",)),
        ("succeed", ("Success!",)),  # succeed with text
        ("succeed", (None,)),  # succeed without text
        ("fail", ()),
        ("stop_and_persist", ("Saved!",)),
    ],
)
def test_smart_halo_behavior_non_tty(
    mocker,
    method: str,
    args: tuple,
):
    mocker.patch("sys.stdout.isatty", return_value=False)
    mock_print = mocker.patch("builtins.print")

    halo = SmartHalo()

    getattr(halo, method)(*args)

    if args and args[0] is not None:
        mock_print.assert_called_once_with(*[arg for arg in args], flush=True)
    else:
        mock_print.assert_not_called()


@pytest.mark.parametrize(
    "isatty, spinner_id",
    [
        (
            True,
            "my-id",
        ),
        (False, None),
    ],
)
def test_smart_halo_behavior_spinner_id(mocker, fake_halo, isatty, spinner_id):
    mocker.patch("sys.stdout.isatty", return_value=isatty)
    fake_halo.return_value.spinner_id = spinner_id

    halo = SmartHalo()

    assert halo.spinner_id == spinner_id
