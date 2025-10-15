# Copyright 2025 Canonical Limited
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

"""SSDLC (Secure Software Development Lifecycle) Logging.

These events provide critical visibility into the asset's lifecycle and health, and can help
detect potential tampering or malicious activities aimed at altering system behavior.

Logging these events allows for the identification of unauthorized changes to system states,
such as unapproved restarts or unexpected shutdowns, which may indicate security incidents
or availability attacks, or changes to security settings.
"""
from datetime import datetime, timezone
from enum import Enum
from logging import getLogger

logger = getLogger(__name__)


class SSDLCSysEvent(str, Enum):  # noqa: N801
    """Constant event defined in SSDLC."""

    STARTUP = "sys_startup"
    SHUTDOWN = "sys_shutdown"
    CRASH = "sys_crash"


_EVENT_MESSAGE_MAPS = {
    SSDLCSysEvent.STARTUP: "charmed-openstack-upgrader start",
    SSDLCSysEvent.SHUTDOWN: "charmed-openstack-upgrader shutdown",
    SSDLCSysEvent.CRASH: "charmed-openstack-upgrader crash",
}


def log_ssdlc_system_event(event: SSDLCSysEvent, msg: str = "") -> None:
    """Log system lifecycle event in SSDLC required format.

    Args:
        event: The SSDLC system event type
        msg: Optional additional message
    """
    event_msg = _EVENT_MESSAGE_MAPS[event]

    now = datetime.now(timezone.utc).astimezone()
    logger.warning(
        {
            "datetime": now.isoformat(),
            "appid": "cou",
            "event": event.value,
            "level": "WARN",
            "description": f"{event_msg} {msg}".strip(),
        },
    )
