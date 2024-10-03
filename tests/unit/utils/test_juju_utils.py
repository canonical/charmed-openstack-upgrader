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
from juju.client._definitions import ApplicationStatus, Base, UnitStatus
from juju.client.connector import NoConnectionException
from juju.machine import Machine
from juju.model import Model
from juju.unit import Unit

from cou.exceptions import (
    ActionFailed,
    ApplicationError,
    ApplicationNotFound,
    CommandRunFailed,
    TimeoutException,
    UnitNotFound,
    WaitForApplicationsTimeout,
)
from cou.utils import juju_utils


@pytest.mark.parametrize(
    "base, exp_series",
    [
        (Base("18.04/stable", "ubuntu"), "bionic"),
        (Base("20.04/stable", "ubuntu"), "focal"),
        (Base("22.04/stable", "ubuntu"), "jammy"),
    ],
)
def test_convert_base_to_series(base, exp_series):
    """Test helper function to convert base to series."""
    assert juju_utils._convert_base_to_series(base) == exp_series


@pytest.fixture
def mocked_model(mocker):
    """Fixture providing mocked juju.model.Model object."""
    mocker.patch("cou.utils.juju_utils.FileJujuData")
    model_mocker = mocker.patch(
        "cou.utils.juju_utils.JujuModel", return_value=MagicMock(spec_set=Model)
    )
    model = model_mocker.return_value
    model.connection.return_value.is_open = True  # simulate already connected model
    model.disconnect = AsyncMock()
    model.connect = AsyncMock()
    model.wait_for_idle = AsyncMock()
    yield model


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


@pytest.mark.parametrize(
    "machine_id, az",
    [
        # one field different is considered another machine
        ("0", "zone-3"),
        ("1", "zone-2"),
    ],
)
def test_machine_not_eq(machine_id, az):
    machine_0 = juju_utils.Machine("0", (), "zone-1")
    machine_1 = juju_utils.Machine(machine_id, (), az)

    assert machine_0 != machine_1


def test_machine_eq():
    machine_0 = juju_utils.Machine("0", (), "zone-1")
    machine_1 = juju_utils.Machine("0", (), "zone-1")

    assert machine_0 == machine_1


@patch("cou.utils.juju_utils.FileJujuData")
def test_coumodel_init(mock_juju_data, mocker):
    """Test Model initialization."""
    model_mocker = mocker.patch("cou.utils.juju_utils.JujuModel")
    mocked_model = model_mocker.return_value
    mocked_model.connection.side_effect = NoConnectionException  # simulate an unconnected model
    name = "test-model"

    model = juju_utils.Model(name)

    mock_juju_data.assert_called_once_with()
    model_mocker.assert_called_once_with(
        max_frame_size=juju_utils.JUJU_MAX_FRAME_SIZE, jujudata=mock_juju_data.return_value
    )
    assert model._model == mocked_model


def test_coumodel_connected_no_connection(mocked_model):
    """Test Model connected property."""
    mocked_model.connection.side_effect = NoConnectionException

    model = juju_utils.Model("test-model")

    assert model.connected is False


def test_coumodel_connected(mocked_model):
    """Test Model connected property."""
    mocked_model.connection.return_value.is_open = True

    model = juju_utils.Model("test-model")

    assert model.connected is True


def test_coumodel_name(mocked_model):
    """Test Model name property without model name."""
    exp_model_name = "test-model"
    mocked_model.connection.side_effect = NoConnectionException  # simulate an unconnected model

    model = juju_utils.Model(exp_model_name)

    assert model.name == exp_model_name
    model.juju_data.current_model.assert_not_called()


def test_coumodel_name_no_name(mocked_model):
    """Test Model name property without model name."""
    mocked_model.connection.side_effect = NoConnectionException  # simulate an unconnected model

    model = juju_utils.Model(None)

    assert model.name == model.juju_data.current_model.return_value
    model.juju_data.current_model.assert_called_once_with(model_only=True)


