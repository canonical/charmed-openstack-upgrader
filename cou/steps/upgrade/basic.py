import logging
from dataclasses import dataclass
from cou.steps import UpgradeStep
from cou.steps.analyze import Application
from cou.utils.juju_utils import (
    async_block_until_all_units_idle,
    async_set_application_config,
    async_upgrade_charm,
)

def wait_for_idle():
    return UpgradeStep(
        description="wait for idle",
        parallel=False,
        function=async_block_until_all_units_idle,
    )

@dataclass
class BasicCharmUpgradePlan:
    app: Application
    current_os_release: str
    next_os_release: str

    def generate_plan(self):
        self.plan = UpgradeStep(
            description=f"Upgrade {self.app.name}", parallel=False, function=None
        )
        self.refresh_current_channel()
        self.refresh_next_channel()
        self.upgrade_plan()
        return self.plan

    def refresh_current_channel(self):
        if self.app.charm_origin == "cs":
            self.plan.add_step(
                UpgradeStep(
                    description="Migration from charmstore to charmhub",
                    parallel=False,
                    function=async_upgrade_charm,
                    application_name=self.app.name,
                    channel=self.current_channel,
                    model_name=self.app.model_name,
                    switch=f"ch:{self.app.charm}",
                )
            )
            self.plan.add_step(wait_for_idle())
        elif self.app.channel != self.current_channel and self.app.channel != self.next_channel:
            self.plan.add_step(
                UpgradeStep(
                    description=f"Changing channel from: {self.app.channel} to: {self.current_channel}",
                    parallel=False,
                    function=async_upgrade_charm,
                    application_name=self.app.name,
                    channel=self.current_channel,
                )
            )
            self.plan.add_step(wait_for_idle())
        elif self.app.channel == self.next_channel:
            logging.warning(
                "App: %s already has the channel set for the next OpenStack version %s",
                self.app.name,
                self.next_os_release,
            )
        else:
            self.plan.add_step(
                UpgradeStep(
                    description=f"Refresh to the latest revision of {self.current_channel}",
                    parallel=False,
                    function=async_upgrade_charm,
                    application_name=self.app.name,
                )
            )
            self.plan.add_step(wait_for_idle())

    def refresh_next_channel(self):
        if self.app.channel != self.next_channel:
            self.plan.add_step(
                UpgradeStep(
                    description=f"Refresh to the new channel: '{self.next_channel}'",
                    parallel=False,
                    function=async_upgrade_charm,
                    application_name=self.app.name,
                    channel=self.next_channel,
                    model_name=self.app.model_name,
                )
            )
            self.plan.add_step(wait_for_idle())

    def upgrade_plan(self):
        if self.app.action_managed_upgrade_support:
            if self.app.config["action-managed-upgrade"].get("value", False):
                self.plan.add_step(
                    UpgradeStep(
                        description="Set action-managed-upgrade to False (all-in-one)",
                        parallel=False,
                        function=async_set_application_config,
                        application_name=self.app.name,
                        configuration={"action-managed-upgrade": False},
                    )
                )
                self.plan.add_step(wait_for_idle())
        if self.app.os_origin != self.new_origin:
            self.plan.add_step(
                UpgradeStep(
                    description=f"Change charm config '{self.app.origin_setting}' to '{self.new_origin}'",
                    parallel=False,
                    function=async_set_application_config,
                    application_name=self.app.name,
                    configuration={self.app.origin_setting: self.new_origin},
                )
            )
            self.plan.add_step(wait_for_idle())
        else:
            logging.warning(
                "App: %s already have %s set to %s",
                self.app.name,
                self.app.origin_setting,
                self.new_origin,
            )

    @property
    def current_channel(self):
        return f"{self.current_os_release}/stable"

    @property
    def next_channel(self):
        return f"{self.next_os_release}/stable"

    @property
    def new_origin(self):
        return f"cloud:focal-{self.next_os_release}"
