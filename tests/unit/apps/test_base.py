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

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from cou.apps.base import OpenStackApplication
from cou.exceptions import ApplicationError, HaltUpgradePlanGeneration
from cou.utils.openstack import OpenStackRelease


@pytest.mark.parametrize("config", ({}, {"enable-auto-restarts": {"value": True}}))
@patch("cou.apps.base.OpenStackApplication.channel", new_callable=PropertyMock)
def test_check_auto_restarts(_, config):
    """Test function to verify that enable-auto-restarts is disabled."""
    app_name = "app"
    app = OpenStackApplication(app_name, MagicMock(), config, MagicMock(), "", "ch", "")

    app._check_auto_restarts()


@patch("cou.apps.base.OpenStackApplication.channel", new_callable=PropertyMock)
def test_check_auto_restarts_error(_):
    """Test function to verify that enable-auto-restarts is disabled raising error."""
    app_name = "app"
    exp_error_msg = (
        "COU does not currently support upgrading applications that disable service restarts. "
        f"Please enable charm option enable-auto-restart and rerun COU to upgrade the {app_name} "
        "application."
    )
    config = {"enable-auto-restarts": {"value": False}}
    app = OpenStackApplication(app_name, MagicMock(), config, MagicMock(), "", "ch", "")

    with pytest.raises(ApplicationError, match=exp_error_msg):
        app._check_auto_restarts()


@patch("cou.apps.base.OpenStackApplication.channel", new_callable=PropertyMock)
@patch("cou.apps.base.OpenStackApplication.apt_source_codename", new_callable=PropertyMock)
@patch("cou.apps.base.OpenStackApplication.current_os_release", new_callable=PropertyMock)
def test_check_application_target(current_os_release, apt_source_codename, _):
    """Test function to verify target."""
    target = OpenStackRelease("victoria")
    release = OpenStackRelease("ussuri")
    app_name = "app"
    app = OpenStackApplication(app_name, MagicMock(), {}, MagicMock(), "", "ch", "")
    current_os_release.return_value = apt_source_codename.return_value = release

    app._check_application_target(target)


@patch("cou.apps.base.OpenStackApplication.channel", new_callable=PropertyMock)
@patch("cou.apps.base.OpenStackApplication.apt_source_codename", new_callable=PropertyMock)
@patch("cou.apps.base.OpenStackApplication.current_os_release", new_callable=PropertyMock)
def test_check_application_target_error(current_os_release, apt_source_codename, _):
    """Test function to verify target raising error."""
    target = OpenStackRelease("victoria")
    app_name = "app"
    exp_error_msg = (
        f"Application '{app_name}' already configured for release equal to or greater than "
        f"{target}. Ignoring."
    )
    app = OpenStackApplication(app_name, MagicMock(), {}, MagicMock(), "", "ch", "")
    current_os_release.return_value = apt_source_codename.return_value = target

    with pytest.raises(HaltUpgradePlanGeneration, match=exp_error_msg):
        app._check_application_target(target)
