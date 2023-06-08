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

from collections import defaultdict

import pytest

from cou.steps import analyze


@pytest.mark.parametrize(
    "issues",
    [
        "no_issues",
        "os_release_units",
        "change_channel",
        "charmhub_migration",
        "change_openstack_release",
    ],
)
def test_application(issues, status, config, mocker):
    """Test the object Application on different scenarios."""
    expected_os_release_units = defaultdict(set)
    expected_pkg_version_units = defaultdict(set)
    expected_upgrade_units = defaultdict(set)
    expected_change_channel = defaultdict(set)
    expected_charmhub_migration = defaultdict(set)
    expected_change_openstack_release = defaultdict(set)

    app_status = status["keystone_ch"]
    app_config = config["keystone"]
    expected_origin = "ch"

    if issues == "os_release_units":
        # different package version for keystone/2
        mocker.patch.object(
            analyze,
            "get_pkg_version",
            side_effect=["2:17.0.1-0ubuntu1", "2:17.0.1-0ubuntu1", "2:18.1.0-0ubuntu1~cloud0"],
        )
        expected_pkg_version_units["2:17.0.1-0ubuntu1"] = {
            "keystone/0",
            "keystone/1",
        }
        expected_pkg_version_units["2:18.1.0-0ubuntu1~cloud0"] = {
            "keystone/2",
        }
        expected_os_version_units = {"victoria", "ussuri"}
        expected_os_release_units["ussuri"] = {"keystone/0", "keystone/1"}
        expected_os_release_units["victoria"] = {"keystone/2"}
        expected_upgrade_units["victoria"] = {"keystone/0", "keystone/1"}

    elif issues == "change_channel":
        # application has wrong channel in status
        mocker.patch.object(analyze, "get_pkg_version", return_value="2:17.0.1-0ubuntu1")
        expected_os_release_units["ussuri"] = {"keystone/0", "keystone/1", "keystone/2"}
        expected_pkg_version_units["2:17.0.1-0ubuntu1"] = {
            "keystone/0",
            "keystone/1",
            "keystone/2",
        }
        expected_os_version_units = {"ussuri"}
        app_status = status["keystone_wrong_channel"]
        expected_change_channel["ussuri/stable"] = {"keystone"}

    elif issues == "charmhub_migration":
        # application is from charm store
        expected_origin = "cs"
        mocker.patch.object(analyze, "get_pkg_version", return_value="2:17.0.1-0ubuntu1")
        expected_os_release_units["ussuri"] = {"keystone/0", "keystone/1", "keystone/2"}
        expected_pkg_version_units["2:17.0.1-0ubuntu1"] = {
            "keystone/0",
            "keystone/1",
            "keystone/2",
        }
        expected_os_version_units = {"ussuri"}
        app_status = status["keystone_cs"]
        expected_charmhub_migration["ussuri/stable"] = {"keystone"}

    elif issues == "change_openstack_release":
        # application has wrong configuration for openstack-release
        app_config = config["keystone_wrong_os_origin"]
        mocker.patch.object(analyze, "get_pkg_version", return_value="2:17.0.1-0ubuntu1")
        expected_os_release_units["ussuri"] = {"keystone/0", "keystone/1", "keystone/2"}
        expected_pkg_version_units["2:17.0.1-0ubuntu1"] = {
            "keystone/0",
            "keystone/1",
            "keystone/2",
        }
        expected_os_version_units = {"ussuri"}
        expected_change_openstack_release["distro"] = {"keystone"}

    else:
        mocker.patch.object(analyze, "get_pkg_version", return_value="2:17.0.1-0ubuntu1")
        expected_os_release_units["ussuri"] = {"keystone/0", "keystone/1", "keystone/2"}
        expected_pkg_version_units["2:17.0.1-0ubuntu1"] = {
            "keystone/0",
            "keystone/1",
            "keystone/2",
        }
        expected_os_version_units = {"ussuri"}

    mocker.patch.object(analyze, "get_openstack_release", return_value=None)

    app = analyze.Application("keystone", app_status, app_config, "my_model")
    assert app.name == "keystone"
    assert app.status == app_status
    assert app.model_name == "my_model"
    assert app.config == app_config
    assert app.os_version_units == expected_os_version_units
    assert app.charm == "keystone"
    assert app.units == {"keystone/0", "keystone/1", "keystone/2"}
    assert app.channel == app_status.base["channel"]
    assert app.pkg_name == "keystone"
    assert app.os_release_units == expected_os_release_units
    assert app.pkg_version_units == expected_pkg_version_units

    assert app.check_os_versions_units(defaultdict(set)) == expected_upgrade_units
    assert app.origin == expected_origin
    assert app.check_os_channels_and_migration(defaultdict(set), defaultdict(set)) == (
        expected_change_channel,
        expected_charmhub_migration,
    )
    assert app.check_os_origin(defaultdict(set)) == expected_change_openstack_release


