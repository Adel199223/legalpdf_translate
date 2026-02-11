"""Command-line interface for LegalPDF Translate."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .checkpoint import bool_from_text, parse_effort, parse_image_mode
from .output_paths import require_writable_output_dir_text
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
    parser.add_argument("--pdf", required=True, help="Path to input PDF file.")
    parser.add_argument("--lang", required=True, type=_parse_lang, help="Target language: EN|FR|AR.")
    parser.add_argument("--outdir", required=True, help="Output folder path.")
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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        outdir_abs = require_writable_output_dir_text(args.outdir)
        config = RunConfig(
            pdf_path=Path(args.pdf).resolve(),
            output_dir=outdir_abs,
            target_lang=args.lang,
            effort=parse_effort(args.effort),
            image_mode=parse_image_mode(args.images),
            max_pages=args.max_pages,
            resume=bool_from_text(args.resume),
            page_breaks=bool_from_text(args.page_breaks),
            keep_intermediates=bool_from_text(args.keep_intermediates),
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
