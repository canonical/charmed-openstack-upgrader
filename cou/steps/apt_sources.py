# Copyright 2025 Canonical Limited
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
"""Functions for verifying APT sources on machines before an upgrade."""
import logging
import os
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from cou.utils.juju_utils import Model

logger = logging.getLogger(__name__)

# Hostnames that are considered safe/expected for OpenStack upgrades.
# This covers standard Ubuntu archives, Ubuntu Cloud Archive (UCA),
# and Ubuntu ports (for non-amd64 architectures).
ALLOWED_HOST_PATTERNS: list[re.Pattern] = [
    re.compile(r"^([a-z]{2}\.)?archive\.ubuntu\.com$"),
    re.compile(r"^security\.ubuntu\.com$"),
    re.compile(r"^ubuntu-cloud\.archive\.canonical\.com$"),
    re.compile(r"^cloud-archive\.canonical\.com$"),
    re.compile(r"^ports\.ubuntu\.com$"),
    re.compile(r"^esm\.ubuntu\.com$"),
]

APT_CACHE_POLICY_CMD = "apt-cache policy"


def _get_allowed_host_patterns() -> list[re.Pattern]:
    """Build list of allowed host patterns including landscape mirror if configured.

    :return: List of compiled regex patterns for allowed APT source hosts.
    :rtype: list[re.Pattern]
    """
    patterns = list(ALLOWED_HOST_PATTERNS)
    landscape_uri = os.environ.get("LANDSCAPE_MIRROR_URI", "")
    if landscape_uri:
        try:
            parsed = urlparse(landscape_uri)
            if parsed.hostname:
                escaped = re.escape(parsed.hostname)
                patterns.append(re.compile(f"^{escaped}$"))
        except ValueError:
            logger.warning("Invalid LANDSCAPE_MIRROR_URI: %s", landscape_uri)
    return patterns


def parse_apt_policy_uris(apt_cache_output: str) -> set[str]:
    """Parse apt-cache policy output and extract unique repository URIs.

    Lines in apt-cache policy output that describe repository sources look like:
      500 http://archive.ubuntu.com/ubuntu jammy/main amd64 Packages
      100 /var/lib/dpkg/status

    We extract the URIs (http/https) from these lines.

    :param apt_cache_output: Raw output from `apt-cache policy`.
    :type apt_cache_output: str
    :return: Set of unique repository URIs found.
    :rtype: set[str]
    """
    uris: set[str] = set()
    for line in apt_cache_output.splitlines():
        match = re.match(r"^\s*\d+\s+(https?://\S+)", line)
        if match:
            uris.add(match.group(1))
    return uris


def find_unexpected_uris(uris: set[str]) -> set[str]:
    """Check URIs against the allowlist and return any that don't match.

    :param uris: Set of repository URIs to check.
    :type uris: set[str]
    :return: Set of URIs that are not in the allowlist.
    :rtype: set[str]
    """
    allowed_patterns = _get_allowed_host_patterns()
    unexpected: set[str] = set()
    for uri in uris:
        try:
            parsed = urlparse(uri)
            hostname = parsed.hostname or ""
        except ValueError:
            unexpected.add(uri)
            continue

        if not any(pattern.search(hostname) for pattern in allowed_patterns):
            unexpected.add(uri)

    return unexpected


@dataclass
class AptSourcesVerification:
    """Result of verifying APT sources across all machines.

    :param failed: Mapping of machine ID to error message for machines where
        apt-cache policy could not be run.
    :param unexpected: Mapping of machine ID to set of unexpected URIs for
        machines that have non-standard APT sources.
    """

    failed: dict[str, str] = field(default_factory=dict)
    unexpected: dict[str, set[str]] = field(default_factory=dict)


def verify_apt_sources(model: Model) -> AptSourcesVerification:
    """Verify APT sources on all machines in the model.

    Runs `apt-cache policy` on all machines using juju exec --all,
    parses the output, and identifies any unexpected repository sources.
    Machines that fail to return results are recorded but do not abort
    the check on remaining machines.

    :param model: Juju model to check.
    :type model: Model
    :return: Verification result containing failed machines and machines with
        unexpected sources.
    :rtype: AptSourcesVerification
    """
    results = model.run_on_all_machines(APT_CACHE_POLICY_CMD, 30)

    failed: dict[str, str] = {}
    unexpected_by_machine: dict[str, set[str]] = {}
    for machine_id, task in results.items():
        if not task.success:
            error = task.stderr or task.message
            logger.error(
                "Failed to run '%s' on machine %s: %s",
                APT_CACHE_POLICY_CMD,
                machine_id,
                error,
            )
            failed[machine_id] = error
            continue

        uris = parse_apt_policy_uris(task.stdout)
        unexpected = find_unexpected_uris(uris)
        if unexpected:
            logger.info(
                "Machine %s has unexpected APT sources: %s",
                machine_id,
                ", ".join(sorted(unexpected)),
            )
            unexpected_by_machine[machine_id] = unexpected

    return AptSourcesVerification(failed=failed, unexpected=unexpected_by_machine)
