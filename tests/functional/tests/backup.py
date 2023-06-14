"""Generic setup for functional tests."""
import logging
import os
import unittest

from cou.steps.backup import backup
from cou.zaza_utils import clean_up_libjuju_thread

logger = logging.getLogger(__name__)


class BackupTest(unittest.TestCase):
    """Code for backup test."""

    @classmethod
    def setUpClass(cls):
        """Run class setup for noop tests."""
        super(BackupTest, cls).setUpClass()

    def tearDown(self):
        """Close thread."""
        logger.info("Closing libjuju thread.")
        clean_up_libjuju_thread()

    def test_backup(self):
        """Backup Test."""
        logger.info("Running backup test....")
        backup_file = backup()
        logger.info("Backup file: %s", backup_file)
        assert os.path.getsize(backup_file) > 0
        self.addCleanup(os.remove, backup_file)
