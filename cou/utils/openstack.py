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
    PACKAGE_CODENAMES,
    SWIFT_CODENAMES,
)

CHARM_TYPES = {
    "neutron": {
        "representative_workload_pkg": "neutron-common",
        "origin_setting": "openstack-origin",
    },
    "nova": {"representative_workload_pkg": "nova-common", "origin_setting": "openstack-origin"},
    "glance": {
        "representative_workload_pkg": "glance-common",
        "origin_setting": "openstack-origin",
    },
    "cinder": {
        "representative_workload_pkg": "cinder-common",
        "origin_setting": "openstack-origin",
    },
    "keystone": {"representative_workload_pkg": "keystone", "origin_setting": "openstack-origin"},
    "openstack-dashboard": {
        "representative_workload_pkg": "openstack-dashboard",
        "origin_setting": "openstack-origin",
    },
    "ceilometer": {
        "representative_workload_pkg": "ceilometer-common",
        "origin_setting": "openstack-origin",
    },
    "designate": {
        "representative_workload_pkg": "designate-common",
        "origin_setting": "openstack-origin",
    },
    "ovn-central": {"representative_workload_pkg": "ovn-common", "origin_setting": "source"},
    "ceph-mon": {"representative_workload_pkg": "ceph-common", "origin_setting": "source"},
    "placement": {
        "representative_workload_pkg": "placement-common",
        "origin_setting": "openstack-origin",
    },
    "nova-cloud-controller": {
        "representative_workload_pkg": "nova-common",
        "origin_setting": "openstack-origin",
    },
}


def get_os_code_info(package, pkg_version) -> str:
    """Determine OpenStack codename that corresponds to package version.

    :param package: Package name
    :type package: string
    :param pkg_version: Package version
    :type pkg_version: string
    :returns: Codename for package
    :rtype: string
    """
    # Remove epoch if it exists
    if ":" in pkg_version:
        pkg_version = pkg_version.split(":")[1:][0]
    if "swift" in package:
        # Fully x.y.z match for swift versions
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)", pkg_version)
    else:
        # x.y match only for 20XX.X
        # and ignore patch level for other packages
        match = re.match(r"^(\d+)\.(\d+)", pkg_version)

    if match:
        vers = match.group(0)
    # Generate a major version number for newer semantic
    # versions of openstack projects
    major_vers = vers.split(".")[0]
    if package in PACKAGE_CODENAMES and major_vers in PACKAGE_CODENAMES[package]:
        return PACKAGE_CODENAMES[package][major_vers]
    else:
        # < Liberty co-ordinated project versions
        if "swift" in package:
            return get_swift_codename(vers)
        elif "ovn" in package:
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
