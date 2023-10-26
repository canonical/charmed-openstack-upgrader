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

"""Package for charmed-openstack-upgrade steps."""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
import warnings
from typing import Any, Coroutine, List, Optional

from cou.exceptions import CanceledUpgradeStep

logger = logging.getLogger(__name__)


def compare_step_coroutines(coro1: Optional[Coroutine], coro2: Optional[Coroutine]) -> bool:
    """Compare two coroutines.

    :param coro1: coroutine to compare
    :type coro1: Optional[coroutine]
    :param coro2: coroutine to compare
    :type coro2: Optional[coroutine]
    :return: True if coroutines are equal
    :rtype: bool
    """
    if coro1 is None or coro2 is None:
        # compare two None or one None and one Coroutine
        return coro1 == coro2

    return (
        # check if same coroutine was used
        coro1.cr_code == coro2.cr_code
        # check coroutine arguments
        and inspect.getcoroutinelocals(coro1) == inspect.getcoroutinelocals(coro2)
    )


class UpgradeStep:
    """Represents each upgrade step.

    This UpgradeStep is used to define any step when performing an OpenStack upgrade.
    And requires description, parallel and coroutine as arguments. The coroutine is expected by
    creating an asyncio.Task task instead of waiting directly, so that it is possible to cancel
    the task and at the same time simply find out which task is really running according to
    its name.
    """

    def __init__(
        self,
        description: str = "",
        parallel: bool = False,
        coro: Optional[Coroutine] = None,
    ):
        """Initialize upgrade step.

        :param description: Description of the step.
        :type description: str
        :param parallel: Define if step should run on parallel or not.
        :type parallel: bool
        :param coro: Step coroutine
        :type coro: Optional[coroutine]
        """
        if coro is not None:
            # NOTE(rgildein): We need to ignore coroutine not to be awaited if step is not run
            warnings.filterwarnings(
                "ignore", message=f"coroutine '.*{coro.__name__}' was never awaited"
            )

        self.parallel = parallel
        self.description = description
        self.sub_steps: List[UpgradeStep] = []
        self._coro: Optional[Coroutine] = coro
        self._canceled: bool = False
        self._task: Optional[asyncio.Task] = None

    def __hash__(self) -> int:
        """Get hash for UpgradeStep."""
        return hash((self.description, self.parallel, self._coro))

    def __eq__(self, other: Any) -> bool:
        """Equal magic method for UpgradeStep.

        :param other: UpgradeStep object to compare.
        :type other: Any
        :return: True if equal False if different.
        :rtype: bool
        """
        if not isinstance(other, UpgradeStep):
            return NotImplemented

        return (
            other.parallel == self.parallel
            and other.description == self.description
            and other.sub_steps == self.sub_steps
            and compare_step_coroutines(other._coro, self._coro)
        )

    def __str__(self) -> str:
        """Dump the plan for upgrade.

        :return: String representation of UpgradeStep.
        :rtype: str
        """
        result = ""
        tab = "\t"
        steps_to_visit = [(self, 0)]
        while steps_to_visit:
            step, indent = steps_to_visit.pop()
            result += f"{tab * indent}{step.description}{os.linesep}" if step else ""
            steps_to_visit.extend([(s, indent + 1) for s in reversed(step.sub_steps)])

        return result

    def __repr__(self) -> str:
        """Representation of UpgradeStep.

        :return: Representation of UpgradeStep.
        :rtype: str
        """
        return f"UpgradeStep({self.description})"

    def __bool__(self) -> bool:
        """Boolean magic method for UpgradeStep.

        :return: True if there is at least one coroutine in a UpgradeStep
        or in its sub steps.
        :rtype: bool
        """
        return self._coro is not None or any(bool(step) for step in self.sub_steps)

    @property
    def canceled(self) -> bool:
        """Return boolean represent if step was canceled."""
        return self._canceled

    @property
    def results(self) -> Any:
        """Return result of UpgradeStep."""
        return self._task.result() if self._task is not None else None

    def add_step(self, step: UpgradeStep) -> None:
        """Add a single step.

        :param step: UpgradeStep to be added as sub step.
        :type step: UpgradeStep
        """
        self.sub_steps.append(step)

    def cancel(self, safe: bool = True) -> None:
        """Cancel step and all its sub steps.

        The dangerous cancellation method should only be used with the user's warning, as it may
        cause damage to the Juju model.

        :param safe: safe cancellation of only not running tasks
        :type safe: bool
        """
        # Note(rgildein): We need to cancel all sub steps first
        for step in self.sub_steps:
            step.cancel(safe=safe)

        if safe is False and self._task is not None:  # unsafe canceling of pending task
            self._task.cancel(f"canceled: {repr(self)}")

        self._canceled = True
        logger.debug("canceled: %s", self)

    async def run(self) -> Any:
        """Run the UpgradeStep coroutine.

        :return: Result of the coroutine.
        :rtype: Any
        :raises CanceledUpgradeStep: If step has already been canceled.
        """
        logger.debug("running step: %s", repr(self))

        if self.canceled:
            raise CanceledUpgradeStep(f"Could not run canceled step: {repr(self)}")

        if self._coro is None:
            return  # do nothing if coro was not provided

        try:
            self._task = asyncio.create_task(self._coro, name=repr(self))
            return await self._task  # wait until task is completed
        except asyncio.CancelledError:  # ignoring asyncio.CancelledError
            logger.warning("Task %s was stopped unsafely.", repr(self))
