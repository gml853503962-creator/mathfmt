# Formula Syntax

What MathFmt accepts as plain-text input, how it transforms it, and what MathML it produces.

---

## 1. Preprocessing

Before the tokenizer runs, `preprocess_formula` applies these transformations in order:

### Derivative normalization

| Input pattern | Normalized form | MathML output |
|---|---|---|
| `ds(t)/dt` | `DERV0` (1st-order Leibniz) | Stacked fraction d s(t) / d t |
| `d²s(t)/dt²` or `d^2s(t)/dt^2` | `DERV0` (2nd-order Leibniz) | d² s(t) / d t² |
| `s'(t)` or `s˙(t)` | `DERV0` (1st-order Newton) | ds(t)/dt fraction |
| `s''(t)` or `s¨(t)` | `DERV0` (2nd-order Newton) | d²s(t)/dt² fraction |

All derivatives render as **stacked Leibniz fractions**. The prime/Newton and dot notations are accepted as input shorthands but always produce fraction output.

### Superscript characters

Adjacent Unicode superscript chars become `^` notation:

| Input | Normalized |
|---|---|
| `x²` | `x^2` |
| `e⁺ˣ` | `e^(+x)` |
| `x⁻¹` | `x^(-1)` |

### Subscript characters

Unicode subscript chars become plain ASCII:

| Input | Normalized |
|---|---|
| `p₁` | `p1` |
| `e₀` | `e0` |
| `p₁,₂` | `pPAIR` (special — renders as p₁,₂) |

### Operator aliases

| Input | Normalized | Renders as |
|---|---|---|
| `!=` | `≠` | ≠ |
| `<=` | `≤` | ≤ |
| `>=` | `≥` | ≥ |
| `->` | `→` | → |
| `=>` | `⇒` | ⇒ |
| `+/-` | `±` | ± |
| `√(...)` | `sqrt(...)` | √(...) |
| `×` | `*` | · (invisible multiply) |
| `·` | `*` | · (invisible multiply) |
| `÷` | `/` | fraction bar |

### Function and constant normalization

| Input | Normalized | Renders as |
|---|---|---|
| `1(t)` or `Γ(t)` | `u(t)` | u(t) |
| `Delta` | `Δ` | Δ |
| `inf` | `∞` | ∞ |
| `pi` | `π` | π |
| `lim_{p→0}` | `lim(p->0)` | lim under p→0 |

### Exponent brace unwrapping

| Input | Normalized |
|---|---|
| `e^{p1t}` | `e^(p1t)` |

---

## 2. Tokenizer

The tokenizer uses this regex (simplified):

```
NUMBER  : \d+(?:[.,]\d+)?
IDENT   : sqrt | lim | exp | sin | cos | tan | Delta | pi | inf
        | e[pv] | pPAIR | DERV\d+
        | [A-Za-z](?:\d+)? | [ΔπΓ∞]
OP      : <= | >= | != | ~= | -> | => | +/- | [+−*/^=<>±≠≤≥≈→⇒·×÷]
LPAREN  : ( [ {
RPAREN  : ) ] }
COMMA   : ,
```

Whitespace between tokens is ignored.

### Token examples

| Input | Tokens |
|---|---|
| `x^2 = 4` | IDENT(x) OP(^) NUMBER(2) OP(=) NUMBER(4) |
| `sin(x)` | IDENT(sin) LPAREN(() IDENT(x) RPAREN()) |
| `p1 = ep` | IDENT(p1) OP(=) IDENT(ep) |
| `a, b, c` | IDENT(a) COMMA IDENT(b) COMMA IDENT(c) |

---

## 3. Grammar (BNF)

```
sequence   → relation ("," relation)*
relation   → add (OP_relation add)*
add        → mul (OP_add mul)*
mul        → power (OP_mul power | power)*     // implicit multiply via adjacency
power      → unary ("^" power)?
unary      → OP_unary unary | atom
atom       → NUMBER | IDENT | group | function | sqrt | limit | derivative
group      → "(" sequence ")" | "[" sequence "]" | "{" sequence "}"
function   → IDENT "(" sequence ")"
sqrt       → "sqrt" "(" sequence ")"
limit      → "lim" "(" sequence ")"
derivative → DERV{N}                            // injected by preprocessor
```

