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
    # apps are on the UPGRADE_ORDER sequence
    assert [app.charm for app in apps] == ["rabbitmq-server", "keystone", "cinder"]


@pytest.mark.asyncio
async def test_analysis_add_special_charm(mocker, apps):
    """Test analysis object that adds special charm."""
    app_keystone = apps["keystone_ussuri"]
    app_cinder = apps["cinder_ussuri"]
    app_rmq = apps["rmq_ussuri"]
    expected_result = analyze.Analysis(apps=[app_rmq, app_keystone, app_cinder])
    mocker.patch.object(
        analyze.Analysis, "_populate", return_value=[app_rmq, app_keystone, app_cinder]
    )

    result = await Analysis.create()
    assert result == expected_result
    assert result.current_cloud_os_release == "ussuri"
    assert result.next_cloud_os_release == "victoria"
    # NOTE(gabrielcocenza) Although special charms, like rabbitmq, can have multiple OpenStack
    # releases with workload version 3.8, the most recent version is considered and in this
    # case is yoga.
    assert result.os_versions == {
        "ussuri": {app_keystone.name, app_cinder.name},
        "yoga": {app_rmq.name},
    }
