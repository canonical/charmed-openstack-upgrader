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

import pytest

from cou.steps import analyze
from cou.steps.analyze import Analysis


@pytest.mark.asyncio
async def test_analysis_dump(mocker, apps):
    """Test analysis dump."""
    expected_result = (
        "keystone:\n"
        "  model_name: my_model\n"
        "  charm: keystone\n"
        "  charm_origin: ch\n"
        "  os_origin: distro\n"
        "  channel: ussuri/stable\n"
        "  units:\n"
        "    keystone/0:\n"
        "      workload_version: 17.0.1\n"
        "      os_version: ussuri\n"
        "    keystone/1:\n"
        "      workload_version: 17.0.1\n"
        "      os_version: ussuri\n"
        "    keystone/2:\n"
        "      workload_version: 17.0.1\n"
        "      os_version: ussuri\n"
        "\n"
        "cinder:\n"
        "  model_name: my_model\n"
        "  charm: cinder\n"
        "  charm_origin: ch\n"
        "  os_origin: distro\n"
        "  channel: ussuri/stable\n"
        "  units:\n"
        "    cinder/0:\n"
        "      workload_version: 16.4.2\n"
        "      os_version: ussuri\n"
        "    cinder/1:\n"
        "      workload_version: 16.4.2\n"
        "      os_version: ussuri\n"
        "    cinder/2:\n"
        "      workload_version: 16.4.2\n"
        "      os_version: ussuri\n"
    )

    mocker.patch.object(analyze.Analysis, "_populate", return_value=apps)
    result = await analyze.Analysis.create()
    assert str(result) == expected_result


@pytest.mark.asyncio
async def test_generate_model(mocker, full_status, config):
    mocker.patch.object(analyze, "async_get_status", return_value=full_status)
    mocker.patch.object(
        analyze, "async_get_application_config", return_value=config["openstack_ussuri"]
    )
    # Initially, 3 applications are in the status (keystone, cinder and rabbitmq-server)
    assert len(full_status.applications) == 3
    apps = await Analysis._populate()
    assert len(apps) == 3
    assert {app.charm for app in apps} == {"keystone", "cinder", "rabbitmq-server"}


@pytest.mark.asyncio
async def test_analysis(mocker, apps):
    """Test analysis function."""
    expected_result = analyze.Analysis(apps=apps)
    mocker.patch.object(analyze.Analysis, "_populate", return_value=apps)

    result = await Analysis.create()
    assert result == expected_result
