# Changelog

All notable changes to MathFmt are documented here.

## [0.2.0] - 2026-06-21

### Added
- Built-in pure-Python OMML generator — no Microsoft Office or `MML2OMML.XSL` required.
  Works on Windows, macOS, and Linux.
- `mathfmt validate` — offline DOCX structure and OMML correctness checks (package
  integrity, OMML structure, formula coverage, cross-backend comparison).
- Confidence scoring (`high`/`medium`/`low`) on all scan candidates. Default `convert`
  only applies high-confidence formulas. `--confidence` flag on `convert`.
- Parser expansion: integrals (`∫`), summation (`∑`), matrices (`[[a,b],[c,d]]`),
  vectors (`[x,y,z]`), piecewise (`{0,x<0;1,x>=0}`), and subscript limit (`lim_{x→0}`).
- `doctor` now reports `backend: python` (default) or `backend: office-xsl`.
- `apply` and `convert` no longer require `--xsl`; Python backend used automatically.
- `.github/ISSUE_TEMPLATE/` with bug report and feature request templates.
- `SECURITY.md` now includes explicit 7-day response timeline.

### Changed
- `mathml_to_omml` dispatches to XSL or Python backend based on availability.
- `apply_docx(xsl_path)` is now optional (`None` = Python backend).
- `scan_docx` report upgraded to `schema_version: 2` with `confidence` fields.
- Roadmap now includes target dates (Q3 2026, Q4 2026, 2027).

### Documentation
- Added `docs/formula-syntax.md`, `docs/workflow.md`.
- Expanded `README.md` with 12 quick examples, compatibility matrix, and version roadmap.

## [0.1.0] - 2026-06-21

- Initial release: review-first `scan` and `apply`, conservative `convert`,
  environment `doctor`, native Word OMML output, Codex Skill, tests, bilingual docs.
