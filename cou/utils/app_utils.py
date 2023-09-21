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
from collections.abc import Iterable

from juju.errors import JujuError

from cou.exceptions import ApplicationUpgradeError, CommandRunFailed
from cou.utils.juju_utils import COUModel

logger = logging.getLogger(__name__)


async def run_on_all_units(units: Iterable[str], model: COUModel, command: str) -> None:
    """Run command on each unit of an Application.

    :param units: The list of unit names where the command runs on.
    :type Iterable[str]
    :param model: COUModel object
    :type model: COUModel
    :param command: The command to run on each unit of an Application.
    :type str
    :raises ApplicationUpgradeError: When the application upgrade fails.
    """
    for unit in units:
        logger.info("Running '%s' on '%s'", command, unit)

        try:
            result = await model.run_on_unit(unit_name=unit, command=command, timeout=600)
            if str(result["Code"]) == "0":
                logger.debug(result["Stdout"])
            else:
                raise ApplicationUpgradeError(
                    f"Cannot upgrade application: operation on {unit} failed."
                ) from CommandRunFailed(cmd=command, result=result)

        except JujuError as exc:
            raise ApplicationUpgradeError(
                f"Cannot upgrade application: operation on {unit} failed."
            ) from exc
