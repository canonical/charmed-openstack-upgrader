import logging
from dataclasses import dataclass

from cou.steps import UpgradeStep
from cou.steps.analyze import Application
from cou.utils.juju_utils import async_set_application_config, async_upgrade_charm


@dataclass
class BasicCharmUpgradePlan:
    app: Application
    current_os_release: str
    next_os_release: str

    def add_plan_refresh_current_channel(self, plan):
        if self.app.charm_origin == "cs":
            plan = self._add_plan_charmhub_migration(plan)
            return plan
        plan = self._add_plan_change_current_channel(plan)
        plan = self._add_plan_update_current_channel(plan)
        return plan

    def add_plan_refresh_next_channel(self, plan):
        if self.app.channel != self.next_channel:
            plan.add_step(
                UpgradeStep(
                    description=f"Refresh {self.app.name} to the new channel: '{self.next_channel}'",
                    parallel=plan.parallel,
                    function=async_upgrade_charm,
                    application_name=self.app.name,
                    channel=self.next_channel,
                    model_name=self.app.model_name,
                )
            )
        return plan

    def _add_plan_charmhub_migration(self, plan):
        plan.add_step(
            UpgradeStep(
                description=f"App: {self.app.name} -> Migration from charmstore to charmhub",
                parallel=plan.parallel,
                function=async_upgrade_charm,
                application_name=self.app.name,
                channel=self.current_channel,
                model_name=self.app.model_name,
                switch=f"ch:{self.app.charm}",
            )
        )
        return plan

    def _add_plan_change_current_channel(self, plan):
        if self.app.channel != self.current_channel and self.app.channel != self.next_channel:
            plan.add_step(
                UpgradeStep(
                    description=f"Changing {self.app.name} channel from: {self.app.channel} to: {self.current_channel}",
                    parallel=plan.parallel,
                    function=async_upgrade_charm,
                    application_name=self.app.name,
                    channel=self.current_channel,
                )
            )
        return plan

    def _add_plan_update_current_channel(self, plan):
        if self.app.channel == self.next_channel:
            logging.warning(
                "App: %s already has the channel set for the next OpenStack version %s",
                self.app.name,
                self.next_os_release,
            )
        else:
            plan.add_step(
                UpgradeStep(
                    description=f"Refresh {self.app.name} to the latest revision of {self.current_channel}",
                    parallel=plan.parallel,
                    function=async_upgrade_charm,
                    application_name=self.app.name,
                )
            )
        return plan

    def add_plan_disable_action_managed(self, plan):
        if self.app.action_managed_upgrade_support:
            if self.app.config["action-managed-upgrade"].get("value", False):
                plan.add_step(
                    UpgradeStep(
                        description=f"App: '{self.app.name}' -> Set action-managed-upgrade to False.",
                        parallel=plan.parallel,
                        function=async_set_application_config,
                        application_name=self.app.name,
                        configuration={"action-managed-upgrade": False},
                    )
                )
        return plan

    def add_plan_payload_upgrade(self, plan):
        if self.app.os_origin != self.new_origin:
            plan.add_step(
                UpgradeStep(
                    description=f"App: '{self.app.name}' -> Change charm config '{self.app.origin_setting}' to '{self.new_origin}'",
                    parallel=plan.parallel,
                    function=async_set_application_config,
                    application_name=self.app.name,
                    configuration={self.app.origin_setting: self.new_origin},
                )
            )
        else:
            logging.warning(
                "App: %s already have %s set to %s",
                self.app.name,
                self.app.origin_setting,
                self.new_origin,
            )
        return plan

    @property
    def current_channel(self):
        return f"{self.current_os_release}/stable"

    @property
    def next_channel(self):
        return f"{self.next_os_release}/stable"

    @property
    def new_origin(self):
        return f"cloud:focal-{self.next_os_release}"
