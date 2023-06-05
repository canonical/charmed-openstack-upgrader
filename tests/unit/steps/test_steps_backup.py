from unittest import mock

from cou.steps.backup import backup


@mock.patch("cou.steps.backup.logging.info")
def test_backup(log):
    backup()
    assert log.call_count == 1
