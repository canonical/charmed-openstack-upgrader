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
from unittest.mock import MagicMock, patch

from cou.steps.apt_sources import (
    _get_allowed_host_patterns,
    find_unexpected_uris,
    parse_apt_policy_uris,
    verify_apt_sources,
)

# Realistic apt-cache policy output snippets for testing
APT_POLICY_CLEAN = """\
Package files:
 100 /var/lib/dpkg/status
     release a=now
 500 http://archive.ubuntu.com/ubuntu jammy/main amd64 Packages
     release v=22.04,o=Ubuntu,a=jammy,n=jammy,l=Ubuntu,c=main,b=amd64
     origin archive.ubuntu.com
 500 http://archive.ubuntu.com/ubuntu jammy/restricted amd64 Packages
     release v=22.04,o=Ubuntu,a=jammy,n=jammy,l=Ubuntu,c=restricted,b=amd64
     origin archive.ubuntu.com
 500 http://archive.ubuntu.com/ubuntu jammy-updates/main amd64 Packages
     release v=22.04,o=Ubuntu,a=jammy-updates,n=jammy,l=Ubuntu,c=main,b=amd64
     origin archive.ubuntu.com
 500 http://security.ubuntu.com/ubuntu jammy-security/main amd64 Packages
     release v=22.04,o=Ubuntu,a=jammy-security,n=jammy,l=Ubuntu,c=main,b=amd64
     origin security.ubuntu.com
 500 http://ubuntu-cloud.archive.canonical.com/ubuntu jammy-updates/antelope/main amd64 Packages
     release v=22.04,o=Ubuntu Cloud Archive,a=jammy-updates/antelope,n=jammy,l=Ubuntu
     origin ubuntu-cloud.archive.canonical.com
Pinned packages:
"""

APT_POLICY_WITH_PPA = """\
Package files:
 100 /var/lib/dpkg/status
     release a=now
 500 http://archive.ubuntu.com/ubuntu jammy/main amd64 Packages
     release v=22.04,o=Ubuntu,a=jammy,n=jammy,l=Ubuntu,c=main,b=amd64
     origin archive.ubuntu.com
 500 http://ppa.launchpad.net/some-user/some-ppa/ubuntu jammy/main amd64 Packages
     release v=22.04,o=LP-PPA-some-user-some-ppa,a=jammy,n=jammy,l=some-ppa
     origin ppa.launchpad.net
Pinned packages:
"""

APT_POLICY_WITH_THIRD_PARTY = """\
Package files:
 100 /var/lib/dpkg/status
     release a=now
 500 http://archive.ubuntu.com/ubuntu jammy/main amd64 Packages
     release v=22.04,o=Ubuntu,a=jammy,n=jammy,l=Ubuntu,c=main,b=amd64
     origin archive.ubuntu.com
 500 https://packages.example.com/stable jammy/main amd64 Packages
     release o=Example,a=jammy
     origin packages.example.com
 500 http://security.ubuntu.com/ubuntu jammy-security/main amd64 Packages
     release v=22.04,o=Ubuntu,a=jammy-security,n=jammy,l=Ubuntu,c=main,b=amd64
     origin security.ubuntu.com
Pinned packages:
"""

APT_POLICY_WITH_COUNTRY_MIRROR = """\
Package files:
 100 /var/lib/dpkg/status
     release a=now
 500 http://br.archive.ubuntu.com/ubuntu jammy/main amd64 Packages
     release v=22.04,o=Ubuntu,a=jammy,n=jammy,l=Ubuntu,c=main,b=amd64
     origin br.archive.ubuntu.com
 500 http://security.ubuntu.com/ubuntu jammy-security/main amd64 Packages
     release v=22.04,o=Ubuntu,a=jammy-security,n=jammy,l=Ubuntu,c=main,b=amd64
     origin security.ubuntu.com
Pinned packages:
"""

APT_POLICY_LANDSCAPE = """\
Package files:
 100 /var/lib/dpkg/status
     release a=now
 500 http://landscape.example.com/ubuntu jammy/main amd64 Packages
     release v=22.04,o=Ubuntu,a=jammy,n=jammy,l=Ubuntu,c=main,b=amd64
     origin landscape.example.com
Pinned packages:
"""

