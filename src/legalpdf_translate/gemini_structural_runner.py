"""Runtime page runner, persistence, and assembly bridge for gemini_structural_v1."""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Callable, Mapping, Sequence

from .arabic_pre_tokenize import (
    extract_locked_tokens,
    is_portuguese_month_date_token,
    pretokenize_arabic_source,
)
from .gemini_structural_schema import (
    PageStructuralDocument,
    StructuralValidationError,
    build_structural_page_prompt,
    build_structural_retry_prompt,
    build_structural_system_instructions,
    gemini_structural_response_format,
    parse_and_validate_structural_page,
)
from .openai_client import ApiCallError
from .provider_client import is_provider_auth_failure
from .source_structural_evidence import (
    HeaderCrestAsset,
    SourceStructuralEvidence,
    extract_source_structural_evidence,
)
from .structural_docx_assembler import StructuralPageBundle, assemble_structural_docx
from .types import ImageMode, PageStatus, RunConfig, TargetLang
from .usage_accounting import accounting_context

STRUCTURAL_MAX_OUTPUT_TOKENS = 65536


def structural_json_path(pages_dir: Path, page_number: int) -> Path:
    return pages_dir / f"page_{page_number:04d}.structural.json"


def structural_evidence_path(pages_dir: Path, page_number: int) -> Path:
    return pages_dir / f"page_{page_number:04d}.evidence.json"


def structural_pages_available(pages_dir: Path, page_numbers: Sequence[int]) -> bool:
    return bool(page_numbers) and all(structural_json_path(pages_dir, num).is_file() for num in page_numbers)


def _persist_crest_asset(run_dir: Path, asset: HeaderCrestAsset | None) -> str | None:
    if asset is None:
        return None
    assets_dir = run_dir / "structural_assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    ext = "jpg" if asset.ext == "jpeg" else asset.ext
    filename = f"crest_{asset.sha256[:16]}.{ext}"
    dest = assets_dir / filename
    if not dest.exists():
        tmp = assets_dir / f".{filename}.tmp"
        tmp.write_bytes(asset.image_bytes)
        tmp.replace(dest)
    return filename


def _load_crest_asset(run_dir: Path, ev_payload: Mapping[str, Any]) -> HeaderCrestAsset | None:
    filename = str(ev_payload.get("crest_filename") or "").strip()
    if not filename:
        return None
    asset_path = run_dir / "structural_assets" / filename
    if not asset_path.is_file():
        return None
    try:
        raw = asset_path.read_bytes()
    except OSError:
        return None
    ext = asset_path.suffix.lstrip(".").lower() or "png"
    bbox_vals = ev_payload.get("crest_bbox_norm") or [0.4, 0.03, 0.6, 0.1]
    bbox_tuple = tuple(float(v) for v in bbox_vals[:4])
    if len(bbox_tuple) != 4:
        bbox_tuple = (0.4, 0.03, 0.6, 0.1)
    return HeaderCrestAsset(
        image_bytes=raw,
        ext="jpeg" if ext == "jpg" else ext,
        sha256=str(ev_payload.get("crest_sha256") or ""),
        width_pt=float(ev_payload.get("crest_width_pt") or 60.0),
        height_pt=float(ev_payload.get("crest_height_pt") or 48.0),
        bbox_norm=bbox_tuple,  # type: ignore[arg-type]
    )


