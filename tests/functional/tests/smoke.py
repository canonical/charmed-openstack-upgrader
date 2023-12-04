import logging
import os
import unittest
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess, check_call, run

import zaza

log = logging.getLogger(__name__)


class SmokeTest(unittest.TestCase):
    """COU smoke functional tests."""

    @classmethod
    def setUpClass(cls) -> None:
        zaza.get_or_create_libjuju_thread()
        cls.create_local_share_folder()
        cls.model_name = zaza.model.get_juju_model()
        cls.package_installed = False
        cls.install_package()
        cls.package_installed = True

    @classmethod
    def tearDownClass(cls) -> None:
        cls.remove_snap_package()
        zaza.clean_up_libjuju_thread()

    def create_local_share_folder() -> None:
        """Create the .local/share/ folder if does not exist."""
        Path(f"/home/{os.getenv('USER')}/.local/share/").mkdir(parents=True, exist_ok=True)

    @classmethod
    def install_package(cls) -> None:
        """Install cou package."""
        cou_test_snap = os.environ.get("TEST_SNAP")
        if cou_test_snap:
            log.info("Installing %s", cou_test_snap)
            assert Path(cou_test_snap).is_file(), f"{cou_test_snap} is not file"
            # install the snap
            assert (
                check_call(["sudo", "snap", "install", "--dangerous", cou_test_snap]) == 0
            ), "cou snap installation failed"
            # connect interfaces
            interfaces_to_connect = [
                "juju-client-observe",
                "dot-local-share-cou",
                "ssh-public-keys",
            ]
            for interface in interfaces_to_connect:
                check_call(
                    [
                        "sudo",
                        "snap",
                        "connect",
                        f"charmed-openstack-upgrader:{interface}",
                        "snapd",
                    ]
                )

            # make the cou alias
            check_call(["sudo", "snap", "alias", "charmed-openstack-upgrader.cou", "cou"])

            # check that the executable path exists
            assert Path("/snap/bin/cou").exists()
            cls.exc_path = "/snap/bin/cou"

        else:
            # functest already installs cou as python package
            log.warning("using cou as python package")
            cls.exc_path = os.getenv("TEST_PYTHON_PACKAGE") + "/bin/cou"

        log.info("Using cou path: %s", cls.exc_path)

    @classmethod
    def remove_snap_package(cls) -> None:
        """Remove cou package."""
        if os.environ.get("TEST_SNAP") and cls.package_installed:
            log.info("Removing snap package cou")
            check_call(["sudo", "snap", "remove", "charmed-openstack-upgrader", "--purge"])

    def cou(self, cmd: list[str]) -> CompletedProcess:
        """Run cou commands.

        :param cmd: Command to run.
        :type cmd: list[str]
        :return: Response of the command with the stderr on stdout.
        :rtype: str
        """
        try:
            return run([self.exc_path] + cmd, capture_output=True, text=True)
        except CalledProcessError as err:
            log.error(err.output)

    def test_plan_default(self) -> None:
        """Test plan with backup."""
        result = self.cou(["plan", "--model", self.model_name]).stdout
        expected_plan = (
            "Upgrade cloud from 'ussuri' to 'victoria'\n"
            "\tVerify that all OpenStack applications are in idle state\n"
            "\tBackup mysql databases\n"
            "\tControl Plane principal(s) upgrade plan\n"
            "\t\tUpgrade plan for 'designate-bind' to victoria\n"
            "\t\t\tUpgrade software packages of 'designate-bind' "
            "from the current APT repositories\n"
            "\t\t\tUpgrade 'designate-bind' to the new channel: 'victoria/stable'\n"
            "\t\t\tWait 300s for app designate-bind to reach the idle state.\n"
            "\t\t\tCheck if the workload of 'designate-bind' has been upgraded\n"
        )
        self.assertIn(expected_plan, result)

    def test_plan_no_backup(self) -> None:
        """Test plan with no backup."""
        result = self.cou(["plan", "--model", self.model_name, "--no-backup"]).stdout
        expected_plan = (
            "Upgrade cloud from 'ussuri' to 'victoria'\n"
            "\tVerify that all OpenStack applications are in idle state\n"
            "\tControl Plane principal(s) upgrade plan\n"
            "\t\tUpgrade plan for 'designate-bind' to victoria\n"
            "\t\t\tUpgrade software packages of 'designate-bind' "
            "from the current APT repositories\n"
            "\t\t\tUpgrade 'designate-bind' to the new channel: 'victoria/stable'\n"
            "\t\t\tWait 300s for app designate-bind to reach the idle state.\n"
            "\t\t\tCheck if the workload of 'designate-bind' has been upgraded\n"
        )
        self.assertIn(expected_plan, result)
