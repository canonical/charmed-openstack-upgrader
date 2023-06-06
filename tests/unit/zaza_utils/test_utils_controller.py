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

import unittest

import mock

import cou.zaza_utils.controller as controller
from cou.zaza_utils import clean_up_libjuju_thread
from tests.unit.utils import BaseTestCase


def tearDownModule():
    clean_up_libjuju_thread()


class TestController(BaseTestCase):
    def setUp(self):
        super(TestController, self).setUp()

        async def _disconnect():
            return

        async def _connect():
            return

        async def _list_models():
            return self.models

        async def _add_model(model_name, config=None):
            return self.model1

        async def _destroy_model(model_name, destroy_storage=False, force=False, max_wait=None):
            if model_name in self.models:
                self.models.remove(model_name)
            return

        async def _get_cloud():
            return self.cloud

        # Cloud
        self.cloud = "FakeCloud"

        # Model
        self.Model_mock = mock.MagicMock()
        self.Model_mock.connect.side_effect = _connect
        self.Model_mock.disconnect.side_effect = _disconnect
        self.Model_mock.disconnect.side_effect = _disconnect
        self.model1 = self.Model_mock
        self.model2 = mock.MagicMock()
        self.model1.info.name = "model1"
        self.model2.info.name = "model2"
        self.models = [self.model1.info.name, self.model2.info.name]

        # Controller
        self.Controller_mock = mock.MagicMock()
        self.Controller_mock.connect.side_effect = _connect
        self.Controller_mock.disconnect.side_effect = _disconnect
        self.Controller_mock.add_model.side_effect = _add_model
        self.Controller_mock.destroy_model.side_effect = _destroy_model
        self.Controller_mock.list_models.side_effect = _list_models
        self.Controller_mock.get_cloud.side_effect = _get_cloud
        self.controller_name = "testcontroller"
        self.Controller_mock.info.name = self.controller_name
        self.patch_object(controller, "Controller")
        self.Controller.return_value = self.Controller_mock

    @unittest.skip("Skipping unti libjuju issue 333 is resolved")
    def test_add_model(self):
        controller.add_model(self.model1.info.name)
        self.Controller_mock.add_model.assert_called_once_with(self.model1.info.name, config=None)

    @unittest.skip("Skipping unti libjuju issue 333 is resolved")
    def test_add_model_config(self):
        controller.add_model(self.model1.info.name, {"run-faster": "true"})
        self.Controller_mock.add_model.assert_called_once_with(
            self.model1.info.name, config={"run-faster": "true"}
        )

    def test_destroy_model(self):
        controller.destroy_model(self.model1.info.name)
        self.Controller_mock.destroy_model.assert_called_once_with(
            self.model1.info.name, destroy_storage=True, force=True, max_wait=600
        )

    def test_get_cloud(self):
        self.assertEqual(controller.get_cloud(), self.cloud)
        self.Controller_mock.get_cloud.assert_called_once()

    def test_list_models(self):
        self.assertEqual(controller.list_models(), self.models)
        self.Controller_mock.list_models.assert_called_once()

    def test_go_list_models(self):
        self.patch_object(controller, "subprocess")
        controller.go_list_models()
        self.subprocess.check_call.assert_called_once_with(["juju", "models"])
