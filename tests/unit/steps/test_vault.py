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
from unittest.mock import MagicMock, patch

import pytest

from cou.exceptions import ApplicationNotFound, VaultSealed
from cou.steps.vault import verify_vault_is_unsealed


@pytest.mark.asyncio
async def test_verify_vault_is_unsealed_sealed(model) -> None:
    model.get_application_names.return_value = ["app1", "app2"]
    model.get_application_status.return_value = MagicMock()
    model.get_application_status.return_value.status = MagicMock()
    model.get_application_status.return_value.status.info = "Unit is sealed"
    model.get_application_status.return_value.status.status = "blocked"
    err_msg = (
        "Vault is sealed, please follow the steps on "
        "https://charmhub.io/vault to unseal the vault manually before upgrade"
    )
    with pytest.raises(VaultSealed, match=err_msg):
        await verify_vault_is_unsealed(model)


@pytest.mark.parametrize(
    "case,info,status",
    [
        ["wrong info", "wrong info msg", "blocked"],
        ["wrong status", "Unit is sealed", "wrong status"],
    ],
)
@pytest.mark.asyncio
async def test_verify_vault_is_unsealed_unseal(case, info, status, model) -> None:
    model.get_application_names.return_value = ["app1", "app2"]
    model.get_application_status.return_value = MagicMock()
    model.get_application_status.return_value.status = MagicMock()
    model.get_application_status.return_value.status.info = info
    model.get_application_status.return_value.status.status = status
    await verify_vault_is_unsealed(model)


@pytest.mark.asyncio
@patch("cou.steps.vault.logger")
async def test_verify_vault_is_unsealed_vault_not_exists(mock_logger, model) -> None:
    model.get_application_names.side_effect = ApplicationNotFound
    await verify_vault_is_unsealed(model)
    mock_logger.warning.assert_called_once_with("Application vault not found, skip")
