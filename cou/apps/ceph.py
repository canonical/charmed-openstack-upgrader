import logging

from cou.steps.application.app import StandardApplication
from cou.steps.application.factory import AppFactory
from cou.utils.openstack import CHARM_TYPES


@AppFactory.register_application(CHARM_TYPES["ceph"])
class Ceph(StandardApplication):
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
