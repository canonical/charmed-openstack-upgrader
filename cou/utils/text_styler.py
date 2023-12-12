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

"""Command line text styling utilities."""

from typing import Optional

from colorama import Style


def bold(text: str) -> str:
    """Transform the text in bold format.

    :param text: text to format.
    :type text: str
    :return: text formatted.
    :rtype: str
    """
    return Style.RESET_ALL + Style.BRIGHT + text + Style.RESET_ALL


def normal(text: str) -> str:
    """Transform the text in normal format.

    :param text: text to format.
    :type text: str
    :return: text formatted.
    :rtype: str
    """
    return Style.RESET_ALL + text + Style.RESET_ALL


def prompt_message(parameter: str, default_choice: Optional[str] = None) -> str:
    """Generate eye-catching prompt.

    :param parameter: String to show at the prompt with the user options.
    :type parameter: str
    :param default_choice: Default choice if user doesn't a provide valid input.
    :type default_choice: Optional[str]
    :return: Prompt string with the user options.
    :rtype: str
    :raise ValueError: raise ValueError if default choice is invalid
    """
    continue_option = "y"
    abort_option = "n"

    if not default_choice:  # use all lowercases if no default is passed
        pass
    elif default_choice.casefold() == "y":
        continue_option = "Y"
    elif default_choice.casefold() == "n":
        abort_option = "N"
    else:
        raise ValueError(f"Invalid default choice: {default_choice}")

    return (
        normal("\n" + parameter + "\nContinue (")
        + bold(continue_option)
        + normal("/")
        + bold(abort_option)
        + normal("): ")
    )