# class TestAnalyze(unittest.TestCase):
#     def test_check_os_versions(self):
#         # scenario where everything is ok
#         os_release_units_keystone = defaultdict(set)
#         os_release_units_cinder = defaultdict(set)
#         os_release_units_keystone["ussuri"].update({"keystone/0", "keystone/1", "keystone/2"})
#         os_release_units_cinder["ussuri"].update({"cinder/0"})
#         os_versions = {"keystone": os_release_units_keystone, "cinder": os_release_units_cinder}
#         results = analyze.check_os_versions(os_versions)
#         expected_result = defaultdict(set)
#         expected_result["victoria"].update({"keystone", "cinder"})
#         upgrade_charms = results[1]
#         self.assertEqual(upgrade_charms, expected_result)

#     def test_check_os_versions_upgrade_units(self):
#         # scenario where it needs to upgrade units
#         os_release_units = defaultdict(set)
#         os_release_units["ussuri"].update({"keystone/1", "keystone/2"})
#         os_release_units["victoria"].update({"keystone/0"})
#         os_versions = {"keystone": os_release_units}
#         results = analyze.check_os_versions(os_versions)
#         expected_result = defaultdict(set)
#         expected_result["victoria"].update({"keystone/1", "keystone/2"})
#         upgrade_units = results[0]
#         self.assertEqual(upgrade_units, expected_result)

#     def test_check_os_versions_upgrade_charms(self):
#         # scenario where it needs to upgrade charms
#         os_release_units_keystone = defaultdict(set)
#         os_release_units_keystone["victoria"].update({"keystone/0"})
#         os_release_units_cinder = defaultdict(set)
#         os_release_units_cinder["ussuri"].update({"cinder/0"})
#         os_versions = {"keystone": os_release_units_keystone, "cinder": os_release_units_cinder}
#         expected_result = defaultdict(set)
#         expected_result["victoria"].update({"cinder"})
#         results = analyze.check_os_versions(os_versions)
#         upgrade_charms = results[1]
#         self.assertEqual(expected_result, upgrade_charms)

#     def test_check_os_channels_and_migration(self):
#         # scenario where everything is ok
#         os_release_units_keystone = defaultdict(set)
#         os_release_units_keystone["ussuri"].update({"keystone/0", "keystone/1", "keystone/2"})
#         os_versions = {"keystone": os_release_units_keystone}
#         with patch("cou.steps.analyze.extract_app_channel_and_origin") as mock_app_channel_origin:
#             mock_app_channel_origin.return_value = ("ussuri/stable", "keystone")
#             change_channel, charmhub_migration = analyze.check_os_channels_and_migration(
#                 os_versions
#             )
#         expected_result_change_channel = defaultdict(set)
#         expected_result_charmhub_migration = defaultdict(set)
#         self.assertEqual(expected_result_change_channel, change_channel)
#         self.assertEqual(expected_result_charmhub_migration, charmhub_migration)

