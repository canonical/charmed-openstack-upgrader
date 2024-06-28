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

"""Lookup utils to determine compatible OpenStack codenames for a given component."""
from __future__ import annotations

import csv
import encodings
import logging
from collections import OrderedDict, defaultdict, namedtuple
from dataclasses import dataclass
from functools import total_ordering
from pathlib import Path
from typing import Any, List, Optional, Tuple

from packaging.version import Version

logger = logging.getLogger(__name__)

TrackKeys = namedtuple("TrackKeys", ["charm", "series", "o7k_release"])
OSReleaseKeys = namedtuple("OSReleaseKeys", ["charm", "series", "track"])

SERVICE_COLUMN_INDEX = 0
VERSION_START_COLUMN_INDEX = 1
CHARM_FAMILIES = {
    "ceph": ["ceph-mon", "ceph-fs", "ceph-radosgw", "ceph-osd", "ceph-dashboard"],
    "swift": ["swift-proxy", "swift-storage"],
    "nova": ["nova-cloud-controller", "nova-compute"],
    "ovn": ["ovn-dedicated-chassis", "ovn-central", "ovn-chassis"],
    "neutron": ["neutron-api", "neutron-gateway"],
    "manila": ["manila-ganesha"],
    "horizon": ["openstack-dashboard"],
    "mysql": ["mysql-innodb-cluster", "mysql-router"],
}

DATA_PLANE_CHARMS = ["nova-compute", "ceph-osd", "swift-proxy", "swift-storage"]

# https://docs.openstack.org/charm-guide/latest/admin/upgrades/openstack.html#list-the-upgrade-order
UPGRADE_ORDER = [
    "rabbitmq-server",
    "ceph-mon",
    "keystone",
    "aodh",
    "barbican",
    "ceilometer",
    "ceph-fs",
    "ceph-radosgw",
    "cinder",
    "designate",
    "designate-bind",
    "glance",
    "gnocchi",
    "heat",
    "manila",
    "manila-ganesha",
    "neutron-api",
    "neutron-gateway",
    "ovn-dedicated-chassis",
    "ovn-central",
    "placement",
    "nova-cloud-controller",
    "nova-compute",
    "openstack-dashboard",
    "ceph-osd",
    "swift-proxy",
    "swift-storage",
    "octavia",
]

SUBORDINATES = [
    "barbican-vault",
    "ceilometer-agent",
    "cinder-backup-swift-proxy",
    "cinder-ceph",
    "cinder-lvm",
    "cinder-netapp",
    "cinder-purestorage",
    "keystone-kerberos",
    "keystone-ldap",
    "keystone-saml-mellon",
    "magnum-dashboard",
    "manila-dashboard",
    "manila-generic",
    "masakari-monitors",
    "neutron-api-plugin-arista",
    "neutron-api-plugin-ironic",
    "neutron-api-plugin-ovn",
    "neutron-openvswitch",
    "octavia-dashboard",
    "octavia-diskimage-retrofit",
]

AUXILIARY_SUBORDINATES = ["hacluster", "mysql-router", "ceph-dashboard"]

CHANNEL_BASED_CHARMS = ["designate-bind", "gnocchi", "glance-simplestreams-sync"]

# https://governance.openstack.org/tc/reference/release-naming.html
OPENSTACK_CODENAMES = OrderedDict(
    [
        ("diablo", "2011.2"),
        ("essex", "2012.1"),
        ("folsom", "2012.2"),
        ("grizzly", "2013.1"),
        ("havana", "2013.2"),
        ("icehouse", "2014.1"),
        ("juno", "2014.2"),
        ("kilo", "2015.1"),
        ("liberty", "2015.2"),
        ("mitaka", "2016.1"),
        ("newton", "2016.2"),
        ("ocata", "2017.1"),
        ("pike", "2017.2"),
        ("queens", "2018.1"),
        ("rocky", "2018.2"),
        ("stein", "2019.1"),
        ("train", "2019.2"),
        ("ussuri", "2020.1"),
        ("victoria", "2020.2"),
        ("wallaby", "2021.1"),
        ("xena", "2021.2"),
        ("yoga", "2022.1"),
        ("zed", "2022.2"),
        ("antelope", "2023.1"),
        ("bobcat", "2023.2"),
        ("caracal", "2024.1"),
    ]
)

