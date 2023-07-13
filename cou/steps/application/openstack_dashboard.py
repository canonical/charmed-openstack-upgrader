import logging
import re

from cou.steps.application.app import Application
from cou.utils.openstack import get_os_code_info


@Application.register_subclass("openstack-dashboard")
class OpenStack_Dashboard(Application):
    """OpenStack Dashboard application."""

    openstack_map = {"18.3": "ussuri", "18.6": "victoria", "19.4": "wallaby"}

    def _get_current_os_version(self, workload_version: str) -> str:
        """Get the openstack version of a unit.

        :param workload_version: Version of the workload of a charm. E.g: 10.2.6
        :type workload_version: str
        :return: OpenStack version detected. If not detected return an empty string.
            E.g: ussuri.
        :rtype: str
        """
        version = ""
        package = self._get_representative_workload_pkg()

        if package and workload_version:
            version = self.get_os_code_info_dashboard(workload_version)
        return version

    def get_os_code_info_dashboard(self, workload_version):
        # NOTE(gabrielcocenza) use packaging instead of regex
        try:
            # Remove epoch if it exists
            if ":" in pkg_version:
                pkg_version = pkg_version.split(":")[1:][0]
            match = re.match(r"^(\d+)\.(\d+)", pkg_version)
            vers = match.group(0)
            os_release = self.openstack_map[vers]
            return os_release
        except KeyError:
            logging.error(
                "It was not possible determine the Openstack release for '%s'", self.name
            )
