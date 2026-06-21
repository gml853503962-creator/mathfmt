# Reusable project lessons

- On Windows, a fixed pytest `--basetemp=.pytest_tmp` can become undeletable after an interrupted or sandboxed run. If setup errors report `WinError 5`, rerun with a fresh, uniquely named basetemp inside the workspace before treating failures or coverage drops as product defects.
- Before release/tagging, run the same `ruff check .` command used by CI; passing pytest and package builds does not imply the CI matrix will proceed past lint.
- Caches for option-sensitive remote checks (for example stable-only versus prerelease updates) must include the option in the cache key or cached payload validation.
