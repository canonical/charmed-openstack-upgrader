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
        """Initialize upgrade step."""
        self.parallel = parallel
        self.description = description
        self.sub_steps: List[UpgradeStep] = list[UpgradeStep]()
        self.params = params
        self.function = function

    def add_step(self, step: UpgradeStep) -> UpgradeStep:
        """Add a single step."""
        self.sub_steps.append(step)
        return self

    async def run(self) -> Any:
        """Run the function."""
        if self.function is not None:
            if self.params:
                return await self.function(**self.params)
            return await self.function()
        return None
