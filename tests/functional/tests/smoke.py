import logging
import os
import unittest
from pathlib import Path
from subprocess import STDOUT, CalledProcessError, check_call, check_output

import zaza

log = logging.getLogger(__name__)


class SmokeTest(unittest.TestCase):
    """COU smoke functional tests."""

    @classmethod
    def setUpClass(cls) -> None:
        zaza.get_or_create_libjuju_thread()
        cls.create_local_share_folder()
        cls.model_name = zaza.model.get_juju_model()
        cls.install_package()

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
            log.info(f"Installing {cou_test_snap}")
            assert Path(cou_test_snap).is_file()
            # install the snap
            assert check_call(f"sudo snap install --dangerous {cou_test_snap}".split()) == 0
            # connect interfaces
            interfaces_to_connect = [
                "juju-client-observe",
                "dot-local-share-cou",
                "ssh-public-keys",
            ]
            for interface in interfaces_to_connect:
                assert (
                    check_call(
                        f"sudo snap connect charmed-openstack-upgrader:{interface} snapd".split()
                    )
                    == 0
                )
            # make the cou alias
            assert check_call("sudo snap alias charmed-openstack-upgrader.cou cou".split()) == 0

            # check that the executable path exists
            assert Path("/snap/bin/cou").exists()
            cls.exc_path = "/snap/bin/cou"

        else:
            # functest already installs cou as python package, but we install again
            # for better developer experience
            log.warning("using cou as python package")
            assert check_call(f"python3 -m pip install {os.getenv('PYTHONPATH')}".split()) == 0
            cls.exc_path = "cou"

    def remove_snap_package() -> None:
        """Remove cou package."""
        if os.environ.get("TEST_SNAP"):
            log.info("Removing snap package cou")
            check_call("sudo snap remove charmed-openstack-upgrader --purge".split())

    def cou(self, cmd: list[str]) -> str:
        """Run cou commands.

        :param cmd: Command to run.
        :type cmd: list[str]
        :return: Response of the command with the stderr on stdout.
        :rtype: str
        """
        try:
            return check_output([self.exc_path] + cmd, stderr=STDOUT).decode()
        except CalledProcessError as err:
            log.error(err.output)

    def test_plan_backup(self) -> None:
        """Test plan with backup."""
        result = self.cou(["plan"])
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
        result = self.cou(["plan", "--no-backup"])
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

    def test_plan_no_backup_choosing_model(self) -> None:
        result = self.cou(["plan", "--model", self.model_name, "--no-backup"])
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