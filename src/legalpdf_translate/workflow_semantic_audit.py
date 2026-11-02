"""Run-owned source evidence and final selection for ordinary semantic audit.

Primary page TXT remains immutable evidence. Only a fully validated separate
audit selection may feed a final DOCX; partial primary exports stay unapproved.
"""
from __future__ import annotations

from dataclasses import fields
import hashlib
import json
from pathlib import Path
import re

from .checkpoint import (ordinary_semantic_audit_recipe, ordinary_semantic_audit_qualification,
                         sha256_of_file, sha256_of_text)


class SemanticIntegrationError(ValueError):
    def __init__(self, code: str):
        self.code = "semantic_audit_" + code
        super().__init__(self.code)


def _fail(code):
    raise SemanticIntegrationError(code) from None


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _owned_directory(run_dir: Path, name: str):
    directory = run_dir / name
    if directory.is_symlink() or directory.resolve().parent != run_dir.resolve():
        _fail("evidence_path_invalid")
    return directory


def fresh_recipe(config, model, policy, *, context_text, context_hash):
    from .pdf_text_order import PRIMARY_PAGE_EVIDENCE_POLICY

    if sha256_of_text(context_text) != context_hash:
        _fail("context_changed")
    recipe = {"version": "ordinary_semantic_audit_v3", "model": model,
            "reasoning_effort": config.effort.value, "effort_policy": config.effort_policy.value,
            "target_language": config.target_lang.value, "max_output_tokens": 32000,
            "timeout_seconds": 480, "ordinary_auto_layout_policy": policy,
            "source_image_policy": "configured_image_mode_v1", "configured_image_mode": config.image_mode.value,
            "context_sha256": context_hash, "context_binding_version": "resolved_context_v1",
            "terminology_policy": "source_matched_primary_terms_v1",
            "source_field_policy": "baseline_label_value_v1",
            "review_protocol": "source_inventory_correct_verify_v1",
            "primary_literal_packaging_version": "lossless_source_components_v3",
            "source_inline_address_join_policy": "source_locative_house_join_v3",
            "semantic_unit_reference_policy": "caller_unit_refs_v1",
            "source_question_row_policy": "baseline_boolean_question_v1",
            "primary_page_evidence_policy": PRIMARY_PAGE_EVIDENCE_POLICY,
            "source_inventory_max_output_tokens": 64000,
            "semantic_source_review_policy": "source_commitment_visual_v9",
            "semantic_page_coverage_policy": "complete_selected_pages_v1"}
    from .semantic_review_model_policy import fresh_semantic_review_model_policy, validate_policy
    model_policy = fresh_semantic_review_model_policy()
    if model_policy is not None:
        recipe["semantic_review_model_policy"] = validate_policy(model_policy)
        recipe["semantic_repair_policy"] = "source_grounded_repair_once_v4"
        recipe["semantic_literal_authority_policy"] = "source_literal_authority_v1"
        recipe["semantic_enclosure_authority_policy"] = "source_enclosure_authority_v1"
        recipe["source_enclosure_identity_policy"] = "bounded_distinct_additions_v1"
        recipe["semantic_enclosure_sequence_repair_policy"] = "initial_enclosure_permutation_replacement_v1"
        recipe["semantic_target_ambiguity_policy"] = "initial_target_ambiguity_repair_v1"
        from .ordinary_auto_layout import frozen_automatic_layout_policy
        if config.strip_bidi_controls is True and policy == frozen_automatic_layout_policy():
            from . import primary_literal_markup as markup
            recipe[markup.KEY] = markup.POLICY
    if (config.ocr_engine.value in {"api", "local_then_api"}
            and config.ocr_api_provider.value == "openai"):
        recipe["ocr_text_transport_policy"] = "openai_ocr_text_envelope_v1"
    return recipe


def capture_context(*, state, run_dir, context_text, context_hash):
    """Keep private resolved context out of checkpoint settings and error strings."""
    recipe = ordinary_semantic_audit_recipe(state.settings)
    if recipe is None or recipe["version"] == "ordinary_semantic_audit_v1":
        return
    if context_text is not None and not isinstance(context_text, str):
        _fail("context_changed")
    text = context_text or ""
    if (context_hash != state.context_hash
            or context_hash != recipe["context_sha256"] or sha256_of_text(text) != context_hash):
        _fail("context_changed")
    payload = {"version": "ordinary_semantic_context_v1", "context_text": text,
               "context_sha256": context_hash, "recipe_sha256": _sha(_encode(recipe))}
    path = _owned_directory(run_dir, "semantic_context.json")
    encoded = _encode(payload)
    if path.is_symlink() or (path.exists() and (not path.is_file() or path.read_bytes() != encoded)):
        _fail("context_evidence_changed")
    if not path.exists():
        with path.open("xb") as handle:
            handle.write(encoded)


def validate_context(*, state, run_dir, context_text=None, context_hash=None):
    """Resume supplies current resolved bytes; offline replay uses only the pack."""
    recipe = ordinary_semantic_audit_recipe(state.settings)
    if recipe is None or recipe["version"] == "ordinary_semantic_audit_v1":
        return ""
    if recipe["context_sha256"] != state.context_hash:
        _fail("context_changed")
    if context_hash is not None and (context_hash != state.context_hash
            or sha256_of_text(context_text) != context_hash):
        _fail("context_changed")
    path = _owned_directory(run_dir, "semantic_context.json")
    try:
        if path.is_symlink():
            _fail("context_evidence_changed")
        raw = path.read_bytes()
        data = json.loads(raw)
    except (OSError, ValueError, UnicodeError):
        _fail("context_evidence_missing_or_changed")
    if (type(data) is not dict
            or set(data) != {"version", "context_text", "context_sha256", "recipe_sha256"}
            or data.get("version") != "ordinary_semantic_context_v1"
            or not isinstance(data.get("context_text"), str)
            or data.get("context_sha256") != state.context_hash
            or sha256_of_text(data["context_text"]) != state.context_hash
            or data.get("recipe_sha256") != _sha(_encode(recipe))
            or _encode(data) != raw
            or (context_hash is not None and data["context_text"] != (context_text or ""))):
        _fail("context_evidence_changed")
    return data["context_text"]


