# Performance and Large-Document Gate

MathFmt 1.0 includes a reproducible 100-page performance benchmark rather than an
informal timing claim.

## Workload

`benchmarks/benchmark_large_docx.py` creates a valid, page-broken OOXML document with
100 pages and eight explicit formulas per page. It then executes the production
workflow:

1. scan 800 formula candidates;
2. convert all 800 in strict mode;
3. validate package structure, every equation, review coverage, and WPS portability;
4. confirm candidate, conversion, and equation counts; and
5. measure phase time and Python peak memory with `tracemalloc`.

Run the same gate locally:

```powershell
python benchmarks/benchmark_large_docx.py `
  --pages 100 `
  --formulas-per-page 8 `
  --max-scan-seconds 5 `
  --max-apply-seconds 5 `
  --max-validate-seconds 8 `
  --max-peak-memory-mb 256 `
  --json work/performance-v1.json
```

The CI job named **100-page performance gate** runs these limits on every push and
pull request and uploads its JSON result.

## v1.0 reference result

Windows, CPython 3.12, with memory tracing enabled:

| Metric | Result | CI limit |
|---|---:|---:|
| Scan | 1.126 s | 5 s |
| Apply | 1.334 s | 5 s |
| Validate | 2.752 s | 8 s |
| Total | 5.211 s | — |
| Peak Python memory | 5.901 MiB | 256 MiB |

Hardware and hosted-runner load vary, so these numbers are a reference rather than
a universal latency promise. The limits are deliberately above the reference result
but low enough to catch material regressions.

## Scaling design

Conversion groups reviewed candidates by OOXML part, parses each part once, modifies
all referenced paragraphs, and serializes once. Coverage validation likewise caches
paragraph text per part. This avoids reparsing a growing document once per formula,
which previously made large workflows approach quadratic time.
