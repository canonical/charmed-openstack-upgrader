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
import json
from unittest.mock import AsyncMock, MagicMock, call, patch

import jubilant
import pytest

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
def mocked_juju(mocker):
    """Fixture providing mocked jubilant.Juju instance."""
    mock_juju = MagicMock(spec_set=jubilant.Juju)
    mocker.patch("cou.utils.juju_utils.jubilant.Juju", return_value=mock_juju)
    yield mock_juju


@pytest.fixture
def mocked_jubilant_juju(mocker):
    # Only mock the Juju class, jubilant.WaitError will remain real
    mock_juju_instance = MagicMock()
    mock_juju_class = MagicMock(return_value=mock_juju_instance)
    mocker.patch("cou.utils.juju_utils.jubilant.Juju", mock_juju_class)

    # Mock other jubilant functions that are used in tests
    mocker.patch("cou.utils.juju_utils.jubilant.any_error", MagicMock())
    mocker.patch("cou.utils.juju_utils.jubilant.any_blocked", MagicMock())
    mocker.patch("cou.utils.juju_utils.jubilant.all_active", MagicMock())
    mocker.patch("cou.utils.juju_utils.jubilant.all_blocked", MagicMock())
    mocker.patch("cou.utils.juju_utils.jubilant.all_maintenance", MagicMock())
    mocker.patch("cou.utils.juju_utils.jubilant.all_waiting", MagicMock())
    mocker.patch("cou.utils.juju_utils.jubilant.all_error", MagicMock())
    mocker.patch("cou.utils.juju_utils.jubilant.all_agents_idle", MagicMock())

    yield mock_juju_instance


@pytest.mark.parametrize(
    "channel, exp_series",
    [
        ("18.04/stable", "bionic"),
        ("20.04/stable", "focal"),
        ("22.04/stable", "jammy"),
    ],
)
def test_convert_base_to_series(channel, exp_series):
    """Test helper function to convert base to series."""
    base = jubilant.statustypes.FormattedBase(name="ubuntu", channel=channel)
    assert juju_utils._convert_base_to_series(base) == exp_series


@pytest.mark.parametrize(
    "hardware, exp_az",
    [
        ("arch=amd64 availability-zone=nova", "nova"),
        ("arch=amd64 availability-zone=us-east-1a", "us-east-1a"),
        ("arch=amd64 mem=1G", None),
        ("", None),
    ],
)
def test_parse_availability_zone(hardware, exp_az):
    """Test helper function to parse availability zone from hardware string."""
    assert juju_utils._parse_availability_zone(hardware) == exp_az


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


def test_coumodel_init(mocked_juju):
    """Test Model initialization."""
    name = "test-model"
    model = juju_utils.Model(name)

    assert model._name == name
    assert model._juju is mocked_juju


def test_coumodel_connected_no_connection(mocked_juju):
    """Test Model connected property when model not accessible."""
    mocked_juju.show_model.side_effect = jubilant.CLIError(1, ["juju"], "", "error")

    model = juju_utils.Model("test-model")

    assert model.connected is False


def test_coumodel_connected(mocked_juju):
    """Test Model connected property when model is accessible."""
    mocked_juju.show_model.return_value = MagicMock()

    model = juju_utils.Model("test-model")

    assert model.connected is True


def test_coumodel_name(mocked_juju):
    """Test Model name property with a provided name."""
    exp_model_name = "test-model"

    model = juju_utils.Model(exp_model_name)

    assert model.name == exp_model_name
    mocked_juju.show_model.assert_not_called()


def test_coumodel_name_no_name(mocked_juju):
    """Test Model name property without model name uses show_model."""
    mocked_juju.show_model.return_value.short_name = "current-model"

    model = juju_utils.Model(None)

    assert model.name == "current-model"
    mocked_juju.show_model.assert_called_once_with()


@pytest.mark.asyncio
async def test_coumodel_connect(mocked_juju):
    """Test Model connection validates model and caches name."""
    mocked_juju.show_model.return_value.short_name = "resolved-model"
    model = juju_utils.Model(None)

    await model.connect()

    mocked_juju.show_model.assert_called()
    assert model._name == "resolved-model"