def test_coumodel_name_connected(mocked_model):
    """Test Model initialization without model name, but connected."""
    mocked_model.connection.return_value.is_open = True

    model = juju_utils.Model(None)

    assert model.name == mocked_model.name
    model.juju_data.current_model.assert_not_called()


@pytest.mark.asyncio
async def test_coumodel_connect(mocked_model):
    """Test Model connection."""
    name = "test-model"
    model = juju_utils.Model(name)
    await model.connect()

    mocked_model.disconnect.assert_awaited_once_with()
    mocked_model.connect.assert_awaited_once_with(
        model_name=name,
        retries=juju_utils.DEFAULT_MODEL_RETRIES,
        retry_backoff=juju_utils.DEFAULT_MODEL_RETRY_BACKOFF,
    )


@pytest.mark.asyncio
async def test_coumodel_get_application(mocked_model):
    """Test Model get application."""
    app_name = "test-app"
    model = juju_utils.Model("test-model")

    app = await model._get_application(app_name)

    mocked_model.applications.get.assert_called_once_with(app_name)
    assert app == mocked_model.applications.get.return_value


@pytest.mark.asyncio
async def test_coumodel_get_application_failure(mocked_model):
    """Test Model get not existing application."""
    model = juju_utils.Model("test-model")
    mocked_model.applications.get.return_value = None

    with pytest.raises(ApplicationNotFound):
        await model._get_application("test-app")


@pytest.mark.asyncio
async def test_coumodel_get_model(mocked_model):
    """Test Model get connected model object."""
    mocked_model.connection.return_value = None  # simulate disconnected model

    model = juju_utils.Model("test-model")
    juju_model = await model._get_model()

    mocked_model.disconnect.assert_awaited_once()
    mocked_model.connect.assert_awaited_once()
    assert juju_model == mocked_model


@pytest.mark.asyncio
async def test_coumodel_get_unit(mocked_model):
    """Test Model get unit."""
    unit_name = "test-unit"
    model = juju_utils.Model("test-model")

    unit = await model.get_unit(unit_name)

    mocked_model.units.get.assert_called_once_with(unit_name)
    assert unit == mocked_model.units.get.return_value


@pytest.mark.asyncio
async def test_coumodel_get_unit_failure(mocked_model):
    """Test Model get not existing unit."""
    model = juju_utils.Model("test-model")
    mocked_model.units.get.return_value = None

    with pytest.raises(UnitNotFound):
        await model.get_unit("test-unit")


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.is_charm_supported")
async def test_coumodel_get_supported_apps(mock_is_charm_supported, mocked_model):
    """Test Model providing list of supported applications."""
    mock_is_charm_supported.side_effect = [False, True]
    model = juju_utils.Model("test-model")
    app = MagicMock(spec_set=Application).return_value
    mocked_model.applications = {"unsupported": app, "supported": app}

    apps = await model._get_supported_apps()

    mock_is_charm_supported.assert_has_calls([call(app.charm_name), call(app.charm_name)])
    assert apps == ["supported"]


@pytest.mark.asyncio
async def test_coumodel_get_application_configs(mocked_model):
    """Test Model get application configuration."""
    mocked_model.applications.get.return_value = mocked_app = AsyncMock(Application)
    model = juju_utils.Model("test-model")

    app = await model.get_application_config("test-app")

    mocked_app.get_config.assert_awaited_once_with()
    assert app == mocked_app.get_config.return_value


@pytest.mark.asyncio
async def test_coumodel_get_charm_name(mocked_model):
    """Test Model get charm name from application by application name."""
    mocked_model.applications.get.return_value = mocked_app = AsyncMock(Application)
    model = juju_utils.Model("test-model")

    charm_name = await model.get_charm_name("test-app")

    assert charm_name == mocked_app.charm_name


@pytest.mark.asyncio
async def test_coumodel_get_charm_name_failure(mocked_model):
    """Test Model get charm name from application by application name."""
    mocked_model.applications.get.return_value = mocked_app = AsyncMock(Application)
    mocked_app.charm_name = None
    app_name = "test-app"
    model = juju_utils.Model("test-model")

    with pytest.raises(ApplicationError, match=f"Cannot obtain charm_name for {app_name}"):
        await model.get_charm_name("test-app")


