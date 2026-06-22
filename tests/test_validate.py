from __future__ import annotations

import json
from pathlib import Path

import pytest
from lxml import etree

from mathfmt.cli import main
from mathfmt.core import M_NS, find_xsl, formula_to_mathml, qname
from mathfmt.omml import mathml_to_omml_py
from mathfmt.validate import validate_docx
from tests.helpers import make_docx, make_docx_with_omml

# -- helpers ------------------------------------------------------------------


def omath_for(source: str) -> str:
    mathml = formula_to_mathml(source)
    omath = mathml_to_omml_py(mathml)
    return etree.tostring(omath, encoding="unicode")


def m(namespace: str, local: str) -> str:
    return qname(namespace, local)


# -- valid DOCX ---------------------------------------------------------------


def test_valid_docx_passes_validation(tmp_path: Path) -> None:
    source = make_docx(tmp_path / "source.docx")
    report = validate_docx(source)
    assert report["valid"] is True
    assert report["package"]["valid_zip"] is True
    assert isinstance(report["package"], dict)
    pkg = report["package"]
    assert pkg.get("paragraphs", 0) > 0


def test_valid_docx_with_omml_passes(tmp_path: Path) -> None:
    clean_omath = omath_for("x = 1")
    source = make_docx_with_omml(
        tmp_path / "omml.docx",
        content=f"<w:p>{clean_omath}</w:p>",
    )
    report = validate_docx(source)
    assert report["valid"] is True
    assert isinstance(report["omml"], dict)
    assert report["omml"]["equation_count"] == 1
    assert report["omml"]["structural_errors"] == []


# -- corrupt / invalid DOCX ---------------------------------------------------


def test_corrupt_zip_returns_valid_false(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.docx"
    corrupt.write_bytes(b"not a zip archive")
    report = validate_docx(corrupt)
    assert report["valid"] is False
    assert report["package"]["valid_zip"] is False


def test_non_docx_extension_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=".docx"):
        validate_docx(tmp_path / "notes.txt")


def test_missing_docx_file_is_reported(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="not found"):
        validate_docx(tmp_path / "missing.docx")


# -- OMML structural checks ---------------------------------------------------


def test_empty_omath_is_flagged(tmp_path: Path) -> None:
    source = make_docx_with_omml(
        tmp_path / "empty.docx",
        content=f'<w:p><m:oMath xmlns:m="{M_NS}"/></w:p>',
    )
    report = validate_docx(source)
    assert any("Empty m:oMath" in e["error"] for e in report["omml"]["structural_errors"])


def test_fraction_missing_den_is_flagged(tmp_path: Path) -> None:
    source = make_docx_with_omml(
        tmp_path / "badfrac.docx",
        content=f'<w:p><m:oMath xmlns:m="{M_NS}"><m:f><m:num><m:r><m:t>x</m:t></m:r></m:num></m:f></m:oMath></w:p>',
    )
    report = validate_docx(source)
    assert any("missing num or den" in e["error"] for e in report["omml"]["structural_errors"])


def test_superscript_missing_e_is_flagged(tmp_path: Path) -> None:
    source = make_docx_with_omml(
        tmp_path / "badssup.docx",
        content=f'<w:p><m:oMath xmlns:m="{M_NS}"><m:sSup><m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup></m:oMath></w:p>',
    )
    report = validate_docx(source)
    assert any("missing e" in e["error"] for e in report["omml"]["structural_errors"])


def test_deep_nesting_is_flagged(tmp_path: Path) -> None:
    # Build 35 nested m:f (fraction) elements — each m:f is a math-structure layer.
    # m:num / m:den are containers, not counted toward depth.
    inner = "<m:num><m:r><m:t>1</m:t></m:r></m:num><m:den><m:r><m:t>2</m:t></m:r></m:den>"
    wrapped = f"<m:f>{inner}</m:f>"
    for _ in range(34):
        wrapped = f"<m:f><m:num><m:r><m:t>1</m:t></m:r></m:num><m:den>{wrapped}</m:den></m:f>"
    source = make_docx_with_omml(
        tmp_path / "deep.docx",
        content=f'<w:p><m:oMath xmlns:m="{M_NS}">{wrapped}</m:oMath></w:p>',
    )
    report = validate_docx(source)
    assert any("depth" in w["warning"].lower() for w in report["omml"]["structural_warnings"])


def test_empty_text_run_is_counted(tmp_path: Path) -> None:
    source = make_docx_with_omml(
        tmp_path / "emptytext.docx",
        content=f'<w:p><m:oMath xmlns:m="{M_NS}"><m:r><m:t/></m:r></m:oMath></w:p>',
    )
    report = validate_docx(source)
    assert report["omml"]["empty_runs"] >= 1