def _validate_terminology(entries, source_text):
    from .glossary import GlossaryEntry
    from .pt_legal_glossary_aliases import source_matches_glossary_entry
    if not isinstance(entries, list) or len(entries) > 50:
        _fail("terminology_evidence_changed")
    total = 0
    for entry in entries:
        if (type(entry) is not dict
                or set(entry) != {"source_text", "preferred_translation", "match_mode", "source_lang", "tier"}
                or any(not isinstance(entry.get(k), str) or not entry[k]
                       for k in ("source_text", "preferred_translation", "match_mode", "source_lang"))
                or entry["match_mode"] not in {"exact", "contains"}
                or entry["source_lang"] not in {"AUTO", "ANY", "PT", "EN", "FR"}
                or type(entry["tier"]) is not int or entry["tier"] not in range(1, 7)
                or not source_matches_glossary_entry(source_text, GlossaryEntry(**entry))):
            _fail("terminology_evidence_changed")
        total += len(entry["source_text"]) + len(entry["preferred_translation"])
    if total > 6000:
        _fail("terminology_evidence_changed")
    return entries


def capture_source(*, state, run_dir, page_number, source_text, original_source_text,
                   expected_ar_tokens, image_data_url, applicable_terminology=(), acronym_rows=(),
                   text_transport_evidence=None, api_ocr_used=False, merged_ocr_source=False, source_witness=None,
                   postal_rows=(), postal_direct=False):
    if state is None:
        return {}
    recipe = ordinary_semantic_audit_recipe(state.settings)
    if recipe is None:
        return {}
    if "ocr_text_transport_policy" in recipe:
        from . import ocr_text_transport as transport
        if api_ocr_used:
            raw_ocr = transport.validate_ref(run_dir=run_dir, pdf_sha256=state.pdf_fingerprint, page=page_number,
                reference=text_transport_evidence, original_source_text=None if (merged_ocr_source or source_witness) else original_source_text)
            if "ocr_visual_source_policy" in recipe and not merged_ocr_source and source_witness is None:
                from .ordinary_ocr_visual_source import eligible_page
                if eligible_page(state.pdf_path, page_number, raw_ocr):
                    _fail("ocr_visual_source_binding")
        elif text_transport_evidence is not None:
            raise transport.OcrTextTransportError("source_binding")
    payload = {"version": "ordinary_semantic_source_v1", "pdf_sha256": state.pdf_fingerprint,
               "recipe_sha256": _sha(_encode(recipe)), "selected_pages": sorted(int(n) for n in state.pages),
               "page_number": page_number, "source_text": source_text,
               "original_source_text": original_source_text,
               "source_text_kind": "pretokenized", "expected_ar_tokens": list(expected_ar_tokens or ()),
               "primary_image_data_url": image_data_url,
               "image_data_url": image_data_url,
               "configured_image_mode": recipe["configured_image_mode"],
               "visual_coverage": "text_only_configured_image_off" if recipe["configured_image_mode"] == "off"
                   else "source_image_available"}
    from .ordinary_source_acronyms import POLICY as acronym_policy
    if recipe.get("primary_page_evidence_policy") == acronym_policy:
        payload["source_acronyms"] = list(acronym_rows)
    if "ocr_text_transport_policy" in recipe and api_ocr_used:
        payload["ocr_text_acquisition"] = {"reference": text_transport_evidence,
            "selected_source_sha256": _sha(original_source_text.encode("utf-8")),
            "composition": "merged_pdf_ocr" if merged_ocr_source else "api_ocr"}
    if source_witness is not None:
        if "ocr_visual_source_policy" not in recipe or not api_ocr_used or merged_ocr_source:
            _fail("ocr_visual_source_binding")
        payload["ocr_text_acquisition"]["composition"] = "verified_source_slots_v1"
        payload["ocr_visual_source"] = source_witness
        _validate_visual_source(state=state, run_dir=run_dir, page_number=page_number, raw=raw_ocr,
                                data=payload, recipe=recipe)
    if recipe["version"] in ("ordinary_semantic_audit_v2", "ordinary_semantic_audit_v3"):
        validate_context(state=state, run_dir=run_dir)
        payload.update(version="ordinary_semantic_source_v2", context_sha256=recipe["context_sha256"],
            source_field_policy=recipe["source_field_policy"],
            applicable_terminology=_validate_terminology(list(applicable_terminology), original_source_text))
    from . import ordinary_source_postal_band as postal_band
    if postal_band.KEY in recipe or postal_rows:
        payload[postal_band.FIELD] = list(postal_rows)
        payload[postal_band.ROUTE] = "direct_text" if postal_direct else "unqualified"
        try:
            postal_band.validate_capture(state, recipe, page_number, payload)
        except ValueError:
            _fail("postal_source_binding")
    directory = _owned_directory(run_dir, "semantic_source")
    directory.mkdir(exist_ok=True)
    path = directory / f"page_{page_number:04d}.json"
    encoded = _encode(payload)
    if path.is_symlink():
        _fail("source_evidence_changed")
    if path.exists():
        if path.read_bytes() != encoded:
            _fail("source_evidence_changed")
    else:
        with path.open("xb") as handle:
            handle.write(encoded)
    return {"semantic_source_sha256": _sha(encoded)}


