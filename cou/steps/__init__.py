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

from cou.exceptions import CanceledStep

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


class BaseStep:
    """Represents a basic upgrade step.

    This BaseStep is used to as the bases for any step when performing an OpenStack upgrade.
    It requires description, parallel, coroutine, and prompt as arguments. The coroutine is
    expected by creating an asyncio.Task task instead of waiting directly, so that it is possible
    to cancel the task and at the same time simply find out which task is really running according
    to its name.

    This class should not be used directly. Please use one of its child classes as fits.
    """

    # pylint: disable=too-many-instance-attributes

    prompt: bool = True  # whether to prompt for user input during execution

    def __init__(
        self,
        description: str = "",
        parallel: bool = False,
        coro: Optional[Coroutine] = None,
        prompt: Optional[bool] = None,
    ):
        """Initialize BaseStep.

        :param description: Description of the step.
        :type description: str
        :param parallel: Define if step should run on parallel or not.
        :type parallel: bool
        :param coro: Step coroutine
        :type coro: Optional[coroutine]
        :param prompt: Whether to prompt for user input during execution
        :type prompt: bool
        """
        if coro is not None:
            # NOTE(rgildein): We need to ignore coroutine not to be awaited if step is not run
            warnings.filterwarnings(
                "ignore", message=f"coroutine '.*{coro.__name__}' was never awaited"
            )

        self._coro: Optional[Coroutine] = coro
        self.parallel = parallel
        self.description = description
        self.sub_steps: List[BaseStep] = []
        self._canceled: bool = False
        self._task: Optional[asyncio.Task] = None

        # Use default prompt value unless explicitly provided
        if prompt is not None:
            self.prompt = prompt

    def __hash__(self) -> int:
        """Get hash for BaseStep."""
        return hash((self.description, self.parallel, self._coro))

    def __eq__(self, other: Any) -> bool:
        """Equal magic method for BaseStep.

        :param other: BaseStep object to compare.
        :type other: Any
        :return: True if equal False if different.
        :rtype: bool
        """
        if not isinstance(other, BaseStep):
            return NotImplemented

        return (
            other.parallel == self.parallel
            and other.description == self.description
            and other.sub_steps == self.sub_steps
            and compare_step_coroutines(other._coro, self._coro)
        )

    def __str__(self) -> str:
        """Dump the plan for upgrade.

        :return: String representation of BaseStep.
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
        """Representation of BaseStep.

        :return: Representation of BaseStep.
        :rtype: str
        """
        return f"{self.__class__.__name__}({self.description})"

    def __bool__(self) -> bool:
        """Boolean magic method for BaseStep.

        :return: True if there is at least one coroutine in a BaseStep
        or in its sub steps.
        :rtype: bool
        """
        return self._coro is not None or any(bool(step) for step in self.sub_steps)

    @property
    def description(self) -> str:
        """Get the description of the BaseStep.

        :return: description
        :rtype: str
        """
        return self._description

    @description.setter
    def description(self, description: str) -> None:
        """Set the description of the BaseStep.

        :param description: description
        :type description: str
        :raises ValueError: When a coroutine is passed without description.
        """
        if not description and self._coro:
            raise ValueError("Every coroutine should have a description")
        self._description = description

    @property
    def canceled(self) -> bool:
        """Return boolean represent if step was canceled."""
        return self._canceled

    @property
    def results(self) -> Any:
        """Return result of BaseStep."""
        return self._task.result() if self._task is not None else None

    def add_step(self, step: BaseStep) -> None:
        """Add a single step.

        :param step: BaseStep to be added as sub step.
        :type step: BaseStep
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
        """Run the BaseStep coroutine.

        :return: Result of the coroutine.
        :rtype: Any
        :raises CanceledStep: If step has already been canceled.
        """
        logger.debug("running step: %s", repr(self))

        if self.canceled:
            raise CanceledStep(f"Could not run canceled step: {repr(self)}")

        if self._coro is None:
            return  # do nothing if coro was not provided

        try:
            self._task = asyncio.create_task(self._coro, name=repr(self))
            return await self._task  # wait until task is completed
        except asyncio.CancelledError:  # ignoring asyncio.CancelledError
            logger.warning("Task %s was stopped unsafely.", repr(self))


class UpgradePlan(BaseStep):
    """Represents the upgrade plan.

    This class is intended to be used as a higher-level group for actual upgrade steps, therefore
    doesn't accept corotine or parallel as inputs.
    """

    prompt: bool = False

    def __init__(
        self,
        description: str = "",
        prompt: bool = False,
    ):
        """Initialize upgrade plan.

        :param description: Description of the step.
        :type description: str
        """
        super().__init__(description=description, parallel=False, coro=None, prompt=prompt)

    async def run(self) -> None:
        """Run UpgradePlan.

        UpgradePlan should not have contain any corotine, so simply print a debug
        message to demonstrate the noop.
        """
        logger.debug("No corotine to run for %s", repr(self))


class ApplicationUpgradePlan(UpgradePlan):
    """Represents the plan for application-level upgrade.

    This class is intended to be used as a group for application-level upgrade steps, therefore
    doesn't accept corotine or parallel as inputs.
    """

    prompt: bool = True


class UpgradeStep(BaseStep):
    """Represents the upgrade step."""

    sub_step_prefix = "[upgrade] "
    prompt: bool = False

    @property
    def description(self) -> str:
        """Get the description of the PreUpgradeStep.

        :return: description
        :rtype: str
        """
        return self._description

    @description.setter
    def description(self, description: str) -> None:
        """Set the description of the PreUpgradeStep.

        :param description: description
        :type description: str
        :raises ValueError: When a coroutine is passed without description.
        """
        if not description and self._coro:
            raise ValueError("Every coroutine should have a description")
        self._description = self.sub_step_prefix + description


class PreUpgradeStep(UpgradeStep):
    """Represents the pre-upgrade step."""

    sub_step_prefix = "[pre-upgrade] "


class PostUpgradeStep(UpgradeStep):
    """Represents the post-upgrade step."""

    sub_step_prefix = "[post-upgrade] "
