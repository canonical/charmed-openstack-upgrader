#  Copyright 2023 Canonical Limited.
#  #
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Execution logic."""

import logging
import sys

from aioconsole import ainput
from colorama import Fore, Style

from cou.steps import UpgradeStep

AVAILABLE_OPTIONS = "cas"

logger = logging.getLogger(__name__)


def prompt(parameter: str) -> str:
    """Generate eye-catching prompt.

    :param parameter: String to show at the prompt with the user options.
    :type parameter: str
    :return: Colored prompt string with the user options.
    :rtype: str
    """

    def bold(text: str) -> str:
        return Style.RESET_ALL + Fore.RED + Style.BRIGHT + text + Style.RESET_ALL

    def normal(text: str) -> str:
        return Style.RESET_ALL + Fore.RED + text + Style.RESET_ALL

    return (
        normal(parameter + " (")
        + bold("c")
        + normal(")ontinue/(")
        + bold("a")
        + normal(")bort/(")
        + bold("s")
        + normal(")kip:")
    )


async def _apply_plan(plan: UpgradeStep, interactive: bool) -> None:
    """Apply the plan for upgrade.

    :param plan: Plan to be executed on steps.
    :type plan: UpgradeStep
    :param interactive:
    :type interactive: bool
    """
    result = "X"
    while result.casefold() not in AVAILABLE_OPTIONS:
        result = (await ainput(prompt(plan.description))).casefold() if interactive else "c"
        match result:
            case "c":
                logger.info("Running: %s", plan.description)
                await plan.run()
                for sub_step in plan.sub_steps:
                    await _apply_plan(sub_step, interactive)
            case "a":
                logger.info("Aborting plan")
                sys.exit(1)
            case "s":
                logger.info("Skipped")
            case _:
                logger.info("No valid input provided!")


async def execute(plan: UpgradeStep, interactive: bool) -> None:
    """Execute the plan for upgrade.

    :param plan: Plan to be executed on steps.
    :type plan: UpgradeStep
    :param interactive:
    :type interactive: bool
    """
    await _apply_plan(plan, interactive)
