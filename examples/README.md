# MathFmt Examples · 示例

This directory contains example workflows for MathFmt. If you're new to the tool,
start here.

---

## Prerequisites · 前提

- Python ≥ 3.10 installed
- MathFmt installed: `pip install mathfmt`
- A `.docx` file containing plain-text math formulas (see below)

## Preparing a Test Document · 准备测试文档

1. Open Microsoft Word, WPS Writer, or any editor that can save `.docx` files.
2. Type some formulas as plain text — for example:

   ```
   The quadratic formula is x = (-b +- sqrt(b^2 - 4ac)) / (2a).

   The derivative is ds(t)/dt and the second derivative is d^2s(t)/dt^2.

   We have the limit lim(x->0) sin(x)/x = 1.

   The integral is int(0, pi) sin(x) dx.
   ```

3. Save the file — e.g. `test.docx`.

> **Tip:** The [formula syntax reference](../docs/formula-syntax.md) lists every
> supported pattern.

## Basic Workflow · 基本流程

### 1. Check your environment

```bash
mathfmt doctor
```

Make sure you see `Ready: yes` and at least one OMML backend listed.

### 2. Scan for formulas

```bash
mathfmt scan test.docx --report candidates.json
```

This produces `candidates.json` — a list of detected formula spans with confidence scores.

### 3. Review candidates (optional but recommended)

Open `candidates.json` in a text editor and:
- Set `"selected"` to `false` for any false positives (non-math text flagged as formulas).
- Set `"selected"` to `true` for any formulas you want converted that were not auto-selected.
- Each candidate has a `confidence` field (`high` / `medium` / `low`) to guide your review.

### 4. Apply conversion

```bash
mathfmt apply test.docx --review candidates.json --output formatted.docx --report result.json
```

Open `formatted.docx` in Word — your plain-text formulas are now native OMML equations.

### One-step shortcut · 一键转换

If you trust the scanner's high-confidence results:

```bash
mathfmt convert test.docx --output formatted.docx
```

This runs scan + apply in a single step, auto-selecting only `high` confidence candidates.

## Using the Test Suite Documents · 使用测试套件文档

The project's test suite (`tests/`) generates synthetic `.docx` files programmatically.
You can use these as a reference for what MathFmt can handle:

```bash
# Run tests (generates temp DOCX files with embedded formulas)
pytest tests/ -k "test_docx" -v
```

These tests aren't shipped as static files, but the test code in `tests/helpers.py`
shows exactly how to construct DOCX files with plain-text formulas for MathFmt.

## Troubleshooting · 常见问题

| Problem | Likely cause | Try |
|---|---|---|
| `mathfmt: command not found` | Not installed or PATH issue | `pip install mathfmt` or use `python -m mathfmt` |
| No formulas detected | Formulas don't match recognized patterns | Check [syntax reference](../docs/formula-syntax.md) |
| Output DOCX looks the same | Opened in a viewer that doesn't support OMML | Open in Microsoft Word (desktop) |
| `doctor` shows no OMML backend | `lxml` not installed | `pip install lxml` |
