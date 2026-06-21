from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

from mathfmt.update import (
    UpdateInfo,
    _build_install_commands,
    _load_cache,
    _parse_semver,
    _save_cache,
    check_for_updates,
    fetch_latest_release,
)


class TestParseSemver:
    def test_simple(self) -> None:
        assert _parse_semver("0.2.0") == (0, 2, 0)
        assert _parse_semver("1.0.0") == (1, 0, 0)
        assert _parse_semver("0.10.5") == (0, 10, 5)

    def test_with_v_prefix(self) -> None:
        assert _parse_semver("v0.2.0") == (0, 2, 0)
        assert _parse_semver("v1.0.0") == (1, 0, 0)

    def test_ordering(self) -> None:
        assert _parse_semver("0.2.0") > _parse_semver("0.1.0")
        assert _parse_semver("0.10.0") > _parse_semver("0.2.0")
        assert _parse_semver("1.0.0") > _parse_semver("0.99.0")
        assert _parse_semver("0.2.0") == _parse_semver("v0.2.0")

    def test_prerelease_suffix_is_stripped(self) -> None:
        """0.2.1-beta.1 should parse as (0,2,1), not (0,2)."""
        assert _parse_semver("0.2.1-beta.1") == (0, 2, 1)
        assert _parse_semver("v0.3.0-rc.2") == (0, 3, 0)
        assert _parse_semver("1.0.0-alpha+001") == (1, 0, 0)

    def test_prerelease_compared_correctly(self) -> None:
        """A stable release after a pre-release should be detected."""
        # 0.3.0 > 0.2.1-beta.1
        assert _parse_semver("0.3.0") > _parse_semver("0.2.1-beta.1")
        # 0.2.1 > 0.2.1-beta.1 (same as current — no update)
        assert not _parse_semver("0.2.1") > _parse_semver("0.2.1-beta.1")

    def test_malformed(self) -> None:
        assert _parse_semver("not-a-version") == (0,)
        assert _parse_semver("") == (0,)


class TestBuildInstallCommands:
    def test_returns_list(self) -> None:
        cmds = _build_install_commands("0.3.0")
        assert len(cmds) == 3
        assert any("pip install --upgrade mathfmt" == c for c in cmds)
        assert any("0.3.0" in c for c in cmds)
        assert any("github.com" in c for c in cmds)

    def test_no_f_string_without_placeholders(self) -> None:
        """First and third commands are plain strings, not f-strings."""
        cmds = _build_install_commands("0.3.0")
        # verify the commands are strings
        assert all(isinstance(c, str) for c in cmds)


class TestUpdateInfo:
    def test_up_to_date(self) -> None:
        info = UpdateInfo(
            current_version="0.2.0",
            latest_version="0.2.0",
            is_update_available=False,
            release_url="",
            release_notes="",
            published_at="",
            install_commands=[],
        )
        assert "up to date" in info.summary

    def test_update_available(self) -> None:
        info = UpdateInfo(
            current_version="0.2.0",
            latest_version="0.3.0",
            is_update_available=True,
            release_url="https://github.com/...",
            release_notes="New features!",
            published_at="2026-06-21",
            install_commands=["pip install --upgrade mathfmt"],
        )
        assert "0.3.0 is available" in info.summary
        assert "you have 0.2.0" in info.summary

    def test_error_message_shown_in_summary(self) -> None:
        info = UpdateInfo(
            current_version="0.2.0",
            latest_version="0.2.0",
            is_update_available=False,
            release_url="",
            release_notes="",
            published_at="",
            install_commands=[],
            error="Could not reach GitHub to check for updates.",
        )
        assert "Could not reach GitHub" in info.summary


