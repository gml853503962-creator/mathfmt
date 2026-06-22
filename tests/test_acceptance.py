"""Automated acceptance: scan → convert → validate for all 5 real-world test DOCX."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mathfmt.core import apply_docx, scan_docx
from mathfmt.validate import validate_docx

# Import the gen_docs builder from the acceptance test directory.
# If the module isn't importable (e.g. CI without the package installed),
# this test is skipped gracefully.
gen_docs = pytest.importorskip("tests.acceptance.gen_docs")


@pytest.fixture(scope="session")
def acceptance_docs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Generate the 5 acceptance DOCX files once per session."""
    tmp = tmp_path_factory.mktemp("acceptance")
    # Patch gen_docs.OUT to point to our tmp dir
    gen_docs.OUT = tmp

    # Rebuild the module-level OUT reference by regenerating
    paths = {}
    for name, builder in [
        ("doc01", gen_docs.doc01_basic),
        ("doc02", gen_docs.doc02_advanced),
        ("doc03", gen_docs.doc03_mixed),
        ("doc04", gen_docs.doc04_edge_cases),
        ("doc05", gen_docs.doc05_textbook),
    ]:
        path = builder()
        paths[name] = path
    return paths


def _scan_convert_validate(docx_path: Path, tmp_path: Path) -> dict:
    """Run full pipeline on one DOCX and return the validation report."""
    scan_report = tmp_path / f"{docx_path.stem}_scan.json"
    output_docx = tmp_path / f"{docx_path.stem}_output.docx"
    result_report = tmp_path / f"{docx_path.stem}_result.json"

    # Scan
    scan_result = scan_docx(docx_path, scan_report)
    candidates = scan_result.get("candidates", [])

    # Write a review that selects ALL candidates for full conversion
    for c in candidates:
        c["selected"] = True
    review = {
        "schema_version": 2,
        "candidates": candidates,
        "profile": {"derivatives": "fraction", "unit_step": "u(t)", "output": "native_word_omml"},
    }
    review_path = tmp_path / f"{docx_path.stem}_review.json"
    review_path.write_text(json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8")

    # Apply (selecting all candidates regardless of confidence)
    apply_docx(docx_path, review_path, output_docx, result_report)

    # Validate
    val = validate_docx(output_docx)
    return val


@pytest.mark.parametrize(
    "doc_name",
    ["doc01", "doc02", "doc03", "doc04", "doc05"],
)
def test_acceptance_scan_convert_validate(
    doc_name: str, acceptance_docs: dict[str, Path], tmp_path: Path
) -> None:
    """Every acceptance DOCX must pass scan → convert → validate."""
    docx_path = acceptance_docs[doc_name]
    val = _scan_convert_validate(docx_path, tmp_path)

    # Validation must pass (structural errors are hard failures)
    assert val.get("valid") is True, (
        f"{doc_name}: validation FAILED — structural_errors={val.get('omml', {}).get('structural_errors', [])}"
    )

    # Must produce at least one OMML equation
    eq_count = val.get("omml", {}).get("equation_count", 0)
    assert eq_count >= 1, f"{doc_name}: no OMML equations produced"


def test_acceptance_key_formulas_parse(acceptance_docs: dict[str, Path], tmp_path: Path) -> None:
    """Verify the 5 regression formulas are parseable in their DOCX context."""
    # Scan all docs and collect parse_status per source
    all_parse_status: dict[str, str] = {}
    for doc_name, docx_path in acceptance_docs.items():
        scan_report = tmp_path / f"{doc_name}_regression_scan.json"
        result = scan_docx(docx_path, scan_report)
        for c in result.get("candidates", []):
            all_parse_status[str(c.get("source", ""))] = str(c.get("parse_status", ""))

    # The 5 regression formulas must parse OK
    targets = [
        "1 + 2 + ... + n = n(n+1)/2",          # ellipsis
        "prod(i=1, n) i = n!",                  # factorial
        "int(cos(x)) dx = sin(x) + C",          # C retention
        "1(t)",                                  # step function
        "s = sqrt((1/(n-1)) sum(i=1, n) (x_i - x_bar)^2)",  # nested standard deviation
    ]
    for target in targets:
        assert all_parse_status.get(target) == "ok", (
            f"Regression formula {target!r} should parse ok, got {all_parse_status.get(target)!r}"
        )
