import logging

from cou.steps.application.app import Application


class Ceph(Application):
    """Ceph Application."""

    openstack_map = {"15": {"ussuri", "victoria"}, "16": {"wallaby", "xena"}, "17": {"yoga"}}

    async def _get_current_os_versions(self, unit: str) -> str:
        """Get the openstack version of a unit."""
        version = ""
        pkg_version = self._get_pkg_version(unit)
        self.units[unit]["pkg_version"] = pkg_version
        self.pkg_version_units[pkg_version].add(unit)

        # for openstack releases >= wallaby
        codename = await self._get_openstack_release(unit, model_name=self.model_name)
        if codename:
            version = codename
        # for openstack releases < wallaby
        elif self.pkg_name and pkg_version:
            version = self.get_os_code_info_ceph(pkg_version)
        return version

    def get_os_code_info_ceph(self, pkg_version):
        try:
            os_release = ""
            major_version = pkg_version.split(".")[0]
            possible_os_releases = self.openstack_map[major_version]
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
