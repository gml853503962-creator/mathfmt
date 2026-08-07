from __future__ import annotations

from pathlib import Path

from benchmarks.benchmark_large_docx import main, make_large_docx, run_benchmark


def test_large_docx_generator_and_workflow(tmp_path: Path) -> None:
    source = make_large_docx(tmp_path / "large.docx", pages=3, formulas_per_page=2)
    assert source.is_file()

    result = run_benchmark(pages=3, formulas_per_page=2)

    assert result["pages"] == 3
    assert result["candidates"] == 6
    assert result["converted"] == 6
    assert result["equations"] == 6
    assert result["valid"] is True
    assert result["wps_compatible"] is True


def test_benchmark_cli_writes_machine_readable_report(tmp_path: Path) -> None:
    report = tmp_path / "benchmark.json"
    code = main(
        [
            "--pages",
            "2",
            "--formulas-per-page",
            "1",
            "--max-scan-seconds",
            "30",
            "--max-apply-seconds",
            "30",
            "--max-validate-seconds",
            "30",
            "--max-peak-memory-mb",
            "512",
            "--json",
            str(report),
        ]
    )

    assert code == 0
    assert '"passed": true' in report.read_text(encoding="utf-8")
