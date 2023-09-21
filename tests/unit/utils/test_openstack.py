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

from cou.utils.openstack import (
    OPENSTACK_TO_TRACK_MAPPING,
    TRACK_TO_OPENSTACK_MAPPING,
    OpenStackCodenameLookup,
    OpenStackRelease,
    VersionRange,
)


@pytest.mark.parametrize("lower, upper", [("2.0", "2.0"), ("2.0", "1.0")])
def test_version_range_raises_ValueError(lower, upper):
    exp_error_msg = "The upper bound version is not higher than the lower bound version."
    with pytest.raises(ValueError, match=exp_error_msg):
        VersionRange(lower, upper)


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
        actual = OpenStackCodenameLookup.find_compatible_versions(charm, version)
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
    "release_1, release_2, exp_result",
    [
        ("victoria", "victoria", True),
        ("victoria", "wallaby", False),
        ("wallaby", "victoria", False),
    ],
)
def test_compare_openstack_release_eq(release_1, release_2, exp_result):
    result_1 = OpenStackRelease(release_1) == release_2
    result_2 = OpenStackRelease(release_1) == OpenStackRelease(release_2)
    assert result_1 == exp_result
    assert result_2 == exp_result


def test_compare_openstack_release_eq_not_implemented():
    assert OpenStackRelease("ussuri").__eq__(1) == NotImplemented


@pytest.mark.parametrize(
    "release_1, release_2, exp_result",
    [
        ("victoria", "victoria", False),
        ("victoria", "wallaby", True),
        ("wallaby", "victoria", True),
    ],
)
def test_compare_openstack_release_neq(release_1, release_2, exp_result):
    result_1 = OpenStackRelease(release_1) != release_2
    result_2 = OpenStackRelease(release_1) != OpenStackRelease(release_2)
    assert result_1 == exp_result
    assert result_2 == exp_result


@pytest.mark.parametrize(
    "release_1, release_2, exp_result",
    [
        ("victoria", "victoria", False),
        ("victoria", "wallaby", True),
        ("wallaby", "victoria", False),
    ],
)
def test_compare_openstack_release_lt(release_1, release_2, exp_result):
    result_1 = OpenStackRelease(release_1) < release_2
    result_2 = OpenStackRelease(release_1) < OpenStackRelease(release_2)
    assert result_1 == exp_result
    assert result_2 == exp_result


def test_compare_openstack_release_lt_not_implemented():
    assert OpenStackRelease("ussuri").__lt__(1) == NotImplemented


@pytest.mark.parametrize(
    "release_1, release_2, exp_result",
    [
        ("victoria", "victoria", True),
        ("victoria", "wallaby", False),
        ("wallaby", "victoria", True),
    ],
)
def test_compare_openstack_release_ge(release_1, release_2, exp_result):
    result_1 = OpenStackRelease(release_1) >= release_2
    result_2 = OpenStackRelease(release_1) >= OpenStackRelease(release_2)
    assert result_1 == exp_result
    assert result_2 == exp_result


@pytest.mark.parametrize(
    "release_1, release_2, exp_result",
    [
        ("victoria", "victoria", False),
        ("victoria", "wallaby", False),
        ("wallaby", "victoria", True),
    ],
)
def test_compare_openstack_release_gt(release_1, release_2, exp_result):
    result_1 = OpenStackRelease(release_1) > release_2
    result_2 = OpenStackRelease(release_1) > OpenStackRelease(release_2)
    assert result_1 == exp_result
    assert result_2 == exp_result


def test_compare_openstack_gt_release_not_implemented():
    assert OpenStackRelease("ussuri").__gt__(1) == NotImplemented


@pytest.mark.parametrize(
    "release_1, release_2, exp_result",
    [
        ("victoria", "victoria", True),
        ("victoria", "wallaby", True),
        ("wallaby", "victoria", False),
    ],
)
def test_compare_openstack_release_le(release_1, release_2, exp_result):
    result_1 = OpenStackRelease(release_1) <= release_2
    result_2 = OpenStackRelease(release_1) <= OpenStackRelease(release_2)
    assert result_1 == exp_result
    assert result_2 == exp_result