@pytest.mark.asyncio
async def test_coumodel_get_status(mocked_model):
    """Test Model get model status."""
    model = juju_utils.Model("test-model")

    status = await model.get_status()

    mocked_model.get_status.assert_awaited_once_with()
    assert status == mocked_model.get_status.return_value


@pytest.mark.asyncio
async def test_coumodel_get_waited_action_object_object(mocked_model):
    """Test Model get action result."""
    mocked_action = AsyncMock(spec_set=Action).return_value
    model = juju_utils.Model("test-model")

    action = await model._get_waited_action_object(mocked_action, False)

    mocked_action.wait.assert_awaited_once_with()
    assert action == mocked_action.wait.return_value


@pytest.mark.asyncio
async def test_coumodel_get_waited_action_object_failure(mocked_model):
    """Test Model get action result failing."""
    mocked_action = AsyncMock(spec_set=Action).return_value
    mocked_action.wait.return_value = mocked_action
    mocked_action.wait.status = "failed"
    model = juju_utils.Model("test-model")

    with pytest.raises(ActionFailed):
        await model._get_waited_action_object(mocked_action, True)


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.Model._get_waited_action_object")
async def test_coumodel_run_action(mock_get_waited_action_object, mocked_model):
    """Test Model run action."""
    action_name = "test-action"
    action_params = {"test-arg": "test"}
    mocked_model.units.get.return_value = mocked_unit = AsyncMock(Unit)
    mock_get_waited_action_object.return_value = mocked_result = AsyncMock(Action)
    model = juju_utils.Model("test-model")

    action = await model.run_action("test_unit/0", action_name, action_params=action_params)

    mocked_unit.run_action.assert_awaited_once_with(action_name, **action_params)
    mock_get_waited_action_object.assert_awaited_once_with(
        mocked_unit.run_action.return_value, False
    )
    assert action == mocked_result


@pytest.mark.asyncio
async def test_coumodel_run_on_unit(mocked_model):
    """Test Model run on unit."""
    command = "test-command"
    expected_results = {"return-code": 0, "stdout": "some results"}
    mocked_model.units.get.return_value = mocked_unit = AsyncMock(Unit)
    mocked_unit.run.return_value = mocked_action = AsyncMock(Action)
    mocked_action.results = expected_results
    model = juju_utils.Model("test-model")

    results = await model.run_on_unit("test-unit/0", command)

    mocked_unit.run.assert_awaited_once_with(command, timeout=None, block=True)
    assert results == expected_results