#     def test_check_os_channels_and_migration_track_channel(self):
#         # scenario where needs track a channel
#         os_release_units_keystone = defaultdict(set)
#         os_release_units_keystone["ussuri"].update({"keystone/0", "keystone/1", "keystone/2"})
#         os_versions = {"keystone": os_release_units_keystone}
#         with patch("cou.steps.analyze.extract_app_channel_and_origin") as mock_app_channel_origin:
#             mock_app_channel_origin.return_value = ("latest/stable", "keystone")
#             change_channel, charmhub_migration = analyze.check_os_channels_and_migration(
#                 os_versions
#             )
#         expected_result_change_channel = defaultdict(set)
#         expected_result_charmhub_migration = defaultdict(set)
#         expected_result_change_channel["ussuri/stable"].update({"keystone"})
#         self.assertEqual(expected_result_change_channel, change_channel)
#         self.assertEqual(expected_result_charmhub_migration, charmhub_migration)

#     def test_check_os_channels_and_migration_ch_migration(self):
#         # scenario where needs migration because of charmstore
#         os_release_units_keystone = defaultdict(set)
#         os_release_units_keystone["ussuri"].update({"keystone/0", "keystone/1", "keystone/2"})
#         os_versions = {"keystone": os_release_units_keystone}
#         with patch("cou.steps.analyze.extract_app_channel_and_origin") as mock_app_channel_origin:
#             mock_app_channel_origin.return_value = ("ussuri/stable", "cs")
#             change_channel, charmhub_migration = analyze.check_os_channels_and_migration(
#                 os_versions
#             )

#         expected_result_change_channel = defaultdict(set)
#         expected_result_charmhub_migration = defaultdict(set)
#         expected_result_charmhub_migration["ussuri/stable"].update({"keystone"})
#         self.assertEqual(expected_result_change_channel, change_channel)
#         self.assertEqual(expected_result_charmhub_migration, charmhub_migration)

#     def test_check_os_channels_and_migration_skip(self):
#         # scenario where skip check because different versions of openstack
#         os_release_units_keystone = defaultdict(set)
#         os_release_units_keystone["ussuri"].update({"keystone/0"})
#         os_release_units_keystone["victoria"].update({"keystone/1"})
#         os_versions = {"keystone": os_release_units_keystone}
#         with patch("cou.steps.analyze.extract_app_channel_and_origin") as mock_app_channel_origin:
#             mock_app_channel_origin.return_value = ("ussuri/stable", "keystone")
#             change_channel, charmhub_migration = analyze.check_os_channels_and_migration(
#                 os_versions
#             )

#         expected_result_change_channel = defaultdict(set)
#         expected_result_charmhub_migration = defaultdict(set)
#         self.assertEqual(expected_result_change_channel, change_channel)
#         self.assertEqual(expected_result_charmhub_migration, charmhub_migration)

#     def test_check_os_release(self):
#         # scenario where everything is ok
#         os_release_units_keystone = defaultdict(set)
#         os_release_units_keystone["ussuri"].update({"keystone/0", "keystone/1", "keystone/2"})
#         os_versions = {"keystone": os_release_units_keystone}
#         with patch("cou.steps.analyze.extract_os_charm_config") as mock_os_charm_config:
#             mock_os_charm_config.return_value = "distro"
#             result = analyze.check_os_origin(os_versions)

#         expected_result = defaultdict(set)
#         self.assertEqual(result, expected_result)

#     def test_check_os_release_ussuri_distro(self):
#         # scenario where 'distro' is not set to ussuri
#         os_release_units_keystone = defaultdict(set)
#         os_release_units_keystone["ussuri"].update({"keystone/0", "keystone/1", "keystone/2"})
#         os_versions = {"keystone": os_release_units_keystone}
#         with patch("cou.steps.analyze.extract_os_charm_config") as mock_os_charm_config:
#             mock_os_charm_config.return_value = "cloud:focal-ussuri"
#             result = analyze.check_os_origin(os_versions)

#         expected_result = defaultdict(set)
#         expected_result["distro"].update({"keystone"})
#         self.assertEqual(result, expected_result)

