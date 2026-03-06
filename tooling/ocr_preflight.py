"""OCR environment preflight for reliability-stage gate packets."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from shutil import which
from typing import Any, Callable

CommandRunner = Callable[[list[str]], tuple[int, str, str]]
REQUIRED_LANGS = ("por", "eng", "fra", "ara")


def _default_runner(command: list[str]) -> tuple[int, str, str]:
    completed = subprocess.run(
        command,
        capture_output=True,
        check=False,
        text=True,
    )
    return completed.returncode, completed.stdout or "", completed.stderr or ""


def _first_line(value: str) -> str:
    for line in value.splitlines():
        cleaned = line.strip()
        if cleaned != "":
            return cleaned
    return ""


def _detect_tesseract(*, runner: CommandRunner) -> dict[str, Any]:
    tesseract_path = which("tesseract")
    if not tesseract_path:
        return {
            "available": False,
            "path": "",
            "version": "",
            "langs_available": [],
            "required_langs": {lang: False for lang in REQUIRED_LANGS},
            "required_langs_ready": False,
            "status": "unavailable",
        }

    version_code, version_stdout, version_stderr = runner(["tesseract", "--version"])
    version = _first_line(f"{version_stdout}\n{version_stderr}") if version_code == 0 else ""

    langs_code, langs_stdout, langs_stderr = runner(["tesseract", "--list-langs"])
    langs_raw = f"{langs_stdout}\n{langs_stderr}" if langs_code == 0 else ""
    langs_available: list[str] = []
    for line in langs_raw.splitlines():
        cleaned = line.strip().lower()
        if cleaned == "" or "list of available languages" in cleaned:
            continue
        if cleaned not in langs_available:
            langs_available.append(cleaned)

    required_langs = {lang: (lang in langs_available) for lang in REQUIRED_LANGS}
    required_langs_ready = all(required_langs.values())
    status = "available" if required_langs_ready else "degraded"
    return {
        "available": True,
        "path": tesseract_path,
        "version": version,
        "langs_available": langs_available,
        "required_langs": required_langs,
        "required_langs_ready": required_langs_ready,
        "status": status,
    }


def _detect_api_fallback(environment: dict[str, str]) -> dict[str, Any]:
    env_name = (environment.get("OCR_API_KEY_ENV_NAME", "") or "").strip() or "DEEPSEEK_API_KEY"
    env_present = (environment.get(env_name, "") or "").strip() != ""
    ignore_stored_key = (environment.get("OCR_PREFLIGHT_IGNORE_STORED_KEY", "") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    stored_present = False
    if not ignore_stored_key:
        try:
            repo_root = Path(__file__).resolve().parents[1]
            src_root = repo_root / "src"
            if str(src_root) not in sys.path:
                sys.path.insert(0, str(src_root))
            from legalpdf_translate.secrets_store import get_ocr_key  # noqa: PLC0415

            stored_present = bool((get_ocr_key() or "").strip())
        except Exception:
            stored_present = False

    key_source = "stored_key" if stored_present else ("env" if env_present else "none")
    return {
        "configured": bool(stored_present or env_present),
        "key_source": key_source,
        "key_env_name": env_name,
    }


def run_ocr_preflight(
    *,
    environment: dict[str, str] | None = None,
    runner: CommandRunner | None = None,
) -> dict[str, Any]:
    env = environment or dict()
    command_runner = runner or _default_runner

    tesseract = _detect_tesseract(runner=command_runner)
    api_fallback = _detect_api_fallback(env)

    local_only_status = str(tesseract.get("status", "unavailable") or "unavailable")
    if local_only_status not in {"available", "degraded", "unavailable"}:
        local_only_status = "unavailable"

    if local_only_status == "unavailable":
        local_then_api_required_only = "unavailable"
    elif bool(api_fallback.get("configured", False)):
        local_then_api_required_only = "available"
    else:
        local_then_api_required_only = "degraded"

    overall_status = local_only_status
    return {
        "tool": "ocr_preflight",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "overall_status": overall_status,
        "fallback_readiness": {
            "local_only": local_only_status,
            "local_then_api_required_only": local_then_api_required_only,
        },
        "tesseract": tesseract,
        "api_fallback": api_fallback,
        "failure_semantics": {
            "unavailable": "local OCR runtime not executable in current environment",
            "degraded": "OCR can run but missing language packs or fallback prerequisites",
            "failed": "OCR tooling executes but assertions in downstream checks fail",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit OCR preflight status JSON.")
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print compact JSON without indentation.",
    )
    args = parser.parse_args(argv)
    payload = run_ocr_preflight(environment=dict(os.environ))
    if args.compact:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
