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
from unittest.mock import patch

import pytest

from cou.utils import prompt_input
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