def save_page_structural_artifacts(
    *,
    run_dir: Path,
    pages_dir: Path,
    page_number: int,
    evidence: SourceStructuralEvidence,
    document: PageStructuralDocument,
    flat_text: str,
) -> None:
    pages_dir.mkdir(parents=True, exist_ok=True)
    crest_filename = _persist_crest_asset(run_dir, evidence.crest_asset)
    ev_meta: dict[str, Any] = {
        "page_number": int(page_number),
        "width_pt": float(evidence.page_width_pt),
        "height_pt": float(evidence.page_height_pt),
        "suggested_archetype": evidence.suggested_archetype,
        "crest_filename": crest_filename or "",
    }
    if evidence.crest_asset is not None:
        ev_meta.update(
            {
                "crest_sha256": evidence.crest_asset.sha256,
                "crest_width_pt": evidence.crest_asset.width_pt,
                "crest_height_pt": evidence.crest_asset.height_pt,
                "crest_bbox_norm": list(evidence.crest_asset.bbox_norm),
            }
        )
    structural_evidence_path(pages_dir, page_number).write_text(
        json.dumps(ev_meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    structural_json_path(pages_dir, page_number).write_text(
        document.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (pages_dir / f"page_{page_number:04d}.txt").write_text(flat_text, encoding="utf-8")


def load_structural_bundles(
    *,
    run_dir: Path,
    pages_dir: Path,
    page_numbers: Sequence[int],
) -> list[StructuralPageBundle]:
    bundles: list[StructuralPageBundle] = []
    for num in page_numbers:
        ir_path = structural_json_path(pages_dir, num)
        doc = PageStructuralDocument.model_validate_json(ir_path.read_text(encoding="utf-8"))
        ev_path = structural_evidence_path(pages_dir, num)
        width_pt = 595.3
        height_pt = 841.9
        crest_asset: HeaderCrestAsset | None = None
        if ev_path.is_file():
            ev_data = json.loads(ev_path.read_text(encoding="utf-8"))
            width_pt = float(ev_data.get("width_pt") or width_pt)
            height_pt = float(ev_data.get("height_pt") or height_pt)
            crest_asset = _load_crest_asset(run_dir, ev_data)
        bundles.append(
            StructuralPageBundle(
                page_number=int(num),
                document=doc,
                width_pt=width_pt,
                height_pt=height_pt,
                crest_asset=crest_asset,
            )
        )
    return bundles


def assemble_structural_output(
    *,
    run_dir: Path,
    pages_dir: Path,
    output_path: Path,
    page_numbers: Sequence[int],
    lang: TargetLang,
    page_breaks: bool,
    strip_bidi_controls: bool,
    stats: dict[str, int] | None = None,
) -> Path:
    bundles = load_structural_bundles(run_dir=run_dir, pages_dir=pages_dir, page_numbers=page_numbers)
    return assemble_structural_docx(
        bundles,
        output_path,
        lang=lang,
        page_breaks=page_breaks,
        strip_bidi_controls=strip_bidi_controls,
        stats=stats,
    )


def summarize_structural_run(bundles: Sequence[StructuralPageBundle]) -> dict[str, Any]:
    archetypes: dict[str, int] = {}
    table_count = 0
    two_col_count = 0
    metadata_band_count = 0
    header_sections = 0
    footer_sections = 0
    crest_pages = 0
    for idx, b in enumerate(bundles):
        arch = b.document.page_archetype
        archetypes[arch] = archetypes.get(arch, 0) + 1
        if idx == 0 or b.document.document_starts_here:
            if b.document.header_stationery.present:
                header_sections += 1
            if b.document.footer_stationery.present:
                footer_sections += 1
        if b.crest_asset is not None and b.document.header_stationery.center_crest_present:
            crest_pages += 1
        for r in b.document.regions:
            if r.kind == "table":
                table_count += 1
            elif r.kind == "two_col_panel":
                two_col_count += 1
            elif r.kind == "metadata_rule_band":
                metadata_band_count += 1
    return {
        "protocol": "gemini_structural_v1",
        "page_count": len(bundles),
        "archetypes": archetypes,
        "table_region_count": table_count,
        "two_col_region_count": two_col_count,
        "metadata_rule_band_count": metadata_band_count,
        "header_stationery_sections": header_sections,
        "footer_stationery_sections": footer_sections,
        "crest_embedded_pages": crest_pages,
    }


def execute_structural_page(
    workflow: Any,
    *,
    client: Any,
    config: RunConfig,
    paths: Any,
    page_number: int,
    total_pages: int,
    source_text: str,
    glossary_source_text: str,
    context_text: str | None,
    image_data_url: str | None,
    image_detail: str,
    attempt1_effort: Any,
    page_metadata: dict[str, Any],
    usage_payload: dict[str, Any],
    started_monotonic: float,
    page_request_started: float,
    request_timeout_budget_seconds: float,
    expected_ar_tokens: Sequence[str] | None = None,
) -> Any:
    """Execute one multimodal gemini_structural_v1 page translation + validation + artifact commit."""
    from .workflow import _PageOutcome

    resolved_expected_tokens: list[str] = list(expected_ar_tokens or [])
    effective_source_text = source_text
    if config.target_lang == TargetLang.AR and source_text.strip() and expected_ar_tokens is None:
        effective_source_text = pretokenize_arabic_source(source_text)
        resolved_expected_tokens = [
            tok
            for tok in extract_locked_tokens(effective_source_text)
            if not is_portuguese_month_date_token(tok)
        ]
        page_metadata["ar_locked_tokens_expected"] = int(len(resolved_expected_tokens))

    evidence = extract_source_structural_evidence(config.pdf_path, page_number - 1)
    glossary_prompt = workflow._append_glossary_prompt(
        "",
        config.target_lang,
        source_text=glossary_source_text,
        page_index=page_number,
    )
    addendum = workflow._append_prompt_addendum("", config.target_lang)
    instructions = build_structural_system_instructions(config.target_lang)
    original_prompt = build_structural_page_prompt(
        lang=config.target_lang,
        page_number=page_number,
        total_pages=total_pages,
        source_text=effective_source_text,
        geometry_hints=evidence.prompt_hints(),
        context_text=context_text,
        glossary_prompt=glossary_prompt,
        prompt_addendum=addendum,
    )
    response_format = gemini_structural_response_format()
    prompt_text = original_prompt
    effort = attempt1_effort
    api_calls_count = 0
    retry_used = False

    def _finalize(api_calls: int) -> None:
        page_metadata["api_calls_count"] = int(api_calls)
        page_metadata["translate_seconds"] = round(
            float(page_metadata.get("attempt1_seconds", 0.0) or 0.0)
            + float(page_metadata.get("attempt2_seconds", 0.0) or 0.0),
            3,
        )
        page_metadata["estimated_cost"] = workflow._estimate_cost_if_available(
            total_input_tokens=int(page_metadata.get("input_tokens", 0) or 0),
            total_output_tokens=int(page_metadata.get("output_tokens", 0) or 0),
            total_reasoning_tokens=int(page_metadata.get("reasoning_tokens", 0) or 0),
        )
        page_metadata["ended_at_iso"] = workflow._utc_now()
        page_metadata["wall_seconds"] = round(time.perf_counter() - started_monotonic, 3)

    if not effective_source_text.strip() and image_data_url is None:
        page_metadata["source_route_reason"] = "source_text_and_image_unavailable"
        _finalize(0)
        return _PageOutcome(
            status=PageStatus.FAILED,
            image_used=False,
            retry_used=False,
            usage=usage_payload,
            error="source_unavailable",
            page_metadata=page_metadata,
        )

    for attempt in (1, 2):
        remaining = workflow._remaining_request_budget_seconds(
            started_at=page_request_started,
            total_budget_seconds=request_timeout_budget_seconds,
        )
        if remaining <= 0.0:
            page_metadata[f"attempt{attempt}_seconds"] = 0.0
            page_metadata["exception_class"] = "APITimeoutError"
            _finalize(api_calls_count)
            return _PageOutcome(
                status=PageStatus.FAILED,
                image_used=bool(image_data_url),
                retry_used=retry_used,
                usage=usage_payload,
                error="runtime_failure",
                page_metadata=page_metadata,
            )

        purpose = "translation" if attempt == 1 else "correction"
        started_call = time.perf_counter()
        try:
            with accounting_context(workflow._dispatch_accounting, purpose=purpose, page_number=page_number):
                result = client.create_page_response(
                    instructions=instructions,
                    prompt_text=prompt_text,
                    effort=effort.value if hasattr(effort, "value") else str(effort),
                    image_data_url=image_data_url,
                    image_detail=image_detail,
                    response_format=response_format,
                    max_output_tokens=STRUCTURAL_MAX_OUTPUT_TOKENS,
                    timeout_seconds=remaining,
                )
            page_metadata[f"attempt{attempt}_seconds"] = round(time.perf_counter() - started_call, 3)
            api_calls_count += 1
        except ApiCallError as exc:
            page_metadata[f"attempt{attempt}_seconds"] = round(time.perf_counter() - started_call, 3)
            api_calls_count += 1
            page_metadata["status_code"] = exc.status_code
            page_metadata["exception_class"] = exc.exception_class
            page_metadata["transport_retries_count"] = int(exc.transport_retries_count)
            page_metadata["last_backoff_seconds"] = float(exc.last_backoff_seconds)
            page_metadata["backoff_wait_seconds_total"] = float(exc.total_backoff_seconds)
            page_metadata["rate_limit_hit"] = bool(exc.rate_limit_hit)
            _finalize(api_calls_count)
            failure_error = (
                "authentication_failure"
                if is_provider_auth_failure(
                    workflow._translation_provider,
                    exception_class=exc.exception_class,
                    status_code=exc.status_code,
                    message=str(exc),
                )
                else ("cancelled" if workflow._cancel_event.is_set() else "runtime_failure")
            )
            return _PageOutcome(
                status=PageStatus.FAILED,
                image_used=bool(image_data_url),
                retry_used=retry_used,
                usage=usage_payload,
                error=failure_error,
                page_metadata=page_metadata,
            )

        usage_payload[f"attempt_{attempt}"] = result.usage
        page_metadata["openai_request_id"] = result.response_id or ""
        page_metadata["transport_retries_count"] = int(result.transport_retries_count)
        page_metadata["last_backoff_seconds"] = float(result.last_backoff_seconds)
        page_metadata["backoff_wait_seconds_total"] = float(result.total_backoff_seconds)
        page_metadata["rate_limit_hit"] = bool(result.rate_limit_hit)
        workflow._accumulate_usage_totals(page_metadata, result.usage)

        try:
            structural_doc, flat_text, stats = parse_and_validate_structural_page(
                result.raw_output,
                lang=config.target_lang,
                source_text=effective_source_text,
                expected_ar_tokens=resolved_expected_tokens,
            )
            page_metadata["structural_protocol"] = "gemini_structural_v1"
            page_metadata["structural_archetype"] = stats["archetype"]
            page_metadata["structural_region_count"] = stats["region_count"]
            page_metadata["ar_locked_token_autofix_applied"] = int(stats.get("autofix_applied_count", 0) or 0)
            save_page_structural_artifacts(
                run_dir=paths.run_dir,
                pages_dir=paths.pages_dir,
                page_number=page_number,
                evidence=evidence,
                document=structural_doc,
                flat_text=flat_text,
            )
            _finalize(api_calls_count)
            return _PageOutcome(
                status=PageStatus.DONE,
                image_used=bool(image_data_url),
                retry_used=retry_used,
                usage=usage_payload,
                error=None,
                page_metadata=page_metadata,
            )
        except StructuralValidationError as exc:
            page_metadata["validator_failed"] = True
            page_metadata["retry_reason"] = exc.code
            defect_detail = str(
                exc.details.get("error_summary")
                or exc.details.get("reason")
                or exc.details.get("kind")
                or exc.code
            ).strip()
            page_metadata["validator_defect_reason"] = defect_detail[:240]
            if attempt == 2:
                _finalize(api_calls_count)
                return _PageOutcome(
                    status=PageStatus.FAILED,
                    image_used=bool(image_data_url),
                    retry_used=True,
                    usage=usage_payload,
                    error="compliance_failure",
                    page_metadata=page_metadata,
                )
            retry_used = True
            effort = workflow._resolve_retry_effort(
                config=config,
                retry_reason=exc.code,
                attempt1_effort=attempt1_effort,
            )
            page_metadata["attempt2_effort"] = effort.value
            prompt_text = build_structural_retry_prompt(
                original_prompt=original_prompt,
                defect_code=exc.code,
                defect_reason=defect_detail or exc.code,
                lang=config.target_lang,
                expected_ar_tokens=resolved_expected_tokens,
            )
