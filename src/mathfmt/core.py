#!/usr/bin/env python3
"""Scan and typeset plain-text DOCX formulas as native Word OMML equations."""

from __future__ import annotations

import copy
import json
import re
import shutil
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from .omml import mathml_to_omml_py

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
MML_NS = "http://www.w3.org/1998/Math/MathML"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"w": W_NS, "m": M_NS}

TARGET_PART_RE = re.compile(r"^word/(document|header\d+|footer\d+)\.xml$")

SUBSCRIPT_MAP = str.maketrans(
    "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ",
    "0123456789+-=()aehijklmnop rstuvx".replace(" ", ""),
)
SUPERSCRIPT_MAP = {
    "⁰": "0",
    "¹": "1",
    "²": "2",
    "³": "3",
    "⁴": "4",
    "⁵": "5",
    "⁶": "6",
    "⁷": "7",
    "⁸": "8",
    "⁹": "9",
    "⁺": "+",
    "⁻": "-",
    "⁼": "=",
    "⁽": "(",
    "⁾": ")",
    "ⁿ": "n",
}
SUPERSCRIPT_CHARS = "".join(SUPERSCRIPT_MAP)

CODE_START_RE = re.compile(
    r"^(?:%|#|pkg\s|clear\b|close\b|plot\b|grid\b|xlabel\b|ylabel\b|"
    r"title\b|legend\b|hold\b|for\b|while\b|if\b|function\b|import\b|from\b)",
    re.IGNORECASE,
)
FORMULA_ANCHOR_RE = re.compile(r"(?:=|≠|<=|>=|!=|→|->|±|\+/-|√|sqrt|lim|∫|∑|∏)")
MATH_CHARS = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    "₀₁₂₃₄₅₆₇₈₉ₚᵥₜ⁰¹²³⁴⁵⁶⁷⁸⁹+-*/^=<>!~→⇒±≠≤≥≈√∞ΔπΓ"
    "()[]{}.,'′˙¨·×÷_ \t∫∑∏;|"
)
TRIM_PUNCT = " \t,，.。;；:："


def qname(ns: str, local: str) -> str:
    return f"{{{ns}}}{local}"


def mml(local: str, text: str | None = None, **attrs: str) -> etree._Element:
    element = etree.Element(qname(MML_NS, local), **attrs)
    if text is not None:
        element.text = text
    return element


def mrow(*children: etree._Element) -> etree._Element:
    row = mml("mrow")
    for child in children:
        row.append(child)
    return row


@dataclass(frozen=True)
class Token:
    kind: str
    value: str


@dataclass
class Node:
    kind: str
    value: str | None = None
    children: tuple[Node, ...] = ()
    meta: dict[str, str] | None = None


class FormulaError(ValueError):
    pass


TOKEN_RE = re.compile(
    r"\s*(?:"
    r"(?P<MATRIX_OPEN>\[\[)|"
    r"(?P<MATRIX_CLOSE>\]\])|"
    r"(?P<NUMBER>\d+(?:[\.,]\d+)?)|"
    r"(?P<IDENT>sqrt|lim|exp|sin|cos|tan|Delta|pi|inf|e[pv]|pPAIR|DERV\d+|[A-Za-z](?:\d+)?|[ΔπΓ∞∫∑∏])|"
    r"(?P<OP><=|>=|!=|~=|->|=>|\+/-|[+\-*/^=<>±≠≤≥≈→⇒·×÷_])|"
    r"(?P<LPAREN>[\(\[\{])|(?P<RPAREN>[\)\]\}])|(?P<COMMA>,)|(?P<SEMI>;)"
    r")"
)


