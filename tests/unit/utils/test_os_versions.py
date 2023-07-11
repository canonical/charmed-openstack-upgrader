# Copyright 2018 Canonical Ltd.
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

import pytest

from cou.utils.os_versions import BasicStringComparator, CompareHostReleases


def test_BasicStringComparator():
    with pytest.raises(Exception):
        BasicStringComparator("22")


def test_BasicStringComparator2():
    with pytest.raises(KeyError):
        CompareHostReleases("other")


def test_CompareHostReleases():
    assert CompareHostReleases("jammy") > "focal"
    assert CompareHostReleases("jammy") >= "focal"
    assert CompareHostReleases("focal") <= "focal"
    assert CompareHostReleases("focal") < "jammy"
    assert CompareHostReleases("jammy") == "jammy"
    assert CompareHostReleases("jammy") != "focal"
    assert CompareHostReleases("jammy").__repr__() == "CompareHostReleases<jammy>"
    assert CompareHostReleases("jammy").__str__() == "jammy"
