import logging
import os
import unittest

import zaza
import zaza.model

from cou.utils.juju_utils import COUModel

log = logging.getLogger(__name__)

TESTED_APP = "rabbitmq-server"
TESTED_UNIT = f"{TESTED_APP}/0"


class COUModelTest(unittest.TestCase):
    """COUModel functional tests."""

    def setUp(self) -> None:
        zaza.get_or_create_libjuju_thread()
        model_name = zaza.model.get_juju_model()
        self.model = COUModel(model_name)

    def tearDown(self) -> None:
        zaza.sync_wrapper(self.model._model.disconnect)()
        zaza.clean_up_libjuju_thread()

    def test_get_charm_name(self):
        """Test get charm name."""
        charm = zaza.sync_wrapper(self.model.get_charm_name)(TESTED_APP)
        self.assertEqual(TESTED_APP, charm)

    def test_get_status(self):
        """Test COUModel.get_status."""
        status = zaza.sync_wrapper(self.model.get_status)()
        self.assertIn(TESTED_APP, status.applications)

    def test_run_action(self):
        """Test run action."""
        action = zaza.sync_wrapper(self.model.run_action)(TESTED_UNIT, "cluster-status")
        self.assertEqual("completed", action.data["status"])
        self.assertIn("RabbitMQ", action.data["results"]["output"])

    def test_run_on_unit(self):
        """Test run command on unit."""
        results = zaza.sync_wrapper(self.model.run_on_unit)(TESTED_UNIT, "actions/cluster-status")
        self.assertIn("RabbitMQ", results["output"])

    def test_scp_from_unit(self):
        """Test copy file from unit."""
        tmp_dir = zaza.model.tempfile.gettempdir()
        test_file = "test.txt"
        path = f"/tmp/{test_file}"
        exp_path = os.path.join(tmp_dir, test_file)
        zaza.model.run_on_unit(unit_name=TESTED_UNIT, command=f"echo 'test' > {path}")

        zaza.sync_wrapper(self.model.scp_from_unit)(TESTED_UNIT, path, tmp_dir)
        self.assertTrue(os.path.exists(exp_path))

    def test_changing_app_configuration(self):
        """Test change of app configuration.

        This test covers set and get configuration option along with waiting for model to be idle.
        """
        original_config = {"enable-auto-restarts": "true"}
        new_config = {"enable-auto-restarts": "false"}
        self.addCleanup(zaza.model.set_application_config, TESTED_APP, original_config)
        self.addCleanup(zaza.model.wait_for_unit_idle, TESTED_UNIT)

        # changing configuration and validating it was changed
        zaza.sync_wrapper(self.model.set_application_config)(TESTED_APP, new_config)
        zaza.sync_wrapper(self.model.wait_for_idle)(120, apps=[TESTED_APP])
        config = zaza.sync_wrapper(self.model.get_application_config)(TESTED_APP)

        self.assertFalse(config["enable-auto-restarts"]["value"])

    def test_upgrade_charm(self):
        """Test upgrade charm to the latest revision of the current channel.

        This test only checks the results of such an upgrade operation.
        """
        status = zaza.model.get_status()
        # get the current channel, so we will not change it
        channel = status.applications[TESTED_APP].charm_channel
        zaza.sync_wrapper(self.model.upgrade_charm)(TESTED_APP, channel=channel)
        zaza.sync_wrapper(self.model.wait_for_idle)(120, apps=[TESTED_APP])
