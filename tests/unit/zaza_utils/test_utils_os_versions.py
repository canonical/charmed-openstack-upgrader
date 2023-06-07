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

import tests.unit.utils as ut_utils
from cou.zaza_utils import os_versions


class TestOpenStackUtils(ut_utils.BaseTestCase):
    def setUp(self):
        super(TestOpenStackUtils, self).setUp()

    def test_compare_openstack(self):
        releases = ["zed", "xena", "antelope", "ussuri", "icehouse"]
        expected_order = ["icehouse", "ussuri", "xena", "zed", "antelope"]
        result = sorted(releases, key=lambda release: os_versions.CompareOpenStack(release))
        self.assertEqual(result, expected_order)

    def test_determine_next_openstack_release(self):
        releases = ["ussuri", "victoria", "wallaby", "xena"]
        expected_next_release = ["victoria", "wallaby", "xena", "yoga"]

        results = []
        for release in releases:
            result = os_versions.determine_next_openstack_release(release)[1]
            results.append(result)
        self.assertEqual(results, expected_next_release)
