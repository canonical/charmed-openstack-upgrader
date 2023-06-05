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

"""Manage global upgrade utilities."""

import itertools
import logging
import re

from cou.zaza_utils import model, os_versions


def extract_charm_name_from_url(charm_url):
    """Extract the charm name from the charm url.

    E.g. Extract 'heat' from local:bionic/heat-12

    :param charm_url: Name of model to query.
    :type charm_url: str
    :returns: Charm name
    :rtype: str
    """
    charm_name = re.sub(r"-[0-9]+$", "", charm_url.split("/")[-1])
    return charm_name.split(":")[-1]


def _filter_non_openstack_services(app, app_config, model_name=None):
    charm_options = model.get_application_config(app, model_name=model_name).keys()
    src_options = ["openstack-origin", "source"]
    if not [x for x in src_options if x in charm_options]:
        logging.warning("Excluding {} from upgrade, no src option".format(app))
        return True
    return False


def _filter_openstack_upgrade_list(app, app_config, model_name=None):
    charm_name = extract_charm_name_from_url(app_config["charm"])
    if app in os_versions.UPGRADE_EXCLUDE_LIST or charm_name in os_versions.UPGRADE_EXCLUDE_LIST:
        print("Excluding {} from upgrade, on the exclude list".format(app))
        logging.warning("Excluding {} from upgrade, on the exclude list".format(app))
        return True
    return False


def _filter_subordinates(app, app_config, model_name=None):
    if app_config.get("subordinate-to"):
        logging.warning("Excluding {} from upgrade, it is a subordinate".format(app))
        return True
    return False


def _include_app(app, app_config, filters, model_name=None):
    for filt in filters:
        if filt(app, app_config, model_name=model_name):
            return False
    return True


def _build_service_groups(applications):
    groups = []
    for phase_name, charms in os_versions.SERVICE_GROUPS:
        group = []
        for app, app_config in applications.items():
            charm_name = extract_charm_name_from_url(app_config["charm"])
            if charm_name in charms:
                group.append(app)
        groups.append((phase_name, group))

    # collect all the values into a list, and then a lookup hash
    values = list(itertools.chain(*(ls for _, ls in groups)))
    vhash = {v: 1 for v in values}
    sweep_up = [app for app in applications if app not in vhash]
    groups.append(("sweep_up", sweep_up))
    for name, group in groups:
        group.sort()
    return groups


def get_upgrade_candidates(model_name=None, filters=None):
    """Extract list of apps from model that can be upgraded.

    :param model_name: Name of model to query.
    :type model_name: str
    :param filters: List of filter functions to apply
    :type filters: List[fn]
    :returns: List of application that can have their payload upgraded.
    :rtype: Dict[str, Dict[str, ANY]]
    """
    if filters is None:
        filters = []
    status = model.get_status(model_name=model_name)
    candidates = {}
    for app, app_config in status.applications.items():
        if _include_app(app, app_config, filters, model_name=model_name):
            candidates[app] = app_config
    return candidates


def get_upgrade_groups(model_name=None):
    """Place apps in the model into their upgrade groups.

    Place apps in the model into their upgrade groups. If an app is deployed
    but is not in SERVICE_GROUPS then it is placed in a sweep_up group.

    :param model_name: Name of model to query.
    :type model_name: str
    :returns: Dict of group lists keyed on group name.
    :rtype: collections.OrderedDict
    """
    filters = [
        _filter_subordinates,
        _filter_openstack_upgrade_list,
        _filter_non_openstack_services,
    ]
    apps_in_model = get_upgrade_candidates(model_name=model_name, filters=filters)

    return _build_service_groups(apps_in_model)


def _check_db_relations(app_config):
    """Check the db relations.

    Gets the openstack database mysql-innodb-cluster application if there are more than one
    application the one with the keystone relation is selected.

    :param app_config: juju app config
    :type app_config: str
    :returns: True if it has a relation with keystone
    :rtype: bool
    """
    for relation, app_list in app_config.relations.items():
        if relation == "db-router":
            if len([a for a in app_list if "keystone".casefold() in a.casefold()]) > 0:
                return True
    return False


def get_database_app(model_name=None):
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
