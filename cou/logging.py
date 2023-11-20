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

"""Set up both global logger for logfile and console'."""
import logging
import logging.handlers
import pathlib
from datetime import datetime

from cou.utils import COU_DATA

COU_DIR_LOG = COU_DATA / "log"

logger = logging.getLogger(__name__)


class TracebackInfoFilter(logging.Filter):  # pylint: disable=too-few-public-methods
    """Filter to clear out exception tracebacks."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter function that sets exception info and cache to None.

        :param record: An event being logged.
        :type record: logging.LogRecord
        :return: Whether the specified record is to be logged.
        :rtype: bool
        """
        record.exc_info, record.exc_text = None, None
        return True


def setup_logging(log_level: str = "INFO") -> None:
    """Do setup for logging.

    :param log_level: Logging level, defaults to "INFO"
    :type log_level: str, optional
    """
    log_formatter_file = logging.Formatter(
        fmt="%(asctime)s [%(name)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    log_formatter_console = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    root_logger = logging.getLogger()
    root_logger.setLevel("NOTSET")

    # handler for the log file. Log level is "NOTSET"
    time_stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    file_name = f"{COU_DIR_LOG}/cou-{time_stamp}.log"
    pathlib.Path(COU_DIR_LOG).mkdir(parents=True, exist_ok=True)
    log_file_handler = logging.FileHandler(file_name)
    log_file_handler.setFormatter(log_formatter_file)
    # suppress python libjuju and websockets debug logs
    if log_level != "NOTSET":
        log_file_handler.addFilter(filter_debug_logs)

    # handler for the console. Log level comes from the CLI
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(log_formatter_console)
    # just cou logs on console
    console_handler.addFilter(logging.Filter(__package__))
    # suppress stack trace on console
    console_handler.addFilter(TracebackInfoFilter())

    root_logger.addHandler(log_file_handler)
    root_logger.addHandler(console_handler)
    logger.info("Logs of this execution can be found at %s", file_name)


def filter_debug_logs(record: logging.LogRecord) -> bool:
    """Filter debug logs to not go to the logfile.

    libjuju and websockets are very verbose on the debug mode and the logfile
    can be huge if not filtered.
    :param record: A LogRecord instance represents an event being logged.
    :type record: LogRecord
    :return: Returns false to not append record in the log file, true for appending it.
    :rtype: bool
    """
    return record.levelname != "DEBUG" or not (
        record.name.startswith("juju.") or record.name.startswith("websockets.")
    )
