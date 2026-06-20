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