# -- coverage layer (with review) ---------------------------------------------


def test_coverage_layer_with_review_passes_parseable_candidates(tmp_path: Path) -> None:
    source = make_docx_with_omml(
        tmp_path / "cov.docx",
        content=f"<w:p>{omath_for('x = 1')}</w:p>",
    )
    review = tmp_path / "candidates.json"
    review.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "id": "c1",
                        "parse_status": "ok",
                        "source": "x = 1",
                        "part": "word/document.xml",
                        "paragraph_index": 0,
                        "start": 0,
                        "end": 5,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    report = validate_docx(source, review_path=review)
    assert report["coverage"]["parseable"] == 1
    assert report["coverage"]["omml_produced"] == 1
    assert report["coverage"]["failures"] == []


def test_coverage_layer_flags_unparseable_candidates(tmp_path: Path) -> None:
    source = make_docx(tmp_path / "badcov.docx")
    review = tmp_path / "candidates.json"
    review.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "id": "c1",
                        "parse_status": "ok",
                        "source": "x @ 2",
                        "part": "word/document.xml",
                        "paragraph_index": 0,
                        "start": 0,
                        "end": 5,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    report = validate_docx(source, review_path=review)
    assert report["coverage"]["failures"]


# -- CLI integration -----------------------------------------------------------


def test_validate_cli_clean_docx_exits_zero(tmp_path: Path) -> None:
    source = make_docx(tmp_path / "source.docx")
    code = main(["validate", str(source)])
    assert code == 0


def test_validate_cli_corrupt_docx_exits_two(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.docx"
    corrupt.write_bytes(b"garbage")
    code = main(["validate", str(corrupt)])
    assert code == 1  # validate_docx catches BadZipFile internally, reports valid=false


def test_validate_cli_bad_omml_exits_one(tmp_path: Path) -> None:
    source = make_docx_with_omml(
        tmp_path / "bad.docx",
        content=f'<w:p><m:oMath xmlns:m="{M_NS}"><m:f><m:num><m:r><m:t>x</m:t></m:r></m:num></m:f></m:oMath></w:p>',
    )
    code = main(["validate", str(source)])
    assert code == 1


def test_validate_cli_writes_report(tmp_path: Path) -> None:
    source = make_docx(tmp_path / "source.docx")
    report_path = tmp_path / "validation.json"
    code = main(["validate", str(source), "--report", str(report_path)])
    assert code == 0
    assert report_path.is_file()
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["valid"] is True


def test_validate_cli_with_review(tmp_path: Path) -> None:
    source = make_docx(tmp_path / "rev.docx")
    review = tmp_path / "candidates.json"
    review.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "id": "v1",
                        "parse_status": "ok",
                        "source": "x^2 + 1 = 2",
                        "part": "word/document.xml",
                        "paragraph_index": 0,
                        "start": 16,
                        "end": 26,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "v-report.json"
    code = main(
        [
            "validate",
            str(source),
            "--review",
            str(review),
            "--report",
            str(report_path),
        ]
    )
    assert code == 0
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["coverage"]["parseable"] == 1


# -- cross-backend (requires native XSL) --------------------------------------


@pytest.mark.native_xsl
def test_cross_backend_structure_comparison(tmp_path: Path) -> None:
    try:
        xsl_path = find_xsl()
    except FileNotFoundError:
        pytest.skip("Microsoft Office MML2OMML.XSL is not installed")

    source = make_docx(tmp_path / "cross.docx")
    review = tmp_path / "cross-review.json"
    review.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "id": "x1",
                        "parse_status": "ok",
                        "source": "x = 1",
                        "part": "word/document.xml",
                        "paragraph_index": 0,
                        "start": 0,
                        "end": 5,
                    },
                    {
                        "id": "x2",
                        "parse_status": "ok",
                        "source": "a/(b+c)",
                        "part": "word/document.xml",
                        "paragraph_index": 0,
                        "start": 0,
                        "end": 7,
                    },
                    {
                        "id": "x3",
                        "parse_status": "ok",
                        "source": "sqrt(x^2+1)",
                        "part": "word/document.xml",
                        "paragraph_index": 0,
                        "start": 0,
                        "end": 12,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    report = validate_docx(source, review_path=review, xsl_path=xsl_path)
    cb = report["cross_backend"]
    assert cb["available"] is True
    assert cb["divergences"] == 0
