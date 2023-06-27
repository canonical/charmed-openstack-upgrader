# mypy: disable-error-code="no-untyped-def"
# Copyright 2018 Canonical Ltd.
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


class CommandRunFailed(Exception):
    """Command failed to run."""

    def __init__(self, cmd, result):
        """Create Command run failed exception.

        :param cmd: Command that was run
        :type cmd: string
        :param result: Dict containing the output of the command
        :type result: dict - {'Code': '0', 'Stdout': '', 'Stderr':''}
        """
        code = result.get("Code")
        output = result.get("Stdout")
        err = result.get("Stderr")
        msg = f"Command {cmd} failed with code {code}, output {output} and error {err}"
        super().__init__(msg)


class UnitNotFound(Exception):
    """Unit not found in actual dict."""


class JujuError(Exception):
    """Exception when libjuju does something unexpected."""


class ActionFailed(Exception):
    # pylint: disable=consider-using-f-string
    """Exception raised when action fails."""

    def __init__(self, action, output=None):
        """Set information about action failure in message and raise."""
        # Bug: #314  -- unfortunately, libjuju goes bang even if getattr(x,y,
        # default) is used, which means we physically have to check for
        # KeyError.
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
            try:
                params[key] = getattr(action, key, "<not-set>")
            except KeyError:
                # code around libjuju in its getattr code.
                params[key] = "<not-set>"

        message = (
            'Run of action "{name}" with parameters "{parameters}" on '
            '"{receiver}" failed with "{message}" (id={id} '
            "status={status} enqueued={enqueued} started={started} "
            "completed={completed} output={output})".format(**params)
        )
        super().__init__(message)


class InvalidCharmNameError(Exception):
    """Represents an invalid charm name being processed."""
