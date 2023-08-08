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

from cou.utils.openstack import OpenStackCodenameLookup, OpenStackRelease, VersionRange


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
        (
            "rabbitmq-server",  # yoga can be 3.8 or 3.9
            ["3.8", "3.9", "3.10"],
            [["ussuri", "victoria", "wallaby", "xena", "yoga"], ["yoga"], []],
        ),
        (
            "hacluster",  # yoga can be 2.0.3 to 2.4
            ["2.0.3", "2.4", "2.5"],
            [["ussuri", "victoria", "wallaby", "xena", "yoga"], ["yoga"], []],
        ),
        (
            "vault",  # yoga can be 1.7 to 1.8
            ["1.7", "1.8", "1.9"],
            [["ussuri", "victoria", "wallaby", "xena", "yoga"], ["yoga"], []],
        ),
        ("my_charm", ["13.1.2"], [[]]),  # unknown charm
        ("keystone", ["63.5.7"], [[]]),  # out-of-bounds of a known charm
    ],
)
def test_get_compatible_openstack_codenames(charm, workload_versions, results):
    for version, result in zip(workload_versions, results):
        actual = OpenStackCodenameLookup.lookup(charm, version)
        assert result == actual


@pytest.mark.parametrize("service", ["aodh", "barbican"])
def test_generate_lookup(service):
    openstack_lookup = OpenStackCodenameLookup._generate_lookup(
        OpenStackCodenameLookup._DEFAULT_CSV_FILE
    )
    os_releases = ["ussuri", "victoria", "wallaby", "xena", "yoga"]
    versions = ["10", "11", "12", "13", "14"]
    for os_release, version in zip(os_releases, versions):
        assert openstack_lookup[service][os_release] == VersionRange(
            version + ".0.0", str(int(version) + 1) + ".0.0"
        )


@pytest.mark.parametrize(
    "release_1, release_2, comparison, expected_result",
    [
        ("victoria", "wallaby", "eq", False),
        ("victoria", "victoria", "eq", True),
        ("victoria", "wallaby", "neq", True),
        ("wallaby", "wallaby", "neq", False),
        ("victoria", "wallaby", "lt", True),
        ("wallaby", "victoria", "lt", False),
        ("victoria", "wallaby", "le", True),
        ("wallaby", "victoria", "le", False),
        ("wallaby", "wallaby", "le", True),
        ("victoria", "wallaby", "ge", False),
        ("wallaby", "victoria", "ge", True),
        ("victoria", "wallaby", "gt", False),
        ("wallaby", "victoria", "gt", True),
    ],
)
def test_compare_openstack(release_1, release_2, comparison, expected_result):
    if comparison == "eq":
        result = OpenStackRelease(release_1) == release_2
        result_alternative = OpenStackRelease(release_1) == OpenStackRelease(release_2)
    elif comparison == "neq":
        result = OpenStackRelease(release_1) != release_2
        result_alternative = OpenStackRelease(release_1) != OpenStackRelease(release_2)
    elif comparison == "lt":
        result = OpenStackRelease(release_1) < release_2
        result_alternative = OpenStackRelease(release_1) < OpenStackRelease(release_2)
    elif comparison == "le":
        result = OpenStackRelease(release_1) <= release_2
        result_alternative = OpenStackRelease(release_1) <= OpenStackRelease(release_2)
    elif comparison == "ge":
        result = OpenStackRelease(release_1) >= release_2
        result_alternative = OpenStackRelease(release_1) >= OpenStackRelease(release_2)
    elif comparison == "gt":
        result = OpenStackRelease(release_1) > release_2
        result_alternative = OpenStackRelease(release_1) > OpenStackRelease(release_2)
    assert result == expected_result
    assert result_alternative == expected_result


@pytest.mark.parametrize("os_release", ["victoria", "wallaby"])
def test_compare_openstack_repr_str(os_release):
    os_compare = OpenStackRelease(os_release)
    expected_str = os_release
    expected_repr = f"OpenStackRelease<{os_release}>"
    assert repr(os_compare) == expected_repr
    assert str(os_compare) == expected_str


def test_compare_openstack_raises_error():
    with pytest.raises(ValueError) as err:
        OpenStackRelease("foo-release")
        assert "Item foo-release is not in list" in str(err.value)


@pytest.mark.parametrize(
    "os_release, release_year, next_os_release",
    [
        ("ussuri", "2020.1", "victoria"),
        ("victoria", "2020.2", "wallaby"),
        ("wallaby", "2021.1", "xena"),
        ("xena", "2021.2", "yoga"),
        ("bobcat", "2023.2", "bobcat"),  # repeat when there is no next release
    ],
)
def test_determine_next_openstack_release(os_release, release_year, next_os_release):
    release = OpenStackRelease(os_release)
    assert release.next_release == next_os_release
    assert release.release_year == release_year
