import logging
import re
from collections import defaultdict
from typing import DefaultDict

import six

from cou.zaza_utils import generic, juju, model
from cou.zaza_utils.os_versions import (
    OPENSTACK_CODENAMES,
    OVN_CODENAMES,
    PACKAGE_CODENAMES,
    SWIFT_CODENAMES,
)

CHARM_TYPES = {
    "neutron": {"pkg": "neutron-common", "origin_setting": "openstack-origin"},
    "nova": {"pkg": "nova-common", "origin_setting": "openstack-origin"},
    "glance": {"pkg": "glance-common", "origin_setting": "openstack-origin"},
    "cinder": {"pkg": "cinder-common", "origin_setting": "openstack-origin"},
    "keystone": {"pkg": "keystone", "origin_setting": "openstack-origin"},
    "openstack-dashboard": {"pkg": "openstack-dashboard", "origin_setting": "openstack-origin"},
    "ceilometer": {"pkg": "ceilometer-common", "origin_setting": "openstack-origin"},
    "designate": {"pkg": "designate-common", "origin_setting": "openstack-origin"},
    "ovn-central": {"pkg": "ovn-common", "origin_setting": "source"},
    "ceph-mon": {"pkg": "ceph-common", "origin_setting": "source"},
    "placement": {"pkg": "placement-common", "origin_setting": "openstack-origin"},
}


def get_current_os_versions(application_charm, model_name=None) -> DefaultDict:
    """Determine OpenStack codename of deployed applications.

    Initially, see if the openstack-release pkg is available and use it
    instead.

    If it isn't then it falls back to the existing method of checking the
    version of the package passed and then resolving the version from that
    using lookup tables.

    :param application_charm: Tuple of application and charm name
    :type deployed_applications: Tuple
    :param model_name: Name of model to query.
    :type model_name: str
    :returns: DefaultDict of OpenStack version and units
    :rtype: DefaultDict
    """
    application, charm = application_charm
    versions = {}
    codename = get_openstack_release(application, model_name=model_name)
    if codename:
        versions = codename
    else:
        version = generic.get_pkg_version(
            application_charm, CHARM_TYPES[charm]["pkg"], model_name=model_name
        )
        versions = get_os_code_info(CHARM_TYPES[charm]["pkg"], version)
    return versions


def get_openstack_release(application, model_name=None) -> DefaultDict:
    """Return the openstack release codename based on /etc/openstack-release.

    This will only return a codename if the openstack-release package is
    installed on the unit.

    :param application: Application name
    :type application: string
    :param model_name: Name of model to query.
    :type model_name: str
    :returns: OpenStack release codename for application and units
    :rtype: DefaultDict
    """
    versions = defaultdict(set)
    units = model.get_units(application, model_name=model_name)
    for unit in units:
        cmd = "cat /etc/openstack-release | grep OPENSTACK_CODENAME"
        try:
            out = juju.remote_run(unit.entity_id, cmd, model_name=model_name)
        except model.CommandRunFailed:
            logging.debug("Fall back to version check for OpenStack codename")
        else:
            codename = out.split("=")[1].strip()
            versions[codename].add(unit.entity_id)
    return versions


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
