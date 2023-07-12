"""Generic setup for functional tests."""
import logging
import os
import unittest

import zaza
import zaza.model as zazamodel

from cou.steps.backup import backup

logger = logging.getLogger(__name__)


class BackupTest(unittest.TestCase):
    """Code for backup test."""

    def test_backup(self):
        """Backup Test."""
        logger.info("Running backup test....")
        sync_backup = zaza.sync_wrapper(backup)
        model_zaza_working_on = zazamodel.get_juju_model()
        zaza.get_or_create_libjuju_thread()
        backup_file = sync_backup(model_zaza_working_on)
        logger.info("Backup file: %s", backup_file)
        assert os.path.getsize(backup_file) > 0
        self.addCleanup(os.remove, backup_file)
        self.addCleanup(zaza.clean_up_libjuju_thread)
