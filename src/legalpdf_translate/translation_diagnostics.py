"""Translation diagnostics: quality checks, cost estimation, prompt metrics (admin-only)."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import re
from typing import Any

from .config import OPENAI_MODEL
from .glossary import detect_source_lang_for_glossary
from .validators import strip_ar_protected_spans_for_language_detection

# ---------------------------------------------------------------------------
# Model price table (per 1M tokens) — fallback when env vars are not set
# ---------------------------------------------------------------------------

_MODEL_PRICES: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00, "reasoning": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "reasoning": 0.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00, "reasoning": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60, "reasoning": 1.60},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40, "reasoning": 0.40},
    "o3": {"input": 2.00, "output": 8.00, "reasoning": 8.00},
    "o3-mini": {"input": 1.10, "output": 4.40, "reasoning": 4.40},
    "o4-mini": {"input": 1.10, "output": 4.40, "reasoning": 4.40},
    "gpt-5.2": {"input": 2.00, "output": 8.00, "reasoning": 8.00},
}


def estimate_cost(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    reasoning_tokens: int,
    env_input_rate: float | None = None,
    env_output_rate: float | None = None,
    env_reasoning_rate: float | None = None,
) -> tuple[float | None, str]:
    """Return ``(cost, explanation)`` for the given token counts.

    Uses env rates if all three are provided; otherwise falls back to
    the built-in price table.  Returns ``(None, reason)`` when the
    model is unknown and no env rates are set.
    """
    if env_input_rate is not None and env_output_rate is not None and env_reasoning_rate is not None:
        cost = (
            (input_tokens / 1_000_000.0) * env_input_rate
            + (output_tokens / 1_000_000.0) * env_output_rate
            + (reasoning_tokens / 1_000_000.0) * env_reasoning_rate
        )
        return round(cost, 6), f"env rates ({env_input_rate}/{env_output_rate}/{env_reasoning_rate} per 1M)"

    prices = _MODEL_PRICES.get(model)
    if prices is None:
        return None, f"model '{model}' not in built-in price table and no LEGALPDF_COST_* env vars set"

    cost = (
        (input_tokens / 1_000_000.0) * prices["input"]
        + (output_tokens / 1_000_000.0) * prices["output"]
        + (reasoning_tokens / 1_000_000.0) * prices["reasoning"]
    )
    return round(cost, 6), f"built-in table for {model}"


# ---------------------------------------------------------------------------
# Prompt metrics
# ---------------------------------------------------------------------------

def compute_prompt_metrics(
    *,
    prompt_text: str,
    system_instructions: str,
    glossary_source_text: str,
) -> dict[str, Any]:
    """Cheap token-estimate metrics for the compiled prompt."""
    # rough: 1 token ≈ 4 chars (for English/Portuguese mix)
    prompt_chars = len(prompt_text)
    system_chars = len(system_instructions)
    prompt_tokens_est = prompt_chars // 4
    system_tokens_est = system_chars // 4

    # Estimate glossary portion by looking for the glossary block
    glossary_chars = 0
    idx_start = prompt_text.find("<<<BEGIN GLOSSARY>>>")
    idx_end = prompt_text.find("<<<END GLOSSARY>>>")
    if idx_start >= 0 and idx_end > idx_start:
        glossary_chars = idx_end + len("<<<END GLOSSARY>>>") - idx_start
    glossary_tokens_est = glossary_chars // 4

    source_lines = [ln for ln in glossary_source_text.splitlines() if ln.strip()]
    segment_count = len(source_lines)

    return {
        "prompt_chars": prompt_chars,
        "prompt_tokens_est": prompt_tokens_est,
        "system_chars": system_chars,
        "system_tokens_est": system_tokens_est,
        "glossary_chars": glossary_chars,
        "glossary_tokens_est": glossary_tokens_est,
        "segment_count": segment_count,
        "prompt_bloat_warning": glossary_tokens_est > 1500,
    }


def system_instructions_hash(text: str) -> str:
    """Short SHA-256 hash of system instructions for version tracking."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Translation quality checks (lightweight, regex-based)