def preprocess_formula(source: str) -> tuple[str, dict[str, tuple[int, str, str]]]:
    text = source.strip()
    derivatives: dict[str, tuple[int, str, str]] = {}

    leibniz_patterns = [
        (2, re.compile(r"\bd(?:\^?2|²)([A-Za-z])\(([^()]*)\)/d([A-Za-z])(?:\^?2|²)")),
        (1, re.compile(r"\bd([A-Za-z])\(([^()]*)\)/d([A-Za-z])")),
    ]
    for order, pattern in leibniz_patterns:
        while True:
            match = pattern.search(text)
            if not match:
                break
            key = f"DERV{len(derivatives)}"
            derivatives[key] = (order, match.group(1), match.group(3))
            text = text[: match.start()] + key + text[match.end() :]

    derivative_patterns = [
        (2, re.compile(r"([A-Za-z])(?:''|¨)\(([^()]*)\)")),
        (1, re.compile(r"([A-Za-z])(?:'|′|˙)\(([^()]*)\)")),
    ]
    for order, pattern in derivative_patterns:
        while True:
            match = pattern.search(text)
            if not match:
                break
            key = f"DERV{len(derivatives)}"
            derivatives[key] = (order, match.group(1), match.group(2))
            text = text[: match.start()] + key + text[match.end() :]

    text = text.replace("limₚ→0", "lim(p->0)").replace("limₜ→∞", "lim(t->inf)")
    text = re.sub(r"lim_\{([^}]+)\}", r"lim(\1)", text)
    text = re.sub(r"\b∑_\{([^{}]+)\}\^\{([^{}]+)\}", r"sum(\1,\2,", text)
    text = re.sub(
        r"([A-Za-z0-9)\]])([" + re.escape(SUPERSCRIPT_CHARS) + r"]+)",
        lambda m: m.group(1) + "^" + "".join(SUPERSCRIPT_MAP[c] for c in m.group(2)),
        text,
    )
    text = text.translate(SUBSCRIPT_MAP)
    text = re.sub(r"\bp1\s*,\s*2\b", "pPAIR", text)
    text = text.replace("√", "sqrt").replace("+/-", "±")
    text = text.replace("!=", "≠").replace("<=", "≤").replace(">=", "≥")
    text = text.replace("->", "→").replace("=>", "⇒")
    text = text.replace("×", "*").replace("·", "*").replace("÷", "/")
    text = re.sub(r"(?:Γ|1)\(t\)", "u(t)", text)
    text = re.sub(r"\bDelta\b", "Δ", text)
    text = re.sub(r"\binf\b", "∞", text)
    text = re.sub(r"\bpi\b", "π", text)
    text = re.sub(r"e\^\{([^{}]+)\}", r"e^(\1)", text)
    return text, derivatives


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    position = 0
    while position < len(text):
        match = TOKEN_RE.match(text, position)
        if not match:
            if text[position:].strip() == "":
                break
            raise FormulaError(f"Unrecognized formula text near: {text[position : position + 24]!r}")
        kind = match.lastgroup
        if kind is None:
            raise FormulaError("Tokenizer produced an empty token")
        tokens.append(Token(kind, match.group(kind)))
        position = match.end()
    tokens.append(Token("EOF", ""))
    return tokens


def _serialize_ast(node: Node) -> str:
    if node.kind in {"number", "identifier"}:
        return node.value or ""
    if node.kind == "sequence":
        return ",".join(_serialize_ast(c) for c in node.children)
    if node.kind == "binary":
        if node.value == "implicit":
            return _serialize_ast(node.children[0]) + _serialize_ast(node.children[1])
        return _serialize_ast(node.children[0]) + (node.value or "") + _serialize_ast(node.children[1])
    return ""


