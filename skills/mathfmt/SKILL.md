---
name: mathfmt
description: Typeset plain-text formulas in Word DOCX documents as native paper-style Word equations. Use for requests to fix awkward formula symbols, convert typed math into textbook or exam formatting, normalize derivatives and control-system notation, or review formula candidates in DOCX files.
---

# MathFmt

Convert plain-text formulas to native Word OMML equations with the installed `mathfmt` CLI. Preserve
the source document and inspect the rendered result.

## Workflow

1. Run `mathfmt doctor` and resolve a missing `MML2OMML.XSL` with `--xsl PATH`.
2. Use `mathfmt convert input.docx` only when conservative automatic selection is appropriate.
3. For mixed technical prose, run `mathfmt scan input.docx --report candidates.json`, review the JSON,
   then run `mathfmt apply input.docx --review candidates.json --output output.docx --report result.json`.
4. Keep code, image formulas, and existing native Word equations unchanged.
5. Inspect the result report and render every output page before delivery.

Read `references/paper-notation.md` when reviewing notation or correcting a candidate's `linear` value.

## Safety

- Never use the input path as the output path.
- Prefer the review-first flow when prose may resemble formulas.
- Treat skipped candidates as unresolved work and report them.
- Deliver only the final DOCX unless QA artifacts are requested.
