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
from juju.client._definitions import ApplicationStatus, UnitStatus
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
    yield model


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
    """Test COUModel initialization."""
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
    """Test COUModel connected property."""
    mocked_model.connection.side_effect = NoConnectionException

    model = juju_utils.Model("test-model")

    assert model.connected is False


def test_coumodel_connected(mocked_model):
    """Test COUModel connected property."""
    mocked_model.connection.return_value.is_open = True

    model = juju_utils.Model("test-model")

    assert model.connected is True


def test_coumodel_name(mocked_model):
    """Test COUModel name property without model name."""
    exp_model_name = "test-model"
    mocked_model.connection.side_effect = NoConnectionException  # simulate an unconnected model

    model = juju_utils.Model(exp_model_name)

    assert model.name == exp_model_name
    model.juju_data.current_model.assert_not_called()


def test_coumodel_name_no_name(mocked_model):
    """Test COUModel name property without model name."""
    mocked_model.connection.side_effect = NoConnectionException  # simulate an unconnected model

    model = juju_utils.Model(None)

    assert model.name == model.juju_data.current_model.return_value
    model.juju_data.current_model.assert_called_once_with(model_only=True)


def test_coumodel_name_connected(mocked_model):
    """Test COUModel initialization without model name, but connected."""
    mocked_model.connection.return_value.is_open = True

    model = juju_utils.Model(None)

    assert model.name == mocked_model.name
    model.juju_data.current_model.assert_not_called()


@pytest.mark.asyncio
async def test_coumodel_connect(mocked_model):
    """Test COUModel connection."""
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
    """Test COUModel get application."""
    app_name = "test-app"
    model = juju_utils.Model("test-model")

    app = await model._get_application(app_name)

    mocked_model.applications.get.assert_called_once_with(app_name)
    assert app == mocked_model.applications.get.return_value


@pytest.mark.asyncio
async def test_coumodel_get_application_failure(mocked_model):
    """Test COUModel get not existing application."""
    model = juju_utils.Model("test-model")
    mocked_model.applications.get.return_value = None

    with pytest.raises(ApplicationNotFound):
        await model._get_application("test-app")


@pytest.mark.asyncio
async def test_coumodel_get_model(mocked_model):
    """Test COUModel get connected model object."""
    mocked_model.connection.return_value = None  # simulate disconnected model

    model = juju_utils.Model("test-model")
    juju_model = await model._get_model()

    mocked_model.disconnect.assert_awaited_once()
    mocked_model.connect.assert_awaited_once()
    assert juju_model == mocked_model


@pytest.mark.asyncio
async def test_coumodel_get_unit(mocked_model):
    """Test COUModel get unit."""
    unit_name = "test-unit"
    model = juju_utils.Model("test-model")

    unit = await model._get_unit(unit_name)

    mocked_model.units.get.assert_called_once_with(unit_name)
    assert unit == mocked_model.units.get.return_value


@pytest.mark.asyncio
async def test_coumodel_get_unit_failure(mocked_model):
    """Test COUModel get not existing unit."""
    model = juju_utils.Model("test-model")
    mocked_model.units.get.return_value = None

    with pytest.raises(UnitNotFound):
        await model._get_unit("test-unit")


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.is_charm_supported")
async def test_coumodel_get_supported_apps(mock_is_charm_supported, mocked_model):
    """Test COUModel providing list of supported applications."""
    mock_is_charm_supported.side_effect = [False, True]
    model = juju_utils.Model("test-model")
    app = MagicMock(spec_set=Application).return_value
    mocked_model.applications = {"unsupported": app, "supported": app}

    apps = await model._get_supported_apps()

    mock_is_charm_supported.assert_has_calls([call(app.charm_name), call(app.charm_name)])
    assert apps == ["supported"]


@pytest.mark.asyncio
async def test_coumodel_get_application_configs(mocked_model):
    """Test COUModel get application configuration."""
    mocked_model.applications.get.return_value = mocked_app = AsyncMock(Application)
    model = juju_utils.Model("test-model")

    app = await model.get_application_config("test-app")

    mocked_app.get_config.assert_awaited_once_with()
    assert app == mocked_app.get_config.return_value


@pytest.mark.asyncio
async def test_coumodel_get_charm_name(mocked_model):
    """Test COUModel get charm name from application by application name."""
    mocked_model.applications.get.return_value = mocked_app = AsyncMock(Application)
    model = juju_utils.Model("test-model")

    charm_name = await model.get_charm_name("test-app")

    assert charm_name == mocked_app.charm_name


@pytest.mark.asyncio
async def test_coumodel_get_charm_name_failure(mocked_model):
    """Test COUModel get charm name from application by application name."""
    mocked_model.applications.get.return_value = mocked_app = AsyncMock(Application)
    mocked_app.charm_name = None
    app_name = "test-app"
    model = juju_utils.Model("test-model")

    with pytest.raises(ApplicationError, match=f"Cannot obtain charm_name for {app_name}"):
        await model.get_charm_name("test-app")


