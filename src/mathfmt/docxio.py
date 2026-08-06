"""Bounded and defensive DOCX package I/O."""

from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path
from typing import Final

from lxml import etree

MAX_DOCX_ENTRY_COUNT: Final = 10_000
MAX_DOCX_MEMBER_BYTES: Final = 128 * 1024 * 1024
MAX_DOCX_TOTAL_UNCOMPRESSED_BYTES: Final = 512 * 1024 * 1024
MAX_DOCX_COMPRESSION_RATIO: Final = 1_000.0
COMPRESSION_RATIO_MIN_BYTES: Final = 1024 * 1024


class DocxSecurityError(ValueError):
    """Raised when a DOCX package exceeds safe processing limits."""


def parse_xml_part(raw: bytes, *, part_name: str = "XML part") -> etree._Element:
    """Parse an OOXML part without DTD loading, entity expansion, or network access."""
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        huge_tree=False,
        recover=False,
    )
    root = etree.fromstring(raw, parser=parser)
    if root.getroottree().docinfo.doctype:
        raise DocxSecurityError(f"{part_name}: DOCTYPE declarations are not allowed")
    return root


def _validate_package_members(infos: list[zipfile.ZipInfo]) -> None:
    if len(infos) > MAX_DOCX_ENTRY_COUNT:
        raise DocxSecurityError(f"DOCX contains {len(infos)} ZIP entries; limit is {MAX_DOCX_ENTRY_COUNT}")

    seen: set[str] = set()
    total_size = 0
    for info in infos:
        if info.filename in seen:
            raise DocxSecurityError(f"DOCX contains a duplicate ZIP entry: {info.filename}")
        seen.add(info.filename)

        if info.flag_bits & 0x1:
            raise DocxSecurityError(f"DOCX contains an encrypted ZIP entry: {info.filename}")
        if info.file_size > MAX_DOCX_MEMBER_BYTES:
            raise DocxSecurityError(
                f"DOCX entry {info.filename!r} expands to {info.file_size} bytes; "
                f"per-entry limit is {MAX_DOCX_MEMBER_BYTES}"
            )

        total_size += info.file_size
        if total_size > MAX_DOCX_TOTAL_UNCOMPRESSED_BYTES:
            raise DocxSecurityError(f"DOCX expands to more than {MAX_DOCX_TOTAL_UNCOMPRESSED_BYTES} bytes")

        if info.file_size >= COMPRESSION_RATIO_MIN_BYTES:
            ratio = info.file_size / max(1, info.compress_size)
            if ratio > MAX_DOCX_COMPRESSION_RATIO:
                raise DocxSecurityError(
                    f"DOCX entry {info.filename!r} has suspicious compression ratio {ratio:.1f}:1"
                )


def inspect_docx(input_path: Path) -> tuple[list[zipfile.ZipInfo], dict[str, bytes]]:
    """Read a DOCX after validating its central-directory resource bounds."""
    with zipfile.ZipFile(input_path, "r") as archive:
        infos = archive.infolist()
        _validate_package_members(infos)
        data = {info.filename: archive.read(info) for info in infos}
    return infos, data


def write_docx(
    output_path: Path,
    infos: list[zipfile.ZipInfo],
    parts: dict[str, bytes],
) -> None:
    """Atomically write a DOCX package while preserving member metadata and order."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.NamedTemporaryFile(
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        dir=output_path.parent,
        delete=False,
    )
    temporary_path = Path(temporary.name)
    temporary.close()
    try:
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for info in infos:
                archive.writestr(info, parts[info.filename])
        os.replace(temporary_path, output_path)
    finally:
        temporary_path.unlink(missing_ok=True)