@pytest.mark.asyncio
async def test_coumodel_run_on_unit_failed_command(mocked_model):
    """Test Model run on unit."""
    command = "test-command"
    expected_results = {"return-code": 1, "stderr": "Error!"}
    mocked_model.units.get.return_value = mocked_unit = AsyncMock(Unit)
    mocked_unit.run.return_value = mocked_action = AsyncMock(Action)
    mocked_action.results = expected_results
    model = juju_utils.Model("test-model")

    expected_err = "Command test-command failed with code 1, output None and error Error!"
    with pytest.raises(CommandRunFailed, match=expected_err):
        await model.run_on_unit("test-unit/0", command)

    mocked_unit.run.assert_awaited_once_with(command, timeout=None, block=True)


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.logger")
@patch("cou.utils.juju_utils.Model._run_update_status_hook")
@patch("cou.utils.juju_utils.Model._dispatch_update_status_hook")
async def test_coumodel_update_status_use_dispatch(
    use_dispatch, use_hooks, mocked_logger, mocked_model
):
    """Test Model update_status using dispatch."""
    model = juju_utils.Model("test-model")
    await model.update_status("test-unit/0")

    use_dispatch.assert_awaited_once()
    use_hooks.assert_not_awaited()
    mocked_logger.assert_not_called()


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.logger")
@patch("cou.utils.juju_utils.Model._run_update_status_hook")
@patch("cou.utils.juju_utils.Model._dispatch_update_status_hook")
async def test_coumodel_update_status_use_dispatch_failed(
    use_dispatch, use_hooks, mocked_logger, mocked_model
):
    """Test Model update_status using dispatch failed."""
    use_dispatch.side_effect = CommandRunFailed("some cmd", result={})
    model = juju_utils.Model("test-model")

    with pytest.raises(CommandRunFailed):
        await model.update_status("test-unit/0")
        use_dispatch.assert_awaited_once()
        use_hooks.assert_not_awaited()
        mocked_logger.assert_not_called()


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.logger")
@patch("cou.utils.juju_utils.Model._run_update_status_hook")
@patch("cou.utils.juju_utils.Model._dispatch_update_status_hook")
async def test_coumodel_update_status_use_hooks(use_dispatch, use_hooks, mocked_model):
    """Test Model update_status using hooks."""
    use_dispatch.side_effect = CommandRunFailed(
        "some cmd",
        result={
            "stderr": (
                "/tmp/juju-exec4159838212/script.sh: "
                "line 1: ./dispatch: No such file or directory"
            ),
        },
    )
    model = juju_utils.Model("test-model")
    await model.update_status("test-unit/0")

    use_dispatch.assert_awaited_once()
    use_hooks.assert_awaited_once()


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.logger")
@patch("cou.utils.juju_utils.Model._run_update_status_hook")
@patch("cou.utils.juju_utils.Model._dispatch_update_status_hook")
async def test_coumodel_update_status_use_hooks_failed(
    use_dispatch, use_hooks, mocked_logger, mocked_model
):
    """Test Model update_status using hooks failed."""
    use_dispatch.side_effect = CommandRunFailed(
        "some cmd",
        result={
            "stderr": (
                "/tmp/juju-exec4159838212/script.sh: "
                "line 1: ./dispatch: No such file or directory"
            )
        },
    )
    use_hooks.side_effect = CommandRunFailed("some cmd", result={})
    model = juju_utils.Model("test-model")

    with pytest.raises(CommandRunFailed):
        await model.update_status("test-unit/0")
        use_dispatch.assert_awaited_once()
        use_hooks.assert_not_awaited()
        mocked_logger.assert_not_called()


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.logger")
@patch("cou.utils.juju_utils.Model._run_update_status_hook")
@patch("cou.utils.juju_utils.Model._dispatch_update_status_hook")
async def test_coumodel_update_status_skipped(
    use_dispatch, use_hooks, mocked_logger, mocked_model
):
    """Test skip Model update_status."""
    use_dispatch.side_effect = CommandRunFailed(
        "some cmd",
        result={
            "stderr": (
                "/tmp/juju-exec4159838212/script.sh: "
                "line 1: ./dispatch: No such file or directory"
            )
        },
    )
    use_hooks.side_effect = CommandRunFailed(
        "some cmd",
        result={
            "stderr": (
                "/tmp/juju-exec1660320022/script.sh: "
                "line 1: hooks/update-status: No such file or directory"
            )
        },
    )
    model = juju_utils.Model("test-model")
    await model.update_status("test-unit/0")

    use_dispatch.assert_awaited_once()
    use_hooks.assert_awaited_once()
    mocked_logger.debug.assert_called_once()


@pytest.mark.asyncio
async def test_coumodel_set_application_configs(mocked_model):
    """Test Model set application configuration."""
    test_config = {"test-key": "test-value"}
    mocked_model.applications.get.return_value = mocked_app = AsyncMock(Application)
    model = juju_utils.Model("test-model")

    await model.set_application_config("test-app", test_config)

    mocked_app.set_config.assert_awaited_once_with(test_config)