def _pages(*, state, config, run_dir, pages_dir, primary_context=None):
    from .ordinary_semantic_audit import SemanticAuditPage
    if primary_context is not None:
        from . import primary_literal_markup as markup
        checked = markup.load_context(state=state, run_dir=run_dir)
        if (type(primary_context) is not markup.Context or checked is None
                or primary_context.evidence_sha256 != checked.evidence_sha256
                or markup.encode(primary_context.primary) != markup.encode(checked.primary)
                or markup.encode(primary_context.groups) != markup.encode(checked.groups)):
            markup.fail("context_changed")
        primary_context = checked
    recipe = ordinary_semantic_audit_recipe(state.settings)
    if recipe is None:
        _fail("recipe_missing")
    numbers = sorted(int(n) for n in state.pages)
    if not 1 <= len(numbers) <= 12:
        _fail("review_required_page_limit")
    if (len(numbers) != state.selection_page_count or numbers[0] != state.selection_start_page
            or numbers[-1] != state.selection_end_page
            or any(state.pages[str(n)].get("status") != "done" for n in numbers)):
        _fail("incomplete_selection")
    if (recipe["target_language"] != config.target_lang.value
            or recipe["reasoning_effort"] != config.effort.value
            or recipe["effort_policy"] != config.effort_policy.value
            or sha256_of_file(config.pdf_path) != state.pdf_fingerprint):
        _fail("source_or_recipe_changed")
    directory = _owned_directory(run_dir, "semantic_source")
    pages = []
    from . import ordinary_source_acronyms as acronyms
    acronym_policy = recipe.get("primary_page_evidence_policy") == acronyms.POLICY
    acronym_sources = acronyms.read_selection(config.pdf_path, numbers) if acronym_policy else ()
    if acronym_policy and not acronym_sources:
        _fail("acronym_source_changed")
    resolved_context = validate_context(state=state, run_dir=run_dir)
    context_bound = recipe["version"] in ("ordinary_semantic_audit_v2", "ordinary_semantic_audit_v3")
    terminology = []
    expected_files = {f"page_{n:04d}.json" for n in numbers}
    if not directory.is_dir() or {p.name for p in directory.iterdir()} != expected_files:
        _fail("source_evidence_missing_or_changed")
    for number in numbers:
        path = directory / f"page_{number:04d}.json"
        if path.is_symlink():
            _fail("source_evidence_changed")
        raw = path.read_bytes()
        if _sha(raw) != state.pages[str(number)].get("semantic_source_sha256"):
            _fail("source_evidence_changed")
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError):
            _fail("source_evidence_changed")
        if (type(data) is not dict or data.get("version") != (
                "ordinary_semantic_source_v2" if context_bound else "ordinary_semantic_source_v1")
                or data.get("pdf_sha256") != state.pdf_fingerprint
                or data.get("recipe_sha256") != _sha(_encode(recipe))
                or data.get("selected_pages") != numbers or data.get("page_number") != number
                or data.get("source_text_kind") != "pretokenized"
                or not isinstance(data.get("source_text"), str)
                or not isinstance(data.get("original_source_text"), str)
                or not isinstance(data.get("expected_ar_tokens"), list)
                or any(not isinstance(t, str) for t in data["expected_ar_tokens"])):
            _fail("source_evidence_changed")
        if context_bound:
            if (data.get("context_sha256") != recipe["context_sha256"]
                    or data.get("source_field_policy") != recipe["source_field_policy"]):
                _fail("context_evidence_changed")
            terminology.append({"page_number": number, "entries": _validate_terminology(
                data.get("applicable_terminology"), data["original_source_text"])})
        if acronym_policy:
            if not acronyms.capture_matches(data, acronym_sources, state.pages[str(number)]):
                _fail("acronym_source_changed")
        _validate_ocr_acquisition(state=state, run_dir=run_dir, page_number=number, recipe=recipe, data=data)
        from . import ordinary_source_postal_band as postal_band
        if postal_band.KEY in recipe or postal_band.FIELD in data or postal_band.ROUTE in data:
            try:
                postal_band.validate_capture(state, recipe, number, data)
            except ValueError:
                _fail("postal_source_binding")
        if data.get("configured_image_mode") != recipe["configured_image_mode"]:
            _fail("source_evidence_changed")
        if recipe["configured_image_mode"] == "off":
            if data.get("image_data_url") is not None or data.get("visual_coverage") != "text_only_configured_image_off":
                _fail("source_evidence_changed")
        elif (not isinstance(data.get("image_data_url"), str) or not data["image_data_url"]
                or data.get("visual_coverage") != "source_image_available"):
            _fail("review_required_source_image")
        primary = pages_dir / f"page_{number:04d}.txt"
        if primary_context is None and (primary.is_symlink() or not primary.is_file()):
            _fail("primary_evidence_missing")
        pages.append(SemanticAuditPage(page_number=number, source_text=data["source_text"],
            original_source_text=data["original_source_text"], source_text_kind="pretokenized",
            source_acronyms=tuple(data["source_acronyms"]) if acronym_policy else (),
            expected_ar_tokens=tuple(data["expected_ar_tokens"]), image_data_url=data["image_data_url"],
            primary_text=(primary_context.primary[number] if primary_context is not None
                else primary.read_bytes().decode("utf-8")), visual_coverage=data["visual_coverage"]))
    context = (_encode({"version": "ordinary_semantic_guidance_v1",
        "resolved_user_context": resolved_context,
        "source_fidelity_priority": "originals_over_context_and_terminology",
        "terminology_policy": "Preserve source-compatible preferred wording; guidance cannot override originals, "
            "protected literals or legal meaning. These are bounded preferences, not translation evidence.",
        "page_terminology": terminology}).decode("utf-8") if context_bound else "")
    return pages, recipe, context


