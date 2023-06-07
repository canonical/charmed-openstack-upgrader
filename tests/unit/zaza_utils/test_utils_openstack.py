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

import mock

import tests.unit.utils as ut_utils
from cou.zaza_utils import generic as generic_utils
from cou.zaza_utils import openstack as openstack_utils


class TestOpenStackUtils(ut_utils.BaseTestCase):
    def setUp(self):
        super(TestOpenStackUtils, self).setUp()
        # Patch all subprocess calls
        self.patch(
            "cou.zaza_utils.generic.subprocess", new_callable=mock.MagicMock(), name="subprocess"
        )

        # Juju Status Object and data
        self.juju_status = mock.MagicMock()
        self.patch_object(generic_utils, "model")
        self.model.get_status.return_value = self.juju_status

    def test_get_os_code_info(self):
        # test if matches expected openstack version based on the package version
        unit_pkg_version = {"keystone/0": "16.0.0", "keystone/1": "17.0.0", "keystone/2": "18.0.0"}
        expected = defaultdict(set)
        expected["train"].add("keystone/0")
        expected["ussuri"].add("keystone/1")
        expected["victoria"].add("keystone/2")
        result = openstack_utils.get_os_code_info("keystone", unit_pkg_version)
        self.assertEqual(result, expected)

        # assert that it raises KeyError if there is a unknown version
        unit_pkg_version = {"keystone/2": "19.0.0"}
        with self.assertRaises(KeyError):
            openstack_utils.get_os_code_info("keystone", unit_pkg_version)

        # test swift package
        unit_pkg_version = {
            "swift/0": "2.25.2-0ubuntu1.1~cloud0",
            "swift/1": "2.26.0-0ubuntu1.1~cloud0",
        }
        expected = defaultdict(set)
        expected["ussuri"].add("swift/0")
        expected["victoria"].add("swift/1")
        result = openstack_utils.get_os_code_info("swift", unit_pkg_version)
        self.assertEqual(result, expected)

        # test ovn packages
        unit_pkg_version = {
            "ovn/0": "20.03.2-0ubuntu0.20.04.4~cloud0",
            "ovn/1": "20.06.1-0ubuntu1.1~cloud0",
        }
        expected = defaultdict(set)
        expected["ussuri"].add("ovn/0")
        expected["victoria"].add("ovn/1")
        result = openstack_utils.get_os_code_info("ovn", unit_pkg_version)
        self.assertEqual(result, expected)

    def test_get_openstack_release(self):
        self.patch_object(openstack_utils.model, "get_units")
        self.patch_object(openstack_utils.juju, "remote_run")

        unit1 = mock.MagicMock()
        unit2 = mock.MagicMock()
        unit1.entity_id = "keystone/0"
        unit2.entity_id = "keystone/1"
        self.get_units.return_value = [unit1, unit2]

        # Test pre-Wallaby behavior where openstack-release pkg isn't installed
        cmd = "cat /etc/openstack-release | grep OPENSTACK_CODENAME"
        self.remote_run.side_effect = openstack_utils.model.CommandRunFailed(
            cmd, {"Code": "1", "Stdout": "", "Stderr": ""}
        )
        result = openstack_utils.get_openstack_release("application", "model")
        expected = defaultdict(set)
        self.assertEqual(result, expected)
        # reset mock
        self.remote_run.reset_mock(side_effect=True)

        # Test Wallaby+ behavior where openstack-release package is installed
        self.remote_run.return_value = "OPENSTACK_CODENAME=wallaby "

        expected["wallaby"] = {"keystone/0", "keystone/1"}
        result = openstack_utils.get_openstack_release("application", "model")
        self.assertEqual(result, expected)

    def test_get_current_os_versions(self):
        self.patch_object(openstack_utils, "get_openstack_release")
        self.patch_object(openstack_utils.generic, "get_pkg_version")

        # Pre-Wallaby scenario where openstack-release package isn't installed
        self.get_openstack_release.return_value = None
        self.get_pkg_version.return_value = {
            "keystone/0": "18.0.0",
            "keystone/1": "18.0.0",
            "keystone/2": "18.0.0",
        }
        expected = defaultdict(set)
        expected["victoria"] = {"keystone/0", "keystone/1", "keystone/2"}
        result = openstack_utils.get_current_os_versions(("keystone", "keystone"))
        self.assertEqual(expected, result)

        # Wallaby+ scenario where openstack-release package is installed
        expected = defaultdict(set)
        expected["wallaby"] = {"keystone/0", "keystone/1", "keystone/2"}
        self.get_openstack_release.return_value = expected
        result = openstack_utils.get_current_os_versions(("keystone", "keystone"))
        self.assertEqual(expected, result)