@pytest.mark.asyncio
async def test_coumodel_get_unit(mocked_juju):
    """Test Model get unit."""
    unit_name = "test-app/0"
    mock_unit_status = MagicMock()
    mock_status = MagicMock()
    mock_status.apps = {"test-app": MagicMock(units={unit_name: mock_unit_status})}
    mocked_juju.status.return_value = mock_status

    model = juju_utils.Model("test-model")
    unit = await model.get_unit(unit_name)

    assert unit is mock_unit_status


@pytest.mark.asyncio
async def test_coumodel_get_unit_failure(mocked_juju):
    """Test Model get not existing unit."""
    mock_status = MagicMock()
    mock_status.apps = {"test-app": MagicMock(units={})}
    mocked_juju.status.return_value = mock_status

    model = juju_utils.Model("test-model")

    with pytest.raises(UnitNotFound):
        await model.get_unit("missing-unit/0")


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.is_charm_supported")
async def test_coumodel_get_supported_apps(mock_is_charm_supported, mocked_juju):
    """Test Model providing list of supported applications."""
    mock_is_charm_supported.side_effect = [False, True]
    mock_status = MagicMock()
    mock_status.apps = {
        "unsupported": MagicMock(charm_name="charm-a"),
        "supported": MagicMock(charm_name="charm-b"),
    }
    mocked_juju.status.return_value = mock_status

    model = juju_utils.Model("test-model")
    apps = await model._get_supported_apps()

    assert apps == ["supported"]


@pytest.mark.asyncio
async def test_coumodel_get_application_configs(mocked_juju):
    """Test Model get application configuration."""
    config_data = {"settings": {"key": {"value": "val", "type": "string"}}}
    mocked_juju.cli.return_value = json.dumps(config_data)
    model = juju_utils.Model("test-model")

    config = await model.get_application_config("test-app")

    assert config == config_data["settings"]


@pytest.mark.asyncio
async def test_coumodel_get_charm_name(mocked_juju):
    """Test Model get charm name from application by application name."""
    mock_status = MagicMock()
    mock_status.apps = {"test-app": MagicMock(charm_name="my-charm")}
    mocked_juju.status.return_value = mock_status

    model = juju_utils.Model("test-model")
    charm_name = await model.get_charm_name("test-app")

    assert charm_name == "my-charm"


@pytest.mark.asyncio
async def test_coumodel_get_charm_name_failure(mocked_juju):
    """Test Model get charm name failure when app has no charm_name."""
    mock_status = MagicMock()
    mock_status.apps = {"test-app": MagicMock(charm_name=None)}
    mocked_juju.status.return_value = mock_status
    app_name = "test-app"
    model = juju_utils.Model("test-model")

    with pytest.raises(ApplicationError, match=f"Cannot obtain charm_name for {app_name}"):
        await model.get_charm_name("test-app")


@pytest.mark.asyncio
async def test_coumodel_get_status(mocked_juju):
    """Test Model get model status."""
    mock_status = MagicMock(spec=jubilant.Status)
    mocked_juju.status.return_value = mock_status

    model = juju_utils.Model("test-model")
    status = await model.get_status()

    mocked_juju.status.assert_called_once_with()
    assert status is mock_status


@pytest.mark.asyncio
async def test_coumodel_run_action(mocked_juju):
    """Test Model run action."""
    action_name = "test-action"
    action_params = {"test-arg": "test"}
    mock_task = MagicMock(spec=jubilant.Task)
    mocked_juju.run.return_value = mock_task
    model = juju_utils.Model("test-model")

    task = await model.run_action("test_unit/0", action_name, action_params=action_params)

    mocked_juju.run.assert_called_once_with("test_unit/0", action_name, params=action_params)
    assert task is mock_task


@pytest.mark.asyncio
async def test_coumodel_run_action_failure_raise(mocked_juju):
    """Test Model run action failure with raise_on_failure=True."""
    mock_task = MagicMock(spec=jubilant.Task)
    mock_task.id = "1"
    mock_task.status = "failed"
    mock_task.message = "oops"
    mock_task.results = {}
    mocked_juju.run.side_effect = jubilant.TaskError(mock_task)
    model = juju_utils.Model("test-model")

    with pytest.raises(ActionFailed):
        await model.run_action("test_unit/0", "test-action", raise_on_failure=True)


