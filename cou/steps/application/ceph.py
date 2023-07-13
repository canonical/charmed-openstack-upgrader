import logging

from cou.steps.application.app import Application
from cou.utils.openstack import get_os_code_info


@Application.register_subclass("ceph-mon")
class Ceph(Application):
    workload_map = {"15": ["ussuri", "victoria"], "16": ["wallaby", "xena"], "17": ["yoga"]}
    # NOTE (gabrielcocenza)
    # https://docs.openstack.org/charm-guide/latest/project/charm-delivery.html
    openstack_map = {
        "ussuri": "octopus",
        "victoria": "octopus",
        "wallaby": "pacific",
        "xena": "pacific",
        "yoga": "quincy",
    }

    @property
    def current_channel(self):
        return f"{self.openstack_map[self.current_os_release]}/stable"

    @property
    def next_channel(self):
        return f"{self.openstack_map[self.next_os_release]}/stable"

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
            version = self.get_os_code_info_ceph(workload_version)
        return version

    def get_os_code_info_ceph(self, workload_version):
        try:
            os_release = ""
            major_version = workload_version.split(".")[0]
            possible_os_releases = self.workload_map[major_version]
            for possible_os_release in possible_os_releases:
                if possible_os_release in self.os_origin:
                    os_release = possible_os_release
            if not os_release:
                logging.error(
                    "It was not possible determine the Openstack release for '%s'", self.name
                )
            return os_release
        except KeyError:
            logging.error(
                "It was not possible determine the Openstack release for '%s'", self.name
            )
