# MathFmt Roadmap · 路线图

This document outlines planned work. Items are ordered by priority within each phase,
but timelines are best-effort — this is a single-maintainer project.

---

## v0.2.x — Documentation & Stability · 文档与稳定性

**Focus:** Make the project easier to discover, install, and trust.

- [x] v0.2.2 — CI/Ruff fixes, cache crash fix, exit code correction
- [x] v0.2.3 — Parser fixes (ellipsis, factorial, n-ary, 1(t), x_bar, C boundary); depth validation; docs & examples
- [x] Bilingual Quick Start in README (`pip install`, `doctor`, basic conversion)
- [x] `examples/` directory with a walkthrough for new users
- [x] `ROADMAP.md` (this file)
- [ ] Improve `mathfmt doctor` output — show versions of key dependencies
- [ ] Fix any crash-on-edge-input bugs reported by users
- [ ] Expand test coverage for boundary cases (empty runs, malformed XML, Unicode edge cases)
- [ ] Triage and fix issues labeled `bug` on GitHub

## v0.3.0 — Conversion Reports & Safety · 转换报告与安全

**Focus:** Give users confidence in automated conversion and visibility into what changed.

- [ ] **Conversion report** — after `apply`, generate a structured report (JSON + human-readable)
  showing exactly which text runs were replaced and with what OMML
- [ ] **Dry-run mode** — `mathfmt apply --dry-run` that previews changes without writing
- [ ] **Failed-formula warnings** — when a formula parses but produces degraded output,
  flag it in the report so users know to review it manually
- [ ] **Per-formula confidence in reports** — include individual confidence scores alongside
  each converted formula, not just aggregate stats
- [ ] **Better error messages** — when parsing fails, show _where_ in the formula the
  parser got stuck (column number, expected token)
- [ ] **`--strict` flag** — fail on any parse error instead of silently skipping (useful
  in CI pipelines)

## v0.4.0 — Formula Coverage · 公式覆盖

**Focus:** Handle more real-world formula patterns.

- [ ] Nested bracketed constructs: `{ ... }` for explicit grouping
- [ ] Multi-line equations and aligned environments (`align`, `cases`)
- [ ] Chemical formulas and reaction arrows
- [ ] Physics notation: bra-ket `⟨φ|ψ⟩`, tensor indices, partial derivatives `∂f/∂x`
- [ ] Improved Unicode symbol mapping
- [ ] User-extensible symbol aliases (e.g. custom shorthand → MathML)

## v0.5.0 — Compatibility & Integration · 兼容性与集成

**Focus:** Work well in more environments and toolchains.

- [ ] LaTeX input mode: `$...$` and `$$...$$` delimiters in DOCX text
- [ ] WPS Office compatibility testing (WPS Writer on Windows/Linux)
- [ ] LibreOffice Writer compatibility testing (ODT → DOCX roundtrip)
- [ ] Batch processing: `mathfmt convert ./folder/*.docx`
- [ ] GitHub Actions recipe in docs for CI integration

## v1.0.0 — Stable API · 稳定 API

**Focus:** Lock down the public API and establish long-term support.

- [ ] Stable Python API with deprecation policy
- [ ] Semantic versioning guarantees documented
- [ ] Plugin/hook system for custom formula recognizers
- [ ] Performance benchmarks and optimization for large documents (100+ pages)

---

## How to Influence This Roadmap · 如何影响路线图

- **:+1: reactions** on GitHub issues help prioritize.
- **Feature requests** with real-world formula examples are much more persuasive than
  abstract suggestions.
- **Pull requests** are welcome — please open an issue first to discuss approach for
  anything beyond a bug fix.

## Versioning Policy · 版本策略

MathFmt follows [Semantic Versioning 2.0](https://semver.org/):

- **Patch** (0.2.x): bug fixes, doc updates, internal refactors — safe to upgrade
- **Minor** (0.x.0): new features, new formula support, new CLI flags — may change
  default behavior slightly
- **Major** (1.0.0): stable API with deprecation notices for breaking changes

Pre-1.0, breaking changes may occur in minor versions but will be noted in the changelog.
