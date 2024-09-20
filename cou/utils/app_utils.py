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

"""Application utilities."""
import logging
from typing import Optional

from cou.utils.juju_utils import Model

logger = logging.getLogger(__name__)


async def upgrade_packages(unit: str, model: Model, packages_to_hold: Optional[list]) -> None:
    """Run package updates and upgrades on each unit of an Application.

    :param unit: Unit name where the package upgrade runs on.
    :type unit: str
    :param model: Model object
    :type model: Model
    :param packages_to_hold: A list of packages to put on hold during package upgrade.
    :type packages_to_hold: Optional[list]
    :raises CommandRunFailed: When a command fails to run.
    """
    dpkg_opts = "-o Dpkg::Options::=--force-confnew -o Dpkg::Options::=--force-confdef"
    command = f"apt-get update && apt-get dist-upgrade {dpkg_opts} -y && apt-get autoremove -y"
    if packages_to_hold:
        packages = " ".join(packages_to_hold)
        command = f"apt-mark hold {packages} && {command} ; apt-mark unhold {packages}"

    await model.run_on_unit(unit_name=unit, command=command, timeout=600)
