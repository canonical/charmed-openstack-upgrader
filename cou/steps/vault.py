# Copyright 2024 Canonical Limited
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
"""Functions for prereq steps relating to vault."""
import logging
from typing import Sequence

from cou.exceptions import ApplicationNotFound, VaultSealed
from cou.utils.juju_utils import Application, get_applications_by_charm_name

logger = logging.getLogger(__name__)


async def verify_vault_is_unsealed(apps: Sequence[Application]) -> None:
    """Verify vault is unsealed.

    Check vault status. If vault is sealed, raise VaultSealed.

    :param apps: List of Application
    :type apps: Sequence[Application]
    :raises VaultSealed: if application in sealed
    """
    try:
        apps = await get_applications_by_charm_name(apps, "vault")
        for app in apps:
            app_status = app.status
            if (
                app_status.status.info == "Unit is sealed"
                and app_status.status.status == "blocked"
            ):
                raise VaultSealed(
                    "Vault is sealed, please follow the steps on "
                    "https://charmhub.io/vault to unseal the vault manually before upgrade"
                )
    except ApplicationNotFound:
        logger.warning("Application vault not found, skip")
    logger.debug("Vault not in sealed status")
