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

"""Upgrade planning utilities."""

import logging

from cou.steps import UpgradeStep
from cou.steps.analyze import Analysis
from cou.steps.backup import backup

logger = logging.getLogger(__name__)


async def generate_plan(args: Analysis) -> UpgradeStep:
    """Generate plan for upgrade.

    :param args: Analysis result.
    :type args: Analysis
    :return: Plan with all upgrade steps necessary based on the Analysis.
    :rtype: UpgradeStep
    """
    logger.info(args)  # for placeholder
    plan = UpgradeStep(description="Top level plan", parallel=False, function=None)
    plan.add_step(
        UpgradeStep(description="backup mysql databases", parallel=False, function=backup)
    )
    return plan
