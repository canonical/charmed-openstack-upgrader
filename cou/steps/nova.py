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

"""Functions for prereq steps relating to nova."""
import logging

from cou.exceptions import ApplicationNotFound, UnitNotFound
from cou.utils.juju_utils import Model

logger = logging.getLogger(__name__)


async def archive(model: Model, *, batch_size: int) -> None:
    """Archive data on a nova-cloud-controller unit.

    The archive-data action only runs a single batch,
    so we run it in a loop until completion.
    See also:
    https://charmhub.io/nova-cloud-controller/actions#archive-data
    https://docs.openstack.org/project-deploy-guide/charm-deployment-guide/wallaby/upgrade-openstack.html#archive-old-database-data
    :param model: juju model to work with
    :type model: Model
    :param batch_size: batch-size to pass to the archive-data action
        (default is 1000; decrease if performance issues seen)
    :type batch_size: int
    """  # noqa: E501 line too long
    unit_name: str = await _get_nova_cloud_controller_unit_name(model)
    while True:
        logger.debug("Running action 'archive-data' on %s", unit_name)
        # https://charmhub.io/nova-cloud-controller/actions#archive-data
        action = await model.run_action(
            unit_name=unit_name,
            action_name="archive-data",
            raise_on_failure=True,
            action_params={"batch-size": batch_size},
        )
        logger.info("action output: %s", action.data)
        output = action.data["results"]["archive-deleted-rows"]
        if "Nothing was archived" in output:
            logger.debug("Archiving complete.")
            break
        logger.debug("Potentially more data to archive...")


async def _get_nova_cloud_controller_unit_name(model: Model) -> str:
    """Get nova-cloud-controller application's first unit's name.

    Assumes only a single nova-cloud-controller application is deployed.

    :param model: juju model to work with
    :type model: Model
    :return: unit name
    :rtype: str
    :raises UnitNotFound: When cannot find a valid unit for 'nova-cloud-controller'
    :raises ApplicationNotFound: When cannot find a 'nova-cloud-controller' application
    """
    status = await model.get_status()
    for app_name, app_config in status.applications.items():
        charm_name = await model.get_charm_name(app_name)
        if charm_name == "nova-cloud-controller":
            units = list(app_config.units.keys())
            if units:
                return units[0]
            raise UnitNotFound(
                f"Cannot find unit for 'nova-cloud-controller' in model '{model.name}'."
            )

    raise ApplicationNotFound(
        f"Cannot find 'nova-cloud-controller' in model '{model.name}'."
    )
