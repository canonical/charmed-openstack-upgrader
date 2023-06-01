# Copyright 2023 Canonical Limited.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Note that the unit_tests/__init__.py also mocks out two charmhelpers imports
# that have side effects that try to apt install modules:
# sys.modules['charmhelpers.contrib.openstack.zaza_utils'] = mock.MagicMock()
# sys.modules['charmhelpers.contrib.network.ip'] = mock.MagicMock()

"""Module to provide helper for writing unit tests."""

import contextlib
import io
import unittest

import mock


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
