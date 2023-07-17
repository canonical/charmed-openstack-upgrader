# mypy: disable-error-code="no-untyped-def"
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


"""Module containing data about OpenStack versions."""
from collections import OrderedDict
from typing import List, Optional

OPENSTACK_CODENAMES = OrderedDict(
    [
        ("2011.2", "diablo"),
        ("2012.1", "essex"),
        ("2012.2", "folsom"),
        ("2013.1", "grizzly"),
        ("2013.2", "havana"),
        ("2014.1", "icehouse"),
        ("2014.2", "juno"),
        ("2015.1", "kilo"),
        ("2015.2", "liberty"),
        ("2016.1", "mitaka"),
        ("2016.2", "newton"),
        ("2017.1", "ocata"),
        ("2017.2", "pike"),
        ("2018.1", "queens"),
        ("2018.2", "rocky"),
        ("2019.1", "stein"),
        ("2019.2", "train"),
        ("2020.1", "ussuri"),
        ("2020.2", "victoria"),
        ("2021.1", "wallaby"),
        ("2021.2", "xena"),
        ("2022.1", "yoga"),
        ("2022.2", "zed"),
        ("2023.1", "antelope"),
    ]
)


UBUNTU_RELEASES = [
    "lucid",
    "maverick",
    "natty",
    "oneiric",
    "precise",
    "quantal",
    "raring",
    "saucy",
    "trusty",
    "utopic",
    "vivid",
    "wily",
    "xenial",
    "yakkety",
    "zesty",
    "artful",
    "bionic",
    "cosmic",
    "disco",
    "eoan",
    "focal",
    "groovy",
    "hirsute",
    "impish",
    "jammy",
    "kinetic",
    "lunar",
]


class BasicStringComparator(object):
    """Provides a class that will compare strings from an iterator type object.

    Used to provide > and < comparisons on strings that may not necessarily be
    alphanumerically ordered.  e.g. OpenStack or Ubuntu releases AFTER the
    z-wrap.
    """

    _list: Optional[List[str]] = None

    def __init__(self, item):
        """Do init."""
        if self._list is None:
            raise Exception("Must define the _list in the class definition!")
        try:
            self.index = self._list.index(item)
        except Exception:
            raise KeyError("Item '{}' is not in list '{}'".format(item, self._list))

    def __eq__(self, other):
        """Do equals."""
        assert isinstance(other, str) or isinstance(other, self.__class__)
        return self.index == self._list.index(other)

    def __ne__(self, other):
        """Do not equals."""
        return not self.__eq__(other)

    def __lt__(self, other):
        """Do less than."""
        assert isinstance(other, str) or isinstance(other, self.__class__)
        return self.index < self._list.index(other)

    def __ge__(self, other):
        """Do greater than or equal."""
        return not self.__lt__(other)

    def __gt__(self, other):
        """Do greater than."""
        assert isinstance(other, str) or isinstance(other, self.__class__)
        return self.index > self._list.index(other)

    def __le__(self, other):
        """Do less than or equals."""
        return not self.__gt__(other)

    def __repr__(self):
        """Return the representation of CompareOpenStack."""
        return "%s<%s>" % (self.__class__.__name__, self._list[self.index])

    def __str__(self):
        """Give back the item at the index.

        This is so it can be used in comparisons like:

        s_mitaka = CompareOpenStack('mitaka')
        s_newton = CompareOpenstack('newton')

        assert s_newton > s_mitaka

        :returns: <string>
        """
        return self._list[self.index]


class CompareHostReleases(BasicStringComparator):
    """Provide comparisons of Ubuntu releases.

    Use in the form of

    if CompareHostReleases(release) > 'trusty':
        # do something with mitaka
    """

    _list = UBUNTU_RELEASES


class CompareOpenStack(BasicStringComparator):
    """Provide comparisons of OpenStack releases.

    Use in the form of

    if CompareOpenStack(release) > 'yoga':
        # do something
    """

    _list = list(OPENSTACK_CODENAMES.values())