# https://ubuntu.com/about/release-cycle#ubuntu
DISTRO_TO_OPENSTACK_MAPPING = {
    "bionic": "queens",
    "cosmic": "rocky",
    "disco": "stein",
    "eoan": "train",
    "focal": "ussuri",
    "groovy": "victoria",
    "hirsute": "wallaby",
    "impish": "xena",
    "jammy": "yoga",
    "kinetic": "zed",
    "lunar": "antelope",
    "mantic": "bobcat",
    "noble": "caracal",
}

# https://ubuntu.com/openstack/docs/supported-versions
# https://governance.openstack.org/tc/reference/release-naming.html
# https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html
LTS_TO_OS_RELEASE = {
    "focal": ["ussuri", "victoria", "wallaby", "xena", "yoga"],
    "jammy": ["yoga", "zed", "antelope", "bobcat", "caracal"],
}

# https://docs.ceph.com/en/latest/releases/
CEPH_RELEASES = [
    "octopus",
    "pacific",
    "quincy",
    "reef",
]


@total_ordering
class OpenStackRelease:
    """Provides a class that will compare OpenStack releases by the codename.

    Used to provide > and < comparisons on strings that may not necessarily be
    alphanumerically ordered.  e.g. OpenStack releases AFTER the z-wrap.
    """

    openstack_codenames = list(OPENSTACK_CODENAMES.keys())
    openstack_release_date = list(OPENSTACK_CODENAMES.values())

    def __init__(self, codename: str):
        """Initialize the OpenStackRelease object.

        :param codename: OpenStack release codename.
        :type codename: str
        :raises ValueError: Raises ValueError if OpenStack codename is unknown.
        """
        self.codename = codename

    def __hash__(self) -> int:
        """Hash magic method for OpenStackRelease.

        :return: Unique hash identifier for OpenStackRelease object.
        :rtype: int
        """
        return hash(f"{self.codename}{self.date}")

    def __eq__(self, other: object) -> bool:
        """Do equals."""
        if not isinstance(other, (str, OpenStackRelease)):
            return NotImplemented
        if isinstance(other, str):
            return self.index == OpenStackRelease(other).index
        return self.index == other.index

    def __lt__(self, other: object) -> bool:
        """Do less than."""
        if not isinstance(other, (str, OpenStackRelease)):
            return NotImplemented
        if isinstance(other, str):
            return self.index < OpenStackRelease(other).index
        return self.index < other.index

    def __repr__(self) -> str:
        """Return the representation of CompareOpenStack."""
        return f"{self.__class__.__name__}<{self.codename}>"

    @property
    def codename(self) -> str:
        """Return the OpenStack release codename.

        :return: OpenStack release codename.
        :rtype: str
        """
        return self._codename

    @codename.setter
    def codename(self, release_identifier: str) -> None:
        """Setter of OpenStack release codename.

        This setter take the OpenStack release identifier string (release
        codename or release date), and convert it into the OpenStack release
        codename.

        :param release_identifier: OpenStack release identifier.
        :type release_identifier: str
        :raises ValueError: Raise ValueError if release_identifier is unknown.
        """
        if release_identifier in self.openstack_codenames:
            self.index = self.openstack_codenames.index(release_identifier)
        elif release_identifier in self.openstack_release_date:
            self.index = self.openstack_release_date.index(release_identifier)
        else:
            raise ValueError(
                f"OpenStack '{release_identifier}' is not in '"
                f"{self.openstack_codenames}' or '{self.openstack_release_date}'"
            )

        self._codename = self.openstack_codenames[self.index]

    @property
    def track(self) -> str:
        """Return charmhub track for this openstack release.

        This property return the charmhub track for this OpenStack release. The
        charmhub tracks before OpenStack Antelope are usually tagged by their
        release codenames such as `ussuri`, `zed`, or `yoga`. For releases at
        or later than Antelope, the charmhub tracks are tagged with the release
        dates[1]. For example, see the charmhub track of nova-compute [2].

        [1] https://governance.openstack.org/tc/reference/release-naming.html
        [2] https://charmhub.io/nova-compute

        :return: Charmhub track
        :rtype: str
        """
        index_zed = self.openstack_codenames.index("zed")
        if self.index <= index_zed:
            return self.openstack_codenames[self.index]
        return self.openstack_release_date[self.index]

    @property
    def next_release(self) -> Optional[OpenStackRelease]:
        """Return the next OpenStack release codename.

        :return: OpenStack release codename.
        :rtype: Optional[OpenStackRelease]
        """
        try:
            return OpenStackRelease(self.openstack_codenames[self.index + 1])
        except IndexError:
            logger.warning("Cannot find an OpenStack release after %s", self.codename)
            return None

    @property
    def previous_release(self) -> Optional[OpenStackRelease]:
        """Return the previous OpenStack release codename.

        :return: OpenStack release codename.
        :rtype: Optional[OpenStackRelease]
        """
        if self.index == 0:
            logger.warning("Cannot find an OpenStack release before %s", self.codename)
            return None

        return OpenStackRelease(self.openstack_codenames[self.index - 1])

    @property
    def date(self) -> str:
        """Release date of the OpenStack release.

        :return: Release date.
        :rtype: str
        """
        return self.openstack_release_date[self.index]

    def __str__(self) -> str:
        """Give back the item at the index.

        This is so it can be used in comparisons like:

        s_mitaka = OpenStackRelease('mitaka')
        s_newton = OpenStackRelease('newton')

        assert s_newton > s_mitaka

        :returns: <string>
        """
        return self.codename


