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

import csv
import encodings
import logging
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple

from packaging.version import Version

logger = logging.getLogger(__name__)

SERVICE_COLUMN_INDEX = 0
VERSION_START_COLUMN_INDEX = 1
CHARM_TYPES = {
    "ceph": ["ceph-mon", "ceph-fs", "ceph-radosgw", "ceph-osd"],
    "swift": ["swift-proxy", "swift-storage"],
    "nova": ["nova-cloud-controller", "nova-compute"],
    "ovn": ["ovn-dedicated-chassis", "ovn-central"],
    "neutron": ["neutron-api", "neutron-gateway"],
    "manila": ["manila-ganesha"],
    "horizon": ["openstack-dashboard"],
    "mysql": ["mysql-innodb-cluster", "mysql-router"],
}

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

    def __eq__(self, other: Any) -> bool:
        """Do equals."""
        if not isinstance(other, (str, OpenStackRelease)):
            return NotImplemented
        return self.index == self.openstack_codenames.index(str(other))

    def __ne__(self, other: Any) -> bool:
        """Do not equals."""
        return not self.__eq__(other)

    def __lt__(self, other: Any) -> bool:
        """Do less than."""
        if not isinstance(other, (str, OpenStackRelease)):
            return NotImplemented
        return self.index < self.openstack_codenames.index(str(other))

    def __ge__(self, other: Any) -> bool:
        """Do greater than or equal."""
        return not self.__lt__(other)

    def __gt__(self, other: Any) -> bool:
        """Do greater than."""
        if not isinstance(other, (str, OpenStackRelease)):
            return NotImplemented
        return self.index > self.openstack_codenames.index(str(other))

    def __le__(self, other: Any) -> bool:
        """Do less than or equals."""
        return not self.__gt__(other)

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
    def codename(self, value: str) -> None:
        """Setter of OpenStack release codename.

        :param value: OpenStack release codename.
        :type value: str
        :raises ValueError: Raise ValueError if codename is unknown.
        """
        if value not in self.openstack_codenames:
            raise ValueError(f"OpenStack '{value}' is not in '{self.openstack_codenames}'")
        self._codename = value
        self.index = self.openstack_codenames.index(value)

    @property
    def next_release(self) -> Optional[str]:
        """Return the next OpenStack release codename.

        :return: OpenStack release codename.
        :rtype: str
        """
        try:
            return self.openstack_codenames[self.index + 1]
        except IndexError:
            logger.warning("There is no OpenStack release after %s", self.codename)
            return None

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
        the services. The csv table is made from the release page [0] charm delivery [1],
        cmadison and rmadison. The lower version is the lowest version of a certain release (N)
        while the upper is the first incompatible version. This way, new patches
        won't affect the comparison.

        Charm designate-bind workload_version tracks the version of the deb package bind9.
        For charm gnocchi it was used cmadison.

        [0] https://releases.openstack.org/
        [1] https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html

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
        for charm_type, charms in CHARM_TYPES.items():
            for charm in charms:
                openstack_lookup[charm] = openstack_lookup[charm_type]
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
            os_version, _ = header[column_index].split("-")
            lower = row[column_index]
            upper = row[column_index + 1]
            service_dict[os_version] = VersionRange(lower, upper)
        return service, service_dict

    @classmethod
    def lookup(cls, component: str, version: str) -> List[OpenStackRelease]:
        """Get the compatible OpenStack codenames based on the component and version.

        :param component: Name of the component. E.g: "keystone"
        :type component: str
        :param version: Version of the component. E.g: "17.0.2"
        :type version: str
        :return: Return a sorted list of compatible OpenStack codenames.
        :rtype: List[str]
        """
        if not cls._OPENSTACK_LOOKUP:
            cls._OPENSTACK_LOOKUP = cls._generate_lookup(cls._DEFAULT_CSV_FILE)
        compatible_os_releases: List[OpenStackRelease] = []
        if not cls._OPENSTACK_LOOKUP.get(component):
            logger.warning(
                "Not possible to find the component %s in the lookup",
                component,
            )
            return compatible_os_releases
        for openstack_release, version_range in cls._OPENSTACK_LOOKUP[component].items():
            if version in version_range:
                compatible_os_releases.append(OpenStackRelease(openstack_release))
        return compatible_os_releases
