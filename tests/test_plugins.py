from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from mathfmt import FormulaCandidate, RecognizerError, cli, load_recognizer
from mathfmt.core import W_NS, candidate_spans, scan_docx
from mathfmt.plugins import normalize_recognizers, recognize_with_plugins, recognizer_metadata
from tests.helpers import make_docx


class BracketRecognizer:
    name = "bracket-equation"
    version = "1.0"

    def recognize(self, text: str) -> list[FormulaCandidate]:
        candidates: list[FormulaCandidate] = []
        for match in re.finditer(r"calc\{(?P<name>[A-Za-z]+)\}", text):
            name = match.group("name")
            candidates.append(
                FormulaCandidate(
                    match.start(),
                    match.end(),
                    match.group(),
                    linear=f"{name}^2",
                    confidence="high",
                    confidence_reason="explicit calc plugin syntax",
                    kind="square",
                )
            )
        return candidates


def test_recognizer_candidates_are_validated_and_annotated() -> None:
    spans = recognize_with_plugins("Use calc{x} here.", [BracketRecognizer()])

    assert len(spans) == 1
    assert spans[0].source == "calc{x}"
    assert spans[0].linear == "x^2"
    assert spans[0].recognizer == "bracket-equation"
    assert spans[0].kind == "square"


def test_builtin_candidate_wins_plugin_overlap() -> None:
    class OverlapRecognizer:
        name = "overlap"

        def recognize(self, text: str) -> list[FormulaCandidate]:
            return [FormulaCandidate(0, len(text), text, linear="y = 2", confidence="high")]

    spans = candidate_spans("x^2 = 1", [OverlapRecognizer()])

    assert len(spans) == 1
    assert spans[0].recognizer is None
    assert spans[0].source == "x^2 = 1"


@pytest.mark.parametrize(
    "candidate,error",
    [
        (FormulaCandidate(-1, 2, "ab"), "invalid range"),
        (FormulaCandidate(0, 2, "wrong"), "does not match"),
        (FormulaCandidate(0, 2, "ab", linear=" "), "empty linear"),
        (FormulaCandidate(0, 2, "ab", linear=42), "empty linear"),
        (FormulaCandidate(0, 2, "ab", display="yes"), "non-boolean 'display'"),
        (FormulaCandidate(0, 2, "ab", explicit=1), "non-boolean 'explicit'"),
        (FormulaCandidate(0, 2, "ab", chemistry=None), "non-boolean 'chemistry'"),
        (FormulaCandidate(0, 2, "ab", physics=42), "invalid physics kind"),
        (FormulaCandidate(0, 2, "ab", confidence="certain"), "invalid confidence"),
    ],
)
def test_invalid_plugin_candidates_fail_clearly(
    candidate: FormulaCandidate,
    error: str,
) -> None:
    class InvalidRecognizer:
        name = "invalid"

        def recognize(self, text: str) -> list[FormulaCandidate]:
            return [candidate]

    with pytest.raises(RecognizerError, match=error):
        recognize_with_plugins("ab", [InvalidRecognizer()])


def test_plugin_exception_is_wrapped_with_name() -> None:
    class BrokenRecognizer:
        name = "broken"

        def recognize(self, text: str) -> list[FormulaCandidate]:
            raise RuntimeError("boom")

    with pytest.raises(RecognizerError, match="'broken' failed: boom"):
        recognize_with_plugins("text", [BrokenRecognizer()])


def test_duplicate_recognizer_names_are_rejected() -> None:
    with pytest.raises(RecognizerError, match="Duplicate formula recognizer name"):
        normalize_recognizers([BracketRecognizer(), BracketRecognizer()])


def test_invalid_recognizer_version_is_rejected() -> None:
    class InvalidVersionRecognizer:
        name = "invalid-version"
        version = 2

        def recognize(self, text: str) -> list[FormulaCandidate]:
            return []

    with pytest.raises(RecognizerError, match="version must be a non-empty string"):
        normalize_recognizers([InvalidVersionRecognizer()])