@pytest.mark.asyncio
async def test_coumodel_run_action_failure_no_raise(mocked_juju):
    """Test Model run action failure with raise_on_failure=False returns task."""
    mock_task = MagicMock(spec=jubilant.Task)
    mock_task.status = "failed"
    mocked_juju.run.side_effect = jubilant.TaskError(mock_task)
    model = juju_utils.Model("test-model")

    result = await model.run_action("test_unit/0", "test-action", raise_on_failure=False)

    assert result is mock_task


@pytest.mark.asyncio
async def test_coumodel_run_on_unit(mocked_juju):
    """Test Model run on unit."""
    command = "test-command"
    mock_task = MagicMock(spec=jubilant.Task)
    mock_task.return_code = 0
    mock_task.stdout = "some results"
    mock_task.stderr = ""
    mocked_juju.exec.return_value = mock_task
    model = juju_utils.Model("test-model")

    results = await model.run_on_unit("test-unit/0", command)

    mocked_juju.exec.assert_called_once_with(command, unit="test-unit/0", wait=None)
    assert results == {"return-code": 0, "stdout": "some results", "stderr": ""}


@pytest.mark.asyncio
async def test_coumodel_run_on_unit_failed_command(mocked_juju):
    """Test Model run on unit with failed command."""
    command = "test-command"
    mock_task = MagicMock(spec=jubilant.Task)
    mock_task.return_code = 1
    mock_task.stdout = None
    mock_task.stderr = "Error!"
    mocked_juju.exec.side_effect = jubilant.TaskError(mock_task)
    model = juju_utils.Model("test-model")

    expected_err = "Command test-command failed with code 1, output None and error Error!"
    with pytest.raises(CommandRunFailed, match=expected_err):
        await model.run_on_unit("test-unit/0", command)

    mocked_juju.exec.assert_called_once_with(command, unit="test-unit/0", wait=None)


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.logger")
@patch("cou.utils.juju_utils.Model._run_update_status_hook")
@patch("cou.utils.juju_utils.Model._dispatch_update_status_hook")
async def test_coumodel_update_status_use_dispatch(
    use_dispatch, use_hooks, mocked_logger, mocked_juju
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
    use_dispatch, use_hooks, mocked_logger, mocked_juju
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
async def test_coumodel_update_status_use_hooks(
    use_dispatch, use_hooks, mocked_logger, mocked_juju
):
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
    use_dispatch, use_hooks, mocked_logger, mocked_juju
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
async def test_coumodel_update_status_skipped(use_dispatch, use_hooks, mocked_logger, mocked_juju):
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
async def test_coumodel_set_application_configs(mocked_juju):
    """Test Model set application configuration."""
    test_config = {"test-key": "test-value"}
    model = juju_utils.Model("test-model")

    await model.set_application_config("test-app", test_config)

    mocked_juju.config.assert_called_once_with("test-app", test_config)


@pytest.mark.asyncio
async def test_coumodel_scp_from_unit(mocked_juju):
    """Test Model scp from unit to destination."""
    source, destination = "/tmp/source", "/tmp/destination"
    model = juju_utils.Model("test-model")

    await model.scp_from_unit("test-unit/0", source, destination)

    mocked_juju.scp.assert_called_once_with("test-unit/0:/tmp/source", destination, scp_options=[])


@pytest.mark.asyncio
async def test_coumodel_upgrade_charm(mocked_juju):
    """Test Model upgrade application."""
    application_name = "test-app"
    channel = "latest/edge"
    model = juju_utils.Model("test-model")

    await model.upgrade_charm(application_name, channel)

    mocked_juju.refresh.assert_called_once_with(
        application_name,
        channel=channel,
        force=False,
        path=None,
        revision=None,
    )


@pytest.mark.asyncio
async def test_coumodel_upgrade_charm_with_switch(mocked_juju):
    """Test Model upgrade application with switch (crossgrade)."""
    application_name = "test-app"
    switch = "ch:new-charm"
    channel = "latest/edge"
    model = juju_utils.Model("test-model")

    await model.upgrade_charm(application_name, channel=channel, switch=switch)

    mocked_juju.cli.assert_called_once_with(
        "refresh", application_name, "--switch", switch, "--channel", channel
    )


@pytest.mark.asyncio
async def test_coumodel_upgrade_charm_with_switch_and_force(mocked_juju):
    """Test Model upgrade application with switch and force flags."""
    application_name = "test-app"
    switch = "ch:new-charm"
    model = juju_utils.Model("test-model")

    # exercise branch where force_units True adds force flags
    await model.upgrade_charm(application_name, switch=switch, force_units=True)

    mocked_juju.cli.assert_called_once_with(
        "refresh",
        application_name,
        "--switch",
        switch,
        "--force",
        "--force-base",
        "--force-units",
    )


def test_get_error_callable():
    """Test _get_error_callable with different parameter combinations."""
    # Test with raise_on_error=True, raise_on_blocked=True
    error_callable = juju_utils.JubilantModelMixin._get_error_callable(True, True)
    mock_status = MagicMock()

    with (
        patch("cou.utils.juju_utils.jubilant.any_error", return_value=False) as mock_any_error,
        patch("cou.utils.juju_utils.jubilant.any_blocked", return_value=False) as mock_any_blocked,
    ):
        result = error_callable(mock_status, "app1", "app2")
        assert result is False
        mock_any_error.assert_called_once_with(mock_status, "app1", "app2")
        mock_any_blocked.assert_called_once_with(mock_status, "app1", "app2")

    # Test with raise_on_error=False, raise_on_blocked=False
    error_callable = juju_utils.JubilantModelMixin._get_error_callable(False, False)
    result = error_callable(mock_status, "app1", "app2")
    assert result is True  # Should return True when both conditions are disabled


def test_get_ready_callable():
    """Test _get_ready_callable with different status values."""
    mock_status = MagicMock()

    # Test with "active" status (default)
    ready_callable = juju_utils.JubilantModelMixin._get_ready_callable("active")
    with (
        patch("cou.utils.juju_utils.jubilant.all_active", return_value=True) as mock_all_active,
        patch(
            "cou.utils.juju_utils.jubilant.all_agents_idle", return_value=True
        ) as mock_agents_idle,
    ):
        result = ready_callable(mock_status, "app1", "app2")
        assert result is True
        mock_all_active.assert_called_once_with(mock_status, "app1", "app2")
        mock_agents_idle.assert_called_once_with(mock_status, "app1", "app2")

    # Test with "blocked" status
    ready_callable = juju_utils.JubilantModelMixin._get_ready_callable("blocked")
    with (
        patch("cou.utils.juju_utils.jubilant.all_blocked", return_value=True) as mock_all_blocked,
        patch(
            "cou.utils.juju_utils.jubilant.all_agents_idle", return_value=True
        ) as mock_agents_idle,
    ):
        result = ready_callable(mock_status, "app1", "app2")
        assert result is True
        mock_all_blocked.assert_called_once_with(mock_status, "app1", "app2")
        mock_agents_idle.assert_called_once_with(mock_status, "app1", "app2")

    # Test with "maintenance" status
    ready_callable = juju_utils.JubilantModelMixin._get_ready_callable("maintenance")
    with (
        patch(
            "cou.utils.juju_utils.jubilant.all_maintenance", return_value=True
        ) as mock_all_maintenance,
        patch(
            "cou.utils.juju_utils.jubilant.all_agents_idle", return_value=True
        ) as mock_agents_idle,
    ):
        result = ready_callable(mock_status, "app1", "app2")
        assert result is True
        mock_all_maintenance.assert_called_once_with(mock_status, "app1", "app2")
        mock_agents_idle.assert_called_once_with(mock_status, "app1", "app2")

    # Test with "waiting" status
    ready_callable = juju_utils.JubilantModelMixin._get_ready_callable("waiting")
    with (
        patch("cou.utils.juju_utils.jubilant.all_waiting", return_value=True) as mock_all_waiting,
        patch(
            "cou.utils.juju_utils.jubilant.all_agents_idle", return_value=True
        ) as mock_agents_idle,
    ):
        result = ready_callable(mock_status, "app1", "app2")
        assert result is True
        mock_all_waiting.assert_called_once_with(mock_status, "app1", "app2")
        mock_agents_idle.assert_called_once_with(mock_status, "app1", "app2")

    # Test with "error" status
    ready_callable = juju_utils.JubilantModelMixin._get_ready_callable("error")
    with (
        patch("cou.utils.juju_utils.jubilant.all_error", return_value=True) as mock_all_error,
        patch(
            "cou.utils.juju_utils.jubilant.all_agents_idle", return_value=True
        ) as mock_agents_idle,
    ):
        result = ready_callable(mock_status, "app1", "app2")
        assert result is True
        mock_all_error.assert_called_once_with(mock_status, "app1", "app2")
        mock_agents_idle.assert_called_once_with(mock_status, "app1", "app2")


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
    mocked_jubilant_juju,
):
    """Test Model wait for related apps to be active idle."""
    model = juju_utils.Model("test-model")
    mock_get_supported_apps.return_value = ["app1", "app2"]

    # Create mock callables that return functions
    ready_func = MagicMock(return_value=True)
    error_func = MagicMock(return_value=False)
    model._get_ready_callable = MagicMock(return_value=ready_func)
    model._get_error_callable = MagicMock(return_value=error_func)

    await model.wait_for_idle(
        timeout=timeout,
        status=status,
        raise_on_error=raise_on_error,
        raise_on_blocked=raise_on_blocked,
    )

    model._get_ready_callable.assert_called_once_with(status)
    model._get_error_callable.assert_called_once_with(raise_on_error, raise_on_blocked)

    # Verify wait was called once with the correct arguments
    mocked_jubilant_juju.wait.assert_called_once()
    call_args = mocked_jubilant_juju.wait.call_args
    assert call_args.kwargs["successes"] == 10
    assert "ready" in call_args.kwargs
    assert "error" in call_args.kwargs
    assert callable(call_args.kwargs["ready"])
    assert callable(call_args.kwargs["error"])

    # Test that the lambda functions pass the right arguments to the callables
    mock_status = MagicMock()
    ready_lambda = call_args.kwargs["ready"]
    error_lambda = call_args.kwargs["error"]

    # Call the lambda functions to verify they pass the right arguments
    ready_lambda(mock_status)
    error_lambda(mock_status)

    # Verify the callables were called with status and the apps
    ready_func.assert_called_once_with(mock_status, "app1", "app2")
    error_func.assert_called_once_with(mock_status, "app1", "app2")


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.Model._get_supported_apps")
async def test_coumodel_wait_for_idle_apps(
    mock_get_supported_apps,
    mocked_jubilant_juju,
):
    """Test Model wait for specific apps to be active idle."""
    timeout = 60
    model = juju_utils.Model("test-model")

    # Create mock callables that return functions
    ready_func = MagicMock(return_value=True)
    error_func = MagicMock(return_value=False)
    model._get_ready_callable = MagicMock(return_value=ready_func)
    model._get_error_callable = MagicMock(return_value=error_func)

    await model.wait_for_idle(timeout, apps=["app1"])

    # Verify wait was called once with the correct arguments
    mocked_jubilant_juju.wait.assert_called_once()
    call_args = mocked_jubilant_juju.wait.call_args
    assert call_args.kwargs["successes"] == 10
    assert "ready" in call_args.kwargs
    assert "error" in call_args.kwargs
    assert callable(call_args.kwargs["ready"])
    assert callable(call_args.kwargs["error"])

    # Test that the lambda functions pass the right arguments to the callables
    mock_status = MagicMock()
    ready_lambda = call_args.kwargs["ready"]
    error_lambda = call_args.kwargs["error"]

    # Call the lambda functions to verify they pass the right arguments
    ready_lambda(mock_status)
    error_lambda(mock_status)

    # Verify the callables were called with status and the specific app
    ready_func.assert_called_once_with(mock_status, "app1")
    error_func.assert_called_once_with(mock_status, "app1")

    # When specific apps are provided, _get_supported_apps should not be called
    mock_get_supported_apps.assert_not_awaited()


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.Model._get_supported_apps")
async def test_coumodel_wait_for_idle_timeout(
    mock_get_supported_apps,
    mocked_jubilant_juju,
):
    """Test Model wait for model to be active idle reach timeout."""
    timeout = 1
    exp_apps = ["app1", "app2"]

    # Make the jubilant wait method raise a TimeoutError to simulate timeout
    mocked_jubilant_juju.wait.side_effect = TimeoutError("Timeout waiting for apps")

    model = juju_utils.Model("test-model")

    # Create mock callables that return functions
    ready_func = MagicMock(return_value=True)
    error_func = MagicMock(return_value=False)
    model._get_ready_callable = MagicMock(return_value=ready_func)
    model._get_error_callable = MagicMock(return_value=error_func)

    with pytest.raises(WaitForApplicationsTimeout):
        await model.wait_for_idle(timeout, apps=exp_apps)

    # Verify wait was called multiple times due to retry logic before timeout
    assert mocked_jubilant_juju.wait.call_count >= 1

    # When specific apps are provided, _get_supported_apps should not be called
    mock_get_supported_apps.assert_not_awaited()


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.asyncio.sleep", new=AsyncMock())
async def test_wait_for_idle_jubilant_waiterror_conversion(
    mocked_jubilant_juju,
):
    """Test that jubilant.WaitError is converted to WaitForApplicationsTimeout."""
    # Create a real jubilant.WaitError instance
    wait_error = jubilant.WaitError("Jubilant wait failed")

    # Make mocked_jubilant_juju.wait raise the real WaitError
    mocked_jubilant_juju.wait.side_effect = wait_error

    model = juju_utils.Model("test-model")

    # Create mock callables
    ready_func = MagicMock(return_value=True)
    error_func = MagicMock(return_value=False)
    model._get_ready_callable = MagicMock(return_value=ready_func)
    model._get_error_callable = MagicMock(return_value=error_func)

    with pytest.raises(WaitForApplicationsTimeout) as exc_info:
        await model.wait_for_idle(timeout=1, apps=["app1"])

    # Verify the original error message is preserved
    assert "Jubilant wait failed" in str(exc_info.value)
    # Verify mocked_jubilant_juju.wait was called
    mocked_jubilant_juju.wait.assert_called_once()


