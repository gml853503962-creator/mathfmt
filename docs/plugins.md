# Custom Formula Recognizers

MathFmt 1.0 can discover project-specific formula notation without patching the
core scanner. A recognizer sees one paragraph at a time and returns validated
`FormulaCandidate` spans whose `linear` value uses MathFmt's documented formula
syntax.

## Minimal plugin

Save this trusted module as `my_mathfmt_plugin.py` on `PYTHONPATH`:

```python
import re

from mathfmt import FormulaCandidate


class Recognizer:
    name = "project-calc"
    version = "1.0"

    def recognize(self, text: str):
        for match in re.finditer(r"calc\{(?P<name>[A-Za-z]+)\}", text):
            name = match.group("name")
            yield FormulaCandidate(
                start=match.start(),
                end=match.end(),
                source=match.group(),
                linear=f"{name}^2",
                confidence="high",
                confidence_reason="explicit project calc syntax",
                kind="square",
            )
```

Use it from the CLI:

```powershell
mathfmt scan input.docx --report candidates.json `
  --recognizer my_mathfmt_plugin:Recognizer

mathfmt convert input.docx --output output.docx `
  --recognizer my_mathfmt_plugin:Recognizer
```

`--recognizer` is repeatable. Classes are constructed without arguments; module
objects may also expose an existing recognizer instance.

## Python API

```python
from pathlib import Path

from mathfmt import load_recognizer, scan_docx

recognizer = load_recognizer("my_mathfmt_plugin:Recognizer")
report = scan_docx(
    Path("input.docx"),
    Path("candidates.json"),
    recognizers=[recognizer],
)
```

Applications may pass their own object implementing `FormulaRecognizer` directly.
No process-global registry is used, so concurrent scans can use different plugin
sets without leaking state.

## Validation rules

For every candidate:

- `0 <= start < end <= len(text)`;
- `source == text[start:end]`;
- `linear`, when supplied, is a non-empty string;
- `display`, `explicit`, and `chemistry` are booleans;
- `physics`, when supplied, is a non-empty string;
- `confidence` is `high`, `medium`, `low`, or omitted;
- `name`, optional `version`, and optional `kind` are non-empty strings.

Structurally invalid results and plugin exceptions raise `RecognizerError` and make
CLI commands exit non-zero. MathFmt parses `linear` during the normal scan phase:
an unparseable candidate is recorded with `parse_status: "review"` and remains
unselected instead of aborting the document scan. A high-confidence, parseable
candidate is selected automatically; medium and low confidence remain reviewable
but unselected by default.

## Deterministic conflict handling

1. Built-in MathFmt candidates always win an overlapping range.
2. Plugins run in the exact order supplied.
3. The first plugin candidate occupying a range wins later overlaps.
4. Duplicate recognizer names are rejected.

Scan reports record ordered plugin metadata under `profile.recognizers` and annotate
each result with `recognizer` and `recognizer_kind`. Conversion reports preserve the
same metadata, so automated pipelines can audit how a review was produced.

## Security

Loading `module:object` imports and executes Python code with the current user's
permissions. Use only plugins you trust and review them like any other dependency.
MathFmt validates returned data but cannot sandbox arbitrary Python code.
