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

"""Module of exceptions that zaza may raise."""


class JujuError(Exception):
    """Exception when libjuju does something unexpected."""

    pass


class TemplateConflict(Exception):
    """Exception when templates are in conflict."""

    pass


class MachineNotFound(Exception):
    """Exception when machine is not found."""

    pass


class MissingOSAthenticationException(Exception):
    """Exception when some data needed to authenticate is missing."""

    pass


class CloudInitIncomplete(Exception):
    """Cloud init has not completed properly."""

    pass


class SSHFailed(Exception):
    """SSH failed."""

    pass


class NeutronAgentMissing(Exception):
    """Agent binary does not appear in the Neutron agent list."""

    pass


class NeutronBGPSpeakerMissing(Exception):
    """No BGP speaker appeared on agent."""

    pass


class ApplicationNotFound(Exception):
    """Application not found in machines."""

    def __init__(self, application):
        """Create Application not found exception.

        :param application: Name of the application
        :type application: string
        :returns: ApplicationNotFound Exception
        """
        msg = "{} application was not found in machines.".format(application)
        super(ApplicationNotFound, self).__init__(msg)


class SeriesNotFound(Exception):
    """Series not found in status."""

    pass


class OSVersionNotFound(Exception):
    """OS Version not found."""

    pass


class ReleasePairNotFound(Exception):
    """Release pair was not found in OPENSTACK_RELEASES_PAIRS."""

    pass


class KeystoneAuthorizationStrict(Exception):
    """Authorization/Policy too strict."""

    pass


class KeystoneAuthorizationPermissive(Exception):
    """Authorization/Policy too permissive."""

    pass


class KeystoneWrongTokenProvider(Exception):
    """A token was issued from the wrong token provider."""

    pass


class KeystoneKeyRepositoryError(Exception):
    """Error in key repository.

    This may be caused by isues with one of:
    - incomplete or missing data in `key_repository` in leader storage
    - synchronization of keys to non-leader units
    - rotation of keys
    """

    pass


class ProcessNameCountMismatch(Exception):
    """Count of process names doesn't match."""

    pass


class ProcessNameMismatch(Exception):
    """Name of processes doesn't match."""

    pass


class PIDCountMismatch(Exception):
    """PID's count doesn't match."""

    pass


class ProcessIdsFailed(Exception):
    """Process ID lookup failed."""

    pass


class UnitNotFound(Exception):
    """Unit not found in actual dict."""

    pass


class UnitCountMismatch(Exception):
    """Count of unit doesn't match."""

    pass


class UbuntuReleaseNotFound(Exception):
    """Ubuntu release not found in list."""

    pass


class ServiceNotFound(Exception):
    """Service not found on unit."""

    pass


class CephPoolNotFound(Exception):
    """Ceph pool not found."""

    pass


class NovaGuestMigrationFailed(Exception):
    """Nova guest migration failed."""

    pass


class NovaGuestRestartFailed(Exception):
    """Nova guest restart failed."""

    pass


class DestroyModelFailed(Exception):
    """The controller.destroy_model() failed in some interesting way."""

    pass
