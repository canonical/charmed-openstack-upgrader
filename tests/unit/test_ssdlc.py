# Copyright 2023 Canonical Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for SSDLC logging module."""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from cou.ssdlc import SSDLCSysEvent, log_ssdlc_system_event


@pytest.mark.parametrize(
    "event,expected_msg",
    [
        (SSDLCSysEvent.STARTUP, "charmed-openstack-upgrader start"),
        (SSDLCSysEvent.SHUTDOWN, "charmed-openstack-upgrader shutdown"),
        (SSDLCSysEvent.CRASH, "charmed-openstack-upgrader crash"),
    ],
)
def test_log_ssdlc_system_event(event, expected_msg):
    """Test logging SSDLC system events."""
    with patch("cou.ssdlc.logger") as mock_logger:
        with patch("cou.ssdlc.datetime") as mock_datetime:
            # Mock datetime
            fixed_time = datetime(2023, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = fixed_time
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            log_ssdlc_system_event(event)

            # Verify logger.warning was called once
            mock_logger.warning.assert_called_once()

            # Get the call arguments
            call_args = mock_logger.warning.call_args[0][0]

            # Verify the structure of the logged message
            assert call_args["appid"] == "cou"
            assert call_args["event"] == event.value
            assert call_args["level"] == "WARN"
            assert call_args["description"] == expected_msg
            assert "datetime" in call_args


def test_log_ssdlc_system_event_with_message():
    """Test logging SSDLC system events with additional message."""
    with patch("cou.ssdlc.logger") as mock_logger:
        with patch("cou.ssdlc.datetime") as mock_datetime:
            # Mock datetime
            fixed_time = datetime(2023, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = fixed_time
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            additional_msg = "test error message"
            log_ssdlc_system_event(SSDLCSysEvent.CRASH, msg=additional_msg)

            # Verify logger.warning was called once
            mock_logger.warning.assert_called_once()

            # Get the call arguments
            call_args = mock_logger.warning.call_args[0][0]

            # Verify the description includes the additional message
            assert call_args["description"] == f"charmed-openstack-upgrader crash {additional_msg}"


def test_ssdlc_event_enum_values():
    """Test SSDLC event enum values."""
    assert SSDLCSysEvent.STARTUP.value == "sys_startup"
    assert SSDLCSysEvent.SHUTDOWN.value == "sys_shutdown"
    assert SSDLCSysEvent.CRASH.value == "sys_crash"


def test_log_ssdlc_system_event_datetime_format():
    """Test that datetime is properly formatted in ISO format."""
    with patch("cou.ssdlc.logger") as mock_logger:
        log_ssdlc_system_event(SSDLCSysEvent.STARTUP)

        # Get the call arguments
        call_args = mock_logger.warning.call_args[0][0]

        # Verify datetime is in ISO format (should contain 'T' separator)
        assert "T" in call_args["datetime"]
        # Verify it's parseable as ISO format
        datetime.fromisoformat(call_args["datetime"])
