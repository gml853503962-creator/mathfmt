from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from mathfmt import docxio
from mathfmt.core import scan_docx
from mathfmt.docxio import DocxSecurityError, inspect_docx, parse_xml_part
from mathfmt.validate import validate_docx
from tests.helpers import make_docx


def zip_info(
    name: str,
    *,
    file_size: int = 0,
    compress_size: int = 0,
    flag_bits: int = 0,
) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name)
    info.file_size = file_size
    info.compress_size = compress_size
    info.flag_bits = flag_bits
    return info


def test_parse_xml_part_rejects_doctype_without_resolving_entity(tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("must not be expanded", encoding="utf-8")
    raw = (
        f'<!DOCTYPE w:document [<!ENTITY ext SYSTEM "{secret.resolve().as_uri()}">]>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>&ext;</w:t></w:r></w:p></w:body></w:document>"
    ).encode()

    with pytest.raises(DocxSecurityError, match="DOCTYPE"):
        parse_xml_part(raw, part_name="word/document.xml")


def test_scan_rejects_docx_with_doctype(tmp_path: Path) -> None:
    source = make_docx(
        tmp_path / "doctype.docx",
        document_xml=(
            '<!DOCTYPE w:document [<!ENTITY value "x = 1">]>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>&value;</w:t></w:r></w:p></w:body></w:document>"
        ),
    )

    with pytest.raises(DocxSecurityError, match="DOCTYPE"):
        scan_docx(source, tmp_path / "report.json")


def test_inspect_docx_rejects_duplicate_members(tmp_path: Path) -> None:
    source = tmp_path / "duplicate.docx"
    with pytest.warns(UserWarning, match="Duplicate name"):
        with zipfile.ZipFile(source, "w") as archive:
            archive.writestr("word/document.xml", b"first")
            archive.writestr("word/document.xml", b"second")

    with pytest.raises(DocxSecurityError, match="duplicate"):
        inspect_docx(source)


def test_inspect_docx_enforces_total_uncompressed_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = make_docx(tmp_path / "bounded.docx")
    monkeypatch.setattr(docxio, "MAX_DOCX_TOTAL_UNCOMPRESSED_BYTES", 32)

    with pytest.raises(DocxSecurityError, match="expands"):
        inspect_docx(source)


def test_package_member_validation_enforces_entry_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(docxio, "MAX_DOCX_ENTRY_COUNT", 1)

    with pytest.raises(DocxSecurityError, match="ZIP entries"):
        docxio._validate_package_members([zip_info("one"), zip_info("two")])


def test_package_member_validation_rejects_encryption_and_oversized_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(DocxSecurityError, match="encrypted"):
        docxio._validate_package_members([zip_info("secret", flag_bits=0x1)])

    monkeypatch.setattr(docxio, "MAX_DOCX_MEMBER_BYTES", 8)
    with pytest.raises(DocxSecurityError, match="per-entry limit"):
        docxio._validate_package_members([zip_info("large", file_size=9, compress_size=9)])


def test_package_member_validation_rejects_extreme_compression_ratio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(docxio, "COMPRESSION_RATIO_MIN_BYTES", 10)
    monkeypatch.setattr(docxio, "MAX_DOCX_COMPRESSION_RATIO", 2.0)

    with pytest.raises(DocxSecurityError, match="compression ratio"):
        docxio._validate_package_members([zip_info("bomb", file_size=100, compress_size=10)])


def test_validate_reports_security_limit_as_invalid_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = make_docx(tmp_path / "bounded.docx")
    monkeypatch.setattr(docxio, "MAX_DOCX_TOTAL_UNCOMPRESSED_BYTES", 32)

    report = validate_docx(source)

    assert report["valid"] is False
    assert report["package"]["valid_zip"] is False
    assert "expands" in report["package"]["error"]