@dataclass(frozen=True)
class VersionRange:
    """Structure for holding version."""

    lower: str
    upper: str

    def __post_init__(self) -> None:
        """Initialize the VersionRange dataclass and check its values."""
        if Version(self.lower) >= Version(self.upper):
            raise ValueError("The upper bound version is not higher than the lower bound version.")

    def __contains__(self, version: str) -> bool:
        """Magic method to check if a version is within the range.

        :param version: version of a service.
        :type version: str
        :return: True if version is in the range.
        :rtype: bool
        """
        lower_v = Version(self.lower)
        upper_v = Version(self.upper)
        service_version = Version(version)
        return lower_v <= service_version < upper_v


# pylint: disable=too-few-public-methods
class OpenStackCodenameLookup:
    """Class to determine compatible OpenStack codenames for a given component."""

    _OPENSTACK_LOOKUP: OrderedDict = OrderedDict()
    _DEFAULT_CSV_FILE = Path(__file__).parent / "openstack_lookup.csv"

    @classmethod
    def _generate_lookup(cls, resource: Path) -> OrderedDict:
        """Generate an OpenStack lookup dictionary based on the version of the components.

        The dictionary is generated from a static csv file that should be updated regularly
        to include new OpenStack releases and updates to the lower and upper versions of
        the services. The csv table is made from the release page [0], charm delivery [1],
        cmadison and rmadison, and ceph release page [2]. The lower version is the lowest
        version of a certain release (N) while the upper is the first incompatible version.
        This way, new patches won't affect the comparison.

        Charm designate-bind workload_version tracks the version of the deb package bind9.
        For charm gnocchi it was used cmadison.

        [0] https://releases.openstack.org/
        [1] https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html
        [2] https://docs.ceph.com/en/latest/releases/

        :param resource: Path to the csv file
        :type resource: Path
        :return: Ordered dictionary containing the version and the compatible OpenStack release.
        :rtype: OrderedDict
        """
        with open(resource, encoding=encodings.utf_8.getregentry().name) as csv_file:
            openstack_lookup = OrderedDict()
            csv_reader = csv.reader(csv_file, delimiter=",")
            header = next(csv_reader)
            for row in csv_reader:
                service, service_dict = cls._parse_row(header, row)
                openstack_lookup[service] = service_dict
        # add openstack charms
        for family, charms in CHARM_FAMILIES.items():
            for charm in charms:
                openstack_lookup[charm] = openstack_lookup[family]
        return openstack_lookup

    @classmethod
    def _parse_row(cls, header: List[str], row: List[str]) -> Tuple[str, defaultdict[str, Any]]:
        """Parse single row.

        :param header: header list
        :type header: list[str]
        :param row: row list
        :type row: list[str]
        :return: service and service dictionary
        :rtype: tuple
        """
        service_dict: defaultdict[str, Any] = defaultdict(OrderedDict)
        service = row[SERVICE_COLUMN_INDEX]
        for column_index in range(VERSION_START_COLUMN_INDEX, len(row), 2):
            o7k_version, _ = header[column_index].split("-")
            lower = row[column_index]
            upper = row[column_index + 1]
            service_dict[o7k_version] = VersionRange(lower, upper)
        return service, service_dict

    @classmethod
    def find_compatible_versions(cls, charm: str, version: str) -> list[OpenStackRelease]:
        """Get the compatible OpenStackRelease(s) based on the charm and version.

        :param charm: Name of the charm. E.g: "keystone"
        :type charm: str
        :param version: Version of the charm. E.g: "17.0.2"
        :type version: str
        :return: Return a sorted list of compatible OpenStackRelease(s).
        :rtype: list[str]
        """
        compatible_o7k_releases: list[OpenStackRelease] = []
        for openstack_release, version_range in cls.lookup(charm).items():
            if version in version_range:
                compatible_o7k_releases.append(OpenStackRelease(openstack_release))
        if not compatible_o7k_releases:
            logger.warning(
                "Not possible to find the charm %s in the lookup",
                charm,
            )
        return compatible_o7k_releases

    @classmethod
    def lookup(cls, charm: str) -> dict:
        """Check if a core OpenStack charm is supported or not in the OpenStackCodenameLookup.

        This function also generate the lookup if _OPENSTACK_LOOKUP is empty.
        :param charm: name of the charm
        :type charm: str
        :return: If supported return the charm, else empty dict
        :rtype: dict
        """
        if not cls._OPENSTACK_LOOKUP:
            cls._OPENSTACK_LOOKUP = cls._generate_lookup(cls._DEFAULT_CSV_FILE)
        return cls._OPENSTACK_LOOKUP.get(charm, {})


