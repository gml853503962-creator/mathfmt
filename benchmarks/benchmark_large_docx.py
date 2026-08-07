"""Generate and benchmark a 100+ page MathFmt DOCX workflow."""

from __future__ import annotations

import argparse
import json
import tempfile
import time
import tracemalloc
import zipfile
from pathlib import Path

from mathfmt import __version__, apply_docx, scan_docx, validate_docx

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

DOCUMENT_START = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
 <w:body>"""

DOCUMENT_END = """
  <w:sectPr>
   <w:pgSz w:w="11906" w:h="16838"/>
   <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>
  </w:sectPr>
 </w:body>
</w:document>"""


def make_large_docx(path: Path, *, pages: int, formulas_per_page: int) -> Path:
    """Create a deterministic page-broken DOCX with explicit formulas."""
    if pages < 1 or formulas_per_page < 1:
        raise ValueError("pages and formulas_per_page must be positive")
    paragraphs: list[str] = []
    for page in range(1, pages + 1):
        paragraphs.append(f"<w:p><w:r><w:t>MathFmt benchmark page {page}</w:t></w:r></w:p>")
        paragraphs.extend(
            "<w:p><w:r><w:t>Formula: $x^2 + y^2 = r^2$.</w:t></w:r></w:p>" for _ in range(formulas_per_page)
        )
        if page != pages:
            paragraphs.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
    document = DOCUMENT_START + "\n".join(paragraphs) + DOCUMENT_END
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("_rels/.rels", ROOT_RELS)
        archive.writestr("word/document.xml", document)
    return path


def run_benchmark(*, pages: int = 100, formulas_per_page: int = 8) -> dict[str, object]:
    """Run scan, strict conversion, and validation; return measured evidence."""
    expected = pages * formulas_per_page
    with tempfile.TemporaryDirectory(prefix="mathfmt-benchmark-") as temporary:
        root = Path(temporary)
        source = make_large_docx(
            root / "large.docx",
            pages=pages,
            formulas_per_page=formulas_per_page,
        )
        review = root / "review.json"
        output = root / "output.docx"
        result_path = root / "result.json"

        tracemalloc.start()
        started = time.perf_counter()
        scan = scan_docx(source, review)
        scanned_at = time.perf_counter()
        result = apply_docx(source, review, output, result_path, strict=True)
        applied_at = time.perf_counter()
        validation = validate_docx(output, review_path=review, compatibility="wps")
        finished = time.perf_counter()
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        candidates = int(scan["summary"]["candidates"])
        converted = int(result["summary"]["converted"])
        output_written = bool(result["summary"]["output_written"])
        if candidates != expected:
            raise RuntimeError(f"Expected {expected} candidates, found {candidates}")
        if converted != expected or not output_written:
            raise RuntimeError(f"Expected {expected} converted formulas and a written output")
        if not validation["valid"]:
            raise RuntimeError("Large-document validation failed")

        return {
            "mathfmt": __version__,
            "pages": pages,
            "formulas_per_page": formulas_per_page,
            "candidates": candidates,
            "converted": converted,
            "equations": int(validation["omml"]["equation_count"]),
            "valid": True,
            "wps_compatible": bool(validation["compatibility"]["compatible"]),
            "seconds": {
                "scan": round(scanned_at - started, 6),
                "apply": round(applied_at - scanned_at, 6),
                "validate": round(finished - applied_at, 6),
                "total": round(finished - started, 6),
            },
            "peak_memory_mb": round(peak_bytes / (1024 * 1024), 3),
            "input_bytes": source.stat().st_size,
            "output_bytes": output.stat().st_size,
        }


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", type=_positive_int, default=100)
    parser.add_argument("--formulas-per-page", type=_positive_int, default=8)
    parser.add_argument("--max-scan-seconds", type=float, default=5.0)
    parser.add_argument("--max-apply-seconds", type=float, default=5.0)
    parser.add_argument("--max-validate-seconds", type=float, default=8.0)
    parser.add_argument("--max-peak-memory-mb", type=float, default=256.0)
    parser.add_argument("--json", type=Path, dest="json_path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_benchmark(pages=args.pages, formulas_per_page=args.formulas_per_page)
    failures: list[str] = []
    seconds = result["seconds"]
    assert isinstance(seconds, dict)
    for phase, limit in (
        ("scan", args.max_scan_seconds),
        ("apply", args.max_apply_seconds),
        ("validate", args.max_validate_seconds),
    ):
        elapsed = float(seconds[phase])
        if elapsed > limit:
            failures.append(f"{phase} took {elapsed:.3f}s (limit {limit:.3f}s)")
    peak = float(result["peak_memory_mb"])
    if peak > args.max_peak_memory_mb:
        failures.append(f"peak memory was {peak:.3f} MiB (limit {args.max_peak_memory_mb:.3f} MiB)")

    result["limits"] = {
        "scan_seconds": args.max_scan_seconds,
        "apply_seconds": args.max_apply_seconds,
        "validate_seconds": args.max_validate_seconds,
        "peak_memory_mb": args.max_peak_memory_mb,
    }
    result["passed"] = not failures
    result["failures"] = failures
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.json_path is not None:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(rendered + "\n", encoding="utf-8")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
