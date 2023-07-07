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

from cou.utils.juju_utils import async_upgrade_charm


async def charm_upgrade(application_name: str) -> None:
    """Upgrade a charm to the latest revision in the current channel.

    :param application_name: Name of the Application. E.g: "keystone".
    :type application_name: str
    """
    logging.info("Upgrading %s to the latest revision in the current channel", application_name)
    await async_upgrade_charm(application_name)


async def charm_channel_refresh(application_name: str, channel: str) -> None:
    """Refresh a charm to track a target channel.

    :param application_name:  Name of the Application. E.g: keystone.
    :type application_name: str
    :param channel: Channel that the application tracks. E.g: "ussuri/stable"
    :type channel: str
    """
    logging.info("Refresh %s to the %s channel", application_name, channel)
    await async_upgrade_charm(application_name, channel=channel)
