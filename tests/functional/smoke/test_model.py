import logging

import pytest

log = logging.getLogger(__name__)

TESTED_APP = "keystone"
TESTED_UNIT = f"{TESTED_APP}/0"


@pytest.mark.abort_on_fail
@pytest.mark.skip_if_deployed
async def test_build_and_deploy(ops_test, channel, series):
    """Deploy bundle."""
    bundle = ops_test.render_bundle(
        "tests/functional/smoke/bundle.yaml.j2", channel=channel, series=series
    )
    await ops_test.model.deploy(bundle)
    await ops_test.model.wait_for_idle(timeout=600)


async def test_get_charm_name(model):
    """Test get charm name."""
    charm = await model.get_charm_name(TESTED_APP)
    assert charm == "keystone"


async def test_get_status(model):
    """Test COUModel.get_status."""
    status = await model.get_status()
    assert TESTED_APP in status.applications


async def test_run_action(model):
    """Test running action."""
    action = await model.run_action(TESTED_UNIT, "get-admin-password")
    results = action.data.get("results", {})
    assert results["admin-password"] == "func-smoke-tests"


async def test_run_on_unit(model):
    """Test run command on unit."""
    results = await model.run_on_unit(TESTED_UNIT, "actions/get-admin-password")
    assert results["admin-password"] == "func-smoke-tests"


async def test_scp_from_unit(ops_test, model):
    """Test copy file from unit."""
    test_file = "test.txt"
    path = f"/tmp/{test_file}"
    exp_path = ops_test.tmp_path / test_file

    await ops_test.model.units[TESTED_APP].run(f"echo 'test' > {path}")
    await model.scp_from_unit(TESTED_UNIT, path, ops_test.tmp_path)
    assert exp_path.exists()


async def test_changing_app_configuration(ops_test, model):
    """Test change of app configuration.

    This tests cover set and get configuration option along with waiting for model to be idle.
    """
    await model.set_application_config(TESTED_APP, {"debug": "true"})
    await ops_test.model.wait_for_idle()
    config = await model.get_application_config(TESTED_APP)
    assert config["debug"]["value"] is True
    # revert changes
    await model.set_application_config(TESTED_APP, {"debug": "false"})
    await ops_test.model.wait_for_idle()


async def test_upgrade_charm(ops_test, model, channel):
    """Test upgrade charm to already deployed channel.

    This test does not actually perform the update of the spell, but rather just the test results
    of such an operation.
    """
    await model.upgrade_charm(TESTED_APP, channel=channel)
    await ops_test.model.wait_for_idle()
