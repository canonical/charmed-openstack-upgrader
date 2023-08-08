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

"""Entrypoint to the 'charmed-openstack-upgrader'."""
import argparse
import logging
import logging.handlers
import os
import pathlib
import sys
from datetime import datetime
from typing import Any

from cou.steps.analyze import Analysis
from cou.steps.execute import ExecutorFactory
from cou.steps.plan import generate_plan
from cou.utils import juju_utils as utils

COU_DIR_LOG = pathlib.Path(os.getenv("COU_DATA", ""), "log")
AVAILABLE_OPTIONS = "cas"

logger = logging.getLogger(__name__)


def parse_args(args: Any) -> argparse.Namespace:
    """Parse cli arguments.

    :param args: Arguments to be parsed.
    :type args: Any
    :return: Arguments parsed to the cli execution.
    :rtype: argparse.Namespace
    """
    parser = argparse.ArgumentParser(
        description="Charmed OpenStack Upgrader(cou) is an application to upgrade Charmed "
        "OpenStack. Application identifies the lowest OpenStack version on the components and "
        "upgrade to the next version.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        exit_on_error=False,
        add_help=False,
    )
    parser.add_argument(
        "--run",
        help="Use this flag to run the upgrade, otherwise just print out the upgrade steps.",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        dest="loglevel",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        type=str.upper,
        help="Set the logging level. Defaults to INFO. This only affects stdout. The logfile "
        "will be always DEBUG. The file location is in COU_DATA/log. You can set the "
        "COU_DATA via environment variable. However it needs to be plugged to snap.",
    )
    parser.add_argument(
        "--model",
        default=None,
        dest="model_name",
        help="Set the model to operate on. If not set it gets the model name in this order:\n"
        "  1 - Environment variable JUJU_MODEL,"
        "  2 - Environment variable MODEL_NAME,"
        "  3 - Current active juju model",
    )
    parser.add_argument(
        "--non-interactive", help="Run upgrade without prompt.", action="store_true", default=False
    )
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        default=argparse.SUPPRESS,
        help="Show this help message and exit.",
    )

    return parser.parse_args(args)


def setup_logging(log_level: str = "INFO") -> None:
    """Do setup for logging.

    :returns: Nothing: This function is executed for its side effect
    :rtype: None
    """
    log_formatter_file = logging.Formatter(
        fmt="%(asctime)s [%(name)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    log_formatter_console = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    root_logger = logging.getLogger()
    root_logger.setLevel("DEBUG")

    # handler for the log file. Log level is DEBUG
    time_stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    file_name = f"{COU_DIR_LOG}/cou-{time_stamp}.log"
    pathlib.Path(COU_DIR_LOG).mkdir(parents=True, exist_ok=True)
    log_file_handler = logging.FileHandler(file_name)
    log_file_handler.setFormatter(log_formatter_file)

    # handler for the console. Log level comes from the CLI
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(log_formatter_console)
    # just cou logs on console
    console_handler.addFilter(logging.Filter(__package__))

    root_logger.addHandler(log_file_handler)
    root_logger.addHandler(console_handler)
    logger.info("Logs of this execution can be found at %s", file_name)


async def entrypoint() -> None:
    """Execute 'charmed-openstack-upgrade' command."""
    try:
        args = parse_args(sys.argv[1:])

        setup_logging(log_level=args.loglevel)

        model_name = await utils.async_set_current_model_name(args.model_name)
        logger.info("Setting current model name: %s", model_name)

        analysis_result = await Analysis.create()
        print(analysis_result)
        upgrade_plan = await generate_plan(analysis_result)
        if args.run:
            await ExecutorFactory.create_executor(upgrade_plan, not args.non_interactive).execute()
        else:
            print(upgrade_plan)

    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.exception(exc)
        sys.exit(1)
