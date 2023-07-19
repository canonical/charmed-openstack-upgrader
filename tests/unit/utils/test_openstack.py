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

from cou.utils.openstack import openstack_lookup, generate_openstack_lookup
from packaging.version import Version


@pytest.mark.parametrize(
    "charm, workload_versions, results",
    [
        (
            "keystone",
            ["17.1.0", "18.3.1", "19.4.5", "20.6.7", "21.8.9"],
            [["ussuri"], ["victoria"], ["wallaby"], ["xena"], ["yoga"]],
        ),
        (
            "ceph-mon",
            ["15.2.0", "16.2.0", "17.2.0"],
            [["ussuri", "victoria"], ["wallaby", "xena"], ["yoga"]],
        ),  # version 15 (octopus) can be ussuri or victoria
        # version 16 (pacific) can be wallaby or xena
        (
            "gnocchi",
            ["4.3.4", "4.4.0", "4.4.1"],
            [["ussuri"], ["victoria", "wallaby"], ["xena", "yoga"]],
        ),
        (
            "openstack-dashboard",
            ["18.3.5", "18.6.3", "19.3.0", "20.1.4", "20.2.0"],
            [["ussuri"], ["victoria"], ["wallaby"], ["xena"], ["yoga"]],
        ),
        ("my_charm", ["13.1.2"], [[]]),  # unknown charm
        ("keystone", ["63.5.7"], [[]]),  # out-of-bounds of a known charm
    ],
)
def test_get_compatible_openstack_codenames(charm, workload_versions, results):
    for version, result in zip(workload_versions, results):
        actual = openstack_lookup.get_compatible_openstack_codenames(charm, version)
        assert result == actual

@pytest.mark.parametrize("service", ["aodh", "barbican"])
def test_generate_openstack_lookup(service):
    openstack_lookup = generate_openstack_lookup()
    os_releases = ["ussuri", "victoria", "wallaby", "xena", "yoga"]
    versions = ["10", "11", "12", "13", "14"]
    for os_release, version in zip(os_releases, versions):
        assert openstack_lookup[service][os_release].lower == Version(version)
        assert openstack_lookup[service][os_release].upper == Version(str(int(version) + 1))