class Parser:
    def __init__(self, tokens: Sequence[Token], derivatives: dict[str, tuple[int, str, str]]):
        self.tokens = tokens
        self.derivatives = derivatives
        self.index = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def advance(self) -> Token:
        token = self.current
        self.index += 1
        return token

    def accept(self, kind: str, value: str | None = None) -> Token | None:
        if self.current.kind == kind and (value is None or self.current.value == value):
            return self.advance()
        return None

    def expect(self, kind: str) -> Token:
        token = self.accept(kind)
        if token is None:
            raise FormulaError(f"Expected {kind}, got {self.current.kind} {self.current.value!r}")
        return token

    def parse(self) -> Node:
        node = self.parse_sequence()
        if self.current.kind != "EOF":
            raise FormulaError(f"Unexpected token: {self.current.value!r}")
        return node

    def parse_sequence(self, semi_is_branch: bool = False) -> Node:
        nodes = [self.parse_relation()]
        while self.accept("COMMA"):
            nodes.append(self.parse_relation())
        if semi_is_branch and self.current.kind == "SEMI":
            branches = [Node("sequence", children=tuple(nodes))]
            while self.accept("SEMI"):
                branch_nodes = [self.parse_relation()]
                while self.accept("COMMA"):
                    branch_nodes.append(self.parse_relation())
                branches.append(Node("sequence", children=tuple(branch_nodes)))
            return Node("piecewise", children=tuple(branches))
        return nodes[0] if len(nodes) == 1 else Node("sequence", children=tuple(nodes))

    def parse_relation(self) -> Node:
        node = self.parse_add()
        while self.current.kind == "OP" and self.current.value in {
            "=",
            "<",
            ">",
            "≤",
            "≥",
            "≠",
            "~=",
            "→",
            "⇒",
        }:
            op = self.advance().value
            node = Node("binary", op, (node, self.parse_add()))
        return node

    def parse_add(self) -> Node:
        node = self.parse_mul()
        while self.current.kind == "OP" and self.current.value in {"+", "-", "±"}:
            op = self.advance().value
            node = Node("binary", op, (node, self.parse_mul()))
        return node

    def starts_atom(self) -> bool:
        return self.current.kind in {"NUMBER", "IDENT", "LPAREN", "MATRIX_OPEN"}

    def parse_mul(self) -> Node:
        node = self.parse_power()
        while True:
            if self.current.kind == "OP" and self.current.value in {"*", "·", "×", "/", "÷"}:
                op = self.advance().value
                node = Node("binary", "/" if op in {"/", "÷"} else "*", (node, self.parse_power()))
            elif self.starts_atom() and self.current.kind != "MATRIX_OPEN":
                node = Node("binary", "implicit", (node, self.parse_power()))
            else:
                break
        return node

    def parse_power(self) -> Node:
        node = self.parse_subsup()
        if self.current.kind == "OP" and self.current.value == "^":
            self.advance()
            node = Node("power", children=(node, self.parse_power()))
        return node

    def parse_subsup(self) -> Node:
        node = self.parse_unary()
        if self.current.kind == "OP" and self.current.value == "_":
            self.advance()
            sub = self.parse_unary()
            if self.current.kind == "OP" and self.current.value == "^":
                self.advance()
                sup = self.parse_unary()
                return Node("subsup", children=(node, sub, sup))
            return Node("sub", children=(node, sub))
        return node

    def parse_unary(self) -> Node:
        if self.current.kind == "OP" and self.current.value in {"+", "-"}:
            return Node("unary", self.advance().value, (self.parse_unary(),))
        return self.parse_atom()

    def parse_group(self) -> Node:
        opener = self.expect("LPAREN").value
        closer = {"(": ")", "[": "]", "{": "}"}[opener]
        child = self.parse_sequence(semi_is_branch=(opener == "{"))
        token = self.expect("RPAREN")
        if token.value != closer:
            raise FormulaError(f"Mismatched group: {opener}{token.value}")
        if child.kind == "piecewise":
            return child
        if opener == "[" and child.kind == "sequence":
            return Node("vector", children=child.children)
        return Node("group", opener + closer, (child,))

    def _parse_nary(self, name: str) -> Node:
        return Node("nary", name)

    def parse_atom(self) -> Node:
        if token := self.accept("MATRIX_OPEN"):
            return self._parse_matrix()
        if token := self.accept("NUMBER"):
            return Node("number", token.value)
        if self.current.kind == "LPAREN":
            return self.parse_group()
        if token := self.accept("IDENT"):
            name = token.value
            if name in self.derivatives:
                order, variable, argument = self.derivatives[name]
                return Node(
                    "derivative",
                    children=(Node("identifier", variable), Node("identifier", argument)),
                    meta={"order": str(order)},
                )
            if name in {"∫", "∏", "∑"}:
                return self._parse_nary(name)
            if self.current.kind == "LPAREN":
                group = self.parse_group()
                if name in {"sqrt", "√"}:
                    return Node("sqrt", children=group.children)
                if name == "lim":
                    return Node("limit", children=group.children)
                return Node("function", name, group.children)
            return Node("identifier", name)
        raise FormulaError(f"Expected formula atom, got {self.current.kind} {self.current.value!r}")

    def _parse_matrix(self) -> Node:
        rows: list[Node] = []
        row = self.parse_sequence()
        rows.append(row)
        while self.accept("MATRIX_CLOSE") is None:
            self.accept("RPAREN")
            if self.accept("COMMA") or self.accept("SEMI"):
                self.accept("LPAREN")
                row = self.parse_sequence()
                rows.append(row)
            elif self.accept("MATRIX_CLOSE"):
                break
            else:
                raise FormulaError("Expected ]] or , between matrix rows")
        return Node("matrix", children=tuple(rows))