@pytest.mark.asyncio
async def test_coumodel_scp_from_unit(mocked_model):
    """Test Model scp from unit to destination."""
    source, destination = "/tmp/source", "/tmp/destination"
    mocked_model.units.get.return_value = mocked_unit = AsyncMock(Unit)
    model = juju_utils.Model("test-model")

    await model.scp_from_unit("test-unit/0", source, destination)

    mocked_unit.scp_from.assert_awaited_once_with(
        source, destination, user="ubuntu", proxy=False, scp_opts=""
    )


@pytest.mark.asyncio
async def test_coumodel_upgrade_charm(mocked_model):
    """Test Model upgrade application."""
    application_name = "test-app"
    channel = "latest/edge"
    mocked_model.applications.get.return_value = mocked_app = AsyncMock(Application)
    model = juju_utils.Model("test-model")

    await model.upgrade_charm(application_name, channel)

    mocked_app.upgrade_charm.assert_awaited_once_with(
        channel=channel,
        force_series=False,
        force_units=False,
        path=None,
        revision=None,
        switch=None,
    )


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.Model._get_supported_apps")
@pytest.mark.parametrize(
    "case, status,timeout,raise_on_blocked,raise_on_error",
    [
        # status
        ("active status", "active", 60, False, True),
        ("blocked status", "blocked", 60, False, True),
        ("error status", "error", 60, False, True),
        ("raise_on_blocked", "active", 60, True, True),
        ("raise_on_error", "active", 60, False, False),
        ("timeout", "active", 120, False, True),
    ],
)
async def test_coumodel_wait_for_idle(
    mock_get_supported_apps,
    case,
    status,
    timeout,
    raise_on_blocked,
    raise_on_error,
    mocked_model,
):
    """Test Model wait for related apps to be active idle."""
    model = juju_utils.Model("test-model")
    mock_get_supported_apps.return_value = ["app1", "app2"]

    await model.wait_for_idle(
        timeout=timeout,
        status=status,
        raise_on_error=raise_on_error,
        raise_on_blocked=raise_on_blocked,
    )

    mocked_model.wait_for_idle.assert_has_awaits(
        [
            call(
                apps=["app1"],
                timeout=timeout,
                idle_period=juju_utils.DEFAULT_MODEL_IDLE_PERIOD,
                raise_on_blocked=raise_on_blocked,
                raise_on_error=raise_on_error,
                status=status,
                wait_for_at_least_units=0,
            ),
            call(
                apps=["app2"],
                timeout=timeout,
                idle_period=juju_utils.DEFAULT_MODEL_IDLE_PERIOD,
                raise_on_blocked=raise_on_blocked,
                raise_on_error=raise_on_error,
                status=status,
                wait_for_at_least_units=0,
            ),
        ]
    )
    mock_get_supported_apps.assert_awaited_once_with()


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.Model._get_supported_apps")
async def test_coumodel_wait_for_idle_apps(mock_get_supported_apps, mocked_model):
    """Test Model wait for specific apps to be active idle."""
    timeout = 60
    model = juju_utils.Model("test-model")

    await model.wait_for_idle(timeout, apps=["app1"])

    mocked_model.wait_for_idle.assert_awaited_once_with(
        apps=["app1"],
        timeout=timeout,
        idle_period=juju_utils.DEFAULT_MODEL_IDLE_PERIOD,
        raise_on_blocked=False,
        raise_on_error=True,
        status="active",
        wait_for_at_least_units=0,
    )
    mock_get_supported_apps.assert_not_awaited()


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.Model._get_supported_apps")
async def test_coumodel_wait_for_idle_timeout(mock_get_supported_apps, mocked_model):
    """Test Model wait for model to be active idle reach timeout."""
    timeout = 60
    exp_apps = ["app1", "app2"]
    mocked_model.wait_for_idle.side_effect = asyncio.exceptions.TimeoutError
    model = juju_utils.Model(None)

    with pytest.raises(WaitForApplicationsTimeout):
        await model.wait_for_idle(timeout, apps=exp_apps)

    mocked_model.wait_for_idle.assert_has_awaits(
        [
            call(
                apps=[app],
                timeout=timeout,
                idle_period=juju_utils.DEFAULT_MODEL_IDLE_PERIOD,
                raise_on_blocked=False,
                raise_on_error=True,
                status="active",
                wait_for_at_least_units=0,
            )
            for app in exp_apps
        ]
    )
    mock_get_supported_apps.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_machines(mocked_model):
    """Test Model getting machines from model."""
    expected_machines = {
        "0": juju_utils.Machine("0", (("my_app1", "app1"), ("my_app2", "app2")), "zone-1"),
        "1": juju_utils.Machine("1", (("my_app1", "app1"),), "zone-2"),
        "2": juju_utils.Machine("2", (("my_app1", "app1"),), "zone-3"),
    }
    mocked_model.machines = {f"{i}": _generate_juju_machine(f"{i}") for i in range(3)}
    mocked_model.units = {
        "my_app1/0": _generate_juju_unit("my_app1", "0", "0"),
        "my_app1/1": _generate_juju_unit("my_app1", "1", "1"),
        "my_app1/2": _generate_juju_unit("my_app1", "2", "2"),
        "my_app2/0": _generate_juju_unit("my_app2", "0", "0"),
    }
    mocked_model.applications = {
        "my_app1": _generate_juju_app("app1"),
        "my_app2": _generate_juju_app("app2"),
    }

    model = juju_utils.Model("test-model")
    machines = await model._get_machines()

    assert machines == expected_machines


