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

"""Test steps package."""
from cou.steps import UpgradeStep
from tests.unit.utils import BaseTestCase


class TestSteps(BaseTestCase):
    def test_upgrade_step(self):
        def sample_function():
            return 1

        u = UpgradeStep(description="test", function=sample_function, parallel=False)
        assert u.description == "test"
        assert u.function is sample_function
        assert not u.parallel
        assert u.params == {}

    def test_upgrade_step_add(self):
        u = UpgradeStep(description="test", function=None, parallel=False)
        substep = UpgradeStep(description="substep", function=None, parallel=False)
        u.add_step(substep)
        assert u.sub_steps[0] is substep

    def test_upgrade_step_set_function(self):
        u = UpgradeStep(description="test", function=None, parallel=False, params=None)

        def sample_function(**kwargs):
            return kwargs["x"]

        u.set_function(function=sample_function, x=10)
        assert u.function(**u.params) == 10
