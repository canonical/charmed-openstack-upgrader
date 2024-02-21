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
"""Module to provide helper for writing unit tests."""

import contextlib
import io
import unittest
from unittest import mock
from unittest.mock import MagicMock

from cou.steps import BaseStep
from cou.utils.juju_utils import COUMachine


@contextlib.contextmanager
def patch_open():
    """Patch open().

    Patch open() to allow mocking both open() itself and the file that is
    yielded.

    Yields the mock for "open" and "file", respectively.
    """
    mock_open = mock.MagicMock(spec=open)
    mock_file = mock.MagicMock(spec=io.FileIO)

    @contextlib.contextmanager
    def stub_open(*args, **kwargs):
        mock_open(*args, **kwargs)
        yield mock_file

    with mock.patch("builtins.open", stub_open):
        yield mock_open, mock_file


class BaseTestCase(unittest.TestCase):
    """Base class for creating classes of unit tests."""

    def shortDescription(self):
        """Disable reporting unit test doc strings rather than names."""
        return None

    def setUp(self):
        """Run setup of patches."""
        self._patches = {}
        self._patches_start = {}

    def tearDown(self):
        """Run teardown of patches."""
        for k, v in self._patches.items():
            v.stop()
            setattr(self, k, None)
        self._patches = None
        self._patches_start = None

    def patch_object(self, obj, attr, return_value=None, name=None, new=None, **kwargs):
        """Patch the given object."""
        if name is None:
            name = attr
        if new is not None:
            mocked = mock.patch.object(obj, attr, new=new, **kwargs)
        else:
            mocked = mock.patch.object(obj, attr, **kwargs)
        self._patches[name] = mocked
        started = mocked.start()
        if new is None:
            started.return_value = return_value
        self._patches_start[name] = started
        setattr(self, name, started)

    def patch(self, item, return_value=None, name=None, new=None, **kwargs):
        """Patch the given item."""
        if name is None:
            raise RuntimeError("Must pass 'name' to .patch()")
        if new is not None:
            mocked = mock.patch(item, new=new, **kwargs)
        else:
            mocked = mock.patch(item, **kwargs)
        self._patches[name] = mocked
        started = mocked.start()
        if new is None:
            started.return_value = return_value
        self._patches_start[name] = started
        setattr(self, name, started)


def assert_steps(step_1: BaseStep, step_2: BaseStep) -> None:
    """Compare two steps and raise exception if they are different."""
    msg = f"\n{step_1}!=\n{step_2}"
    assert step_1 == step_2, msg


def generate_cou_machine(machine_id: str, az: str | None = None) -> MagicMock:
    machine = MagicMock(spec_set=COUMachine)()
    machine.machine_id = machine_id
    machine.az = az
    return machine
