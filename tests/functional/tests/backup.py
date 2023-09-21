"""Generic setup for functional tests."""
import logging
import os
import unittest

import zaza
import zaza.model as zazamodel

from cou.steps.backup import backup
from cou.utils.juju_utils import COUModel

logger = logging.getLogger(__name__)


class BackupTest(unittest.TestCase):
    """Code for backup test."""

    def test_backup(self):
        """Backup Test."""
        zaza.get_or_create_libjuju_thread()
        sync_backup = zaza.sync_wrapper(backup)
        sync_create_model = zaza.sync_wrapper(COUModel.create)

        logger.info("Running backup test....")
        model_name = zazamodel.get_juju_model()
        model = sync_create_model(model_name)

        backup_file = sync_backup(model)
        logger.info("Backup file: %s", backup_file)
        assert os.path.getsize(backup_file) > 0
        self.addCleanup(os.remove, backup_file)
        self.addCleanup(zaza.clean_up_libjuju_thread)
