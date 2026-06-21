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
# Known v0.1.0 limitations — planned for v0.3.0 (formal grammar + LaTeX input)
# ---------------------------------------------------------------------------


@pytest.mark.xfail(reason="Integral (∫) not supported — planned for v0.3.0")
def test_integral_notation() -> None:
    formula_to_mathml("∫f(x)dx")


@pytest.mark.xfail(reason="Summation (∑) not supported — planned for v0.3.0")
def test_summation_notation() -> None:
    formula_to_mathml("∑_{i=1}^{n} x_i")


@pytest.mark.xfail(reason="Matrix notation not supported (no mtable output) — planned for v0.3.0")
def test_matrix_notation() -> None:
    root = formula_to_mathml("[[a, b], [c, d]]")
    tags = {etree.QName(e).localname for e in root.iter()}
    assert "mtable" in tags


@pytest.mark.xfail(reason="Vector notation not supported (brackets become generic group) — planned for v0.3.0")
def test_vector_notation() -> None:
    root = formula_to_mathml("v = [x, y, z]")
    tags = {etree.QName(e).localname for e in root.iter()}
    assert "mover" in tags


@pytest.mark.xfail(reason="Piecewise / cases not supported — planned for v0.3.0")
def test_piecewise_notation() -> None:
    formula_to_mathml("f(x) = {0, x<0; 1, x>=0}")


@pytest.mark.xfail(reason="Subscript limit (lim_{x→0}) not supported; inline lim(x->0) works")
def test_limit_subscript_notation() -> None:
    root = formula_to_mathml("lim_{x→0} f(x)")
    assert "munder" not in {etree.QName(e).localname for e in root.iter()}


@pytest.mark.xfail(reason="Heuristic scan may miss formulas without anchor operators (= ≠ ≤ etc.)")
def test_scan_misses_formulas_without_anchors() -> None:
    from mathfmt.core import candidate_runs
    assert len(candidate_runs("a b c d e f")) > 0


@pytest.mark.xfail(reason="Cross-paragraph formulas not merged — each paragraph scanned independently")
def test_cross_paragraph_formula_detection() -> None:
    from mathfmt.core import candidate_runs
    candidates = candidate_runs("x = 1\n+ 2")
    assert len(candidates) > 0