def test_compare_openstack_release_order():
    ussuri = OpenStackRelease("ussuri")
    wallaby = OpenStackRelease("wallaby")
    antelope = OpenStackRelease("antelope")
    bobcat = OpenStackRelease("bobcat")
    caracal = OpenStackRelease("2024.1")
    os_releases = {
        caracal,
        wallaby,
        ussuri,
        bobcat,
        antelope,
    }
    assert min(os_releases) == ussuri
    assert max(os_releases) == caracal
    assert sorted(os_releases) == [ussuri, wallaby, antelope, bobcat, caracal]


def test_openstack_release_setter():
    openstack_release = OpenStackRelease("wallaby")
    assert openstack_release.next_release == "xena"
    # change OpenStack release
    openstack_release.codename = "xena"
    assert openstack_release.next_release == "yoga"


def test_openstack_release_setter_by_date():
    openstack_release = OpenStackRelease("2023.1")
    assert openstack_release.codename == "antelope"
    assert openstack_release.next_release == "bobcat"
    assert openstack_release.date == "2023.1"


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
        ("caracal", "2024.1", None),  # None when there is no next release
    ],
)
def test_determine_next_openstack_release(os_release, release_year, next_os_release):
    release = OpenStackRelease(os_release)
    assert release.next_release == next_os_release
    assert release.date == release_year


@pytest.mark.parametrize(
    "os_release, previous_os_release",
    [
        ("ussuri", "train"),
        ("victoria", "ussuri"),
        ("wallaby", "victoria"),
        ("xena", "wallaby"),
        ("diablo", None),  # None when there is no previous release
    ],
)
def test_determine_previous_openstack_release(os_release, previous_os_release):
    release = OpenStackRelease(os_release)
    assert release.previous_release == previous_os_release


@pytest.mark.parametrize(
    "series, charm, os_release, exp_result",
    [
        ("focal", "ceph-mon", "ussuri", ["octopus"]),
        ("focal", "ceph-mon", "victoria", ["octopus"]),
        ("focal", "ceph-mon", "wallaby", ["pacific"]),
        ("focal", "ceph-mon", "xena", ["pacific"]),
        ("focal", "ceph-mon", "yoga", ["quincy"]),
        ("jammy", "ceph-mon", "yoga", ["quincy"]),
        ("jammy", "ceph-mon", "zed", ["quincy"]),
        ("focal", "ovn-central", "ussuri", ["22.03"]),
        ("focal", "ovn-central", "victoria", ["22.03"]),
        ("focal", "ovn-central", "wallaby", ["22.03"]),
        ("focal", "ovn-central", "xena", ["22.03"]),
        ("focal", "ovn-central", "yoga", ["22.03"]),
        ("jammy", "ovn-central", "yoga", ["22.03"]),
        ("jammy", "ovn-central", "zed", ["22.09"]),
        ("focal", "mysql-router", "ussuri", ["8.0"]),
        ("focal", "mysql-router", "victoria", ["8.0"]),
        ("focal", "mysql-router", "wallaby", ["8.0"]),
        ("focal", "mysql-router", "xena", ["8.0"]),
        ("focal", "mysql-router", "yoga", ["8.0"]),
        ("jammy", "mysql-router", "yoga", ["8.0"]),
        ("jammy", "mysql-router", "zed", ["8.0"]),
        ("focal", "hacluster", "ussuri", ["2.0.3", "2.4"]),
        ("focal", "hacluster", "victoria", ["2.0.3", "2.4"]),
        ("focal", "hacluster", "wallaby", ["2.0.3", "2.4"]),
        ("focal", "hacluster", "xena", ["2.0.3", "2.4"]),
        ("focal", "hacluster", "yoga", ["2.0.3", "2.4"]),
        ("jammy", "hacluster", "yoga", ["2.4"]),
        ("jammy", "hacluster", "zed", ["2.4"]),
        ("focal", "rabbitmq-server", "ussuri", ["3.8", "3.9"]),
        ("focal", "rabbitmq-server", "victoria", ["3.8", "3.9"]),
        ("focal", "rabbitmq-server", "wallaby", ["3.8", "3.9"]),
        ("focal", "rabbitmq-server", "xena", ["3.8", "3.9"]),
        ("focal", "rabbitmq-server", "yoga", ["3.8", "3.9"]),
        ("jammy", "rabbitmq-server", "yoga", ["3.9"]),
        ("jammy", "rabbitmq-server", "zed", ["3.9"]),
        ("focal", "vault", "ussuri", ["1.7"]),
        ("focal", "vault", "victoria", ["1.7"]),
        ("focal", "vault", "wallaby", ["1.7"]),
        ("focal", "vault", "xena", ["1.7"]),
        ("focal", "vault", "yoga", ["1.7"]),
        ("jammy", "vault", "yoga", ["1.8"]),
        ("jammy", "vault", "zed", ["1.8"]),
        ("bionic", "vault", "zed", None),  # release not mapped
        ("jammy", "my-service", "zed", None),  # family not mapped
    ],
)
def test_openstack_to_track(charm, series, os_release, exp_result):
    assert OPENSTACK_TO_TRACK_MAPPING.get((charm, series, os_release)) == exp_result


