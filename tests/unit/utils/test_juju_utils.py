# Copyright 2018 Canonical Ltd.
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
import asyncio
import os
from unittest.mock import MagicMock

import aiounittest
import mock
from mock.mock import AsyncMock

import cou.utils.juju_utils as model

FAKE_STATUS = {
    "can-upgrade-to": "",
    "charm": "local:trusty/app-136",
    "subordinate-to": [],
    "units": {
        "app/0": {
            "leader": True,
            "machine": "0",
            "agent-status": {"status": "idle"},
            "subordinates": {
                "app-hacluster/0": {
                    "charm": "local:trusty/hacluster-0",
                    "leader": True,
                    "agent-status": {"status": "idle"},
                }
            },
        },
        "app/1": {
            "machine": "1",
            "agent-status": {"status": "idle"},
            "subordinates": {
                "app-hacluster/1": {
                    "charm": "local:trusty/hacluster-0",
                    "agent-status": {"status": "idle"},
                }
            },
        },
        "app/2": {
            "machine": "2",
            "agent-status": {"status": "idle"},
            "subordinates": {
                "app-hacluster/2": {
                    "charm": "local:trusty/hacluster-0",
                    "agent-status": {"status": "idle"},
                }
            },
        },
    },
}

EXECUTING_STATUS = {
    "can-upgrade-to": "",
    "charm": "local:trusty/app-136",
    "subordinate-to": [],
    "units": {
        "app/0": {
            "leader": True,
            "machine": "0",
            "agent-status": {"status": "executing"},
            "subordinates": {
                "app-hacluster/0": {
                    "charm": "local:trusty/hacluster-0",
                    "leader": True,
                    "agent-status": {"status": "executing"},
                }
            },
        }
    },
}


