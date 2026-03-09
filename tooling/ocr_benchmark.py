#!/usr/bin/env python3
"""Benchmark OCR providers/models on one PDF page or one standalone image."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from legalpdf_translate.metadata_autofill import extract_from_header_text
from legalpdf_translate.ocr_engine import (  # noqa: E402
    GEMINI_OCR_BENCHMARK_MODEL,
    OcrEngineConfig,
    build_ocr_engine,
    default_ocr_api_env_name,
    default_ocr_api_model,
)
from legalpdf_translate.source_document import (  # noqa: E402
    get_source_page_count,
    is_supported_source_file,
    ocr_source_page_text,
    source_type_label,
)
from legalpdf_translate.types import OcrApiProvider, OcrEnginePolicy, OcrMode  # noqa: E402
from legalpdf_translate.user_settings import load_joblog_settings  # noqa: E402


@dataclass(slots=True)
class BenchmarkResult:
    provider: str
    model: str
    source_type: str
    page: int
    elapsed_seconds: float
    chars: int
    quality_score: float
    failed_reason: str | None
    case_entity: str | None
    case_city: str | None
    case_number: str | None
    court_email: str | None


def _provider_cases(provider_arg: str) -> list[tuple[OcrApiProvider, str]]:
    cases: list[tuple[OcrApiProvider, str]] = []
    provider_text = provider_arg.strip().lower()
    if provider_text in {"openai", "all"}:
        cases.append((OcrApiProvider.OPENAI, default_ocr_api_model(OcrApiProvider.OPENAI)))
    if provider_text in {"gemini", "all"}:
        cases.append((OcrApiProvider.GEMINI, default_ocr_api_model(OcrApiProvider.GEMINI)))
        cases.append((OcrApiProvider.GEMINI, GEMINI_OCR_BENCHMARK_MODEL))
    return cases


def benchmark_one(
    *,
    source_path: Path,
    page_number: int,
    provider: OcrApiProvider,
    model: str,
    lang_hint: str | None,
) -> BenchmarkResult:
    config = OcrEngineConfig(
        policy=OcrEnginePolicy.API,
        api_provider=provider,
        api_model=model,
        api_key_env_name=default_ocr_api_env_name(provider),
    )
    engine = build_ocr_engine(config)
    started = time.perf_counter()
    result = ocr_source_page_text(
        source_path,
        page_number,
        OcrMode.ALWAYS,
        engine,
        lang_hint=lang_hint,
    )
    elapsed = time.perf_counter() - started
    settings = load_joblog_settings()
    suggestion = extract_from_header_text(
        result.text,
        vocab_cities=list(settings.get("vocab_cities", [])),
        ai_enabled=False,
    )
    return BenchmarkResult(
        provider=provider.value,
        model=model,
        source_type=source_type_label(source_path),
        page=page_number,
        elapsed_seconds=round(elapsed, 3),
        chars=result.chars,
        quality_score=result.quality_score,
        failed_reason=result.failed_reason,
        case_entity=suggestion.case_entity,
        case_city=suggestion.case_city,
        case_number=suggestion.case_number,
        court_email=suggestion.court_email,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ocr_benchmark.py")
    parser.add_argument("source", help="Path to source PDF or image.")
    parser.add_argument("--page", type=int, default=1, help="1-based page number for PDF sources (default: 1).")
    parser.add_argument("--provider", choices=["openai", "gemini", "all"], default="all")
    parser.add_argument("--lang-hint", default="", help="Optional OCR language hint.")
    parser.add_argument("--out", default="", help="Optional JSON output path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    source_path = Path(args.source).expanduser().resolve()
    if not source_path.exists():
        print(f"Source file not found: {source_path}", file=sys.stderr)
        return 1
    if not is_supported_source_file(source_path):
        print("Unsupported source file type. Use PDF or a supported image format.", file=sys.stderr)
        return 1
    page_number = max(1, int(args.page))
    if source_type_label(source_path) == "pdf":
        page_count = get_source_page_count(source_path)
        if page_number > page_count:
            print(f"Page {page_number} exceeds source page count {page_count}.", file=sys.stderr)
            return 1
    else:
        page_number = 1

    results: list[BenchmarkResult] = []
    for provider, model in _provider_cases(args.provider):
        try:
            results.append(
                benchmark_one(
                    source_path=source_path,
                    page_number=page_number,
                    provider=provider,
                    model=model,
                    lang_hint=args.lang_hint.strip() or None,
                )
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                BenchmarkResult(
                    provider=provider.value,
                    model=model,
                    source_type=source_type_label(source_path),
                    page=page_number,
                    elapsed_seconds=0.0,
                    chars=0,
                    quality_score=0.0,
                    failed_reason=str(exc),
                    case_entity=None,
                    case_city=None,
                    case_number=None,
                    court_email=None,
                )
            )

    payload = {"source": str(source_path), "page": page_number, "results": [asdict(row) for row in results]}
    if args.out.strip():
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
