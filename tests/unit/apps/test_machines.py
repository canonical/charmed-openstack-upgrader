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
import pytest

from cou.apps.machine import Machine


@pytest.mark.parametrize(
    "machine_id, hostname, az",
    [
        # one field different is considered another machine
        ("0", "juju-c307f8-my_model-0", "zone-3"),
        ("1", "juju-c307f8-my_model-1", "zone-2"),
    ],
)
def test_machine_not_eq(machine_id, hostname, az):
    machine_0 = Machine(machine_id="0", hostname="juju-c307f8-my_model-0", az="zone-1")
    machine_1 = Machine(machine_id=machine_id, hostname=hostname, az=az)

    assert machine_0 != machine_1


def test_machine_eq():
    machine_0 = Machine(machine_id="0", hostname="juju-c307f8-my_model-0", az="zone-1")

    machine_1 = Machine(machine_id="0", hostname="juju-c307f8-my_model-0", az="zone-1")

    assert machine_0 == machine_1


def test_machine_repr():
    machine_0 = Machine(machine_id="0", hostname="juju-c307f8-my_model-0", az="zone-1")
    expected_repr = "Machine[0]"
    assert repr(machine_0) == expected_repr
