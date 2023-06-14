# Copyright 2023 Canonical Limited.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Functions for backing up openstack database."""
import logging
import os
from typing import Optional

from cou.zaza_utils import model
from cou.zaza_utils.upgrade_utils import (
    extract_charm_name_from_url,
    get_upgrade_candidates,
)


def backup() -> str:
    """Backup mysql database of openstack."""
    logging.info("Backing up mysql database")

    mysql_app = get_database_app()
    mysql_leader = model.get_unit_from_name(model.get_lead_unit_name(mysql_app))

    logging.info("mysqldump mysql-innodb-cluster DBs ...")
    action = model.run_action_on_leader(mysql_app, "mysqldump")
    remote_file = action.data["results"]["mysqldump-file"]
    basedir = action.data["parameters"]["basedir"]

    logging.info("Set permissions to read mysql-innodb-cluster:%s ...", basedir)
    model.run_on_leader(mysql_app, f"chmod o+rx {basedir}")

    local_file = os.path.abspath(os.path.basename(remote_file))
    logging.info("SCP from  mysql-innodb-cluster:%s to %s ...", remote_file, local_file)
    model.scp_from_unit(mysql_leader.name, remote_file, local_file)

    logging.info("Remove permissions to read mysql-innodb-cluster:%s ...", basedir)
    model.run_on_leader(mysql_app, f"chmod o-rx {basedir}")
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


def get_database_app(model_name: Optional[str] = None) -> Optional[str]:
    """Get mysql-innodb-cluster application name.

    Gets the openstack database mysql-innodb-cluster application if there are more than one
    application the one with the keystone relation is selected.

    :param model_name: Name of model to query.
    :type model_name: str
    :returns: Name of the mysql-innodb-cluster application name
    :rtype: str
    """
    candidates = get_upgrade_candidates(model_name=model_name)
    for app, app_config in candidates.items():
        charm_name = extract_charm_name_from_url(app_config["charm"])
        if charm_name == "mysql-innodb-cluster" and _check_db_relations(app_config):
            return app

    return None
