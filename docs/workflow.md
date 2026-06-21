# Workflow Guide

How to use MathFmt from installation to a finished document.

---

## 1. Install and Verify

```powershell
pip install mathfmt
mathfmt doctor
```

`doctor` checks:

- Python version
- Platform
- `lxml` availability
- Whether `MML2OMML.XSL` is found in the standard Office paths

If `MML2OMML.XSL` is not found, point to it explicitly:

```powershell
mathfmt doctor --xsl "C:\Program Files\Microsoft Office\root\Office16\MML2OMML.XSL"
```

All commands that need the stylesheet (`apply`, `convert`) accept `--xsl`.

---

## 2. Review-First Workflow (Recommended)

For documents with mixed technical prose, code, images, and formulas:

### Step 1 — Scan

```powershell
mathfmt scan document.docx --report candidates.json
```

This produces `candidates.json` containing every detected formula candidate:

```json
{
  "schema_version": 1,
  "input": "C:\\path\\to\\document.docx",
  "profile": {
    "derivatives": "fraction",
    "unit_step": "u(t)",
    "output": "native_word_omml"
  },
  "summary": {
    "paragraphs": 42,
    "candidates": 15,
    "existing_equations": 3,
    "drawing_paragraphs": 2,
    "code_paragraphs": 8
  },
  "candidates": [
    {
      "id": "f0001",
      "selected": true,
      "part": "word/document.xml",
      "paragraph_index": 3,
      "start": 10,
      "end": 20,
      "source": "x^2 + 1 = 2",
      "linear": "x^2 + 1 = 2",
      "display": false,
      "paragraph_text": "Inline: x^2 + 1 = 2 and more text.",
      "parse_status": "ok"
    }
  ]
}
```

### Step 2 — Review

Open `candidates.json` and for each candidate:

| Field | What to check |
|---|---|
| `source` | The original text from the DOCX |
| `linear` | The formula string that will be parsed (edit this to fix notation, e.g. change `p1,2` to `p1, p2` if you prefer comma-separated subscripts) |
| `selected` | Set to `true` to convert, `false` to skip |
| `parse_status` | `"ok"` = parsable; `"review"` = failed, check `parse_error` |

Common review actions:

- **False positive** (prose misidentified as formula): set `"selected": false`.
- **Notation fix**: edit the `linear` field. For example, if the source is `s'(t) + s''(t)` and you want both derivatives, keep it as-is. If you want only first-order, shorten it.
- **Parse failure**: read `parse_error`, adjust `linear`, re-run `scan` to verify.

### Step 3 — Apply

```powershell
mathfmt apply document.docx --review candidates.json --output result.docx --report result.json
```

This writes `result.docx` with native Word equations and `result.json` with conversion statistics:

```json
{
  "converted_count": 12,
  "skipped_count": 3,
  "converted": [
    {"id": "f0001", "source": "x^2 + 1 = 2", "part": "word/document.xml", "lines": 1}
  ],
  "skipped": [
    {"id": "f0005", "source": "…", "error": "Reviewed source no longer matches the paragraph span"}
  ]
}
```

Check `skipped` entries for errors. A non-zero skip count produces exit code 2.

### Step 4 — Verify

Open `result.docx` in Word and inspect:
- Each converted formula renders as a native equation
- Surrounding text is intact
- Tables, headers, and footers are correct
- Code blocks remain as plain text

---

## 3. One-Step Conversion

For documents where most candidates are likely formulas (e.g., all-math problem sets):

```powershell
mathfmt convert input.docx
```

This runs `scan` + `apply` internally, producing:

- `input.mathfmt.docx` — the converted document
- `input.mathfmt.report.json` — the conversion report

Custom output paths:

```powershell
mathfmt convert input.docx --output final.docx --report conversion.json
```

**Important**: `convert` uses default `selected: true` for all parseable candidates. It does not apply human judgment. If your document has prose that resembles formulas, use `scan` + `apply` instead.

**Safety**: `convert` never overwrites the input file. The output name always differs from the input name.

---

## 4. Understanding the Report

### Scan report (`candidates.json`)

| Field | Meaning |
|---|---|
| `summary.paragraphs` | Total paragraphs scanned |
| `summary.candidates` | Formulas found |
| `summary.existing_equations` | Paragraphs that already contain native Word equations (skipped) |
| `summary.drawing_paragraphs` | Paragraphs containing images or drawings (skipped) |
| `summary.code_paragraphs` | Paragraphs identified as code (skipped) |
| `candidates[].display` | `true` if the formula fills the entire paragraph (renders as display equation) |
| `candidates[].parse_status` | `"ok"` or `"review"` (see above) |

### Apply report (`result.json`)

| Field | Meaning |
|---|---|
| `converted_count` | Formulas successfully converted |
| `skipped_count` | Formulas that could not be converted |
| `converted[].lines` | Number of equation lines (1 normally; >1 for split long table formulas) |
| `skipped[].error` | Reason for skipping |

---

## 5. Working with Tables

Formulas in table cells are automatically detected and rendered with reduced font size.

Long formulas that exceed the column width are split at top-level `+`/`-` operators into multiple lines. This is applied when:

- The paragraph is inside a table cell (`w:tc`)
- The formula covers the entire paragraph
- The estimated formula width (accounting for derivative expansion) exceeds the threshold

The split logic respects bracket nesting — it will not break inside `(...)`, `[...]`, or `{...}`.

---

## 6. Headers and Footers

MathFmt scans `word/header*.xml` and `word/footer*.xml` in addition to the document body. Formulas in headers and footers are converted the same way as body text formulas.

---

## 7. CI / Headless Use

MathFmt can run without a display:

```powershell
# In CI, point to the XSL file explicitly
mathfmt convert input.docx --xsl "C:\path\to\MML2OMML.XSL"

# Or run scan-only (no XSL needed)
mathfmt scan input.docx --report candidates.json
```

The `doctor --json` output is machine-readable:

```json
{"mathfmt": "0.1.0", "python": "3.12.0", "platform": "Windows-10-...", "windows": true, "lxml": [5, 3, 0], "xsl": "C:\\...\\MML2OMML.XSL", "ready": true}
```

---

## 8. Troubleshooting

| Problem | Solution |
|---|---|
| `MML2OMML.XSL was not found` | Install Microsoft Office, or use `--xsl` to point to the file directly |
| `Refusing to overwrite the input DOCX` | MathFmt never overwrites the source; choose a different `--output` path |
| `Input must be a .docx file` | MathFmt only handles `.docx` (Office Open XML); convert older `.doc` files first |
| Formula not detected | Check whether it contains an anchor operator (`=`, `≠`, `<=`, `>=`, `!=`, `→`, `->`, `±`, `+/-`, `√`, `sqrt`, `lim`). If not, the scanner will miss it |
| `parse_status: "review"` | The formula couldn't be parsed. Edit `linear` in the candidate report, or set `selected: false` |
| Table formula is cut off | The formula may be too long even after splitting. Shorten the `linear` text or split it manually into multiple paragraphs |
| `hyperlink` in skipped error | The formula is inside a hyperlink. Move it outside the `w:hyperlink` element in the DOCX |
