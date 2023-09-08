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
from colorama import Fore, Style

from cou.steps import UpgradeStep

AVAILABLE_OPTIONS = ["c", "a", "s"]

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


async def _run_step(step: UpgradeStep, interactive: bool) -> None:
    """Run step and all sub-steps.

    :param plan: Plan to be executed on steps.
    :type plan: UpgradeStep
    :param interactive:
    :type interactive: bool
    """
    logger.debug("running step %s", step)
    await step.run()

    if step.parallel:
        logger.debug("running all sub-steps of %s step in parallel", step)
        grouped_coroutines = (apply_plan(sub_step, interactive) for sub_step in step.sub_steps)
        await asyncio.gather(*grouped_coroutines)
    else:
        logger.debug("running all sub-steps of %s step sequentially", step)
        for sub_step in step.sub_steps:
            logger.debug("running sub-step %s of %s step", sub_step, step)
            await apply_plan(sub_step, interactive)


async def apply_plan(plan: UpgradeStep, interactive: bool) -> None:
    """Apply the plan for upgrade.

    :param plan: Plan to be executed on steps.
    :type plan: UpgradeStep
    :param interactive:
    :type interactive: bool
    """
    result = ""
    while result.casefold() not in AVAILABLE_OPTIONS:
        result = (await ainput(prompt(plan.description))).casefold() if interactive else "c"
        match result:
            case "c":
                logger.info("Running: %s", plan.description)
                await _run_step(plan, interactive)
            case "a":
                logger.info("Aborting plan")
                sys.exit(1)
            case "s":
                logger.info("Skipped")
            case _:
                logger.info("No valid input provided!")
