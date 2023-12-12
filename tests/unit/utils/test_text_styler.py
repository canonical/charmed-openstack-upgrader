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

from cou.utils.text_styler import bold, normal, prompt_message


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
def test_prompt_message(default_choice_input, expected_continue, expected_abort):
    expected_output = (
        normal("\n" + "test prompt message\nContinue (")
        + bold(expected_continue)
        + normal("/")
        + bold(expected_abort)
        + normal("): ")
    )
    actual_output = prompt_message("test prompt message", default_choice=default_choice_input)

    assert actual_output == expected_output


@patch("cou.utils.text_styler.bold")
def test_prompt_message_invalid_default_choice(mock_bold):
    with pytest.raises(ValueError):
        prompt_message("test prompt message", default_choice="x")

    mock_bold.assert_not_called()