def source_origins_from_checkpoint(state, pages):
    """Bind actual retained acquisition metadata; representation is not origin.

    The source pack stays immutable. Missing/inconsistent metadata is explicitly
    unknown and cannot license source-authority repair.
    """
    origins = []
    keys = ("source_route", "source_route_reason", "ocr_used", "ocr_engine_used", "ocr_selected_pass")
    for page in pages:
        metadata = state.pages[str(page.page_number)]
        provenance = {key: metadata.get(key) for key in keys}
        kind = "unknown"
        if metadata.get("source_route") == "direct_text" and metadata.get("ocr_used") is False:
            kind = "pdf_extraction_v1"
        elif (metadata.get("source_route") == "ocr" and metadata.get("ocr_used") is True
                and type(metadata.get("ocr_engine_used")) is str and metadata["ocr_engine_used"]):
            kind = ("merged_pdf_ocr_v1" if metadata.get("source_route_reason") == "visual_recovery_crop_merged"
                else "ocr_v1")
        origins.append({"version": "semantic_source_origin_v1", "page": page.page_number,
            "kind": kind, "provenance": provenance})
    return origins


def select_pages(*, state, config, run_dir, pages_dir, client=None, accountant=None, cancel_check=None):
    """The same exact selection powers fresh assembly, Resume and offline rebuild."""
    if ordinary_semantic_audit_recipe(state.settings) is None:
        qualification = ordinary_semantic_audit_qualification(state.settings)
        if qualification is not None and qualification["selected_pages"] != sorted(int(n) for n in state.pages):
            _fail("qualification_selection_changed")
        if any(_owned_directory(run_dir, name).exists() for name in
               ("semantic_source", "semantic_audit", "semantic_context.json", "primary_markup")):
            _fail("recipe_missing")
        return pages_dir, None
    from .ordinary_semantic_audit import (SemanticAuditError, SemanticAuditRecipe,
        run_semantic_audit, load_semantic_audit)
    from .usage_accounting import accounting_context
    from . import primary_literal_markup as markup
    primary_context = markup.load_context(state=state, run_dir=run_dir)
    pages, saved, context = _pages(state=state, config=config, run_dir=run_dir, pages_dir=pages_dir,
        **({"primary_context": primary_context} if primary_context is not None else {}))
    review = saved["version"] == "ordinary_semantic_audit_v3"
    if review:
        from .ordinary_semantic_review import run_semantic_review, load_semantic_review
        run_operation, load_operation = run_semantic_review, load_semantic_review
        if "semantic_repair_policy" in saved:
            from .ordinary_semantic_repair import run_semantic_repair, load_semantic_repair
            run_operation, load_operation = run_semantic_repair, load_semantic_repair
    else:
        run_operation, load_operation = run_semantic_audit, load_semantic_audit
    from .semantic_review_model_policy import effective_model
    recipe_values = {f.name: saved[f.name] for f in fields(SemanticAuditRecipe) if f.name in saved}
    recipe_values["model"] = effective_model(saved)
    recipe = SemanticAuditRecipe(**recipe_values, context_text=context)
    directory = _owned_directory(run_dir, "semantic_audit")
    try:
        arguments = dict(pages=pages, recipe=recipe, pdf_sha256=state.pdf_fingerprint, evidence_dir=directory)
        if review and "semantic_unit_reference_policy" in saved:
            arguments["semantic_unit_reference_policy"] = saved["semantic_unit_reference_policy"]
        if review and "semantic_source_review_policy" in saved:
            arguments["semantic_source_review_policy"] = saved["semantic_source_review_policy"]
        if review and "semantic_page_coverage_policy" in saved:
            arguments["semantic_page_coverage_policy"] = saved["semantic_page_coverage_policy"]
        if review and "source_inventory_max_output_tokens" in saved:
            arguments["source_inventory_max_output_tokens"] = saved["source_inventory_max_output_tokens"]
        if review and "semantic_repair_policy" in saved:
            arguments["semantic_repair_policy"] = saved["semantic_repair_policy"]
            arguments["stage_guard"] = repair_stage_guard(state=state, run_dir=run_dir, accountant=accountant)
        if review and "semantic_literal_authority_policy" in saved:
            arguments["semantic_literal_authority_policy"] = saved["semantic_literal_authority_policy"]
            arguments["source_origins"] = source_origins_from_checkpoint(state, pages)
        if review and "semantic_enclosure_authority_policy" in saved:
            arguments["semantic_enclosure_authority_policy"] = saved["semantic_enclosure_authority_policy"]
        if review and "source_enclosure_identity_policy" in saved:
            arguments["source_enclosure_identity_policy"] = saved["source_enclosure_identity_policy"]
        if review and "semantic_enclosure_sequence_repair_policy" in saved:
            arguments["semantic_enclosure_sequence_repair_policy"] = saved["semantic_enclosure_sequence_repair_policy"]
        if review and "semantic_target_ambiguity_policy" in saved:
            arguments["semantic_target_ambiguity_policy"] = saved["semantic_target_ambiguity_policy"]
        if primary_context is not None:
            arguments.update(primary_literal_markup_policy=saved[markup.KEY],
                primary_markup_context=primary_context)
        if review:
            before = dispatch_rollup(state=state, run_dir=run_dir, accountant=accountant)
            if (before["in_flight_count"] or before["missing_usage_count"]
                    or before["invalid_usage_count"] or before["conflicting_event_count"]
                    or ("semantic_review_model_policy" in saved and before["unknown_cost_count"])):
                _fail("usage_unknown_or_unsettled")
        if client is None:
            result = load_operation(**arguments)
        else:
            if getattr(client, "model", None) != recipe.model:
                _fail("model_changed")
            if accountant is None:
                _fail("accounting_unavailable")
            from .usage_accounting import DispatchAccounting, _fingerprint
            if isinstance(accountant, DispatchAccounting) and not review:
                before = dispatch_rollup(state=state, run_dir=run_dir, accountant=accountant)
                expected_path = run_dir / "accounting" / state.dispatch_accounting["id"] / "dispatch_accounting.json"
                if (Path(accountant.journal_path).resolve() == expected_path.resolve()
                        and _fingerprint(accountant.run_identity) == before.get("run_identity_sha256")
                        and before["call_count"] == 0):
                    arguments["undispatched_journal_sha256"] = before["journal_sha256"]
            if cancel_check is not None and cancel_check():
                _fail("cancelled")
            actual_client = client
            if cancel_check is not None and not review:
                class CancellableAuditClient:
                    model = actual_client.model
                    def create_page_response(self, **request):
                        return actual_client.create_page_response(**request, cancel_check=cancel_check)
                client = CancellableAuditClient()
            with accounting_context(accountant, purpose="semantic_audit", page_number=None):
                if review:
                    # Global zero-audit evidence cannot authorize a new substage.
                    # The engine handles request cancellation and final publication.
                    result = run_operation(**arguments, client=client,
                        stage_dispatch_proof=None, cancel_check=cancel_check)
                else:
                    result = run_operation(**arguments, client=client)
    except (SemanticAuditError, markup.PrimaryMarkupError) as exc:
        code = exc.code if re.fullmatch(r"[a-z][a-z0-9_]{0,100}", exc.code) else "provider_or_evidence_failure"
        _fail(code)
    if (result.manifest_path.parent.resolve() != directory.resolve()
            or set(result.selected_text_by_page) != {page.page_number for page in pages}
            or {p.name for p in directory.glob("page_*.txt")} != {f"page_{p.page_number:04d}.txt" for p in pages}):
        _fail("selection_changed")
    rollup = dispatch_rollup(state=state, run_dir=run_dir, accountant=accountant)
    if (rollup["provider_dispatch_count"] < (3 if review else 1) or rollup["in_flight_count"]
            or rollup["missing_usage_count"] or rollup["invalid_usage_count"]
            or rollup["conflicting_event_count"]):
        _fail("usage_unknown_or_unsettled")
    return directory, result


