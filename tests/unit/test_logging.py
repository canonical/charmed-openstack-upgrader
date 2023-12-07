# Copyright 2023 Canonical Limited
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
from logging import LogRecord
from unittest.mock import MagicMock, patch

import pytest

from cou.logging import TracebackInfoFilter, filter_debug_logs, setup_logging


def test_filter_clears_exc_info_and_text():
    """Test filtering out exception traceback and cache."""
    record = MagicMock()
    record.exc_info = (Exception, Exception("Test Exception"), None)
    record.exc_text = "Test Exception Traceback"
    logger = MagicMock()
    logger.filters = [TracebackInfoFilter()]

    logger.filters[0].filter(record)

    assert record.exc_info is None
    assert record.exc_text is None


@pytest.mark.parametrize("log_level", ["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR"])
def test_setup_logging(log_level):
    """Test setting up logging."""
    with (
        patch("cou.logging.logging") as mock_logging,
        patch("cou.logging.progress_indicator") as mock_indicator,
    ):
        log_file_handler = MagicMock()
        console_handler = MagicMock()
        mock_root_logger = mock_logging.getLogger.return_value
        mock_logging.FileHandler.return_value = log_file_handler
        mock_logging.StreamHandler.return_value = console_handler

        setup_logging(log_level)

        mock_root_logger.addHandler.assert_any_call(log_file_handler)
        mock_root_logger.addHandler.assert_any_call(console_handler)
        mock_indicator.start.assert_called_once()
        mock_indicator.stop_and_persist.assert_called_once()

        if log_level == "NOTSET":
            log_file_handler.addFilter.assert_not_called()
        else:
            log_file_handler.addFilter.assert_called_with(filter_debug_logs)


@pytest.mark.parametrize(
    "name, level, exp_result",
    [
        ("juju.client.connection", "DEBUG", False),  # juju debug is not logged
        ("juju.client.connection", "INFO", True),  # juju info is logged
        ("websockets.client", "DEBUG", False),  # websockets debug is not logged
        ("websockets.client", "WARNING", True),  # websockets warning is logged
        ("cou.apps.core", "DEBUG", True),  # debug logs from other modules are logged
        ("my.juju", "DEBUG", True),  # modules that doesn't starts with juju are logged
        ("my.websockets", "DEBUG", True),  # modules that doesn't starts with websockets are logged
    ],
)
def test_filter_debug_logs(name, level, exp_result):
    mock_record = MagicMock(
        spec_set=LogRecord(
            name,
            level,
            pathname="/var/my_path",
            lineno=56,
            msg="my log line",
            args=None,
            exc_info="my_info",
        )
    )
    mock_record.name = name
    mock_record.levelname = level

    assert filter_debug_logs(mock_record) is exp_result
