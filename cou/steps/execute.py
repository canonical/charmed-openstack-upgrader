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
"""Execution logic."""

import asyncio
import logging
import sys

from aioconsole import ainput
from colorama import Style

from cou.steps import ApplicationUpgradePlan, BaseStep, UpgradeStep
from cou.utils import progress_indicator

AVAILABLE_OPTIONS = ["y", "n"]

logger = logging.getLogger(__name__)


def prompt(parameter: str) -> str:
    """Generate eye-catching prompt.

    :param parameter: String to show at the prompt with the user options.
    :type parameter: str
    :return: Colored prompt string with the user options.
    :rtype: str
    """

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

    return normal(parameter + "Continue(") + bold("y") + normal("/") + bold("n") + normal("):")


async def _run_step(step: BaseStep, interactive: bool) -> None:
    """Run a step and all its sub-steps.

    :param step: Step to be executed.
    :type step: BaseStep
    :param interactive: Whether to run upgrade step in interactive mode.
    :type interactive: bool
    """
    if isinstance(step, UpgradeStep):
        progress_indicator.start(step.description)
        await step.run()
        progress_indicator.succeed()
    else:
        await step.run()

    if step.parallel:
        logger.debug("running all sub-steps of %s step in parallel", step)
        grouped_coroutines = (apply_step(sub_step, interactive) for sub_step in step.sub_steps)
        await asyncio.gather(*grouped_coroutines)
    else:
        logger.debug("running all sub-steps of %s step sequentially", step)
        for sub_step in step.sub_steps:
            logger.debug("running sub-step %s of %s step", sub_step, step)
            await apply_step(sub_step, interactive)


async def apply_step(step: BaseStep, interactive: bool) -> None:
    """Apply a step to execute.

    :param step: Step to be executed.
    :type step: BaseStep
    :param interactive:
    :type interactive: bool
    """
    # adding a space at the end to better separate description with prompt options
    # Example:
    #   This is an upgrade step Continue(y/n)
    description = step.description + " "
    result = ""
    # do nothing for empty upgrade step
    if not step:
        return

    # group and print all sub-steps with hierarchy for ApplicationUpgradePlan
    if isinstance(step, ApplicationUpgradePlan):
        description = str(step) + "\n"
        if not interactive:
            print(step.description)

    while result.casefold() not in AVAILABLE_OPTIONS:
        if not interactive or not step.prompt:
            result = "y"
        else:
            result = (await ainput(prompt(description))).casefold()

        match result:
            case "y":
                logger.info("Running: %s", step.description)
                await _run_step(step, interactive)
            case "n":
                logger.info("Aborting plan")
                sys.exit(1)
            case _:
                print("No valid input provided!")
                logger.debug("No valid input provided!")
