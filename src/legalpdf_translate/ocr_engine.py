"""OCR engine implementations and policy routing."""

from __future__ import annotations

import base64
import hashlib
import inspect
import json
import os
import subprocess
import tempfile
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from shutil import which
from typing import Any, Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from openai import OpenAI

from .config import DEFAULT_OCR_API_TIMEOUT_SECONDS
from .ocr_defaults import (
    GEMINI_OCR_DEFAULT_ENV,
    OPENAI_OCR_DEFAULT_ENV,
    OPENAI_OCR_LEGACY_ENV,
    default_ocr_api_env_name,
)
from .secrets_store import get_ocr_key, get_openai_key
from .openai_client import (
    _accounted_openai_create,
    _active_accountant,
    _dispatch_limits,
    _validate_dispatch_input_bound,
)
from .types import OcrApiProvider, OcrEnginePolicy, RunConfig, TargetLang
from .usage_accounting import MemoryDispatchAccounting

_PROVIDER_TEST_ACCOUNTING = MemoryDispatchAccounting()

_PROFILE_PT_LATIN_DEFAULT = "pt_latin_default"
_PROFILE_AR_TRACK_DEFAULT = "ar_track_default"
_PT_LATIN_LANG_PACK = "por+eng+fra"
_AR_TRACK_LANG_PACK = "ara+eng"
_EARLY_ACCEPT_SCORE = 0.82
_MIN_ACCEPTABLE_LOCAL_SCORE = 0.18
OPENAI_OCR_DEFAULT_MODEL = "gpt-4o-mini"
GEMINI_OCR_DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"
GEMINI_OCR_BENCHMARK_MODEL = "gemini-3-flash-preview"
GEMINI_OCR_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_GEMINI_TIMEOUT_SECONDS = 120
GEMINI_MEDIA_RESOLUTION_PDF = "MEDIUM"
GEMINI_MEDIA_RESOLUTION_IMAGE = "HIGH"


@dataclass(frozen=True, slots=True)
class _LocalPassSpec:
    name: str
    lang: str
    psm: int


@dataclass(frozen=True, slots=True, repr=False)
class LocalOcrEvidence:
    """Opt-in private acquisition bytes; never place in result metadata/reports."""

    selected_pass: str
    image_sha256: str
    text_bytes: bytes
    tsv_bytes: bytes
    structure_bytes: bytes


@dataclass(slots=True)
class OcrResult:
    text: str
    engine: Literal["none", "local", "api"]
    failed_reason: str | None
    chars: int
    quality_score: float = 0.0
    selected_pass: str = ""
    attempts: list[dict[str, Any]] | None = None
    structure: dict[str, Any] | None = None
    structure_metadata: dict[str, Any] | None = None
    local_evidence: LocalOcrEvidence | None = field(default=None, repr=False)


class OCREngine(Protocol):
    def ocr_image(
        self,
        image_bytes: bytes,
        lang_hint: str | None = None,
        *,
        source_type: Literal["pdf", "image"] = "pdf",
    ) -> OcrResult:
        ...


def invoke_ocr_image(
    engine: OCREngine,
    image_bytes: bytes,
    lang_hint: str | None = None,
    *,
    source_type: Literal["pdf", "image"] = "pdf",
    preserve_structure: bool = False,
) -> OcrResult:
    # Decide legacy-adapter compatibility before the only dispatch. An internal
    # TypeError may happen after a paid request; never catch it and replay.
    options: dict[str, Any] = {"lang_hint": lang_hint, "source_type": source_type}
    if preserve_structure:
        options["preserve_structure"] = True
    try:
        parameters = inspect.signature(engine.ocr_image).parameters
    except (ValueError, TypeError):
        parameters = None
    if parameters is not None and not any(item.kind == inspect.Parameter.VAR_KEYWORD for item in parameters.values()):
        options = {key: value for key, value in options.items() if key in parameters}
    return engine.ocr_image(image_bytes, **options)


