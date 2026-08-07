from __future__ import annotations

import json
from pathlib import Path

import pytest

from mathfmt import cli
from mathfmt.core import W_NS
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


def test_alias_profile_is_supported_across_cli_formula_commands(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    alias_path = tmp_path / "engineering.json"
    alias_path.write_text(
        json.dumps({"name": "engineering", "aliases": {"ohm": "Ω"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    source = make_docx(
        tmp_path / "source.docx",
        document_xml=(
            f'<w:document xmlns:w="{W_NS}"><w:body>'
            "<w:p><w:r><w:t>Resistance: $R = ohm$.</w:t></w:r></w:p>"
            "</w:body></w:document>"
        ),
    )
    review = tmp_path / "review.json"
    output = tmp_path / "output.docx"
    result = tmp_path / "result.json"
    xsl = make_fake_xsl(tmp_path / "fake.xsl")

    assert cli.main(["scan", str(source), "--report", str(review), "--aliases", str(alias_path)]) == 0
    capsys.readouterr()
    scanned = json.loads(review.read_text(encoding="utf-8"))
    assert scanned["profile"]["aliases"]["name"] == "engineering"

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
                "--aliases",
                str(alias_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert json.loads(result.read_text(encoding="utf-8"))["options"]["alias_profile"]["name"] == (
        "engineering"
    )

    assert (
        cli.main(
            [
                "validate",
                str(output),
                "--review",
                str(review),
                "--aliases",
                str(alias_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

    converted = tmp_path / "converted.docx"
    converted_report = tmp_path / "converted.json"
    assert (
        cli.main(
            [
                "convert",
                str(source),
                "--output",
                str(converted),
                "--report",
                str(converted_report),
                "--xsl",
                str(xsl),
                "--aliases",
                str(alias_path),
            ]
        )
        == 0
    )
    assert json.loads(converted_report.read_text(encoding="utf-8"))["converted_count"] == 1


def test_cli_invalid_alias_profile_returns_nonzero(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = make_docx(tmp_path / "source.docx")
    aliases = tmp_path / "aliases.json"
    aliases.write_text('{"aliases":{"sqrt":"√"}}', encoding="utf-8")

    code = cli.main(
        ["scan", str(source), "--report", str(tmp_path / "review.json"), "--aliases", str(aliases)]
    )

    assert code == 1
    assert "reserved by MathFmt core syntax" in capsys.readouterr().err


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
    output = capsys.readouterr().out
    assert "Ready: yes" in output
    assert "lxml:" in output
    assert "libxml2:" in output
    assert "libxslt:" in output
    assert cli.main(["doctor", "--xsl", str(xsl), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["ready"] is True
    assert data["lxml"]
    assert data["libxml2"]
    assert data["libxslt"]


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


def test_convert_batch_glob_writes_outputs_and_aggregate_report(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    make_docx(sources / "alpha.docx")
    make_docx(sources / "beta.docx")
    outputs = tmp_path / "outputs"
    reports = tmp_path / "reports"
    batch_report = tmp_path / "batch.json"

    code = cli.main(
        [
            "convert",
            str(sources / "*.docx"),
            "--output-dir",
            str(outputs),
            "--report-dir",
            str(reports),
            "--batch-report",
            str(batch_report),
        ]
    )

    assert code == 0
    assert (outputs / "alpha.mathfmt.docx").is_file()
    assert (outputs / "beta.mathfmt.docx").is_file()
    assert (reports / "alpha.mathfmt.report.json").is_file()
    assert (reports / "beta.mathfmt.report.json").is_file()
    data = json.loads(batch_report.read_text(encoding="utf-8"))
    assert data["report_type"] == "batch_conversion"
    assert data["summary"]["files"] == 2
    assert data["summary"]["succeeded"] == 2
    assert {item["status"] for item in data["files"]} == {"success"}
    assert "Batch summary:" in capsys.readouterr().out


def test_convert_directory_skips_existing_mathfmt_outputs(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    make_docx(sources / "source.docx")
    make_docx(sources / "old.mathfmt.docx")
    expanded, batch_requested = cli.expand_convert_inputs([sources])

    assert batch_requested is True
    assert [path.name for path in expanded] == ["source.docx"]


def test_convert_batch_continues_after_bad_docx(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "bad.docx").write_bytes(b"not-a-docx")
    make_docx(sources / "good.docx")
    outputs = tmp_path / "outputs"
    batch_report = tmp_path / "batch.json"

    code = cli.main(
        [
            "convert",
            str(sources),
            "--output-dir",
            str(outputs),
            "--batch-report",
            str(batch_report),
        ]
    )

    assert code == 1
    assert (outputs / "good.mathfmt.docx").is_file()
    data = json.loads(batch_report.read_text(encoding="utf-8"))
    assert data["summary"]["failed"] == 1
    assert data["summary"]["succeeded"] == 1
    assert {item["status"] for item in data["files"]} == {"failed", "success"}


def test_convert_batch_rejects_output_name_collisions(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    make_docx(first / "same.docx")
    make_docx(second / "same.docx")

    code = cli.main(
        [
            "convert",
            str(first / "same.docx"),
            str(second / "same.docx"),
            "--output-dir",
            str(tmp_path / "outputs"),
        ]
    )

    assert code == 1
    assert "same output DOCX" in capsys.readouterr().err
