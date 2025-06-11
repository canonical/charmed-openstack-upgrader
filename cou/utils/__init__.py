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

"""Utilities for charmed-openstack-upgrader."""

import inspect
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

from aioconsole import ainput
from halo import Halo

from cou.utils.text_styler import bold, normal

COU_DATA = Path(f"/home/{os.getenv('USER')}/.local/share/cou") if os.getenv("USER") else Path(".")


class SmartHalo:
    """SmartHalo detects non-TTY and disable spinner accordingly."""

    def __init__(self) -> None:
        self.is_tty = sys.stdout.isatty()
        self.spinner = Halo(spinner="line", placement="right") if self.is_tty else None

    def start(self, text: Optional[str] = None) -> None:
        if self.spinner:
            self.spinner.start(text)
        elif text:
            print(text, flush=True)

    def info(self, text: str) -> None:
        self.spinner.info(text) if self.spinner else print(text, flush=True)

    def stop(self) -> None:
        if self.spinner:
            self.spinner.stop()

    def succeed(self, text: Optional[str] = None) -> None:
        if self.spinner:
            self.spinner.succeed(text)
        elif text:
            print(text, flush=True)

    def fail(self) -> None:
        if self.spinner:
            self.spinner.fail()

    def stop_and_persist(self, text: str) -> None:
        self.spinner.stop_and_persist(text) if self.spinner else print(text, flush=True)


progress_indicator = SmartHalo()


def print_and_debug(message: Any) -> None:
    """Print and log message at debug level.

    :param message: The object to print and log.
    :type message: Any
    """
    print(message)

    logger = logging.getLogger(inspect.stack()[1].filename)
    logger.debug(message)


async def prompt_input(
    text_list: list[str],
    separator: str = "\n",
    choices: Optional[list[str]] = None,
    default: str = "",
) -> str:
    """Generate eye-catching prompt.

    :param text_list: List of text to show at the prompt with the user options.
    :type text_list: list[str]
    :param separator: Separator between each text. Default to newline.
    :type separator: str
    :param choices: List of options to show at the prompt with the user options. If no value
    supplied, 'y' and 'n' will be used by default.
    :type choices: Optional[list[str]]
    :param default: The default choice if user doesn't a provide valid input.
    :type default: str
    :return: The input value (if any) or the default choice.
    :rtype: str
    :raise ValueError: raise ValueError if default choice is invalid
    """
    if not choices:
        choices = ["y", "n"]

    message_str = normal(separator).join(normal(text) for text in text_list)
    choices_str = normal("/").join(
        bold(choice.upper() if choice == default.casefold() else choice) for choice in choices
    )
    formatted_message = normal("\n") + message_str + normal(" (") + choices_str + normal("): ")

    input_value = await ainput(formatted_message)

    return (input_value or default).casefold()
