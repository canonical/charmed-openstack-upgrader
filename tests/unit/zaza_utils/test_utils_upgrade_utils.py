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

import copy
import pprint

import mock

import cou.zaza_utils.upgrade_utils as openstack_upgrade
import tests.unit.utils as ut_utils


class TestUpgradeUtils(ut_utils.BaseTestCase):
    def setUp(self):
        super(TestUpgradeUtils, self).setUp()
        self.patch_object(openstack_upgrade.model, "get_units")
        self.juju_status = mock.MagicMock()
        self.patch_object(openstack_upgrade.model, "get_status", return_value=self.juju_status)
        self.patch_object(openstack_upgrade.model, "get_application_config")

        def _get_application_config(app, model_name=None):
            app_config = {
                "ceph-mon": {"verbose": True, "source": "old-src"},
                "neutron-openvswitch": {"verbose": True},
                "ntp": {"verbose": True},
                "percona-cluster": {"verbose": True, "source": "old-src"},
                "cinder": {
                    "verbose": True,
                    "openstack-origin": "old-src",
                    "action-managed-upgrade": False,
                },
                "neutron-api": {
                    "verbose": True,
                    "openstack-origin": "old-src",
                    "action-managed-upgrade": False,
                },
                "nova-compute": {
                    "verbose": True,
                    "openstack-origin": "old-src",
                    "action-managed-upgrade": False,
                },
            }
            return app_config[app]

        self.get_application_config.side_effect = _get_application_config
        self.juju_status.applications = {
            "mydb": {"charm": "cs:percona-cluster"},  # Filter as it is on UPGRADE_EXCLUDE_LIST
            "neutron-openvswitch": {  # Filter as it is a subordinates
                "charm": "cs:neutron-openvswitch",
                "subordinate-to": "nova-compute",
            },
            "ntp": {"charm": "cs:ntp"},  # Filter as it has no source option
            "nova-compute": {
                "charm": "cs:nova-compute",
                "units": {
                    "nova-compute/0": {
                        "subordinates": {
                            "neutron-openvswitch/2": {"charm": "cs:neutron-openvswitch-22"}
                        }
                    }
                },
            },
            "cinder": {
                "charm": "cs:cinder-23",
                "units": {
                    "cinder/1": {
                        "subordinates": {
                            "cinder-hacluster/0": {"charm": "cs:hacluster-42"},
                            "cinder-ceph/3": {"charm": "cs:cinder-ceph-2"},
                        }
                    }
                },
            },
        }

    def test_get_upgrade_candidates(self):
        expected = copy.deepcopy(self.juju_status.applications)
        self.assertEqual(openstack_upgrade.get_upgrade_candidates(), expected)

    def test_get_upgrade_groups(self):
        expected = [
            ("Database Services", []),
            ("Stateful Services", []),
            ("Core Identity", []),
            ("Control Plane", ["cinder"]),
            ("Data Plane", ["nova-compute"]),
            ("sweep_up", []),
        ]
        actual = openstack_upgrade.get_upgrade_groups()
        pprint.pprint(expected)
        pprint.pprint(actual)
        self.assertEqual(actual, expected)

    def test_extract_charm_name_from_url(self):
        self.assertEqual(
            openstack_upgrade.extract_charm_name_from_url("local:bionic/heat-12"), "heat"
        )
        self.assertEqual(
            openstack_upgrade.extract_charm_name_from_url("cs:bionic/heat-12"), "heat"
        )
        self.assertEqual(openstack_upgrade.extract_charm_name_from_url("cs:heat"), "heat")

    def test_determine_next_openstack_release(self):
        releases = ["ussuri", "victoria", "wallaby", "xena"]
        expected_next_release = ["victoria", "wallaby", "xena", "yoga"]

        results = []
        for release in releases:
            result = openstack_upgrade.determine_next_openstack_release(release)[1]
            results.append(result)
        self.assertEqual(results, expected_next_release)
