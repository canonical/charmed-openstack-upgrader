"""Generic setup for functional tests."""
import asyncio
import logging
import os
import unittest

from cou.steps.backup import backup

logger = logging.getLogger(__name__)


class BackupTest(unittest.TestCase):
    """Code for backup test."""

    def test_backup(self):
        """Backup Test."""
        logger.info("Running backup test....")
        backup_file = asyncio.run(backup())
        logger.info("Backup file: %s", backup_file)
        assert os.path.getsize(backup_file) > 0
        self.addCleanup(os.remove, backup_file)