def test_scan_report_records_plugin_and_candidate_metadata(tmp_path: Path) -> None:
    source = make_docx(
        tmp_path / "source.docx",
        document_xml=(
            f'<w:document xmlns:w="{W_NS}"><w:body>'
            "<w:p><w:r><w:t>Use calc{x} here.</w:t></w:r></w:p>"
            "</w:body></w:document>"
        ),
    )
    report_path = tmp_path / "report.json"

    report = scan_docx(source, report_path, recognizers=[BracketRecognizer()])

    assert report["profile"]["recognizers"] == [
        {
            "name": "bracket-equation",
            "module": "tests.test_plugins",
            "object": "BracketRecognizer",
            "version": "1.0",
        }
    ]
    plugin_candidates = [
        candidate for candidate in report["candidates"] if candidate["recognizer"] == "bracket-equation"
    ]
    assert len(plugin_candidates) == 1
    candidate = plugin_candidates[0]
    assert candidate["source"] == "calc{x}"
    assert candidate["linear"] == "x^2"
    assert candidate["selected"] is True
    assert candidate["recognizer"] == "bracket-equation"
    assert candidate["recognizer_kind"] == "square"
    assert candidate["parse_status"] == "ok"


def test_unparseable_plugin_formula_is_reviewable_not_selected(tmp_path: Path) -> None:
    class ReviewRecognizer:
        name = "review-plugin"

        def recognize(self, text: str) -> list[FormulaCandidate]:
            return [FormulaCandidate(0, len(text), text, linear="x +", confidence="high")]

    source = make_docx(
        tmp_path / "source.docx",
        document_xml=(
            f'<w:document xmlns:w="{W_NS}"><w:body>'
            "<w:p><w:r><w:t>custom</w:t></w:r></w:p>"
            "</w:body></w:document>"
        ),
    )

    report = scan_docx(source, tmp_path / "report.json", recognizers=[ReviewRecognizer()])

    candidate = next(item for item in report["candidates"] if item["recognizer"] == "review-plugin")
    assert candidate["parse_status"] == "review"
    assert candidate["selected"] is False
    assert "parse_error" in candidate


def test_load_recognizer_and_cli_scan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = tmp_path / "custom_mathfmt_plugin.py"
    module_path.write_text(
        """from mathfmt import FormulaCandidate

class Recognizer:
    name = "loaded-plugin"
    version = "2"

    def recognize(self, text):
        source = "custom-token"
        start = text.find(source)
        if start < 0:
            return []
        return [FormulaCandidate(start, start + len(source), source, linear="z^3", confidence="high")]
""",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    recognizer = load_recognizer("custom_mathfmt_plugin:Recognizer")
    assert recognizer_metadata(recognizer) == {
        "name": "loaded-plugin",
        "module": "custom_mathfmt_plugin",
        "object": "Recognizer",
        "spec": "custom_mathfmt_plugin:Recognizer",
        "version": "2",
    }

    source = make_docx(
        tmp_path / "source.docx",
        document_xml=(
            f'<w:document xmlns:w="{W_NS}"><w:body>'
            "<w:p><w:r><w:t>Use custom-token here.</w:t></w:r></w:p>"
            "</w:body></w:document>"
        ),
    )
    report_path = tmp_path / "report.json"

    assert (
        cli.main(
            [
                "scan",
                str(source),
                "--report",
                str(report_path),
                "--recognizer",
                "custom_mathfmt_plugin:Recognizer",
            ]
        )
        == 0
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["profile"]["recognizers"][0]["spec"] == "custom_mathfmt_plugin:Recognizer"
    assert report["candidates"][0]["linear"] == "z^3"

    output = tmp_path / "output.docx"
    result_path = tmp_path / "result.json"
    assert (
        cli.main(
            [
                "convert",
                str(source),
                "--output",
                str(output),
                "--report",
                str(result_path),
                "--recognizer",
                "custom_mathfmt_plugin:Recognizer",
            ]
        )
        == 0
    )
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert output.is_file()
    assert result["options"]["recognizers"][0]["name"] == "loaded-plugin"
    assert any(item["recognizer"] == "loaded-plugin" for item in result["formulas"])


def test_load_recognizer_wraps_constructor_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module_path = tmp_path / "broken_mathfmt_plugin.py"
    module_path.write_text(
        """class Recognizer:
    def __init__(self):
        raise RuntimeError("constructor boom")
""",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(RecognizerError, match="constructor boom"):
        load_recognizer("broken_mathfmt_plugin:Recognizer")


def test_cli_bad_recognizer_returns_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main(["scan", "missing.docx", "--report", "report.json", "--recognizer", "invalid-spec"])

    assert code == 1
    assert "module:object" in capsys.readouterr().err
