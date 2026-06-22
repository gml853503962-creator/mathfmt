"""Validate DOCX structural integrity and OMML equation correctness."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from lxml import etree

from .core import (
    M_NS,
    NS,
    TARGET_PART_RE,
    FormulaError,
    _mathml_to_omml_xsl,
    formula_to_mathml,
    inspect_docx,
    paragraph_text,
)
from .omml import mathml_to_omml_py

MAX_NESTING_DEPTH = 32

# Math-structure element local-names — only these count toward nesting depth.
_MATH_STRUCTURE = frozenset(
    {"f", "rad", "sSup", "sSub", "sSubSup", "groupChr", "lim", "nary", "eqArr", "box", "borderBox"}
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
            root = etree.fromstring(raw)
        except etree.XMLSyntaxError as exc:
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
            root = etree.fromstring(raw)
        except etree.XMLSyntaxError:
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
        part_name = str(candidate.get("part", ""))
        raw = parts.get(part_name)

        # Check source matches DOCX
        if raw is not None:
            try:
                root = etree.fromstring(raw)
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
            mathml = formula_to_mathml(source)
            result["parseable"] += 1
        except FormulaError as exc:
            result["failures"].append({"source": source, "error": str(exc)})
            continue

        # Check OMML producible
        try:
            omath = mathml_to_omml_py(mathml)
            if omath is not None:
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
) -> dict[str, object] | None:
    try:
        transform = etree.XSLT(etree.parse(str(xsl_path)))
    except Exception as exc:
        return {"available": False, "error": str(exc)}

    ok = [c for c in candidates if c.get("parse_status") == "ok"]
    divergences: list[dict[str, object]] = []

    for candidate in ok[:20]:  # sample cap
        source = str(candidate.get("source", ""))
        try:
            mathml = formula_to_mathml(source)
        except FormulaError:
            continue

        try:
            xsl_omath = _mathml_to_omml_xsl(mathml, transform)
            py_omath = mathml_to_omml_py(mathml)
        except Exception as exc:
            divergences.append({"source": source, "error": str(exc)})
            continue

        xsl_count = _tag_signature(xsl_omath)
        py_count = _tag_signature(py_omath)
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
) -> dict[str, object]:
    if input_path.suffix.lower() != ".docx":
        raise ValueError("Input must be a .docx file")
    if not input_path.is_file():
        raise FileNotFoundError(f"Input DOCX was not found: {input_path}")

    from ._version import __version__

    report: dict[str, object] = {
        "mathfmt": __version__,
        "input": str(input_path.resolve()),
        "backend": "python" if xsl_path is None else "office-xsl",
        "valid": True,
        "package": {},
        "omml": {},
    }

    # Layer 1: package
    try:
        _, parts = inspect_docx(input_path)
    except zipfile.BadZipFile:
        report["valid"] = False
        report["package"] = {"valid_zip": False}
        return report

    report["package"] = _validate_package(input_path, parts)

    # Layer 2: OMML
    report["omml"] = _validate_omml_structure(parts)

    # Layer 3: coverage (requires review)
    if review_path is not None:
        review = json.loads(review_path.read_text(encoding="utf-8"))
        report["coverage"] = _validate_coverage(parts, review)

        # Layer 4: cross-backend (requires candidates + XSL)
        if xsl_path is not None:
            report["cross_backend"] = _validate_cross_backend(review.get("candidates", []), xsl_path)

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

    return report
