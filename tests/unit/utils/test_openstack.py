# Copyright 2018 Canonical Ltd.
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

from cou.utils.openstack import get_latest_compatible_openstack_codename


@pytest.mark.parametrize(
    "charm, workload_versions, results",
    [
        (
            "keystone",
            ["17.1.0", "18.3.1", "19.4.5", "20.6.7", "21.8.9"],
            ["ussuri", "victoria", "wallaby", "xena", "yoga"],
        ),  # major
        (
            "ceph-mon",
            ["15.2.13", "16.2.12", "17.2.1"],
            ["victoria", "xena", "yoga"],
        ),  # version 15 (octopus) can be ussuri or victoria, we return the latest (victoria)
        # version 16 (pacific) can be wallaby or xena, we return the latest (xena)
        ("gnocchi", ["4.3.4", "4.4.0", "4.4.1"], ["ussuri", "wallaby", "yoga"]),  # micro
        (
            "openstack-dashboard",
            ["18.3.5", "18.6.3", "19.3.0", "20.1.4", "20.2.0"],
            ["ussuri", "victoria", "wallaby", "xena", "yoga"],
        ),  # minor
        ("my_charm", ["13.1.2"], [None]),  # non-existent
    ],
)
def test_get_os_code_info(charm, workload_versions, results):
    for index in range(len(workload_versions)):
        actual = get_latest_compatible_openstack_codename(charm, workload_versions[index])
        assert results[index] == actual
