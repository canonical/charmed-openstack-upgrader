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

"""Machine class."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Machine:
    """Representation of a juju machine."""

    machine_id: str
    hostname: str
    az: Optional[str]  # simple deployments may not have azs
    is_data_plane: bool

    def __repr__(self) -> str:
        """Representation of the juju Machine.

        :return: Representation of the juju Machine
        :rtype: str
        """
        return f"Machine[{self.machine_id}]"