APT_POLICY_LANDSCAPE_MIRROR = """\
Package files:
 100 /var/lib/dpkg/status
     release a=now
 500 https://repo.mirror.example.com/repository/standalone/ubuntu jammy/main amd64 Packages
     release a=jammy,n=jammy,c=main,b=amd64
     origin repo.mirror.example.com
 500 https://repo.mirror.example.com/repository/standalone/ubuntu jammy-updates/main amd64 Packages
     release a=jammy-updates,n=jammy-updates,c=main,b=amd64
     origin repo.mirror.example.com
Pinned packages:
"""

APT_POLICY_PORTS = """\
Package files:
 100 /var/lib/dpkg/status
     release a=now
 500 http://ports.ubuntu.com/ubuntu-ports jammy/main arm64 Packages
     release v=22.04,o=Ubuntu,a=jammy,n=jammy,l=Ubuntu,c=main,b=arm64
     origin ports.ubuntu.com
Pinned packages:
"""

APT_POLICY_ESM = """\
Package files:
 100 /var/lib/dpkg/status
     release a=now
 500 https://esm.ubuntu.com/infra/ubuntu jammy-infra-security/main amd64 Packages
     release v=22.04,o=UbuntuESMApps,a=jammy-apps-security
     origin esm.ubuntu.com
Pinned packages:
"""

APT_POLICY_CLOUD_ARCHIVE_PPA = """\
Package files:
 100 /var/lib/dpkg/status
     release a=now
 500 http://ppa.launchpadcontent.net/ubuntu-cloud-archive/antelope/ubuntu jammy/main amd64 Packages
     release v=22.04,o=LP-PPA-ubuntu-cloud-archive-antelope,a=jammy,n=jammy,l=antelope
     origin ppa.launchpadcontent.net
Pinned packages:
"""


class TestParseAptPolicyUris:
    def test_clean_output(self):
        """Test parsing apt-cache policy with only standard Ubuntu and UCA sources."""
        uris = parse_apt_policy_uris(APT_POLICY_CLEAN)
        assert uris == {
            "http://archive.ubuntu.com/ubuntu",
            "http://security.ubuntu.com/ubuntu",
            "http://ubuntu-cloud.archive.canonical.com/ubuntu",
        }

    def test_with_ppa(self):
        """Test parsing output containing a PPA source."""
        uris = parse_apt_policy_uris(APT_POLICY_WITH_PPA)
        assert "http://ppa.launchpad.net/some-user/some-ppa/ubuntu" in uris
        assert "http://archive.ubuntu.com/ubuntu" in uris

    def test_with_third_party(self):
        """Test parsing output containing a third-party source."""
        uris = parse_apt_policy_uris(APT_POLICY_WITH_THIRD_PARTY)
        assert "https://packages.example.com/stable" in uris

    def test_with_country_mirror(self):
        """Test parsing output with a country-specific Ubuntu mirror."""
        uris = parse_apt_policy_uris(APT_POLICY_WITH_COUNTRY_MIRROR)
        assert "http://br.archive.ubuntu.com/ubuntu" in uris

    def test_empty_output(self):
        """Test parsing empty output."""
        uris = parse_apt_policy_uris("")
        assert uris == set()

    def test_no_uris(self):
        """Test output with only local dpkg status and no remote repos."""
        output = """\
Package files:
 100 /var/lib/dpkg/status
     release a=now
Pinned packages:
"""
        uris = parse_apt_policy_uris(output)
        assert uris == set()

    def test_https_uris(self):
        """Test that both http and https URIs are parsed."""
        uris = parse_apt_policy_uris(APT_POLICY_WITH_THIRD_PARTY)
        assert any(uri.startswith("https://") for uri in uris)
        assert any(uri.startswith("http://") for uri in uris)


