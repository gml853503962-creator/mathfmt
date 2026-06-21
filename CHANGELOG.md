# Changelog

All notable changes to MathFmt are documented here.

## [Unreleased]

### Added
- Built-in pure-Python OMML generator (`src/mathfmt/omml.py`) — no Microsoft Office or
  `MML2OMML.XSL` required. Works on Windows, macOS, and Linux.
- `mathfmt validate` command — offline DOCX structure and OMML correctness checks with
  four-layer validation (package integrity, OMML structure, formula coverage, cross-backend).
- `mathfmt doctor` now reports `backend: python` (default) or `backend: office-xsl`.
- `apply` and `convert` commands no longer require `--xsl`; the Python backend is used
  automatically when Office is not detected.

### Changed
- `mathfmt_to_omml` now dispatches to XSL or Python backend based on availability.
- `apply_docx(xsl_path)` parameter is now optional (`None` = Python backend).
- Compatibility matrix updated: all platforms supported for OMML output.

### Documentation
- Added `docs/formula-syntax.md` — complete reference covering all preprocessing rules,
  token types, BNF grammar, MathML output mapping, scanning heuristics, known limitations,
  and error handling.
- Added `docs/workflow.md` — step-by-step guide for installation, review-first and one-step
  workflows, report interpretation, table/header/footer handling, CI usage, and troubleshooting.
- Expanded `README.md` with 12 quick examples, OS×Python×Office compatibility matrix, alpha
  status notice, version roadmap (v0.2 / v0.3 / v1.0), and maintenance policy.

### Testing
- Added 8 `pytest.mark.xfail` tests for known v0.1 limitations (integral, summation, matrix,
  vector, piecewise, subscript limit, anchor-less scanning, cross-paragraph formulas).
- Fixed stale `.pytest_cache` permission error by setting `--basetemp=.pytest_tmp`.

## [0.1.0] - 2026-06-21

- Added review-first `scan` and `apply` commands.
- Added conservative `convert` and environment `doctor` commands.
- Added native Word equation output for DOCX body text, tables, headers, and footers.
- Added Codex Skill, tests, bilingual documentation, and release automation.
