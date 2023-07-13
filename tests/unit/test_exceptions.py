import pytest

from cou.exceptions import ActionFailed, CommandRunFailed, JujuError, UnitNotFound


def test_command_run_failed():
    with pytest.raises(CommandRunFailed):
        raise CommandRunFailed(cmd="cmd", code="1", output="nok", err="err")


def test_unit_not_found():
    with pytest.raises(UnitNotFound):
        raise UnitNotFound()


def test_juju_error():
    with pytest.raises(JujuError):
        raise JujuError()


def test_action_failed():
    with pytest.raises(ActionFailed):

        class TestClass:
            pass

        raise ActionFailed(action=TestClass(), output="output")