def _generate_juju_unit(app: str, unit_id: str, machine_id: str) -> MagicMock:
    unit = MagicMock(set=Unit)()
    unit.application = app
    unit.name = f"{app}/{unit_id}"
    unit.machine.id = machine_id
    return unit


def _generate_juju_app(charm: str) -> MagicMock:
    app = MagicMock(spec_set=Application)()
    app.charm_name = charm
    return app


def _generate_juju_machine(machine_id: str) -> MagicMock:
    machine = MagicMock(set=Machine)()
    machine.id = machine_id
    machine.hardware_characteristics = {
        "arch": "amd64",
        "mem": 0,
        "cpu-cores": 0,
        "availability-zone": f"zone-{int(machine_id) + 1}",
    }
    return machine


def _generate_unit_status(
    app: str,
    unit_id: int,
    machine_id: str,
    subordinates: dict[str, MagicMock] = {},
) -> tuple[str, MagicMock]:
    """Generate unit name and status."""
    status = MagicMock(spec_set=UnitStatus)()
    status.machine = machine_id
    status.subordinates = subordinates
    status.charm = app
    return f"{app}/{unit_id}", status


def _generate_app_status(units: dict[str, MagicMock]) -> MagicMock:
    """Generate app status with units."""
    status = MagicMock(spec_set=ApplicationStatus)()
    status.units = units
    status.base = Base("20.04/stable", "ubuntu")
    return status


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.Model.get_status")
@patch("cou.utils.juju_utils.Model._get_machines")
async def test_get_applications(mock_get_machines, mock_get_status, mocked_model):
    """Test Model getting applications from model.

    Getting application from status, where model contain 3 applications deployed on 3 machines.
    The juju status to show model, which this test try to use.

    Model  Controller  Cloud/Region         Version  SLA          Timestamp
    test   lxd         localhost/localhost  3.1.6    unsupported  18:52:34+01:00

    App   Version  Status  Scale  Charm  Channel  Rev  Exposed  Message
    app1  20.04    active      3  app    stable    28  no
    app2  20.04    active      1  app    stable    24  no
    app3  20.04    active      1  app    stable    24  no
    app4  20.04    active      1  app    stable    24  no

    Unit      Workload  Agent  Machine  Public address  Ports  Message
    app1/0*   active    idle   0        10.147.4.1
    app1/1    active    idle   1        10.147.4.2
    app1/2    active    idle   2        10.147.4.3
    app2/0*   active    idle   0        10.147.4.1
      app4/0* active    idle            10.147.4.1
    app3/0*   active    idle   1        10.147.4.2

    Machine  State    Address     Inst id        Base          AZ  Message
    0        started  10.147.4.1  juju-62c6c2-0  ubuntu@20.04       Running
    1        started  10.147.4.2  juju-62c6c2-1  ubuntu@20.04       Running
    2        started  10.147.4.3  juju-62c6c2-2  ubuntu@20.04       Running
    """
    exp_apps = ["app1", "app2", "app3", "app4"]
    exp_machines = {
        "0": juju_utils.Machine("0", ()),
        "1": juju_utils.Machine("1", ()),
        "2": juju_utils.Machine("2", ()),
    }
    exp_units_from_status = {
        "app1": dict([_generate_unit_status("app1", i, f"{i}") for i in range(3)]),
        "app2": dict(
            [_generate_unit_status("app2", 0, "0", dict([_generate_unit_status("app4", 0, "")]))]
        ),
        "app3": dict([_generate_unit_status("app3", 0, "1")]),
        "app4": {},  # subordinate application has no units defined in juju status
    }
    exp_units = {
        "app1": [_generate_juju_unit("app1", f"{i}", f"{i}") for i in range(3)],
        "app2": [_generate_juju_unit("app2", "0", "0")],
        "app3": [_generate_juju_unit("app3", "0", "0")],
        "app4": [_generate_juju_unit("app4", "0", "0")],
    }

    mocked_model.applications = {app: MagicMock(spec_set=Application)() for app in exp_apps}

    for app in exp_apps:
        mocked_model.applications[app].get_actions = AsyncMock()
        mocked_model.applications[app].get_config = AsyncMock()
        mocked_model.applications[app].units = exp_units[app]
        mocked_model.applications[app].charm_name = app

    full_status_apps = {app: _generate_app_status(exp_units_from_status[app]) for app in exp_apps}
    mock_get_status.return_value.applications = full_status_apps
    mock_get_machines.return_value = exp_machines

    model = juju_utils.Model("test-model")
    exp_apps = {
        app: juju_utils.Application(
            name=app,
            can_upgrade_to=status.can_upgrade_to,
            charm=mocked_model.applications[app].charm_name,
            channel=status.charm_channel,
            config=mocked_model.applications[app].get_config.return_value,
            machines={unit.machine.id: exp_machines[unit.machine.id] for unit in exp_units[app]},
            model=model,
            origin=status.charm.split(":")[0],
            series="focal",
            subordinate_to=status.subordinate_to,
            units={
                name: juju_utils.Unit(
                    name,
                    exp_machines[unit.machine],
                    unit.workload_version,
                    [
                        juju_utils.SubordinateUnit(
                            subordinate_name,
                            subordinate.charm,
                        )
                        for subordinate_name, subordinate in unit.subordinates.items()
                    ],
                )
                for name, unit in exp_units_from_status[app].items()
            },
            workload_version=status.workload_version,
        )
        for app, status in full_status_apps.items()
    }

    apps = await model.get_applications()

    # check mocked objects
    mock_get_status.assert_awaited_once_with()
    mock_get_machines.assert_awaited_once_with()
    for app in full_status_apps:
        mocked_model.applications[app].get_config.assert_awaited_once_with()

    # check expected output
    assert apps == exp_apps

    # check number of units
    assert len(apps["app1"].units) == 3
    assert len(apps["app2"].units) == 1
    assert len(apps["app3"].units) == 1
    assert len(apps["app4"].units) == 0
    # check number of machines
    assert len(apps["app1"].machines) == 3
    assert len(apps["app2"].machines) == 1
    assert len(apps["app3"].machines) == 1
    assert len(apps["app4"].machines) == 1


