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

"""Lookup utils to have the latest compatible Openstack codename based on workload version."""

import csv
import logging
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from typing import Any, Union

from packaging.version import Version


@dataclass(frozen=True)
class Versions:
    min_version: Version
    max_version: Version
    minor: bool = False
    micro: bool = False


def generate_openstack_lookup() -> OrderedDict:
    """Generate an OpenStack lookup dictionary based on the version of the components.

    The dictionary is generated thru an static csv file that should be update regularly
    to include new Openstack releases and update the min and max versions of the services.
    The csv table is made from the release page [0] charm delivery [1], cmadison and rmadison.

    In the csv file it's possible to see that there are two columns named "minor" and "micro".
    Set to true if the service does not get major version updates between OpenStack releases.
    E.g:
    ussuri: 10.1.3 focal 11.2.3. In this case the identifier is the "major" (10 and 11).
    ussuri: 17.1.6 focal: 17.2.3. In this case the identifier is the "minor" (17.1 and 17.2).
    ussuri: 13.1.0 focal 13.1.1. In this case the identifier is the "micro" (13.1.0 and 13.1.1).

    charm designate-bind workload_version tracks the version of the deb package bind9.

    [0] https://releases.openstack.org/
    [1] https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html

    :return: Ordered dictionary containing the version and the possible Openstack release.
    :rtype: OrderedDict
    """
    charms_types = {
        "ceph": ["ceph-mon", "ceph-fs", "ceph-radosgw", "ceph-osd"],
        "swift": ["swift-proxy", "swift-storage"],
        "nova": ["nova-cloud-controller", "nova-compute"],
        "ovn": ["ovn-dedicated-chassis", "ovn-central"],
        "neutron": ["neutron-api", "neutron-gateway"],
        "manila": ["manila-ganesha"],
        "horizon": ["openstack-dashboard"],
    }
    with open("cou/utils/openstack_lookup.csv") as csv_file:
        openstack_lookup = OrderedDict()
        service_column_index = 0
        minor_column_index = 1
        micro_column_index = 2
        version_start_column_index = 3
        csv_reader = csv.reader(csv_file, delimiter=",")
        header = next(csv_reader)
        for row in csv_reader:
            service_dict: defaultdict[str, Any] = defaultdict(OrderedDict)
            service = row[service_column_index]
            minor = row[minor_column_index]
            micro = row[micro_column_index]
            for column_index in range(version_start_column_index, len(row), 2):
                os_version, _ = header[column_index].split("-")
                min_version = row[column_index]
                max_version = row[column_index + 1]
                service_dict[os_version] = Versions(
                    Version(min_version),
                    Version(max_version),
                    True if minor == "TRUE" else False,
                    True if micro == "TRUE" else False,
                )
            openstack_lookup[service] = service_dict
    for charm_type, charms in charms_types.items():
        for charm in charms:
            openstack_lookup[charm] = openstack_lookup[charm_type]
    return openstack_lookup


OPENSTACK_LOOKUP = generate_openstack_lookup()


def get_latest_compatible_openstack_codename(
    charm: str, workload_version: str
) -> Union[str, None]:
    """Get the latest Openstack codename based on the charm name and workload version.

    :param charm: Charm name.
    :type charm: str
    :param workload_version: Workload version of a charm.
    :type workload_version: str
    :return: Return the latest compatible Openstack codename or None if not found.
    :rtype: Union[str, None]
    """
    wl_version = Version(workload_version)
    possible_os_releases = []
    if not OPENSTACK_LOOKUP.get(charm):
        logging.warning(
            (
                "Not possible to find a compatible Openstack codename for "
                "charm: %s with workload_version: %s"
            ),
            charm,
            workload_version,
        )
        return None
    for openstack_release, versions in OPENSTACK_LOOKUP[charm].items():
        if versions.minor and not versions.micro:
            wl_version = Version(f"{wl_version.major}.{wl_version.minor}")
            if wl_version >= versions.min_version and wl_version <= versions.max_version:
                possible_os_releases.append(openstack_release)
        elif versions.micro:
            wl_version = Version(wl_version.public)
            if wl_version >= versions.min_version and wl_version <= versions.max_version:
                possible_os_releases.append(openstack_release)
        else:
            if wl_version.major == versions.max_version.major:
                possible_os_releases.append(openstack_release)
    if possible_os_releases:
        return possible_os_releases[-1]
    return None
