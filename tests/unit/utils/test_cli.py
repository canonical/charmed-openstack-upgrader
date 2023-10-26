#  Copyright 2023 Canonical Limited
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest

from cou.utils.cli import _cancel_plan, keyboard_interrupt_handler


@pytest.mark.asyncio
@patch("cou.utils.cli.asyncio.sleep")
async def test_cancel_plan(mock_sleep, mocker):
    """Test behavior of watcher for canceling the plan."""
    exp_msg = "charmed-openstack-upgrader has been stopped cleanly"
    indicator = mocker.patch("halo.Halo")()
    plan = mocker.patch("cou.steps.UpgradeStep")()
    type(plan).all_done = PropertyMock(side_effect=[False, False, False, True])

    with pytest.raises(KeyboardInterrupt, match=exp_msg):
        await _cancel_plan(plan, indicator)

    indicator.clear.assert_called_once_with()
    indicator.start.assert_called_once_with(
        "Canceling upgrade... (Press ctrl+c again to stop immediately)"
    )
    mock_sleep.assert_has_calls([call(0.2), call(0.2), call(0.2)])
    assert mock_sleep.call_count == 3
    indicator.succeed.assert_called_once_with()
    plan.cancel.assert_called_once_with(safe=True)


@patch("cou.utils.cli._cancel_plan", new_callable=MagicMock)
def test_keyboard_interrupt_handler_safe(mock_cancel_plan, mocker):
    """Test handler to do safe canceling."""
    loop = MagicMock()
    indicator = mocker.patch("halo.Halo")()
    plan = mocker.patch("cou.steps.UpgradeStep")()
    plan.canceled = False

    keyboard_interrupt_handler(plan, loop, indicator)

    loop.create_task.assert_called_once_with(mock_cancel_plan.return_value)
    mock_cancel_plan.assert_called_once_with(plan, indicator)


def test_keyboard_interrupt_handler_unsafe(mocker):
    """Test handler to do unsafe canceling."""
    exp_msg = "charmed-openstack-upgrade has been terminated without waiting"
    loop = MagicMock()
    indicator = mocker.patch("halo.Halo")()
    plan = mocker.patch("cou.steps.UpgradeStep")()
    plan.canceled = True

    with pytest.raises(KeyboardInterrupt, match=exp_msg):
        keyboard_interrupt_handler(plan, loop, indicator)

    plan.cancel.assert_called_once_with(safe=False)
    indicator.fail.assert_called_once_with()
