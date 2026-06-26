# Changelog

All notable changes to MathFmt are documented here.

## [Unreleased]

### Added
- LaTeX-style DOCX text delimiters: `$...$` scans as a high-confidence inline
  formula, and `$$...$$` scans as a high-confidence display formula.
- Scan reports now include `explicit: true` for delimiter-detected formulas while
  preserving delimiter text in `source` and parsing delimiter-free `linear`.

### Fixed
- Validation coverage now parses reviewed candidates through `linear` when present,
  so delimiter-detected formulas validate consistently with `apply`.

## [0.3.0] - 2026-06-25

### Added
- v3 conversion/validation report metadata: `schema_version`, `report_type`, `command`,
  `inputs`, `outputs`, `options`, `summary`, and per-formula `formulas`.
- `mathfmt apply --dry-run` previews reviewed conversions and writes a report without
  writing a DOCX output file.
- `mathfmt apply --strict` and `mathfmt convert --strict` block DOCX output when any
  selected formula fails or is skipped.
- Structured parser error details in scan, apply, and validation reports: column,
  nearby context, expected token, and found token when available.
- Per-formula warnings for selected formulas that fail or are skipped during apply.

## [0.2.3] - 2026-06-22

### Fixed
- **Parser:** `...` (ellipsis) now tokenized as `…` — `1+2+...+n` parses without error.
- **Parser:** `n!` factorial added as postfix operator.
- **Parser:** `int(...)` / `sum(...)` / `prod(...)` now produce proper n-ary MathML
  (`munderover` for sum/prod, `msubsup` for integrals) with bounds and body, instead
  of being split as implicit multiplication.
- **Parser:** multi-letter identifiers (e.g. `x_bar`) now parse correctly; bar is no
  longer split into `b * a * r`.
- **Scanner:** single-letter `C` removed from French text-boundary rule, so
  `sin(x) + C` is no longer truncated.
- **Scanner:** `1(t)` and `Γ(t)` (unit step) now detected by an exact pattern before
  the general heuristic scan.
- **Validator:** OMML nesting-depth limit raised from 8 to 32; only math-structure
  elements (`f`, `rad`, `sSup`, `sSub`, …) count toward depth, not container/run
  wrappers. Depth exceeding the limit is now a warning, not a hard validation error.

### Documentation
- Bilingual Quick Start section added to README (`pip install`, `doctor`, `convert`).
- `examples/README.md` — step-by-step walkthrough for new users.
- `ROADMAP.md` — phased version plan from v0.2.x through v1.0.0.
- `CLAUDE.md` — comprehensive project reference for Claude Code (fixed several
  factual inaccuracies: API count, function signatures, CI matrix shape, backend
  default, `--output` flag).
- `tests/acceptance/` — 5 real-world test DOCX files with generator script.
- `convert` command examples now use `--output` instead of the non-existent `-o`.
- `apply` command examples now include the required `--report` flag.
- `doctor` output description and candidate review instructions corrected.

### Tests
- 5 new regression tests covering ellipsis, factorial, indefinite integral `+C`,
  step function detection, and deeply nested standard-deviation formula.
- Acceptance test pipeline: scan → convert → validate on 5 real-world DOCX files.

## [0.2.2] - 2026-06-21

### Fixed
- Ruff/CI errors resolved (unused imports, f-string without placeholders, import order).
- Stable and pre-release update caches are now isolated — running `--pre` no longer
  poisons the normal update check, and vice versa.
- SemVer pre-release labels (`alpha`, `beta`, `rc`) are now compared correctly per
  SemVer 2.0 — a stable release sorts after any pre-release with the same base.
- Network failures during `mathfmt update` now exit with code 2 instead of 0,
  so CI scripts can distinguish "up-to-date" from "could not check."
- Malformed cache files (JSON arrays, primitives, missing keys) no longer crash
  `_load_cache`.
- `mathfmt validate` now reports the actual installed version instead of a
  hardcoded string.
- README version roadmaps (Chinese and English) reflect actual release dates.
- Maintainer email `gml853503962@gmail.com` added to package metadata.

## [0.2.1] - 2026-06-21

### Added
- `mathfmt update` — checks GitHub Releases for newer versions and shows upgrade
  instructions. Supports `--check` (CI-friendly exit codes), `--pre` (pre-releases),
  and `--force` (bypass 1-hour cache).
- `mathfmt.update` public API: `check_for_updates()`, `UpdateInfo`, `fetch_latest_release()`.

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
