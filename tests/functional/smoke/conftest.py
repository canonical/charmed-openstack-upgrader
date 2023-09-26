import logging

import pytest
import pytest_asyncio

from cou.utils.juju_utils import COUModel

log = logging.getLogger(__name__)


def pytest_addoption(parser):
    parser.addoption(
        "--channel",
        type=str,
        default="ussuri/stable",
        help="Set series for the machine units",
    )
    parser.addoption(
        "--series",
        type=str,
        default="focal",
        help="Set series for the machine units",
    )


@pytest.fixture(scope="module")
def channel(request):
    return request.config.getoption("--channel")


@pytest.fixture(scope="module")
def series(request):
    return request.config.getoption("--series")


@pytest_asyncio.fixture
async def model(ops_test):
    """Define COUModel."""
    model = COUModel(ops_test.model_name)
    yield model
    await model._model.disconnect()
