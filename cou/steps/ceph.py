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

"""Functions for prereq steps related to ceph."""
import json
import logging

from cou.exceptions import ApplicationError, ApplicationNotFound
from cou.utils.juju_utils import Model

logger = logging.getLogger(__name__)


async def verify_ceph_cluster_noout_unset(model: Model) -> None:
    """Ensure ceph cluster has the noout flag unset.

    :param model: juju model to work with
    :type model: Model
    :raises ApplicationNotFound: if ceph-mon not found
    :raises ApplicationError: if noout is set
    """
    try:
        status = await model.get_application_status(app_name="ceph-mon")
        leader_unit = [unit for unit in status["units"] if status["units"][unit]["leader"]][0]
    except ApplicationNotFound:
        logger.warning("Application ceph-mon not found, skipping")
    else:
        results = await model.run_on_unit(leader_unit, "ceph osd dump -f json")
        osd_flags_set = json.loads(results["stdout"].strip()).get("flags_set", [])
        if "noout" in osd_flags_set:
            raise ApplicationError(
                "'noout' flag is set for ceph cluster, please fix any issues and"
                " unset manually before continue with `cou upgrade`."
            )
