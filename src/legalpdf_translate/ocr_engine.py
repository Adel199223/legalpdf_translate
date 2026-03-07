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

from .config import DEFAULT_OCR_API_TIMEOUT_SECONDS
from .secrets_store import get_ocr_key
from .types import OcrEnginePolicy, RunConfig, TargetLang

_PROFILE_PT_LATIN_DEFAULT = "pt_latin_default"
_PROFILE_AR_TRACK_DEFAULT = "ar_track_default"
_PT_LATIN_LANG_PACK = "por+eng+fra"
_AR_TRACK_LANG_PACK = "ara+eng"
_EARLY_ACCEPT_SCORE = 0.82
_MIN_ACCEPTABLE_LOCAL_SCORE = 0.18


@dataclass(frozen=True, slots=True)
class _LocalPassSpec:
    name: str
    lang: str
    psm: int


@dataclass(slots=True)
class OcrResult:
    text: str
    engine: Literal["none", "local", "api"]
    failed_reason: str | None
    chars: int
    quality_score: float = 0.0
    selected_pass: str = ""
    attempts: list[dict[str, Any]] | None = None


class OCREngine(Protocol):
    def ocr_image(self, image_bytes: bytes, lang_hint: str | None = None) -> OcrResult:
        ...


@dataclass(slots=True)
class OcrEngineConfig:
    policy: OcrEnginePolicy = OcrEnginePolicy.LOCAL_THEN_API
    api_base_url: str | None = None
    api_model: str | None = None
    api_key_env_name: str = "DEEPSEEK_API_KEY"
    api_timeout_seconds: float = float(DEFAULT_OCR_API_TIMEOUT_SECONDS)


def ocr_engine_config_from_run_config(config: RunConfig) -> OcrEngineConfig:
    return OcrEngineConfig(
        policy=config.ocr_engine,
        api_base_url=config.ocr_api_base_url,
        api_model=config.ocr_api_model,
        api_key_env_name=config.ocr_api_key_env_name,
        api_timeout_seconds=float(DEFAULT_OCR_API_TIMEOUT_SECONDS),
    )


