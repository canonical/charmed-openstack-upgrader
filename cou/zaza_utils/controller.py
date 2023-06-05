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
"""Module for interacting with a juju controller."""

import asyncio
import logging
import subprocess

from juju.controller import Controller

from cou.zaza_utils import exceptions, sync_wrapper


async def async_add_model(model_name, config=None, cloud_name=None, region=None):
    """Add a model to the current controller.

    :param model_name: Name to give the new model.
    :type model_name: str
    :param config: Model configuration.
    :type config: dict
    :param region: Region in which to create the model.
    :type region: str
    """
    controller = Controller()
    await controller.connect()
    logging.debug("Adding model {}".format(model_name))
    model = await controller.add_model(
        model_name, config=config, cloud_name=cloud_name, region=region
    )
    # issue/135 It is necessary to disconnect the model here or async spews
    # tracebacks even during a successful run.
    await model.disconnect()
    await controller.disconnect()


add_model = sync_wrapper(async_add_model)


async def async_destroy_model(model_name):
    """Remove a model from the current controller.

    :param model_name: Name of model to remove
    :type model_name: str
    """
    controller = Controller()
    try:
        await controller.connect()
        logging.info("Destroying model {}".format(model_name))
        await controller.destroy_model(model_name, destroy_storage=True, force=True, max_wait=600)
        # The model ought to be destroyed by now.  Let's make sure, and if not,
        # raise an error.  Even if the model has been destroyed, it's still
        # hangs around in the .list_models() for a little while; retry until it
        # goes away, or that fails.
        attempt = 1
        while True:
            logging.info("Waiting for model to be fully destroyed: " "attempt: {}".format(attempt))
            remaining_models = await controller.list_models()
            if model_name not in remaining_models:
                break
            await asyncio.sleep(10)
            attempt += 1
            if attempt > 20:
                raise exceptions.DestroyModelFailed(
                    "Destroying model {} failed.".format(model_name)
                )

        logging.info("Model {} destroyed.".format(model_name))
    finally:
        try:
            await controller.disconnect()
        except Exception as e:
            logging.error("Couldn't disconnect from model: {}".format(str(e)))


destroy_model = sync_wrapper(async_destroy_model)


async def async_cloud(name=None):
    """Return information about cloud.

    :param name: Cloud name. If not specified, the cloud where
                 the controller lives on is returned.
    :type name: Optional[str]
    :returns: Information on all clouds in the controller.
    :rtype: CloudResult
    """
    controller = Controller()
    await controller.connect()
    cloud = await controller.cloud(name=name)
    await controller.disconnect()
    return cloud


cloud = sync_wrapper(async_cloud)


def get_cloud_type(name=None):
    """Return type of cloud.

    :param name: Cloud name. If not specified, the cloud where
                 the controller lives on is returned.
    :type name: Optional[str]
    :returns: Type of cloud
    :rtype: str
    """
    _cloud = cloud(name=name)
    return _cloud.cloud.type_


async def async_get_cloud():
    """Return the name of the current cloud.

    :returns: Name of cloud
    :rtype: str
    """
    controller = Controller()
    await controller.connect()
    cloud = await controller.get_cloud()
    await controller.disconnect()
    return cloud


get_cloud = sync_wrapper(async_get_cloud)


async def async_list_models():
    """Return a list of the available models.

    :returns: List of models
    :rtype: list
    """
    controller = Controller()
    await controller.connect()
    models = await controller.list_models()
    await controller.disconnect()
    return models


list_models = sync_wrapper(async_list_models)


def go_list_models():
    """Execute juju models.

    NOTE: Excuting the juju models command updates the local cache of models.
    Python-juju currently does not update the local cache on add model.
    https://github.com/juju/python-libjuju/issues/267

    :returns: None
    :rtype: None
    """
    cmd = ["juju", "models"]
    subprocess.check_call(cmd)
