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
import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from juju.action import Action
from juju.application import Application
from juju.client.connector import NoConnectionException
from juju.model import Model
from juju.unit import Unit

from cou.exceptions import (
    ActionFailed,
    ApplicationError,
    ApplicationNotFound,
    TimeoutException,
    UnitNotFound,
)
from cou.utils import juju_utils


def test_normalize_action_results():
    results = {"Stderr": "error", "stdout": "output"}
    expected = {"Stderr": "error", "Stdout": "output", "stderr": "error", "stdout": "output"}

    normalized_results = juju_utils._normalize_action_results(results)

    assert normalized_results == expected


def test_normalize_action_results_empty_results():
    results = {}
    expected = {}

    normalized_results = juju_utils._normalize_action_results(results)

    assert normalized_results == expected


@pytest.mark.asyncio
async def test_retry_without_args():
    """Test retry as decorator without any arguments."""
    obj = MagicMock()

    class TestModel:
        @juju_utils.retry
        async def func(self):
            obj.run()

    test_model = TestModel()
    await test_model.func()
    obj.run.assert_called_once_with()


@pytest.mark.asyncio
async def test_retry_with_args():
    """Test retry as decorator with arguments."""
    obj = MagicMock()

    class TestModel:
        @juju_utils.retry(timeout=1, no_retry_exceptions=(Exception,))
        async def func(self):
            obj.run()

    test_model = TestModel()
    await test_model.func()
    obj.run.assert_called_once_with()


@pytest.mark.asyncio
@patch("asyncio.sleep", new=AsyncMock())
async def test_retry_with_failures():
    """Test retry with some failures."""
    obj = MagicMock()
    obj.run.side_effect = [ValueError, KeyError, None]

    class TestModel:
        @juju_utils.retry(timeout=1)
        async def func(self):
            obj.run()

    test_model = TestModel()
    await test_model.func()
    obj.run.assert_has_calls([call()] * 3)


@pytest.mark.asyncio
@patch("asyncio.sleep", new=AsyncMock())
async def test_retry_ignored_exceptions():
    """Test retry with ignored exceptions."""
    obj = MagicMock()
    obj.run.side_effect = [ValueError, KeyError, SystemExit]

    class TestModel:
        @juju_utils.retry(timeout=1, no_retry_exceptions=(SystemExit,))
        async def func(self):
            obj.run()

    test_model = TestModel()
    with pytest.raises(SystemExit):
        await test_model.func()

    obj.run.assert_has_calls([call()] * 3)


@pytest.mark.asyncio
async def test_retry_failure():
    """Test retry with ignored exceptions."""
    obj = MagicMock()
    obj.run.side_effect = [ValueError]
    timeout = 1

    class TestModel:
        @juju_utils.retry(timeout=timeout)
        async def func(self):
            obj.run()
            await asyncio.sleep(timeout)  # waiting for timeout

    test_model = TestModel()
    with pytest.raises(TimeoutException):
        await test_model.func()


@pytest.fixture
def mocked_model(mocker):
    """Fixture providing mocked juju.model.Model object."""
    model_mocker = mocker.patch("cou.utils.juju_utils.Model", return_value=AsyncMock(Model))
    model = model_mocker.return_value
    model.connection.return_value.is_open = True  # simulate already connected model
    yield model


def test_coumodel_init(mocker):
    """Test COUModel initialization."""
    model_mocker = mocker.patch("cou.utils.juju_utils.Model")
    name = "test-model"
    model = juju_utils.COUModel(name)

    model_mocker.assert_called_once_with(max_frame_size=juju_utils.JUJU_MAX_FRAME_SIZE)
    assert model._model == model_mocker.return_value
    assert model.name == name


@pytest.mark.asyncio
async def test_coumodel_create(mocked_model):
    """Test COUModel create function with no model_name defined."""
    model = await juju_utils.COUModel.create(None)

    assert model.name == mocked_model.name
    mocked_model.disconnect.assert_awaited_once_with()
    mocked_model.connect.assert_awaited_once_with(
        model_name=None,
        retries=juju_utils.DEFAULT_MODEL_RETRIES,
        retry_backoff=juju_utils.DEFAULT_MODEL_RETRY_BACKOFF,
    )


