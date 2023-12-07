import logging
import os
import unittest
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess, check_call, run

import zaza

from cou.utils import COU_DATA

log = logging.getLogger(__name__)


class FuncSmokeException(Exception):
    """Default Func Smoke exception."""


class SmokeTest(unittest.TestCase):
    """COU smoke functional tests."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.create_local_share_folder()
        cls.model_name = zaza.model.get_juju_model()
        cls.configure_executable_path()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.remove_snap_package()

    def create_local_share_folder() -> None:
        """Create the .local/share/ folder if does not exist."""
        COU_DATA.mkdir(parents=True, exist_ok=True)

    @classmethod
    def configure_executable_path(cls) -> None:
        cls.snap_installed = False
        cou_snap = os.environ.get("TEST_SNAP")
        if cou_snap:
            cls.install_snap_package(cou_snap)
            cls.exc_path = "/snap/bin/cou"
            cls.snap_installed = True
        else:
            # functest already installs cou as python package
            log.warning("using cou as python package")
            cls.exc_path = os.getenv("TEST_PYTHON_PACKAGE") + "/bin/cou"

        log.info("Using cou path: %s", cls.exc_path)

    @classmethod
    def install_snap_package(cls, cou_snap: str) -> None:
        """Install cou snap package.

        :param cou_snap: Path to the cou snap.
        :type cou_snap: str
        """
        log.info("Installing %s", cou_snap)
        assert Path(cou_snap).is_file(), f"{cou_snap} is not file"

        # install the snap
        cls.snap_install_commands(
            ["sudo", "snap", "install", "--dangerous", cou_snap],
            "Cannot install the cou snap. Please check your permission",
        )

        # connect interfaces
        interfaces_to_connect = [
            "juju-client-observe",
            "dot-local-share-cou",
            "ssh-public-keys",
        ]
        for interface in interfaces_to_connect:
            cls.snap_install_commands(
                [
                    "sudo",
                    "snap",
                    "connect",
                    f"charmed-openstack-upgrader:{interface}",
                    "snapd",
                ],
                f"Cannot connect the interface: {interface}",
            )

        # make the cou alias
        cls.snap_install_commands(
            ["sudo", "snap", "alias", "charmed-openstack-upgrader.cou", "cou"],
            "Cannot create the cou alias",
        )

        # check that the executable path exists
        assert Path("/snap/bin/cou").exists(), "Cannot find the cou executable snap path."
        cls.exc_path = "/snap/bin/cou"

    def snap_install_commands(cmd: list[str], custom_err_msg: str):
        """Commands to run and install the cou snap.

        :param cmd: The command to be executed.
        :type cmd: list[str]
        :param custom_err_msg: Custom error message if the command fails.
        :type custom_err_msg: str
        :raises FuncSmokeException: When the command fails.
        """
        try:
            check_call(cmd)
        except CalledProcessError as err:
            raise FuncSmokeException(custom_err_msg) from err

    @classmethod
    def remove_snap_package(cls) -> None:
        """Remove cou package."""
        if cls.snap_installed:
            log.info("Removing snap package cou")
            check_call(["sudo", "snap", "remove", "charmed-openstack-upgrader", "--purge"])

    def cou(self, cmd: list[str]) -> CompletedProcess:
        """Run cou commands.

        :param cmd: Command to run.
        :type cmd: list[str]
        :return: Response of the command.
        :rtype: CompletedProcess
        """
        return run([self.exc_path] + cmd, capture_output=True, text=True)

    def generate_expected_plan(self, backup: bool = True) -> str:
        """Generate the expected plan for the smoke bundle.

        :param backup: Weather the plan should contains the backup, defaults to True
        :type backup: bool, optional
        :return: The upgrade plan.
        :rtype: str
        """
        backup_plan = "\tBackup mysql databases\n" if backup else ""
        return (
            "Upgrade cloud from 'ussuri' to 'victoria'\n"
            "\tVerify that all OpenStack applications are in idle state\n"
            f"{backup_plan}"
            "\tControl Plane principal(s) upgrade plan\n"
            "\t\tUpgrade plan for 'designate-bind' to victoria\n"
            "\t\t\tUpgrade software packages of 'designate-bind' "
            "from the current APT repositories\n"
            "\t\t\tUpgrade 'designate-bind' to the new channel: 'victoria/stable'\n"
            "\t\t\tWait 300s for app designate-bind to reach the idle state.\n"
            "\t\t\tCheck if the workload of 'designate-bind' has been upgraded\n"
            "\t\tUpgrade plan for 'mysql-innodb-cluster' to victoria\n"
            "\t\t\tUpgrade software packages of 'mysql-innodb-cluster' "
            "from the current APT repositories\n"
            "\t\t\tChange charm config of 'mysql-innodb-cluster' 'source' to "
            "'cloud:focal-victoria'\n"
            "\t\t\tWait 1800s for app mysql-innodb-cluster to reach the idle state.\n"
            "\t\t\tCheck if the workload of 'mysql-innodb-cluster' has been upgraded\n"
        )

    def test_plan_default(self) -> None:
        """Test plan with backup."""
        result = self.cou(["plan", "--model", self.model_name]).stdout
        expected_plan = self.generate_expected_plan()
        self.assertIn(expected_plan, result)

    def test_plan_no_backup(self) -> None:
        """Test plan with no backup."""
        result = self.cou(["plan", "--model", self.model_name, "--no-backup"]).stdout
        expected_plan = self.generate_expected_plan(backup=False)
        self.assertIn(expected_plan, result)

    def test_run(self) -> None:
        """Test cou run."""
        # designate-bind upgrades from ussuri to victoria
        expected_msg_before_upgrade = "Upgrade plan for 'designate-bind' to victoria"
        result_before_upgrade = self.cou(
            ["run", "--model", self.model_name, "--no-backup", "--no-interactive"]
        ).stdout
        self.assertIn(expected_msg_before_upgrade, result_before_upgrade)

        # designate-bind was upgraded to victoria and next step is to wallaby
        expected_msg_after_upgrade = "Upgrade plan for 'designate-bind' to wallaby"
        result_after = self.cou(["plan", "--model", self.model_name, "--no-backup"]).stdout
        self.assertIn(expected_msg_after_upgrade, result_after)
