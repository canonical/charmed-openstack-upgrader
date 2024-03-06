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
from typing import Any, Optional, Union

from juju.action import Action


class COUException(Exception):
    """Default COU exception."""


class CommandRunFailed(COUException):
    """Exception raised when a command fails to run."""

    def __init__(self, cmd: str, result: dict):
        """Create Command run failed exception.

        :param cmd: Command that was run
        :type cmd: string
        :param result: Dict returned by juju containing the output of the command
        :type result: dict - {'Code': '0', 'Stdout': '', 'Stderr':''}
        """
        code = result.get("Code")
        output = result.get("Stdout")
        err = result.get("Stderr")
        msg = f"Command {cmd} failed with code {code}, output {output} and error {err}"
        super().__init__(msg)


class UnitNotFound(COUException):
    """Exception raised when a unit is not found in the model."""


class ApplicationNotFound(COUException):
    """Exception raised when an application is not found in the model."""


class MismatchedOpenStackVersions(COUException):
    """Exception raised when more than one OpenStack version is found in the Application."""


class NoTargetError(COUException):
    """Exception raised when there is no target to upgrade."""


class HaltUpgradePlanGeneration(COUException):
    """Exception to halt the application plan generation at any moment."""


class HaltUpgradeExecution(COUException):
    """Exception to halt the application upgrade at any moment."""


class ApplicationError(COUException):
    """Exception raised when Application does something unexpected."""


class RunUpgradeError(COUException):
    """Exception raised when an upgrade fails."""


class DataPlaneMachineFilterError(COUException):
    """Exception raised when filtering data-plane machines fails."""


class ActionFailed(COUException):
    """Exception raised when action fails."""

    # pylint: disable=consider-using-f-string
    def __init__(self, action: Action, output: Optional[Union[Any, dict]] = None):
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


class CanceledStep(COUException):
    """COU exception when executing canceled step."""


class HighestReleaseAchieved(COUException):
    """COU exception when the highest possible OpenStack release is already achieved."""


class OutOfSupportRange(COUException):
    """COU exception when the release or series is out of the current supporting range."""


class NotSupported(COUException):
    """COU exception when upgrading a deployment is not supported."""


class WaitForApplicationsTimeout(COUException):
    """Waiting for applications hit timeout error."""


class DataPlaneCannotUpgrade(COUException):
    """COU exception when the cloud is inconsistent to generate a plan."""


class InterruptError(KeyboardInterrupt):
    """COU exception when upgrade was interrupted by signal."""

    def __init__(self, message: str, exit_code: int) -> None:
        """Set information about KeyboardInterrupt.

        :param message: error message
        :type message: str
        :param exit_code: Exit code
        :type exit_code: int
        """
        self.exit_code = exit_code
        super().__init__(message)
