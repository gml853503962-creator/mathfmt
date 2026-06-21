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


def test_doctor_data_reports_missing_xsl(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(_: Path | None = None) -> Path:
        raise FileNotFoundError("missing test stylesheet")

    monkeypatch.setattr(cli, "find_xsl", missing)
    data = cli.doctor_data()
    assert data["ready"] is False
    assert data["error"] == "missing test stylesheet"


def test_scan_and_apply_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = make_docx(tmp_path / "source.docx")
    review = tmp_path / "review.json"
    output = tmp_path / "output.docx"
    result = tmp_path / "result.json"
    xsl = make_fake_xsl(tmp_path / "fake.xsl")

    assert cli.main(["scan", str(source), "--report", str(review)]) == 0
    assert "Candidates:" in capsys.readouterr().out
    assert cli.main(
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
    ) == 0
    assert output.is_file()
    assert "Converted:" in capsys.readouterr().out


def test_doctor_command_text_and_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    xsl = make_fake_xsl(tmp_path / "fake.xsl")
    assert cli.main(["doctor", "--xsl", str(xsl)]) == 0
    assert "Ready: yes" in capsys.readouterr().out
    assert cli.main(["doctor", "--xsl", str(xsl), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ready"] is True


def test_cli_reports_missing_input(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["scan", "missing.docx", "--report", "report.json"]) == 1
    assert "mathfmt: error:" in capsys.readouterr().err


def test_doctor_command_explains_missing_xsl(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["doctor", "--xsl", "missing.xsl"]) == 1
    output = capsys.readouterr().out
    assert "Ready: no" in output
    assert "not found" in output


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