@dataclass(slots=True)
class OcrEngineConfig:
    policy: OcrEnginePolicy = OcrEnginePolicy.LOCAL_THEN_API
    api_provider: OcrApiProvider = OcrApiProvider.OPENAI
    api_base_url: str | None = None
    api_model: str | None = None
    api_key_env_name: str = OPENAI_OCR_DEFAULT_ENV
    api_timeout_seconds: float = float(DEFAULT_OCR_API_TIMEOUT_SECONDS)


def ocr_engine_config_from_run_config(config: RunConfig) -> OcrEngineConfig:
    return OcrEngineConfig(
        policy=config.ocr_engine,
        api_provider=config.ocr_api_provider,
        api_base_url=config.ocr_api_base_url,
        api_model=config.ocr_api_model,
        api_key_env_name=config.ocr_api_key_env_name,
        api_timeout_seconds=float(DEFAULT_OCR_API_TIMEOUT_SECONDS),
    )


def local_only_ocr_engine_config_from_run_config(config: RunConfig) -> OcrEngineConfig:
    return OcrEngineConfig(
        policy=OcrEnginePolicy.LOCAL,
        api_provider=config.ocr_api_provider,
        api_base_url=config.ocr_api_base_url,
        api_model=config.ocr_api_model,
        api_key_env_name=config.ocr_api_key_env_name,
        api_timeout_seconds=float(DEFAULT_OCR_API_TIMEOUT_SECONDS),
    )


def normalize_ocr_api_provider(value: object, default: OcrApiProvider = OcrApiProvider.OPENAI) -> OcrApiProvider:
    if isinstance(value, OcrApiProvider):
        return value
    cleaned = str(value or "").strip().lower()
    if cleaned == OcrApiProvider.GEMINI.value:
        return OcrApiProvider.GEMINI
    if cleaned == OcrApiProvider.OPENAI.value:
        return OcrApiProvider.OPENAI
    return default


def default_ocr_api_model(provider: OcrApiProvider) -> str:
    if provider == OcrApiProvider.GEMINI:
        return GEMINI_OCR_DEFAULT_MODEL
    return OPENAI_OCR_DEFAULT_MODEL


def local_ocr_available() -> bool:
    return bool(which("tesseract"))


def candidate_ocr_api_env_names(config: OcrEngineConfig) -> tuple[str, ...]:
    provider = normalize_ocr_api_provider(config.api_provider)
    configured = (config.api_key_env_name or "").strip()
    if provider == OcrApiProvider.GEMINI:
        return (configured or default_ocr_api_env_name(provider),)
    if configured and configured not in {OPENAI_OCR_DEFAULT_ENV, OPENAI_OCR_LEGACY_ENV}:
        return (configured,)
    return (OPENAI_OCR_DEFAULT_ENV, OPENAI_OCR_LEGACY_ENV)


def resolve_ocr_api_key_source(
    config: OcrEngineConfig,
) -> tuple[Literal["stored", "env"], str] | None:
    try:
        stored = get_ocr_key()
    except RuntimeError:
        stored = None
    if stored:
        return ("stored", "ocr_api_key")
    provider = normalize_ocr_api_provider(config.api_provider)
    if provider == OcrApiProvider.OPENAI:
        try:
            shared_openai_key = get_openai_key()
        except RuntimeError:
            shared_openai_key = None
        if shared_openai_key:
            return ("stored", "openai_api_key_fallback")
    for env_name in candidate_ocr_api_env_names(config):
        from_env = os.getenv(env_name, "").strip()
        if from_env:
            return ("env", env_name)
    return None


def resolve_ocr_api_key(config: OcrEngineConfig) -> str | None:
    source = resolve_ocr_api_key_source(config)
    if source is None:
        return None
    source_kind, source_name = source
    if source_kind == "stored":
        if source_name == "openai_api_key_fallback":
            try:
                return get_openai_key()
            except RuntimeError:
                return None
        try:
            return get_ocr_key()
        except RuntimeError:
            return None
    return os.getenv(source_name, "").strip() or None


