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

import re

import six

from cou.utils.os_versions import (
    OPENSTACK_CODENAMES,
    OVN_CODENAMES,
    SWIFT_CODENAMES,
    WORKLOAD_CODENAMES,
)

CHARM_TYPES = {
    "neutron": {"workload": "neutron-common", "origin_setting": "openstack-origin"},
    "nova": {"workload": "nova-common", "origin_setting": "openstack-origin"},
    "glance": {"workload": "glance-common", "origin_setting": "openstack-origin"},
    "cinder": {"workload": "cinder-common", "origin_setting": "openstack-origin"},
    "keystone": {"workload": "keystone", "origin_setting": "openstack-origin"},
    "openstack-dashboard": {
        "workload": "openstack-dashboard",
        "origin_setting": "openstack-origin",
    },
    "ceilometer": {"workload": "ceilometer-common", "origin_setting": "openstack-origin"},
    "designate": {"workload": "designate-common", "origin_setting": "openstack-origin"},
    "ovn-central": {"workload": "ovn-common", "origin_setting": "source"},
    "ceph-mon": {"workload": "ceph-common", "origin_setting": "source"},
    "placement": {"workload": "placement-common", "origin_setting": "openstack-origin"},
    "nova-cloud-controller": {"workload": "nova-common", "origin_setting": "openstack-origin"},
}


def get_os_code_info(workload_name, workload_version) -> str:
    """Determine OpenStack codename that corresponds to package version.

    :param workload_name: Workload name
    :type workload_name: string
    :param workload_version: Workload version
    :type workload_version: string
    :returns: Codename for workload
    :rtype: string
    """
    # Remove epoch if it exists
    if ":" in workload_version:
        workload_version = workload_version.split(":")[1:][0]
    if "swift" in workload_name:
        # Fully x.y.z match for swift versions
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)", workload_version)
    else:
        # x.y match only for 20XX.X
        # and ignore patch level for other packages
        match = re.match(r"^(\d+)\.(\d+)", workload_version)

    if match:
        vers = match.group(0)
    # Generate a major version number for newer semantic
    # versions of openstack projects
    major_vers = vers.split(".")[0]
    if workload_name in WORKLOAD_CODENAMES and major_vers in WORKLOAD_CODENAMES[workload_name]:
        return WORKLOAD_CODENAMES[workload_name][major_vers]
    else:
        # < Liberty co-ordinated project versions
        if "swift" in workload_name:
            return get_swift_codename(vers)
        elif "ovn" in workload_name:
            return get_ovn_codename(vers)
        else:
            return OPENSTACK_CODENAMES[vers]


# Codename and package versions
def get_swift_codename(version):
    """Determine OpenStack codename that corresponds to swift version.

    :param version: Version of Swift
    :type version: string
    :returns: Codename for swift
    :rtype: string
    """
    return _get_special_codename(version, SWIFT_CODENAMES)


def get_ovn_codename(version):
    """Determine OpenStack codename that corresponds to OVN version.

    :param version: Version of OVN
    :type version: string
    :returns: Codename for OVN
    :rtype: string
    """
    return _get_special_codename(version, OVN_CODENAMES)


def _get_special_codename(version, codenames):
    found = [k for k, v in six.iteritems(codenames) if version in v]
    return found[0]
