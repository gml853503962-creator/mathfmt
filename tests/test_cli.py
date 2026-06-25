from __future__ import annotations

import json
from pathlib import Path

import pytest

from mathfmt import cli
from tests.helpers import make_docx, make_fake_xsl


def test_default_paths() -> None:
    source = Path("notes.docx")
    output = cli.default_output(source)
    assert output == Path("notes.mathfmt.docx")
    assert cli.default_result_report(output) == Path("notes.mathfmt.report.json")


def test_doctor_data_reports_ready_with_explicit_xsl(tmp_path: Path) -> None:
    xsl = make_fake_xsl(tmp_path / "fake.xsl")
    data = cli.doctor_data(xsl)
    assert data["ready"] is True
    assert data["xsl"] == str(xsl.resolve())


def test_doctor_data_reports_builtin_backend_when_xsl_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(_: Path | None = None) -> Path:
        raise FileNotFoundError("missing test stylesheet")

    monkeypatch.setattr(cli, "find_xsl", missing)
    data = cli.doctor_data()
    assert data["ready"] is True
    assert data["backend"] == "python"
    assert data["xsl"] is None


def test_scan_and_apply_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = make_docx(tmp_path / "source.docx")
    review = tmp_path / "review.json"
    output = tmp_path / "output.docx"
    result = tmp_path / "result.json"
    xsl = make_fake_xsl(tmp_path / "fake.xsl")

    assert cli.main(["scan", str(source), "--report", str(review)]) == 0
    assert "Candidates:" in capsys.readouterr().out
    assert (
        cli.main(
            [
                "apply",
                str(source),
                "--review",
                str(review),
                "--output",
                str(output),
                "--report",
                str(result),
                "--xsl",
                str(xsl),
            ]
        )
        == 0
    )
    assert output.is_file()
    assert "Converted:" in capsys.readouterr().out


def test_apply_requires_output_unless_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = make_docx(tmp_path / "source.docx")
    review = tmp_path / "review.json"
    result = tmp_path / "result.json"

    assert cli.main(["scan", str(source), "--report", str(review)]) == 0
    capsys.readouterr()

    code = cli.main(["apply", str(source), "--review", str(review), "--report", str(result)])
    assert code == 1
    assert "requires --output unless --dry-run" in capsys.readouterr().err


def test_apply_dry_run_does_not_require_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = make_docx(tmp_path / "source.docx")
    review = tmp_path / "review.json"
    result = tmp_path / "result.json"

    assert cli.main(["scan", str(source), "--report", str(review)]) == 0
    capsys.readouterr()

    code = cli.main(["apply", str(source), "--review", str(review), "--report", str(result), "--dry-run"])
    output = capsys.readouterr().out
    report = json.loads(result.read_text(encoding="utf-8"))

    assert code == 0
    assert "dry-run, not written" in output
    assert not (tmp_path / "source.mathfmt.docx").exists()
    assert report["options"]["dry_run"] is True
    assert report["summary"]["output_written"] is False


def test_apply_strict_returns_failure_without_writing_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = make_docx(tmp_path / "source.docx")
    review = tmp_path / "review.json"
    output = tmp_path / "output.docx"
    result = tmp_path / "result.json"
    review.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "id": "stale",
                        "selected": True,
                        "part": "word/document.xml",
                        "paragraph_index": 0,
                        "start": 0,
                        "end": 5,
                        "source": "wrong",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    code = cli.main(
        [
            "apply",
            str(source),
            "--review",
            str(review),
            "--output",
            str(output),
            "--report",
            str(result),
            "--strict",
        ]
    )
    capsys.readouterr()
    report = json.loads(result.read_text(encoding="utf-8"))

    assert code == 1
    assert not output.exists()
    assert report["options"]["strict"] is True
    assert report["summary"]["strict_failed"] is True


