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

"""Manage global upgrade utilities."""

from typing import Tuple

from cou.utils import os_versions

UPGRADE_ORDER = [
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
    "ovn-central",
    "ovn-dedicated-chassis",
    "placement",
    "nova-cloud-controller",
    "nova-compute",
    "openstack-dashboard",
    "ceph-osd",
    "swift-proxy",
    "swift-storage",
    "octavia",
]


def determine_next_openstack_release(release: str) -> Tuple[str, str]:
    """Determine the next release after the one passed as a str.

    The returned value is a tuple of the form: ('2020.1', 'ussuri')

    :param release: the release to use as the base
    :type release: str
    :returns: the release tuple immediately after the current one.
    :rtype: Tuple[str, str]
    :raises: KeyError if the current release doesn't actually exist
    """
    old_index = list(os_versions.OPENSTACK_CODENAMES.values()).index(release)
    new_index = old_index + 1
    return list(os_versions.OPENSTACK_CODENAMES.items())[new_index]
