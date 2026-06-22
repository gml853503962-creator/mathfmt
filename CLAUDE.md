# MathFmt — Project Reference for Claude Code

> Typeset plain-text formulas in DOCX files as native Word OMML equations — cross-platform, no Office required.

## Overview

MathFmt is a Python CLI tool & library that converts plain-text math formulas (e.g. `x^2+1`, `sqrt(a/b)`, `lim(x->0)`) embedded in `.docx` files into native Office Math Markup Language (OMML) equations. Designed for textbooks, exams, and technical reports.

- **Author:** Leo (gml853503962@gmail.com)
- **Version:** 0.2.2 (see `src/mathfmt/_version.py`)
- **License:** MIT
- **Repo:** https://github.com/gml853503962-creator/mathfmt
- **Python:** ≥3.10 (pure Python, no native extensions)
- **Sole runtime dependency:** `lxml >= 5.0`
- **Dev dependencies:** `build`, `pytest`, `pytest-cov`, `ruff`

---

## Directory Structure

```
MathFmt/
├── src/mathfmt/           # Package source (5 production modules)
│   ├── __init__.py        # Public API exports (8 symbols)
│   ├── _version.py        # Single version source: "0.2.2"
│   ├── cli.py             # argparse CLI: 6 subcommands
│   ├── core.py            # Core engine (~950 lines): scan, parse, apply
│   ├── omml.py            # Pure-Python MathML→OMML converter
│   ├── update.py          # Self-update checker (GitHub Releases API)
│   └── validate.py        # Multi-layer DOCX/OMML validator
├── tests/                 # pytest suite (8 test files)
│   ├── helpers.py         # Synthetic DOCX builder, fake XSL, OMML template
│   ├── test_cli.py, test_core.py, test_docx.py, test_formula.py
│   ├── test_omml.py, test_skill.py, test_update.py, test_validate.py
├── docs/
│   ├── formula-syntax.md  # Complete grammar reference, preprocessing, MathML mapping
│   └── workflow.md        # Install, scan/review/apply cycle, CI usage, troubleshooting
├── skills/mathfmt/        # Claude Code skill
│   ├── SKILL.md           # Skill workflow instructions
│   ├── agents/openai.yaml # Agent interface
│   └── references/paper-notation.md  # Design conventions
├── examples/
│   └── README.md          # New-user walkthrough: test doc → scan → apply
├── ROADMAP.md             # Phased version plan (v0.2.x → v1.0.0)
├── .github/workflows/
│   ├── ci.yml             # CI: 3 OS × 4 Python, pytest, ruff, coverage, packaging
│   └── publish.yml        # CD: tag → PyPI + GitHub Release
├── .claude/
│   ├── memory.md          # Project lessons learned (5 items)
│   └── settings.local.json
├── pyproject.toml         # Build config, metadata, tool settings
├── CHANGELOG.md
├── CONTRIBUTING.md
└── README.md              # Bilingual (zh/en) overview
```

---

## Architecture — Module Responsibilities

### `core.py` — The engine (~950 lines)
The heart of the project. Data flow:
1. **Preprocessing** — derivative normalization (`ds/dt` → Leibniz form), Unicode sub/superscript → ASCII, operator aliases
2. **Tokenization** — regex-based lexer
3. **Parsing** — recursive-descent parser following the BNF grammar (see `docs/formula-syntax.md`)
4. **AST → MathML** — tree walker builds `<math>` element tree
5. **DOCX injection** — finds text runs matching formula spans, replaces with OMML markup, handles table multi-line splitting

Key functions exported via `__init__.py`:
- `scan_docx(docx_path)` → JSON-serializable candidate list with confidence scores
- `apply_docx(docx_path, candidates, output_path)` → writes new DOCX with OMML
- `formula_to_mathml(text)` → parse single formula → MathML string
- `mathml_to_omml(mathml)` → convert MathML → OMML (auto-selects backend)
- `find_xsl()` → locate Office MML2OMML.XSL if available