### Operator sets

| Level | Operators |
|---|---|
| `OP_relation` | `=` `<` `>` `≤` `≥` `≠` `~=` `→` `⇒` |
| `OP_add` | `+` `-` `±` |
| `OP_mul` | `*` `·` `×` `/` `÷` |
| `OP_unary` | `+` `-` |

### Precedence (lowest to highest)

1. `,` (sequence separator)
2. `=` `<` `>` `≤` `≥` `≠` `~=` `→` `⇒` (relations)
3. `+` `-` `±` (addition)
4. `*` `/` implicit (multiplication — implicit multiply binds tighter than explicit)
5. `^` (power — right-associative)
6. Unary `+` `-`

### Grouping

Brackets must match: `(...)`, `[...]`, `{...}`. Brackets inside a fraction's numerator/denominator are stripped from the MathML output (e.g. `(a+b)/(c-d)` renders without the literal parentheses).

---

## 4. MathML Output Mapping

| AST node | MathML element(s) |
|---|---|
| `number` | `m:mn` |
| `identifier` (e.g. `x`, `e0`) | `m:mi` or `m:msub` (when subscripted like `p1`) |
| `identifier` `pPAIR` | `m:msub` with `p` and `m:mrow(1, ,, 2)` |
| `identifier` `∞` | `m:mo` (infinity) |
| `identifier` `Δ`, `π` | `m:mi` (Greek letter) |
| `derivative` | `m:mfrac` with stacked numerator/denominator |
| `group` `(...)` | `m:mfenced` |
| `sqrt` | `m:msqrt` |
| `function` `sin(…)` | `m:mrow(m:mi(sin), m:mfenced(…))` |
| `limit` `lim(p→0)` | `m:munder(m:mi(lim), …)` |
| `unary` `−x` | `m:mrow(m:mo(−), …)` |
| `power` `x^2` | `m:msup` |
| `binary` `/` | `m:mfrac` (stacked fraction, outer groups stripped) |
| `binary` `*` or `implicit` | `m:mrow` with invisible-times `m:mo` (U+2062) |
| `binary` `+` `−` `=` `→` etc. | `m:mrow(left, m:mo(op), right)` |
| `sequence` `a, b, c` | `m:mrow` with `m:mo(,)` separators |

---

## 5. Scanning Heuristics

Formulas are detected by walking character runs. A span must satisfy **all** of:

1. **Character whitelist**: every character in `"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789₀₁₂₃₄₅₆₇₈₉ₚᵥₜ⁰¹²³⁴⁵⁶⁷⁸⁹+-*/^=<>!...()[]{}.,"` (full list in `MATH_CHARS` in `core.py`).
2. **Anchor operator**: must contain at least one of `=` `≠` `<=` `>=` `!=` `→` `->` `±` `+/-` `√` `sqrt` `lim`.
3. **Minimum score** ≥ 4: scored by `math_score` — 3 points per `=`/`≠`/`<=`/`>=`/`!=`, 2 points per `+*/^√±∞→`, 1 point per function call pattern `f(x)`, 0.5 points per digit.

### Code exclusion

A paragraph is skipped entirely when `likely_code` returns `True`:

- Starts with `%`, `#`, `pkg`, `clear`, `close`, `plot`, `grid`, `xlabel`, `ylabel`, `title`, `legend`, `hold`, `for`, `while`, `if`, `function`, `import`, `from`.
- Contains `;` with assignment (e.g. `y = step(sys, t);`).
- Matches known function patterns that end with `;` (e.g. `tf(…);`, `step(…);`, `roots(…);`, `exp(…);`).

### Existing equations and images

Paragraphs containing `m:oMath`, `m:oMathPara`, `w:drawing`, or `w:pict` are skipped entirely during scanning. They appear in the report summary as `existing_equations` and `drawing_paragraphs`.

### Pre/post trimming

Candidates are cleaned by removing:

- Leading/trailing punctuation (`.`, `,`, `;`, `:`)
- Trailing prose after a sentence-ending `.` followed by a capital letter
- Trailing French/English linking words: `avec`, `si`, `et`, `Elle`, `C`, `La`, `Pour`, `est`, `sont`, `vaut`, `discriminant`, `vers`, `equals`, `is`

---

## 6. Limitations

### Unsupported structures (will raise `FormulaError`)

| Structure | Example | Tracked by |
|---|---|---|
| Integral | `∫f(x)dx` | `test_integral_notation` (xfail) |
| Summation | `∑_{i=1}^{n} x_i` | `test_summation_notation` (xfail) |
| Matrix | `[[a,b],[c,d]]` | `test_matrix_notation` (xfail) |
| Vector | `[x, y, z]` | `test_vector_notation` (xfail) |
| Piecewise/cases | `f(x) = {0, x<0; 1, x>=0}` | `test_piecewise_notation` (xfail) |
| `lim_{x→0}` (subscript) | `lim_{x→0}` (use `lim(x->0)`) | `test_limit_subscript_notation` (xfail) |

### Heuristic limitations

- **False positives**: prose that resembles a formula may be selected as a candidate. Always review the `candidates.json` before applying.
- **False negatives**: formulas without anchor operators (`=`, `≠`, `≤`, `≥`, `!=`, `→`, `->`, `±`, `+/-`, `√`, `sqrt`, `lim`) are not detected.
- **Cross-paragraph**: each paragraph is scanned independently; a formula split across two paragraphs is not merged.

### Structural limitations

- **Hyperlinks**: formulas inside `w:hyperlink` are skipped (the run nesting can't be reconstructed reliably).
- **Images**: paragraph-level image detection skips the whole paragraph; an image embedded mid-paragraph before a formula will cause the formula to be missed.
- **Formatting preservation**: when a formula occupies part of a single `w:r` (run), the suffix text after the formula inherits the original run's formatting. When a formula spans multiple runs, formatting of the boundary runs is preserved but intermediate runs' formatting is discarded.

### Platform

- **OMML conversion** requires Microsoft Office's `MML2OMML.XSL`. Without it, MathFmt can scan and parse but cannot produce native Word equations. macOS and Linux users must provide the stylesheet manually via `--xsl`.

---

## 7. Error Handling

### Parse failures

When `formula_to_mathml` raises `FormulaError`, the candidate is marked:

```json
{
  "id": "f0012",
  "selected": false,
  "parse_status": "review",
  "parse_error": "Unrecognized formula text near: '@ 2'"
}
```

Common parse errors:

| Error message | Cause |
|---|---|
| `Unrecognized formula text near: …` | Character not in tokenizer vocabulary |
| `Expected …, got …` | Syntax error (e.g. missing operator or bracket) |
| `Mismatched group: (}` | Opening/closing bracket mismatch |
| `Unsupported AST node: …` | Internal — valid parse but unknown node kind |

### Apply failures

During `apply`, a candidate is skipped (not converted) when:

- The DOCX part is not found in the file (`error: "DOCX part not found"`)
- The paragraph index is out of range (`error: "Paragraph index out of range"`)
- The source text no longer matches the document (`error: "Reviewed source no longer matches the paragraph span"`)
- The formula spans a hyperlink boundary (`error: "Formula span crosses a hyperlink or unsupported nested run"`)
- Any `FormulaError` or `etree` error during conversion

Skipped candidates appear in the result report under `skipped` and do not block other candidates.

---

## 8. Design Philosophy

See `skills/mathfmt/references/paper-notation.md` for the notation conventions MathFmt targets:

- Stacked fractions for division
- Radical bars for `sqrt(…)`
- True superscripts and subscripts (not `^`/`_` characters)
- Leibniz fraction derivatives
- `u(t)` for the unit-step function
- Standard mathematical operator glyphs (`±`, `≠`, `≤`, `≥`, `→`, `∞`, `Δ`, `π`)
- Invisible multiplication for coefficient-variable products
- Top-level `+`/`-` splitting for long table formulas