def default_ocr_api_base_url(provider: OcrApiProvider) -> str:
    if provider == OcrApiProvider.GEMINI:
        return GEMINI_OCR_DEFAULT_BASE_URL
    return ""


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
    def ocr_image(
        self,
        image_bytes: bytes,
        lang_hint: str | None = None,
        *,
        source_type: Literal["pdf", "image"] = "pdf",
    ) -> OcrResult:
        _ = image_bytes
        _ = lang_hint
        _ = source_type
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
        preserve_structure: bool = False,
    ) -> tuple[int, str, str] | tuple[int, str, str, str]:
        if not self._tesseract_path:
            return 1, "", "Local OCR unavailable: 'tesseract' executable was not found in PATH."
        output_base = input_path.parent / pass_spec.name
        command = [
            str(self._tesseract_path),
            str(input_path),
            str(output_base) if preserve_structure else "stdout",
            "-l",
            pass_spec.lang,
            "--oem",
            "1",
            "--psm",
            str(pass_spec.psm),
        ]
        if preserve_structure:
            # Both renderers consume one recognition pass. Keep TXT for winner
            # scoring and selected text; TSV is optional layout evidence only.
            command.extend(("txt", "tsv"))
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            timeout=90,
        )
        stdout = completed.stdout.decode("utf-8", errors="ignore")
        stderr = completed.stderr.decode("utf-8", errors="ignore")
        if preserve_structure:
            text_path, tsv_path = output_base.with_suffix(".txt"), output_base.with_suffix(".tsv")
            text = text_path.read_bytes().decode("utf-8", errors="ignore") if text_path.is_file() else ""
            tsv = tsv_path.read_bytes().decode("utf-8", errors="ignore") if tsv_path.is_file() else ""
            return completed.returncode, text, stderr, tsv
        return completed.returncode, stdout, stderr

    def ocr_image(
        self,
        image_bytes: bytes,
        lang_hint: str | None = None,
        *,
        source_type: Literal["pdf", "image"] = "pdf",
        preserve_structure: bool = False,
        retain_local_evidence: bool = False,
    ) -> OcrResult:
        _ = source_type
        if retain_local_evidence:
            preserve_structure = True
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
        best_structure = None
        best_evidence = None

        with tempfile.TemporaryDirectory(prefix="legalpdf_ocr_") as temp_dir:
            input_path = Path(temp_dir) / "input.png"
            input_path.write_bytes(image_bytes)

            for pass_spec in pass_specs:
                try:
                    pass_result = self._run_pass(
                        input_path=input_path,
                        pass_spec=pass_spec,
                        **({"preserve_structure": True} if preserve_structure else {}),
                    )
                    return_code, stdout, stderr = pass_result[:3]
                    tsv = pass_result[3] if len(pass_result) == 4 else ""
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
                structure = None
                if preserve_structure and tsv:
                    from .document_structure import structure_from_tesseract_tsv, text_sha256
                    try:
                        parsed = structure_from_tesseract_tsv(tsv)
                        if parsed.text.split() != text.split():
                            raise ValueError("TSV does not match the selected TXT content.")
                        # Existing PSM choices are unchanged, and can flatten
                        # columns. Retain their boxes but not layout certainty.
                        parsed.uncertain = True
                        parsed.metadata.update(local_pass=pass_spec.name, psm=pass_spec.psm,
                            language_pack=pass_spec.lang, selected_text_sha256=text_sha256(text),
                            image_sha256=hashlib.sha256(image_bytes).hexdigest(),
                            text_binding="ordered_non_whitespace_tokens",
                            warnings=["local_ocr_reading_order_requires_review"])
                        structure = parsed.to_dict()
                    except (ValueError, TypeError, KeyError, OverflowError, UnicodeError):
                        # Failed optional evidence never changes selected text,
                        # quality scoring, pass count or API fallback routing.
                        structure = None
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
                    best_structure = structure
                    best_evidence = None
                    if retain_local_evidence and structure is not None:
                        # Read the actual renderer files before TemporaryDirectory
                        # cleanup. Never regenerate TSV from derived word boxes.
                        try:
                            base = input_path.parent / pass_spec.name
                            with base.with_suffix(".txt").open("rb") as stream:
                                raw_txt = stream.read(8_000_001)
                            with base.with_suffix(".tsv").open("rb") as stream:
                                raw_tsv = stream.read(8_000_001)
                            if (len(raw_txt) <= 8_000_000 and len(raw_tsv) <= 8_000_000
                                    and raw_txt.decode("utf-8") == stdout
                                    and raw_tsv.decode("utf-8") == tsv):
                                best_evidence = LocalOcrEvidence(pass_spec.name,
                                    hashlib.sha256(image_bytes).hexdigest(), raw_txt, raw_tsv,
                                    json.dumps(structure, ensure_ascii=False, sort_keys=True,
                                        separators=(",", ":"), allow_nan=False).encode("utf-8"))
                        except (OSError, ValueError, TypeError, UnicodeError):
                            # Missing optional retention cannot alter winner or
                            # normal OCR routing; the acquisition caller declines.
                            best_evidence = None

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
            structure=best_structure,
            structure_metadata=self._readiness_metadata(best_structure),
            local_evidence=best_evidence,
        )

    @staticmethod
    def _readiness_metadata(structure):
        # Additive diagnostics only. Never feed these back into legacy winner
        # ranking, early acceptance, pass count or provider fallback policy.
        from .source_readiness import source_readiness_diagnostics
        if structure is None:
            return {"source_readiness": {"status": "review_required",
                "fidelity_status": "not_evaluated", "winner_score_is_fidelity": False,
                "codes": ["same_pass_word_evidence_invalid_or_missing"]}}
        return {"source_readiness": source_readiness_diagnostics(structure)}


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
        self._dispatch_accounting = MemoryDispatchAccounting()

    def ocr_image(
        self,
        image_bytes: bytes,
        lang_hint: str | None = None,
        *,
        source_type: Literal["pdf", "image"] = "pdf",
    ) -> OcrResult:
        _ = source_type
        prompt = "Extract all visible text. Preserve line breaks. No commentary. Return plain text only."
        if lang_hint:
            prompt += f" Language hint: {lang_hint}."
        encoded = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:image/png;base64,{encoded}"
        try:
            response = _accounted_openai_create(
                client=self._client, accountant=self._dispatch_accounting, purpose="ocr",
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


def _gemini_extract_output_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return ""
    chunks: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    chunks.append(text)
    return "\n".join(chunk.strip() for chunk in chunks if chunk.strip()).strip()


def _gemini_post_json(
    *,
    api_key: str,
    model: str,
    base_url: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    root = (base_url or GEMINI_OCR_DEFAULT_BASE_URL).strip().rstrip("/")
    endpoint = f"{root}/models/{model}:generateContent?{urlencode({'key': api_key})}"
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=_GEMINI_TIMEOUT_SECONDS) as response:  # noqa: S310
            raw = response.read().decode("utf-8", errors="ignore")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        try:
            body = json.loads(detail)
        except (ValueError, TypeError):
            body = None
        raise GeminiRequestError(f"gemini HTTP {exc.code}", body=body, status_code=exc.code) from exc
    except URLError as exc:
        raise GeminiRequestError("gemini transport error") from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("gemini returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("gemini returned an invalid payload type")
    return parsed


class GeminiRequestError(RuntimeError):
    def __init__(self, message: str, *, body: Any = None, status_code: int | None = None) -> None:
        super().__init__(message)
        self.body = body if isinstance(body, dict) else {}
        self.status_code = status_code


def _accounted_gemini_post_json(
    *, accountant: Any, purpose: str, api_key: str, model: str,
    base_url: str | None, payload: dict[str, Any],
) -> dict[str, Any]:
    active = _active_accountant(accountant)
    purpose, limits = _dispatch_limits(active, provider="gemini", purpose=purpose, model=model)
    request = deepcopy(payload)
    maximum = limits.get("max_output_tokens")
    if maximum is not None:
        if type(maximum) is not int or maximum <= 0:
            raise ValueError("Dispatch output token bound must be a positive integer.")
        generation = request.setdefault("generationConfig", {})
        generation["maxOutputTokens"] = min(maximum, generation.get("maxOutputTokens", maximum))
    encoded = json.dumps(request, sort_keys=True, ensure_ascii=False).encode("utf-8")
    text_request = deepcopy(request)
    image_count = 0
    for content in text_request.get("contents", []):
        for part in content.get("parts", []):
            if "inline_data" in part:
                image_count += 1
                part["inline_data"].pop("data", None)
    observed = {"input_bytes": len(json.dumps(text_request, ensure_ascii=False).encode("utf-8")) + 64,
                "image_count": image_count}
    _validate_dispatch_input_bound(active, limits, observed)
    # This route has no approved billing-tier policy in the ordinary snapshot.
    # Preserve OCR usage, but never infer standard OpenAI pricing for Gemini.
    if active.hard_budget:
        raise ValueError("Gemini hard-budget billing scope is not verified.")
    verifier = getattr(active, "verify_dispatch", None)
    if callable(verifier):
        verifier(request=request, provider="gemini", purpose=purpose, attempt=1,
                 route="models.generateContent", base_url=base_url)
    ticket = active.begin(provider="gemini", requested_model=model, purpose=purpose,
                          request_hash=hashlib.sha256(encoded).hexdigest(), bounds={**limits, **observed}, attempt=1,
                          route="models.generateContent", base_url=base_url)
    try:
        response = _gemini_post_json(api_key=api_key, model=model, base_url=base_url, payload=request)
    except BaseException as exc:
        evidence = getattr(exc, "body", {})
        if not isinstance(evidence, dict):
            evidence = {}
        active.finish(ticket, outcome="timeout" if isinstance(exc, TimeoutError) else "failed",
                      usage=evidence.get("usageMetadata"), response_id=evidence.get("responseId"),
                      actual_model=evidence.get("modelVersion"), error_code=type(exc).__name__)
        raise
    active.finish(ticket, outcome="succeeded", usage=response.get("usageMetadata"),
                  response_id=response.get("responseId"), actual_model=response.get("modelVersion"))
    return response


class GeminiApiOcrEngine:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("OCR API key is required for Gemini OCR engine.")
        if not model.strip():
            raise ValueError("OCR API model is required for Gemini OCR engine.")
        self._api_key = api_key.strip()
        self._model = model.strip()
        self._base_url = (base_url or GEMINI_OCR_DEFAULT_BASE_URL).strip()
        self._dispatch_accounting = MemoryDispatchAccounting()

    def ocr_image(
        self,
        image_bytes: bytes,
        lang_hint: str | None = None,
        *,
        source_type: Literal["pdf", "image"] = "pdf",
    ) -> OcrResult:
        prompt = "Extract all visible text. Preserve line breaks. Return plain text only. No commentary."
        if lang_hint:
            prompt += f" Language hint: {lang_hint}."
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": base64.b64encode(image_bytes).decode("ascii"),
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "mediaResolution": (
                    GEMINI_MEDIA_RESOLUTION_IMAGE
                    if source_type == "image"
                    else GEMINI_MEDIA_RESOLUTION_PDF
                ),
            },
        }
        try:
            parsed = _accounted_gemini_post_json(
                accountant=self._dispatch_accounting, purpose="ocr",
                api_key=self._api_key,
                model=self._model,
                base_url=self._base_url,
                payload=payload,
            )
            text = _gemini_extract_output_text(parsed)
        except Exception as exc:  # noqa: BLE001
            return OcrResult(text="", engine="api", failed_reason=f"api OCR request failed: {exc}", chars=0)

        if not text:
            return OcrResult(text="", engine="api", failed_reason="api OCR returned empty output", chars=0)
        score = _text_quality_score(text)
        return OcrResult(
            text=text,
            engine="api",
            failed_reason=None,
            chars=len(text),
            quality_score=score,
            selected_pass="gemini_single_pass",
            attempts=[
                {
                    "pass": "gemini_single_pass",
                    "lang": _source_profile_from_hint(lang_hint),
                    "psm": 0,
                    "status": "ok",
                    "reason": "",
                    "chars": len(text),
                    "score": score,
                }
            ],
        )


