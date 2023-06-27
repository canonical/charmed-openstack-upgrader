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

from colorama import Fore, Style

from cou.steps import UpgradeStep
from cou.steps.analyze import Analysis
from cou.steps.backup import backup

AVAILABLE_OPTIONS = "cas"


def generate_plan(args: Analysis) -> UpgradeStep:
    """Generate plan for upgrade."""
    logging.info(args)  # for placeholder
    plan = UpgradeStep(description="Top level plan", parallel=False, function=None)
    plan.add_step(
        UpgradeStep(description="backup mysql databases", parallel=False, function=backup)
    )
    return plan


def prompt(parameter: str) -> str:
    """Generate eye-catching prompt."""

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


async def apply_plan(upgrade_plan: UpgradeStep) -> None:
    """Apply the plan for upgrade."""
    result = "X"
    while result.casefold() not in AVAILABLE_OPTIONS:
        result = input(prompt(upgrade_plan.description)).casefold()
        match result:
            case "c":
                await upgrade_plan.run()
                for sub_step in upgrade_plan.sub_steps:
                    await apply_plan(sub_step)
            case "a":
                logging.info("Aborning plan")
                sys.exit(1)
            case "s":
                logging.info("Skipped")
            case _:
                logging.info("No valid input provided!")


def dump_plan(upgrade_plan: UpgradeStep, ident: int = 0) -> None:
    """Dump the plan for upgrade."""
    tab = "\t"
    logging.info(f"{tab * ident}{upgrade_plan.description}")  # pylint: disable=W1203
    for sub_step in upgrade_plan.sub_steps:
        dump_plan(sub_step, ident + 1)
