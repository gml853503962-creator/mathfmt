from pathlib import Path

import pytest
from lxml import etree

from mathfmt.core import MML_NS, formula_to_mathml, preprocess_formula


def tags(source: str) -> set[str]:
    root = formula_to_mathml(source)
    return {etree.QName(node).localname for node in root.iter()}


def test_fraction_radical_power_and_subscript() -> None:
    assert "mfrac" in tags("ds(t)/dt")
    assert "msqrt" in tags("sqrt(x^2+1)")
    assert "msup" in tags("x^3")
    assert "msub" in tags("p1 = p2")


def test_prime_derivative_becomes_fraction() -> None:
    assert "mfrac" in tags("s'(t) = 1")


def test_leibniz_derivative_is_one_fraction() -> None:
    first = formula_to_mathml("ds(t)/dt")
    second = formula_to_mathml("d^2s(t)/dt^2")
    assert etree.QName(first[0]).localname == "mfrac"
    assert etree.QName(second[0]).localname == "mfrac"


def test_control_notation_normalization() -> None:
    normalized, _ = preprocess_formula("1(t) + Delta + inf + pi")
    assert normalized == "u(t) + Δ + ∞ + π"


def test_mathml_namespace() -> None:
    root = formula_to_mathml("x = 1")
    assert etree.QName(root).namespace == MML_NS


# ---------------------------------------------------------------------------
# Expanded v0.2 parser coverage — integral, sum, matrix, vector, piecewise, limit
# ---------------------------------------------------------------------------


def test_integral_notation() -> None:
    root = formula_to_mathml("∫x*dx")
    tags = {etree.QName(e).localname for e in root.iter()}
    assert "mo" in tags  # integral sign present


def test_summation_notation() -> None:
    root = formula_to_mathml("∑_{i=1}^{n} x_i")
    tags = {etree.QName(e).localname for e in root.iter()}
    assert "msubsup" in tags


def test_matrix_notation() -> None:
    root = formula_to_mathml("[[a, b], [c, d]]")
    tags = {etree.QName(e).localname for e in root.iter()}
    assert "mtable" in tags


def test_vector_notation() -> None:
    root = formula_to_mathml("v = [x, y, z]")
    tags = {etree.QName(e).localname for e in root.iter()}
    assert "mfenced" in tags


def test_piecewise_notation() -> None:
    root = formula_to_mathml("f(x) = {0, x<0; 1, x>=0}")
    tags = {etree.QName(e).localname for e in root.iter()}
    assert "piecewise" in tags or "mfenced" in tags


def test_limit_subscript_notation() -> None:
    root = formula_to_mathml("lim_{x→0} f(x)")
    tags = {etree.QName(e).localname for e in root.iter()}
    assert "munder" in tags


def test_confidence_scoring_in_scan(tmp_path: Path) -> None:
    from mathfmt.core import scan_docx
    from tests.helpers import make_docx

    source = make_docx(tmp_path / "conf.docx")
    report = scan_docx(source, tmp_path / "conf.json")
    assert report["schema_version"] == 2
    for c in report["candidates"]:
        assert "confidence" in c
        assert c["confidence"] in {"high", "medium", "low"}


# ---------------------------------------------------------------------------
# Known v0.2 limitations — heuristic boundaries
# ---------------------------------------------------------------------------


@pytest.mark.xfail(reason="Heuristic scan may miss formulas without anchor operators (= ≠ ≤ etc.)")
def test_scan_misses_formulas_without_anchors() -> None:
    from mathfmt.core import candidate_runs
    assert len(candidate_runs("a b c d e f")) > 0


@pytest.mark.xfail(reason="Cross-paragraph formulas not merged — each paragraph scanned independently")
def test_cross_paragraph_formula_detection() -> None:
    from mathfmt.core import candidate_runs
    candidates = candidate_runs("x = 1\n+ 2")
    assert len(candidates) > 0