def _generate_unit_status(app: str, unit_id: int, machine_id: str, subordinates=None):
    """Generate a mock jubilant UnitStatus."""
    status = MagicMock()
    status.machine = machine_id
    status.subordinates = subordinates or {}
    status.workload_status.version = "20.04"
    return f"{app}/{unit_id}", status


def _generate_app_status(units, charm_name="app", base_channel="20.04/stable"):
    """Generate a mock jubilant AppStatus."""
    status = MagicMock()
    status.units = units
    if base_channel:
        status.base = jubilant.statustypes.FormattedBase(name="ubuntu", channel=base_channel)
    else:
        status.base = None
    status.charm_name = charm_name
    return status


@pytest.mark.asyncio
async def test_get_machines(mocked_juju):
    """Test Model getting machines from model."""
    expected_machines = {
        "0": juju_utils.Machine("0", (("my_app1", "app1"), ("my_app2", "app2")), "zone-1"),
        "1": juju_utils.Machine("1", (("my_app1", "app1"),), "zone-2"),
        "2": juju_utils.Machine("2", (("my_app1", "app1"),), "zone-3"),
    }

    # Build jubilant status mock
    mock_status = MagicMock()

    # Set up machine statuses with hardware strings
    mock_machines = {}
    for i in range(3):
        m = MagicMock()
        m.hardware = f"arch=amd64 availability-zone=zone-{i + 1}"
        mock_machines[str(i)] = m
    mock_status.machines = mock_machines

    # Set up app statuses with units on machines
    unit_0a = MagicMock()
    unit_0a.machine = "0"
    unit_1a = MagicMock()
    unit_1a.machine = "1"
    unit_2a = MagicMock()
    unit_2a.machine = "2"
    unit_0b = MagicMock()
    unit_0b.machine = "0"

    app1_status = MagicMock()
    app1_status.charm_name = "app1"
    app1_status.units = {"my_app1/0": unit_0a, "my_app1/1": unit_1a, "my_app1/2": unit_2a}

    app2_status = MagicMock()
    app2_status.charm_name = "app2"
    app2_status.units = {"my_app2/0": unit_0b}

    mock_status.apps = {"my_app1": app1_status, "my_app2": app2_status}
    mocked_juju.status.return_value = mock_status

    model = juju_utils.Model("test-model")
    machines = await model._get_machines(mock_status)

    assert machines == expected_machines


