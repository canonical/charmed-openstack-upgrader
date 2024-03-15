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

"""Core application class."""
import logging

from cou.apps.base import LONG_IDLE_TIMEOUT, OpenStackApplication
from cou.apps.factory import AppFactory

logger = logging.getLogger(__name__)


@AppFactory.register_application(["keystone"])
class Keystone(OpenStackApplication):
    """Keystone application.

    Keystone must wait for the entire model to be idle before declaring the upgrade complete.
    """

    wait_timeout = LONG_IDLE_TIMEOUT
    wait_for_model = True


@AppFactory.register_application(["octavia"])
class Octavia(OpenStackApplication):
    """Octavia application.

    Octavia required more time to settle before COU can continue.
    """

    wait_timeout = LONG_IDLE_TIMEOUT
