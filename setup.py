#  Copyright 2023 Canonical Limited
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""Manage package and distribution."""
import subprocess
from typing import List

from setuptools import setup


def find_version() -> str:
    """Parse charmed-openstack-upgrader version based on the git tag.

    :return: Version of the package.
    :rtype: str
    """
    try:
        cmd: List[str] = ["git", "describe", "--tags", "--always", "HEAD"]
        gitversion: str = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
        if all(char.isdigit() or char == "." for char in gitversion):
            return gitversion
        build: List[str] = gitversion.split("-")
        return f"{build[0]}.post{build[1]}"
    except IndexError:
        cmde: List[str] = ["git", "rev-list", "--count", "HEAD"]
        commits_count: str = (
            subprocess.check_output(cmde, stderr=subprocess.DEVNULL).decode().strip()
        )
        return f"0.0.dev{commits_count}"
    except subprocess.CalledProcessError:
        return "0.0.dev0"


setup(version=find_version())
