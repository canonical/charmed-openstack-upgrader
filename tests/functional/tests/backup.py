"""Generic setup for functional tests."""
import logging
import os

import pytest

from cou.steps.backup import backup

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_backup(self):
    """Backup Test."""
    logger.info("Running backup test....")
    backup_file = await backup()
    logger.info("Backup file: %s", backup_file)
    assert os.path.getsize(backup_file) > 0
    self.addCleanup(os.remove, backup_file)