def validate_retained_source_pins(*, state, run_dir):
    """Reject damaged completed-source evidence before any resumed page dispatch."""
    from . import primary_literal_markup as markup
    markup.load_context(state=state, run_dir=run_dir, completed_only=True)
    if ordinary_semantic_audit_recipe(state.settings) is None:
        qualification = ordinary_semantic_audit_qualification(state.settings)
        if qualification is not None and qualification["selected_pages"] != sorted(int(n) for n in state.pages):
            _fail("qualification_selection_changed")
        if _owned_directory(run_dir, "semantic_context.json").exists():
            _fail("recipe_missing")
        return
    validate_context(state=state, run_dir=run_dir)
    directory = _owned_directory(run_dir, "semantic_source")
    for number, record in state.pages.items():
        if record.get("status") != "done":
            continue
        path = directory / f"page_{int(number):04d}.json"
        if (path.is_symlink() or not path.is_file()
                or _sha(path.read_bytes()) != record.get("semantic_source_sha256")):
            _fail("source_evidence_changed")
        _validate_ocr_acquisition(state=state, run_dir=run_dir, page_number=int(number),
            recipe=ordinary_semantic_audit_recipe(state.settings), data=json.loads(path.read_bytes()))


def _validate_ocr_acquisition(*, state, run_dir, page_number, recipe, data):
    from . import ocr_text_transport as transport
    if "ocr_visual_source" in data and "ocr_visual_source_policy" not in recipe:
        raise transport.OcrTextTransportError("source_binding")
    if "ocr_text_transport_policy" not in recipe:
        return
    metadata = state.pages[str(page_number)]
    selected_api = bool(metadata.get("ocr_used") and metadata.get("ocr_engine_used") == "api")
    acquisition = data.get("ocr_text_acquisition")
    if not selected_api:
        if acquisition is not None or "ocr_visual_source" in data:
            raise transport.OcrTextTransportError("source_binding")
        return
    composition = "merged_pdf_ocr" if metadata.get("source_route_reason") == "visual_recovery_crop_merged" else "api_ocr"
    if "ocr_visual_source_policy" not in recipe:
        if (type(acquisition) is not dict or set(acquisition) != {"reference", "selected_source_sha256", "composition"}
                or acquisition["composition"] != composition
                or acquisition["selected_source_sha256"] != _sha(data["original_source_text"].encode("utf-8"))):
            raise transport.OcrTextTransportError("source_binding")
        transport.validate_ref(run_dir=run_dir, pdf_sha256=state.pdf_fingerprint, page=page_number,
            reference=acquisition["reference"], original_source_text=data["original_source_text"] if composition == "api_ocr" else None)
        return
    if type(acquisition) is not dict or set(acquisition) != {"reference", "selected_source_sha256", "composition"}:
        raise transport.OcrTextTransportError("source_binding")
    raw = transport.validate_ref(run_dir=run_dir, pdf_sha256=state.pdf_fingerprint, page=page_number,
        reference=acquisition["reference"])
    if composition == "api_ocr":
        from . import ordinary_ocr_visual_source as local
        if local.eligible_page(state.pdf_path, page_number, raw):
            composition = "verified_source_slots_v1"
    if ("ocr_visual_source" in data) != (composition == "verified_source_slots_v1"):
        raise transport.OcrTextTransportError("source_binding")
    if (acquisition["composition"] != composition or (composition == "api_ocr" and raw != data["original_source_text"])
            or acquisition["selected_source_sha256"] != _sha(data["original_source_text"].encode("utf-8"))):
        raise transport.OcrTextTransportError("source_binding")
    if composition == "verified_source_slots_v1":
        _validate_visual_source(state=state, run_dir=run_dir, page_number=page_number, raw=raw, data=data, recipe=recipe)


