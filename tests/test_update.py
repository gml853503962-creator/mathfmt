from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from mathfmt.update import (
    CACHE_FILE,
    CACHE_TTL,
    UpdateInfo,
    _build_install_commands,
    _parse_semver,
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

    def test_malformed(self) -> None:
        assert _parse_semver("not-a-version") == ()
        assert _parse_semver("") == ()


class TestBuildInstallCommands:
    def test_returns_list(self) -> None:
        cmds = _build_install_commands("0.3.0")
        assert len(cmds) == 3
        assert any("pip install --upgrade mathfmt" == c for c in cmds)
        assert any("0.3.0" in c for c in cmds)
        assert any("github.com" in c for c in cmds)


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
    def test_returns_up_to_date_when_no_network(self) -> None:
        with patch("mathfmt.update.fetch_latest_release", return_value=None):
            with patch("mathfmt.update._load_cache", return_value=None):
                info = check_for_updates(force=True)
                assert not info.is_update_available

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
            "release_url": "",
            "release_notes": "",
            "published_at": "",
        }
        with patch("mathfmt.update._load_cache", return_value=cached):
            info = check_for_updates()
            assert info.is_update_available
            assert info.latest_version == "0.3.0"

    def test_bypasses_stale_cache(self) -> None:
        # When _load_cache returns None (stale/missing), it should fall
        # through to fetch_latest_release and get the real version.
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


class TestCache:
    def setup_method(self) -> None:
        self.tmp_cache = CACHE_FILE  # use a fixed reference for monkeypatching

    def test_load_cache_returns_none_for_missing_file(self) -> None:
        from mathfmt.update import _load_cache

        with patch.object(Path, "is_file", return_value=False):
            assert _load_cache() is None

    def test_load_cache_returns_none_for_invalid_json(
        self, tmp_path: Path
    ) -> None:
        from mathfmt.update import _load_cache

        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid", encoding="utf-8")
        with patch("mathfmt.update.CACHE_FILE", bad_file):
            assert _load_cache() is None

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        from mathfmt.update import _load_cache, _save_cache

        fake_data: dict[str, object] = {
            "checked_at": time.time(),
            "latest_version": "0.3.0",
            "is_update_available": True,
            "release_url": "https://example.com",
            "release_notes": "notes",
            "published_at": "2026-06-22",
        }
        with patch("mathfmt.update.CACHE_FILE", tmp_path / "cache.json"):
            _save_cache(fake_data)
            loaded = _load_cache()
            assert loaded is not None
            assert loaded["latest_version"] == "0.3.0"
            assert loaded["is_update_available"] is True
