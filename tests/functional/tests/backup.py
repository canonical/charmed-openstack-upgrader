"""Generic setup for functional tests."""

import asyncio
import logging
import os
import unittest
from unittest.mock import patch

import zaza
import zaza.model

from cou.steps.backup import backup
from cou.utils import COU_DATA
from cou.utils.juju_utils import Model

logger = logging.getLogger(__name__)


class BackupTest(unittest.TestCase):
    """Code for backup test."""

    def setUp(self) -> None:
        model_name = zaza.model.get_juju_model()
        self.model = Model(model_name)
        asyncio.get_event_loop().run_until_complete(self.model.connect())

    def tearDown(self) -> None:
        pass  # jubilant is CLI-based; no persistent connection to tear down

    def test_backup(self):
        """Backup Test."""
        # create the COU_DATA path to place the backup file
        COU_DATA.mkdir(parents=True, exist_ok=True)
        sync_backup = zaza.sync_wrapper(backup)

        logger.info("Running backup test....")
        # NOTE(gabrielcocenza) mocking _check_db_relations to return True allows
        # backup test without the need of deploying a heavy OpenStack bundle.
        with patch("cou.steps.backup._check_db_relations") as mock_relations:
            mock_relations.return_value = True
            backup_file = sync_backup(self.model)
            logger.info("Backup file: %s", backup_file)
            assert os.path.getsize(backup_file) > 0
            self.addCleanup(os.remove, backup_file)
