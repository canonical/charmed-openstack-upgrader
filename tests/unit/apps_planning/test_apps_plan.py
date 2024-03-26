#  Copyright 2023 Canonical Limited
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
"""Test all sample plans."""
from unittest.mock import patch

import pytest

from cou.commands import CLIargs
from cou.steps.plan import generate_plan


@pytest.mark.asyncio
@patch("cou.steps.plan.filter_hypervisors_machines")
async def test_sample_plans_no_inputs(_, subtests, sample_plans):
    """Testing all sample plans."""
    args = CLIargs("plan", auto_approve=True)

    for analysis_create_coro, exp_plan, file in sample_plans:
        with subtests.test(msg=file.name):
            analysis_results = await analysis_create_coro
            plan = await generate_plan(analysis_results, args)
            assert str(plan) == exp_plan
