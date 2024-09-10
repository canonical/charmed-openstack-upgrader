# Copyright 2024 Canonical Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cou.exceptions import (
    ApplicationError,
    ApplicationNotFound,
    RunUpgradeError,
    UnitNotFound,
)
from cou.steps import ceph
from cou.utils.juju_utils import Application, Unit


@pytest.mark.asyncio
async def test_get_application(model) -> None:
    ceph_mon_1 = MagicMock(spec_set=Application)()
    ceph_mon_1.name = "ceph-mon-1"
    ceph_mon_1.charm = "ceph-mon"

    ceph_mon_2 = MagicMock(spec_set=Application)()
    ceph_mon_2.name = "ceph-mon-2"
    ceph_mon_2.charm = "ceph-mon"

    model.get_applications.return_value = {
        "ceph-mon-1": ceph_mon_1,
        "ceph-mon-2": ceph_mon_2,
    }
    ceph_mon_apps = await ceph._get_applications(model)
    assert len(ceph_mon_apps) == 2


@pytest.mark.asyncio
async def test_get_application_error(model) -> None:
    model.get_applications.return_value = {}

    with pytest.raises(ApplicationNotFound):
        await ceph._get_applications(model)


@pytest.mark.asyncio
async def test_get_unit_name(model) -> None:
    ceph_mon_1 = MagicMock(spec_set=Application)()
    ceph_mon_1.name = "ceph-mon"
    ceph_mon_unit = MagicMock(spec_set=Unit)()
    ceph_mon_unit.name = "ceph-mon/0"
    ceph_mon_1.units = {"ceph-mon/0": ceph_mon_unit}

    ceph_mon_unit_name = await ceph._get_unit_name(ceph_mon_1)
    assert ceph_mon_unit_name == "ceph-mon/0"


@pytest.mark.asyncio
async def test_get_unit_name_error(model) -> None:
    ceph_mon_1 = MagicMock(spec_set=Application)()
    ceph_mon_1.name = "ceph-mon"
    ceph_mon_1.units = {}

    with pytest.raises(UnitNotFound):
        await ceph._get_unit_name(ceph_mon_1)


@pytest.mark.asyncio
async def test_osd_noout(model) -> None:
    ceph_mon_1_unit = MagicMock(spec_set=Unit)()
    ceph_mon_1_unit.name = "ceph-mon-1/0"
    ceph_mon_1 = MagicMock(spec_set=Application)()
    ceph_mon_1.name = "ceph-mon-1"
    ceph_mon_1.charm = "ceph-mon"
    ceph_mon_1.units = {"ceph-mon-1/0": ceph_mon_1_unit}

    ceph_mon_2_unit = MagicMock(spec_set=Unit)()
    ceph_mon_2_unit.name = "ceph-mon-2/0"
    ceph_mon_2 = MagicMock(spec_set=Application)()
    ceph_mon_2.name = "ceph-mon-2"
    ceph_mon_2.charm = "ceph-mon"
    ceph_mon_2.units = {"ceph-mon-2/0": ceph_mon_2_unit}

    model.get_applications.return_value = {
        "ceph-mon-1": ceph_mon_1,
        "ceph-mon-2": ceph_mon_2,
    }

    await ceph.osd_noout(model, True)

    model.run_action.assert_awaited()
    assert model.run_action.await_count == 2


@pytest.mark.asyncio
async def test_osd_noout_no_ceph_mon_app(model) -> None:
    model.get_applications.return_value = {}

    await ceph.osd_noout(model, True)

    model.run_action.assert_not_awaited()


@pytest.mark.asyncio
async def test_osd_noout_no_ceph_mon_units(model) -> None:
    ceph_mon = MagicMock(spec_set=Application)()
    ceph_mon.name = "ceph-mon"
    ceph_mon.charm = "ceph-mon"
    ceph_mon.units = {}

    model.get_applications.return_value = {
        "ceph-mon": ceph_mon,
    }

    await ceph.osd_noout(model, True)

    model.run_action.assert_not_awaited()


@pytest.mark.asyncio
@patch("cou.steps.ceph.get_osd_noout_state")
async def test_assert_osd_noout_state_same(mock_get_osd_noout_state, model) -> None:
    ceph_mon_1_unit = MagicMock(spec_set=Unit)()
    ceph_mon_1_unit.name = "ceph-mon-1/0"
    ceph_mon_1 = MagicMock(spec_set=Application)()
    ceph_mon_1.name = "ceph-mon-1"
    ceph_mon_1.charm = "ceph-mon"
    ceph_mon_1.units = {"ceph-mon-1/0": ceph_mon_1_unit}

    ceph_mon_2_unit = MagicMock(spec_set=Unit)()
    ceph_mon_2_unit.name = "ceph-mon-2/0"
    ceph_mon_2 = MagicMock(spec_set=Application)()
    ceph_mon_2.name = "ceph-mon-2"
    ceph_mon_2.charm = "ceph-mon"
    ceph_mon_2.units = {"ceph-mon-2/0": ceph_mon_2_unit}

    model.get_applications.return_value = {
        "ceph-mon-1": ceph_mon_1,
        "ceph-mon-2": ceph_mon_2,
    }

    mock_get_osd_noout_state.return_value = True
    await ceph.assert_osd_noout_state(model, True)