def test_unit_repr():
    unit = juju_utils.Unit(name="foo/0", machine=MagicMock(), workload_version="1")
    assert repr(unit) == "foo/0"


def test_suborinate_unit_repr():
    unit = juju_utils.SubordinateUnit(name="foo/0", charm="foo")
    assert repr(unit) == "foo/0"


@pytest.mark.asyncio
async def test_run_update_status_hook(mocked_model):
    """Test Model _run_update_status hook."""
    mocked_model.units.get.return_value = mocked_unit = AsyncMock(Unit)
    mocked_unit.run.return_value = mocked_action = AsyncMock(Action)
    mocked_action.results = {"return-code": 0, "stderr": ""}
    model = juju_utils.Model("test-model")
    await model._run_update_status_hook(mocked_unit)
    mocked_unit.run.assert_awaited_once_with("hooks/update-status", timeout=None, block=True)


@pytest.mark.asyncio
async def test_dispatch_update_status_hook(mocked_model):
    """Test Model _dispatch_update_status hook."""
    mocked_model.units.get.return_value = mocked_unit = AsyncMock(Unit)
    mocked_unit.run.return_value = mocked_action = AsyncMock(Action)
    mocked_action.results = {"return-code": 0, "stderr": ""}
    model = juju_utils.Model("test-model")
    await model._dispatch_update_status_hook(mocked_unit)
    mocked_unit.run.assert_awaited_once_with(
        "JUJU_DISPATCH_PATH=hooks/update-status ./dispatch", timeout=None, block=True
    )


