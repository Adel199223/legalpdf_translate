"""Shared backend service layer for interpretation-only workflows."""

from __future__ import annotations

from contextlib import closing
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .honorarios_docx import (
    HonorariosDraft,
    HonorariosKind,
    build_interpretation_honorarios_draft,
    default_honorarios_filename,
    default_interpretation_recipient_block,
    generate_honorarios_docx,
)
from .joblog_db import insert_job_run, list_job_runs, open_job_log, update_job_run
from .joblog_flow import (
    JobLogSavedResult,
    JobLogSeed,
    build_blank_interpretation_seed,
    build_interpretation_notice_diagnostics_text,
    build_interpretation_seed_from_notification_pdf,
    build_interpretation_seed_from_photo_screenshot,
    build_joblog_saved_result,
    build_seed_from_joblog_row,
    build_joblog_settings_save_bundle,
    hydrate_joblog_seed,
    merge_payload_into_joblog_settings,
    normalize_joblog_payload,
)
from .metadata_autofill import (
    MetadataAutofillConfig,
    MetadataExtractionDiagnostics,
    extract_interpretation_notification_metadata_from_pdf_with_diagnostics,
    extract_interpretation_photo_metadata_from_image,
    metadata_config_from_settings,
)
from .ocr_engine import OcrEngineConfig, candidate_ocr_api_env_names, local_ocr_available, resolve_ocr_api_key
from .types import OcrApiProvider
from .user_profile import PROFILE_FIELD_LABELS, PROFILE_REQUIRED_FIELDS, UserProfile, distance_for_city, primary_profile
from .user_settings import (
    load_gui_settings_from_path,
    load_joblog_settings_from_path,
    load_profile_settings_from_path,
    save_joblog_settings_to_path,
    save_profile_settings_to_path,
)
from .word_automation import WordAutomationResult, export_docx_to_pdf_in_word, probe_word_pdf_export_support

INITIAL_HONORARIOS_PDF_EXPORT_TIMEOUT_SECONDS = 45.0
RETRY_HONORARIOS_PDF_EXPORT_TIMEOUT_SECONDS = 90.0


def _path_text(path: Path | None) -> str | None:
    if path is None:
        return None
    return str(path.expanduser().resolve())


def serialize_joblog_seed(seed: JobLogSeed) -> dict[str, Any]:
    payload = asdict(seed)
    payload["pdf_path"] = _path_text(seed.pdf_path)
    payload["output_docx"] = _path_text(seed.output_docx)
    payload["partial_docx"] = _path_text(seed.partial_docx)
    return payload


def serialize_joblog_saved_result(result: JobLogSavedResult) -> dict[str, Any]:
    payload = asdict(result)
    payload["translated_docx_path"] = _path_text(result.translated_docx_path)
    payload["payload"] = dict(result.payload or {})
    return payload


def serialize_honorarios_draft(draft: HonorariosDraft) -> dict[str, Any]:
    payload = asdict(draft)
    payload["kind"] = draft.kind.value
    payload["profile"] = {
        "id": draft.profile.id,
        "document_name": draft.profile.document_name,
        "email": draft.profile.email,
        "travel_origin_label": draft.profile.travel_origin_label,
    }
    return payload


def serialize_joblog_row(row: Mapping[str, Any]) -> dict[str, Any]:
    if hasattr(row, "keys"):
        return {str(key): row[key] for key in row.keys()}
    return {str(key): value for key, value in dict(row).items()}


def _seed_from_payload(seed_payload: Mapping[str, Any] | None) -> JobLogSeed:
    if seed_payload is None:
        return build_blank_interpretation_seed()
    return hydrate_joblog_seed(seed_payload)


def _metadata_config_from_settings_path(settings_path: Path) -> tuple[dict[str, Any], MetadataAutofillConfig]:
    joblog_settings = load_joblog_settings_from_path(settings_path)
    return joblog_settings, metadata_config_from_settings(joblog_settings)