@pytest.mark.asyncio
async def test_coumodel_get_status(mocked_model):
    """Test COUModel get model status."""
    model = juju_utils.Model("test-model")

    status = await model.get_status()

    mocked_model.get_status.assert_awaited_once_with()
    assert status == mocked_model.get_status.return_value


@pytest.mark.asyncio
async def test_coumodel_get_waited_action_object_object(mocked_model):
    """Test COUModel get action result."""
    mocked_action = AsyncMock(spec_set=Action).return_value
    model = juju_utils.Model("test-model")

    action = await model._get_waited_action_object(mocked_action, False)

    mocked_action.wait.assert_awaited_once_with()
    assert action == mocked_action.wait.return_value


@pytest.mark.asyncio
async def test_coumodel_get_waited_action_object_failure(mocked_model):
    """Test COUModel get action result failing."""
    mocked_action = AsyncMock(spec_set=Action).return_value
    mocked_action.wait.return_value = mocked_action
    mocked_action.wait.status = "failed"
    model = juju_utils.Model("test-model")

    with pytest.raises(ActionFailed):
        await model._get_waited_action_object(mocked_action, True)


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.Model._get_waited_action_object")
async def test_coumodel_run_action(mock_get_waited_action_object, mocked_model):
    """Test COUModel run action."""
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
@patch("cou.utils.juju_utils._normalize_action_results")
async def test_coumodel_run_on_unit(mock_normalize_action_results, mocked_model):
    """Test COUModel run on unit."""
    command = "test-command"
    mocked_model.units.get.return_value = mocked_unit = AsyncMock(Unit)
    mocked_unit.run.return_value = mocked_action = AsyncMock(Action)
    results = mocked_action.data.get.return_value
    mock_normalize_action_results.return_value = {"Code": "0", "Stdout": "some results"}
    model = juju_utils.Model("test-model")

    await model.run_on_unit("test-unit/0", command)

    mocked_unit.run.assert_awaited_once_with(command, timeout=None)
    mock_normalize_action_results.assert_called_once_with(results)


@pytest.mark.asyncio
@patch("cou.utils.juju_utils._normalize_action_results")
async def test_coumodel_run_on_unit_failed_command(mock_normalize_action_results, mocked_model):
    """Test COUModel run on unit."""
    command = "test-command"
    mocked_model.units.get.return_value = mocked_unit = AsyncMock(Unit)
    mocked_unit.run.return_value = mocked_action = AsyncMock(Action)
    results = mocked_action.data.get.return_value
    mock_normalize_action_results.return_value = {"Code": "1", "Stderr": "Error!"}
    model = juju_utils.Model("test-model")

    with pytest.raises(CommandRunFailed):
        await model.run_on_unit("test-unit/0", command)

    mocked_unit.run.assert_awaited_once_with(command, timeout=None)
    mock_normalize_action_results.assert_called_once_with(results)


@pytest.mark.asyncio
async def test_coumodel_set_application_configs(mocked_model):
    """Test COUModel set application configuration."""
    test_config = {"test-key": "test-value"}
    mocked_model.applications.get.return_value = mocked_app = AsyncMock(Application)
    model = juju_utils.Model("test-model")

    await model.set_application_config("test-app", test_config)

    mocked_app.set_config.assert_awaited_once_with(test_config)


@pytest.mark.asyncio
async def test_coumodel_scp_from_unit(mocked_model):
    """Test COUModel scp from unit to destination."""
    source, destination = "/tmp/source", "/tmp/destination"
    mocked_model.units.get.return_value = mocked_unit = AsyncMock(Unit)
    model = juju_utils.Model("test-model")

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
async def test_coumodel_wait_for_active_idle(mock_get_supported_apps, mocked_model):
    """Test COUModel wait for related apps to be active idle."""
    timeout = 60
    model = juju_utils.Model("test-model")
    mock_get_supported_apps.return_value = ["app1", "app2"]

    await model.wait_for_active_idle(timeout)

    mocked_model.wait_for_idle.assert_awaited_once_with(
        apps=["app1", "app2"],
        timeout=timeout,
        idle_period=juju_utils.DEFAULT_MODEL_IDLE_PERIOD,
        raise_on_blocked=False,
        status="active",
    )
    mock_get_supported_apps.assert_awaited_once_with()


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.Model._get_supported_apps")
async def test_coumodel_wait_for_active_idle_apps(mock_get_supported_apps, mocked_model):
    """Test COUModel wait for specific apps to be active idle."""
    timeout = 60
    model = juju_utils.Model("test-model")

    await model.wait_for_active_idle(timeout, apps=["app1"])

    mocked_model.wait_for_idle.assert_awaited_once_with(
        apps=["app1"],
        timeout=timeout,
        idle_period=juju_utils.DEFAULT_MODEL_IDLE_PERIOD,
        raise_on_blocked=False,
        status="active",
    )
    mock_get_supported_apps.assert_not_awaited()


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.Model._get_supported_apps")
async def test_coumodel_wait_for_active_idle_timeout(mock_get_supported_apps, mocked_model):
    """Test COUModel wait for model to be active idle reach timeout."""
    timeout = 60
    exp_apps = ["app1", "app2"]
    mocked_model.wait_for_idle.side_effect = asyncio.exceptions.TimeoutError
    model = juju_utils.Model(None)

    with pytest.raises(WaitForApplicationsTimeout):
        await model.wait_for_active_idle(timeout, apps=exp_apps)

    mocked_model.wait_for_idle.assert_awaited_once_with(
        apps=exp_apps,
        timeout=timeout,
        idle_period=juju_utils.DEFAULT_MODEL_IDLE_PERIOD,
        raise_on_blocked=False,
        status="active",
    )
    mock_get_supported_apps.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_machines(mocked_model):
    """Test COUModel getting machines from model."""
    expected_machines = {
        "0": juju_utils.Machine(
            "0",
            (
                "app1",
                "app2",
            ),
            "zone-1",
        ),
        "1": juju_utils.Machine("1", ("app1",), "zone-2"),
        "2": juju_utils.Machine("2", ("app1",), "zone-3"),
    }
    mocked_model.machines = {f"{i}": _generate_juju_machine(f"{i}") for i in range(3)}
    mocked_model.units = {
        "app1/0": _generate_juju_unit("app1", "0"),
        "app1/1": _generate_juju_unit("app1", "1"),
        "app1/2": _generate_juju_unit("app1", "2"),
        "app2/0": _generate_juju_unit("app2", "0"),
    }
    mocked_model.applications = {
        "app1": MagicMock(spec_set=Application)(),
        "app2": MagicMock(spec_set=Application)(),
    }

    model = juju_utils.Model("test-model")
    machines = await model._get_machines()

    assert machines == expected_machines


