from __future__ import annotations

import json
from pathlib import Path

import tooling.ocr_benchmark as ocr_benchmark
from legalpdf_translate.types import OcrApiProvider


def test_provider_cases_include_flash_and_flash_lite() -> None:
    cases = ocr_benchmark._provider_cases("all")
    assert (OcrApiProvider.GEMINI, "gemini-3.1-flash-lite-preview") in cases
    assert (OcrApiProvider.GEMINI, "gemini-3-flash-preview") in cases
    assert (OcrApiProvider.OPENAI, "gpt-4o-mini") in cases


def test_main_writes_json_payload(monkeypatch, tmp_path: Path, capsys) -> None:
    source = tmp_path / "scan.png"
    source.write_bytes(b"fake")
    out = tmp_path / "bench.json"

    monkeypatch.setattr(ocr_benchmark, "is_supported_source_file", lambda path: True)
    monkeypatch.setattr(ocr_benchmark, "source_type_label", lambda path: "image")
    monkeypatch.setattr(
        ocr_benchmark,
        "benchmark_one",
        lambda **kwargs: ocr_benchmark.BenchmarkResult(
            provider=kwargs["provider"].value,
            model=kwargs["model"],
            source_type="image",
            page=1,
            elapsed_seconds=1.25,
            chars=42,
            quality_score=0.75,
            failed_reason=None,
            case_entity="Juízo Local Criminal de Beja",
            case_city="Beja",
            case_number="109/26.0PBBJA",
            court_email="beja.judicial@tribunais.org.pt",
        ),
    )

    exit_code = ocr_benchmark.main([str(source), "--provider", "gemini", "--out", str(out)])

    assert exit_code == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["page"] == 1
    assert len(written["results"]) == 2
    stdout_payload = json.loads(capsys.readouterr().out)
    assert stdout_payload["results"][0]["provider"] == "gemini"