@pytest.mark.asyncio
@patch("cou.utils.juju_utils.Model.get_status")
@patch("cou.utils.juju_utils.Model._get_machines")
async def test_get_applications(mock_get_machines, mock_get_status, mocked_juju):
    """Test Model getting applications from model."""
    exp_apps = ["app1", "app2", "app3", "app4"]
    exp_machines = {
        "0": juju_utils.Machine("0", ()),
        "1": juju_utils.Machine("1", ()),
        "2": juju_utils.Machine("2", ()),
    }

    # Build unit statuses
    def make_unit(machine_id, subordinates=None):
        u = MagicMock()
        u.machine = machine_id
        u.subordinates = subordinates or {}
        u.workload_status.version = "20.04"
        return u

    app_units = {
        "app1": {f"app1/{i}": make_unit(str(i)) for i in range(3)},
        "app2": {"app2/0": make_unit("0", subordinates={"app4/0": MagicMock()})},
        "app3": {"app3/0": make_unit("1")},
        "app4": {},
    }

    # Build app statuses
    mock_apps = {}
    for app_name in exp_apps:
        app_st = MagicMock()
        app_st.charm_name = app_name
        app_st.charm = f"ch:{app_name}"
        app_st.charm_origin = "ch"
        app_st.charm_channel = "stable/ussuri"
        app_st.can_upgrade_to = ""
        app_st.subordinate_to = []
        app_st.version = "20.04"
        app_st.units = app_units[app_name]
        app_st.base = jubilant.statustypes.FormattedBase(name="ubuntu", channel="20.04/stable")
        mock_apps[app_name] = app_st

    mock_status = MagicMock()
    mock_status.apps = mock_apps

    mock_get_status.return_value = mock_status
    mock_get_machines.return_value = exp_machines

    # Mock config and actions CLI calls
    mocked_juju.cli.side_effect = lambda *args, **kw: (
        json.dumps({"settings": {}}) if args[0] == "config" else json.dumps({})
    )

    model = juju_utils.Model("test-model")
    apps = await model.get_applications()

    assert set(apps.keys()) == set(exp_apps)
    assert len(apps["app1"].units) == 3
    assert len(apps["app2"].units) == 1
    assert len(apps["app3"].units) == 1
    assert len(apps["app4"].units) == 0


