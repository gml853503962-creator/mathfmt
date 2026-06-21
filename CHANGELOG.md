# Changelog

All notable changes to MathFmt are documented here.

## [0.2.1] - 2026-06-21

### Added
- `mathfmt update` — checks GitHub Releases for newer versions and shows upgrade
  instructions. Supports `--check` (CI-friendly exit codes), `--pre` (pre-releases),
  and `--force` (bypass 1-hour cache).
- `mathfmt.update` public API: `check_for_updates()`, `UpdateInfo`, `fetch_latest_release()`.

### Fixed
- `--pre` cache isolated from stable checks — stale prerelease data won't leak
  into normal update queries, and vice versa.
- Network errors now set `error` field instead of silently reporting "up to date",
  so CI scripts using `--check` get an actionable message.
- Semver parser now strips pre-release suffixes (`-beta.1`, `-rc.2`) so version
  comparison yields correct results.
- Malformed cache files (missing keys) are treated as absent instead of raising
  `KeyError`.
- Validate report now emits the actual package version instead of a hardcoded
  `0.1.0` string.
- README version and build status badge updated to reflect v0.2.1.
- Five ruff lint errors resolved (unused imports, f-string without placeholders).

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
