from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from lxml import etree

from mathfmt.cli import main
from mathfmt.core import M_NS, NS, W_NS, apply_docx, find_xsl, paragraph_text, scan_docx
from tests.helpers import make_docx, make_fake_xsl


def document_with_body(body: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{W_NS}" xmlns:m="{M_NS}"><w:body>{body}</w:body></w:document>"""


def test_scan_reports_supported_parts_and_skips(tmp_path: Path) -> None:
    source = make_docx(tmp_path / "source.docx")
    report_path = tmp_path / "candidates.json"
    report = scan_docx(source, report_path)

    assert report["summary"]["existing_equations"] == 1
    assert report["summary"]["drawing_paragraphs"] == 1
    assert report["summary"]["code_paragraphs"] == 1
    parts = {candidate["part"] for candidate in report["candidates"]}
    assert {"word/document.xml", "word/header1.xml", "word/footer1.xml"} <= parts
    assert all(candidate["parse_status"] == "ok" for candidate in report["candidates"])


def test_apply_creates_omml_without_overwriting_source(tmp_path: Path) -> None:
    source = make_docx(tmp_path / "source.docx")
    original = source.read_bytes()
    review = tmp_path / "review.json"
    result_path = tmp_path / "result.json"
    output = tmp_path / "output.docx"
    xsl = make_fake_xsl(tmp_path / "fake.xsl")

    scanned = scan_docx(source, review)
    result = apply_docx(source, review, output, result_path, xsl)

    assert source.read_bytes() == original
    assert output.is_file()
    # With confidence scoring, only "high" candidates are selected by default
    assert result["converted_count"] >= 1
    assert scanned["summary"]["candidates"] >= 1
    assert any(item["lines"] > 1 for item in result["converted"])
    with zipfile.ZipFile(output) as archive:
        root = etree.fromstring(archive.read("word/document.xml"))
    assert len(root.xpath(".//m:oMath", namespaces=NS)) >= 3
    assert root.xpath(".//w:br", namespaces=NS)
    assert json.loads(result_path.read_text(encoding="utf-8"))["converted_count"] > 0


def test_apply_writes_v3_conversion_report_schema(tmp_path: Path) -> None:
    source = make_docx(tmp_path / "source.docx")
    review = tmp_path / "review.json"
    result_path = tmp_path / "result.json"
    output = tmp_path / "output.docx"

    scan_docx(source, review)
    result = apply_docx(source, review, output, result_path, xsl_path=None)
    saved = json.loads(result_path.read_text(encoding="utf-8"))

    assert result["schema_version"] == 3
    assert saved["schema_version"] == 3
    assert saved["report_type"] == "conversion"
    assert saved["command"]["name"] == "apply"
    assert saved["inputs"]["docx"] == str(source.resolve())
    assert saved["inputs"]["review"] == str(review.resolve())
    assert saved["outputs"]["docx"] == str(output.resolve())
    assert saved["outputs"]["report"] == str(result_path.resolve())
    assert saved["options"]["backend"] == "python"
    assert saved["summary"]["selected"] >= saved["summary"]["converted"]
    assert saved["summary"]["converted"] == saved["converted_count"]
    assert saved["summary"]["skipped"] == saved["skipped_count"]
    assert saved["formulas"]
    assert {item["status"] for item in saved["formulas"]} == {"converted"}


def test_apply_dry_run_writes_report_without_docx_output(tmp_path: Path) -> None:
    source = make_docx(tmp_path / "source.docx")
    original = source.read_bytes()
    review = tmp_path / "review.json"
    result_path = tmp_path / "result.json"
    output = tmp_path / "output.docx"

    scan_docx(source, review)
    result = apply_docx(source, review, output, result_path, xsl_path=None, dry_run=True)
    saved = json.loads(result_path.read_text(encoding="utf-8"))

    assert source.read_bytes() == original
    assert not output.exists()
    assert result["converted_count"] > 0
    assert saved["options"]["dry_run"] is True
    assert saved["summary"]["dry_run"] is True
    assert saved["summary"]["output_written"] is False
    assert saved["summary"]["converted"] == saved["converted_count"]


def test_refuses_to_overwrite_input(tmp_path: Path) -> None:
    source = make_docx(tmp_path / "source.docx")
    review = tmp_path / "review.json"
    scan_docx(source, review)
    with pytest.raises(ValueError, match="overwrite"):
        apply_docx(source, review, source, tmp_path / "result.json", make_fake_xsl(tmp_path / "fake.xsl"))


def test_convert_command_uses_safe_defaults(tmp_path: Path) -> None:
    source = make_docx(tmp_path / "source.docx")
    xsl = make_fake_xsl(tmp_path / "fake.xsl")
    assert main(["convert", str(source), "--xsl", str(xsl)]) == 0
    assert (tmp_path / "source.mathfmt.docx").is_file()
    report_path = tmp_path / "source.mathfmt.report.json"
    assert report_path.is_file()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["schema_version"] == 3
    assert report["command"]["name"] == "convert"


def test_explicit_missing_xsl_is_reported(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="not found at"):
        find_xsl(tmp_path / "missing.xsl")


@pytest.mark.native_xsl
def test_native_xsl_when_available(tmp_path: Path) -> None:
    try:
        xsl = find_xsl()
    except FileNotFoundError:
        pytest.skip("Microsoft Office MML2OMML.XSL is not installed")
    source = make_docx(tmp_path / "source.docx")
    review = tmp_path / "review.json"
    output = tmp_path / "native.docx"
    scan_docx(source, review)
    result = apply_docx(source, review, output, tmp_path / "native.json", xsl)
    assert result["converted_count"] > 0
    with zipfile.ZipFile(output) as archive:
        root = etree.fromstring(archive.read("word/document.xml"))
    assert root.xpath(".//m:oMath", namespaces={"m": M_NS})


def test_scan_validates_input_and_corrupt_archives(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=".docx"):
        scan_docx(tmp_path / "notes.txt", tmp_path / "report.json")
    with pytest.raises(FileNotFoundError, match="not found"):
        scan_docx(tmp_path / "missing.docx", tmp_path / "report.json")
    corrupt = tmp_path / "corrupt.docx"
    corrupt.write_bytes(b"not a zip archive")
    with pytest.raises(zipfile.BadZipFile):
        scan_docx(corrupt, tmp_path / "report.json")


def test_scan_records_empty_pict_and_unparseable_formula(tmp_path: Path) -> None:
    document = document_with_body(
        """
        <w:p><w:r><w:t>   </w:t></w:r></w:p>
        <w:p><w:r><w:pict/></w:r><w:r><w:t>x = 1</w:t></w:r></w:p>
        <w:p><w:r><w:t>x = +</w:t></w:r></w:p>
        """
    )
    source = make_docx(tmp_path / "source.docx", document_xml=document)
    report = scan_docx(source, tmp_path / "report.json")
    assert report["summary"]["drawing_paragraphs"] == 1
    assert report["candidates"][0]["parse_status"] == "review"
    assert report["candidates"][0]["selected"] is False
    assert report["candidates"][0]["parse_error"]


def test_apply_preserves_mixed_text_across_runs(tmp_path: Path) -> None:
    document = document_with_body(
        """
        <w:p>
          <w:r><w:t xml:space="preserve">Before </w:t></w:r>
          <w:r><w:rPr><w:b/></w:rPr><w:t>x^2</w:t></w:r>
          <w:r><w:t xml:space="preserve"> = 4</w:t></w:r>
          <w:r><w:t xml:space="preserve"> after</w:t></w:r>
        </w:p>
        """
    )
    source = make_docx(tmp_path / "source.docx", document_xml=document)
    review = tmp_path / "review.json"
    review.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "id": "mixed",
                        "selected": True,
                        "part": "word/document.xml",
                        "paragraph_index": 0,
                        "start": 7,
                        "end": 14,
                        "source": "x^2 = 4",
                        "linear": "x^2 = 4",
                        "display": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "output.docx"
    result = apply_docx(
        source,
        review,
        output,
        tmp_path / "result.json",
        make_fake_xsl(tmp_path / "fake.xsl"),
    )
    assert result["converted_count"] == 1
    with zipfile.ZipFile(output) as archive:
        root = etree.fromstring(archive.read("word/document.xml"))
    paragraph = root.xpath(".//w:p", namespaces=NS)[0]
    assert paragraph_text(paragraph) == "Before  after"
    assert paragraph.xpath(".//m:oMath", namespaces=NS)


def test_apply_preserves_single_run_suffix_formatting(tmp_path: Path) -> None:
    document = document_with_body("<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Before x = 1 after</w:t></w:r></w:p>")
    source = make_docx(tmp_path / "source.docx", document_xml=document)
    review = tmp_path / "review.json"
    review.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "id": "styled",
                        "selected": True,
                        "part": "word/document.xml",
                        "paragraph_index": 0,
                        "start": 7,
                        "end": 12,
                        "source": "x = 1",
                        "display": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "output.docx"
    apply_docx(
        source,
        review,
        output,
        tmp_path / "result.json",
        make_fake_xsl(tmp_path / "fake.xsl"),
    )
    with zipfile.ZipFile(output) as archive:
        root = etree.fromstring(archive.read("word/document.xml"))
    suffix = root.xpath(".//w:r[w:t=' after']", namespaces=NS)
    assert suffix and suffix[0].xpath("boolean(./w:rPr/w:b)", namespaces=NS)


def test_apply_reports_stale_and_invalid_review_locations(tmp_path: Path) -> None:
    source = make_docx(tmp_path / "source.docx")
    review = tmp_path / "review.json"
    candidates = [
        {
            "id": "missing-part",
            "selected": True,
            "part": "word/missing.xml",
            "paragraph_index": 0,
            "start": 0,
            "end": 1,
            "source": "x",
        },
        {
            "id": "missing-paragraph",
            "selected": True,
            "part": "word/header1.xml",
            "paragraph_index": 99,
            "start": 0,
            "end": 1,
            "source": "x",
        },
        {
            "id": "stale",
            "selected": True,
            "part": "word/footer1.xml",
            "paragraph_index": 0,
            "start": 0,
            "end": 5,
            "source": "wrong",
        },
    ]
    review.write_text(json.dumps({"candidates": candidates}), encoding="utf-8")
    result = apply_docx(
        source,
        review,
        tmp_path / "output.docx",
        tmp_path / "result.json",
        make_fake_xsl(tmp_path / "fake.xsl"),
    )
    assert result["converted_count"] == 0
    assert result["skipped_count"] == 3
    errors = {item["id"]: item["error"] for item in result["skipped"]}
    assert "part not found" in errors["missing-part"]
    assert "index out of range" in errors["missing-paragraph"]
    assert "no longer matches" in errors["stale"]


def test_apply_rejects_invalid_extensions_and_nested_hyperlink(tmp_path: Path) -> None:
    source = make_docx(tmp_path / "source.docx")
    review = tmp_path / "review.json"
    review.write_text('{"candidates": []}', encoding="utf-8")
    xsl = make_fake_xsl(tmp_path / "fake.xsl")
    with pytest.raises(ValueError, match="must be .docx"):
        apply_docx(source, review, tmp_path / "output.txt", tmp_path / "result.json", xsl)

    nested_document = document_with_body("<w:p><w:hyperlink><w:r><w:t>x = 1</w:t></w:r></w:hyperlink></w:p>")
    nested = make_docx(tmp_path / "nested.docx", document_xml=nested_document)
    nested_review = tmp_path / "nested.json"
    nested_review.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "id": "nested",
                        "selected": True,
                        "part": "word/document.xml",
                        "paragraph_index": 0,
                        "start": 0,
                        "end": 5,
                        "source": "x = 1",
                        "display": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = apply_docx(
        nested,
        nested_review,
        tmp_path / "nested-output.docx",
        tmp_path / "nested-result.json",
        xsl,
    )
    assert result["skipped_count"] == 1
    assert "hyperlink" in result["skipped"][0]["error"]


def test_unselected_candidates_leave_document_unchanged(tmp_path: Path) -> None:
    source = make_docx(tmp_path / "source.docx")
    review = tmp_path / "review.json"
    scanned = scan_docx(source, review)
    for candidate in scanned["candidates"]:
        candidate["selected"] = False
    review.write_text(json.dumps(scanned), encoding="utf-8")
    result = apply_docx(
        source,
        review,
        tmp_path / "output.docx",
        tmp_path / "result.json",
        make_fake_xsl(tmp_path / "fake.xsl"),
    )
    assert result["converted_count"] == result["skipped_count"] == 0


def test_apply_with_python_backend_produces_omml(tmp_path: Path) -> None:
    source = make_docx(tmp_path / "source.docx")
    review = tmp_path / "review.json"
    scan_docx(source, review)
    output = tmp_path / "output.docx"
    result = apply_docx(
        source,
        review,
        output,
        tmp_path / "result.json",
        xsl_path=None,
    )
    assert result["converted_count"] > 0
    assert result["skipped_count"] == 0
    assert result["xsl"] is None
    with zipfile.ZipFile(output) as archive:
        root = etree.fromstring(archive.read("word/document.xml"))
    assert root.xpath(".//m:oMath", namespaces=NS)


def test_convert_without_xsl_flag_does_not_crash(tmp_path: Path) -> None:
    source = make_docx(tmp_path / "source.docx")
    code = main(["convert", str(source), "--output", str(tmp_path / "out.docx")])
    assert code in (0, 2)
    assert (tmp_path / "out.docx").is_file()
