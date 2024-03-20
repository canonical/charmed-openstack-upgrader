"""Generic setup for functional tests."""

import logging
import os
import unittest
from unittest.mock import patch

import zaza

from cou.steps.backup import backup
from cou.utils import COU_DATA
from cou.utils.juju_utils import Model

logger = logging.getLogger(__name__)


class BackupTest(unittest.TestCase):
    """Code for backup test."""

    def setUp(self) -> None:
        zaza.get_or_create_libjuju_thread()
        model_name = zaza.model.get_juju_model()
        self.model = Model(model_name)
        zaza.sync_wrapper(self.model.connect)()

    def tearDown(self) -> None:
        zaza.sync_wrapper(self.model._model.disconnect)()
        zaza.clean_up_libjuju_thread()

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