# ---------------------------------------------------------------------------

_NUMBER_RE = re.compile(r"\d[\d.,]*\d|\d")
_CITATION_RE = re.compile(
    r"\bn\.?[ºo°]\b|\bartigo\b|\bart\.?\s*\d|\balínea\b",
    re.IGNORECASE,
)
_PAREN_OPEN_RE = re.compile(r"[(\[{]")
_PAREN_CLOSE_RE = re.compile(r"[)\]}]")
_BIDI_CONTROL_RE = re.compile(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]")
_REPLACEMENT_CHAR_RE = re.compile(r"\ufffd")


def check_numeric_preservation(source: str, output: str) -> dict[str, Any]:
    """Compare number tokens between source and output."""
    src_nums = sorted(_NUMBER_RE.findall(source))
    out_nums = sorted(_NUMBER_RE.findall(output))
    missing = []
    extra = []
    out_copy = list(out_nums)
    for n in src_nums:
        if n in out_copy:
            out_copy.remove(n)
        else:
            missing.append(n)
    extra = out_copy
    return {
        "source_count": len(src_nums),
        "output_count": len(out_nums),
        "missing_count": len(missing),
        "extra_count": len(extra),
        "missing_sample": missing[:5],
        "extra_sample": extra[:5],
    }


def check_citation_preservation(source: str, output: str) -> dict[str, Any]:
    """Compare legal citation pattern counts."""
    src_count = len(_CITATION_RE.findall(source))
    out_count = len(_CITATION_RE.findall(output))
    src_parens = len(_PAREN_OPEN_RE.findall(source)) + len(_PAREN_CLOSE_RE.findall(source))
    out_parens = len(_PAREN_OPEN_RE.findall(output)) + len(_PAREN_CLOSE_RE.findall(output))
    return {
        "source_citations": src_count,
        "output_citations": out_count,
        "citation_delta": out_count - src_count,
        "source_parens": src_parens,
        "output_parens": out_parens,
        "parens_delta": out_parens - src_parens,
    }


def check_structure(source: str, output: str) -> dict[str, Any]:
    """Compare paragraph/line structure."""
    src_lines = source.count("\n") + 1
    out_lines = output.count("\n") + 1
    src_paras = len([ln for ln in source.split("\n") if ln.strip()])
    out_paras = len([ln for ln in output.split("\n") if ln.strip()])
    delta = out_paras - src_paras
    collapse_warning = src_paras > 3 and out_paras < src_paras * 0.5
    return {
        "source_lines": src_lines,
        "output_lines": out_lines,
        "source_paragraphs": src_paras,
        "output_paragraphs": out_paras,
        "paragraph_delta": delta,
        "collapse_warning": collapse_warning,
    }


def check_bidi_safety(output: str) -> dict[str, Any]:
    """Check for suspicious bidi controls and replacement chars."""
    bidi_count = len(_BIDI_CONTROL_RE.findall(output))
    replacement_count = len(_REPLACEMENT_CHAR_RE.findall(output))
    return {
        "bidi_control_count": bidi_count,
        "replacement_char_count": replacement_count,
        "bidi_warning": bidi_count > 20,
        "replacement_warning": replacement_count > 5,
    }


def check_target_language(
    output: str,
    target_lang: str,
) -> dict[str, Any]:
    """Cheap heuristic: detect if output is primarily in the target language."""
    # Map expected: EN→EN, FR→FR, AR→expect non-PT detection
    if target_lang == "AR":
        stripped = strip_ar_protected_spans_for_language_detection(output)
        if stripped == "":
            detected = "AUTO"
        else:
            detected = detect_source_lang_for_glossary(stripped)
        language_ok = detected != "PT"
    else:
        detected = detect_source_lang_for_glossary(output)
        language_ok = detected in (target_lang, "AUTO")
    return {
        "detected_lang": detected,
        "target_lang": target_lang,
        "language_ok": language_ok,
    }


