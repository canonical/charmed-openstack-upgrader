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

import pytest

from cou.utils.juju_utils import Model
from tests.mocked_plans.utils import get_sample_files, get_sample_plan


@pytest.fixture(params=get_sample_files(), ids=[path.name for path in get_sample_files()])
def sample_plans(request) -> tuple[Model, str]:
    """Return all sample plans in a directory.

    This parametrized fixture return a tuple with a cou.utils.juju_utils.Model object and the
    expected plan in string format as the value. The get_applications function of this Model object
    returns the applications read from a YAML file, from which the expected plan is also parsed.
    """
    return get_sample_plan(request.param)
