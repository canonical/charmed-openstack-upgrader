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
from unittest.mock import MagicMock, patch

from cou.logging import TracebackInfoFilter, setup_logging


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


def test_setup_logging():
    """Test setting up logging."""
    with patch("cou.logging.logging") as mock_logging:
        log_file_handler = MagicMock()
        console_handler = MagicMock()
        mock_root_logger = mock_logging.getLogger.return_value
        mock_logging.FileHandler.return_value = log_file_handler
        mock_logging.StreamHandler.return_value = console_handler

        setup_logging("INFO")

        mock_root_logger.addHandler.assert_any_call(log_file_handler)
        mock_root_logger.addHandler.assert_any_call(console_handler)
