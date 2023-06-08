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

import unittest
from collections import defaultdict
from unittest.mock import patch

import mock

from cou.steps import analyze

FAKE_STATUS = {
    "can-upgrade-to": "",
    "charm": "keystone",
    "subordinate-to": [],
    "charm-channel": "ussuri/stable",
    "units": {
        "keystone/0": {
            "leader": True,
            "machine": "0",
            "subordinates": {
                "app-hacluster/0": {"charm": "local:trusty/hacluster-0", "leader": True}
            },
        },
        "keystone/1": {
            "machine": "1",
            "subordinates": {"app-hacluster/1": {"charm": "local:trusty/hacluster-0"}},
        },
        "keystone/2": {
            "machine": "2",
            "subordinates": {"app-hacluster/2": {"charm": "local:trusty/hacluster-0"}},
        },
    },
}


class TestAnalyze(unittest.TestCase):
    def test_check_os_versions(self):
        # scenario where everything is ok
        os_release_units_keystone = defaultdict(set)
        os_release_units_cinder = defaultdict(set)
        os_release_units_keystone["ussuri"].update({"keystone/0", "keystone/1", "keystone/2"})
        os_release_units_cinder["ussuri"].update({"cinder/0"})
        os_versions = {"keystone": os_release_units_keystone, "cinder": os_release_units_cinder}
        results = analyze.check_os_versions(os_versions)
        expected_result = defaultdict(set)
        expected_result["victoria"].update({"keystone", "cinder"})
        upgrade_charms = results[1]
        self.assertEqual(upgrade_charms, expected_result)

    def test_check_os_versions_upgrade_units(self):
        # scenario where it needs to upgrade units
        os_release_units = defaultdict(set)
        os_release_units["ussuri"].update({"keystone/1", "keystone/2"})
        os_release_units["victoria"].update({"keystone/0"})
        os_versions = {"keystone": os_release_units}
        results = analyze.check_os_versions(os_versions)
        expected_result = defaultdict(set)
        expected_result["victoria"].update({"keystone/1", "keystone/2"})
        upgrade_units = results[0]
        self.assertEqual(upgrade_units, expected_result)

    def test_check_os_versions_upgrade_charms(self):
        # scenario where it needs to upgrade charms
        os_release_units_keystone = defaultdict(set)
        os_release_units_keystone["victoria"].update({"keystone/0"})
        os_release_units_cinder = defaultdict(set)
        os_release_units_cinder["ussuri"].update({"cinder/0"})
        os_versions = {"keystone": os_release_units_keystone, "cinder": os_release_units_cinder}
        expected_result = defaultdict(set)
        expected_result["victoria"].update({"cinder"})
        results = analyze.check_os_versions(os_versions)
        upgrade_charms = results[1]
        self.assertEqual(expected_result, upgrade_charms)

    def test_check_os_channels_and_migration(self):
        # scenario where everything is ok
        os_release_units_keystone = defaultdict(set)
        os_release_units_keystone["ussuri"].update({"keystone/0", "keystone/1", "keystone/2"})
        os_versions = {"keystone": os_release_units_keystone}
        with patch("cou.steps.analyze.extract_app_channel_and_origin") as mock_app_channel_origin:
            mock_app_channel_origin.return_value = ("ussuri/stable", "keystone")
            change_channel, charmhub_migration = analyze.check_os_channels_and_migration(
                os_versions
            )
        expected_result_change_channel = defaultdict(set)
        expected_result_charmhub_migration = defaultdict(set)
        self.assertEqual(expected_result_change_channel, change_channel)
        self.assertEqual(expected_result_charmhub_migration, charmhub_migration)

    def test_check_os_channels_and_migration_track_channel(self):
        # scenario where needs track a channel
        os_release_units_keystone = defaultdict(set)
        os_release_units_keystone["ussuri"].update({"keystone/0", "keystone/1", "keystone/2"})
        os_versions = {"keystone": os_release_units_keystone}
        with patch("cou.steps.analyze.extract_app_channel_and_origin") as mock_app_channel_origin:
            mock_app_channel_origin.return_value = ("latest/stable", "keystone")
            change_channel, charmhub_migration = analyze.check_os_channels_and_migration(
                os_versions
            )
        expected_result_change_channel = defaultdict(set)
        expected_result_charmhub_migration = defaultdict(set)
        expected_result_change_channel["ussuri/stable"].update({"keystone"})
        self.assertEqual(expected_result_change_channel, change_channel)
        self.assertEqual(expected_result_charmhub_migration, charmhub_migration)

    def test_check_os_channels_and_migration_ch_migration(self):
        # scenario where needs migration because of charmstore
        os_release_units_keystone = defaultdict(set)
        os_release_units_keystone["ussuri"].update({"keystone/0", "keystone/1", "keystone/2"})
        os_versions = {"keystone": os_release_units_keystone}
        with patch("cou.steps.analyze.extract_app_channel_and_origin") as mock_app_channel_origin:
            mock_app_channel_origin.return_value = ("ussuri/stable", "cs")
            change_channel, charmhub_migration = analyze.check_os_channels_and_migration(
                os_versions
            )

        expected_result_change_channel = defaultdict(set)
        expected_result_charmhub_migration = defaultdict(set)
        expected_result_charmhub_migration["ussuri/stable"].update({"keystone"})
        self.assertEqual(expected_result_change_channel, change_channel)
        self.assertEqual(expected_result_charmhub_migration, charmhub_migration)

    def test_check_os_channels_and_migration_skip(self):
        # scenario where skip check because different versions of openstack
        os_release_units_keystone = defaultdict(set)
        os_release_units_keystone["ussuri"].update({"keystone/0"})
        os_release_units_keystone["victoria"].update({"keystone/1"})
        os_versions = {"keystone": os_release_units_keystone}
        with patch("cou.steps.analyze.extract_app_channel_and_origin") as mock_app_channel_origin:
            mock_app_channel_origin.return_value = ("ussuri/stable", "keystone")
            change_channel, charmhub_migration = analyze.check_os_channels_and_migration(
                os_versions
            )

        expected_result_change_channel = defaultdict(set)
        expected_result_charmhub_migration = defaultdict(set)
        self.assertEqual(expected_result_change_channel, change_channel)
        self.assertEqual(expected_result_charmhub_migration, charmhub_migration)

    def test_check_os_release(self):
        # scenario where everything is ok
        os_release_units_keystone = defaultdict(set)
        os_release_units_keystone["ussuri"].update({"keystone/0", "keystone/1", "keystone/2"})
        os_versions = {"keystone": os_release_units_keystone}
        with patch("cou.steps.analyze.extract_os_charm_config") as mock_os_charm_config:
            mock_os_charm_config.return_value = "distro"
            result = analyze.check_os_origin(os_versions)

        expected_result = defaultdict(set)
        self.assertEqual(result, expected_result)

    def test_check_os_release_ussuri_distro(self):
        # scenario where 'distro' is not set to ussuri
        os_release_units_keystone = defaultdict(set)
        os_release_units_keystone["ussuri"].update({"keystone/0", "keystone/1", "keystone/2"})
        os_versions = {"keystone": os_release_units_keystone}
        with patch("cou.steps.analyze.extract_os_charm_config") as mock_os_charm_config:
            mock_os_charm_config.return_value = "cloud:focal-ussuri"
            result = analyze.check_os_origin(os_versions)

        expected_result = defaultdict(set)
        expected_result["distro"].update({"keystone"})
        self.assertEqual(result, expected_result)

    def test_check_os_release_config(self):
        # scenario where it needs to change openstack release config
        os_release_units_keystone = defaultdict(set)
        os_release_units_keystone["victoria"].update({"keystone/0", "keystone/1", "keystone/2"})
        os_versions = {"keystone": os_release_units_keystone}
        with patch("cou.steps.analyze.extract_os_charm_config") as mock_os_charm_config:
            mock_os_charm_config.return_value = "distro"
            result = analyze.check_os_origin(os_versions)
        expected_result = defaultdict(set)
        expected_result["cloud:focal-victoria"].update({"keystone"})
        self.assertEqual(result, expected_result)

    def test_check_os_release_skip(self):
        # scenario where skip check because different versions of openstack
        os_release_units_keystone = defaultdict(set)
        os_release_units_keystone["ussuri"].update({"keystone/0"})
        os_release_units_keystone["victoria"].update({"keystone/1"})
        os_versions = {"keystone": os_release_units_keystone}
        with patch("cou.steps.analyze.extract_os_charm_config") as mock_os_charm_config:
            mock_os_charm_config.return_value = "distro"
            result = analyze.check_os_origin(os_versions)
        expected_result = defaultdict(set)
        self.assertEqual(result, expected_result)

    def test_analyze(self):
        os_release_units_keystone = defaultdict(set)
        upgrade_units = defaultdict(set)
        upgrade_charms = defaultdict(set)
        change_channel = defaultdict(set)
        charmhub_migration = defaultdict(set)
        change_openstack_release = defaultdict(set)
        os_release_units_keystone["ussuri"].update({"keystone/0"})
        os_versions = {"keystone": os_release_units_keystone}
        with patch("cou.steps.analyze.extract_os_versions") as mock_os_versions, patch(
            "cou.steps.analyze.check_os_channels_and_migration"
        ) as mock_channels_migrations, patch(
            "cou.steps.analyze.check_os_origin"
        ) as mock_os_origin:
            mock_os_versions.return_value = os_versions
            mock_channels_migrations.return_value = (change_channel, charmhub_migration)
            mock_os_origin.return_value = change_openstack_release
            upgrade_charms["victoria"].add("keystone")
            expected_result = analyze.Analyze(
                upgrade_units,
                upgrade_charms,
                change_channel,
                charmhub_migration,
                change_openstack_release,
            )
            result = analyze.analyze()
            self.assertEqual(result, expected_result)

    def test_extract_app_channel_and_origin(self):
        with mock.patch("cou.steps.analyze.get_application_status") as mock_app_status:
            mock_app_status.return_value = FAKE_STATUS
            app_channel, charm_origin = analyze.extract_app_channel_and_origin("keystone")
        expected_app_channel = "ussuri/stable"
        expected_charm_origin = "keystone"
        self.assertEqual(app_channel, expected_app_channel)
        self.assertEqual(charm_origin, expected_charm_origin)

    def test_extract_os_charm_config(self):
        with mock.patch("cou.steps.analyze.model.get_application_config") as mock_app_config:
            mock_app_config.return_value = {"openstack-origin": {"value": "cloud:focal-victoria"}}
            result = analyze.extract_os_charm_config("keystone")
        expected = "cloud:focal-victoria"
        self.assertEqual(result, expected)

    def test_extract_os_charm_config_empty(self):
        with mock.patch("cou.steps.analyze.model.get_application_config") as mock_app_config:
            mock_app_config.return_value = {"foo": {"value": "bar"}}
            result = analyze.extract_os_charm_config("keystone")
        expected = ""
        self.assertEqual(result, expected)

    def test_extract_os_versions(self):
        mock_status = mock.MagicMock()
        mock_charm = mock.MagicMock()
        mock_charm.charm = "ch:keystone"
        mock_status.applications = {"keystone": mock_charm}
        with mock.patch("cou.steps.analyze.get_full_juju_status") as mock_app, mock.patch(
            "cou.steps.analyze.get_current_os_versions"
        ) as mock_os_versions:
            mock_app.return_value = mock_status
            analyze.extract_os_versions()
            mock_app.assert_called_once()
            mock_os_versions.assert_called_once()