def _capability_flags_from_settings_path(settings_path: Path) -> dict[str, Any]:
    joblog_settings = load_joblog_settings_from_path(settings_path)
    metadata_config = metadata_config_from_settings(joblog_settings)
    ocr_engine_config = OcrEngineConfig(
        policy=metadata_config.ocr_engine_policy,
        api_provider=metadata_config.ocr_api_provider,
        api_base_url=metadata_config.ocr_api_base_url,
        api_model=metadata_config.ocr_api_model,
        api_key_env_name=metadata_config.ocr_api_key_env_name,
        api_timeout_seconds=float(metadata_config.ocr_api_timeout_seconds),
    )
    api_provider = (
        OcrApiProvider.GEMINI
        if str(joblog_settings.get("ocr_api_provider", "openai")).strip().lower() == "gemini"
        else OcrApiProvider.OPENAI
    )
    return {
        "ocr": {
            "mode": metadata_config.ocr_mode.value,
            "engine_policy": metadata_config.ocr_engine_policy.value,
            "provider": metadata_config.ocr_api_provider.value,
            "local_available": local_ocr_available(),
            "api_configured": resolve_ocr_api_key(ocr_engine_config) is not None,
            "api_env_names": list(candidate_ocr_api_env_names(ocr_engine_config)),
            "default_env_name": metadata_config.ocr_api_key_env_name,
            "provider_default_env_name": metadata_config.ocr_api_key_env_name
            if metadata_config.ocr_api_key_env_name
            else (
                "OPENAI_API_KEY"
                if api_provider == OcrApiProvider.OPENAI
                else "GEMINI_API_KEY"
            ),
        },
        "word_pdf_export": {
            "host_bound": True,
        },
        "gmail": {
            "status": "unavailable",
            "reason": "out_of_scope_for_shadow_v1",
        },
        "translation": {
            "status": "unavailable",
            "reason": "out_of_scope_for_shadow_v1",
        },
        "browser_extension": {
            "status": "unavailable",
            "reason": "out_of_scope_for_shadow_v1",
        },
    }


def build_interpretation_capability_flags(*, settings_path: Path) -> dict[str, Any]:
    return _capability_flags_from_settings_path(settings_path)


def _profile_missing_fields(profile: UserProfile) -> list[str]:
    missing: list[str] = []
    for field_name in PROFILE_REQUIRED_FIELDS:
        if str(getattr(profile, field_name, "") or "").strip():
            continue
        missing.append(PROFILE_FIELD_LABELS.get(field_name, field_name))
    return missing


def _current_profile(
    *,
    settings_path: Path,
    profile_id: str | None = None,
) -> tuple[list[UserProfile], str, UserProfile]:
    profiles, primary_profile_id = load_profile_settings_from_path(settings_path)
    selected_id = str(profile_id or primary_profile_id or "").strip() or primary_profile_id
    profile = primary_profile(profiles, selected_id)
    return profiles, primary_profile_id, profile


def _persist_interpretation_distance(
    *,
    settings_path: Path,
    city: str,
    distance_value: float,
    profile_id: str | None = None,
) -> None:
    city_clean = " ".join(str(city or "").split()).strip()
    if not city_clean:
        return
    profiles, primary_profile_id, profile = _current_profile(settings_path=settings_path, profile_id=profile_id)
    existing = distance_for_city(profile, city_clean)
    if existing is not None and abs(float(existing) - float(distance_value)) < 1e-9:
        return
    profile.travel_distances_by_city[city_clean] = float(distance_value)
    save_profile_settings_to_path(
        settings_path,
        profiles=profiles,
        primary_profile_id=primary_profile_id,
    )


