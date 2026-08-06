"""Validate DOCX structural integrity and OMML equation correctness."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from lxml import etree

from .aliases import AliasProfile, alias_profile_metadata, validate_review_alias_profile
from .core import (
    M_NS,
    NS,
    TARGET_PART_RE,
    FormulaError,
    _error_details,
    _mathml_to_omml_xsl,
    formula_to_mathml,
    paragraph_text,
    split_multiline_formula,
)
from .docxio import DocxSecurityError, inspect_docx, parse_xml_part
from .omml import mathml_to_omml_py

MAX_NESTING_DEPTH = 32

# Math-structure element local-names — only these count toward nesting depth.
_MATH_STRUCTURE = frozenset(
    {
        "f",
        "rad",
        "sSup",
        "sSub",
        "sSubSup",
        "groupChr",
        "limLow",
        "limUpp",
        "nary",
        "eqArr",
        "box",
        "borderBox",
    }
)

F_NS_MAP = {"m": M_NS}


def _validate_package(
    input_path: Path,
    parts: dict[str, bytes],
) -> dict[str, object]:
    result: dict[str, object] = {"valid_zip": True, "missing_parts": [], "xml_errors": [], "paragraphs": 0}

    required = {"word/document.xml", "[Content_Types].xml"}
    missing = required - set(parts.keys())
    result["missing_parts"] = sorted(missing)

    paragraph_count = 0
    for name, raw in parts.items():
        if not TARGET_PART_RE.match(name) and name != "word/document.xml":
            continue
        try:
            root = parse_xml_part(raw, part_name=name)
        except (etree.XMLSyntaxError, DocxSecurityError) as exc:
            result["xml_errors"].append({"part": name, "error": str(exc)})
            continue
        if name == "word/document.xml":
            paragraphs = root.xpath(".//w:p", namespaces=NS)
            paragraph_count = len(paragraphs)
    result["paragraphs"] = paragraph_count
    return result


def _nesting_depth(
    elem: etree._Element,
    depth: int = 0,
) -> int:
    """Return maximum math-structure nesting depth (ignores container/run wrappers)."""
    local = etree.QName(elem).localname
    structural = local in _MATH_STRUCTURE
    current = depth + 1 if structural else depth
    if not len(elem):
        return current
    return max(_nesting_depth(child, current) for child in elem)


def _validate_omml_structure(
    parts: dict[str, bytes],
) -> dict[str, object]:
    result: dict[str, object] = {
        "equation_count": 0,
        "display_count": 0,
        "structural_warnings": [],
        "structural_errors": [],
        "empty_runs": 0,
        "nesting_depth": 0,
    }

    for name, raw in parts.items():
        if not TARGET_PART_RE.match(name) and name != "word/document.xml":
            continue
        try:
            root = parse_xml_part(raw, part_name=name)
        except (etree.XMLSyntaxError, DocxSecurityError):
            continue

        equations = root.xpath(".//m:oMath", namespaces=NS)
        result["equation_count"] += len(equations)
        result["display_count"] += len(root.xpath(".//m:oMathPara", namespaces=NS))

        for omath in equations:
            # Empty check
            if not len(omath):
                result["structural_errors"].append({"part": name, "error": "Empty m:oMath element"})
                continue

            # Nesting depth
            depth = _nesting_depth(omath)
            if depth > result["nesting_depth"]:
                result["nesting_depth"] = depth
            if depth > MAX_NESTING_DEPTH:
                result["structural_warnings"].append(
                    {"part": name, "warning": f"OMML nesting depth {depth} exceeds limit {MAX_NESTING_DEPTH}"}
                )

            # Empty text runs
            for mr in omath.xpath(".//m:r", namespaces=NS):
                text = "".join(t.text or "" for t in mr.xpath(".//m:t", namespaces=NS))
                if not text.strip():
                    result["empty_runs"] += 1

            # Fraction structural check
            for mf in omath.xpath(".//m:f", namespaces=NS):
                has_num = mf.xpath("boolean(./m:num)", namespaces=NS)
                has_den = mf.xpath("boolean(./m:den)", namespaces=NS)
                if not (has_num and has_den):
                    result["structural_errors"].append({"part": name, "error": "m:f missing num or den"})

            # Radical structural check
            for mrad in omath.xpath(".//m:rad", namespaces=NS):
                if not mrad.xpath("boolean(./m:e)", namespaces=NS):
                    result["structural_errors"].append({"part": name, "error": "m:rad missing e"})

            # Script structural checks
            for tag, roles in [("m:sSup", ["e", "sup"]), ("m:sSub", ["e", "sub"])]:
                for script in omath.xpath(f".//{tag}", namespaces=NS):
                    for role in roles:
                        if not script.xpath(f"boolean(./m:{role})", namespaces=NS):
                            result["structural_errors"].append(
                                {"part": name, "error": f"{tag} missing {role}"}
                            )

    return result


def _validate_coverage(
    parts: dict[str, bytes],
    review: dict[str, object],
    alias_profile: AliasProfile | None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "candidates_total": 0,
        "parseable": 0,
        "omml_produced": 0,
        "stale_source": 0,
        "failures": [],
    }
    candidates = review.get("candidates", [])
    if not isinstance(candidates, list):
        return result

    ok_candidates = [c for c in candidates if c.get("parse_status") == "ok"]
    result["candidates_total"] = len(ok_candidates)

    for candidate in ok_candidates:
        source = str(candidate.get("source", ""))
        linear = str(candidate.get("linear", source))
        part_name = str(candidate.get("part", ""))
        raw = parts.get(part_name)

        # Check source matches DOCX
        if raw is not None:
            try:
                root = parse_xml_part(raw, part_name=part_name)
                paragraphs = root.xpath(".//w:p", namespaces=NS)
                idx = int(candidate.get("paragraph_index", -1))
                if 0 <= idx < len(paragraphs):
                    text = paragraph_text(paragraphs[idx])
                    start = int(candidate.get("start", 0))
                    end = int(candidate.get("end", 0))
                    if text[start:end] != source:
                        result["stale_source"] += 1
            except (etree.XMLSyntaxError, ValueError, IndexError):
                pass

        # Check parseable
        try:
            mathml_lines = [
                formula_to_mathml(
                    line,
                    aliases=alias_profile.aliases if alias_profile is not None else None,
                )
                for line in split_multiline_formula(linear)
            ]
            result["parseable"] += 1
        except FormulaError as exc:
            result["failures"].append(
                {"source": source, "linear": linear, "error": str(exc), "error_details": _error_details(exc)}
            )
            continue

        # Check OMML producible
        try:
            omaths = [mathml_to_omml_py(mathml) for mathml in mathml_lines]
            if all(omath is not None for omath in omaths):
                result["omml_produced"] += 1
        except Exception as exc:
            result["failures"].append({"source": source, "error": f"OMML: {exc}"})

    return result


def _tag_signature(omath: etree._Element) -> int:
    count = 0
    for _ in omath.iter():
        count += 1
    return count


def _validate_cross_backend(
    candidates: list[dict[str, object]],
    xsl_path: Path,
    alias_profile: AliasProfile | None,
) -> dict[str, object] | None:
    try:
        transform = etree.XSLT(etree.parse(str(xsl_path)))
    except Exception as exc:
        return {"available": False, "error": str(exc)}

    ok = [c for c in candidates if c.get("parse_status") == "ok"]
    divergences: list[dict[str, object]] = []

    for candidate in ok[:20]:  # sample cap
        source = str(candidate.get("source", ""))
        linear = str(candidate.get("linear", source))
        try:
            mathml_lines = [
                formula_to_mathml(
                    line,
                    aliases=alias_profile.aliases if alias_profile is not None else None,
                )
                for line in split_multiline_formula(linear)
            ]
        except FormulaError:
            continue

        try:
            xsl_omaths = [_mathml_to_omml_xsl(mathml, transform) for mathml in mathml_lines]
            py_omaths = [mathml_to_omml_py(mathml) for mathml in mathml_lines]
        except Exception as exc:
            divergences.append({"source": source, "linear": linear, "error": str(exc)})
            continue

        xsl_count = sum(_tag_signature(omath) for omath in xsl_omaths)
        py_count = sum(_tag_signature(omath) for omath in py_omaths)
        if abs(xsl_count - py_count) > 10:
            divergences.append(
                {
                    "source": source,
                    "xsl_elements": xsl_count,
                    "py_elements": py_count,
                }
            )

    return {
        "available": True,
        "sampled": len(ok[:20]),
        "divergences": len(divergences),
        "details": divergences if divergences else None,
    }


def validate_docx(
    input_path: Path,
    *,
    review_path: Path | None = None,
    xsl_path: Path | None = None,
    alias_profile: AliasProfile | None = None,
) -> dict[str, object]:
    if input_path.suffix.lower() != ".docx":
        raise ValueError("Input must be a .docx file")
    if not input_path.is_file():
        raise FileNotFoundError(f"Input DOCX was not found: {input_path}")

    from ._version import __version__

    backend = "python" if xsl_path is None else "office-xsl"
    report: dict[str, object] = {
        "schema_version": 3,
        "report_type": "validation",
        "mathfmt": __version__,
        "command": {"name": "validate"},
        "inputs": {
            "docx": str(input_path.resolve()),
            "review": str(review_path.resolve()) if review_path is not None else None,
            "aliases": str(alias_profile.path) if alias_profile is not None else None,
        },
        "outputs": {},
        "options": {
            "backend": backend,
            "xsl": str(xsl_path.resolve()) if xsl_path is not None else None,
            "alias_profile": alias_profile_metadata(alias_profile),
        },
        "summary": {
            "valid": True,
            "errors": 0,
            "warnings": 0,
            "equations": 0,
        },
        "input": str(input_path.resolve()),
        "backend": backend,
        "valid": True,
        "package": {},
        "omml": {},
    }

    # Layer 1: package
    try:
        _, parts = inspect_docx(input_path)
    except (zipfile.BadZipFile, DocxSecurityError) as exc:
        report["valid"] = False
        report["package"] = {"valid_zip": False, "error": str(exc)}
        report["summary"] = {
            "valid": False,
            "errors": 1,
            "warnings": 0,
            "equations": 0,
        }
        return report

    report["package"] = _validate_package(input_path, parts)

    # Layer 2: OMML
    report["omml"] = _validate_omml_structure(parts)

    # Layer 3: coverage (requires review)
    if review_path is not None:
        review = json.loads(review_path.read_text(encoding="utf-8"))
        validate_review_alias_profile(review, alias_profile)
        report["coverage"] = _validate_coverage(parts, review, alias_profile)

        # Layer 4: cross-backend (requires candidates + XSL)
        if xsl_path is not None:
            report["cross_backend"] = _validate_cross_backend(
                review.get("candidates", []),
                xsl_path,
                alias_profile,
            )

    # Determine overall validity
    has_issues = False
    pkg = report["package"]
    if isinstance(pkg, dict):
        if pkg.get("missing_parts") or pkg.get("xml_errors"):
            has_issues = True
    oml = report["omml"]
    if isinstance(oml, dict):
        if oml.get("structural_errors"):
            has_issues = True
    cov = report.get("coverage")
    if isinstance(cov, dict):
        if cov.get("failures"):
            has_issues = True
    report["valid"] = not has_issues
    structural_errors = oml.get("structural_errors", []) if isinstance(oml, dict) else []
    structural_warnings = oml.get("structural_warnings", []) if isinstance(oml, dict) else []
    coverage_failures = cov.get("failures", []) if isinstance(cov, dict) else []
    equation_count = oml.get("equation_count", 0) if isinstance(oml, dict) else 0
    report["summary"] = {
        "valid": report["valid"],
        "errors": len(structural_errors) + len(coverage_failures),
        "warnings": len(structural_warnings),
        "equations": equation_count,
    }

    return report
