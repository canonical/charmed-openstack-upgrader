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

from cou.exceptions import ApplicationNotFound, VaultSealed
from cou.utils.juju_utils import Model

logger = logging.getLogger(__name__)


async def verify_vault_is_unsealed(model: Model) -> None:
    """Verify vault is unsealed.

    Check vault status. If vault is sealed, raise VaultSealed.

    :param model: juju model to work with
    :type model: Model
    :raises VaultSealed: if application in sealed status
    """
    try:
        app_names = await model.get_application_names(charm_name="vault")
        for app_name in app_names:
            app = await model.get_application_status(app_name=app_name)
            if app.status.info == "Unit is sealed" and app.status.status == "blocked":
                raise VaultSealed(
                    "Vault is sealed, please follow the steps on "
                    "https://charmhub.io/vault to unseal the vault manually before upgrade"
                )
    except ApplicationNotFound:
        logger.warning("Application vault not found, skip")
    logger.debug("Vault not in sealed status")