def test_unit_repr():
    unit = juju_utils.Unit(name="foo/0", machine=MagicMock(), workload_version="1")
    assert repr(unit) == "foo/0"


def test_subordinate_unit_repr():
    unit = juju_utils.SubordinateUnit(name="foo/0", charm="foo")
    assert repr(unit) == "foo/0"


@pytest.mark.asyncio
async def test_run_update_status_hook(mocked_juju):
    """Test Model _run_update_status hook."""
    mock_task = MagicMock(spec=jubilant.Task)
    mock_task.return_code = 0
    mock_task.stdout = ""
    mock_task.stderr = ""
    mocked_juju.exec.return_value = mock_task
    model = juju_utils.Model("test-model")
    await model._run_update_status_hook("test-unit/0")
    mocked_juju.exec.assert_called_once_with("hooks/update-status", unit="test-unit/0", wait=None)


@pytest.mark.asyncio
async def test_dispatch_update_status_hook(mocked_juju):
    """Test Model _dispatch_update_status hook."""
    mock_task = MagicMock(spec=jubilant.Task)
    mock_task.return_code = 0
    mock_task.stdout = ""
    mock_task.stderr = ""
    mocked_juju.exec.return_value = mock_task
    model = juju_utils.Model("test-model")
    await model._dispatch_update_status_hook("test-unit/0")
    mocked_juju.exec.assert_called_once_with(
        "JUJU_DISPATCH_PATH=hooks/update-status ./dispatch", unit="test-unit/0", wait=None
    )