class TestFindUnexpectedUris:
    def test_all_allowed(self):
        """Test with only standard Ubuntu and UCA sources."""
        uris = {
            "http://archive.ubuntu.com/ubuntu",
            "http://security.ubuntu.com/ubuntu",
            "http://ubuntu-cloud.archive.canonical.com/ubuntu",
        }
        assert find_unexpected_uris(uris) == set()

    def test_country_mirror_allowed(self):
        """Test that country-specific Ubuntu mirrors are allowed."""
        uris = {
            "http://br.archive.ubuntu.com/ubuntu",
            "http://us.archive.ubuntu.com/ubuntu",
        }
        assert find_unexpected_uris(uris) == set()

    def test_ppa_unexpected(self):
        """Test that PPA sources are flagged as unexpected."""
        uris = {
            "http://archive.ubuntu.com/ubuntu",
            "http://ppa.launchpad.net/some-user/some-ppa/ubuntu",
        }
        unexpected = find_unexpected_uris(uris)
        assert unexpected == {"http://ppa.launchpad.net/some-user/some-ppa/ubuntu"}

    def test_third_party_unexpected(self):
        """Test that third-party sources are flagged as unexpected."""
        uris = {
            "http://archive.ubuntu.com/ubuntu",
            "https://packages.example.com/stable",
        }
        unexpected = find_unexpected_uris(uris)
        assert unexpected == {"https://packages.example.com/stable"}

    def test_ports_allowed(self):
        """Test that ports.ubuntu.com is allowed."""
        uris = {"http://ports.ubuntu.com/ubuntu-ports"}
        assert find_unexpected_uris(uris) == set()

    def test_esm_allowed(self):
        """Test that esm.ubuntu.com is allowed."""
        uris = {"https://esm.ubuntu.com/infra/ubuntu"}
        assert find_unexpected_uris(uris) == set()

    def test_cloud_archive_ppa_unexpected(self):
        """Test that the ubuntu-cloud-archive PPA is flagged as unexpected."""
        uris = {
            "http://ppa.launchpadcontent.net/ubuntu-cloud-archive/antelope/ubuntu",
        }
        unexpected = find_unexpected_uris(uris)
        assert unexpected == {
            "http://ppa.launchpadcontent.net/ubuntu-cloud-archive/antelope/ubuntu",
        }

    @patch.dict("os.environ", {"LANDSCAPE_MIRROR_URI": "http://landscape.example.com/repository"})
    def test_landscape_allowed(self):
        """Test that landscape mirror URI is allowed when env var is set."""
        uris = {"http://landscape.example.com/ubuntu"}
        assert find_unexpected_uris(uris) == set()

    def test_landscape_not_set(self):
        """Test that landscape URI is unexpected when env var is not set."""
        uris = {"http://landscape.example.com/ubuntu"}
        unexpected = find_unexpected_uris(uris)
        assert unexpected == {"http://landscape.example.com/ubuntu"}

    @patch.dict(
        "os.environ",
        {"LANDSCAPE_MIRROR_URI": "https://repo.mirror.example.com/repository/standalone"},
    )
    def test_landscape_mirror_with_path_allowed(self):
        """Test that a landscape mirror with a path in the URI is allowed."""
        uris = {"https://repo.mirror.example.com/repository/standalone/ubuntu"}
        assert find_unexpected_uris(uris) == set()

    def test_landscape_mirror_unexpected_without_env(self):
        """Test that a landscape mirror is unexpected when LANDSCAPE_MIRROR_URI is not set."""
        uris = {"https://repo.mirror.example.com/repository/standalone/ubuntu"}
        unexpected = find_unexpected_uris(uris)
        assert unexpected == {"https://repo.mirror.example.com/repository/standalone/ubuntu"}

    @patch.dict(
        "os.environ",
        {"LANDSCAPE_MIRROR_URI": "http://mirror-a.example.com/repository"},
    )
    def test_landscape_different_host_unexpected(self):
        """Test is unexpected when LANDSCAPE_MIRROR_URI points to a different host."""
        uris = {"http://mirror-b.example.com/repository/ubuntu"}
        unexpected = find_unexpected_uris(uris)
        assert unexpected == {"http://mirror-b.example.com/repository/ubuntu"}

    def test_empty_uris(self):
        """Test with empty set of URIs."""
        assert find_unexpected_uris(set()) == set()

    def test_multiple_unexpected(self):
        """Test with multiple unexpected sources."""
        uris = {
            "http://archive.ubuntu.com/ubuntu",
            "http://ppa.launchpad.net/some-user/ppa/ubuntu",
            "https://packages.example.com/repo",
        }
        unexpected = find_unexpected_uris(uris)
        assert len(unexpected) == 2
        assert "http://ppa.launchpad.net/some-user/ppa/ubuntu" in unexpected
        assert "https://packages.example.com/repo" in unexpected

    @patch("cou.steps.apt_sources.urlparse")
    def test_urlparse_valueerror(self, mock_urlparse):
        """Test that ValueError from urlparse is handled gracefully."""
        mock_urlparse.side_effect = ValueError("invalid URI")
        uris = {"http://invalid-uri"}
        unexpected = find_unexpected_uris(uris)
        assert unexpected == {"http://invalid-uri"}


