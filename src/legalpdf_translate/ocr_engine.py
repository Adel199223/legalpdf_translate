"""OCR engine implementations and policy routing."""

from __future__ import annotations

import base64
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Any, Literal, Protocol

from openai import OpenAI

from .secrets_store import get_ocr_key
from .types import OcrEnginePolicy, RunConfig, TargetLang


@dataclass(slots=True)
class OcrResult:
    text: str
    engine: Literal["none", "local", "api"]
    failed_reason: str | None
    chars: int


class OCREngine(Protocol):
    def ocr_image(self, image_bytes: bytes, lang_hint: str | None = None) -> OcrResult:
        ...


@dataclass(slots=True)
class OcrEngineConfig:
    policy: OcrEnginePolicy = OcrEnginePolicy.LOCAL_THEN_API
    api_base_url: str | None = None
    api_model: str | None = None
    api_key_env_name: str = "DEEPSEEK_API_KEY"


def ocr_engine_config_from_run_config(config: RunConfig) -> OcrEngineConfig:
    return OcrEngineConfig(
        policy=config.ocr_engine,
        api_base_url=config.ocr_api_base_url,
        api_model=config.ocr_api_model,
        api_key_env_name=config.ocr_api_key_env_name,
    )


def _lang_hint_to_tesseract(lang_hint: str | None) -> str:
    if not lang_hint:
        return "por"
    upper = lang_hint.strip().upper()
    if upper == TargetLang.EN.value:
        return "eng"
    if upper == TargetLang.FR.value:
        return "fra"
    if upper == TargetLang.AR.value:
        return "ara"
    if upper in ("PT", "POR"):
        return "por"
    return "por"


class NoopOcrEngine:
    def ocr_image(self, image_bytes: bytes, lang_hint: str | None = None) -> OcrResult:
        _ = image_bytes
        _ = lang_hint
        return OcrResult(text="", engine="none", failed_reason="ocr disabled", chars=0)


class LocalTesseractEngine:
    def __init__(self, *, strict_unavailable: bool = True) -> None:
        self._tesseract_path = which("tesseract")
        if strict_unavailable and not self._tesseract_path:
            raise RuntimeError("Local OCR unavailable: 'tesseract' executable was not found in PATH.")

    @property
    def is_available(self) -> bool:
        return bool(self._tesseract_path)

    def ocr_image(self, image_bytes: bytes, lang_hint: str | None = None) -> OcrResult:
        if not self._tesseract_path:
            return OcrResult(
                text="",
                engine="local",
                failed_reason="Local OCR unavailable: 'tesseract' executable was not found in PATH.",
                chars=0,
            )

        with tempfile.TemporaryDirectory(prefix="legalpdf_ocr_") as temp_dir:
            input_path = Path(temp_dir) / "input.png"
            input_path.write_bytes(image_bytes)
            command = [
                str(self._tesseract_path),
                str(input_path),
                "stdout",
                "-l",
                _lang_hint_to_tesseract(lang_hint),
            ]
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    check=False,
                    timeout=90,
                )
            except Exception as exc:  # noqa: BLE001
                return OcrResult(text="", engine="local", failed_reason=f"tesseract execution failed: {exc}", chars=0)

        if completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="ignore").strip()
            reason = stderr or f"tesseract exited with code {completed.returncode}"
            return OcrResult(text="", engine="local", failed_reason=reason, chars=0)

        text = completed.stdout.decode("utf-8", errors="ignore").strip()
        if not text:
            return OcrResult(text="", engine="local", failed_reason="tesseract returned empty output", chars=0)
        return OcrResult(text=text, engine="local", failed_reason=None, chars=len(text))


