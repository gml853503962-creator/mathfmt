"""Command-line interface for MathFmt."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import tempfile
import zipfile
from collections.abc import Sequence
from pathlib import Path

from lxml import etree

from . import __version__
from .core import apply_docx, find_xsl, scan_docx
from .validate import validate_docx


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
        "backend": "python",
        "ready": True,
    }
    try:
        data["xsl"] = str(find_xsl(explicit_xsl).resolve())
        data["backend"] = "office-xsl"
    except FileNotFoundError:
        pass
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
    apply.add_argument("--xsl", type=Path, help="path to MML2OMML.XSL (optional; built-in Python backend used otherwise)")

    convert = subparsers.add_parser("convert", help="conservatively convert detected formulas in one step")
    convert.add_argument("input", type=Path)
    convert.add_argument("--output", "--out", dest="output", type=Path)
    convert.add_argument("--report", type=Path)
    convert.add_argument("--xsl", type=Path)
    convert.add_argument("--confidence", choices=["high", "medium", "all"], default="high",
                         help="minimum confidence level to convert (default: high)")

    doctor = subparsers.add_parser("doctor", help="check the local MathFmt environment")
    doctor.add_argument("--xsl", type=Path)
    doctor.add_argument("--json", action="store_true", dest="as_json")

    validate = subparsers.add_parser("validate", help="validate DOCX structure and OMML equations offline")
    validate.add_argument("input", type=Path)
    validate.add_argument("--report", type=Path)
    validate.add_argument("--review", type=Path, help="path to candidates.json for formula coverage check")
    validate.add_argument("--xsl", type=Path, help="path to MML2OMML.XSL for cross-backend comparison")
    return parser


def run_convert(args: argparse.Namespace) -> int:
    output = args.output or default_output(args.input)
    report_path = args.report or default_result_report(output)
    if args.xsl is not None:
        xsl = find_xsl(args.xsl)
    else:
        try:
            xsl = find_xsl()
        except FileNotFoundError:
            xsl = None
    with tempfile.TemporaryDirectory(prefix="mathfmt-") as temp_dir:
        review_path = Path(temp_dir) / "candidates.json"
        scan = scan_docx(args.input, review_path)
        if args.confidence != "all":
            review = json.loads(review_path.read_text(encoding="utf-8"))
            confidence_order = {"high": 0, "medium": 1, "low": 2}
            min_level = confidence_order[args.confidence]
            for c in review.get("candidates", []):
                c_level = confidence_order.get(c.get("confidence"), 2)
                if c_level > min_level:
                    c["selected"] = False
            review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
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
            if args.xsl is not None:
                xsl_path = find_xsl(args.xsl)
            else:
                try:
                    xsl_path = find_xsl()
                except FileNotFoundError:
                    xsl_path = None
            result = apply_docx(
                args.input,
                args.review,
                args.output,
                args.report,
                xsl_path,
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
                print(f"OMML backend: {data['backend']}")
                if data["xsl"]:
                    print(f"MML2OMML.XSL: {data['xsl']}")
                print(f"Ready: {'yes' if data['ready'] else 'no'}")
            return 0 if data["ready"] else 1
        if args.command == "validate":
            if args.xsl is not None:
                xsl_path = find_xsl(args.xsl)
            else:
                try:
                    xsl_path = find_xsl()
                except FileNotFoundError:
                    xsl_path = None
            report = validate_docx(
                args.input,
                review_path=args.review,
                xsl_path=xsl_path,
            )
            if args.report:
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"Report: {args.report}")
            if report["valid"]:
                print("Validation: PASS")
                eq_count = report.get("omml", {}).get("equation_count", 0) if isinstance(report.get("omml"), dict) else 0
                print(f"Equations: {eq_count}")
                return 0
            else:
                print("Validation: FAIL")
                oml = report.get("omml", {})
                if isinstance(oml, dict):
                    errors = oml.get("structural_errors", [])
                    if errors:
                        print(f"OMML errors: {len(errors)}")
                return 1
    except (FileNotFoundError, ValueError, json.JSONDecodeError, etree.XMLSyntaxError) as exc:
        print(f"mathfmt: error: {exc}", file=sys.stderr)
        return 1
    except zipfile.BadZipFile as exc:
        print(f"mathfmt: error: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
