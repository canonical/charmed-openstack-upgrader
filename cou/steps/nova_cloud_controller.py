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
from typing import Optional, Sequence

from cou.exceptions import COUException, UnitNotFound
from cou.utils.juju_utils import Application, Model, get_applications_by_charm_name

logger = logging.getLogger(__name__)


async def archive(model: Model, apps: Sequence[Application], *, batch_size: int) -> None:
    """Archive data on a nova-cloud-controller unit.

    The archive-data action only runs a single batch,
    so we run it in a loop until completion.
    See also:
    https://charmhub.io/nova-cloud-controller/actions#archive-data
    https://docs.openstack.org/project-deploy-guide/charm-deployment-guide/wallaby/upgrade-openstack.html#archive-old-database-data
    :param model: juju model to work with
    :type model: Model
    :param apps: Applications in the model
    :type apps: Sequence of Applications
    :param batch_size: batch-size to pass to the archive-data action
        (default is 1000; decrease if performance issues seen)
    :type batch_size: int
    :raises COUException: if action returned unexpected output
    """  # noqa: E501 line too long
    unit_name: str = await _get_nova_cloud_controller_unit_name(apps)
    # The archive-data action only archives a single batch,
    # so we must run it in a loop until everything is archived.
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
        output = action.results.get("archive-deleted-rows")
        if output is None:
            raise COUException(
                "Expected to find output in action results.'archive-deleted-rows', "
                "but it was not present."
            )
        # The command will contain this string if there is nothing left to archive.
        # This means we don't need to run the command any more.
        if "Nothing was archived" in output:
            logger.debug("Archiving complete.")
            break
        logger.debug("Potentially more data to archive...")


async def purge(model: Model, apps: Sequence[Application], before: Optional[str]) -> None:
    """Purge data on a nova-cloud-controller unit.

    The purge-data action delete rows from shadow tables.
    :param model: juju model to work with
    :type model: Model
    :param apps: Applications in the model
    :type apps: Sequence of Applications
    :param before: specifying before will delete data from all shadow tables
        that is older than the data provided.
        Date string format should be YYYY-MM-DD[HH:mm][:ss]
    :raises COUException: if action returned unexpected output or failed
    """
    action_params = {}
    if before is not None:
        action_params = {"before": before}

    unit_name: str = await _get_nova_cloud_controller_unit_name(apps)
    action = await model.run_action(
        unit_name=unit_name,
        action_name="purge-data",
        raise_on_failure=True,
        action_params=action_params,
    )
    output = action.results.get("output")
    if output is None:
        raise COUException(
            "Expected to find output in action results. 'output', but it was not present."
        )
    if "Purging stale soft-deleted rows failed" in output:
        raise COUException(
            f"purge-data action failed on {unit_name}, please check unit's debug log"
            " for more details."
        )
    if "Purging stale soft-deleted rows and no data was deleted" in output:
        logger.info("purge-data action succeeded on %s (no data was deleted)", unit_name)
    else:
        logger.info("purge-data action succeeded on %s", unit_name)


async def _get_nova_cloud_controller_unit_name(apps: Sequence[Application]) -> str:
    """Get nova-cloud-controller application's first unit's name.

    Assumes only a single nova-cloud-controller application is deployed.

    :param apps: Applications in the model
    :type apps: Sequence of Applications
    :return: unit name
    :rtype: str
    :raises UnitNotFound: When cannot find a valid unit for 'nova-cloud-controller'
    :raises ApplicationNotFound: When cannot find a 'nova-cloud-controller' application
    """
    apps = await get_applications_by_charm_name(apps, "nova-cloud-controller")
    for app in apps:
        units = list(app.units.keys())
        if units:
            return units[0]
    raise UnitNotFound("Cannot find unit for 'nova-cloud-controller'.")