def test_coumodel_connected_no_connection(mocked_model):
    """Test COUModel connected property."""
    mocked_model.connection.side_effect = NoConnectionException

    model = juju_utils.COUModel("test-model")

    assert model.connected is False


def test_coumodel_connected(mocked_model):
    """Test COUModel connected property."""
    mocked_model.connection.return_value.is_open = True

    model = juju_utils.COUModel("test-model")

    assert model.connected is True


@pytest.mark.asyncio
async def test_coumodel_connect(mocked_model):
    """Test COUModel connection."""
    name = "test-model"
    model = juju_utils.COUModel(name)
    await model._connect()

    mocked_model.disconnect.assert_awaited_once_with()
    mocked_model.connect.assert_awaited_once_with(
        model_name=name,
        retries=juju_utils.DEFAULT_MODEL_RETRIES,
        retry_backoff=juju_utils.DEFAULT_MODEL_RETRY_BACKOFF,
    )


@pytest.mark.asyncio
async def test_coumodel_get_application(mocked_model):
    """Test COUModel get application."""
    app_name = "test-app"
    model = juju_utils.COUModel("test-model")

    app = await model._get_application(app_name)

    mocked_model.applications.get.assert_called_once_with(app_name)
    assert app == mocked_model.applications.get.return_value


@pytest.mark.asyncio
async def test_coumodel_get_application_failure(mocked_model):
    """Test COUModel get not existing application."""
    model = juju_utils.COUModel("test-model")
    mocked_model.applications.get.return_value = None

    with pytest.raises(ApplicationNotFound):
        await model._get_application("test-app")


@pytest.mark.asyncio
async def test_coumodel_get_model(mocked_model):
    """Test COUModel get connected model object."""
    mocked_model.connection.return_value = None  # simulate disconnected model

    model = juju_utils.COUModel("test-model")
    juju_model = await model._get_model()

    mocked_model.disconnect.assert_awaited_once()
    mocked_model.connect.assert_awaited_once()
    assert juju_model == mocked_model


@pytest.mark.asyncio
async def test_coumodel_get_unit(mocked_model):
    """Test COUModel get unit."""
    unit_name = "test-unit"
    model = juju_utils.COUModel("test-model")

    unit = await model._get_unit(unit_name)

    mocked_model.units.get.assert_called_once_with(unit_name)
    assert unit == mocked_model.units.get.return_value


@pytest.mark.asyncio
async def test_coumodel_get_unit_failure(mocked_model):
    """Test COUModel get not existing unit."""
    model = juju_utils.COUModel("test-model")
    mocked_model.units.get.return_value = None

    with pytest.raises(UnitNotFound):
        await model._get_unit("test-unit")


@pytest.mark.asyncio
async def test_coumodel_get_application_configs(mocked_model):
    """Test COUModel get application configuration."""
    mocked_model.applications.get.return_value = mocked_app = AsyncMock(Application)
    model = juju_utils.COUModel("test-model")

    app = await model.get_application_config("test-app")

    mocked_app.get_config.assert_awaited_once_with()
    assert app == mocked_app.get_config.return_value


@pytest.mark.asyncio
async def test_coumodel_get_charm_name(mocked_model):
    """Test COUModel get charm name from application by application name."""
    mocked_model.applications.get.return_value = mocked_app = AsyncMock(Application)
    model = juju_utils.COUModel("test-model")

    charm_name = await model.get_charm_name("test-app")

    assert charm_name == mocked_app.charm_name


@pytest.mark.asyncio
async def test_coumodel_get_charm_name_failure(mocked_model):
    """Test COUModel get charm name from application by application name."""
    mocked_model.applications.get.return_value = mocked_app = AsyncMock(Application)
    mocked_app.charm_name = None
    app_name = "test-app"
    model = juju_utils.COUModel("test-model")

    with pytest.raises(ApplicationError, match=f"Cannot obtain charm_name for {app_name}"):
        await model.get_charm_name("test-app")


@pytest.mark.asyncio
async def test_coumodel_get_status(mocked_model):
    """Test COUModel get model status."""
    model = juju_utils.COUModel("test-model")

    status = await model.get_status()

    mocked_model.get_status.assert_awaited_once_with()
    assert status == mocked_model.get_status.return_value