def _generate_juju_unit(app: str, machine_id: str) -> MagicMock:
    unit = MagicMock(set=Unit)()
    unit.application = app
    unit.machine.id = machine_id
    return unit


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


def _generate_unit_status(app: str, unit_id: int, machine_id: str) -> tuple[str, MagicMock]:
    """Generate unit name and status."""
    status = MagicMock(spec_set=UnitStatus)()
    status.machine = machine_id
    return f"{app}/{unit_id}", status


def _generate_app_status(units: dict[str, MagicMock]) -> MagicMock:
    """Generate app status with units."""
    status = MagicMock(spec_set=ApplicationStatus)()
    status.units = units
    return status


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.Model.get_status")
@patch("cou.utils.juju_utils.Model._get_machines")
async def test_get_applications(mock_get_machines, mock_get_status, mocked_model):
    """Test COUModel getting applications from model.

    Getting application from status, where model contain 3 applications deployed on 3 machines.
    The juju status to show model, which this test try to use.

    Model  Controller  Cloud/Region         Version  SLA          Timestamp
    test   lxd         localhost/localhost  3.1.6    unsupported  18:52:34+01:00

    App   Version  Status  Scale  Charm  Channel  Rev  Exposed  Message
    app1  20.04    active      3  app    stable    28  no
    app2  20.04    active      1  app    stable    24  no
    app3  20.04    active      1  app    stable    24  no

    Unit     Workload  Agent  Machine  Public address  Ports  Message
    app1/0*  active    idle   0        10.147.4.1
    app1/1   active    idle   1        10.147.4.2
    app1/2   active    idle   2        10.147.4.3
    app2/0*  active    idle   0        10.147.4.1
    app3/0*  active    idle   1        10.147.4.2

    Machine  State    Address     Inst id        Base          AZ  Message
    0        started  10.147.4.1  juju-62c6c2-0  ubuntu@20.04       Running
    1        started  10.147.4.2  juju-62c6c2-1  ubuntu@20.04       Running
    2        started  10.147.4.3  juju-62c6c2-2  ubuntu@20.04       Running
    """
    exp_apps = ["app1", "app2", "app3"]
    # definy AsyncMock for app.get_config, so it can be awaited
    for app in exp_apps:
        mocked_model.applications[app].get_config = AsyncMock()

    exp_machines = {
        "0": juju_utils.Machine("0", ()),
        "1": juju_utils.Machine("1", ()),
        "2": juju_utils.Machine("2", ()),
    }
    exp_units = {
        "app1": dict([_generate_unit_status("app1", i, f"{i}") for i in range(3)]),
        "app2": dict([_generate_unit_status("app2", 0, "0")]),
        "app3": dict([_generate_unit_status("app3", 0, "1")]),
    }
    full_status_apps = {app: _generate_app_status(exp_units[app]) for app in exp_apps}
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
            machines={
                unit.machine: exp_machines[unit.machine] for unit in exp_units[app].values()
            },
            model=model,
            origin=status.charm.split(":")[0],
            series=status.series,
            subordinate_to=status.subordinate_to,
            units={
                name: juju_utils.Unit(name, exp_machines[unit.machine], unit.workload_version)
                for name, unit in exp_units[app].items()
            },
            workload_version=status.workload_version,
        )
        for app, status in full_status_apps.items()
    }

    apps = await model.get_applications()

    mock_get_status.assert_awaited_once_with()
    mock_get_machines.assert_awaited_once_with()
    (mocked_model.applications[app].assert_awaited_once_with(app) for app in full_status_apps)
    assert apps == exp_apps