@pytest.mark.asyncio
async def test_coumodel_resolve_all(mocked_juju):
    """Test Model resolve all units in error."""
    model = juju_utils.Model("test-model")
    await model.resolve_all()
    mocked_juju.cli.assert_called_once_with("resolve", "--all")


@pytest.mark.asyncio
async def test_get_application_names(mocked_juju):
    model = juju_utils.Model("test-model")
    mock_status = MagicMock()
    mock_status.apps = {
        "app1": MagicMock(charm_name="target_charm_name"),
        "app2": MagicMock(charm_name="target_charm_name"),
        "app3": MagicMock(charm_name="not_target_charm_name"),
    }
    mocked_juju.status.return_value = mock_status

    names = await model.get_application_names("target_charm_name")
    assert names == ["app1", "app2"]


@pytest.mark.asyncio
async def test_get_application_names_failed(mocked_juju):
    model = juju_utils.Model("test-model")
    mock_status = MagicMock()
    mock_status.apps = {
        "app1": MagicMock(charm_name="other"),
        "app2": MagicMock(charm_name="other"),
    }
    mocked_juju.status.return_value = mock_status
    mocked_juju.show_model.return_value.short_name = "mocked-model"

    with pytest.raises(
        ApplicationNotFound,
        match="Cannot find 'app1_charm_name' charm in model",
    ):
        await model.get_application_names("app1_charm_name")