class AsyncModelTests(aiounittest.AsyncTestCase):
    def patch_object(self, obj, attr, return_value=None, name=None, new=None, **kwargs):
        """Patch the given object."""
        if name is None:
            name = attr
        if new is not None:
            mocked = mock.patch.object(obj, attr, new=new, **kwargs)
        else:
            mocked = mock.patch.object(obj, attr, **kwargs)
        self._patches[name] = mocked
        started = mocked.start()
        if new is None:
            started.return_value = return_value
        self._patches_start[name] = started
        setattr(self, name, started)

    def patch(self, item, return_value=None, name=None, new=None, **kwargs):
        """Patch the given item."""
        if name is None:
            raise RuntimeError("Must pass 'name' to .patch()")
        if new is not None:
            mocked = mock.patch(item, new=new, **kwargs)
        else:
            mocked = mock.patch(item, **kwargs)
        self._patches[name] = mocked
        started = mocked.start()
        if new is None:
            started.return_value = return_value
        self._patches_start[name] = started
        setattr(self, name, started)

    def setUp(self):
        super().setUp()
        self._patches = {}
        self._patches_start = {}

        async def _scp_to(source, destination, user=None, proxy=None, scp_opts=None):
            return

        async def _scp_from(source, destination, user=None, proxy=None, scp_opts=None):
            return

        async def _run(command, timeout=None):
            return self.action

        async def _run_action(command, **params):
            return self.run_action

        async def _wait():
            return

        async def _add_relation(rel1, rel2):
            return

        async def _destroy_relation(rel1, rel2):
            return

        async def _add_unit(count=1, to=None):
            return

        async def _destroy_unit(*unitnames):
            return

        async def _scale(scale=None, scale_change=None):
            return

        def _is_leader(leader):
            async def _inner_is_leader():
                return leader

            return _inner_is_leader

        self.run_action = mock.MagicMock()
        self.run_action.wait.side_effect = _wait
        self.action = mock.MagicMock()
        self.action.data = {
            "model-uuid": "1a035018-71ff-473e-8aab-d1a8d6b6cda7",
            "id": "e26ffb69-6626-4e93-8840-07f7e041e99d",
            "receiver": "glance/0",
            "name": "juju-run",
            "parameters": {"command": "somecommand someargument", "timeout": 0},
            "status": "completed",
            "message": "",
            "results": {"Code": "0", "Stderr": "", "Stdout": "RESULT"},
            "enqueued": "2018-04-11T23:13:42Z",
            "started": "2018-04-11T23:13:42Z",
            "completed": "2018-04-11T23:13:43Z",
        }

        self.machine3 = mock.MagicMock(status="active")
        self.machine7 = mock.MagicMock(status="active")
        self.unit1 = mock.MagicMock()

        def make_get_public_address(ip):
            async def _get_public_address():
                return ip

            return _get_public_address

        def fail_on_use():
            raise RuntimeError("Don't use this property.")

        self.unit1.public_address = property(fail_on_use)
        self.unit1.get_public_address = make_get_public_address("ip1")
        self.unit1.name = "app/2"
        self.unit1.entity_id = "app/2"
        self.unit1.machine = self.machine3
        self.unit2 = mock.MagicMock()
        self.unit2.public_address = property(fail_on_use)
        self.unit2.get_public_address = make_get_public_address("ip2")
        self.unit2.name = "app/4"
        self.unit2.entity_id = "app/4"
        self.unit2.machine = self.machine7
        self.unit2.run.side_effect = _run
        self.unit1.run.side_effect = _run
        self.unit1.scp_to.side_effect = _scp_to
        self.unit2.scp_to.side_effect = _scp_to
        self.unit1.scp_from.side_effect = _scp_from
        self.unit2.scp_from.side_effect = _scp_from
        self.unit1.run_action.side_effect = _run_action
        self.unit2.run_action.side_effect = _run_action
        self.unit1.is_leader_from_status.side_effect = _is_leader(False)
        self.unit2.is_leader_from_status.side_effect = _is_leader(True)
        self.unit1.data = {"agent-status": {"current": "idle"}}
        self.unit2.data = {"agent-status": {"current": "idle"}}
        self.units = [self.unit1, self.unit2]
        self.relation1 = mock.MagicMock()
        self.relation1.id = 42
        self.relation1.matches.side_effect = lambda x: True if x == "app" else False
        self.relation2 = mock.MagicMock()
        self.relation2.id = 51
        self.relation2.matches.side_effect = lambda x: True if x == "app:interface" else False
        self.relations = [self.relation1, self.relation2]
        _units = mock.MagicMock()
        _units.units = self.units
        _units.relations = self.relations
        _units.add_relation.side_effect = _add_relation
        _units.destroy_relation.side_effect = _destroy_relation
        _units.add_unit.side_effect = _add_unit
        _units.destroy_unit.side_effect = _destroy_unit
        _units.scale.side_effect = _scale

        self.mymodel = mock.MagicMock()
        self.mymodel.applications = {"app": _units}
        self.Model_mock = mock.MagicMock()

        # Juju Status Object and data
        self.key = "instance-id"
        self.key_data = "machine-uuid"
        self.machine = "1"
        self.machine_data = {self.key: self.key_data}
        self.unit = "app/1"
        self.application = "app"
        self.subordinate_application = "subordinate_application"
        self.subordinate_application_data = {"subordinate-to": [self.application], "units": None}
        self.subordinate_unit = "subordinate_application/1"
        self.subordinate_unit_data = {"workload-status": {"status": "active"}}
        self.unit_data = {
            "workload-status": {"status": "active"},
            "machine": self.machine,
            "subordinates": {self.subordinate_unit: self.subordinate_unit_data},
        }
        self.application_data = {
            "units": {self.unit1.name: self.subordinate_unit_data, self.unit: self.unit_data}
        }
        self.juju_status = mock.MagicMock()
        self.juju_status.applications = {
            self.application: self.application_data,
            self.subordinate_application: self.subordinate_application_data,
        }
        self.juju_status.machines = self.machine_data

        async def _connect_model(model_name):
            return model_name

        async def _connect_current():
            pass

        async def _disconnect():
            return

        async def _connect(*args):
            return

        async def _ctrl_connect():
            return

        async def _ctrl_add_model(model_name, config=None):
            return

        async def _ctrl_destroy_models(model_name):
            return

        self.Model_mock.connect.side_effect = _connect
        self.Model_mock.connect_model.side_effect = _connect_model
        self.Model_mock.connect_current.side_effect = _connect_current
        self.Model_mock.disconnect.side_effect = _disconnect
        self.Model_mock.applications = self.mymodel.applications
        self.Model_mock.units = {"app/2": self.unit1, "app/4": self.unit2}
        self.model_name = "testmodel"
        self.Model_mock.info.name = self.model_name

        self.Controller_mock = mock.MagicMock()
        self.Controller_mock.connect.side_effect = _ctrl_connect
        self.Controller_mock.add_model.side_effect = _ctrl_add_model
        self.Controller_mock.destroy_models.side_effect = _ctrl_destroy_models

    def tearDown(self):
        # Clear cached model name
        model.CURRENT_MODEL = None
        super().tearDown()

    @mock.patch.dict(os.environ, {"MODEL_NAME": "model_name"}, clear=True)
    async def test_async_get_juju_model_juju_model(self):
        model.CURRENT_MODEL_NAME = None
        model_name = await model.async_set_current_model_name()
        assert model_name == "model_name"

    @mock.patch.dict(os.environ, {"JUJU_MODEL": "model_name"}, clear=True)
    async def test_async_get_juju_model_name(self):
        model.CURRENT_MODEL_NAME = None
        model_name = await model.async_set_current_model_name()
        assert model_name == "model_name"

    @mock.patch.dict(os.environ, {}, clear=True)
    async def test_async_get_juju_model_empty(self):
        with mock.patch(
            "cou.utils.juju_utils._async_get_current_model_name_from_juju"
        ) as get_model:
            get_model.return_value = "model_name"
            model.CURRENT_MODEL_NAME = None
            model_name = await model.async_set_current_model_name()
            assert model_name == "model_name"

    async def test_async_set_juju_model(self):
        model_name = await model.async_set_current_model_name(model_name="jujumodel")
        assert model_name == "jujumodel"

    async def test_get_model(self):
        with mock.patch("cou.utils.juju_utils.CURRENT_MODEL") as juju_model:
            current_model = await model._async_get_model()
            assert current_model == juju_model

    async def test_get_model_disconnected(self):
        with mock.patch("cou.utils.juju_utils.CURRENT_MODEL"), mock.patch(
            "cou.utils.juju_utils._is_model_disconnected"
        ) as is_disconnected, mock.patch("cou.utils.juju_utils._disconnect") as disconnect:
            await model._async_get_model()
            is_disconnected.assert_called()
            disconnect.assert_called()

    def test_is_model_disconnected(self):
        disconnected = model._is_model_disconnected(self.mymodel)
        assert not disconnected

    async def test_async_get_current_model(self):
        self.mymodel.name = "test"
        with mock.patch("cou.utils.juju_utils.Model") as init:
            init.return_value = self.Model_mock
            name = await model._async_get_current_model_name_from_juju()
            assert name == "testmodel"

    async def test_async_get_full_juju_status(self):
        with mock.patch("cou.utils.juju_utils._async_get_model") as get_model:
            mymodel = AsyncMock()
            get_model.return_value = mymodel
            mymodel.get_status = AsyncMock()
            mymodel.get_status.return_value = "test"
            result = await model.async_get_status()
            get_model.assert_called()
            mymodel.get_status.assert_called()
            assert result == "test"

    def test_normalise_action_results(self):
        results = {"Stderr": "error", "stdout": "output"}

        expected = {"Stderr": "error", "Stdout": "output", "stderr": "error", "stdout": "output"}

        normalized_results = model._normalise_action_results(results)

        self.assertEqual(normalized_results, expected)

    def test_normalise_action_results_empty_results(self):
        results = {}

        expected = {}

        normalized_results = model._normalise_action_results(results)

        self.assertEqual(normalized_results, expected)

    def test_async_run_on_unit(self):
        with mock.patch("cou.utils.juju_utils.async_set_current_model_name") as get_model:
            get_model.return_value = "mname"
            expected = {
                "Code": "0",
                "Stderr": "",
                "Stdout": "RESULT",
                "stderr": "",
                "stdout": "RESULT",
            }
            self.cmd = cmd = "somecommand someargument"
            self.patch_object(model, "Model")
            self.patch_object(model, "async_get_unit_from_name")
            self.async_get_unit_from_name.return_value = self.unit1
            self.Model.return_value = self.Model_mock
            result = asyncio.run(model.async_run_on_unit("app/2", cmd))
            self.assertEqual(result, expected)
            self.unit1.run.assert_called_once_with(cmd, timeout=None)

    async def test_async_get_unit_from_name(self):
        with mock.patch("cou.utils.juju_utils.async_set_current_model_name") as get_model:
            get_model.return_value = "mname"

            self.patch_object(model, "Model")
            self.Model.return_value = self.Model_mock
            # Normal case
            self.assertEqual(
                await model.async_get_unit_from_name("app/4", model_name="mname"), self.unit2
            )

            # Normal case with Model()
            self.assertEqual(
                await model.async_get_unit_from_name("app/4", self.mymodel), self.unit2
            )

            # Normal case, using default
            self.assertEqual(await model.async_get_unit_from_name("app/4"), self.unit2)

            # Unit does not exist
            with self.assertRaises(model.UnitNotFound):
                await model.async_get_unit_from_name("app/10", model_name="mname")

            # Application does not exist
            self.patch_object(model.logging, "error")
            with self.assertRaises(model.UnitNotFound):
                await model.async_get_unit_from_name("bad_name", model_name="mname")

    async def test_async_get_application_config(self):
        test_model = AsyncMock()
        test_app = AsyncMock()
        test_app.get_config = AsyncMock()
        test_app.get_config.return_value = "config"
        test_model.applications = {"app": test_app}

        with mock.patch("cou.utils.juju_utils._async_get_model") as juju_model:
            juju_model.return_value = test_model
            config = await model.async_get_application_config("app")
            assert config == "config"

    async def test_async_run_action_empty(self):
        with mock.patch("cou.utils.juju_utils.async_set_current_model_name") as get_model:
            get_model.return_value = "mname"
            self.patch_object(model, "Model")

            async def _fake_get_action_output(_):
                return {"fake": "output"}

            self.Model_mock.get_action_output = _fake_get_action_output
            self.Model.return_value = self.Model_mock
            self.run_action.status = "failed"
            self.run_action.message = "aMessage"
            self.run_action.id = "aId"
            self.run_action.enqueued = "aEnqueued"
            self.run_action.started = "aStarted"
            self.run_action.completed = "aCompleted"
            self.run_action.name = "backup2"
            self.run_action.parameters = None
            self.run_action.receiver = "app/2"
            with self.assertRaises(model.ActionFailed) as e:
                await model.async_run_action(
                    self.run_action.receiver,
                    self.run_action.name,
                    action_params=self.run_action.parameters,
                    raise_on_failure=True,
                )
            self.assertEqual(
                str(e.exception),
                (
                    'Run of action "backup2" with parameters "None" on "app/2" failed with '
                    '"aMessage" (id=aId status=failed enqueued=aEnqueued started=aStarted '
                    "completed=aCompleted output={'fake': 'output'})"
                ),
            )

    async def test_async_run_action_with_action_fails(self):
        with mock.patch("cou.utils.juju_utils.async_set_current_model_name") as get_model:
            get_model.return_value = "mname"
            self.patch_object(model, "Model")

            async def _fake_get_action_output(_):
                raise KeyError

            self.Model_mock.get_action_output = _fake_get_action_output
            self.Model.return_value = self.Model_mock
            self.run_action.status = "failed"
            self.run_action.message = "aMessage"
            self.run_action.id = "aId"
            self.run_action.enqueued = "aEnqueued"
            self.run_action.started = "aStarted"
            self.run_action.completed = "aCompleted"
            self.run_action.name = "backup2"
            self.run_action.parameters = None
            self.run_action.receiver = "app/2"
            with self.assertRaises(model.ActionFailed) as e:
                await model.async_run_action(
                    self.run_action.receiver,
                    self.run_action.name,
                    action_params=self.run_action.parameters,
                    raise_on_failure=True,
                )
            self.assertEqual(
                str(e.exception),
                (
                    'Run of action "backup2" with parameters "None" on "app/2" failed with '
                    '"aMessage" (id=aId status=failed enqueued=aEnqueued started=aStarted '
                    "completed=aCompleted output=None)"
                ),
            )

    async def test_async_run_action_with_action_not_fails(self):
        with mock.patch("cou.utils.juju_utils.async_set_current_model_name") as get_model:
            get_model.return_value = "mname"
            self.patch_object(model, "Model")

            async def _fake_get_action_output(_):
                raise KeyError

            self.Model_mock.get_action_output = _fake_get_action_output
            self.Model.return_value = self.Model_mock
            self.run_action.status = "failed"
            self.run_action.message = "aMessage"
            self.run_action.id = "aId"
            self.run_action.enqueued = "aEnqueued"
            self.run_action.started = "aStarted"
            self.run_action.completed = "aCompleted"
            self.run_action.name = "backup2"
            self.run_action.parameters = None
            self.run_action.receiver = "app/2"
            await model.async_run_action(
                self.run_action.receiver,
                self.run_action.name,
                action_params=self.run_action.parameters,
                raise_on_failure=False,
            )

    async def test_async_scp_from_unit(self):
        with mock.patch("cou.utils.juju_utils.async_set_current_model_name") as get_model:
            get_model.return_value = "mname"
            self.patch_object(model, "Model")
            self.patch_object(model, "async_get_unit_from_name")
            self.async_get_unit_from_name.return_value = self.unit1
            self.Model.return_value = self.Model_mock
            await model.async_scp_from_unit("app/2", "/tmp/src", "/tmp/dest")
            self.unit1.scp_from.assert_called_once_with(
                "/tmp/src", "/tmp/dest", proxy=False, scp_opts="", user="ubuntu"
            )

    async def test_async_upgrade_charm(self):
        async def _upgrade_charm(
            channel=None,
            force_series=False,
            force_units=False,
            path=None,
            resources=None,
            revision=None,
            switch=None,
            model_name=None,
        ):
            return

        with mock.patch("cou.utils.juju_utils.async_set_current_model_name") as get_model:
            get_model.return_value = "mname"
            self.patch_object(model, "Model")
            self.patch_object(model, "async_get_unit_from_name")
            self.async_get_unit_from_name.return_value = self.unit1
            self.Model.return_value = self.Model_mock
            app_mock = mock.MagicMock()
            app_mock.upgrade_charm.side_effect = _upgrade_charm
            self.mymodel.applications["myapp"] = app_mock
            await model.async_upgrade_charm("myapp", switch="cs:~me/new-charm-45")
            app_mock.upgrade_charm.assert_called_once_with(
                channel=None,
                force_series=False,
                force_units=False,
                path=None,
                resources=None,
                revision=None,
                switch="cs:~me/new-charm-45",
            )

    async def test_disconnect(self):
        mymodel = MagicMock()
        mymodel.disconnect.return_value = "ok"
        await model._disconnect(mymodel)
