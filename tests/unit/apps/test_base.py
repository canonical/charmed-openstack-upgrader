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
from unittest.mock import MagicMock, patch

import pytest
from juju.client._definitions import UnitStatus

from cou.apps.base import OpenStackApplication
from cou.exceptions import ApplicationError


@patch("cou.apps.base.OpenStackApplication._verify_channel", return_value=None)
@patch("cou.utils.openstack.OpenStackCodenameLookup.find_compatible_versions")
def test_application_get_latest_os_version_failed(
    mock_find_compatible_versions, config, status, model, apps_machines
):
    charm = "app"
    app_name = "my_app"
    unit = MagicMock(spec_set=UnitStatus())
    unit.workload_version = "15.0.1"
    exp_error = (
        f"'{app_name}' with workload version {unit.workload_version} has no compatible OpenStack "
        "release."
    )
    mock_find_compatible_versions.return_value = []

    app = OpenStackApplication(app_name, MagicMock(), MagicMock(), MagicMock(), charm, {})

    with pytest.raises(ApplicationError, match=exp_error):
        app._get_latest_os_version(unit)

    mock_find_compatible_versions.assert_called_once_with(charm, unit.workload_version)
