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

"""Command line interaction utilities."""

import asyncio
import logging
from typing import NoReturn

from cou.exceptions import InterruptError
from cou.steps import UpgradePlan
from cou.utils import progress_indicator

logger = logging.getLogger(__name__)


async def _cancel_plan(plan: UpgradePlan, exit_code: int) -> NoReturn:
    """Watch plan and raise InterruptError when it is done.

    This watcher will make sure that InterruptError is raised after plan and all it's
    sub-steps are done.

    :param plan: watched UpgradeStep
    :type plan: UpgradePlan
    :param exit_code: Exit code
    :type exit_code: int
    :raise InterruptError: raise InterruptError after plan and all it's sub-steps are done
    """
    progress_indicator.clear()  # remove any prompt message
    progress_indicator.start("Canceling upgrade... (Press ctrl+c again to stop immediately)")
    logger.info("safely handle keyboard interrupts for %s", plan.description)
    plan.cancel(safe=True)

    logger.info("waiting for the currently running step to complete")
    while not plan.all_done:
        await asyncio.sleep(0.2)

    progress_indicator.succeed()

    raise InterruptError("charmed-openstack-upgrader has been stopped safely", exit_code)


def interrupt_handler(plan: UpgradePlan, loop: asyncio.AbstractEventLoop, exit_code: int) -> None:
    """Handle cou interruption.

    This handler first tries to safely cancel the update plan otherwise immediately raises
    the exception.
    :param plan: UpgradePlan to by canceled by this function
    :type plan: UpgradePlan
    :param loop: event loop
    :type loop: asyncio.AbstractEventLoop
    :param exit_code: Exit code
    :type exit_code: int
    :raise InterruptError: raise InterruptError after plan and all it's sub-steps are done
    """
    # NOTE(rgildein): if step is already canceled (e.g. ctr+c was already pressed) we will raise
    # KeyboardInterrupt to exit whole cou immediately
    if plan.canceled:
        plan.cancel(safe=False)
        progress_indicator.fail()  # stop previous indicator
        raise InterruptError(
            "charmed-openstack-upgrader has been terminated without waiting", exit_code
        )

    loop.create_task(_cancel_plan(plan, exit_code))