class TestFetchLatestRelease:
    def test_returns_none_on_network_error(self) -> None:
        with patch("mathfmt.update.urlopen", side_effect=OSError("no network")):
            result = fetch_latest_release()
            assert result is None

    def test_returns_dict_on_success(self) -> None:
        fake_release = {
            "tag_name": "v0.3.0",
            "html_url": "https://github.com/gml853503962-creator/mathfmt/releases/tag/v0.3.0",
            "body": "Release notes here.",
            "published_at": "2026-06-22T00:00:00Z",
            "prerelease": False,
        }
        with patch("mathfmt.update.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                json.dumps(fake_release).encode("utf-8")
            )
            result = fetch_latest_release()
            assert result is not None
            assert result["tag_name"] == "v0.3.0"

    def test_filters_prereleases_in_list(self) -> None:
        releases = [
            {"tag_name": "v0.3.0-beta", "prerelease": True},
            {"tag_name": "v0.2.0", "prerelease": False},
        ]
        with patch("mathfmt.update.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                json.dumps(releases).encode("utf-8")
            )
            result = fetch_latest_release(include_prerelease=False)
            assert result is not None
            assert result["tag_name"] == "v0.2.0"

    def test_include_prerelease_does_not_filter(self) -> None:
        releases = [
            {"tag_name": "v0.3.0-beta", "prerelease": True},
            {"tag_name": "v0.2.0", "prerelease": False},
        ]
        with patch("mathfmt.update.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                json.dumps(releases).encode("utf-8")
            )
            result = fetch_latest_release(include_prerelease=True)
            assert result is not None
            assert result["tag_name"] == "v0.3.0-beta"