@pytest.mark.asyncio
@patch("cou.steps.ceph.get_osd_noout_state")
async def test_assert_osd_noout_state_different(mock_get_osd_noout_state, model) -> None:
    ceph_mon_1_unit = MagicMock(spec_set=Unit)()
    ceph_mon_1_unit.name = "ceph-mon-1/0"
    ceph_mon_1 = MagicMock(spec_set=Application)()
    ceph_mon_1.name = "ceph-mon-1"
    ceph_mon_1.charm = "ceph-mon"
    ceph_mon_1.units = {"ceph-mon-1/0": ceph_mon_1_unit}

    ceph_mon_2_unit = MagicMock(spec_set=Unit)()
    ceph_mon_2_unit.name = "ceph-mon-2/0"
    ceph_mon_2 = MagicMock(spec_set=Application)()
    ceph_mon_2.name = "ceph-mon-2"
    ceph_mon_2.charm = "ceph-mon"
    ceph_mon_2.units = {"ceph-mon-2/0": ceph_mon_2_unit}

    model.get_applications.return_value = {
        "ceph-mon-1": ceph_mon_1,
        "ceph-mon-2": ceph_mon_2,
    }

    mock_get_osd_noout_state.return_value = False
    with pytest.raises(ApplicationError):
        await ceph.assert_osd_noout_state(model, True)


@pytest.mark.asyncio
@patch("cou.steps.ceph.get_osd_noout_state")
async def test_assert_osd_noout_state_no_app(mock_get_osd_noout_state, model) -> None:
    model.get_applications.return_value = {}

    await ceph.assert_osd_noout_state(model, True)

    mock_get_osd_noout_state.assert_not_awaited()


@pytest.mark.asyncio
@patch("cou.steps.ceph.get_osd_noout_state")
async def test_assert_osd_noout_state_no_units(mock_get_osd_noout_state, model) -> None:
    ceph_mon = MagicMock(spec_set=Application)()
    ceph_mon.name = "ceph-mon"
    ceph_mon.charm = "ceph-mon"
    ceph_mon.units = {}

    model.get_applications.return_value = {
        "ceph-mon": ceph_mon,
    }

    await ceph.assert_osd_noout_state(model, True)

    mock_get_osd_noout_state.assert_not_awaited()


@pytest.mark.asyncio
@patch("cou.steps.ceph.set_require_osd_release_option_on_unit")
async def test_set_require_osd_release_option(
    mock_set_require_osd_release_option_on_unit, model
) -> None:
    ceph_mon_1_unit = MagicMock(spec_set=Unit)()
    ceph_mon_1_unit.name = "ceph-mon-1/0"
    ceph_mon_1 = MagicMock(spec_set=Application)()
    ceph_mon_1.name = "ceph-mon-1"
    ceph_mon_1.charm = "ceph-mon"
    ceph_mon_1.units = {"ceph-mon-1/0": ceph_mon_1_unit}

    ceph_mon_2_unit = MagicMock(spec_set=Unit)()
    ceph_mon_2_unit.name = "ceph-mon-2/0"
    ceph_mon_2 = MagicMock(spec_set=Application)()
    ceph_mon_2.name = "ceph-mon-2"
    ceph_mon_2.charm = "ceph-mon"
    ceph_mon_2.units = {"ceph-mon-2/0": ceph_mon_2_unit}

    model.get_applications.return_value = {
        "ceph-mon-1": ceph_mon_1,
        "ceph-mon-2": ceph_mon_2,
    }

    await ceph.set_require_osd_release_option(model)

    mock_set_require_osd_release_option_on_unit.assert_awaited()
    assert mock_set_require_osd_release_option_on_unit.await_count == 2


@pytest.mark.asyncio
@patch("cou.steps.ceph.set_require_osd_release_option_on_unit")
async def test_set_require_osd_release_option_no_app(
    mock_set_require_osd_release_option_on_unit, model
) -> None:
    model.get_applications.return_value = {}

    await ceph.set_require_osd_release_option(model)

    mock_set_require_osd_release_option_on_unit.assert_not_awaited()


@pytest.mark.asyncio
@patch("cou.steps.ceph.set_require_osd_release_option_on_unit")
async def test_set_require_osd_release_option_no_units(
    mock_set_require_osd_release_option_on_unit, model
) -> None:
    ceph_mon = MagicMock(spec_set=Application)()
    ceph_mon.name = "ceph-mon"
    ceph_mon.charm = "ceph-mon"
    ceph_mon.units = {}

    model.get_applications.return_value = {
        "ceph-mon": ceph_mon,
    }

    await ceph.set_require_osd_release_option(model)

    mock_set_require_osd_release_option_on_unit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("flags_set,expected_noout_state", [([], False), (["noout"], True)])
