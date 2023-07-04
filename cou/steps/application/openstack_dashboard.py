import logging
import re

from cou.steps.application.app import Application


class OpenStack_Dashboard(Application):
    """OpenStack Dashboard application."""

    openstack_map = {"18.3": "ussuri", "18.6": "victoria", "19.4": "wallaby"}

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
            version = self.get_os_code_info_dashboard(pkg_version)
        return version

    def get_os_code_info_dashboard(self, pkg_version):
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
