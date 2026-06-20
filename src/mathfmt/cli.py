"""Command-line interface for MathFmt."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from lxml import etree

from . import __version__
from .core import apply_docx, find_xsl, scan_docx


def default_output(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}.mathfmt.docx")


def default_result_report(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}.report.json")


def doctor_data(explicit_xsl: Path | None = None) -> dict[str, object]:
    data: dict[str, object] = {
        "mathfmt": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "windows": os.name == "nt",
        "lxml": etree.LXML_VERSION,
        "xsl": None,
        "ready": False,
    }
    try:
        data["xsl"] = str(find_xsl(explicit_xsl).resolve())
        data["ready"] = True
    except FileNotFoundError as exc:
        data["error"] = str(exc)
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mathfmt",
        description="Typeset plain-text DOCX formulas as native Word equations.",
    )
    parser.add_argument("--version", action="version", version=f"MathFmt {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="create a reviewable formula candidate report")
    scan.add_argument("input", type=Path)
    scan.add_argument("--report", type=Path, required=True)

    apply = subparsers.add_parser("apply", help="apply a reviewed candidate report")
    apply.add_argument("input", type=Path)
    apply.add_argument("--review", type=Path, required=True)
    apply.add_argument("--output", "--out", dest="output", type=Path, required=True)
    apply.add_argument("--report", type=Path, required=True)
    apply.add_argument("--xsl", type=Path)

    convert = subparsers.add_parser("convert", help="conservatively convert detected formulas in one step")
    convert.add_argument("input", type=Path)
    convert.add_argument("--output", "--out", dest="output", type=Path)
    convert.add_argument("--report", type=Path)
    convert.add_argument("--xsl", type=Path)

    doctor = subparsers.add_parser("doctor", help="check the local MathFmt environment")
    doctor.add_argument("--xsl", type=Path)
    doctor.add_argument("--json", action="store_true", dest="as_json")
    return parser


def run_convert(args: argparse.Namespace) -> int:
    output = args.output or default_output(args.input)
    report_path = args.report or default_result_report(output)
    xsl = find_xsl(args.xsl)
    with tempfile.TemporaryDirectory(prefix="mathfmt-") as temp_dir:
        review_path = Path(temp_dir) / "candidates.json"
        scan = scan_docx(args.input, review_path)
        result = apply_docx(args.input, review_path, output, report_path, xsl)
    print(f"Candidates: {scan['summary']['candidates']}")
    print(f"Converted: {result['converted_count']}")
    print(f"Skipped: {result['skipped_count']}")
    print(f"Output: {output}")
    print(f"Report: {report_path}")
    return 0 if result["skipped_count"] == 0 else 2


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "scan":
            report = scan_docx(args.input, args.report)
            print(f"Candidates: {report['summary']['candidates']}")
            print(f"Report: {args.report}")
            return 0
        if args.command == "apply":
            result = apply_docx(
                args.input,
                args.review,
                args.output,
                args.report,
                find_xsl(args.xsl),
            )
            print(f"Converted: {result['converted_count']}")
            print(f"Skipped: {result['skipped_count']}")
            print(f"Output: {args.output}")
            print(f"Report: {args.report}")
            return 0 if result["skipped_count"] == 0 else 2
        if args.command == "convert":
            return run_convert(args)
        if args.command == "doctor":
            data = doctor_data(args.xsl)
            if args.as_json:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                print(f"MathFmt: {data['mathfmt']}")
                print(f"Python: {data['python']}")
                print(f"Platform: {data['platform']}")
                print(f"MML2OMML.XSL: {data['xsl'] or 'not found'}")
                print(f"Ready: {'yes' if data['ready'] else 'no'}")
                if data.get("error"):
                    print(f"Hint: {data['error']}")
            return 0 if data["ready"] else 1
    except (FileNotFoundError, ValueError, json.JSONDecodeError, etree.XMLSyntaxError) as exc:
        print(f"mathfmt: error: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
