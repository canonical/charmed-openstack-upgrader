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

"""Functions for backing up openstack database."""
import logging
import os
from pathlib import Path

from cou.exceptions import UnitNotFound
from cou.utils import COU_DATA
from cou.utils.juju_utils import COUModel

logger = logging.getLogger(__name__)


async def backup(model: COUModel) -> Path:
    """Backup mysql database of openstack.

    :param model: COUModel object
    :type model: COUModel
    :return: Path of the local file from the backup.
    :rtype: Path
    """
    logger.info("Backing up mysql database")
    unit_name = await get_database_app_unit_name(model)

    logger.info("mysqldump mysql-innodb-cluster DBs ...")
    action = await model.run_action(unit_name, "mysqldump")
    remote_file = action.data["results"]["mysqldump-file"]
    basedir = action.data["parameters"]["basedir"]

    logger.info("Set permissions to read mysql-innodb-cluster:%s ...", basedir)
    await model.run_on_unit(unit_name, f"chmod o+rx {basedir}")

    local_file = COU_DATA / os.path.basename(remote_file)
    logger.info("SCP from  mysql-innodb-cluster:%s to %s ...", remote_file, local_file)
    await model.scp_from_unit(unit_name, remote_file, str(local_file))

    logger.info("Remove permissions to read mysql-innodb-cluster:%s ...", basedir)
    await model.run_on_unit(unit_name, f"chmod o-rx {basedir}")
    return local_file


def _check_db_relations(app_config: dict) -> bool:
    """Check the db relations.

    Gets the openstack database mysql-innodb-cluster application if there are more than one
    application the one with the keystone relation is selected.

    :param app_config: juju app config
    :type app_config: str
    :returns: True if it has a relation with keystone
    :rtype: bool
    """
    for relation, app_list in app_config["relations"].items():
        if relation == "db-router":
            if len([a for a in app_list if "keystone".casefold() in a.casefold()]) > 0:
                return True
    return False


async def get_database_app_unit_name(model: COUModel) -> str:
    """Get mysql-innodb-cluster application's first unit's name.

    Gets the openstack database mysql-innodb-cluster application if there are more than one
    application the one with the keystone relation is selected.

    :param model: COUModel object
    :type model: COUModel
    :raises UnitNotFound: When cannot find a valid unit for 'mysql-innodb-cluster
    :returns: Name of the mysql-innodb-cluster application name
    :rtype: ApplicationStatus
    """
    status = await model.get_status()
    for app_name, app_config in status.applications.items():
        charm_name = await model.get_charm_name(app_name)
        if charm_name == "mysql-innodb-cluster" and _check_db_relations(app_config):
            return list(app_config.units.keys())[0]

    raise UnitNotFound(
        f"Cannot find a valid unit for 'mysql-innodb-cluster' in model '{model.name}'."
    )
