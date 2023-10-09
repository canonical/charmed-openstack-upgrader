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

"""Main entry point."""
import asyncio
import signal
import sys


def main() -> None:
    """Enter the application."""
    loop = None
    try:
        from cou.cli import entrypoint  # pylint: disable=import-outside-toplevel

        loop = asyncio.get_event_loop()
        entrypoint_task = asyncio.ensure_future(entrypoint())
        loop.add_signal_handler(signal.SIGINT, entrypoint_task.cancel)
        loop.add_signal_handler(signal.SIGTERM, entrypoint_task.cancel)
        loop.run_until_complete(entrypoint_task)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print(f"{__package__} was interrupted.")
        sys.exit(130)
    finally:
        if loop is not None and loop.is_running():
            loop.close()


if __name__ == "__main__":
    main()