def _extract_output_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    chunks: list[str] = []
    for output_item in getattr(response, "output", []) or []:
        content = getattr(output_item, "content", None)
        if content is None and isinstance(output_item, dict):
            content = output_item.get("content", [])
        for entry in content or []:
            entry_type = getattr(entry, "type", None)
            if entry_type is None and isinstance(entry, dict):
                entry_type = entry.get("type")
            if entry_type not in ("output_text", "text"):
                continue
            text = getattr(entry, "text", None)
            if text is None and isinstance(entry, dict):
                text = entry.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "\n".join(chunks).strip()


class ApiOcrEngine:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("OCR API key is required for API OCR engine.")
        if not model.strip():
            raise ValueError("OCR API model is required for API OCR engine.")
        self._client = OpenAI(api_key=api_key, base_url=(base_url.strip() if base_url else None))
        self._model = model.strip()

    def ocr_image(self, image_bytes: bytes, lang_hint: str | None = None) -> OcrResult:
        prompt = "Extract all visible text. Preserve line breaks. No commentary. Return plain text only."
        if lang_hint:
            prompt += f" Language hint: {lang_hint}."
        encoded = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:image/png;base64,{encoded}"
        try:
            response = self._client.responses.create(
                model=self._model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {"type": "input_image", "image_url": data_url, "detail": "high"},
                        ],
                    }
                ],
                store=False,
            )
            text = _extract_output_text(response)
        except Exception as exc:  # noqa: BLE001
            return OcrResult(text="", engine="api", failed_reason=f"api OCR request failed: {exc}", chars=0)

        if not text:
            return OcrResult(text="", engine="api", failed_reason="api OCR returned empty output", chars=0)
        return OcrResult(text=text, engine="api", failed_reason=None, chars=len(text))


class LocalThenApiEngine:
    def __init__(self, *, local_engine: LocalTesseractEngine, api_engine: ApiOcrEngine | None) -> None:
        self.local_engine = local_engine
        self.api_engine = api_engine

    def ocr_image(self, image_bytes: bytes, lang_hint: str | None = None) -> OcrResult:
        local_result = self.local_engine.ocr_image(image_bytes, lang_hint=lang_hint)
        if local_result.chars > 0:
            return local_result
        if self.api_engine is None:
            return OcrResult(
                text="",
                engine="none",
                failed_reason=local_result.failed_reason or "local OCR failed and API fallback is unavailable",
                chars=0,
            )
        api_result = self.api_engine.ocr_image(image_bytes, lang_hint=lang_hint)
        if api_result.chars > 0:
            return api_result
        reason_parts = [part for part in (local_result.failed_reason, api_result.failed_reason) if part]
        return OcrResult(
            text="",
            engine="api",
            failed_reason="; ".join(reason_parts) if reason_parts else "OCR failed",
            chars=0,
        )


def _resolve_api_key(config: OcrEngineConfig) -> str | None:
    try:
        stored = get_ocr_key()
    except RuntimeError:
        stored = None
    if stored:
        return stored
    env_name = (config.api_key_env_name or "").strip() or "DEEPSEEK_API_KEY"
    from_env = os.getenv(env_name, "").strip()
    return from_env or None


def build_ocr_engine(config: OcrEngineConfig) -> OCREngine:
    if config.policy == OcrEnginePolicy.LOCAL:
        return LocalTesseractEngine(strict_unavailable=True)

    if config.policy == OcrEnginePolicy.API:
        api_key = _resolve_api_key(config)
        if not api_key:
            raise ValueError("OCR API key is not configured.")
        model = (config.api_model or "").strip() or "gpt-4o-mini"
        return ApiOcrEngine(api_key=api_key, model=model, base_url=config.api_base_url)

    # local_then_api
    local_engine = LocalTesseractEngine(strict_unavailable=False)
    api_key = _resolve_api_key(config)
    api_engine: ApiOcrEngine | None = None
    if api_key:
        model = (config.api_model or "").strip() or "gpt-4o-mini"
        api_engine = ApiOcrEngine(api_key=api_key, model=model, base_url=config.api_base_url)
    return LocalThenApiEngine(local_engine=local_engine, api_engine=api_engine)