class TestGetAllowedHostPatterns:
    def test_without_landscape(self):
        """Test patterns without LANDSCAPE_MIRROR_URI set."""
        patterns = _get_allowed_host_patterns()
        # Should have the default patterns only
        assert len(patterns) >= 6

    @patch.dict("os.environ", {"LANDSCAPE_MIRROR_URI": "http://landscape.example.com/repository"})
    def test_with_landscape(self):
        """Test patterns with LANDSCAPE_MIRROR_URI set."""
        patterns = _get_allowed_host_patterns()
        # Should have default patterns + landscape pattern
        pattern_strs = [p.pattern for p in patterns]
        assert any("landscape" in p for p in pattern_strs)

    @patch("cou.steps.apt_sources.urlparse")
    @patch.dict("os.environ", {"LANDSCAPE_MIRROR_URI": "http://landscape.example.com/repo"})
    def test_landscape_urlparse_valueerror(self, mock_urlparse):
        """Test that ValueError from urlparse for landscape URI is handled."""
        mock_urlparse.side_effect = ValueError("invalid URI")
        patterns = _get_allowed_host_patterns()
        # Should still return default patterns without landscape
        assert len(patterns) == len([p for p in patterns if "landscape" not in p.pattern])


class TestVerifyAptSources:
    def _make_task(self, stdout="", stderr="", return_code=0, status="completed"):
        """Create mocks for jubilant Task."""
        task = MagicMock()
        task.stdout = stdout
        task.stderr = stderr
        task.return_code = return_code
        task.status = status
        task.success = status == "completed" and return_code == 0
        task.message = ""
        return task

    def test_clean_machines(self):
        """Test that clean machines return no unexpected sources."""
        model = MagicMock()
        model.run_on_all_machines.return_value = {
            "0": self._make_task(stdout=APT_POLICY_CLEAN),
            "1": self._make_task(stdout=APT_POLICY_CLEAN),
        }
        result = verify_apt_sources(model)
        assert result.unexpected == {}
        assert result.failed == {}

    def test_machine_with_ppa(self):
        """Test that a machine with PPA is flagged."""
        model = MagicMock()
        model.run_on_all_machines.return_value = {
            "0": self._make_task(stdout=APT_POLICY_CLEAN),
            "1": self._make_task(stdout=APT_POLICY_WITH_PPA),
        }
        result = verify_apt_sources(model)
        assert "1" in result.unexpected
        assert "http://ppa.launchpad.net/some-user/some-ppa/ubuntu" in result.unexpected["1"]
        assert "0" not in result.unexpected

    def test_machine_with_third_party(self):
        """Test that a machine with third-party repo is flagged."""
        model = MagicMock()
        model.run_on_all_machines.return_value = {
            "0": self._make_task(stdout=APT_POLICY_WITH_THIRD_PARTY),
        }
        result = verify_apt_sources(model)
        assert "0" in result.unexpected
        assert "https://packages.example.com/stable" in result.unexpected["0"]

    def test_machine_failure_handled(self):
        """Test that machine command failures are collected without aborting other machines."""
        model = MagicMock()
        model.run_on_all_machines.return_value = {
            "0": self._make_task(stdout=APT_POLICY_CLEAN),
            "1": self._make_task(
                stdout="", stderr="connection refused", return_code=1, status="failed"
            ),
            "2": self._make_task(stdout=APT_POLICY_WITH_PPA),
            "3": self._make_task(stdout="", stderr="timeout", return_code=1, status="failed"),
        }
        result = verify_apt_sources(model)
        assert result.failed == {"1": "connection refused", "3": "timeout"}
        assert "2" in result.unexpected
        assert "0" not in result.unexpected
        assert "1" not in result.unexpected
        assert "3" not in result.unexpected

    def test_country_mirror_clean(self):
        """Test that country mirrors are accepted."""
        model = MagicMock()
        model.run_on_all_machines.return_value = {
            "0": self._make_task(stdout=APT_POLICY_WITH_COUNTRY_MIRROR),
        }
        result = verify_apt_sources(model)
        assert result.unexpected == {}

    def test_ports_clean(self):
        """Test that ports.ubuntu.com sources are accepted."""
        model = MagicMock()
        model.run_on_all_machines.return_value = {
            "0": self._make_task(stdout=APT_POLICY_PORTS),
        }
        result = verify_apt_sources(model)
        assert result.unexpected == {}

    def test_esm_clean(self):
        """Test that esm.ubuntu.com sources are accepted."""
        model = MagicMock()
        model.run_on_all_machines.return_value = {
            "0": self._make_task(stdout=APT_POLICY_ESM),
        }
        result = verify_apt_sources(model)
        assert result.unexpected == {}

    def test_cloud_archive_ppa_flagged(self):
        """Test that ubuntu-cloud-archive PPA is flagged by verify_apt_sources."""
        model = MagicMock()
        model.run_on_all_machines.return_value = {
            "0": self._make_task(stdout=APT_POLICY_CLOUD_ARCHIVE_PPA),
        }
        result = verify_apt_sources(model)
        assert "0" in result.unexpected
        assert (
            "http://ppa.launchpadcontent.net/ubuntu-cloud-archive/antelope/ubuntu"
            in result.unexpected["0"]
        )

    @patch.dict("os.environ", {"LANDSCAPE_MIRROR_URI": "http://landscape.example.com/repository"})
    def test_landscape_clean(self):
        """Test that landscape sources are accepted when env var is set."""
        model = MagicMock()
        model.run_on_all_machines.return_value = {
            "0": self._make_task(stdout=APT_POLICY_LANDSCAPE),
        }
        result = verify_apt_sources(model)
        assert result.unexpected == {}

    def test_landscape_mirror_unexpected_without_env(self):
        """Test that landscape mirror sources are flagged when env var is not set."""
        model = MagicMock()
        model.run_on_all_machines.return_value = {
            "0": self._make_task(stdout=APT_POLICY_LANDSCAPE_MIRROR),
        }
        result = verify_apt_sources(model)
        assert "0" in result.unexpected
        assert (
            "https://repo.mirror.example.com/repository/standalone/ubuntu"
            in result.unexpected["0"]
        )

    @patch.dict(
        "os.environ",
        {"LANDSCAPE_MIRROR_URI": "https://repo.mirror.example.com/repository/standalone"},
    )
    def test_landscape_mirror_clean(self):
        """Test that landscape mirror sources are accepted when env var matches."""
        model = MagicMock()
        model.run_on_all_machines.return_value = {
            "0": self._make_task(stdout=APT_POLICY_LANDSCAPE_MIRROR),
        }
        result = verify_apt_sources(model)
        assert result.unexpected == {}

    def test_multiple_machines_mixed(self):
        """Test with multiple machines, some clean and some with issues."""
        model = MagicMock()
        model.run_on_all_machines.return_value = {
            "0": self._make_task(stdout=APT_POLICY_CLEAN),
            "1": self._make_task(stdout=APT_POLICY_WITH_PPA),
            "2": self._make_task(stdout=APT_POLICY_WITH_THIRD_PARTY),
            "3": self._make_task(stdout=APT_POLICY_CLEAN),
        }
        result = verify_apt_sources(model)
        assert len(result.unexpected) == 2
        assert "1" in result.unexpected
        assert "2" in result.unexpected
        assert "0" not in result.unexpected
        assert "3" not in result.unexpected
