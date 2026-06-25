# Reusable project lessons

- On Windows, a fixed pytest `--basetemp=.pytest_tmp` can become undeletable after an interrupted or sandboxed run. If setup errors report `WinError 5`, rerun with a fresh, uniquely named basetemp inside the workspace before treating failures or coverage drops as product defects.
- Before release/tagging, run the same `ruff check .` command used by CI; passing pytest and package builds does not imply the CI matrix will proceed past lint.
- Caches for option-sensitive remote checks (for example stable-only versus prerelease updates) must include the option in the cache key or cached payload validation.
- When adding an error field to a library result, also test the CLI exit code for that error path; displaying an error message while returning success still breaks CI callers.
- After decoding cache JSON, validate that the root value is a mapping and that required values have usable types before calling mapping methods or doing arithmetic.
- On Windows, isolated `python -m build` may fail while logging localized pip output with `UnicodeDecodeError`; retry with `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`, and `python -m build --no-isolation` to verify packaging before treating it as a project build defect.
- When bumping MathFmt's current version for a release, update self-update tests so fake "newer release" fixtures are greater than the new current version; otherwise update detection tests will correctly report no update.
