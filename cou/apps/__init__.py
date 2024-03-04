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
"""Applications for charmed-openstack-upgrader."""
import os

STANDARD_IDLE_TIMEOUT: int = int(
    os.environ.get("COU_STANDARD_IDLE_TIMEOUT", 5 * 60)
)  # default of 5 min
LONG_IDLE_TIMEOUT: int = int(os.environ.get("COU_LONG_IDLE_TIMEOUT", 30 * 60))  # default of 30 min