def _default_interpretation_raw_values(form_values: Mapping[str, Any]) -> dict[str, str]:
    service_date = str(form_values.get("service_date", "") or "").strip()
    translation_date = str(form_values.get("translation_date", "") or service_date).strip() or service_date
    return {
        "translation_date": translation_date,
        "job_type": "Interpretation",
        "case_number": str(form_values.get("case_number", "") or "").strip(),
        "court_email": str(form_values.get("court_email", "") or "").strip(),
        "case_entity": str(form_values.get("case_entity", "") or "").strip(),
        "case_city": str(form_values.get("case_city", "") or "").strip(),
        "service_entity": str(form_values.get("service_entity", "") or "").strip(),
        "service_city": str(form_values.get("service_city", "") or "").strip(),
        "service_date": service_date,
        "travel_km_outbound": str(form_values.get("travel_km_outbound", "") or "").strip(),
        "travel_km_return": str(form_values.get("travel_km_return", "") or form_values.get("travel_km_outbound", "") or "").strip(),
        "lang": str(form_values.get("lang", "") or "").strip(),
        "target_lang": str(form_values.get("target_lang", "") or "").strip(),
        "run_id": str(form_values.get("run_id", "") or "").strip(),
        "pages": str(form_values.get("pages", "") or "").strip(),
        "word_count": str(form_values.get("word_count", "") or "").strip(),
        "total_tokens": str(form_values.get("total_tokens", "") or "").strip(),
        "rate_per_word": str(form_values.get("rate_per_word", "") or "").strip(),
        "expected_total": str(form_values.get("expected_total", "") or "").strip(),
        "amount_paid": str(form_values.get("amount_paid", "") or "").strip(),
        "api_cost": str(form_values.get("api_cost", "") or "").strip(),
        "estimated_api_cost": str(form_values.get("estimated_api_cost", "") or "").strip(),
        "quality_risk_score": str(form_values.get("quality_risk_score", "") or "").strip(),
        "profit": str(form_values.get("profit", "") or "").strip(),
    }


def build_shadow_bootstrap(
    *,
    settings_path: Path,
    job_log_db_path: Path,
    history_limit: int = 25,
) -> dict[str, Any]:
    gui_settings = load_gui_settings_from_path(settings_path)
    profiles, primary_profile_id = load_profile_settings_from_path(settings_path)
    history = list_interpretation_history(db_path=job_log_db_path, limit=history_limit)
    return {
        "status": "ok",
        "normalized_payload": {
            "blank_seed": serialize_joblog_seed(build_blank_interpretation_seed()),
            "profiles": [
                {
                    "id": profile.id,
                    "document_name": profile.document_name,
                    "email": profile.email,
                    "travel_origin_label": profile.travel_origin_label,
                    "travel_distances_by_city": dict(profile.travel_distances_by_city),
                }
                for profile in profiles
            ],
            "primary_profile_id": primary_profile_id,
            "gui_settings": {
                "ui_theme": gui_settings.get("ui_theme"),
                "ui_scale": gui_settings.get("ui_scale"),
            },
            "history": history,
        },
        "diagnostics": {},
        "capability_flags": _capability_flags_from_settings_path(settings_path),
    }


def autofill_interpretation_from_notification_pdf(
    *,
    pdf_path: Path,
    settings_path: Path,
) -> dict[str, Any]:
    joblog_settings, metadata_config = _metadata_config_from_settings_path(settings_path)
    extraction = extract_interpretation_notification_metadata_from_pdf_with_diagnostics(
        pdf_path.expanduser().resolve(),
        vocab_cities=list(joblog_settings["vocab_cities"]),
        config=metadata_config,
    )
    seed = build_interpretation_seed_from_notification_pdf(
        pdf_path=pdf_path.expanduser().resolve(),
        suggestion=extraction.suggestion,
        vocab_court_emails=list(joblog_settings["vocab_court_emails"]),
    )
    extracted = list(extraction.diagnostics.extracted_fields)
    return {
        "status": "ok" if extracted else "failed",
        "normalized_payload": serialize_joblog_seed(seed),
        "diagnostics": {
            "metadata_extraction": extraction.diagnostics.to_payload(),
            "metadata_extraction_text": build_interpretation_notice_diagnostics_text(extraction.diagnostics),
        },
        "capability_flags": _capability_flags_from_settings_path(settings_path),
    }


