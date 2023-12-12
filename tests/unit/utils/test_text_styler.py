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
from unittest.mock import call, patch

import pytest

from cou.utils.text_styler import prompt_message


@pytest.mark.parametrize(
    "default_input,expected_continue,expected_abort",
    [
        [None, "y", "n"],
        ["y", "Y", "n"],
        ["Y", "Y", "n"],
        ["n", "y", "N"],
        ["N", "y", "N"],
    ],
)
@patch("cou.utils.text_styler.bold")
def test_prompt_message(mock_bold, default_input, expected_continue, expected_abort):
    prompt_message("test prompt message", default=default_input)

    mock_bold.assert_has_calls([call(expected_continue), call(expected_abort)], any_order=True)


@patch("cou.utils.text_styler.bold")
def test_prompt_message_invalid_default(mock_bold):
    with pytest.raises(ValueError):
        prompt_message("test prompt message", default="x")

    mock_bold.assert_not_called()