def summarize_extraction_integrity(
    integrity_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(integrity_context, Mapping):
        return {
            "extraction_integrity_warnings_count": 0,
            "extraction_integrity_reasons": [],
            "vector_gap_count": 0,
            "visual_recovery_strategy": "",
            "visual_recovery_used": False,
            "visual_recovery_failed": False,
        }
    reasons_value = integrity_context.get("extraction_integrity_reasons", [])
    reasons = [
        str(item)
        for item in reasons_value
        if isinstance(item, str) and str(item).strip()
    ]
    return {
        "extraction_integrity_warnings_count": int(bool(integrity_context.get("extraction_integrity_suspect", False))),
        "extraction_integrity_reasons": reasons[:3],
        "vector_gap_count": int(integrity_context.get("vector_gap_count", 0) or 0),
        "visual_recovery_strategy": str(integrity_context.get("visual_recovery_strategy", "") or ""),
        "visual_recovery_used": bool(integrity_context.get("visual_recovery_used", False)),
        "visual_recovery_failed": bool(integrity_context.get("visual_recovery_failed", False)),
    }


def run_all_quality_checks(
    *,
    source_text: str,
    output_text: str,
    target_lang: str,
    integrity_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run all lightweight quality checks, return combined summary."""
    lang_check = check_target_language(output_text, target_lang)
    numeric_check = check_numeric_preservation(source_text, output_text)
    citation_check = check_citation_preservation(source_text, output_text)
    structure_check = check_structure(source_text, output_text)
    bidi_check = check_bidi_safety(output_text)
    integrity_check = summarize_extraction_integrity(integrity_context)
    return {
        "language_ok": lang_check["language_ok"],
        "detected_lang": lang_check["detected_lang"],
        "numeric_mismatches_count": numeric_check["missing_count"] + numeric_check["extra_count"],
        "numeric_missing_sample": numeric_check["missing_sample"],
        "citation_mismatches_count": abs(citation_check["citation_delta"]) + abs(citation_check["parens_delta"]),
        "structure_warnings_count": int(structure_check["collapse_warning"]),
        "source_paragraphs": structure_check["source_paragraphs"],
        "output_paragraphs": structure_check["output_paragraphs"],
        "bidi_warnings_count": int(bidi_check["bidi_warning"]) + int(bidi_check["replacement_warning"]),
        "bidi_control_count": bidi_check["bidi_control_count"],
        "replacement_char_count": bidi_check["replacement_char_count"],
        "extraction_integrity_warnings_count": integrity_check["extraction_integrity_warnings_count"],
        "extraction_integrity_reasons": integrity_check["extraction_integrity_reasons"],
        "vector_gap_count": integrity_check["vector_gap_count"],
        "visual_recovery_strategy": integrity_check["visual_recovery_strategy"],
        "visual_recovery_used": integrity_check["visual_recovery_used"],
        "visual_recovery_failed": integrity_check["visual_recovery_failed"],
    }


# ---------------------------------------------------------------------------
# Event emission helpers
# ---------------------------------------------------------------------------


def emit_prompt_compiled_event(
    collector: object,
    *,
    page_index: int,
    metrics: dict[str, Any],
) -> None:
    """Emit prompt_compiled event."""
    if collector is None or not hasattr(collector, "add_event"):
        return
    collector.add_event(
        event_type="prompt_compiled",
        stage="translate",
        page_index=page_index,
        counters={
            "prompt_tokens_est": metrics.get("prompt_tokens_est", 0),
            "system_tokens_est": metrics.get("system_tokens_est", 0),
            "glossary_tokens_est": metrics.get("glossary_tokens_est", 0),
            "segment_count": metrics.get("segment_count", 0),
        },
        decisions={
            "prompt_bloat_warning": bool(metrics.get("prompt_bloat_warning", False)),
        },
    )


def emit_validation_summary_event(
    collector: object,
    *,
    page_index: int,
    checks: dict[str, Any],
) -> None:
    """Emit translation_validation_summary event."""
    if collector is None or not hasattr(collector, "add_event"):
        return
    collector.add_event(
        event_type="translation_validation_summary",
        stage="translate",
        page_index=page_index,
        counters={
            "numeric_mismatches_count": checks.get("numeric_mismatches_count", 0),
            "numeric_missing_sample": list(checks.get("numeric_missing_sample", []))[:3],
            "citation_mismatches_count": checks.get("citation_mismatches_count", 0),
            "structure_warnings_count": checks.get("structure_warnings_count", 0),
            "extraction_integrity_warnings_count": checks.get("extraction_integrity_warnings_count", 0),
            "vector_gap_count": checks.get("vector_gap_count", 0),
            "source_paragraphs": checks.get("source_paragraphs", 0),
            "output_paragraphs": checks.get("output_paragraphs", 0),
            "bidi_warnings_count": checks.get("bidi_warnings_count", 0),
            "bidi_control_count": checks.get("bidi_control_count", 0),
            "replacement_char_count": checks.get("replacement_char_count", 0),
        },
        decisions={
            "language_ok": bool(checks.get("language_ok", True)),
            "detected_lang": str(checks.get("detected_lang", "?")),
            "visual_recovery_strategy": str(checks.get("visual_recovery_strategy", "") or ""),
            "visual_recovery_used": bool(checks.get("visual_recovery_used", False)),
            "visual_recovery_failed": bool(checks.get("visual_recovery_failed", False)),
        },
        details={
            "extraction_integrity_reasons": list(checks.get("extraction_integrity_reasons", []))[:3],
        },
    )


def emit_cost_estimate_event(
    collector: object,
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    reasoning_tokens: int,
    estimated_cost: float | None,
    cost_explanation: str,
) -> None:
    """Emit cost_estimate_summary event."""
    if collector is None or not hasattr(collector, "add_event"):
        return
    collector.add_event(
        event_type="cost_estimate_summary",
        stage="run",
        counters={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "reasoning_tokens": reasoning_tokens,
            "total_tokens": input_tokens + output_tokens + reasoning_tokens,
        },
        details={
            "model": model,
            "estimated_cost": estimated_cost,
            "cost_explanation": cost_explanation,
        },
    )


def emit_docx_write_event(
    collector: object,
    *,
    write_ms: float,
    page_count: int,
    paragraph_count: int = 0,
    run_count: int = 0,
) -> None:
    """Emit docx_write_summary event."""
    if collector is None or not hasattr(collector, "add_event"):
        return
    collector.add_event(
        event_type="docx_write_summary",
        stage="assemble",
        duration_ms=write_ms,
        counters={
            "page_count": page_count,
            "paragraph_count": paragraph_count,
            "run_count": run_count,
        },
    )


def emit_run_config_event(
    collector: object,
    *,
    model: str,
    system_instructions_hash: str,
    image_mode: str,
    ocr_mode: str,
    strip_bidi_controls: bool,
    effort_policy: str,
    glossary_entries_count: int,
    glossary_tiers: str,
    target_lang: str,
    effort_resolved: str = "",
    page_breaks: bool = True,
    workers: int = 1,
    resume: bool = False,
    keep_intermediates: bool = True,
) -> None:
    """Emit run_config_summary event."""
    if collector is None or not hasattr(collector, "add_event"):
        return
    collector.add_event(
        event_type="run_config_summary",
        stage="run",
        details={
            "model": model,
            "system_instructions_hash": system_instructions_hash,
            "image_mode": image_mode,
            "ocr_mode": ocr_mode,
            "strip_bidi_controls": strip_bidi_controls,
            "effort_policy": effort_policy,
            "glossary_entries_count": glossary_entries_count,
            "glossary_tiers": glossary_tiers,
            "target_lang": target_lang,
            "effort_resolved": effort_resolved,
            "page_breaks": page_breaks,
            "workers": workers,
            "resume": resume,
            "keep_intermediates": keep_intermediates,
        },
    )
