# mypy: disable-error-code="no-untyped-def"
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

"""Lookup utils to determine compatible OpenStack codenames for a given component."""

import csv
import logging
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from typing import Any, List

from packaging.version import Version

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
}


@dataclass(frozen=True)
class VersionRange:
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
        return service_version >= lower_v and service_version < upper_v


class OpenStackCodenameLookup(object):
    _OPENSTACK_LOOKUP: OrderedDict = OrderedDict()
    _DEFAULT_CSV_FILE = "cou/utils/openstack_lookup.csv"

    @classmethod
    def initialize_lookup(cls) -> OrderedDict:
        """Generate an OpenStack lookup dictionary based on the version of the components.

        If not passed a path for a custom csv file, the function will use the default one.
        Be sure to have the same format as found at "cou/utils/openstack_lookup.csv" if you want to
        have your custom lookup dictionary.

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

        :return: Ordered dictionary containing the version and the compatible OpenStack release.
        :rtype: OrderedDict
        """
        cls._OPENSTACK_LOOKUP = cls._generate_lookup(cls._DEFAULT_CSV_FILE)
        return cls._OPENSTACK_LOOKUP

    @classmethod
    def _generate_lookup(cls, resource: str) -> OrderedDict:
        """Generate an OpenStack lookup dictionary based on the version of the components.

        :param resource: Path to the csv file
        :type resource: str
        :return: Ordered dictionary containing the version and the compatible OpenStack release.
        :rtype: OrderedDict
        """
        with open(resource) as csv_file:
            openstack_lookup = OrderedDict()
            csv_reader = csv.reader(csv_file, delimiter=",")
            header = next(csv_reader)
            for row in csv_reader:
                service_dict: defaultdict[str, Any] = defaultdict(OrderedDict)
                service = row[SERVICE_COLUMN_INDEX]
                for column_index in range(VERSION_START_COLUMN_INDEX, len(row), 2):
                    os_version, _ = header[column_index].split("-")
                    lower = row[column_index]
                    upper = row[column_index + 1]
                    service_dict[os_version] = VersionRange(lower, upper)
                openstack_lookup[service] = service_dict
        # add openstack charms
        for charm_type, charms in CHARM_TYPES.items():
            for charm in charms:
                openstack_lookup[charm] = openstack_lookup[charm_type]
        return openstack_lookup

    @classmethod
    def lookup(cls, component: str, version: str) -> List[str]:
        """Get the compatible OpenStack codenames based on the component and version.

        :param component: Name of the component. E.g: "keystone"
        :type component: str
        :param version: Version of the component. E.g: "17.0.2"
        :type version: str
        :return: Return a sorted list of compatible OpenStack codenames.
        :rtype: List[str]
        """
        if not cls._OPENSTACK_LOOKUP:
            cls.initialize_lookup()
        compatible_os_releases: List[str] = []
        if not cls._OPENSTACK_LOOKUP.get(component):
            logging.warning(
                "Not possible to find the component %s in the lookup",
                component,
            )
            return compatible_os_releases
        for openstack_release, version_range in cls._OPENSTACK_LOOKUP[component].items():
            if version in version_range:
                compatible_os_releases.append(openstack_release)
        return compatible_os_releases