@pytest.mark.asyncio
async def test_coumodel_resolve_all(mocked_model):
    model = juju_utils.Model("test-model")

    mock_active_juju_app = AsyncMock()
    mock_active_juju_app.status = "active"

    mock_error_juju_app = AsyncMock()
    mock_error_juju_app.status = "error"

    mocked_model.applications = {"app1": mock_active_juju_app, "app2": mock_error_juju_app}

    mock_active_juju_unit = AsyncMock()
    mock_active_juju_unit.workload_status = "active"
    mock_error_juju_unit = AsyncMock()
    mock_error_juju_unit.workload_status = "error"

    mock_error_juju_app.units = [mock_active_juju_unit, mock_error_juju_unit]

    await model.resolve_all()

    mock_error_juju_unit.resolved.assert_awaited_once_with(retry=True)


@pytest.mark.asyncio
async def test_get_application_names(mocked_model):
    model = juju_utils.Model("test-model")
    test_apps = {
        "app1": MagicMock(),
        "app2": MagicMock(),
        "app3": MagicMock(),
    }
    test_apps["app1"].charm_name = "target_charm_name"
    test_apps["app2"].charm_name = "target_charm_name"
    test_apps["app3"].charm_name = "not_target_charm_name"
    mocked_model.applications = test_apps

    names = await model.get_application_names("target_charm_name")
    assert names == ["app1", "app2"]


@pytest.mark.asyncio
async def test_get_application_names_failed(mocked_model):
    model = juju_utils.Model("test-model")
    test_apps = {
        "app1": MagicMock(),
        "app2": MagicMock(),
        "app3": MagicMock(),
    }
    mocked_model.applications = test_apps
    mocked_model.name = "mocked-model"

    with pytest.raises(
        ApplicationNotFound, match="Cannot find 'app1_charm_name' charm in model 'mocked-model'"
    ):
        await model.get_application_names("app1_charm_name")


@pytest.mark.asyncio
async def test_coumodel_get_application_status(mocked_model):
    model = juju_utils.Model("test-model")
    data = {
        "app1": "app-status-1",
        "app2": "app-status-2",
        "app3": "app-status-3",
    }
    mocked_model.get_status.return_value.applications = data
    status = await model.get_application_status(app_name="app1")
    assert status == "app-status-1"
    mocked_model.get_status.assert_awaited_once_with(filters=["app1"])


@pytest.mark.asyncio
async def test_coumodel_get_application_status_failed(mocked_model):
    model = juju_utils.Model("test-model")
    mocked_model.name = "mocked-model"

    data = {
        "app1": "app-status-1",
        "app2": "app-status-2",
        "app3": "app-status-3",
    }
    mocked_model.get_status.return_value.applications = data
    with pytest.raises(
        ApplicationNotFound, match="Cannot find 'app-not-exists' in model 'mocked-model'."
    ):
        await model.get_application_status(app_name="app-not-exists")
