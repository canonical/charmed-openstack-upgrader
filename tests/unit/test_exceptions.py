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
    action = mock.Mock(spec_set=Action)()
    action.safe_data = {
        "model-uuid": "12885f47-4dfa-4457-8ed1-1f08c1b278dd",
        "id": "4",
        "receiver": "my-charm/0",
        "name": "test-action",
        "status": "failed",
        "message": "error message",
        "enqueued": "2024-05-29T14:50:08Z",
        "started": "2024-05-29T14:50:11Z",
        "completed": "2024-05-29T14:50:11Z",
    }

    error = ActionFailed(action=action)
    assert str(error) == (
        "Run of action 'test-action' with parameters '<not-set>' on 'my-charm/0' failed with "
        "'error message' (id=4 status=failed enqueued=2024-05-29T14:50:08Z started=2024-05-29T14:"
        "50:11Z completed=2024-05-29T14:50:11Z output={'model-uuid': '12885f47-4dfa-4457-8ed1-1f0"
        "8c1b278dd', 'id': '4', 'receiver': 'my-charm/0', 'name': 'test-action', 'status': "
        "'failed', 'message': 'error message', 'enqueued': '2024-05-29T14:50:08Z', 'started': "
        "'2024-05-29T14:50:11Z', 'completed': '2024-05-29T14:50:11Z'})"
    )
