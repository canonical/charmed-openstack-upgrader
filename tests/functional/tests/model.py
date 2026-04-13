import logging
import os
import unittest

from cou.utils.juju_utils import Model

log = logging.getLogger(__name__)

TESTED_APP = "designate-bind"
TESTED_UNIT = f"{TESTED_APP}/0"


class ModelTest(unittest.TestCase):
    """Model functional tests."""

    def setUp(self) -> None:
        import zaza.model

        model_name = zaza.model.get_juju_model()
        self.model = Model(model_name)

    def tearDown(self) -> None:
        pass  # jubilant is CLI-based; no persistent connection to tear down

    def test_connection(self):
        """Test model connection."""
        import asyncio

        asyncio.get_event_loop().run_until_complete(self.model.connect())
        self.assertTrue(self.model.connected)

    def test_get_charm_name(self):
        """Test get charm name."""
        import asyncio

        charm = asyncio.get_event_loop().run_until_complete(self.model.get_charm_name(TESTED_APP))
        self.assertEqual(TESTED_APP, charm)

    def test_get_status(self):
        """Test Model.get_status."""
        import asyncio

        status = asyncio.get_event_loop().run_until_complete(self.model.get_status())
        self.assertIn(TESTED_APP, status.apps)

    def test_run_action(self):
        """Test run action."""
        import asyncio

        action = asyncio.get_event_loop().run_until_complete(
            self.model.run_action(TESTED_UNIT, "resume")
        )
        self.assertEqual(0, action.return_code)
        self.assertEqual("completed", action.status)

    def test_run_on_unit(self):
        """Test run command on unit."""
        import asyncio

        results = asyncio.get_event_loop().run_until_complete(
            self.model.run_on_unit(TESTED_UNIT, "actions/resume")
        )
        self.assertIn("active", results["stdout"])

    def test_scp_from_unit(self):
        """Test copy file from unit."""
        import asyncio
        import tempfile

        tmp_dir = tempfile.gettempdir()
        test_file = "test.txt"
        path = f"/tmp/{test_file}"
        exp_path = os.path.join(tmp_dir, test_file)
        self.model._juju.exec(f"echo 'test' > {path}", unit=TESTED_UNIT)

        asyncio.get_event_loop().run_until_complete(
            self.model.scp_from_unit(TESTED_UNIT, path, tmp_dir)
        )
        self.assertTrue(os.path.exists(exp_path))

    def test_changing_app_configuration(self):
        """Test change of app configuration."""
        import asyncio

        original_config = {"debug": "false"}
        new_config = {"debug": "true"}

        asyncio.get_event_loop().run_until_complete(
            self.model.set_application_config(TESTED_APP, new_config)
        )
        asyncio.get_event_loop().run_until_complete(
            self.model.wait_for_idle(120, apps=[TESTED_APP])
        )
        config = asyncio.get_event_loop().run_until_complete(
            self.model.get_application_config(TESTED_APP)
        )
        self.assertTrue(config["debug"]["value"])

        # cleanup
        asyncio.get_event_loop().run_until_complete(
            self.model.set_application_config(TESTED_APP, original_config)
        )

    def test_upgrade_charm(self):
        """Test upgrade charm to the latest revision of the current channel."""
        import asyncio

        status = self.model._juju.status()
        channel = status.apps[TESTED_APP].charm_channel
        asyncio.get_event_loop().run_until_complete(
            self.model.upgrade_charm(TESTED_APP, channel=channel)
        )
        asyncio.get_event_loop().run_until_complete(
            self.model.wait_for_idle(120, apps=[TESTED_APP])
        )
