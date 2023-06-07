# Copyright 2023 Canonical Limited.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Charm operation utilities."""
import logging
from cou.zaza_utils.model import upgrade_charm, block_until_all_units_idle


def charm_upgrade(application_name: str) -> None:
    """Upgrade a charm to the latest revision in the current channel."""
    logging.info(
        "Upgrading %s to the latest revision in the current channel",
        application_name
    )
    upgrade_charm(application_name)
    block_until_all_units_idle()


def charm_channel_refresh(application_name: str, target_channel: str) -> None:
    """Refresh a charm to track a target channel."""
    logging.info(
        "Refresh %s to the %s channel",
        application_name, target_channel
    )
    upgrade_charm(application_name, target_channel)
    block_until_all_units_idle()
