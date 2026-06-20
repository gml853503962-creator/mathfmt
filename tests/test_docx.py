from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from lxml import etree

from mathfmt.cli import main
from mathfmt.core import M_NS, NS, apply_docx, find_xsl, scan_docx
from tests.helpers import make_docx, make_fake_xsl


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
    assert result["converted_count"] == scanned["summary"]["candidates"]
    assert result["skipped_count"] == 0
    assert any(item["lines"] > 1 for item in result["converted"])
    with zipfile.ZipFile(output) as archive:
        root = etree.fromstring(archive.read("word/document.xml"))
    assert len(root.xpath(".//m:oMath", namespaces=NS)) >= 3
    assert root.xpath(".//w:br", namespaces=NS)
    assert json.loads(result_path.read_text(encoding="utf-8"))["converted_count"] > 0


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
    assert (tmp_path / "source.mathfmt.report.json").is_file()


def test_explicit_missing_xsl_is_reported(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="not found at"):
        find_xsl(tmp_path / "missing.xsl")


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