class LocalThenApiEngine:
    def __init__(self, *, local_engine: LocalTesseractEngine, api_engine: OCREngine | None) -> None:
        self.local_engine = local_engine
        self.api_engine = api_engine

    def ocr_image(
        self,
        image_bytes: bytes,
        lang_hint: str | None = None,
        *,
        source_type: Literal["pdf", "image"] = "pdf",
        preserve_structure: bool = False,
    ) -> OcrResult:
        local_result = invoke_ocr_image(
            self.local_engine,
            image_bytes,
            lang_hint=lang_hint,
            source_type=source_type,
            **({"preserve_structure": True} if preserve_structure else {}),
        )
        if local_result.chars > 0:
            return local_result
        if self.api_engine is None:
            return OcrResult(
                text="",
                engine="none",
                failed_reason=local_result.failed_reason or "local OCR failed and API fallback is unavailable",
                chars=0,
            )
        api_result = invoke_ocr_image(
            self.api_engine,
            image_bytes,
            lang_hint=lang_hint,
            source_type=source_type,
        )
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
    return resolve_ocr_api_key(config)


def test_ocr_provider_connection(config: OcrEngineConfig, *, api_key: str | None = None) -> None:
    provider = normalize_ocr_api_provider(config.api_provider)
    model = (config.api_model or "").strip() or default_ocr_api_model(provider)
    base_url = (config.api_base_url or "").strip() or default_ocr_api_base_url(provider)
    resolved_api_key = (api_key or "").strip() or _resolve_api_key(config)
    if not resolved_api_key:
        raise ValueError("OCR API key is not configured.")
    if provider == OcrApiProvider.GEMINI:
        payload = {
            "contents": [{"parts": [{"text": "Reply exactly with OK."}]}],
            "generationConfig": {"temperature": 0},
        }
        parsed = _accounted_gemini_post_json(
            accountant=_PROVIDER_TEST_ACCOUNTING, purpose="auth",
            api_key=resolved_api_key,
            model=model,
            base_url=base_url,
            payload=payload,
        )
        if "OK" not in _gemini_extract_output_text(parsed):
            raise RuntimeError("gemini OCR provider test did not return OK")
        return

    client = OpenAI(api_key=resolved_api_key, base_url=(base_url or None), max_retries=0)
    response = _accounted_openai_create(
        client=client, accountant=_PROVIDER_TEST_ACCOUNTING, purpose="auth",
        model=model,
        input=[{"role": "user", "content": [{"type": "input_text", "text": "Reply exactly with OK."}]}],
        max_output_tokens=16,
        store=False,
    )
    output_text = _extract_output_text(response)
    if "OK" not in output_text:
        raise RuntimeError("openai OCR provider test did not return OK")