def identifier_mathml(value: str) -> etree._Element:
    if value in {"∞", "inf"}:
        return mml("mo", "∞")
    greek = {"Delta": "Δ", "Δ": "Δ", "pi": "π", "π": "π"}
    if value in greek:
        return mml("mi", greek[value])
    if value == "pPAIR":
        sub = mml("msub")
        sub.append(mml("mi", "p"))
        sub.append(mrow(mml("mn", "1"), mml("mo", ","), mml("mn", "2")))
        return sub
    match = re.fullmatch(r"([A-Za-z])([0-9]+|[pv])", value)
    if match:
        sub = mml("msub")
        sub.append(mml("mi", match.group(1)))
        suffix = match.group(2)
        sub.append(mml("mn" if suffix.isdigit() else "mi", suffix))
        return sub
    return mml("mi", value)


def derivative_mathml(node: Node) -> etree._Element:
    order = int((node.meta or {}).get("order", "1"))
    variable = node_to_mathml(node.children[0])
    argument = node_to_mathml(node.children[1])
    function = mrow(variable, fenced(argument, "()"))
    numerator_d = mml("mi", "d")
    if order > 1:
        power = mml("msup")
        power.append(numerator_d)
        power.append(mml("mn", str(order)))
        numerator_d = power
    numerator = mrow(numerator_d, function)
    denominator_variable = node_to_mathml(node.children[1])
    if order > 1:
        power = mml("msup")
        power.append(denominator_variable)
        power.append(mml("mn", str(order)))
        denominator_variable = power
    denominator = mrow(mml("mi", "d"), denominator_variable)
    fraction = mml("mfrac")
    fraction.extend([numerator, denominator])
    return fraction


def fenced(child: etree._Element, brackets: str) -> etree._Element:
    element = mml("mfenced", open=brackets[0], close=brackets[1])
    element.append(child)
    return element


def node_to_mathml(node: Node) -> etree._Element:
    if node.kind == "number":
        return mml("mn", node.value or "")
    if node.kind == "identifier":
        return identifier_mathml(node.value or "")
    if node.kind == "derivative":
        return derivative_mathml(node)
    if node.kind == "group":
        return fenced(node_to_mathml(node.children[0]), node.value or "()")
    if node.kind == "sqrt":
        root = mml("msqrt")
        root.append(node_to_mathml(node.children[0]))
        return root
    if node.kind == "function":
        return mrow(identifier_mathml(node.value or ""), fenced(node_to_mathml(node.children[0]), "()"))
    if node.kind == "limit":
        under = mml("munder")
        under.append(mml("mi", "lim"))
        under.append(node_to_mathml(node.children[0]))
        return under
    if node.kind == "unary":
        return mrow(mml("mo", node.value or ""), node_to_mathml(node.children[0]))
    if node.kind == "power":
        power = mml("msup")
        exponent = node.children[1]
        if exponent.kind == "group" and exponent.value == "()":
            exponent = exponent.children[0]
        power.extend([node_to_mathml(node.children[0]), node_to_mathml(exponent)])
        return power
    if node.kind == "binary":
        left = node_to_mathml(node.children[0])
        right = node_to_mathml(node.children[1])
        if node.value == "/":
            left_node, right_node = node.children
            if left_node.kind == "group":
                left = node_to_mathml(left_node.children[0])
            if right_node.kind == "group":
                right = node_to_mathml(right_node.children[0])
            fraction = mml("mfrac")
            fraction.extend([left, right])
            return fraction
        if node.value in {"*", "implicit"}:
            return mrow(left, mml("mo", "\u2062"), right)
        symbols = {"~=": "≈"}
        return mrow(left, mml("mo", symbols.get(node.value or "", node.value or "")), right)
    if node.kind == "sequence":
        row = mml("mrow")
        for index, child in enumerate(node.children):
            if index:
                row.append(mml("mo", ","))
            row.append(node_to_mathml(child))
        return row
    if node.kind == "vector":
        row = mml("mrow")
        for index, child in enumerate(node.children):
            if index:
                row.append(mml("mo", ","))
            row.append(node_to_mathml(child))
        return fenced(row, "[]")
    if node.kind == "matrix":
        table = mml("mtable")
        for row_node in node.children:
            tr = mml("mtr")
            items = row_node.children if row_node.kind == "sequence" else (row_node,)
            for item in items:
                td = mml("mtd")
                td.append(node_to_mathml(item))
                tr.append(td)
            table.append(tr)
        return fenced(table, "[]")
    if node.kind == "sub":
        sub = mml("msub")
        sub.append(node_to_mathml(node.children[0]))
        sub.append(node_to_mathml(node.children[1]))
        return sub
    if node.kind == "subsup":
        ss = mml("msubsup")
        for child in node.children:
            ss.append(node_to_mathml(child))
        return ss
    if node.kind == "nary":
        nary_elem = mml("mo", node.value or "∫")
        return nary_elem
    if node.kind == "piecewise":
        row = mml("mrow")
        for i, branch in enumerate(node.children):
            if i:
                row.append(mml("mo", ";"))
            row.append(node_to_mathml(branch))
        return fenced(row, "{}")
    raise FormulaError(f"Unsupported AST node: {node.kind}")