def _validate_visual_source(*, state, run_dir, page_number, raw, data, recipe):
    from . import ordinary_ocr_visual_source as local, ocr_text_transport as transport
    from .arabic_pre_tokenize import pretokenize_arabic_source, extract_locked_tokens, is_portuguese_month_date_token
    effective, proof = local.replay(state.pdf_path, page_number, raw, state.pdf_fingerprint, run_dir,
                                  policy=recipe[local.KEY])
    prepared = pretokenize_arabic_source(local.prepared_source(effective, proof),
                                         source_field_policy=recipe["source_field_policy"])
    required = [t for t in extract_locked_tokens(prepared) if not is_portuguese_month_date_token(t)]
    if (proof != data.get("ocr_visual_source") or data["original_source_text"] != effective
            or data["source_text"] != prepared or data["expected_ar_tokens"] != required or not local.image_matches(
                state.pdf_path, state.pdf_fingerprint, page_number, data.get("primary_image_data_url"), data.get("image_data_url"))):
        raise transport.OcrTextTransportError("source_binding")


def dispatch_rollup(*, state, run_dir, accountant=None):
    """Read settled/failed/unknown audit attempts once from the dispatch journal."""
    from .usage_accounting import (_summarize, _state_fingerprint, _fingerprint,
        _validate_retained_events, _normalize_limits, ACCOUNTING_SCHEMA_VERSION, DispatchAccountingError)
    from .cost_guardrails import PricingSnapshot
    journal = getattr(accountant, "journal_path", None)
    if journal is None and state.dispatch_accounting:
        identifier = state.dispatch_accounting.get("id")
        if not isinstance(identifier, str) or re.fullmatch(r"[a-f0-9]{32}", identifier) is None:
            _fail("accounting_identity_invalid")
        journal = run_dir / "accounting" / identifier / "dispatch_accounting.json"
    if journal is not None:
        try:
            path = Path(journal)
            if path.is_symlink():
                _fail("accounting_evidence_invalid")
            raw = path.read_bytes()
            saved = json.loads(raw)
            identifier = state.dispatch_accounting["id"]
            recipe = ordinary_semantic_audit_recipe(state.settings)
            expected = {"accounting_id": identifier, "source_sha256": state.pdf_fingerprint,
                "context_hash": state.context_hash, "language": state.lang,
                "protocol": state.protocol_identity.get("protocol", "legacy_text_v1"),
                "model": recipe["model"], "protocol_identity": dict(state.protocol_identity),
                "selection": [state.selection_start_page, state.selection_end_page],
                "run_started_at": state.run_started_at}
            from .semantic_review_model_policy import identity_fields, effective_model
            expected.update(identity_fields(recipe))
            if (saved.get("schema_version") != ACCOUNTING_SCHEMA_VERSION
                    or saved.get("fingerprint") != _state_fingerprint(saved)
                    or saved.get("run_identity") != expected
                    or saved.get("run_identity_hash") != _fingerprint(expected)
                    or saved.get("historical_incomplete") is not state.dispatch_accounting.get("historical_incomplete", False)
                    or not isinstance(saved.get("events"), list)):
                _fail("accounting_evidence_invalid")
            catalog = saved.get("pricing_catalog")
            if (PricingSnapshot.from_mapping(catalog).metadata() if catalog is not None else None) != saved.get("pricing_snapshot"):
                _fail("accounting_evidence_invalid")
            _normalize_limits(saved.get("dispatch_limits"))
            events = saved["events"]
            _validate_retained_events(events)
            from .semantic_review_billing import validate_retained_responses
            validate_retained_responses(path.parent, events)
            if any(e.get("requested_model") != (effective_model(recipe)
                       if e.get("purpose") == "semantic_audit" else recipe["model"]) for e in events
                   if e.get("event") == "begin" and e.get("purpose") in {"translation", "correction", "semantic_audit"}):
                _fail("accounting_evidence_invalid")
            if path.read_bytes() != raw:
                _fail("accounting_evidence_changed")
        except SemanticIntegrationError:
            raise
        except (OSError, ValueError, KeyError, TypeError, AttributeError, DispatchAccountingError):
            _fail("accounting_evidence_invalid")
    else:
        events = getattr(accountant, "_events", [])
    ids = {e.get("call_id") for e in events if isinstance(e, dict)
           and e.get("event") == "begin" and e.get("purpose") == "semantic_audit"}
    selected = [e for e in events if isinstance(e, dict) and e.get("call_id") in ids]
    rollup = _summarize(selected, historical_incomplete=False)
    if journal is not None:
        rollup.update(journal_sha256=_sha(raw), run_identity_sha256=_fingerprint(expected))
    return rollup


