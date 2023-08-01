# Copyright 2023 Canonical Limited.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
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
async def test_analysis_add_special_charm(mocker, apps):
    """Test analysis object that adds special charm."""
    app_keystone = apps["keystone_ussuri"]
    app_cinder = apps["cinder_ussuri"]
    app_rmq = apps["rmq_ussuri"]
    expected_result = analyze.Analysis(apps=[app_keystone, app_cinder, app_rmq])
    mocker.patch.object(
        analyze.Analysis, "_populate", return_value=[app_keystone, app_cinder, app_rmq]
    )

    result = await Analysis.create()
    assert result == expected_result
    assert result.current_cloud_os_release == "ussuri"
    assert result.next_cloud_os_release == "victoria"
    # NOTE(gabrielcocenza) Although special charms, like rabbitmq, can have multiple OpenStack
    # releases to a workload version, it's necessary to set the right source on the charm
    # configuration. Rabbitmq with workload version 3.8, will always indicate that the application
    # is on yoga. However, we should configure the source accordingly with the OpenStack version of
    # the cloud. In this case, even that rabbitmq is theoretically on yoga, we should change the
    # source to cloud:focal-victoria and that is why it's added on apps to upgrade.
    assert result.os_versions == {"ussuri": {app_keystone, app_cinder}, "yoga": {app_rmq}}
    # rabbitmq is included because source is configured as "distro" for ussuri.
    assert result.apps_to_upgrade == [app_rmq, app_keystone, app_cinder]


@pytest.mark.asyncio
async def test_analysis_not_add_special_charms(mocker, apps):
    """Test analysis object when special charms are configured for a higher OpenStack version."""
    app_keystone = apps["keystone_ussuri"]
    app_cinder = apps["cinder_ussuri"]
    app_rmq = apps["rmq_wallaby"]
    expected_result = analyze.Analysis(apps=[app_keystone, app_cinder, app_rmq])
    mocker.patch.object(
        analyze.Analysis, "_populate", return_value=[app_keystone, app_cinder, app_rmq]
    )

    result = await Analysis.create()
    assert result == expected_result
    assert result.current_cloud_os_release == "ussuri"
    assert result.next_cloud_os_release == "victoria"
    assert result.os_versions == {"ussuri": {app_keystone, app_cinder}, "yoga": {app_rmq}}
    # rabbitmq is not included because source is configured for wallaby that is bigger than
    # the cloud OpenStack Version that is on ussuri.
    assert result.apps_to_upgrade == [app_keystone, app_cinder]
