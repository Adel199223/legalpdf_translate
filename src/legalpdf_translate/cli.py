"""Command-line interface for LegalPDF Translate."""

from __future__ import annotations

import argparse
import getpass
import sys
from datetime import datetime
from pathlib import Path

from .checkpoint import (
    bool_from_text,
    parse_effort,
    parse_image_mode,
    parse_ocr_engine_policy,
    parse_ocr_mode,
)
from .output_paths import require_writable_output_dir_text
from .secrets_store import (
    delete_openai_key,
    delete_ocr_key,
    get_openai_key,
    get_ocr_key,
    set_openai_key,
    set_ocr_key,
)
from .types import RunConfig, TargetLang
from .workflow import TranslationWorkflow


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_lang(value: str) -> TargetLang:
    upper = value.strip().upper()
    if upper == TargetLang.EN.value:
        return TargetLang.EN
    if upper == TargetLang.FR.value:
        return TargetLang.FR
    if upper == TargetLang.AR.value:
        return TargetLang.AR
    raise argparse.ArgumentTypeError("lang must be EN, FR, or AR")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="legalpdf-translate")
    parser.add_argument("--pdf", help="Path to input PDF file.")
    parser.add_argument("--lang", type=_parse_lang, help="Target language: EN|FR|AR.")
    parser.add_argument("--outdir", help="Output folder path.")
    parser.add_argument("--effort", default="high", choices=["high", "xhigh"], help="Reasoning effort.")
    parser.add_argument("--images", default="auto", choices=["off", "auto", "always"], help="Image mode.")
    parser.add_argument("--max-pages", type=int, default=None, help="Optional maximum pages to translate.")
    parser.add_argument("--resume", default="true", help="Resume from checkpoints: true|false.")
    parser.add_argument("--page-breaks", default="true", help="Insert page breaks: true|false.")
    parser.add_argument(
        "--keep-intermediates",
        default="true",
        help="Keep pages/images in run folder for resume/rebuild: true|false.",
    )
    parser.add_argument(
        "--context-file",
        default="",
        help="Optional context file path; empty string disables context.",
    )
    parser.add_argument(
        "--rebuild-docx",
        action="store_true",
        help="Rebuild DOCX from existing run_dir/pages without API calls.",
    )
    parser.add_argument("--ocr-mode", default="auto", choices=["off", "auto", "always"], help="OCR mode.")
    parser.add_argument(
        "--ocr-engine",
        default="local_then_api",
        choices=["local", "local_then_api", "api"],
        help="OCR engine routing.",
    )
    parser.add_argument("--ocr-api-base-url", default="", help="Optional OCR API base URL.")
    parser.add_argument("--ocr-api-model", default="", help="Optional OCR API model.")
    parser.add_argument("--ocr-api-key-env", default="DEEPSEEK_API_KEY", help="Environment variable for OCR API key.")
    parser.add_argument("--set-openai-key", action="store_true", help="Store OpenAI API key securely.")
    parser.add_argument("--clear-openai-key", action="store_true", help="Delete stored OpenAI API key.")
    parser.add_argument("--set-ocr-key", action="store_true", help="Store OCR API key securely.")
    parser.add_argument("--clear-ocr-key", action="store_true", help="Delete stored OCR API key.")
    return parser


def _handle_key_commands(args: argparse.Namespace) -> int | None:
    requested = [
        bool(args.set_openai_key),
        bool(args.clear_openai_key),
        bool(args.set_ocr_key),
        bool(args.clear_ocr_key),
    ]
    if sum(1 for value in requested if value) == 0:
        return None
    if sum(1 for value in requested if value) > 1:
        print(f"[{_timestamp()}] Key command error: choose only one key-management flag.", file=sys.stderr)
        return 1

    try:
        if args.set_openai_key:
            key_value = getpass.getpass("Enter OpenAI API key: ").strip()
            if not key_value:
                print(f"[{_timestamp()}] Key command error: key cannot be empty.", file=sys.stderr)
                return 1
            set_openai_key(key_value)
            if not get_openai_key():
                print(f"[{_timestamp()}] Key command error: failed to verify saved key.", file=sys.stderr)
                return 1
            print(f"[{_timestamp()}] OpenAI API key saved.")
            return 0
        if args.clear_openai_key:
            delete_openai_key()
            print(f"[{_timestamp()}] OpenAI API key cleared.")
            return 0
        if args.set_ocr_key:
            key_value = getpass.getpass("Enter OCR API key: ").strip()
            if not key_value:
                print(f"[{_timestamp()}] Key command error: key cannot be empty.", file=sys.stderr)
                return 1
            set_ocr_key(key_value)
            if not get_ocr_key():
                print(f"[{_timestamp()}] Key command error: failed to verify saved key.", file=sys.stderr)
                return 1
            print(f"[{_timestamp()}] OCR API key saved.")
            return 0
        if args.clear_ocr_key:
            delete_ocr_key()
            print(f"[{_timestamp()}] OCR API key cleared.")
            return 0
    except RuntimeError as exc:
        print(f"[{_timestamp()}] Key command error: {exc}", file=sys.stderr)
        return 1

    return None