### `omml.py` — Built-in MathML→OMML converter
Pure Python, no Office required. Cross-platform default backend. Key function:
- `mathml_to_omml_py(mathml_elem)` → OMML element tree

### `cli.py` — Command-line interface
Six subcommands via `argparse`:
| Command | Purpose |
|---|---|
| `mathfmt scan` | Scan DOCX for formulas → JSON report |
| `mathfmt apply` | Apply reviewed candidates → output DOCX |
| `mathfmt convert` | One-step conservative conversion (scan + apply high-confidence only) |
| `mathfmt validate` | Multi-layer offline validation |
| `mathfmt doctor` | Environment diagnostics |
| `mathfmt update` | Check for newer version on PyPI |

### `validate.py` — Validator
Four validation layers:
1. ZIP package integrity
2. OMML structural checks
3. Formula coverage analysis
4. Cross-backend comparison (Python vs Office XSL)

### `update.py` — Self-update checker
- Polls GitHub Releases API
- SemVer 2.0 parsing
- 1-hour response caching

---

## Development Commands

All commands run from project root (`C:\Users\gml85\Desktop\MathFmt`).

```powershell
# Install in editable mode with dev deps
pip install -e ".[dev]"

# Run tests (coverage threshold: 85%)
pytest

# Lint (same as CI)
ruff check .

# Build distribution
python -m build

# Run CLI locally (editable install)
mathfmt doctor
mathfmt convert input.docx -o output.docx
```

**Pytest notes:**
- Markers: `native_xsl` tests require Microsoft Office — skip on non-Windows or non-Office machines
- Coverage: branch coverage, 85% threshold, HTML report in `htmlcov/`
- If `WinError 5` on Windows, use a fresh `--basetemp` (known issue, see `.claude/memory.md`)

---

## Coding Conventions

- **Line length:** 110 (configured in `pyproject.toml` `[tool.ruff]`)
- **Linter:** ruff with rules `F` (Pyflakes), `I` (isort), `UP` (pyupgrade)
- **Imports:** `from __future__ import annotations` at top of each module
- **Typing:** type hints used throughout, `collections.abc.Sequence` not `typing.Sequence`
- **Docstrings:** Google-style or concise single-line
- **Error handling:** library functions return structured results; CLI translates to exit codes (both must be correct — see memory.md lesson 4)
- **No `if __name__ == "__main__":`** in library code (excluded from coverage)
- **Package layout:** `src/` layout with `pyproject.toml` `[tool.setuptools.package-dir] = {"" = "src"}`

---

## Two OMML Backends

1. **Built-in Python** (`omml.py`) — default, cross-platform, no dependencies beyond lxml
2. **Microsoft Office XSL** — auto-detected on Windows via `find_xsl()`, uses `MML2OMML.XSL`

Backend selection is automatic; `mathml_to_omml()` tries Office XSL first, falls back to Python.

---

## CI/CD

- **CI** (`.github/workflows/ci.yml`): Triggers on push/PR to main. Matrix: Windows + Ubuntu + macOS × Python 3.10–3.13. Runs ruff → pytest → build check.
- **CD** (`.github/workflows/publish.yml`): Triggers on tag push `v*`. Builds → publishes to PyPI via Trusted Publishing → creates GitHub Release.

---

## Key Project Knowledge (from `.claude/memory.md`)

1. Windows pytest `--basetemp` can become undeletable after sandboxed runs → use fresh temp dir
2. Always run `ruff check .` before tagging a release
3. Option-sensitive caches must include the option in the cache key
4. Always test CLI exit code alongside error messages — displaying error + exit 0 breaks CI
5. Validate JSON cache root type before calling mapping methods

---

## Related Files

- Formula syntax reference: `docs/formula-syntax.md`
- User workflow guide: `docs/workflow.md`
- Examples walkthrough: `examples/README.md`
- Project roadmap: `ROADMAP.md`
- Design conventions: `skills/mathfmt/references/paper-notation.md`
- Claude Code skill: `skills/mathfmt/SKILL.md`
- Changelog: `CHANGELOG.md`