#     def test_check_os_release_config(self):
#         # scenario where it needs to change openstack release config
#         os_release_units_keystone = defaultdict(set)
#         os_release_units_keystone["victoria"].update({"keystone/0", "keystone/1", "keystone/2"})
#         os_versions = {"keystone": os_release_units_keystone}
#         with patch("cou.steps.analyze.extract_os_charm_config") as mock_os_charm_config:
#             mock_os_charm_config.return_value = "distro"
#             result = analyze.check_os_origin(os_versions)
#         expected_result = defaultdict(set)
#         expected_result["cloud:focal-victoria"].update({"keystone"})
#         self.assertEqual(result, expected_result)

#     def test_check_os_release_skip(self):
#         # scenario where skip check because different versions of openstack
#         os_release_units_keystone = defaultdict(set)
#         os_release_units_keystone["ussuri"].update({"keystone/0"})
#         os_release_units_keystone["victoria"].update({"keystone/1"})
#         os_versions = {"keystone": os_release_units_keystone}
#         with patch("cou.steps.analyze.extract_os_charm_config") as mock_os_charm_config:
#             mock_os_charm_config.return_value = "distro"
#             result = analyze.check_os_origin(os_versions)
#         expected_result = defaultdict(set)
#         self.assertEqual(result, expected_result)

#     def test_analyze(self):
#         os_release_units_keystone = defaultdict(set)
#         upgrade_units = defaultdict(set)
#         upgrade_charms = defaultdict(set)
#         change_channel = defaultdict(set)
#         charmhub_migration = defaultdict(set)
#         change_openstack_release = defaultdict(set)
#         os_release_units_keystone["ussuri"].update({"keystone/0"})
#         os_versions = {"keystone": os_release_units_keystone}
#         with patch("cou.steps.analyze.extract_os_versions") as mock_os_versions, patch(
#             "cou.steps.analyze.check_os_channels_and_migration"
#         ) as mock_channels_migrations, patch(
#             "cou.steps.analyze.check_os_origin"
#         ) as mock_os_origin:
#             mock_os_versions.return_value = os_versions
#             mock_channels_migrations.return_value = (change_channel, charmhub_migration)
#             mock_os_origin.return_value = change_openstack_release
#             upgrade_charms["victoria"].add("keystone")
#             expected_result = analyze.Analyze(
#                 upgrade_units,
#                 upgrade_charms,
#                 change_channel,
#                 charmhub_migration,
#                 change_openstack_release,
#             )
#             result = analyze.analyze()
#             self.assertEqual(result, expected_result)

#     def test_extract_app_channel_and_origin(self):
#         with mock.patch("cou.steps.analyze.get_application_status") as mock_app_status:
#             mock_app_status.return_value = FAKE_STATUS
#             app_channel, charm_origin = analyze.extract_app_channel_and_origin("keystone")
#         expected_app_channel = "ussuri/stable"
#         expected_charm_origin = "keystone"
#         self.assertEqual(app_channel, expected_app_channel)
#         self.assertEqual(charm_origin, expected_charm_origin)

#     def test_extract_os_charm_config(self):
#         with mock.patch("cou.steps.analyze.model.get_application_config") as mock_app_config:
#             mock_app_config.return_value = {"openstack-origin": {"value": "cloud:focal-victoria"}}
#             result = analyze.extract_os_charm_config("keystone")
#         expected = "cloud:focal-victoria"
#         self.assertEqual(result, expected)

#     def test_extract_os_charm_config_empty(self):
#         with mock.patch("cou.steps.analyze.model.get_application_config") as mock_app_config:
#             mock_app_config.return_value = {"foo": {"value": "bar"}}
#             result = analyze.extract_os_charm_config("keystone")
#         expected = ""
#         self.assertEqual(result, expected)

#     def test_extract_os_versions(self):
#         mock_status = mock.MagicMock()
#         mock_charm = mock.MagicMock()
#         mock_charm.charm = "ch:keystone"
#         mock_status.applications = {"keystone": mock_charm}
#         with mock.patch("cou.steps.analyze.get_full_juju_status") as mock_app, mock.patch(
#             "cou.steps.analyze.get_current_os_versions"
#         ) as mock_os_versions:
#             mock_app.return_value = mock_status
#             analyze.extract_os_versions()
#             mock_app.assert_called_once()
#             mock_os_versions.assert_called_once()
