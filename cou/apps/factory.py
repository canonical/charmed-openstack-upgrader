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

"""Application factory class."""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Optional

from juju.client._definitions import ApplicationStatus

from cou.apps.base import OpenStackApplication
from cou.utils.juju_utils import COUModel
from cou.utils.openstack import is_charm_supported

logger = logging.getLogger(__name__)


class AppFactory:
    """Factory class for Application objects."""

    charms: dict[str, type[OpenStackApplication]] = {}

    @classmethod
    def create(
        cls,
        name: str,
        status: ApplicationStatus,
        config: dict,
        model: COUModel,
        charm: str,
    ) -> Optional[OpenStackApplication]:
        """Create the OpenStackApplication or registered subclasses.

        Applications Subclasses registered with the "register_application"
        decorator can be instantiated and used with their customized methods.
        :param name: Name of the application
        :type name: str
        :param status: Status of the application
        :type status: ApplicationStatus
        :param config: Configuration of the application
        :type config: dict
        :param model: COUModel object
        :type model: COUModel
        :param charm: Name of the charm
        :type charm: str
        :return: The OpenStackApplication class or None if not supported.
        :rtype: Optional[OpenStackApplication]
        """
        # pylint: disable=too-many-arguments
        if is_charm_supported(charm):
            app_class = cls.charms.get(charm, OpenStackApplication)
            return app_class(name=name, status=status, config=config, model=model, charm=charm)
        logger.debug(
            "'%s' is not a supported OpenStack related application and will be ignored.",
            name,
        )
        return None

    @classmethod
    def register_application(
        cls, charms: list[str]
    ) -> Callable[[type[OpenStackApplication]], type[OpenStackApplication]]:
        """Register Application subclasses.

        Use this method as decorator to register Applications that
        cannot be described appropriately by the OpenStackApplication class.

        Example:
        ceph_charms = ["ceph-mon", "ceph-fs", "ceph-radosgw", "ceph-osd"]

        @AppFactory.register_application(ceph_charms)
        class Ceph(OpenStackApplication):
            pass
        This is registering the charms "ceph-mon", "ceph-fs", "ceph-radosgw", "ceph-osd"
        to the Ceph class.

        :param charms: List of charms names.
        :type charms: list[str]
        :return: The decorated class. E.g: the Ceph class in the example above.
        :rtype: Callable[[type[OpenStackApplication]], type[OpenStackApplication]]
        """

        def decorator(  # pylint: disable=W9011
            application: type[OpenStackApplication],
        ) -> type[OpenStackApplication]:
            for charm in charms:
                cls.charms[charm] = application
            return application

        return decorator