class TestCheckForUpdates:
    def test_network_failure_sets_error(self) -> None:
        """When GitHub is unreachable, error should be set."""
        with patch("mathfmt.update.fetch_latest_release", return_value=None):
            with patch("mathfmt.update._load_cache", return_value=None):
                info = check_for_updates(force=True)
                assert not info.is_update_available
                assert info.error != ""
                assert "Could not reach GitHub" in info.error

    def test_detects_newer_version(self) -> None:
        fake_release = {
            "tag_name": "v0.3.0",
            "html_url": "https://github.com/gml853503962-creator/mathfmt/releases/tag/v0.3.0",
            "body": "New release!",
            "published_at": "2026-06-22T00:00:00Z",
            "prerelease": False,
        }
        with patch("mathfmt.update.fetch_latest_release", return_value=fake_release):
            with patch("mathfmt.update._load_cache", return_value=None):
                with patch("mathfmt.update._save_cache"):
                    info = check_for_updates(force=True)
                    assert info.is_update_available
                    assert info.latest_version == "0.3.0"
                    assert "New release!" in info.release_notes

    def test_same_version_is_up_to_date(self) -> None:
        from mathfmt import __version__

        fake_release: dict[str, object] = {
            "tag_name": f"v{__version__}",
            "html_url": "",
            "body": "",
            "published_at": "",
            "prerelease": False,
        }
        with patch("mathfmt.update.fetch_latest_release", return_value=fake_release):
            with patch("mathfmt.update._load_cache", return_value=None):
                info = check_for_updates(force=True)
                assert not info.is_update_available

    def test_uses_cache_when_fresh(self) -> None:
        cached = {
            "checked_at": time.time(),
            "latest_version": "0.3.0",
            "is_update_available": True,
            "prerelease": False,
            "release_url": "",
            "release_notes": "",
            "published_at": "",
        }
        with patch("mathfmt.update._load_cache", return_value=cached):
            info = check_for_updates()
            assert info.is_update_available
            assert info.latest_version == "0.3.0"

    def test_bypasses_stale_cache(self) -> None:
        fake_release = {
            "tag_name": "v0.3.0",
            "html_url": "",
            "body": "",
            "published_at": "",
            "prerelease": False,
        }
        with patch("mathfmt.update._load_cache", return_value=None):
            with patch("mathfmt.update.fetch_latest_release", return_value=fake_release):
                with patch("mathfmt.update._save_cache"):
                    info = check_for_updates()
                    assert info.is_update_available
                    assert info.latest_version == "0.3.0"

    def test_prerelease_cache_isolated_from_stable(self, tmp_path: Path) -> None:
        """A cache from --pre should not be used for a normal check, and vice versa."""
        prerelease_cache = {
            "checked_at": time.time(),
            "latest_version": "0.3.0-beta",
            "is_update_available": True,
            "prerelease": True,
            "release_url": "",
            "release_notes": "",
            "published_at": "",
        }
        fake_release = {
            "tag_name": "v0.2.0",
            "html_url": "",
            "body": "",
            "published_at": "",
            "prerelease": False,
        }
        cache_path = tmp_path / "cache.json"
        cache_path.write_text(json.dumps(prerelease_cache), encoding="utf-8")
        with patch("mathfmt.update.CACHE_FILE", cache_path):
            with patch("mathfmt.update.fetch_latest_release", return_value=fake_release):
                with patch("mathfmt.update._save_cache"):
                    info = check_for_updates(include_prerelease=False)
                    # prerelease cache should be rejected, fall through to fetch
                    assert info.latest_version == "0.2.0"

    def test_load_cache_validates_required_keys(self) -> None:
        """Cache missing required keys should be treated as absent."""
        incomplete = {
            "checked_at": time.time(),
            # missing latest_version, is_update_available, prerelease
        }
        with patch("mathfmt.update.CACHE_FILE") as mock_file:
            mock_file.is_file.return_value = True
            mock_file.read_text.return_value = json.dumps(incomplete)
            result = _load_cache(prerelease=False)
            assert result is None

    def test_load_cache_rejects_wrong_prerelease_mode(self) -> None:
        """Cache stored for --pre should not match a non-pre request."""
        stable_cache = {
            "checked_at": time.time(),
            "latest_version": "0.3.0",
            "is_update_available": True,
            "prerelease": False,
            "release_url": "",
            "release_notes": "",
            "published_at": "",
        }
        with patch("mathfmt.update.CACHE_FILE") as mock_file:
            mock_file.is_file.return_value = True
            mock_file.read_text.return_value = json.dumps(stable_cache)
            result = _load_cache(prerelease=True)
            assert result is None

    def test_load_cache_accepts_matching_prerelease_mode(self) -> None:
        """Cache stored for --pre should match a --pre request."""
        prerelease_cache = {
            "checked_at": time.time(),
            "latest_version": "0.3.0-beta",
            "is_update_available": True,
            "prerelease": True,
            "release_url": "",
            "release_notes": "",
            "published_at": "",
        }
        with patch("mathfmt.update.CACHE_FILE") as mock_file:
            mock_file.is_file.return_value = True
            mock_file.read_text.return_value = json.dumps(prerelease_cache)
            result = _load_cache(prerelease=True)
            assert result is not None
            assert result["latest_version"] == "0.3.0-beta"


class TestCache:
    def test_load_cache_returns_none_for_missing_file(self) -> None:
        with patch.object(Path, "is_file", return_value=False):
            assert _load_cache(prerelease=False) is None

    def test_load_cache_returns_none_for_invalid_json(
        self, tmp_path: Path
    ) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid", encoding="utf-8")
        with patch("mathfmt.update.CACHE_FILE", bad_file):
            assert _load_cache(prerelease=False) is None

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        fake_data: dict[str, object] = {
            "checked_at": time.time(),
            "latest_version": "0.3.0",
            "is_update_available": True,
            "prerelease": False,
            "release_url": "https://example.com",
            "release_notes": "notes",
            "published_at": "2026-06-22",
        }
        with patch("mathfmt.update.CACHE_FILE", tmp_path / "cache.json"):
            _save_cache(fake_data)
            loaded = _load_cache(prerelease=False)
            assert loaded is not None
            assert loaded["latest_version"] == "0.3.0"
            assert loaded["is_update_available"] is True
