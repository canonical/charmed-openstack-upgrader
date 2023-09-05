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
from unittest import mock

from juju.action import Action

from cou.exceptions import ActionFailed


def test_action_failed():
    """Test error message composition for ActionFailed."""
    mocked_action = mock.Mock(spec=Action)
    action = mocked_action()
    action.name = "test-action"
    action.parameters = "test=1"
    action.receiver = "test-receiver"
    action.message = "test-message"
    action.id = "test-id"
    action.status = "test-status"
    action.enqueued = "test-enqueued"
    action.started = "test-started"
    action.completed = "test-completed"

    error = ActionFailed(action=action, output="test output")
    assert str(error) == (
        'Run of action "test-action" with parameters "test=1" on '
        '"test-receiver" failed with "test-message" (id=test-id '
        "status=test-status enqueued=test-enqueued started=test-started "
        "completed=test-completed output=test output)"
    )
