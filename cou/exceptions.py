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
from typing import Optional

from juju.action import Action


class CommandRunFailed(Exception):
    """Exception raised when a command fails to run."""

    def __init__(self, cmd: str, code: str, output: str, err: str):
        """Create Command run failed exception.

        :param cmd: Command that was run
        :type cmd: string
        :param result: Dict containing the output of the command
        :type result: dict - {'Code': '0', 'Stdout': '', 'Stderr':''}
        """
        msg = f"Command {cmd} failed with code {code}, output {output} and error {err}"
        super().__init__(msg)


class UnitNotFound(Exception):
    """Exception raised when a unit is not found in the model."""


class JujuError(Exception):
    """Exception raised when libjuju does something unexpected."""


class MismatchedOpenStackVersions(Exception):
    """Exception raised when more than one OpenStack version is found in the Application."""


class NoTargetError(Exception):
    """Exception raised when there is no target to upgrade."""


class HaltUpgradePlanGeneration(Exception):
    """Exception to halt the application upgrade at any moment."""


class ApplicationError(Exception):
    """Exception raised when Application does something unexpected."""


class PackageUpgradeError(Exception):
    """Exception raised when a package upgrade fails."""


class ActionFailed(Exception):
    # pylint: disable=consider-using-f-string
    """Exception raised when action fails."""

    def __init__(self, action: Action, output: Optional[str] = None):
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