@pytest.mark.asyncio
async def test_coumodel_get_action_result(mocked_model):
    """Test COUModel run action."""
    mocked_action = AsyncMock(spec_set=Action).return_value
    model = juju_utils.COUModel("test-model")

    action = await model._get_action_result(mocked_action, False)

    mocked_action.wait.assert_awaited_once_with()
    assert action == mocked_action.wait.return_value
    mocked_model.get_action_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_coumodel_get_action_result_failure(mocked_model):
    """Test COUModel run action failing."""
    mocked_action = AsyncMock(spec_set=Action).return_value
    mocked_model.get_action_status.return_value = "failed"
    model = juju_utils.COUModel("test-model")

    with pytest.raises(ActionFailed):
        await model._get_action_result(mocked_action, True)

    mocked_action.wait.assert_awaited_once_with()

    mocked_model.get_action_status.assert_awaited_once_with(uuid_or_prefix=mocked_action.entity_id)
    mocked_model.get_action_output.assert_awaited_once_with(mocked_action.entity_id)


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.COUModel._get_action_result")
async def test_coumodel_run_action(mock_get_action_result, mocked_model):
    """Test COUModel run action."""
    action_name = "test-action"
    action_params = {"test-arg": "test"}
    mocked_model.units.get.return_value = mocked_unit = AsyncMock(Unit)
    mock_get_action_result.return_value = mocked_result = AsyncMock(Action)
    model = juju_utils.COUModel("test-model")

    action = await model.run_action("test_unit/0", action_name, action_params=action_params)

    mocked_unit.run_action.assert_awaited_once_with(action_name, **action_params)
    mock_get_action_result.assert_awaited_once_with(mocked_unit.run_action.return_value, False)
    assert action == mocked_result


@pytest.mark.asyncio
@patch("cou.utils.juju_utils._normalize_action_results")
async def test_coumodel_run_on_unit(mock_normalize_action_results, mocked_model):
    """Test COUModel run on unit."""
    command = "test-command"
    mocked_model.units.get.return_value = mocked_unit = AsyncMock(Unit)
    mocked_unit.run.return_value = mocked_action = AsyncMock(Action)
    results = mocked_action.data.get.return_value
    model = juju_utils.COUModel("test-model")

    await model.run_on_unit("test-unit/0", command)

    mocked_unit.run.assert_awaited_once_with(command, timeout=None)
    mock_normalize_action_results.assert_called_once_with(results)


@pytest.mark.asyncio
async def test_coumodel_set_application_configs(mocked_model):
    """Test COUModel set application configuration."""
    test_config = {"test-key": "test-value"}
    mocked_model.applications.get.return_value = mocked_app = AsyncMock(Application)
    model = juju_utils.COUModel("test-model")

    await model.set_application_config("test-app", test_config)

    mocked_app.set_config.assert_awaited_once_with(test_config)


@pytest.mark.asyncio
async def test_coumodel_scp_from_unit(mocked_model):
    """Test COUModel scp from unit to destination."""
    source, destination = "/tmp/source", "/tmp/destination"
    mocked_model.units.get.return_value = mocked_unit = AsyncMock(Unit)
    model = juju_utils.COUModel("test-model")

    await model.scp_from_unit("test-unit/0", source, destination)

    mocked_unit.scp_from.assert_awaited_once_with(
        source, destination, user="ubuntu", proxy=False, scp_opts=""
    )


@pytest.mark.asyncio
async def test_coumodel_upgrade_charm(mocked_model):
    """Test COUModel upgrade application."""
    application_name = "test-app"
    channel = "latest/edge"
    mocked_model.applications.get.return_value = mocked_app = AsyncMock(Application)
    model = juju_utils.COUModel("test-model")

    await model.upgrade_charm(application_name, channel)

    mocked_app.upgrade_charm.assert_awaited_once_with(
        channel=channel,
        force_series=False,
        force_units=False,
        path=None,
        resources=None,
        revision=None,
        switch=None,
    )


@pytest.mark.asyncio
async def test_coumodel_wait_for_idle(mocked_model):
    """Test COUModel wait for model to be idle."""
    timeout = 60
    model = juju_utils.COUModel("test-model")

    await model.wait_for_idle(timeout)

    mocked_model.wait_for_idle.assert_awaited_once_with(
        apps=None, timeout=timeout, idle_period=juju_utils.DEFAULT_MODEL_IDLE_PERIOD
    )