def autofill_interpretation_from_photo(
    *,
    image_path: Path,
    settings_path: Path,
) -> dict[str, Any]:
    joblog_settings, metadata_config = _metadata_config_from_settings_path(settings_path)
    suggestion = extract_interpretation_photo_metadata_from_image(
        image_path.expanduser().resolve(),
        vocab_cities=list(joblog_settings["vocab_cities"]),
        config=metadata_config,
    )
    seed = build_interpretation_seed_from_photo_screenshot(
        suggestion=suggestion,
        vocab_court_emails=list(joblog_settings["vocab_court_emails"]),
    )
    extracted_fields = [
        field_name
        for field_name in ("case_entity", "case_city", "case_number", "service_date")
        if str(getattr(suggestion, field_name, "") or "").strip()
    ]
    return {
        "status": "ok" if extracted_fields else "failed",
        "normalized_payload": serialize_joblog_seed(seed),
        "diagnostics": {
            "metadata_extraction": {
                "source": "photo",
                "extracted_fields": extracted_fields,
            }
        },
        "capability_flags": _capability_flags_from_settings_path(settings_path),
    }


def normalize_interpretation_form_payload(
    *,
    seed_payload: Mapping[str, Any] | None,
    form_values: Mapping[str, Any],
    settings_path: Path,
    service_same_checked: bool,
    use_service_location_in_honorarios_checked: bool,
    include_transport_sentence_in_honorarios_checked: bool,
) -> dict[str, Any]:
    seed = _seed_from_payload(seed_payload)
    return normalize_joblog_payload(
        seed=seed,
        raw_values=_default_interpretation_raw_values(form_values),
        service_same_checked=service_same_checked,
        use_service_location_in_honorarios_checked=use_service_location_in_honorarios_checked,
        include_transport_sentence_in_honorarios_checked=include_transport_sentence_in_honorarios_checked,
    )


def save_interpretation_row(
    *,
    settings_path: Path,
    job_log_db_path: Path,
    form_values: Mapping[str, Any],
    seed_payload: Mapping[str, Any] | None = None,
    row_id: int | None = None,
    service_same_checked: bool = True,
    use_service_location_in_honorarios_checked: bool = False,
    include_transport_sentence_in_honorarios_checked: bool = True,
    profile_id: str | None = None,
) -> dict[str, Any]:
    seed = _seed_from_payload(seed_payload)
    payload = normalize_joblog_payload(
        seed=seed,
        raw_values=_default_interpretation_raw_values(form_values),
        service_same_checked=service_same_checked,
        use_service_location_in_honorarios_checked=use_service_location_in_honorarios_checked,
        include_transport_sentence_in_honorarios_checked=include_transport_sentence_in_honorarios_checked,
    )
    if include_transport_sentence_in_honorarios_checked:
        city = str(payload.get("service_city", "") or "").strip()
        distance_value = payload.get("travel_km_outbound")
        if city and isinstance(distance_value, (int, float)):
            _persist_interpretation_distance(
                settings_path=settings_path,
                city=city,
                distance_value=float(distance_value),
                profile_id=profile_id,
            )

    with closing(open_job_log(job_log_db_path)) as conn:
        if row_id is not None:
            update_job_run(conn, row_id=int(row_id), values=payload)
            saved_row_id = int(row_id)
        else:
            insert_payload = {
                "completed_at": seed.completed_at or datetime.now().replace(microsecond=0).isoformat(),
                **payload,
                "output_docx_path": _path_text(seed.output_docx),
                "partial_docx_path": _path_text(seed.partial_docx),
            }
            saved_row_id = insert_job_run(conn, insert_payload)

    settings = load_joblog_settings_from_path(settings_path)
    merged_settings = merge_payload_into_joblog_settings(
        settings,
        payload,
        service_equals_case_by_default=bool(service_same_checked),
    )
    save_joblog_settings_to_path(
        settings_path,
        build_joblog_settings_save_bundle(merged_settings),
    )
    saved_result = build_joblog_saved_result(
        row_id=saved_row_id,
        payload=payload,
        translated_docx_path=seed.output_docx or seed.partial_docx,
    )
    return {
        "status": "ok",
        "normalized_payload": dict(payload),
        "diagnostics": {},
        "saved_result": serialize_joblog_saved_result(saved_result),
        "capability_flags": _capability_flags_from_settings_path(settings_path),
    }


