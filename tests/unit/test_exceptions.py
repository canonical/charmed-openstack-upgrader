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
import jubilant

from cou.exceptions import ActionFailed


def test_action_failed():
    """Test error message composition for ActionFailed."""
    task = jubilant.Task(
        id="4",
        status="failed",
        results={"instance-count": "5"},
        return_code=1,
        stdout="",
        stderr="some error",
        message="error message",
    )

    error = ActionFailed(task=task)
    assert "4" in str(error)
    assert "failed" in str(error)
    assert "error message" in str(error)