@pytest.mark.asyncio
async def test_coumodel_get_application_status(mocked_juju):
    model = juju_utils.Model("test-model")
    mock_app_status = MagicMock()
    mock_status = MagicMock()
    mock_status.apps = {
        "app1": mock_app_status,
        "app2": MagicMock(),
        "app3": MagicMock(),
    }
    mocked_juju.status.return_value = mock_status

    status = await model.get_application_status(app_name="app1")
    assert status is mock_app_status


@pytest.mark.asyncio
async def test_coumodel_get_application_status_failed(mocked_juju):
    model = juju_utils.Model("test-model")
    mock_status = MagicMock()
    mock_status.apps = {
        "app1": MagicMock(),
        "app2": MagicMock(),
    }
    mocked_juju.status.return_value = mock_status
    mocked_juju.show_model.return_value.short_name = "mocked-model"

    with pytest.raises(
        ApplicationNotFound,
        match="Cannot find 'app-not-exists' in model",
    ):
        await model.get_application_status(app_name="app-not-exists")


@pytest.mark.asyncio
async def test_get_applications_actions_clierror(mocked_juju, monkeypatch):
    """Test that get_applications handles jubilant.CLIError for actions gracefully."""
    # prepare status and machines similar to other tests
    mock_status = MagicMock()
    app_st = MagicMock()
    app_st.charm_name = "appx"
    app_st.charm = "ch:appx"
    app_st.charm_origin = "ch"
    app_st.charm_channel = "stable/ussuri"
    app_st.can_upgrade_to = ""
    app_st.subordinate_to = []
    app_st.version = "20.04"
    app_st.units = {}
    app_st.base = jubilant.statustypes.FormattedBase(name="ubuntu", channel="20.04/stable")

    mock_status.apps = {"appx": app_st}

    # _get_machines should return empty mapping
    monkeypatch.setattr(juju_utils.Model, "get_status", AsyncMock(return_value=mock_status))
    monkeypatch.setattr(juju_utils.Model, "_get_machines", AsyncMock(return_value={}))

    # config should return valid json, but actions will raise CLIError
    def _cli_side_effect(*args, **kwargs):
        if args[0] == "config":
            return json.dumps({"settings": {}})
        if args[0] == "actions":
            raise jubilant.CLIError(1, ["juju"], "", "no actions")
        return json.dumps({})

    mocked_juju.cli.side_effect = _cli_side_effect

    model = juju_utils.Model("test-model")
    apps = await model.get_applications()

    # Ensure application exists and actions defaulted to empty dict
    assert "appx" in apps
    assert apps["appx"].actions == {}


@pytest.mark.asyncio
async def test_get_application_config_failure_raises(mocked_juju):
    """Test that get_application_config converts CLIError into ApplicationNotFound."""
    mocked_juju.cli.side_effect = jubilant.CLIError(1, ["juju"], "", "error")
    model = juju_utils.Model("test-model")

    with pytest.raises(ApplicationNotFound, match="Application not-found was not found"):
        # name used in message doesn't need to exist in status; check message formatting
        await model.get_application_config("not-found")


def test_get_applications_by_charm_name_not_found():
    """Test get_applications_by_charm_name raises when not found."""
    apps = [MagicMock(charm="foo"), MagicMock(charm="bar")]

    with pytest.raises(ApplicationNotFound, match="Application with 'baz' not found"):
        juju_utils.get_applications_by_charm_name(apps, "baz")
