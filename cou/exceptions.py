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
"""Module of exceptions that charmed-openstack-upgrader may raise."""
from typing import Any

from juju.action import Action


class COUException(Exception):
    """Default COU exception."""


class UnitNotFound(COUException):
    """Exception raised when a unit is not found in the model."""


class MismatchedOpenStackVersions(COUException):
    """Exception raised when more than one OpenStack version is found in the Application."""


class NoTargetError(COUException):
    """Exception raised when there is no target to upgrade."""


class HaltUpgradePlanGeneration(COUException):
    """Exception to halt the application upgrade at any moment."""


class ApplicationError(COUException):
    """Exception raised when Application does something unexpected."""


class PackageUpgradeError(COUException):
    """Exception raised when a package upgrade fails."""


class ActionFailed(COUException):
    """Exception raised when action fails."""

    # pylint: disable=consider-using-f-string
    def __init__(self, action: Action, output: Any | dict | None = None):
        """Set information about action failure in message and raise.

        :param action: Action that failed.
        :type action: Action
        :param output: Description of the failed action, defaults to None
        :type output: Optional[str], optional
        """
        params = {"output": output}
        for key in [
            "name",
            "parameters",
            "receiver",
            "message",
            "id",
            "status",
            "enqueued",
            "started",
            "completed",
        ]:
            params[key] = getattr(action, key, "<not-set>")

        message = (
            'Run of action "{name}" with parameters "{parameters}" on '
            '"{receiver}" failed with "{message}" (id={id} '
            "status={status} enqueued={enqueued} started={started} "
            "completed={completed} output={output})".format(**params)
        )
        super().__init__(message)


class TimeoutException(COUException):
    """COU timeout exception."""
