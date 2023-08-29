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

from cou.exceptions import PackageUpgradeError
from cou.utils.juju_utils import async_run_on_unit

logger = logging.getLogger(__name__)


async def upgrade_packages(units: Iterable[str], model_name: str) -> None:
    """Run package updates and upgrades on each unit of an Application.

    :param units: The list of unit names where the package upgrade runs on.
    :type Iterable[str]
    :param model_name: The name of the model that the application belongs to.
    :type str
    :raises PackageUpgradeError: When the package upgrade fails.
    """
    dpkg_opts = "-o Dpkg::Options::=--force-confnew -o Dpkg::Options::=--force-confdef"
    command = f"apt-get update && apt-get dist-upgrade {dpkg_opts} -y && apt-get autoremove -y"

    for unit in units:
        logger.info("Running '%s' on '%s'", command, unit)

        try:
            result = await async_run_on_unit(
                unit_name=unit, command=command, model_name=model_name, timeout=600
            )
            if str(result["Code"]) == "0":
                logger.debug(result["Stdout"])
            else:
                logger.error("Error upgrading package on %s: %s", unit, result["Stderr"])
                raise PackageUpgradeError()
        except JujuError as exc:
            logger.error("Failed running package upgrade on %s: %s", unit, exc)
            raise PackageUpgradeError() from exc