def test_doctor_command_text_and_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    xsl = make_fake_xsl(tmp_path / "fake.xsl")
    assert cli.main(["doctor", "--xsl", str(xsl)]) == 0
    assert "Ready: yes" in capsys.readouterr().out
    assert cli.main(["doctor", "--xsl", str(xsl), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ready"] is True


def test_cli_reports_missing_input(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["scan", "missing.docx", "--report", "report.json"]) == 1
    assert "mathfmt: error:" in capsys.readouterr().err


def test_doctor_command_falls_back_to_builtin_backend(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["doctor", "--xsl", "missing.xsl"]) == 0
    output = capsys.readouterr().out
    assert "Ready: yes" in output
    assert "python" in output


def test_cli_reports_invalid_review_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = make_docx(tmp_path / "source.docx")
    review = tmp_path / "review.json"
    review.write_text("{", encoding="utf-8")
    xsl = make_fake_xsl(tmp_path / "fake.xsl")
    code = cli.main(
        [
            "apply",
            str(source),
            "--review",
            str(review),
            "--output",
            str(tmp_path / "out.docx"),
            "--report",
            str(tmp_path / "result.json"),
            "--xsl",
            str(xsl),
        ]
    )
    assert code == 1
    assert "mathfmt: error:" in capsys.readouterr().err


def test_version_argument_exits_cleanly(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="0"):
        cli.main(["--version"])
    assert "MathFmt" in capsys.readouterr().out


def test_doctor_json_reports_python_backend_without_xsl(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def missing(_: Path | None = None) -> Path:
        raise FileNotFoundError("missing")

    monkeypatch.setattr(cli, "find_xsl", missing)
    code = cli.main(["doctor", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert code == 0
    assert data["ready"] is True
    assert data["backend"] == "python"
    assert data["xsl"] is None


def test_update_command_shows_up_to_date(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from mathfmt.update import UpdateInfo

    fake_info = UpdateInfo(
        current_version="0.2.0",
        latest_version="0.2.0",
        is_update_available=False,
        release_url="",
        release_notes="",
        published_at="",
        install_commands=[],
    )

    monkeypatch.setattr(cli, "check_for_updates", lambda **kw: fake_info)
    code = cli.main(["update"])
    assert code == 0
    assert "up to date" in capsys.readouterr().out


def test_update_command_shows_available_update(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from mathfmt.update import UpdateInfo

    fake_info = UpdateInfo(
        current_version="0.2.0",
        latest_version="0.3.0",
        is_update_available=True,
        release_url="https://github.com/gml853503962-creator/mathfmt/releases/tag/v0.3.0",
        release_notes="Bug fixes and new features.",
        published_at="2026-06-22",
        install_commands=["pip install --upgrade mathfmt"],
    )

    monkeypatch.setattr(cli, "check_for_updates", lambda **kw: fake_info)
    code = cli.main(["update"])
    assert code == 0
    out = capsys.readouterr().out
    assert "0.3.0 is available" in out
    assert "pip install --upgrade mathfmt" in out


def test_update_check_flag_exits_1_when_update_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mathfmt.update import UpdateInfo

    fake_info = UpdateInfo(
        current_version="0.2.0",
        latest_version="0.3.0",
        is_update_available=True,
        release_url="",
        release_notes="",
        published_at="",
        install_commands=["pip install --upgrade mathfmt"],
    )

    monkeypatch.setattr(cli, "check_for_updates", lambda **kw: fake_info)
    assert cli.main(["update", "--check"]) == 1


def test_update_check_flag_exits_0_when_up_to_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mathfmt.update import UpdateInfo

    fake_info = UpdateInfo(
        current_version="0.2.0",
        latest_version="0.2.0",
        is_update_available=False,
        release_url="",
        release_notes="",
        published_at="",
        install_commands=[],
    )

    monkeypatch.setattr(cli, "check_for_updates", lambda **kw: fake_info)
    assert cli.main(["update", "--check"]) == 0


def test_update_network_error_exits_2_with_check(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from mathfmt.update import UpdateInfo

    fake_info = UpdateInfo(
        current_version="0.2.0",
        latest_version="0.2.0",
        is_update_available=False,
        release_url="",
        release_notes="",
        published_at="",
        install_commands=[],
        error="Could not reach GitHub to check for updates.",
    )

    monkeypatch.setattr(cli, "check_for_updates", lambda **kw: fake_info)
    assert cli.main(["update", "--check"]) == 2
    assert "Could not reach GitHub" in capsys.readouterr().out


def test_update_network_error_exits_2_without_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mathfmt.update import UpdateInfo

    fake_info = UpdateInfo(
        current_version="0.2.0",
        latest_version="0.2.0",
        is_update_available=False,
        release_url="",
        release_notes="",
        published_at="",
        install_commands=[],
        error="Could not reach GitHub to check for updates.",
    )

    monkeypatch.setattr(cli, "check_for_updates", lambda **kw: fake_info)
    assert cli.main(["update"]) == 2
