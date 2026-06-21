from __future__ import annotations

from lxml import etree

from mathfmt.core import M_NS, formula_to_mathml, qname
from mathfmt.omml import mathml_to_omml_py


def omath_for(source: str) -> etree._Element:
    return mathml_to_omml_py(formula_to_mathml(source))


def tags(source: str) -> set[str]:
    root = omath_for(source)
    return {etree.QName(e).localname for e in root.iter()}


def count_tag(source: str, local: str) -> int:
    return len(omath_for(source).xpath(f".//m:{local}", namespaces={"m": M_NS}))


# -- structure tests ----------------------------------------------------------


def test_fraction_produces_m_f() -> None:
    assert "f" in tags("a/(b+c)")
    t = omath_for("a/b")
    f = t.find(qname(M_NS, "f"))
    assert f is not None
    assert f.find(qname(M_NS, "num")) is not None
    assert f.find(qname(M_NS, "den")) is not None


def test_radical_produces_m_rad() -> None:
    assert "rad" in tags("sqrt(x^2+1)")
    rad = omath_for("sqrt(x)").find(".//m:rad", namespaces={"m": M_NS})
    assert rad is not None
    rad_pr = rad.find(qname(M_NS, "radPr"))
    assert rad_pr is not None
    deg_hide = rad_pr.find(qname(M_NS, "degHide"))
    assert deg_hide is not None
    assert deg_hide.get(qname(M_NS, "val")) == "1"


def test_superscript_produces_m_sSup() -> None:
    assert "sSup" in tags("x^3")
    ssup = omath_for("x^2").find(".//m:sSup", namespaces={"m": M_NS})
    assert ssup is not None
    assert ssup.find(qname(M_NS, "e")) is not None
    assert ssup.find(qname(M_NS, "sup")) is not None


def test_subscript_produces_m_sSub() -> None:
    assert "sSub" in tags("p1 = p2")
    ssub = omath_for("p1").find(".//m:sSub", namespaces={"m": M_NS})
    assert ssub is not None
    assert ssub.find(qname(M_NS, "e")) is not None
    assert ssub.find(qname(M_NS, "sub")) is not None


def test_delimited_group_produces_m_d() -> None:
    assert "d" in tags("sin(x)")


def test_limit_produces_m_limLow() -> None:
    assert "limLow" in tags("lim(p->0)")


def test_derivative_produces_m_f() -> None:
    assert "f" in tags("ds(t)/dt")


# -- round-trip tests (all README examples) -----------------------------------


def test_all_readme_examples_produce_omath_root() -> None:
    examples = [
        "ds(t)/dt",
        "s'(t) = -s''(t)",
        "sqrt(x^2 + 1)",
        "x^3 + p1",
        "x != 0",
        "sin(x) + cos(x)",
        "lim(p->0)",
        "a/(b+c)",
        "e^(p1*t)",
        "1(t)",
        "Delta + pi",
        "x, y, z",
    ]
    for ex in examples:
        omath = omath_for(ex)
        assert etree.QName(omath).localname == "oMath", f"failed on: {ex}"
        assert len(omath) > 0, f"empty oMath for: {ex}"


# -- operator / edge case tests -----------------------------------------------


def test_invisible_times_is_skipped() -> None:
    num_runs = count_tag("a b", "r")
    assert num_runs == 2  # just a and b, no invisible-times run


def test_subscript_pPAIR_has_nested_runs() -> None:
    assert count_tag("p1,2", "r") >= 3


def test_greek_letters_are_text_runs() -> None:
    for source in ("Delta = 1", "pi > 0"):
        assert count_tag(source, "r") >= 1


def test_number_is_text_run() -> None:
    omath = omath_for("x = 42")
    runs = omath.xpath(".//m:r/m:t", namespaces={"m": M_NS})
    texts = {r.text for r in runs}
    assert "42" in texts


def test_binary_operator_is_text_run() -> None:
    omath = omath_for("a + b")
    runs = omath.xpath(".//m:r/m:t", namespaces={"m": M_NS})
    texts = [r.text for r in runs]
    assert "+" in texts
    assert texts == ["a", "+", "b"]


def test_unary_minus_is_preserved() -> None:
    omath = omath_for("-x")
    runs = omath.xpath(".//m:r/m:t", namespaces={"m": M_NS})
    assert runs[0].text == "-"
    assert runs[1].text == "x"


def test_comma_separated_sequence() -> None:
    omath = omath_for("x, y, z")
    runs = omath.xpath(".//m:r/m:t", namespaces={"m": M_NS})
    texts = [r.text for r in runs]
    assert texts == ["x", ",", "y", ",", "z"]


def test_variable_with_numeric_suffix_is_subscript() -> None:
    assert "sSub" in tags("e0")
    assert "sSub" in tags("ep")


def test_function_application_has_delimiters() -> None:
    assert "d" in tags("exp(x)")


def test_nested_fraction() -> None:
    omath = omath_for("a/(b/c)")
    assert len(omath.xpath(".//m:f", namespaces={"m": M_NS})) == 2