def list_interpretation_history(*, db_path: Path, limit: int = 100) -> list[dict[str, Any]]:
    with closing(open_job_log(db_path)) as conn:
        rows = list_job_runs(conn, limit=max(1, int(limit)))
    items: list[dict[str, Any]] = []
    for row in rows:
        payload = serialize_joblog_row(row)
        if str(payload.get("job_type", "") or "").strip().casefold() != "interpretation":
            continue
        items.append(
            {
                "row": payload,
                "seed": serialize_joblog_seed(build_seed_from_joblog_row(payload)),
            }
        )
    return items


def _build_pdf_export_response(
    *,
    docx_path: Path,
    pdf_path: Path,
    automation: WordAutomationResult,
) -> dict[str, Any]:
    return {
        "docx_path": _path_text(docx_path),
        "pdf_path": _path_text(pdf_path) if automation.ok else None,
        "ok": bool(automation.ok),
        "failure_code": str(automation.failure_code or "").strip(),
        "failure_message": str(automation.message or "").strip(),
        "failure_details": str(automation.details or "").strip(),
        "elapsed_ms": int(automation.elapsed_ms),
    }


def _run_pdf_export_with_retry(*, docx_path: Path, pdf_path: Path) -> dict[str, Any]:
    preflight = probe_word_pdf_export_support(timeout_seconds=max(8.0, INITIAL_HONORARIOS_PDF_EXPORT_TIMEOUT_SECONDS))
    if not preflight.ok:
        return _build_pdf_export_response(docx_path=docx_path, pdf_path=pdf_path, automation=preflight)
    result = export_docx_to_pdf_in_word(
        docx_path,
        pdf_path,
        timeout_seconds=INITIAL_HONORARIOS_PDF_EXPORT_TIMEOUT_SECONDS,
    )
    if result.ok:
        return _build_pdf_export_response(docx_path=docx_path, pdf_path=pdf_path, automation=result)
    if str(result.failure_code or "").strip() == "timeout":
        retry_preflight = probe_word_pdf_export_support(
            timeout_seconds=max(8.0, RETRY_HONORARIOS_PDF_EXPORT_TIMEOUT_SECONDS)
        )
        if not retry_preflight.ok:
            return _build_pdf_export_response(docx_path=docx_path, pdf_path=pdf_path, automation=retry_preflight)
        retry_result = export_docx_to_pdf_in_word(
            docx_path,
            pdf_path,
            timeout_seconds=RETRY_HONORARIOS_PDF_EXPORT_TIMEOUT_SECONDS,
        )
        return _build_pdf_export_response(docx_path=docx_path, pdf_path=pdf_path, automation=retry_result)
    return _build_pdf_export_response(docx_path=docx_path, pdf_path=pdf_path, automation=result)