def formula_to_mathml(source: str) -> etree._Element:
    normalized, derivatives = preprocess_formula(source)
    ast = Parser(tokenize(normalized), derivatives).parse()
    root = mml("math", display="inline", nsmap={None: MML_NS})
    root.append(node_to_mathml(ast))
    return root


def find_xsl(explicit: Path | None = None) -> Path:
    if explicit is not None and not explicit.is_file():
        raise FileNotFoundError(f"MML2OMML.XSL was not found at: {explicit}")
    candidates = [
        explicit,
        Path(r"C:\Program Files\Microsoft Office\root\Office16\MML2OMML.XSL"),
        Path(r"C:\Program Files (x86)\Microsoft Office\root\Office16\MML2OMML.XSL"),
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    raise FileNotFoundError("MML2OMML.XSL was not found; pass --xsl with its path")


def _mathml_to_omml_xsl(math: etree._Element, transform: etree.XSLT) -> etree._Element:
    """Convert MathML to OMML via Microsoft's MML2OMML.XSL stylesheet."""
    result = transform(etree.ElementTree(math))
    root = result.getroot()
    if root is None:
        raise FormulaError("MML2OMML produced no root element")
    if root.tag == qname(M_NS, "oMathPara"):
        equations = root.xpath(".//m:oMath", namespaces=NS)
        if not equations:
            raise FormulaError("MML2OMML output contains no m:oMath")
        return copy.deepcopy(equations[0])
    if root.tag == qname(M_NS, "oMath"):
        return copy.deepcopy(root)
    equations = root.xpath(".//m:oMath", namespaces=NS)
    if not equations:
        raise FormulaError(f"Unexpected MML2OMML root: {root.tag}")
    return copy.deepcopy(equations[0])


def mathml_to_omml(
    math: etree._Element,
    transform: etree.XSLT | None = None,
) -> etree._Element:
    """Convert MathML to OMML, using XSL when available or the built-in Python backend."""
    if transform is not None:
        return _mathml_to_omml_xsl(math, transform)
    return mathml_to_omml_py(math)


def paragraph_text(paragraph: etree._Element) -> str:
    return "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))


def likely_code(text: str) -> bool:
    stripped = text.strip()
    if CODE_START_RE.search(stripped):
        return True
    if ";" in stripped and re.search(r"\b[A-Za-z_]\w*\s*=", stripped):
        return True
    if re.search(r"\b(?:tf|step|roots|exp)\s*\(", stripped) and stripped.endswith(";"):
        return True
    return False


def math_score(source: str) -> int:
    score = 0
    score += 3 * len(re.findall(r"=|≠|<=|>=|!=", source))
    score += 2 * len(re.findall(r"[+*/^√±∞→]", source))
    score += len(re.findall(r"[A-Za-z]\w*\([^)]*\)", source))
    score += len(re.findall(r"\d", source)) // 2
    return score


def candidate_runs(text: str) -> list[tuple[int, int, str]]:
    candidates: list[tuple[int, int, str]] = []
    index = 0
    while index < len(text):
        if text[index] not in MATH_CHARS:
            index += 1
            continue
        start = index
        while index < len(text) and text[index] in MATH_CHARS:
            index += 1
        end = index
        raw = text[start:end]
        left_trim = len(raw) - len(raw.lstrip(TRIM_PUNCT))
        right_trim = len(raw) - len(raw.rstrip(TRIM_PUNCT))
        start += left_trim
        end -= right_trim
        source = text[start:end]
        if not source or not FORMULA_ANCHOR_RE.search(source) or math_score(source) < 4:
            continue
        source = re.split(r"\.\s+(?=[A-Za-z])", source, maxsplit=1)[0]
        source = re.split(r",?\s+(?:avec|si|et|Elle|C|La|Pour)\b", source, maxsplit=1, flags=re.IGNORECASE)[0]
        source = re.sub(
            r"^.*\b(?:est|sont|vaut|discriminant|vers|equals?|is)\s+",
            "",
            source,
            flags=re.IGNORECASE,
        )
        source = source.strip(TRIM_PUNCT)
        if not source or not FORMULA_ANCHOR_RE.search(source) or math_score(source) < 4:
            continue
        start = text.find(source, start, end)
        end = start + len(source)
        if source and start >= 0:
            candidates.append((start, end, source))
    deduped: list[tuple[int, int, str]] = []
    for item in candidates:
        if not deduped or item[:2] != deduped[-1][:2]:
            deduped.append(item)
    return deduped


def inspect_docx(input_path: Path) -> tuple[list[zipfile.ZipInfo], dict[str, bytes]]:
    with zipfile.ZipFile(input_path, "r") as archive:
        infos = archive.infolist()
        data = {info.filename: archive.read(info.filename) for info in infos}
    return infos, data


def scan_docx(input_path: Path, report_path: Path) -> dict[str, object]:
    if input_path.suffix.lower() != ".docx":
        raise ValueError("Input must be a .docx file")
    if not input_path.is_file():
        raise FileNotFoundError(f"Input DOCX was not found: {input_path}")
    _, parts = inspect_docx(input_path)
    report: dict[str, object] = {
        "schema_version": 2,
        "input": str(input_path.resolve()),
        "profile": {"derivatives": "fraction", "unit_step": "u(t)", "output": "native_word_omml"},
        "summary": {
            "paragraphs": 0,
            "candidates": 0,
            "existing_equations": 0,
            "drawing_paragraphs": 0,
            "code_paragraphs": 0,
        },
        "candidates": [],
    }
    candidates: list[dict[str, object]] = []
    summary = report["summary"]
    assert isinstance(summary, dict)

    for part_name, raw in parts.items():
        if not TARGET_PART_RE.match(part_name):
            continue
        root = etree.fromstring(raw)
        paragraphs = root.xpath(".//w:p", namespaces=NS)
        for paragraph_index, paragraph in enumerate(paragraphs):
            summary["paragraphs"] += 1
            if paragraph.xpath(".//m:oMath | .//m:oMathPara", namespaces=NS):
                summary["existing_equations"] += 1
                continue
            if paragraph.xpath(".//w:drawing | .//w:pict", namespaces=NS):
                summary["drawing_paragraphs"] += 1
                continue
            text = paragraph_text(paragraph)
            if not text.strip():
                continue
            if likely_code(text):
                summary["code_paragraphs"] += 1
                continue
            for start, end, source in candidate_runs(text):
                candidate_id = f"f{len(candidates) + 1:04d}"
                display = text.strip() == source.strip()
                score = math_score(source)
                has_relation = bool(re.search(r"[=≠≤≥≈→⇒]", source))
                has_func = bool(re.search(r"\([^)]*\)", source))
                if score >= 8 and has_relation:
                    confidence = "high"
                    reason = "strong formula signal"
                elif score >= 6 or (score >= 4 and (has_relation or has_func)):
                    confidence = "medium"
                    reason = "moderate formula signal"
                else:
                    confidence = "low"
                    reason = "weak formula signal; likely prose"

                candidate = {
                    "id": candidate_id,
                    "selected": confidence == "high",
                    "part": part_name,
                    "paragraph_index": paragraph_index,
                    "start": start,
                    "end": end,
                    "source": source,
                    "linear": source,
                    "display": display,
                    "paragraph_text": text,
                    "confidence": confidence,
                    "confidence_reason": reason,
                }
                try:
                    formula_to_mathml(source)
                    candidate["parse_status"] = "ok"
                except Exception as exc:
                    candidate["selected"] = False
                    candidate["parse_status"] = "review"
                    candidate["parse_error"] = str(exc)
                candidates.append(candidate)
    summary["candidates"] = len(candidates)
    report["candidates"] = candidates
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def ancestor_run(text_node: etree._Element, paragraph: etree._Element) -> etree._Element | None:
    current = text_node.getparent()
    while current is not None and current is not paragraph:
        if current.tag == qname(W_NS, "r") and current.getparent() is paragraph:
            return current
        current = current.getparent()
    return None


def run_with_text_like(run: etree._Element, text: str) -> etree._Element:
    new_run = etree.Element(qname(W_NS, "r"))
    rpr = run.find(qname(W_NS, "rPr"))
    if rpr is not None:
        new_run.append(copy.deepcopy(rpr))
    text_element = etree.SubElement(new_run, qname(W_NS, "t"))
    if text.startswith(" ") or text.endswith(" "):
        text_element.set(qname(XML_NS, "space"), "preserve")
    text_element.text = text
    return new_run


def replace_inline_span(paragraph: etree._Element, start: int, end: int, omath: etree._Element) -> None:
    text_nodes = paragraph.xpath(".//w:t", namespaces=NS)
    offsets: list[tuple[etree._Element, int, int]] = []
    cursor = 0
    for node in text_nodes:
        value = node.text or ""
        offsets.append((node, cursor, cursor + len(value)))
        cursor += len(value)
    touched = [(node, lo, hi) for node, lo, hi in offsets if hi > start and lo < end]
    if not touched:
        raise FormulaError("Candidate span does not overlap any text node")
    start_node, start_lo, _ = touched[0]
    end_node, end_lo, _ = touched[-1]
    start_run = ancestor_run(start_node, paragraph)
    end_run = ancestor_run(end_node, paragraph)
    if start_run is None or end_run is None:
        raise FormulaError("Formula span crosses a hyperlink or unsupported nested run")

    start_value = start_node.text or ""
    end_value = end_node.text or ""
    prefix = start_value[: max(0, start - start_lo)]
    suffix = end_value[max(0, end - end_lo) :]

    for node, lo, hi in touched:
        value = node.text or ""
        keep_left = value[: max(0, start - lo)] if node is start_node else ""
        keep_right = value[max(0, end - lo) :] if node is end_node else ""
        node.text = keep_left + keep_right
    start_node.text = prefix

    parent = paragraph
    insert_index = parent.index(start_run) + 1
    parent.insert(insert_index, omath)
    if start_run is end_run and suffix:
        start_node.text = prefix
        parent.insert(insert_index + 1, run_with_text_like(start_run, suffix))


def replace_display_paragraph(paragraph: etree._Element, omath: etree._Element) -> None:
    for child in list(paragraph):
        if child.tag != qname(W_NS, "pPr"):
            paragraph.remove(child)
    math_para = etree.Element(qname(M_NS, "oMathPara"))
    math_para.append(omath)
    paragraph.append(math_para)


def replace_multiline_table_formula(
    paragraph: etree._Element,
    equations: Sequence[etree._Element],
    suffix: str = "",
) -> None:
    for child in list(paragraph):
        if child.tag != qname(W_NS, "pPr"):
            paragraph.remove(child)
    for index, equation in enumerate(equations):
        if index:
            run = etree.SubElement(paragraph, qname(W_NS, "r"))
            etree.SubElement(run, qname(W_NS, "br"))
        paragraph.append(equation)
    if suffix:
        run = etree.SubElement(paragraph, qname(W_NS, "r"))
        text = etree.SubElement(run, qname(W_NS, "t"))
        text.text = suffix


def split_top_level_additive(text: str, target_length: int = 30) -> list[str]:
    depth = 0
    starts = [0]
    for index, char in enumerate(text):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif depth == 0 and char in "+-" and index > 0:
            previous = text[index - 1]
            if previous not in "=<>+-*/^(,":
                starts.append(index)
    if len(starts) == 1:
        return [text]
    terms = [
        text[starts[i] : starts[i + 1] if i + 1 < len(starts) else len(text)] for i in range(len(starts))
    ]
    lines: list[str] = []
    current = ""
    for term in terms:
        if current and len(current) + len(term) > target_length:
            lines.append(current)
            current = term
        else:
            current += term
    if current:
        lines.append(current)
    return lines


def estimated_formula_width(text: str) -> int:
    derivative_count = len(re.findall(r"(?:''|'|¨|˙)\s*\(", text))
    return len(text) + derivative_count * 18


def set_math_font_size(omath: etree._Element, half_points: int) -> None:
    for math_run in omath.xpath(".//m:r", namespaces=NS):
        word_rpr = math_run.find(qname(W_NS, "rPr"))
        if word_rpr is None:
            word_rpr = etree.Element(qname(W_NS, "rPr"))
            math_rpr = math_run.find(qname(M_NS, "rPr"))
            insert_at = 1 if math_rpr is not None else 0
            math_run.insert(insert_at, word_rpr)
        for local in ("sz", "szCs"):
            size = word_rpr.find(qname(W_NS, local))
            if size is None:
                size = etree.SubElement(word_rpr, qname(W_NS, local))
            size.set(qname(W_NS, "val"), str(half_points))


def apply_docx(
    input_path: Path,
    review_path: Path,
    output_path: Path,
    result_path: Path,
    xsl_path: Path | None = None,
) -> dict[str, object]:
    if input_path.suffix.lower() != ".docx" or output_path.suffix.lower() != ".docx":
        raise ValueError("Input and output must be .docx files")
    if input_path.resolve() == output_path.resolve():
        raise ValueError("Refusing to overwrite the input DOCX")
    review = json.loads(review_path.read_text(encoding="utf-8"))
    candidates = [c for c in review.get("candidates", []) if c.get("selected")]
    infos, parts = inspect_docx(input_path)
    transform = etree.XSLT(etree.parse(str(xsl_path))) if xsl_path is not None else None
    result: dict[str, object] = {
        "input": str(input_path.resolve()),
        "output": str(output_path.resolve()),
        "review": str(review_path.resolve()),
        "xsl": str(xsl_path.resolve()) if xsl_path else None,
        "converted": [],
        "skipped": [],
    }

    grouped: dict[tuple[str, int], list[dict[str, object]]] = {}
    for candidate in candidates:
        key = (str(candidate["part"]), int(candidate["paragraph_index"]))
        grouped.setdefault(key, []).append(candidate)

    for (part_name, paragraph_index), group in grouped.items():
        if part_name not in parts:
            for candidate in group:
                result["skipped"].append({"id": candidate.get("id"), "error": "DOCX part not found"})
            continue
        root = etree.fromstring(parts[part_name])
        paragraphs = root.xpath(".//w:p", namespaces=NS)
        if paragraph_index >= len(paragraphs):
            for candidate in group:
                result["skipped"].append({"id": candidate.get("id"), "error": "Paragraph index out of range"})
            continue
        paragraph = paragraphs[paragraph_index]
        original_text = paragraph_text(paragraph)
        for candidate in sorted(group, key=lambda c: int(c["start"]), reverse=True):
            try:
                start, end = int(candidate["start"]), int(candidate["end"])
                source = str(candidate["source"])
                if original_text[start:end] != source:
                    raise FormulaError("Reviewed source no longer matches the paragraph span")
                linear = str(candidate.get("linear", source))
                in_table = bool(paragraph.xpath("ancestor::w:tc", namespaces=NS))
                is_display = bool(candidate.get("display")) and source.strip() == original_text.strip()
                outside_formula = original_text[:start] + original_text[end:]
                covers_formula_paragraph = not outside_formula.strip(TRIM_PUNCT)
                table_lines = (
                    split_top_level_additive(linear)
                    if in_table and covers_formula_paragraph and estimated_formula_width(linear) > 65
                    else [linear]
                )
                equations = [mathml_to_omml(formula_to_mathml(line), transform) for line in table_lines]
                if in_table:
                    for equation in equations:
                        set_math_font_size(equation, 16)
                if len(equations) > 1:
                    replace_multiline_table_formula(paragraph, equations, original_text[end:])
                elif is_display:
                    omath = equations[0]
                    replace_display_paragraph(paragraph, omath)
                else:
                    omath = equations[0]
                    replace_inline_span(paragraph, start, end, omath)
                result["converted"].append(
                    {"id": candidate.get("id"), "source": source, "part": part_name, "lines": len(equations)}
                )
            except Exception as exc:
                result["skipped"].append(
                    {"id": candidate.get("id"), "source": candidate.get("source"), "error": str(exc)}
                )
        parts[part_name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for info in infos:
                archive.writestr(info, parts[info.filename])
        shutil.move(str(tmp_path), str(output_path))
    finally:
        tmp_path.unlink(missing_ok=True)
    result["converted_count"] = len(result["converted"])
    result["skipped_count"] = len(result["skipped"])
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