def is_charm_supported(charm: str) -> bool:
    """Check if a charm upgrade is supported.

    Currently data plane apps are not supported.
    :param charm: Name of the charm.
    :type charm: str
    :return: True if supported, else False
    :rtype: bool
    """
    return (
        bool(OpenStackCodenameLookup.lookup(charm))
        or charm in SUBORDINATES + AUXILIARY_SUBORDINATES + CHANNEL_BASED_CHARMS
    )


def _generate_track_mapping() -> tuple[
    defaultdict[tuple[str, str, str], list[str]],
    defaultdict[tuple[str, str, str], list[OpenStackRelease]],
]:
    """Generate the track mappings for the auxiliary charms.

    Those mappings should be updated periodically by adding new lines in the file
    openstack_to_track_mapping.csv

    See the following url for more details:
    https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html

    :return: Dictionaries containing the tracks by charm name, series and OpenStack release.
    :rtype: tuple[
        defaultdict[tuple[str, str, str], list[str]],
        defaultdict[tuple[str, str, str], list[OpenStackRelease]]
    ]
    """
    track_mapping: defaultdict[tuple[str, str, str], list[str]] = defaultdict(list)
    o7k_release_mapping: defaultdict[tuple[str, str, str], list[OpenStackRelease]] = defaultdict(
        list
    )
    with open(
        Path(__file__).parent / "openstack_to_track_mapping.csv",
        encoding=encodings.utf_8.getregentry().name,
    ) as csv_file:
        csv_reader = csv.DictReader(csv_file, delimiter=",")
        for row in csv_reader:
            track_key = TrackKeys(
                charm=row["charm"], series=row["series"], o7k_release=row["o7k_release"]
            )
            o7k_release_key = OSReleaseKeys(
                charm=row["charm"], series=row["series"], track=row["track"]
            )
            track_mapping[track_key].append(row["track"])
            o7k_release_mapping[o7k_release_key].append(OpenStackRelease(row["o7k_release"]))
    return track_mapping, o7k_release_mapping


OPENSTACK_TO_TRACK_MAPPING, TRACK_TO_OPENSTACK_MAPPING = _generate_track_mapping()