def _build_interpretation_draft_from_form(
    *,
    form_values: Mapping[str, Any],
    settings_path: Path,
    profile_id: str | None = None,
    service_same_checked: bool = True,
) -> HonorariosDraft:
    _profiles, _primary_profile_id, profile = _current_profile(settings_path=settings_path, profile_id=profile_id)
    missing_profile_fields = _profile_missing_fields(profile)
    if missing_profile_fields:
        raise ValueError(
            "Selected profile is missing required fields: "
            + ", ".join(missing_profile_fields)
            + "."
        )
    include_transport_sentence = bool(form_values.get("include_transport_sentence_in_honorarios", True))
    if include_transport_sentence and not profile.travel_origin_label.strip():
        raise ValueError("Selected profile is missing an interpretation travel origin label.")
    case_number = str(form_values.get("case_number", "") or "").strip()
    case_entity = str(form_values.get("case_entity", "") or "").strip()
    case_city = str(form_values.get("case_city", "") or "").strip()
    service_date = str(form_values.get("service_date", "") or "").strip()
    service_entity = str(form_values.get("service_entity", "") or "").strip()
    service_city = str(form_values.get("service_city", "") or "").strip()
    if service_same_checked:
        service_entity = case_entity
        service_city = case_city
    if not case_number:
        raise ValueError("Case number is required.")
    if not case_entity:
        raise ValueError("Case entity is required.")
    if not case_city:
        raise ValueError("Case city is required.")
    if not service_date:
        raise ValueError("Service date is required.")
    if not service_city:
        raise ValueError("Service city is required.")
    travel_km_outbound = float(form_values.get("travel_km_outbound", 0.0) or 0.0)
    if include_transport_sentence and travel_km_outbound <= 0:
        known_distance = distance_for_city(profile, service_city)
        if known_distance is not None:
            travel_km_outbound = float(known_distance)
    recipient_block = (
        str(form_values.get("recipient_block", "") or "").strip()
        or default_interpretation_recipient_block(case_entity, case_city)
    )
    return build_interpretation_honorarios_draft(
        case_number=case_number,
        case_entity=case_entity,
        case_city=case_city,
        service_date=service_date,
        service_entity=service_entity,
        service_city=service_city,
        use_service_location_in_honorarios=bool(form_values.get("use_service_location_in_honorarios", False)),
        include_transport_sentence_in_honorarios=include_transport_sentence,
        travel_km_outbound=travel_km_outbound,
        travel_km_return=float(form_values.get("travel_km_return", travel_km_outbound) or travel_km_outbound or 0.0),
        recipient_block=recipient_block,
        profile=profile,
    )


def export_interpretation_honorarios(
    *,
    settings_path: Path,
    outputs_dir: Path,
    form_values: Mapping[str, Any],
    profile_id: str | None = None,
    output_filename: str | None = None,
    service_same_checked: bool = True,
) -> dict[str, Any]:
    draft = _build_interpretation_draft_from_form(
        form_values=form_values,
        settings_path=settings_path,
        profile_id=profile_id,
        service_same_checked=service_same_checked,
    )
    outputs_dir = outputs_dir.expanduser().resolve()
    outputs_dir.mkdir(parents=True, exist_ok=True)
    requested_name = str(output_filename or "").strip() or default_honorarios_filename(
        draft.case_number,
        kind=HonorariosKind.INTERPRETATION,
    )
    requested_path = (outputs_dir / requested_name).expanduser().resolve()
    docx_path = generate_honorarios_docx(draft, requested_path)
    pdf_export = _run_pdf_export_with_retry(docx_path=docx_path, pdf_path=docx_path.with_suffix(".pdf"))
    status = "ok" if pdf_export["ok"] else "local_only"
    return {
        "status": status,
        "normalized_payload": {
            "docx_path": _path_text(docx_path),
            "pdf_path": pdf_export["pdf_path"],
            "draft": serialize_honorarios_draft(draft),
        },
        "diagnostics": {
            "pdf_export": pdf_export,
        },
        "capability_flags": _capability_flags_from_settings_path(settings_path),
    }


def import_live_profile_settings(
    *,
    shadow_settings_path: Path,
    live_settings_path: Path,
) -> dict[str, Any]:
    profiles, primary_profile_id = load_profile_settings_from_path(live_settings_path)
    save_profile_settings_to_path(
        shadow_settings_path,
        profiles=profiles,
        primary_profile_id=primary_profile_id,
    )
    return {
        "status": "ok",
        "normalized_payload": {
            "primary_profile_id": primary_profile_id,
            "profiles": [
                {
                    "id": profile.id,
                    "document_name": profile.document_name,
                    "email": profile.email,
                    "travel_origin_label": profile.travel_origin_label,
                    "travel_distances_by_city": dict(profile.travel_distances_by_city),
                }
                for profile in profiles
            ],
        },
        "diagnostics": {},
        "capability_flags": _capability_flags_from_settings_path(shadow_settings_path),
    }
