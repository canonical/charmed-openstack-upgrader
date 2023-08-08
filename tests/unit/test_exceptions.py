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

from cou.exceptions import ActionFailed, CommandRunFailed, JujuError, UnitNotFound


def test_command_run_failed():
    with pytest.raises(CommandRunFailed):
        raise CommandRunFailed(cmd="cmd", code="1", output="nok", err="err")


def test_unit_not_found():
    with pytest.raises(UnitNotFound):
        raise UnitNotFound()


def test_juju_error():
    with pytest.raises(JujuError):
        raise JujuError()


def test_action_failed():
    with pytest.raises(ActionFailed):

        class TestClass:
            pass

        raise ActionFailed(action=TestClass(), output="output")
