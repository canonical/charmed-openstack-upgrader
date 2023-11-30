import logging
import os
import unittest
from subprocess import check_call, check_output

import zaza

log = logging.getLogger(__name__)


class COUSmokeTest(unittest.TestCase):
    """COU smoke functional tests."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.model_name = zaza.model.get_juju_model()
        cls.install_package()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.remove_package()

    def install_package() -> None:
        """Install cou package."""
        cou_test_snap = os.environ.get("TEST_SNAP")
        if cou_test_snap:
            log.info(f"Installing {cou_test_snap}")
            assert os.path.isfile(cou_test_snap)
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

            assert check_output("which cou".split()).decode().strip() == os.path.join(
                "/snap/bin/cou"
            )
        else:
            log.warning("Installing python package")
            assert check_call("python3 -m pip install .".split()) == 0
            assert (
                check_output("which cou".split())
                .decode()
                .strip()
                .startswith(os.path.join(os.getcwd(), ".tox"))
            )

    def remove_package() -> None:
        """Remove cou package."""
        cou_test_snap = os.environ.get("TEST_SNAP")
        if cou_test_snap:
            log.info("Removing snap package cou")
            check_call("sudo snap remove charmed-openstack-upgrader --purge".split())
        else:
            logging.info("Uninstalling python package cou")
            check_call("python3 -m pip uninstall --yes charmed-openstack-upgrader".split())

    def test_plan_backup(self) -> None:
        """Test plan with backup."""
        result = check_output("cou plan".split()).decode()
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
        result = check_output("cou plan --no-backup".split()).decode()
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
        result = check_output(f"cou plan --model {self.model_name} --no-backup".split()).decode()
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

    def test_help(self) -> None:
        """Test that help is working."""
        assert check_call("cou --help".split()) == 0
        assert check_call("cou -h".split()) == 0
        assert check_call("cou plan --help".split()) == 0
        assert check_call("cou plan -h".split()) == 0
        assert check_call("cou run --help".split()) == 0
        assert check_call("cou run -h".split()) == 0

    def test_version(self) -> None:
        """Test that version is working."""
        assert check_call("cou --version".split()) == 0
        assert check_call("cou -V".split()) == 0
