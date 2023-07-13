# Copyright 2023 Canonical Limited.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Package for charmed openstack upgrade steps."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Callable, List, Optional

from cou.utils.juju_utils import async_block_until_all_units_idle


class UpgradeStep:
    """Represents each upgrade step."""

    def __init__(
        self,
        description: str,
        parallel: bool,
        function: Optional[Callable],
        **params: Optional[Any],
    ):
        """Initialize upgrade step.

        :param description: Description of the step.
        :type description: str
        :param parallel: Define if step should run on parallel or not.
        :type parallel: bool
        :param function: Function to run in the step.
        :type function: Optional[Callable]
        :param params: Unlimited parameters to be run at the "function".
            E.g:  UpgradeStep("my_description", False, my_func, foo=bar)
            In this case, my_func expects the parameter foo that has the value bar.
        :type params: Optional[Any]
        """
        self.parallel = parallel
        self.description = description
        self.sub_steps: List[UpgradeStep] = list[UpgradeStep]()
        self.params = params
        self.function = function

    def add_step(self, step: UpgradeStep) -> UpgradeStep:
        """Add a single step.

        :param step: UpgradeStep to be added as sub step.
        :type step: UpgradeStep
        :return: UpgradeStep added into sub step.
        :rtype: UpgradeStep
        """
        self.sub_steps.append(step)
        return step

    async def run(self) -> Any:
        """Run the function."""
        if self.parallel:
            await self.wait_until_all_units_idle()
            logging.info(
                "Running: %s", ", ".join(sub_step.description for sub_step in self.sub_steps)
            )
            parallel_exec = [sub_step.function(**sub_step.params) for sub_step in self.sub_steps]
            await asyncio.gather(*parallel_exec)
            await self.wait_until_all_units_idle()
        else:
            if self.function is not None:
                await self.wait_until_all_units_idle()
                if self.params:
                    await self.function(**self.params)
                else:
                    await self.function()
            await self.wait_until_all_units_idle()

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
            result += f"{tab * indent}{step.description}{os.linesep}"
            steps_to_visit.extend([(s, indent + 1) for s in reversed(step.sub_steps)])

        return result

    async def wait_until_all_units_idle(self):
        logging.info("Wait until all units idle")
        await async_block_until_all_units_idle()
