from cou.steps.upgrade.basic import BasicCharmUpgradePlan


class CephUpgradePlan(BasicCharmUpgradePlan):
    """Ceph upgrade plan."""

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
