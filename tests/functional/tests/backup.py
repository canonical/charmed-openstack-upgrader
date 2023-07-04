"""Generic setup for functional tests."""
import logging
import os
import unittest

import zaza

from cou.steps.backup import backup

logger = logging.getLogger(__name__)


class BackupTest(unittest.TestCase):
    """Code for backup test."""

    def test_backup(self):
        """Backup Test."""
        logger.info("Running backup test....")
        sync_backup = zaza.sync_wrapper(backup)
        zaza.get_or_create_libjuju_thread()
        backup_file = sync_backup()
        logger.info("Backup file: %s", backup_file)
        assert os.path.getsize(backup_file) > 0
        self.addCleanup(os.remove, backup_file)