def _validate_required_run_args(args: argparse.Namespace) -> tuple[str, TargetLang, str]:
    if not args.pdf:
        raise ValueError("Missing required argument: --pdf")
    if args.lang is None:
        raise ValueError("Missing required argument: --lang")
    if not args.outdir:
        raise ValueError("Missing required argument: --outdir")
    return args.pdf, args.lang, args.outdir


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    key_command_result = _handle_key_commands(args)
    if key_command_result is not None:
        return key_command_result

    try:
        pdf_arg, lang_arg, outdir_arg = _validate_required_run_args(args)
        outdir_abs = require_writable_output_dir_text(outdir_arg)
        config = RunConfig(
            pdf_path=Path(pdf_arg).resolve(),
            output_dir=outdir_abs,
            target_lang=lang_arg,
            effort=parse_effort(args.effort),
            image_mode=parse_image_mode(args.images),
            max_pages=args.max_pages,
            resume=bool_from_text(args.resume),
            page_breaks=bool_from_text(args.page_breaks),
            keep_intermediates=bool_from_text(args.keep_intermediates),
            ocr_mode=parse_ocr_mode(args.ocr_mode),
            ocr_engine=parse_ocr_engine_policy(args.ocr_engine),
            ocr_api_base_url=args.ocr_api_base_url.strip() or None,
            ocr_api_model=args.ocr_api_model.strip() or None,
            ocr_api_key_env_name=args.ocr_api_key_env.strip() or "DEEPSEEK_API_KEY",
            context_file=Path(args.context_file).resolve() if args.context_file.strip() != "" else None,
            context_text=None,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[{_timestamp()}] Config error: {exc}", file=sys.stderr)
        return 1

    def log_callback(message: str) -> None:
        print(f"[{_timestamp()}] {message}")

    def progress_callback(page: int, total: int, status: str) -> None:
        print(f"[{_timestamp()}] page={page}/{total} status={status}")

    workflow = TranslationWorkflow(log_callback=log_callback, progress_callback=progress_callback)

    if args.rebuild_docx:
        try:
            rebuilt_path = workflow.rebuild_docx(config)
        except (FileNotFoundError, ValueError) as exc:
            print(f"[{_timestamp()}] Rebuild error: {exc}", file=sys.stderr)
            return 1
        except Exception as exc:  # noqa: BLE001
            print(f"[{_timestamp()}] Rebuild runtime error: {exc}", file=sys.stderr)
            return 2
        print(f"[{_timestamp()}] Saved DOCX: {rebuilt_path}")
        return 0

    try:
        summary = workflow.run(config)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[{_timestamp()}] Input/config error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"[{_timestamp()}] Runtime error: {exc}", file=sys.stderr)
        return 2

    if summary.success and summary.output_docx is not None:
        print(f"[{_timestamp()}] Saved DOCX: {summary.output_docx}")
        return 0

    if summary.partial_docx is not None:
        print(f"[{_timestamp()}] Partial export: {summary.partial_docx}")
    if summary.error == "docx_write_failed" and summary.attempted_output_docx is not None:
        print(
            f"[{_timestamp()}] DOCX save failed at: {summary.attempted_output_docx}",
            file=sys.stderr,
        )
    print(f"[{_timestamp()}] Failed: {summary.error}; failed_page={summary.failed_page}", file=sys.stderr)
    return summary.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
