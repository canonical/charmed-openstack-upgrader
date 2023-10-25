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

from halo import Halo

from cou.steps import UpgradeStep

logger = logging.getLogger(__name__)


async def _cancel_plan(plan: UpgradeStep, progress_indicator: Halo) -> NoReturn:
    """Watch plan and raise KeyboardInterrupt when it is done.

    This watcher will make sure that KeyboardInterrupt is raised after plan and all it's
    sub-steps are done.

    :param plan: watched UpgradeStep
    :type plan: UpgradeStep
    :param progress_indicator: CLI indicator
    :type progress_indicator: Halo
    :raise KeyboardInterrupt: raise KeyboardInterrupt after plan and all it's sub-steps are done
    """
    progress_indicator.clear()  # remove any prompt message
    progress_indicator.start("Canceling upgrade... (Press ctrl+c again to stop immediately)")
    logger.info("safely handle keyboard interrupts for %s", plan.description)
    plan.cancel(safe=True)

    logger.info("waiting for the currently running step to complete")
    while not plan.all_done:
        await asyncio.sleep(0.2)

    progress_indicator.succeed()

    raise KeyboardInterrupt("charmed-openstack-upgrader has been stopped cleanly")


def keyboard_interrupt_handler(
    plan: UpgradeStep, loop: asyncio.AbstractEventLoop, progress_indicator: Halo
) -> None:
    """Handle single or multiple ctr+c pressed.

    This handler first tries to safely cancel the update plan otherwise immediately raises
    the KeyboardInterrupt.
    :param plan: UpgradeStep to by canceled by this function
    :type plan: UpgradeStep
    :param loop: event loop
    :type loop: asyncio.AbstractEventLoop
    :param progress_indicator: CLI indicator
    :type progress_indicator: Halo
    :raise KeyboardInterrupt: raise KeyboardInterrupt after plan and all it's sub-steps are done
    """
    # NOTE(rgildein): if step is already canceled (e.g. ctr+c was already pressed) we will raise
    # KeyboardInterrupt to exit whole cou immediately
    if plan.canceled:
        plan.cancel(safe=False)
        progress_indicator.stop_and_persist()  # stop previous indicator
        raise KeyboardInterrupt("charmed-openstack-upgrade has been terminated without waiting")

    loop.create_task(_cancel_plan(plan, progress_indicator))