def repair_stage_guard(*, state, run_dir, accountant=None):
    """Bind each repair-controller stage to native SDK attempts and settlement.

    This is a read-only journal consumer, never another cost ledger. Existing
    dispatch admission remains authoritative inside every transport attempt.
    """
    from types import SimpleNamespace
    from .usage_accounting import DispatchAccounting, _summarize, normalize_usage, TOKEN_FIELDS
    from .openai_client import (_build_page_request, _apply_openai_dispatch_limits,
        _request_accounting_details, _extract_output_text, _has_refusal, _has_incomplete_message)
    from .semantic_review_billing import strict_limits, read_response
    from .ordinary_semantic_audit import _write_new, _read_json
    saved_recipe = ordinary_semantic_audit_recipe(state.settings)
    if (saved_recipe.get("semantic_repair_policy") not in {"source_grounded_repair_once_v1", "source_grounded_repair_once_v2", "source_grounded_repair_once_v3", "source_grounded_repair_once_v4"}
            or (accountant is not None and (not isinstance(accountant, DispatchAccounting) or accountant.hard_budget))):
        _fail("repair_native_accounting_required")
    identifier = state.dispatch_accounting["id"]
    path = run_dir / "accounting" / identifier / "dispatch_accounting.json"
    if accountant is not None and Path(accountant.journal_path).resolve() != path.resolve():
        _fail("repair_native_accounting_required")

    def journal():
        rollup = dispatch_rollup(state=state, run_dir=run_dir, accountant=accountant)
        raw = path.read_bytes()
        if _sha(raw) != rollup.get("journal_sha256"):
            _fail("accounting_evidence_changed")
        saved = json.loads(raw)
        totals = _summarize(saved["events"], historical_incomplete=saved["historical_incomplete"])
        if (totals["historical_incomplete"] or any(totals[key] for key in (
                "in_flight_count", "missing_usage_count", "invalid_usage_count", "unknown_cost_count",
                "budget_incomplete_count", "billing_identity_incomplete_count", "duplicate_event_count",
                "conflicting_event_count"))):
            _fail("usage_unknown_or_unsettled")
        if accountant is not None and not accountant.can_retry:
            _fail("usage_unknown_or_unsettled")
        context = {key: value for key, value in saved.items() if key not in {"events", "fingerprint", "updated_at"}}
        return saved, _sha(_encode(context))

    def persist(file, value):
        raw = _encode(value)
        if file.exists():
            if file.is_symlink() or not file.is_file() or file.read_bytes() != raw:
                _fail("repair_native_evidence_changed")
        else:
            _write_new(file, raw.decode("utf-8"))

    def proof_at(record):
        expected = record["stage_id"] + "_native/native_settlement.json"
        if record.get("native_settlement_path") != expected:
            _fail("repair_native_evidence_changed")
        file = run_dir / "semantic_audit" / expected
        proof = _read_json(file)
        from .ordinary_semantic_audit import _json
        if _sha(_json(proof).encode("utf-8")) != record["native_settlement_sha256"]:
            _fail("repair_native_evidence_changed")
        return proof

    def guard(*, action, stage_id, request, directory, envelope, records):
        saved, context_sha = journal()
        events = saved["events"]
        if action == "final":
            assigned = []
            end = None
            for record in records:
                proof = proof_at(record)
                if end is None:
                    if any(row["event"] == "begin" and row["purpose"] == "semantic_audit"
                           for row in events[:proof["before_event_count"]]):
                        _fail("repair_native_stage_partition")
                elif proof["before_event_count"] != end:
                    _fail("repair_native_stage_partition")
                if (_sha(_encode(events[proof["before_event_count"]:proof["after_event_count"]])) != proof["stage_events_sha256"]):
                    _fail("repair_native_evidence_changed")
                assigned.extend(proof["call_ids"])
                end = proof["after_event_count"]
            actual = [event["call_id"] for event in events if event["event"] == "begin" and event["purpose"] == "semantic_audit"]
            if len(assigned) != len(set(assigned)) or set(assigned) != set(actual) or end != len(events):
                _fail("repair_native_stage_partition")
            return {"native_calls": len(assigned)}
        from .ordinary_semantic_audit import _json
        high_hash = _sha(_json(request).encode("utf-8"))
        limits = next((dict(saved["dispatch_limits"][key]) for key in (
            "openai:semantic_audit:gpt-6-astra", "openai:*:gpt-6-astra", "openai:semantic_audit")
            if key in saved["dispatch_limits"]), None)
        if not isinstance(limits, dict) or not strict_limits(limits):
            _fail("repair_native_limits")
        if accountant is not None and dict(accountant.request_limits("openai", "semantic_audit", "gpt-6-astra")) != limits:
            _fail("repair_native_limits")
        arguments = {key: value for key, value in request.items() if key != "timeout_seconds"}
        wire = _build_page_request(**arguments, model="gpt-6-astra")
        wire = _apply_openai_dispatch_limits(wire, accountant or SimpleNamespace(hard_budget=False), limits)
        wire_hash, observed = _request_accounting_details(wire)
        expected_bounds = {**limits, **observed}
        native = directory.parent / (directory.name + "_native")
        if native.is_symlink():
            _fail("repair_native_evidence_changed")
        native.mkdir(exist_ok=True)
        pre_path, post_path = native / "native_intent.json", native / "native_settlement.json"
        identity = {"version": "native_semantic_stage_binding_v1", "stage_id": stage_id,
            "request_sha256": high_hash, "wire_request_sha256": wire_hash,
            "journal_context_sha256": context_sha, "run_identity_sha256": saved["run_identity_hash"],
            "dispatch_limits_sha256": _sha(_encode(limits))}
        if pre_path.exists():
            pre = _read_json(pre_path)
            count = pre.get("before_event_count")
            if (type(count) is not int or not 0 <= count <= len(events)
                    or set(pre) != set(identity) | {"before_event_count", "before_events_sha256"}
                    or any(pre.get(key) != value for key, value in identity.items())
                    or pre["before_events_sha256"] != _sha(_encode(events[:count]))):
                _fail("repair_native_evidence_changed")
            if not (directory / "raw_response.json").is_file() or not (directory / "raw_receipt.json").is_file():
                # The sidecar can precede the old engine's intent. Recover only
                # that genuinely undispatched slot; an engine intent remains
                # conservative even when the native tail happens to be empty.
                if ((directory / "intent.json").exists() or (directory / "raw_response.json").exists()
                        or (directory / "raw_receipt.json").exists() or post_path.exists()
                        or count != len(events)):
                    _fail("repair_unsettled_stage")
        elif action == "prepare":
            if post_path.exists() or (directory / "intent.json").exists() or (directory / "raw_response.json").exists():
                _fail("repair_native_evidence_missing")
            pre = {**identity, "before_event_count": len(events), "before_events_sha256": _sha(_encode(events))}
            persist(pre_path, pre)
        else:
            _fail("repair_native_evidence_missing")
        if records:
            if proof_at(records[-1])["after_event_count"] != pre["before_event_count"]:
                _fail("repair_native_stage_partition")
        elif any(row["event"] == "begin" and row["purpose"] == "semantic_audit"
                 for row in events[:pre["before_event_count"]]):
            _fail("repair_native_stage_partition")
        if action == "prepare":
            return pre
        if action not in {"settled", "failed"}:
            _fail("repair_native_action")
        previous = _read_json(post_path) if post_path.exists() else None
        end = previous.get("after_event_count") if previous is not None else len(events)
        start = pre["before_event_count"]
        if type(end) is not int or not start < end <= len(events):
            _fail("repair_native_stage_partition")
        rows = events[start:end]
        if len(rows) % 2 or not rows:
            _fail("repair_native_stage_partition")
        calls, terminal = [], None
        for index in range(0, len(rows), 2):
            begin, finish = rows[index:index + 2]
            if (begin.get("event") != "begin" or finish.get("event") != "finish"
                    or finish.get("call_id") != begin.get("call_id")
                    or begin.get("provider") != "openai" or begin.get("purpose") != "semantic_audit"
                    or begin.get("requested_model") != "gpt-6-astra" or begin.get("effort") != request["effort"]
                    or begin.get("request_hash") != wire_hash or begin.get("bounds") != expected_bounds
                    or begin.get("route") != "responses.create"
                    or begin.get("base_url") not in [str(value).rstrip("/") for value in limits.get("allowed_base_urls", [])]
                    or begin.get("billing_scope") != limits.get("billing_scope")
                    or begin.get("currency") != limits.get("currency", "USD")
                    or begin.get("requested_service_tier") != wire.get("service_tier", "auto")
                    or begin.get("attempt") != index // 2 + 1
                    or finish.get("cost_status") != "available" or finish.get("usage", {}).get("usage_status") != "available"):
                _fail("repair_native_stage_partition")
            calls.append(begin["call_id"])
            terminal = finish
        intent = _read_json(directory / "intent.json")
        if intent.get("request_sha256") != high_hash:
            _fail("repair_native_stage_request")
        billing = terminal.get("semantic_review_billing_evidence", {})
        body = read_response(path.parent, billing.get("response"))
        normalized = normalize_usage(envelope["usage"])
        if (terminal.get("outcome") not in ({"succeeded"} if action == "settled" else {"succeeded", "refused", "failed", "timeout"})
                or terminal.get("response_id") != envelope.get("response_id")
                or body.get("id") != envelope.get("response_id") or body.get("model") != envelope.get("model")
                or body.get("status") != envelope.get("response_status")
                or envelope.get("effort") != request["effort"] or _has_refusal(body) is not envelope.get("refused")
                or (envelope.get("raw_response_available") is True and _extract_output_text(body) != envelope["raw_output"])
                or any(normalized[key] != terminal["usage"][key] for key in TOKEN_FIELDS)):
            _fail("repair_native_response_mismatch")
        if action == "settled" and (_has_refusal(body) or _has_incomplete_message(body)
                or body.get("status") != "completed" or body.get("incomplete_details") is not None):
            _fail("repair_native_response_hard_stop")
        proof = {**pre, "after_event_count": end, "stage_events_sha256": _sha(_encode(rows)),
            "call_ids": calls, "stage_intent_sha256": _sha(_json(intent).encode("utf-8")),
            "raw_receipt_sha256": _sha((directory / "raw_receipt.json").read_bytes()),
            "response_sha256": billing["response"]["sha256"],
            "usage": _summarize(rows, historical_incomplete=False)["totals"]}
        persist(post_path, proof)
        return proof
    return guard
