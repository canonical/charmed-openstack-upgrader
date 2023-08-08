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
from abc import ABC, abstractmethod

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


# pylint: disable=too-few-public-methods
class BaseExecutor(ABC):
    """Abstract base class for executor."""

    def __init__(self, plan: UpgradeStep, interactive: bool):
        """
        Initialize Executor.

        :param plan: generated plan to execute
        :type plan: UpgradeStep
        :param interactive: if plan should be executed interactive
        :type interactive: bool
        """
        self.plan = plan
        self.interactive = interactive

    @abstractmethod
    async def execute(self) -> None:
        """Execute upgrade steps."""


# pylint: disable=too-few-public-methods
class ExecutorFactory:
    """Factory to create executor."""

    @classmethod
    def create_executor(cls, plan: UpgradeStep, interactive: bool) -> BaseExecutor:
        """Create executor.

        :param plan: Plan to be executed on steps.
        :type plan: UpgradeStep
        :param interactive:
        :type interactive: bool
        :returns: BaseExecutor
        """
        return SerialExecutor(plan, interactive=interactive)


# pylint: disable=too-few-public-methods
class SerialExecutor(BaseExecutor):
    """Executes steps in serial manner."""

    async def execute(self) -> None:
        await self._apply_plan(self.plan, self.interactive)

    async def _apply_plan(self, plan: UpgradeStep, interactive: bool) -> None:
        """Apply the plan for upgrade.

        :param plan: Plan to be executed on steps.
        :type plan: UpgradeStep
        :param interactive:
        :type interactive: bool
        """
        result = "X"
        while result.casefold() not in AVAILABLE_OPTIONS:
            result = input(prompt(plan.description)).casefold() if interactive else "c"
            match result:
                case "c":
                    logger.info("Running: %s", plan.description)
                    await plan.run()
                    for sub_step in plan.sub_steps:
                        await self._apply_plan(sub_step, interactive)
                case "a":
                    logger.info("Aborting plan")
                    sys.exit(1)
                case "s":
                    logger.info("Skipped")
                case _:
                    logger.info("No valid input provided!")