@pytest.mark.parametrize(
    "series, charm, track, exp_result",
    [
        (
            "focal",
            "ceph-mon",
            "octopus",
            [OpenStackRelease("ussuri"), OpenStackRelease("victoria")],
        ),
        (
            "focal",
            "ceph-mon",
            "pacific",
            [OpenStackRelease("wallaby"), OpenStackRelease("xena")],
        ),
        (
            "focal",
            "ceph-mon",
            "quincy",
            [OpenStackRelease("yoga")],
        ),
        (
            "jammy",
            "ceph-mon",
            "quincy",
            [OpenStackRelease("yoga"), OpenStackRelease("zed"), OpenStackRelease("2023.1")],
        ),
        (
            "focal",
            "ovn-central",
            "22.03",
            [
                OpenStackRelease("ussuri"),
                OpenStackRelease("victoria"),
                OpenStackRelease("wallaby"),
                OpenStackRelease("xena"),
                OpenStackRelease("yoga"),
            ],
        ),
        (
            "jammy",
            "ovn-central",
            "22.03",
            [OpenStackRelease("yoga")],
        ),
        (
            "jammy",
            "ovn-central",
            "22.09",
            [OpenStackRelease("zed")],
        ),
        (
            "jammy",
            "ovn-central",
            "23.03",
            [OpenStackRelease("2023.1")],
        ),
        (
            "focal",
            "mysql-router",
            "8.0",
            [
                OpenStackRelease("ussuri"),
                OpenStackRelease("victoria"),
                OpenStackRelease("wallaby"),
                OpenStackRelease("xena"),
                OpenStackRelease("yoga"),
            ],
        ),
        (
            "jammy",
            "mysql-router",
            "8.0",
            [OpenStackRelease("yoga"), OpenStackRelease("zed"), OpenStackRelease("2023.1")],
        ),
        (
            "focal",
            "hacluster",
            "2.0.3",
            [
                OpenStackRelease("ussuri"),
                OpenStackRelease("victoria"),
                OpenStackRelease("wallaby"),
                OpenStackRelease("xena"),
                OpenStackRelease("yoga"),
            ],
        ),
        (
            "jammy",
            "hacluster",
            "2.4",
            [OpenStackRelease("yoga"), OpenStackRelease("zed"), OpenStackRelease("2023.1")],
        ),
        (
            "focal",
            "rabbitmq-server",
            "3.8",
            [
                OpenStackRelease("ussuri"),
                OpenStackRelease("victoria"),
                OpenStackRelease("wallaby"),
                OpenStackRelease("xena"),
                OpenStackRelease("yoga"),
            ],
        ),
        (
            "jammy",
            "rabbitmq-server",
            "3.9",
            [OpenStackRelease("yoga"), OpenStackRelease("zed"), OpenStackRelease("2023.1")],
        ),
        (
            "focal",
            "vault",
            "1.7",
            [
                OpenStackRelease("ussuri"),
                OpenStackRelease("victoria"),
                OpenStackRelease("wallaby"),
                OpenStackRelease("xena"),
                OpenStackRelease("yoga"),
            ],
        ),
        (
            "jammy",
            "vault",
            "1.8",
            [OpenStackRelease("yoga"), OpenStackRelease("zed"), OpenStackRelease("2023.1")],
        ),
    ],
)
def test_track_to_openstack(charm, series, track, exp_result):
    assert TRACK_TO_OPENSTACK_MAPPING.get((charm, series, track)) == exp_result
