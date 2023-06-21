import unittest
from unittest.mock import patch

import pytest

from cou.steps.charm_operation import charm_channel_refresh, charm_upgrade


class StepsCharmOperationTestCase(unittest.TestCase):
    @pytest.mark.asyncio
    async def test_charm_upgrade(self):
        application_name = "example_charm"
        with patch("cou.steps.charm_operation.upgrade_charm") as mock_upgrade, patch(
            "cou.steps.charm_operation.logging.info"
        ):
            await charm_upgrade(application_name)
            mock_upgrade.assert_called_once_with(application_name)

    @pytest.mark.asyncio
    async def test_charm_channel_refresh(log):
        application_name = "example_charm"
        target_channel = "exampe/stable"
        with patch("cou.steps.charm_operation.upgrade_charm") as mock_upgrade, patch(
            "cou.steps.charm_operation.logging.info"
        ):
            await charm_channel_refresh(application_name, target_channel)
            mock_upgrade.assert_called_once_with(application_name, channel=target_channel)
