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
        "\n"
        "rabbitmq-server:\n"
        "  model_name: my_model\n"
        "  charm: rabbitmq-server\n"
        "  charm_origin: ch\n"
        "  os_origin: distro\n"
        "  channel: 3.8/stable\n"
        "  units:\n"
        "    rabbitmq-server/0:\n"
        "      workload_version: '3.8'\n"
        "      os_version: yoga\n"
    )

    mocker.patch.object(
        analyze.Analysis,
        "_populate",
        return_value=[apps["keystone_ussuri"], apps["cinder_ussuri"], apps["rmq_ussuri"]],
    )
    result = await analyze.Analysis.create()
    assert str(result) == expected_result


@pytest.mark.asyncio
async def test_populate_model(mocker, full_status, config):
    mocker.patch.object(analyze, "async_get_status", return_value=full_status)
    mocker.patch.object(
        analyze, "async_get_application_config", return_value=config["openstack_ussuri"]
    )
    # Initially, 4 applications are in the status: keystone, cinder, rabbitmq-server and my-app
    # my-app is a unknown application in the model.
    assert len(full_status.applications) == 4
    apps = await Analysis._populate()
    assert len(apps) == 4
    # apps are on the UPGRADE_ORDER sequence and unknown in the end of the list
    assert [app.charm for app in apps] == ["rabbitmq-server", "keystone", "cinder", "my-app"]


@pytest.mark.asyncio
async def test_analysis_create(mocker, apps):
    """Test analysis object."""
    app_keystone = apps["keystone_ussuri"]
    app_cinder = apps["cinder_ussuri"]
    app_rmq = apps["rmq_ussuri"]
    app_mysql_router = apps["mysql_router_ussuri"]
    no_openstack = apps["no_openstack"]
    expected_result = analyze.Analysis(
        apps=[app_rmq, app_keystone, app_cinder, app_mysql_router, no_openstack]
    )
    mocker.patch.object(
        analyze.Analysis,
        "_populate",
        return_value=[app_rmq, app_keystone, app_cinder, app_mysql_router, no_openstack],
    )

    result = await Analysis.create()
    assert result == expected_result


@pytest.mark.asyncio
async def test_analysis_detect_current_cloud_os_release_different_releases(apps):
    keystone_wallaby = apps["keystone_wallaby"]
    cinder_ussuri = apps["cinder_ussuri"]
    rmq_ussuri = apps["rmq_ussuri"]
    app_mysql_router = apps["mysql_router_ussuri"]
    no_openstack = apps["no_openstack"]
    result = analyze.Analysis(
        apps=[rmq_ussuri, keystone_wallaby, cinder_ussuri, app_mysql_router, no_openstack]
    )

    # current_cloud_os_release takes the minimum OpenStack version
    assert result.current_cloud_os_release == "ussuri"


@pytest.mark.asyncio
async def test_analysis_detect_current_cloud_os_release_same_release(apps):
    keystone_wallaby = apps["keystone_ussuri"]
    cinder_ussuri = apps["cinder_ussuri"]
    result = analyze.Analysis(apps=[keystone_wallaby, cinder_ussuri])

    # current_cloud_os_release takes the minimum OpenStack version
    assert result.current_cloud_os_release == "ussuri"


@pytest.mark.asyncio
async def test_analysis_subordinate_charm(mocker, apps):
    """Test analysis object."""
    app_mysql_router = apps["mysql_router_ussuri"]
    result = analyze.Analysis(apps=[app_mysql_router])
    mock_logger = mocker.patch("cou.steps.analyze.logger")

    assert result.current_cloud_os_release is None
    mock_logger.warning.assert_called_once_with(
        "Ignoring %s when determining the minimum version of the cloud.", app_mysql_router.name
    )


@pytest.mark.asyncio
async def test_analysis_no_openstack_charm(mocker, apps):
    """Test analysis object."""
    no_openstack = apps["no_openstack"]
    result = analyze.Analysis(apps=[no_openstack])
    mock_logger = mocker.patch("cou.steps.analyze.logger")

    assert result.current_cloud_os_release is None
    mock_logger.debug.assert_called_once_with(
        (
            "Ignoring %s when determining the minimum version of the cloud: "
            "not an OpenStack charm."
        ),
        no_openstack.name,
    )
