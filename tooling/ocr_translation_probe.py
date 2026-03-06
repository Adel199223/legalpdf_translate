"""Small-slice OCR-heavy translation probe helper."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[0]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from ocr_preflight import run_ocr_preflight

from legalpdf_translate.pdf_text_order import extract_ordered_page_text, get_page_count
from legalpdf_translate.types import EffortPolicy, ImageMode, OcrEnginePolicy, OcrMode, ReasoningEffort, RunConfig, TargetLang
from legalpdf_translate.user_settings import load_gui_settings
from legalpdf_translate.workflow import TranslationWorkflow


def parse_pages_spec(spec: str, *, page_count: int | None = None) -> list[int]:
    text = spec.strip()
    if text == "":
        raise ValueError("Page spec cannot be blank.")
    pages: list[int] = []
    seen: set[int] = set()
    for chunk in text.split(","):
        part = chunk.strip()
        if part == "":
            continue
        if "-" in part:
            start_text, end_text = [item.strip() for item in part.split("-", 1)]
            start = int(start_text)
            end = int(end_text)
            if start <= 0 or end <= 0 or end < start:
                raise ValueError(f"Invalid page range: {part}")
            values = range(start, end + 1)
        else:
            value = int(part)
            if value <= 0:
                raise ValueError(f"Invalid page number: {part}")
            values = (value,)
        for value in values:
            if page_count is not None and value > page_count:
                raise ValueError(f"Page {value} exceeds page count {page_count}.")
            if value not in seen:
                seen.add(value)
                pages.append(value)
    if not pages:
        raise ValueError("No pages resolved from page spec.")
    return pages


def build_safe_probe_config(
    *,
    pdf_path: Path,
    outdir: Path,
    lang: TargetLang,
    pages: list[int],
    settings: dict[str, object],
) -> RunConfig:
    return RunConfig(
        pdf_path=pdf_path,
        output_dir=outdir,
        target_lang=lang,
        effort=ReasoningEffort.HIGH,
        image_mode=ImageMode.OFF,
        start_page=min(pages),
        end_page=max(pages),
        workers=1,
        resume=False,
        keep_intermediates=True,
        ocr_mode=OcrMode.ALWAYS,
        ocr_engine=OcrEnginePolicy.API,
        ocr_api_base_url=str(settings.get("ocr_api_base_url", "") or "").strip() or None,
        ocr_api_model=str(settings.get("ocr_api_model", "") or "").strip() or None,
        ocr_api_key_env_name=str(
            settings.get("ocr_api_key_env_name", settings.get("ocr_api_key_env", "DEEPSEEK_API_KEY")) or "DEEPSEEK_API_KEY"
        ).strip()
        or "DEEPSEEK_API_KEY",
        effort_policy=EffortPolicy.FIXED_HIGH,
    )


def _build_recommended_args(config: RunConfig) -> list[str]:
    return [
        "--pdf",
        str(config.pdf_path),
        "--lang",
        config.target_lang.value,
        "--outdir",
        str(config.output_dir),
        "--ocr-mode",
        config.ocr_mode.value,
        "--ocr-engine",
        config.ocr_engine.value,
        "--image-mode",
        config.image_mode.value,
        "--workers",
        str(config.workers),
        "--effort-policy",
        config.effort_policy.value,
        "--resume",
        "false",
        "--keep-intermediates",
        "true",
        "--start-page",
        str(config.start_page),
        "--end-page",
        str(config.end_page),
    ]


def inspect_pdf_for_probe(pdf_path: Path, pages: list[int]) -> dict[str, Any]:
    page_count = int(get_page_count(pdf_path))
    first_page = pages[0]
    ordered = extract_ordered_page_text(pdf_path, first_page - 1)
    text = str(ordered.text or "")
    return {
        "page_count": page_count,
        "first_selected_page": first_page,
        "direct_text_char_count": len(text.strip()),
        "direct_extraction_failed": bool(ordered.extraction_failed),
        "direct_fragmented": bool(ordered.fragmented),
        "direct_text_preview": text.strip()[:240],
    }


def collect_probe_packet(
    *,
    pdf_path: Path,
    lang: TargetLang,
    outdir: Path,
    pages: list[int],
    run_workflow: bool,
    environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    env = environment if environment is not None else dict(os.environ)
    settings = load_gui_settings()
    preflight = run_ocr_preflight(environment=env)
    config = build_safe_probe_config(
        pdf_path=pdf_path,
        outdir=outdir,
        lang=lang,
        pages=pages,
        settings=settings,
    )
    inspection = inspect_pdf_for_probe(pdf_path, pages)
    packet: dict[str, Any] = {
        "tool": "ocr_translation_probe",
        "pdf_path": str(pdf_path.resolve()),
        "selected_pages": pages,
        "inspection": inspection,
        "preflight": preflight,
        "recommended_settings": {
            "ocr_mode": config.ocr_mode.value,
            "ocr_engine": config.ocr_engine.value,
            "image_mode": config.image_mode.value,
            "workers": config.workers,
            "effort_policy": config.effort_policy.value,
            "resume": config.resume,
            "keep_intermediates": config.keep_intermediates,
        },
        "recommended_cli_args": _build_recommended_args(config),
        "workflow_probe": None,
    }

    if run_workflow:
        summary = TranslationWorkflow().run(config)
        packet["workflow_probe"] = {
            "success": bool(summary.success),
            "exit_code": int(summary.exit_code),
            "error": summary.error,
            "completed_pages": int(summary.completed_pages),
            "run_dir": str(summary.run_dir),
            "run_summary_path": str(summary.run_summary_path) if summary.run_summary_path is not None else "",
        }

    return packet


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a small-slice OCR-heavy translation probe.")
    parser.add_argument("--pdf", type=Path, required=True, help="PDF to inspect or probe.")
    parser.add_argument("--lang", choices=["EN", "FR", "AR"], required=True, help="Target language.")
    parser.add_argument(
        "--pages",
        default="1-2",
        help="Page slice to inspect or probe. Examples: 1-2, 3, 5-7.",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=REPO_ROOT / "tmp_ocr_probe",
        help="Output directory used when workflow probe mode is enabled.",
    )
    parser.add_argument(
        "--run-workflow",
        action="store_true",
        help="Run a real workflow slice with locked safe settings instead of inspection only.",
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=None,
        help="Optional path to write the JSON packet.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    pdf_path = args.pdf.expanduser().resolve()
    page_count = int(get_page_count(pdf_path))
    pages = parse_pages_spec(str(args.pages), page_count=page_count)
    packet = collect_probe_packet(
        pdf_path=pdf_path,
        lang=TargetLang(str(args.lang).upper()),
        outdir=args.outdir.expanduser().resolve(),
        pages=pages,
        run_workflow=bool(args.run_workflow),
    )
    payload = json.dumps(packet, ensure_ascii=False, indent=2)
    if args.out_json is not None:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(payload, encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