test_ocr_provider_connection.__test__ = False


def build_ocr_engine(config: OcrEngineConfig) -> OCREngine:
    provider = normalize_ocr_api_provider(config.api_provider)
    if config.policy == OcrEnginePolicy.LOCAL:
        return LocalTesseractEngine(strict_unavailable=True)

    if config.policy == OcrEnginePolicy.API:
        api_key = _resolve_api_key(config)
        if not api_key:
            raise ValueError("OCR API key is not configured.")
        model = (config.api_model or "").strip() or default_ocr_api_model(provider)
        if provider == OcrApiProvider.GEMINI:
            return GeminiApiOcrEngine(
                api_key=api_key,
                model=model,
                base_url=(config.api_base_url or "").strip() or default_ocr_api_base_url(provider),
            )
        return ApiOcrEngine(
            api_key=api_key,
            model=model,
            base_url=config.api_base_url,
            timeout_seconds=float(config.api_timeout_seconds or DEFAULT_OCR_API_TIMEOUT_SECONDS),
        )

    # local_then_api
    local_engine = LocalTesseractEngine(strict_unavailable=False)
    api_key = _resolve_api_key(config)
    api_engine: OCREngine | None = None
    if api_key:
        model = (config.api_model or "").strip() or default_ocr_api_model(provider)
        if provider == OcrApiProvider.GEMINI:
            api_engine = GeminiApiOcrEngine(
                api_key=api_key,
                model=model,
                base_url=(config.api_base_url or "").strip() or default_ocr_api_base_url(provider),
            )
        else:
            api_engine = ApiOcrEngine(
                api_key=api_key,
                model=model,
                base_url=config.api_base_url,
                timeout_seconds=float(config.api_timeout_seconds or DEFAULT_OCR_API_TIMEOUT_SECONDS),
            )
    return LocalThenApiEngine(local_engine=local_engine, api_engine=api_engine)
