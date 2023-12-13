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

from cou.steps import ApplicationUpgradePlan, BaseStep, UpgradeStep
from cou.utils import print_and_debug, progress_indicator, prompt_input

AVAILABLE_OPTIONS = ["y", "yes", "n", "no"]

logger = logging.getLogger(__name__)


async def _run_step(step: BaseStep, prompt: bool, overwrite_progress: bool = False) -> None:
    """Run a step and all its sub-steps.

    :param step: Step to be executed.
    :type step: BaseStep
    :param prompt: Whether to run upgrade step with prompt (interactive mode).
    :type prompt: bool
    :param overwrite_progress: Whether to overwrite the current step's progress indication message
    in CLI output. True to overwrite and False (the default) to persist.
    :type overwrite_progress: bool
    """
    if isinstance(step, UpgradeStep):
        progress_indicator.start(step.description)
        await step.run()
        if not overwrite_progress:
            progress_indicator.succeed()
    else:
        await step.run()

    # The progress indication message of ApplicationUpgradePlan's sub-steps and all their
    # sub-steps will get overwritten upon completion
    overwrite_substeps_progress = overwrite_progress or isinstance(step, ApplicationUpgradePlan)

    if step.parallel:
        logger.debug("running all sub-steps of %s step in parallel", step)
        grouped_coroutines = (
            apply_step(sub_step, prompt, overwrite_substeps_progress)
            for sub_step in step.sub_steps
        )
        await asyncio.gather(*grouped_coroutines)
    else:
        logger.debug("running all sub-steps of %s step sequentially", step)
        for sub_step in step.sub_steps:
            logger.debug("running sub-step %s of %s step", sub_step, step)
            await apply_step(sub_step, prompt, overwrite_substeps_progress)

    # Upon completion of all sub-steps of ApplicationUpgradePlan, replace the current progress
    # indication message, if any, with a persistent application description message.
    if isinstance(step, ApplicationUpgradePlan) and progress_indicator.spinner_id is not None:
        progress_indicator.succeed(step.description)


async def apply_step(step: BaseStep, prompt: bool, overwrite_progress: bool = False) -> None:
    """Apply a step to execute.

    :param step: Step to be executed.
    :type step: BaseStep
    :param prompt: Whether to run upgrade step with prompt (interactive mode).
    :type prompt: bool
    :param overwrite_progress: Whether to overwrite the current step's progress indication message
    in CLI output. True to overwrite and False (the default) to persist.
    :type overwrite_progress: bool
    """
    description_to_prompt = step.description

    # do nothing if neither the current step nor any of its sub steps contains
    # at least one coroutine
    if not step:
        return

    # group and print all sub-steps with hierarchy for ApplicationUpgradePlan
    if isinstance(step, ApplicationUpgradePlan):
        description_to_prompt = str(step)

    result = ""
    while result not in AVAILABLE_OPTIONS:
        if not prompt or not step.prompt:
            result = "y"
        else:
            result = await prompt_input([description_to_prompt, "Continue"])

        match result:
            case "y" | "yes":
                logger.info("Running: %s", step.description)
                await _run_step(step, prompt, overwrite_progress)
            case "n" | "no":
                logger.info("Aborting plan")
                sys.exit(1)
            case _:
                print_and_debug("No valid input provided!")
