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
import asyncio
import runpy
from unittest import mock

import pytest

from cou import main


@mock.patch("cou.cli.entrypoint")
def test_execution(mock_entrypoint):
    runpy.run_path("cou/__main__.py", run_name="__main__")
    mock_entrypoint.assert_called_once_with()
    mock_entrypoint.assert_awaited_once_with()


@mock.patch("asyncio.get_event_loop")
@mock.patch("cou.cli.entrypoint")
def test_main(mock_entrypoint, mock_get_event_loop):
    loop = mock_get_event_loop.return_value
    loop.is_running.return_value = True

    main()

    mock_entrypoint.assert_called_once_with()
    loop.close.assert_called_once_with()


@pytest.mark.parametrize("exc", [KeyboardInterrupt, asyncio.CancelledError])
@mock.patch("cou.cli.entrypoint")
def test_main_exception(mock_entrypoint, exc):
    mock_entrypoint.side_effect = exc

    with pytest.raises(SystemExit, match="130"):
        main()