async def test_get_osd_noout_state(flags_set, expected_noout_state, model) -> None:
    model.run_on_unit.return_value = {"stdout": json.dumps({"flags_set": flags_set})}

    noout_state = await ceph.get_osd_noout_state(model, "ceph-mon/0")
    assert noout_state == expected_noout_state


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "current_required_osd_release, current_osd_release",
    [
        ("nautilus", "octopus"),
        ("octopus", "pacific"),
        ("pacific", "quincy"),
    ],
)
@patch("cou.steps.ceph._get_required_osd_release", new_callable=AsyncMock)
@patch("cou.steps.ceph._get_current_osd_release", new_callable=AsyncMock)
async def test_set_require_osd_release_option_different_releases(
    mock_get_current_osd_release,
    mock_get_required_osd_release,
    model,
    current_required_osd_release,
    current_osd_release,
):
    mock_get_required_osd_release.return_value = current_required_osd_release
    mock_get_current_osd_release.return_value = current_osd_release
    model.run_on_unit.return_value = {"return-code": 0, "stdout": "Success"}

    await ceph.set_require_osd_release_option_on_unit(model, "ceph-mon/0")

    model.run_on_unit.assert_called_once_with(
        unit_name="ceph-mon/0",
        command=f"ceph osd require-osd-release {current_osd_release}",
        timeout=600,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "current_required_osd_release, current_osd_release",
    [
        ("octopus", "octopus"),
        ("pacific", "pacific"),
    ],
)
@patch("cou.steps.ceph._get_required_osd_release", new_callable=AsyncMock)
@patch("cou.steps.ceph._get_current_osd_release", new_callable=AsyncMock)
async def test_set_require_osd_release_option_same_release(
    mock_get_current_osd_release,
    mock_get_required_osd_release,
    model,
    current_required_osd_release,
    current_osd_release,
):
    mock_get_required_osd_release.return_value = current_required_osd_release
    mock_get_current_osd_release.return_value = current_osd_release

    await ceph.set_require_osd_release_option_on_unit(model, "ceph-mon/0")

    assert not model.run_on_unit.called


@pytest.mark.asyncio
async def test_get_required_osd_release(model):
    expected_current_release = "octopus"
    check_result = """
        {"crush_version":7,"min_compat_client":"jewel","require_osd_release":"octopus"}
    """
    model.run_on_unit.return_value = {"return-code": 0, "stdout": check_result}
    actual_current_release = await ceph._get_required_osd_release(unit="ceph-mon/0", model=model)

    model.run_on_unit.assert_called_once_with(
        unit_name="ceph-mon/0",
        command="ceph osd dump -f json",
        timeout=600,
    )
    assert actual_current_release == expected_current_release


@pytest.mark.asyncio
async def test_get_current_osd_release(model):
    expected_osd_release = "octopus"
    check_output = """
    {
        "mon": {
            "ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) octopus (stable)": 1
        },
        "mgr": {
            "ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) octopus (stable)": 1
        },
        "osd": {
            "ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) %s (stable)": 3
        },
        "mds": {},
        "overall": {
            "ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) octopus (stable)": 5
        }
    }
    """ % (
        expected_osd_release
    )
    model.run_on_unit.return_value = {"return-code": 0, "stdout": check_output}
    actual_osd_release = await ceph._get_current_osd_release(unit="ceph-mon/0", model=model)

    model.run_on_unit.assert_called_once_with(
        unit_name="ceph-mon/0",
        command="ceph versions -f json",
        timeout=600,
    )

    assert actual_osd_release == expected_osd_release


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "osd_release_output, error_message",
    [
        (
            {},  # OSDs release information is empty
            "Cannot get OSD release information on ceph-mon unit 'ceph-mon/0'.",
        ),
        (
            {
                "ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) octopus (stable)": 2,
                "ceph version 16.2.13 (8a82819d84cf884bd39c17e3236e0632) pacific (stable)": 1,
            },  # mismatched OSD releases
            "OSDs are on mismatched releases:\n",
        ),
        (
            {
                "ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) invalid (stable)": 3,
            },  # unsupported OSD releases
            "Cannot recognize Ceph release 'invalid'. The supporting "
            "releases are: octopus, pacific, quincy",
        ),
    ],
)
async def test_get_current_osd_release_unsuccessful(model, osd_release_output, error_message):
    check_output = """
    {
        "mon": {
            "ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) octopus (stable)": 1
        },
        "mgr": {
            "ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) octopus (stable)": 1
        },
        "osd": %s,
        "mds": {},
        "overall": {
            "ceph version 15.2.17 (8a82819d84cf884bd39c17e3236e0632) octopus (stable)": 5
        }
    }
    """ % (
        json.dumps(osd_release_output)
    )
    model.run_on_unit.return_value = {"return-code": 0, "stdout": check_output}
    with pytest.raises(RunUpgradeError, match=error_message):
        await ceph._get_current_osd_release(unit="ceph-mon/0", model=model)

    model.run_on_unit.assert_called_once_with(
        unit_name="ceph-mon/0",
        command="ceph versions -f json",
        timeout=600,
    )
