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

"""Upgrade planning utilities."""

import logging
import sys
from argparse import Namespace
from typing import Any

from cou.steps import UpgradeStep
from cou.steps.backup import backup


def generate_plan(args: Namespace) -> UpgradeStep:
    """Generate plan for upgrade."""
    logging.info(args)  # for placeholder
    plan = UpgradeStep(description="Top level plan", parallel=False, function=None)
    plan.add_step(
        UpgradeStep(description="backup mysql databases", parallel=False, function=backup)
    )
    return plan


def apply_plan(upgrade_plan: Any) -> None:
    """Apply the plan for upgrade."""
    result = input(upgrade_plan.description + "[Continue/abort/skip]")
    if result.casefold() == "c".casefold():
        if upgrade_plan.function is not None:
            if upgrade_plan.params:
                upgrade_plan.function(upgrade_plan.params)
            else:
                upgrade_plan.function()
    elif result.casefold() == "a".casefold():
        sys.exit(1)

    for sub_step in upgrade_plan.sub_steps:
        apply_plan(sub_step)


def dump_plan(upgrade_plan: UpgradeStep, ident: int = 0) -> None:
    """Dump the plan for upgrade."""
    tab = "\t"
    logging.info(f"{tab*ident}{upgrade_plan.description}")  # pylint: disable=W1203
    for sub_step in upgrade_plan.sub_steps:
        dump_plan(sub_step, ident + 1)
