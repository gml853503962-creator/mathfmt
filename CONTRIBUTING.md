# Contributing

Thank you for helping improve MathFmt.

1. Open an issue before large behavioral changes.
2. Create a focused branch and keep source documents private.
3. Install development dependencies with `python -m pip install -e ".[dev]"`.
4. Run `ruff check .`, `ruff format --check .`, and `pytest` before submitting a pull request.
5. Add synthetic fixtures and tests for new notation or DOCX structures.
6. Changes to public exports or signatures must update `docs/api.md` and the API snapshot test.
7. Changes affecting scanning, conversion, validation, or OOXML traversal must pass
   `python benchmarks/benchmark_large_docx.py`.

Do not commit copyrighted, confidential, or personally identifying documents. Reproduce document
problems with the smallest synthetic fixture possible.
