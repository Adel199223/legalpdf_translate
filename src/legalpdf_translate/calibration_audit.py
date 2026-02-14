"""Calibration audit helpers (sampled QA with forced OCR + verifier LLM)."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from .arabic_pre_tokenize import pretokenize_arabic_source
from .glossary import (
    GlossaryEntry,
    cap_entries_for_prompt,
    detect_source_lang_for_glossary,
    filter_entries_for_prompt,
    format_glossary_for_prompt,
    merge_glossary_scopes,
    sort_entries_for_prompt,
)
from .image_io import render_page_image_data_url, should_include_image
from .ocr_engine import build_ocr_engine, ocr_engine_config_from_run_config
from .ocr_helpers import ocr_pdf_page_text
from .openai_client import OpenAIResponsesClient
from .output_normalize import normalize_output_text
from .output_paths import build_output_paths
from .pdf_text_order import extract_ordered_page_text, get_page_count
from .prompt_builder import build_page_prompt
from .resources_loader import load_system_instructions
from .types import OcrMode, RunConfig, TargetLang
from .validators import parse_code_block_output, validate_ar, validate_enfr

_VALID_ISSUE_TYPES = {
    "omission",
    "addition",
    "mistranslation",
    "register",
    "formality",
    "terminology_inconsistency",
    "numbers_dates_layout",
    "other",
}
_VALID_SEVERITIES = {"low", "med", "high"}


@dataclass(slots=True, frozen=True)
class CalibrationFinding:
    issue_type: str
    severity: str
    evidence: str
    explanation: str
    recommended_fix: str


def pick_sample_pages(total_pages: int, n_pages: int, seed_material: str, user_seed: str = "") -> list[int]:
    page_total = max(0, int(total_pages))
    if page_total <= 0:
        return []
    sample_size = max(1, min(page_total, int(n_pages)))
    seed_input = f"{seed_material}|{user_seed}".encode("utf-8", errors="ignore")
    digest = hashlib.sha256(seed_input).hexdigest()
    seed = int(digest[:16], 16)
    rng = random.Random(seed)
    return sorted(rng.sample(list(range(1, page_total + 1)), sample_size))


def _evaluate_translation_output(raw_output: str, lang: TargetLang) -> str:
    parsed = parse_code_block_output(raw_output)
    if parsed.block_count != 1 or parsed.inner_content is None or parsed.outside_has_non_whitespace:
        raise ValueError("Translation output is not compliant (single plain-text code block required).")
    normalized = normalize_output_text(parsed.inner_content, lang=lang)
    validation = validate_ar(normalized) if lang == TargetLang.AR else validate_enfr(normalized, lang=lang)
    if not validation.ok:
        raise ValueError(validation.reason or "Translation output failed validation.")
    return normalized


def _append_glossary_prompt_for_audit(
    prompt_text: str,
    *,
    lang: TargetLang,
    source_text: str,
    glossaries_by_lang: dict[str, list[GlossaryEntry]],
    enabled_tiers_by_lang: dict[str, list[int]],
) -> str:
    rows = glossaries_by_lang.get(lang.value, [])
    if not rows:
        return prompt_text
    detected = detect_source_lang_for_glossary(source_text)
    enabled = enabled_tiers_by_lang.get(lang.value, [1, 2])
    filtered = filter_entries_for_prompt(rows, detected_source_lang=detected, enabled_tiers=enabled)
    if not filtered:
        return prompt_text
    sorted_rows = sort_entries_for_prompt(filtered)
    capped_rows = cap_entries_for_prompt(
        sorted_rows,
        target_lang=lang.value,
        detected_source_lang=detected,
        max_entries=50,
        max_chars=6000,
    )
    if not capped_rows:
        return prompt_text
    block = format_glossary_for_prompt(lang.value, capped_rows, detected_source_lang=detected)
    if block.strip() == "":
        return prompt_text
    return f"{prompt_text}\n{block}"


def _append_prompt_addendum(prompt_text: str, *, lang: TargetLang, addendum_by_lang: dict[str, str]) -> str:
    addendum = str(addendum_by_lang.get(lang.value, "") or "").strip()
    if addendum == "":
        return prompt_text
    return "\n".join([prompt_text, "<<<BEGIN ADDENDUM>>>", addendum, "<<<END ADDENDUM>>>"])


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    cleaned = str(text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


def _verifier_prompt(
    *,
    target_lang: TargetLang,
    page_number: int,
    extracted_source: str,
    forced_ocr_source: str,
    translated_output: str,
    glossary_block: str,
    prompt_addendum: str,
    include_excerpts: bool,
    excerpt_max_chars: int,
) -> str:
    if include_excerpts:
        extracted = _truncate(extracted_source, excerpt_max_chars)
        forced_ocr = _truncate(forced_ocr_source, excerpt_max_chars)
        translated = _truncate(translated_output, excerpt_max_chars)
    else:
        extracted = "omitted due to privacy"
        forced_ocr = "omitted due to privacy"
        translated = "omitted due to privacy"
    glossary_for_verifier = glossary_block.strip() or "No glossary entries."
    addendum_for_verifier = prompt_addendum.strip() or "No prompt addendum."
    return "\n".join(
        [
            "You are a legal translation verifier.",
            "Return JSON only. No markdown, no prose outside JSON.",
            "JSON schema:",
            "{",
            '  "findings": [',
            "    {",
            '      "issue_type": "omission|addition|mistranslation|register|formality|terminology_inconsistency|numbers_dates_layout|other",',
            '      "severity": "low|med|high",',
            '      "evidence": "...",',
            '      "explanation": "...",',
            '      "recommended_fix": "..."',
            "    }",
            "  ],",
            '  "glossary_suggestions": [',
            "    {",
            '      "source_text": "...",',
            '      "preferred_translation": "...",',
            f'      "target_lang": "{target_lang.value}",',
            '      "source_lang": "PT|ANY|AUTO|EN|FR",',
            '      "match_mode": "exact|contains",',
            '      "tier": 1',
            "    }",
            "  ],",
            '  "prompt_addendum_suggestion": "max 12 lines or empty string"',
            "}",
            f"Page: {page_number}",
            f"Target language: {target_lang.value}",
            "<<<BEGIN EXTRACTED SOURCE>>>",
            extracted,
            "<<<END EXTRACTED SOURCE>>>",
            "<<<BEGIN FORCED OCR SOURCE>>>",
            forced_ocr,
            "<<<END FORCED OCR SOURCE>>>",
            "<<<BEGIN TRANSLATED OUTPUT>>>",
            translated,
            "<<<END TRANSLATED OUTPUT>>>",
            "<<<BEGIN GLOSSARY CONTEXT>>>",
            glossary_for_verifier,
            "<<<END GLOSSARY CONTEXT>>>",
            "<<<BEGIN ADDENDUM CONTEXT>>>",
            addendum_for_verifier,
            "<<<END ADDENDUM CONTEXT>>>",
        ]
    )


def _verifier_retry_prompt(prior_output: str) -> str:
    return "\n".join(
        [
            "FORMAT FIX ONLY: Re-emit as valid JSON only matching the required schema. No markdown.",
            "<<<BEGIN PRIOR OUTPUT>>>",
            prior_output,
            "<<<END PRIOR OUTPUT>>>",
        ]
    )


def _parse_verifier_json(raw_output: str) -> dict[str, object]:
    direct = str(raw_output or "").strip()
    candidates = [direct]
    parsed = parse_code_block_output(direct)
    if parsed.block_count == 1 and parsed.inner_content is not None:
        candidates.insert(0, parsed.inner_content.strip())
    for candidate in candidates:
        if candidate == "":
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError("Verifier output was not valid JSON.")


def _normalize_findings(payload: dict[str, object]) -> list[CalibrationFinding]:
    raw = payload.get("findings")
    findings: list[CalibrationFinding] = []
    if not isinstance(raw, list):
        return findings
    for item in raw:
        if not isinstance(item, dict):
            continue
        issue_type = str(item.get("issue_type", "other") or "").strip().lower()
        if issue_type not in _VALID_ISSUE_TYPES:
            issue_type = "other"
        severity = str(item.get("severity", "low") or "").strip().lower()
        if severity not in _VALID_SEVERITIES:
            severity = "low"
        evidence = str(item.get("evidence", "") or "").strip()
        explanation = str(item.get("explanation", "") or "").strip()
        recommended_fix = str(item.get("recommended_fix", "") or "").strip()
        if explanation == "" and recommended_fix == "":
            continue
        findings.append(
            CalibrationFinding(
                issue_type=issue_type,
                severity=severity,
                evidence=evidence,
                explanation=explanation,
                recommended_fix=recommended_fix,
            )
        )
    return findings


def _call_verifier_with_retries(
    *,
    client: OpenAIResponsesClient,
    prompt_text: str,
) -> dict[str, object]:
    current_prompt = prompt_text
    last_error = "Unknown verifier error."
    for attempt in range(0, 3):
        response = client.create_page_response(
            instructions="Return JSON only. No markdown.",
            prompt_text=current_prompt,
            effort="xhigh",
            image_data_url=None,
        )
        raw = response.raw_output
        try:
            return _parse_verifier_json(raw)
        except ValueError as exc:
            last_error = str(exc)
            if attempt >= 2:
                break
            current_prompt = _verifier_retry_prompt(raw)
    raise ValueError(last_error)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _build_markdown_report(report_payload: dict[str, object]) -> str:
    sampled = report_payload.get("sampled_pages", [])
    findings = report_payload.get("findings", [])
    lines: list[str] = [
        "# Calibration Audit Report",
        "",
        f"Generated: {report_payload.get('generated_at_iso', '')}",
        f"PDF: {report_payload.get('pdf_path', '')}",
        f"Target language: {report_payload.get('target_lang', '')}",
        f"Sample pages: {sampled}",
        "",
    ]
    if not isinstance(findings, list) or not findings:
        lines.append("No findings.")
        return "\n".join(lines).strip() + "\n"
    lines.append("| Page | Issue type | Severity | Explanation | Recommended fix |")
    lines.append("| --- | --- | --- | --- | --- |")
    for row in findings:
        if not isinstance(row, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("page_number", "")),
                    str(row.get("issue_type", "")).replace("|", "\\|"),
                    str(row.get("severity", "")).replace("|", "\\|"),
                    str(row.get("explanation", "")).replace("|", "\\|"),
                    str(row.get("recommended_fix", "")).replace("|", "\\|"),
                ]
            )
            + " |"
        )
    return "\n".join(lines).strip() + "\n"


def run_calibration_audit(
    *,
    config: RunConfig,
    personal_glossaries_by_lang: dict[str, list[GlossaryEntry]],
    project_glossaries_by_lang: dict[str, list[GlossaryEntry]],
    enabled_tiers_by_lang: dict[str, list[int]],
    prompt_addendum_by_lang: dict[str, str],
    sample_pages: int = 5,
    user_seed: str = "",
    include_excerpts: bool = False,
    excerpt_max_chars: int = 200,
    client: OpenAIResponsesClient | None = None,
    logger: Callable[[str], None] | None = None,
    progress_callback: Callable[[int, str], None] | None = None,
    cancel_requested: Callable[[], bool] | None = None,
) -> dict[str, object]:
    def _log(message: str) -> None:
        if logger:
            logger(message)

    total_pages = int(get_page_count(config.pdf_path))
    file_size = config.pdf_path.stat().st_size if config.pdf_path.exists() else 0
    seed_material = f"{config.pdf_path.resolve()}|{file_size}|{total_pages}"
    sampled_pages = pick_sample_pages(total_pages, sample_pages, seed_material, user_seed=user_seed)
    if not sampled_pages:
        raise ValueError("No pages available for calibration audit.")

    merged_glossaries = merge_glossary_scopes(project_glossaries_by_lang, personal_glossaries_by_lang)
    addendum = str(prompt_addendum_by_lang.get(config.target_lang.value, "") or "").strip()
    instructions = load_system_instructions(config.target_lang)
    local_client = client or OpenAIResponsesClient()
    ocr_engine = build_ocr_engine(ocr_engine_config_from_run_config(config))

    findings_payload: list[dict[str, object]] = []
    glossary_suggestions: list[dict[str, object]] = []
    prompt_addendum_suggestions: list[str] = []

    sampled_total = max(1, len(sampled_pages))
    for idx, page_number in enumerate(sampled_pages, start=1):
        if cancel_requested and cancel_requested():
            raise RuntimeError("Calibration audit cancelled by user.")
        if progress_callback:
            progress_callback(
                int(((idx - 1) / float(sampled_total)) * 100.0),
                f"Auditing page {page_number} ({idx}/{sampled_total})",
            )
        _log(f"Calibration audit: page {page_number}/{total_pages}")
        ordered = extract_ordered_page_text(config.pdf_path, page_number - 1)
        extracted_text = str(ordered.text or "")
        extracted_usable = (not ordered.extraction_failed) and len(extracted_text.strip()) >= 20
        normal_ocr_text = ""
        if config.ocr_mode == OcrMode.ALWAYS or (config.ocr_mode == OcrMode.AUTO and not extracted_usable):
            normal_ocr = ocr_pdf_page_text(
                config.pdf_path,
                page_number,
                mode=OcrMode.ALWAYS,
                engine=ocr_engine,
                prefer_header=False,
                lang_hint=config.target_lang.value,
            )
            if normal_ocr.chars > 0:
                normal_ocr_text = normal_ocr.text
        source_for_translation = normal_ocr_text if normal_ocr_text.strip() else extracted_text
        glossary_source_text = source_for_translation
        if config.target_lang == TargetLang.AR:
            source_for_translation = pretokenize_arabic_source(source_for_translation)

        prompt = build_page_prompt(
            config.target_lang,
            page_number,
            total_pages,
            source_for_translation,
            context_text=config.context_text,
        )
        prompt = _append_glossary_prompt_for_audit(
            prompt,
            lang=config.target_lang,
            source_text=glossary_source_text,
            glossaries_by_lang=merged_glossaries,
            enabled_tiers_by_lang=enabled_tiers_by_lang,
        )
        prompt = _append_prompt_addendum(prompt, lang=config.target_lang, addendum_by_lang=prompt_addendum_by_lang)

        image_data_url = None
        if should_include_image(
            config.image_mode,
            extracted_text,
            ordered.extraction_failed,
            ordered.fragmented,
            lang=config.target_lang,
        ):
            rendered = render_page_image_data_url(config.pdf_path, page_number - 1, max_data_url_bytes=2_000_000)
            image_data_url = rendered.data_url

        translation_call = local_client.create_page_response(
            instructions=instructions,
            prompt_text=prompt,
            effort=config.effort.value,
            image_data_url=image_data_url,
        )
        translated_text = _evaluate_translation_output(translation_call.raw_output, config.target_lang)

        forced_ocr = ocr_pdf_page_text(
            config.pdf_path,
            page_number,
            mode=OcrMode.ALWAYS,
            engine=ocr_engine,
            prefer_header=False,
            lang_hint=config.target_lang.value,
        )
        forced_ocr_text = forced_ocr.text if forced_ocr.chars > 0 else ""

        glossary_block_for_verifier = _append_glossary_prompt_for_audit(
            "BASE",
            lang=config.target_lang,
            source_text=glossary_source_text,
            glossaries_by_lang=merged_glossaries,
            enabled_tiers_by_lang=enabled_tiers_by_lang,
        ).replace("BASE\n", "", 1)
        verifier_prompt = _verifier_prompt(
            target_lang=config.target_lang,
            page_number=page_number,
            extracted_source=extracted_text,
            forced_ocr_source=forced_ocr_text,
            translated_output=translated_text,
            glossary_block=glossary_block_for_verifier,
            prompt_addendum=addendum,
            include_excerpts=include_excerpts,
            excerpt_max_chars=excerpt_max_chars,
        )
        verifier_payload = _call_verifier_with_retries(client=local_client, prompt_text=verifier_prompt)
        for finding in _normalize_findings(verifier_payload):
            findings_payload.append(
                {
                    "page_number": page_number,
                    "issue_type": finding.issue_type,
                    "severity": finding.severity,
                    "evidence": finding.evidence if include_excerpts else "omitted due to privacy",
                    "explanation": finding.explanation,
                    "recommended_fix": finding.recommended_fix,
                }
            )
        raw_suggestions = verifier_payload.get("glossary_suggestions")
        if isinstance(raw_suggestions, list):
            for suggestion in raw_suggestions:
                if not isinstance(suggestion, dict):
                    continue
                source_text = str(suggestion.get("source_text", "") or "").strip()
                preferred_translation = str(suggestion.get("preferred_translation", "") or "").strip()
                if source_text == "" or preferred_translation == "":
                    continue
                glossary_suggestions.append(
                    {
                        "source_text": source_text,
                        "preferred_translation": preferred_translation,
                        "target_lang": str(suggestion.get("target_lang", config.target_lang.value) or config.target_lang.value)
                        .strip()
                        .upper(),
                        "source_lang": str(suggestion.get("source_lang", "PT") or "PT").strip().upper(),
                        "match_mode": str(suggestion.get("match_mode", "exact") or "exact").strip().lower(),
                        "tier": int(suggestion.get("tier", 2) or 2),
                        "page_number": page_number,
                    }
                )
        addendum_suggestion = str(verifier_payload.get("prompt_addendum_suggestion", "") or "").strip()
        if addendum_suggestion:
            prompt_addendum_suggestions.append(addendum_suggestion)

        if progress_callback:
            progress_callback(
                int((idx / float(sampled_total)) * 100.0),
                f"Completed page {page_number} ({idx}/{sampled_total})",
            )

    now_iso = datetime.now().replace(microsecond=0).isoformat()
    report = {
        "generated_at_iso": now_iso,
        "pdf_path": str(config.pdf_path),
        "target_lang": config.target_lang.value,
        "sampled_pages": sampled_pages,
        "seed_material": seed_material,
        "user_seed": user_seed,
        "findings": findings_payload,
    }
    suggestions = {
        "glossary_suggestions": glossary_suggestions,
        "prompt_addendum_suggestions": prompt_addendum_suggestions,
    }

    paths = build_output_paths(config.output_dir, config.pdf_path, config.target_lang)
    paths.run_dir.mkdir(parents=True, exist_ok=True)
    report_json_path = paths.run_dir / "calibration_report.json"
    report_md_path = paths.run_dir / "calibration_report.md"
    suggestions_json_path = paths.run_dir / "calibration_suggestions.json"
    _write_json(report_json_path, report)
    report_md_path.write_text(_build_markdown_report(report), encoding="utf-8")
    _write_json(suggestions_json_path, suggestions)
    return {
        "report": report,
        "suggestions": suggestions,
        "report_json_path": report_json_path,
        "report_md_path": report_md_path,
        "suggestions_json_path": suggestions_json_path,
    }
