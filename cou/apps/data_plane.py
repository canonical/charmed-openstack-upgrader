# Copyright 2024 Canonical Limited
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

"""Data plane application class."""
import logging
from typing import Optional

from cou.apps.base import OpenStackApplication
from cou.apps.factory import AppFactory

logger = logging.getLogger(__name__)


class BaseDataPlaneApplication(OpenStackApplication):
    """Base data plane application."""

    async def _check_control_plane_was_upgraded(self) -> bool:
        """Check that all control plane apps was upgraded.

        This function is part of required pre-checks for all data plane apps.
        """
        raise NotImplementedError

    async def populate_units(
        self,
        hostname: Optional[str] = None,
        machine_id: Optional[str] = None,
        az: Optional[str] = None,
    ) -> None:
        """Populate units and filtered specific machine, hostname or az.

        :param hostname: machine hostname
        :type hostname: str
        :param machine_id: machine id
        :type machine_id: str
        :param az: az of machine
        :type az: str
        """
        raise NotImplementedError


@AppFactory.register_application(["nova-compute"])
class NovaCompute(BaseDataPlaneApplication):
    """Nova-compute application."""

    wait_timeout = 30 * 60  # 30 min
    wait_for_model = True

    async def instance_count(self) -> int:
        """Get number of instances running on hypervisor."""
        raise NotImplementedError

    async def populate_units(self, *args: Optional[str], **kwargs: Optional[str]) -> None:
        """Populate units and filtered specific machine, hostname or az.

        :param args: arguments parser
        :type args: Any
        :param kwargs: named argument parser
        :type kwargs: Any
        """
        raise NotImplementedError