def local_only_ocr_engine_config_from_run_config(config: RunConfig) -> OcrEngineConfig:
    return OcrEngineConfig(
        policy=OcrEnginePolicy.LOCAL,
        api_base_url=config.ocr_api_base_url,
        api_model=config.ocr_api_model,
        api_key_env_name=config.ocr_api_key_env_name,
        api_timeout_seconds=float(DEFAULT_OCR_API_TIMEOUT_SECONDS),
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


def _source_profile_from_hint(lang_hint: str | None) -> str:
    if not lang_hint:
        return _PROFILE_PT_LATIN_DEFAULT
    lowered = lang_hint.strip().lower()
    if lowered in {
        "ar",
        "ara",
        TargetLang.AR.value.lower(),
        _PROFILE_AR_TRACK_DEFAULT,
        "ar_track",
        "arabic",
    }:
        return _PROFILE_AR_TRACK_DEFAULT
    return _PROFILE_PT_LATIN_DEFAULT


def _passes_for_profile(source_profile: str) -> list[_LocalPassSpec]:
    passes: list[_LocalPassSpec] = [
        _LocalPassSpec(
            name="pass_a_document",
            lang=_PT_LATIN_LANG_PACK,
            psm=6,
        ),
        _LocalPassSpec(
            name="pass_b_sparse",
            lang=_PT_LATIN_LANG_PACK,
            psm=11,
        ),
    ]
    if source_profile == _PROFILE_AR_TRACK_DEFAULT:
        passes.append(
            _LocalPassSpec(
                name="pass_c_ar_track",
                lang=_AR_TRACK_LANG_PACK,
                psm=6,
            )
        )
    return passes


def _text_quality_score(text: str) -> float:
    cleaned = (text or "").strip()
    if cleaned == "":
        return 0.0
    non_ws = [ch for ch in cleaned if not ch.isspace()]
    if not non_ws:
        return 0.0
    chars = len(cleaned)
    lines = [line for line in cleaned.splitlines() if line.strip()]
    alnum = sum(1 for ch in non_ws if ch.isalnum())
    replacement = sum(1 for ch in non_ws if ch == "\uFFFD")
    control = sum(1 for ch in non_ws if ord(ch) < 32 and ch not in {"\n", "\r", "\t"})

    char_score = min(1.0, chars / 500.0)
    line_score = min(1.0, len(lines) / 18.0)
    alnum_ratio = alnum / float(len(non_ws))
    junk_ratio = (replacement + control) / float(len(non_ws))

    score = (0.55 * char_score) + (0.22 * line_score) + (0.33 * alnum_ratio) - (1.45 * junk_ratio)
    if chars < 30:
        score -= 0.20
    if alnum < 8:
        score -= 0.12
    return round(max(0.0, min(1.0, score)), 4)


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

    def _run_pass(
        self,
        *,
        input_path: Path,
        pass_spec: _LocalPassSpec,
    ) -> tuple[int, str, str]:
        if not self._tesseract_path:
            return 1, "", "Local OCR unavailable: 'tesseract' executable was not found in PATH."
        command = [
            str(self._tesseract_path),
            str(input_path),
            "stdout",
            "-l",
            pass_spec.lang,
            "--oem",
            "1",
            "--psm",
            str(pass_spec.psm),
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            timeout=90,
        )
        stdout = completed.stdout.decode("utf-8", errors="ignore")
        stderr = completed.stderr.decode("utf-8", errors="ignore")
        return completed.returncode, stdout, stderr

    def ocr_image(self, image_bytes: bytes, lang_hint: str | None = None) -> OcrResult:
        if not self._tesseract_path:
            return OcrResult(
                text="",
                engine="local",
                failed_reason="Local OCR unavailable: 'tesseract' executable was not found in PATH.",
                chars=0,
            )

        source_profile = _source_profile_from_hint(lang_hint)
        pass_specs = _passes_for_profile(source_profile)
        attempts: list[dict[str, Any]] = []
        reasons: list[str] = []
        best_text = ""
        best_score = 0.0
        best_chars = 0
        best_pass = ""

        with tempfile.TemporaryDirectory(prefix="legalpdf_ocr_") as temp_dir:
            input_path = Path(temp_dir) / "input.png"
            input_path.write_bytes(image_bytes)

            for pass_spec in pass_specs:
                try:
                    return_code, stdout, stderr = self._run_pass(
                        input_path=input_path,
                        pass_spec=pass_spec,
                    )
                except Exception as exc:  # noqa: BLE001
                    reason = f"tesseract execution failed in {pass_spec.name}: {exc}"
                    attempts.append(
                        {
                            "pass": pass_spec.name,
                            "lang": pass_spec.lang,
                            "psm": pass_spec.psm,
                            "status": "error",
                            "reason": reason,
                            "chars": 0,
                            "score": 0.0,
                        }
                    )
                    reasons.append(reason)
                    continue

                if return_code != 0:
                    reason = stderr.strip() or f"tesseract exited with code {return_code}"
                    attempts.append(
                        {
                            "pass": pass_spec.name,
                            "lang": pass_spec.lang,
                            "psm": pass_spec.psm,
                            "status": "error",
                            "reason": reason,
                            "chars": 0,
                            "score": 0.0,
                        }
                    )
                    reasons.append(reason)
                    continue

                text = stdout.strip()
                score = _text_quality_score(text)
                chars = len(text)
                attempts.append(
                    {
                        "pass": pass_spec.name,
                        "lang": pass_spec.lang,
                        "psm": pass_spec.psm,
                        "status": "ok" if chars > 0 else "empty",
                        "reason": "" if chars > 0 else "empty_output",
                        "chars": chars,
                        "score": score,
                    }
                )

                if chars > 0 and (
                    score > best_score or (score == best_score and chars > best_chars)
                ):
                    best_text = text
                    best_score = score
                    best_chars = chars
                    best_pass = pass_spec.name

                if best_score >= _EARLY_ACCEPT_SCORE:
                    break

        if best_chars <= 0:
            reason = "; ".join(reasons) if reasons else "tesseract returned empty output"
            return OcrResult(
                text="",
                engine="local",
                failed_reason=reason,
                chars=0,
                quality_score=0.0,
                selected_pass=best_pass,
                attempts=attempts,
            )

        if best_score < _MIN_ACCEPTABLE_LOCAL_SCORE:
            reason = (
                "local OCR result below acceptance threshold "
                f"(score={best_score:.4f}, pass={best_pass or 'n/a'})"
            )
            return OcrResult(
                text="",
                engine="local",
                failed_reason=reason,
                chars=0,
                quality_score=best_score,
                selected_pass=best_pass,
                attempts=attempts,
            )

        return OcrResult(
            text=best_text,
            engine="local",
            failed_reason=None,
            chars=best_chars,
            quality_score=best_score,
            selected_pass=best_pass,
            attempts=attempts,
        )


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
        timeout_seconds: float = float(DEFAULT_OCR_API_TIMEOUT_SECONDS),
    ) -> None:
        if not api_key.strip():
            raise ValueError("OCR API key is required for API OCR engine.")
        if not model.strip():
            raise ValueError("OCR API model is required for API OCR engine.")
        self._client = OpenAI(
            api_key=api_key,
            base_url=(base_url.strip() if base_url else None),
            max_retries=0,
        )
        self._model = model.strip()
        self._timeout_seconds = max(0.1, float(timeout_seconds))

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
                timeout=self._timeout_seconds,
            )
            text = _extract_output_text(response)
        except Exception as exc:  # noqa: BLE001
            return OcrResult(text="", engine="api", failed_reason=f"api OCR request failed: {exc}", chars=0)

        if not text:
            return OcrResult(text="", engine="api", failed_reason="api OCR returned empty output", chars=0)
        return OcrResult(
            text=text,
            engine="api",
            failed_reason=None,
            chars=len(text),
            quality_score=_text_quality_score(text),
            selected_pass="api_single_pass",
            attempts=[
                {
                    "pass": "api_single_pass",
                    "lang": _source_profile_from_hint(lang_hint),
                    "psm": 0,
                    "status": "ok",
                    "reason": "",
                    "chars": len(text),
                    "score": _text_quality_score(text),
                }
            ],
        )


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
        return ApiOcrEngine(
            api_key=api_key,
            model=model,
            base_url=config.api_base_url,
            timeout_seconds=float(config.api_timeout_seconds or DEFAULT_OCR_API_TIMEOUT_SECONDS),
        )

    # local_then_api
    local_engine = LocalTesseractEngine(strict_unavailable=False)
    api_key = _resolve_api_key(config)
    api_engine: ApiOcrEngine | None = None
    if api_key:
        model = (config.api_model or "").strip() or "gpt-4o-mini"
        api_engine = ApiOcrEngine(
            api_key=api_key,
            model=model,
            base_url=config.api_base_url,
            timeout_seconds=float(config.api_timeout_seconds or DEFAULT_OCR_API_TIMEOUT_SECONDS),
        )
    return LocalThenApiEngine(local_engine=local_engine, api_engine=api_engine)
