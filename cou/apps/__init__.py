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
"""Applications for charmed-openstack-upgrader."""

import logging
from typing import Optional

from juju.client._definitions import FullStatus

from cou.apps.app import OpenStackApplication
from cou.apps.auxiliary import OpenStackAuxiliaryApplication
from cou.apps.auxiliary_subordinate import OpenStackAuxiliarySubordinateApplication
from cou.apps.subordinate import OpenStackSubordinateApplication
from cou.utils import juju_utils

logger = logging.getLogger(__name__)


APPS: dict[str, type[OpenStackApplication]] = {
    "hacluster": OpenStackAuxiliarySubordinateApplication,
    "mysql-router": OpenStackAuxiliarySubordinateApplication,
    "rabbitmq-server": OpenStackAuxiliaryApplication,
    "vault": OpenStackAuxiliaryApplication,
    "mysql-innodb-cluster": OpenStackAuxiliaryApplication,
    "ovn-dedicated-chassis": OpenStackAuxiliaryApplication,
    "ovn-central": OpenStackAuxiliaryApplication,
    "barbican-vault": OpenStackSubordinateApplication,
    "ceilometer-agent": OpenStackSubordinateApplication,
    "cinder-backup-swift-proxy": OpenStackSubordinateApplication,
    "cinder-ceph": OpenStackSubordinateApplication,
    "cinder-lvm": OpenStackSubordinateApplication,
    "cinder-netapp": OpenStackSubordinateApplication,
    "cinder-purestorage": OpenStackSubordinateApplication,
    "keystone-kerberos": OpenStackSubordinateApplication,
    "keystone-ldap": OpenStackSubordinateApplication,
    "keystone-saml-mellon": OpenStackSubordinateApplication,
    "magnum-dashboard": OpenStackSubordinateApplication,
    "manila-dashboard": OpenStackSubordinateApplication,
    "manila-generic": OpenStackSubordinateApplication,
    "masakari-monitors": OpenStackSubordinateApplication,
    "neutron-api-plugin-arista": OpenStackSubordinateApplication,
    "neutron-api-plugin-ironic": OpenStackSubordinateApplication,
    "neutron-api-plugin-ovn": OpenStackSubordinateApplication,
    "neutron-openvswitch": OpenStackSubordinateApplication,
    "octavia-dashboard": OpenStackSubordinateApplication,
    "octavia-diskimage-retrofit": OpenStackSubordinateApplication,
}


async def get_apps(status: FullStatus, model_name: Optional[str]) -> set[OpenStackApplication]:
    """Get all supported applications from juju status.

    :param status: Juju status
    :type status: FullStatus
    :param model_name: Name of model to query
    :type model_name: Optional[str]
    :return: Application objects with their respective information.
    :rtype: List[OpenStackApplication]
    """
    apps = set()
    for name, app_status in status.applications.items():
        app = APPS.get(name)
        if app is None:
            logger.debug("app %s is not supported", name)
            continue

        apps.add(
            app(
                name=name,
                status=app_status,
                config=await juju_utils.get_application_config(name, model_name),
                model_name=model_name,
                charm=await juju_utils.extract_charm_name(name, model_name),
            )
        )

    return apps
