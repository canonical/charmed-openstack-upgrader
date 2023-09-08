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

"""Package for canonical-openstack-upgrade steps."""

from __future__ import annotations

import os
from typing import Any, Callable, List, Optional


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
        self.sub_steps: List[UpgradeStep] = []
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
        """Run the function.

        :return: Result of the function.
        :rtype: Any
        """
        if self.function is not None:
            if self.params:
                return await self.function(**self.params)
            return await self.function()

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
