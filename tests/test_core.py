from __future__ import annotations

import pytest
from lxml import etree

from mathfmt.core import (
    M_NS,
    MML_NS,
    NS,
    W_NS,
    FormulaError,
    Node,
    candidate_runs,
    estimated_formula_width,
    formula_to_mathml,
    likely_code,
    mathml_to_omml,
    node_to_mathml,
    qname,
    run_with_text_like,
    set_math_font_size,
    split_top_level_additive,
    tokenize,
)


def local_tags(source: str) -> list[str]:
    return [etree.QName(node).localname for node in formula_to_mathml(source).iter()]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("lim(p->0)", "munder"),
        ("sin(x) + cos(x)", "mfenced"),
        ("(a+b)/(c-d)", "mfrac"),
        ("2x + 3*x", "mrow"),
        ("x^(2)", "msup"),
        ("p1,2 = ep", "msub"),
        ("-x <= +2", "mo"),
        ("x, y", "mrow"),
    ],
)
def test_supported_formula_structures(source: str, expected: str) -> None:
    assert expected in local_tags(source)


@pytest.mark.parametrize("source", ["x @ 2", "(x]", "x +", ")"])
def test_formula_errors_are_explicit(source: str) -> None:
    with pytest.raises(FormulaError):
        formula_to_mathml(source)


def test_tokenizer_accepts_trailing_space_and_rejects_unknown_text() -> None:
    assert tokenize("x = 1   ")[-1].kind == "EOF"
    with pytest.raises(FormulaError, match="Unrecognized"):
        tokenize("x @ 1")


def test_unknown_ast_node_is_rejected() -> None:
    with pytest.raises(FormulaError, match="Unsupported AST"):
        node_to_mathml(Node("not_a_real_node_kind"))


def transform(source: str) -> etree.XSLT:
    return etree.XSLT(etree.fromstring(source.encode("utf-8")))


def test_mathml_to_omml_accepts_supported_transform_roots() -> None:
    math = formula_to_mathml("x = 1")
    para_xsl = transform(
        f"""<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
        xmlns:m="{M_NS}"><xsl:template match="/"><m:oMathPara><m:oMath/></m:oMathPara></xsl:template>
        </xsl:stylesheet>"""
    )
    wrapper_xsl = transform(
        f"""<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
        xmlns:m="{M_NS}"><xsl:template match="/"><root><m:oMath/></root></xsl:template>
        </xsl:stylesheet>"""
    )
    assert mathml_to_omml(math, para_xsl).tag == qname(M_NS, "oMath")
    assert mathml_to_omml(math, wrapper_xsl).tag == qname(M_NS, "oMath")


@pytest.mark.parametrize(
    "body",
    [
        f"<m:oMathPara xmlns:m='{M_NS}'/>",
        f"<root xmlns:m='{M_NS}'/>",
    ],
)
def test_mathml_to_omml_rejects_transform_without_equation(body: str) -> None:
    xsl = transform(
        f"""<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
        <xsl:template match="/">{body}</xsl:template></xsl:stylesheet>"""
    )
    with pytest.raises(FormulaError):
        mathml_to_omml(formula_to_mathml("x = 1"), xsl)


@pytest.mark.parametrize(
    "text",
    [
        "% comment",
        "value = 1;",
        "step(system, t);",
        "import module",
    ],
)
def test_code_detection_positive_cases(text: str) -> None:
    assert likely_code(text)


def test_code_detection_leaves_prose_untouched() -> None:
    assert not likely_code("The result is x = 1")


def test_candidate_boundaries_and_low_score_text() -> None:
    candidates = candidate_runs("Result is x^2 + 1 = 2. More text")
    assert candidates
    assert candidates[0][2].endswith("= 2")
    assert candidate_runs("ordinary prose") == []


def test_table_line_splitting_respects_groups_and_unary_signs() -> None:
    source = "a+(b+c+d)+e+f+g"
    lines = split_top_level_additive(source, target_length=8)
    assert "".join(lines) == source
    assert all("(b+c+d)" in line for line in lines if "(" in line)
    assert split_top_level_additive("a*(b+c)") == ["a*(b+c)"]
    assert split_top_level_additive("x^-2+y", target_length=3) == ["x^-2", "+y"]


def test_estimated_width_accounts_for_derivatives() -> None:
    assert estimated_formula_width("s'(t)") == len("s'(t)") + 18


def test_math_run_font_size_updates_existing_and_new_properties() -> None:
    root = etree.fromstring(
        f"""<m:oMath xmlns:m="{M_NS}" xmlns:w="{W_NS}">
        <m:r><m:rPr/><m:t>x</m:t></m:r>
        <m:r><w:rPr><w:sz w:val="20"/></w:rPr><m:t>y</m:t></m:r>
        </m:oMath>"""
    )
    set_math_font_size(root, 16)
    assert root.xpath("count(.//w:sz[@w:val='16'])", namespaces=NS) == 2
    assert root.xpath("count(.//w:szCs[@w:val='16'])", namespaces=NS) == 2


def test_text_run_clone_preserves_formatting_and_spaces() -> None:
    run = etree.fromstring(
        f"<w:r xmlns:w='{W_NS}'><w:rPr><w:b/></w:rPr><w:t>old</w:t></w:r>"
    )
    cloned = run_with_text_like(run, " suffix ")
    assert cloned.xpath("boolean(./w:rPr/w:b)", namespaces=NS)
    text = cloned.find(qname(W_NS, "t"))
    assert text is not None and text.get("{http://www.w3.org/XML/1998/namespace}space") == "preserve"
    assert etree.QName(formula_to_mathml("x")).namespace == MML_NS
