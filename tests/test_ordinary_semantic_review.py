"""Fictional source-first review protocol and durable bounded fake-client tests."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from legalpdf_translate import ordinary_semantic_review as review
from legalpdf_translate.openai_client import ApiCallError, ApiCallResult


PDF = "a" * 64
IMAGE = "data:image/png;base64,YQ=="


def pack(*, count=1, off=False):
    return tuple(review.SemanticAuditPage(i, f"A fictional office issued notice {i}.", (),
        None if off else IMAGE, f"أصدر المكتب إشعارا {i}.",
        original_source_text=f"A fictional office issued notice {i}.",
        visual_coverage="text_only_configured_image_off" if off else "source_image_available")
        for i in range(1, count + 1))


def recipe(**kwargs):
    return review.SemanticAuditRecipe("fictional-model", "high", **kwargs)


def inventory(payload):
    claims = []
    coverage = []
    for n, unit in enumerate(payload["source_units"], 1):
        key = f"claim_{n}"
        claims.append({"claim_id": key, "source_unit_ids": [unit["unit_id"]],
            "source_evidence": [{"kind": "text", **{k: unit[k] for k in ("page", "start", "end")}, "quote": unit["text"]}],
            "proposition": unit["text"], "axes": {"actor_recipient": "fictional office issues notice",
                "polarity_modality": "assertion", "temporal_state": "completed", "participant_number": "one", "conditions": ""},
            "unresolved": False})
        coverage.append({"unit_id": unit["unit_id"], "claim_ids": [key]})
    for page in payload["source_pages"]:
        if not any(c["source_evidence"][0]["page"] == page["page"] for c in claims):
            claims.append({"claim_id": f"image_{page['page']}", "source_unit_ids": [],
                "source_evidence": [{"kind": "image", "page": page["page"], "bbox": [.1, .1, .9, .9]}],
                "proposition": "A fictional visible notice.", "axes": {"actor_recipient": "office",
                    "polarity_modality": "assertion", "temporal_state": "completed", "participant_number": "one", "conditions": ""}, "unresolved": False})
    return {"version": review.INVENTORY_VERSION, "claims": claims, "unit_coverage": coverage,
        "boundaries": [{"left_page": a["page"], "right_page": b["page"], "relation": "separate",
            "claim_ids": [c["claim_id"] for c in claims if c["source_evidence"][0]["page"] in {a["page"], b["page"]}]}
            for a, b in zip(payload["source_pages"], payload["source_pages"][1:])],
        "page_visual_coverage": [{"page": p["page"], "status": "reviewed" if p["image_position"] is not None else "text_only"}
            for p in payload["source_pages"]]}


def correction(payload):
    return {"version": review.CORRECTION_VERSION,
        "pages": [{"page_number": p["page"], "status": "no_change", "corrected_text": "", "reason_codes": []}
                  for p in payload["primary_pages"]],
        "claim_coverage": [{"claim_id": c["claim_id"], "status": "preserved"} for c in payload["source_inventory"]["claims"]]}


def verification(payload):
    results, inverse = [], {u["unit_id"]: [] for u in payload["target_units"]}
    source_pages = {unit["unit_id"]: unit["page"] for unit in payload["source_units"]}
    for claim in payload["source_inventory"]["claims"]:
        pages = ({source_pages[key] for key in claim["source_unit_ids"]} if claim["source_unit_ids"] else
                 {span["page"] for span in claim["source_evidence"] if span["kind"] == "image"})
        spans = []
        for unit in payload["target_units"]:
            if unit["page"] in pages:
                spans.append({**{k: unit[k] for k in ("page", "start", "end")}, "quote": unit["text"]})
                inverse[unit["unit_id"]].append(claim["claim_id"])
        results.append({"claim_id": claim["claim_id"], "status": "equivalent", "target_spans": spans})
    return {"version": review.VERIFICATION_VERSION, "claim_results": results,
        "target_unit_coverage": [{"unit_id": key, "claim_ids": claims} for key, claims in inverse.items()],
        "boundary_results": [{"left_page": b["left_page"], "right_page": b["right_page"], "status": "equivalent"}
            for b in payload["source_inventory"]["boundaries"]], "inventory_errors": [], "unsupported_additions": []}


class Client:
    model = "fictional-model"

    def __init__(self, mutate=None, after=None):
        self.requests = []
        self.mutate, self.after = mutate, after

    def create_page_response(self, **request):
        self.requests.append(request)
        payload = json.loads(request["prompt_text"])
        value = {review.STAGES[0]: inventory, review.STAGES[1]: correction, review.STAGES[2]: verification}[payload["stage"]](payload)
        if self.mutate:
            value = self.mutate(payload["stage"], value, payload)
        response = value if isinstance(value, ApiCallResult) else ApiCallResult(json.dumps(value, ensure_ascii=False),
            {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}, f"response-{len(self.requests)}", effort="high")
        if self.after:
            self.after(payload["stage"])
        return response


def run(tmp_path, client=None, pages=None, settings=None, **kwargs):
    return review.run_semantic_review(pages=pages or pack(), recipe=settings or recipe(),
        pdf_sha256=PDF, evidence_dir=tmp_path / "semantic_audit", client=client, **kwargs)


def test_three_ordered_calls_and_zero_call_verified_reuse(tmp_path):
    client = Client()
    first = run(tmp_path, client, pack(count=2))
    assert [json.loads(r["prompt_text"])["stage"] for r in client.requests] == list(review.STAGES)
    assert first.selected_text_by_page == {p.page_number: p.primary_text for p in pack(count=2)}
    assert first.usage["input_tokens"] == 30 and first.usage["output_tokens"] == 60 and first.usage["total_tokens"] == 90
    assert set(first.usage["stages"]) == set(review.STAGES)
    manifest = first.manifest_path.read_bytes()
    loaded = review.load_semantic_review(pages=pack(count=2), recipe=recipe(), pdf_sha256=PDF, evidence_dir=first.manifest_path.parent)
    assert loaded.reused and loaded.selected_text_by_page == first.selected_text_by_page
    assert loaded.usage == first.usage and len(client.requests) == 3
    assert first.manifest_path.read_bytes() == manifest
    data = json.loads(manifest)
    assert data["human_review_complete"] is False and data["automated_semantic_verified"] is True
    assert [s["response_id"] for s in data["stages"]] == ["response-1", "response-2", "response-3"]


def test_source_inventory_never_sees_primary_context_or_locked_inventory_and_verifier_has_no_verdict(tmp_path):
    pages = (replace(pack()[0], primary_text="صياغة عربية فريدة.", expected_ar_tokens=()),)
    settings = recipe(context_text="private preference must not reach inventory")
    client = Client()
    run(tmp_path, client, pages, settings)
    first = json.loads(client.requests[0]["prompt_text"])
    assert "context_text" not in first and "primary_pages" not in first and "literal_protocol" not in first
    assert pages[0].primary_text not in client.requests[0]["prompt_text"]
    assert settings.context_text not in client.requests[0]["prompt_text"]
    final = json.loads(client.requests[-1]["prompt_text"])
    assert "candidate_pages" in final and "primary_pages" not in final and "claim_coverage" not in final
    assert "context_text" not in final and settings.context_text not in client.requests[-1]["prompt_text"]
    assert json.loads(client.requests[1]["prompt_text"])["context_text"] == settings.context_text
    assert "reason_codes" not in client.requests[-1]["prompt_text"]
    assert all(r["effort"] == "high" and r["max_output_tokens"] == 32000 and r["timeout_seconds"] == 480 for r in client.requests)
    assert all(r["response_format"]["strict"] is True for r in client.requests)


def test_cross_page_claim_can_cover_two_exact_units_with_explicit_boundary(tmp_path):
    def cross(stage, data, payload):
        if stage == review.STAGES[0]:
            first, second = data["claims"]
            first["source_unit_ids"] += second["source_unit_ids"]
            first["source_evidence"] += second["source_evidence"]
            data["claims"] = [first]
            for row in data["unit_coverage"]: row["claim_ids"] = [first["claim_id"]]
            data["boundaries"][0].update(relation="continuation", claim_ids=[first["claim_id"]])
        return data
    client = Client(cross)
    assert run(tmp_path, client, pack(count=2)).manifest_path.is_file()
    payload = json.loads(client.requests[-1]["prompt_text"])
    assert payload["source_inventory"]["boundaries"][0]["relation"] == "continuation"


def test_exact_source_unit_offsets_hashes_crlf_and_whitespace():
    text = "  First fictional line.\r\n\r\nSecond line.\n"
    pages = (replace(pack()[0], original_source_text=text),)
    units = review.source_units(pages)
    assert len(units) == 2
    for unit in units:
        assert text[unit["start"]:unit["end"]] == unit["text"]
        assert unit["sha256"] == review.audit._sha(unit["text"])


def test_image_off_is_text_only_and_no_empty_multiimage_argument(tmp_path):
    client = Client()
    run(tmp_path, client, pack(off=True), recipe(configured_image_mode="off"))
    assert all("image_data_urls" not in r for r in client.requests)
    assert all(json.loads(r["prompt_text"])["source_pages"][0]["image_position"] is None for r in client.requests)


def test_image_only_source_requires_actual_image_evidence(tmp_path):
    pages = (replace(pack()[0], source_text="", original_source_text=""),)
    client = Client()
    assert run(tmp_path, client, pages).manifest_path.is_file()
    first = json.loads(client.requests[0]["prompt_text"])
    assert first["source_units"] == []


@pytest.mark.parametrize("defect", ["missing_unit", "empty_coverage", "duplicate_claim", "wrong_quote", "wrong_offset", "foreign_page",
    "nonfinite_bbox", "missing_boundary", "uncertain_boundary", "visual_unreadable", "wrong_inverse", "missing_axes", "unresolved", "uncertain_number", "uncertain_time"])
def test_invalid_inventory_stops_after_first_call(tmp_path, defect):
    def damage(stage, data, payload):
        if stage != review.STAGES[0]: return data
        claim = data["claims"][0]
        if defect == "missing_unit": data["unit_coverage"].pop()
        elif defect == "empty_coverage": data["unit_coverage"][0]["claim_ids"] = []
        elif defect == "duplicate_claim": data["claims"].append(deepcopy(claim))
        elif defect == "wrong_quote": claim["source_evidence"][0]["quote"] += " changed"
        elif defect == "wrong_offset": claim["source_evidence"][0]["start"] = True
        elif defect == "foreign_page": claim["source_evidence"][0]["page"] = 999
        elif defect == "nonfinite_bbox": claim["source_evidence"] = [{"kind": "image", "page": 1, "bbox": [0, 0, float("nan"), 1]}]
        elif defect == "missing_boundary": data["boundaries"] = []
        elif defect == "uncertain_boundary": data["boundaries"][0]["relation"] = "uncertain"
        elif defect == "visual_unreadable": data["page_visual_coverage"][0]["status"] = "unreadable"
        elif defect == "wrong_inverse": data["unit_coverage"][0]["claim_ids"] = [data["claims"][1]["claim_id"]]
        elif defect == "missing_axes": claim["axes"].pop("temporal_state")
        elif defect == "unresolved": claim["unresolved"] = True
        elif defect == "uncertain_number": claim["axes"]["participant_number"] = "uncertain"
        elif defect == "uncertain_time": claim["axes"]["temporal_state"] = "uncertain"
        return data
    client = Client(damage)
    with pytest.raises(review.SemanticAuditError): run(tmp_path, client, pack(count=2))
    assert len(client.requests) == 1
    assert not (tmp_path / "semantic_audit/manifest.json").exists()
    assert not list((tmp_path / "semantic_audit").glob("page_*.txt"))


@pytest.mark.parametrize("defect", ["missing_page", "missing_claim", "unresolved", "primary_literal_loss"])
def test_correction_keeps_existing_coverage_and_anti_loss_guards(tmp_path, defect):
    pages = (replace(pack()[0], primary_text="نص عربي إضافي \u2066[[47]]\u2069"),)
    def damage(stage, data, payload):
        if stage != review.STAGES[1]: return data
        if defect == "missing_page": data["pages"] = []
        elif defect == "missing_claim": data["claim_coverage"] = []
        elif defect == "unresolved": data["claim_coverage"][0]["status"] = "unresolved"
        else: data["pages"][0].update(status="corrected", corrected_text="نص عربي إضافي", reason_codes=["omission"])
        return data
    client = Client(damage)
    with pytest.raises(review.SemanticAuditError): run(tmp_path, client, pages)
    assert len(client.requests) == 2
    assert not (tmp_path / "semantic_audit/manifest.json").exists()


def test_valid_correction_is_the_only_candidate_independent_verifier_receives(tmp_path):
    chosen = "أصدر المكتب الإشعار المطلوب \u2066[[1]]\u2069."
    pages = (replace(pack()[0], expected_ar_tokens=("1",), primary_text="أصدر المكتب إشعارا \u2066[[1]]\u2069."),)
    def change(stage, data, payload):
        if stage == review.STAGES[1]:
            data["pages"][0].update(status="corrected", corrected_text=chosen, reason_codes=["material_meaning"])
            data["claim_coverage"][0]["status"] = "corrected"
        return data
    client = Client(change)
    result = run(tmp_path, client, pages)
    assert result.selected_text_by_page[1] == chosen
    assert json.loads(client.requests[-1]["prompt_text"])["candidate_pages"][0]["text"] == chosen


@pytest.mark.parametrize("defect", ["missing_claim", "contradiction", "unresolved", "no_target_spans", "changed_span", "missing_target_unit",
    "wrong_inverse", "missing_boundary", "boundary_contradiction", "inventory_error", "unsupported_addition"])
def test_independent_verification_failure_never_publishes_or_repairs(tmp_path, defect):
    def damage(stage, data, payload):
        if stage != review.STAGES[2]: return data
        if defect == "missing_claim": data["claim_results"].pop()
        elif defect in {"contradiction", "unresolved"}: data["claim_results"][0]["status"] = defect
        elif defect == "no_target_spans": data["claim_results"][0]["target_spans"] = []
        elif defect == "changed_span": data["claim_results"][0]["target_spans"][0]["quote"] += " invented"
        elif defect == "missing_target_unit": data["target_unit_coverage"].pop()
        elif defect == "wrong_inverse": data["target_unit_coverage"][0]["claim_ids"] = []
        elif defect == "missing_boundary": data["boundary_results"] = []
        elif defect == "boundary_contradiction": data["boundary_results"][0]["status"] = "contradiction"
        elif defect == "inventory_error": data["inventory_errors"] = [{"source_unit_ids": [], "reason": "source inventory omitted a completed act"}]
        else: data["unsupported_additions"] = [{"target_spans": [], "reason": "candidate invented a future promise"}]
        return data
    client = Client(damage)
    with pytest.raises(review.SemanticAuditError): run(tmp_path, client, pack(count=2))
    assert len(client.requests) == 3
    assert not (tmp_path / "semantic_audit/manifest.json").exists()
    with pytest.raises(review.SemanticAuditError): run(tmp_path, client, pack(count=2))
    assert len(client.requests) == 3


@pytest.mark.parametrize("stage", review.STAGES)
@pytest.mark.parametrize("failure", ["refusal", "incomplete", "unknown"])
def test_provider_failure_retains_settlement_or_blocks_uncertain_repurchase(tmp_path, stage, failure):
    def bad(current, data, payload):
        if current != stage: return data
        if failure == "unknown": raise RuntimeError("private provider text must never escape")
        return ApiCallResult("private retained refusal" if failure == "refusal" else "{}", {}, "terminal-id",
            refused=failure == "refusal", response_status="incomplete" if failure == "incomplete" else "completed")
    client = Client(bad)
    with pytest.raises(review.SemanticAuditError) as first: run(tmp_path, client)
    assert "private" not in str(first.value)
    calls = len(client.requests)
    with pytest.raises(review.SemanticAuditError): run(tmp_path, client)
    assert len(client.requests) == calls
    assert not (tmp_path / "semantic_audit/manifest.json").exists()


@pytest.mark.parametrize("where", ["source_inventory", "correction", "verification", "manifest", "page", "receipt", "parent_intent"])
def test_corruption_is_rejected_without_any_additional_dispatch(tmp_path, where):
    client = Client()
    result = run(tmp_path, client)
    folder = result.manifest_path.parent
    if where in review.STAGES: (folder / where / "raw_response.json").write_text("{}")
    elif where == "manifest": result.manifest_path.write_text("{}")
    elif where == "page": (folder / "page_0001.txt").write_text("changed")
    elif where == "receipt": (folder / review.STAGES[1] / "raw_receipt.json").write_text("{}")
    else: (folder / "intent.json").write_text("{}")
    with pytest.raises(review.SemanticAuditError): run(tmp_path, client)
    assert len(client.requests) == 3


@pytest.mark.parametrize("change", ["source", "primary", "image", "recipe", "pdf"])
def test_exact_source_pack_and_recipe_binding_cannot_be_reinterpreted(tmp_path, change):
    client = Client()
    run(tmp_path, client)
    pages, settings, pdf = pack(), recipe(), PDF
    if change == "source": pages = (replace(pages[0], original_source_text="Changed fictional source."),)
    elif change == "primary": pages = (replace(pages[0], primary_text="نص آخر"),)
    elif change == "image": pages = (replace(pages[0], image_data_url="data:image/png;base64,Yg=="),)
    elif change == "recipe": settings = replace(settings, context_text="changed context")
    else: pdf = "b" * 64
    with pytest.raises(review.SemanticAuditError, match="source_binding_mismatch"):
        review.run_semantic_review(pages=pages, recipe=settings, pdf_sha256=pdf,
            evidence_dir=tmp_path / "semantic_audit", client=client)
    assert len(client.requests) == 3


@pytest.mark.parametrize("cancel_stage", review.STAGES)
def test_cancelled_settled_stage_is_retained_and_resumed_once(tmp_path, cancel_stage):
    state = {"cancel": False}
    client = Client(after=lambda stage: state.update(cancel=stage == cancel_stage))
    with pytest.raises(review.SemanticAuditError, match="operation_cancelled"):
        run(tmp_path, client, cancel_check=lambda: state["cancel"])
    assert not (tmp_path / "semantic_audit/manifest.json").exists()
    assert (tmp_path / "semantic_audit" / cancel_stage / "raw_receipt.json").is_file()
    state["cancel"] = False
    client.after = None
    result = run(tmp_path, client, cancel_check=lambda: state["cancel"])
    assert result.manifest_path.is_file() and len(client.requests) == 3


def test_cancel_before_dispatch_and_after_final_settlement_allow_local_revalidation(tmp_path):
    client = Client()
    with pytest.raises(review.SemanticAuditError, match="operation_cancelled"):
        run(tmp_path, client, cancel_check=lambda: True)
    assert not client.requests and not (tmp_path / "semantic_audit").exists()
    state = {"cancel": False}
    client.after = lambda stage: state.update(cancel=stage == review.STAGES[2])
    with pytest.raises(review.SemanticAuditError): run(tmp_path, client, cancel_check=lambda: state["cancel"])
    assert run(tmp_path).manifest_path.is_file() and len(client.requests) == 3


def test_interrupted_publication_replays_three_raw_responses_locally(tmp_path, monkeypatch):
    client = Client()
    original = review.audit._write_new
    def interrupted(path, text):
        if path.name == "manifest.json": raise review.SemanticReviewError("evidence_write_failure")
        original(path, text)
    with monkeypatch.context() as patch:
        patch.setattr(review.audit, "_write_new", interrupted)
        with pytest.raises(review.SemanticAuditError): run(tmp_path, client)
    assert run(tmp_path).manifest_path.is_file() and len(client.requests) == 3


def test_interrupted_raw_staging_never_repeats_uncertain_call(tmp_path, monkeypatch):
    client = Client()
    original = review.audit.os.link
    def interrupted(src, dst):
        if Path(dst).parent.name == review.STAGES[1] and Path(dst).name == "raw_response.json":
            raise OSError("fictional interruption after fsync")
        return original(src, dst)
    with monkeypatch.context() as patch:
        patch.setattr(review.audit.os, "link", interrupted)
        with pytest.raises(review.SemanticAuditError): run(tmp_path, client)
    assert list((tmp_path / "semantic_audit/correction").glob("*.pending"))
    with pytest.raises(review.SemanticAuditError, match="review_unsettled_stage"): run(tmp_path, client)
    assert len(client.requests) == 2


def test_no_global_zero_dispatch_proof_is_accepted(tmp_path):
    with pytest.raises(review.SemanticAuditError, match="review_invalid_stage_dispatch_proof"):
        run(tmp_path, Client(), stage_dispatch_proof="c" * 64)


def test_unit_and_document_bounds_fail_explicitly_without_dispatch(tmp_path):
    client = Client()
    with pytest.raises(review.SemanticAuditError): run(tmp_path, client, pack(count=13))
    many = replace(pack()[0], original_source_text="x\n" * (review.MAX_UNITS + 1))
    with pytest.raises(review.SemanticAuditError, match="review_unit_bound"): run(tmp_path, client, (many,))
    no_original = replace(pack()[0], original_source_text=None, source_text_kind="pretokenized")
    with pytest.raises(review.SemanticAuditError, match="review_original_source_required"): run(tmp_path, client, (no_original,))
    assert not client.requests


def test_mixed_rtl_literal_units_copy_raw_offsets_and_explicit_json_control_escapes(tmp_path):
    text = "أصدر المكتب \u2066[[47]]\u2069 / \u2066[[98]]\u2069\u200e.\nإفادة أخرى."
    pages = (replace(pack()[0], primary_text=text),)
    client = Client()
    result = run(tmp_path, client, pages)
    final_request = client.requests[-1]
    assert "\\u2066" in final_request["prompt_text"] and "\\u200e" in final_request["prompt_text"]
    assert "\u2066" not in final_request["prompt_text"] and "\u200e" not in final_request["prompt_text"]
    payload = json.loads(final_request["prompt_text"])
    assert payload["candidate_pages"][0]["text"] == text
    for unit in payload["target_units"]:
        assert text[unit["start"]:unit["end"]] == unit["text"]
    assert result.selected_text_by_page[1] == text


def test_verifier_cannot_strip_controls_and_reuse_raw_candidate_offsets(tmp_path):
    text = "صياغة \u2066[[47]]\u2069\u200e."
    def wrong(stage, data, payload):
        if stage == review.STAGES[2]:
            span = data["claim_results"][0]["target_spans"][0]
            span["quote"] = span["quote"].replace("\u2066", "").replace("\u2069", "").replace("\u200e", "")
        return data
    client = Client(wrong)
    with pytest.raises(review.SemanticAuditError, match="review_evidence"):
        run(tmp_path, client, (replace(pack()[0], primary_text=text),))
    assert len(client.requests) == 3


@pytest.mark.parametrize("terminal", ["refusal", "incomplete", "cancelled_completed"])
def test_client_terminal_error_retains_actual_available_raw_and_no_repeat(tmp_path, terminal):
    class ErrorClient(Client):
        def create_page_response(self, **request):
            self.requests.append(request)
            payload = json.loads(request["prompt_text"])
            raw = json.dumps(inventory(payload)) if terminal == "cancelled_completed" else None
            raise ApiCallError("private provider failure", None,
                "CancelledError" if terminal == "cancelled_completed" else "APIError", 0, 0, 0, False,
                usage={"input_tokens": 4, "output_tokens": 2, "total_tokens": 6}, response_id="settled-error-id",
                response_status="completed" if terminal != "incomplete" else "incomplete",
                refused=terminal == "refusal", raw_output=raw)
    client = ErrorClient()
    with pytest.raises(review.SemanticAuditError): run(tmp_path, client)
    raw = json.loads((tmp_path / "semantic_audit/source_inventory/raw_response.json").read_text())
    assert raw["raw_response_available"] is (terminal == "cancelled_completed")
    assert (tmp_path / "semantic_audit/source_inventory/raw_receipt.json").is_file()
    if terminal == "cancelled_completed":
        next_client = Client()
        assert run(tmp_path, next_client).manifest_path.is_file()
        assert len(next_client.requests) == 2
    else:
        with pytest.raises(review.SemanticAuditError): run(tmp_path, client)
        assert len(client.requests) == 1


def test_stage_dispatch_proof_requires_exact_stage_intent_not_global_journal(tmp_path):
    client = Client()
    # Simulate a process stopping immediately after a durable zero-event stage intent.
    units = review.source_units(pack())
    _, _, binding = review._prepare(pack(), recipe(), PDF)
    folder = tmp_path / "semantic_audit"
    folder.mkdir()
    review.audit._write_new(folder / "intent.json", review.audit._json(binding))
    stage_folder = folder / review.STAGES[0]
    stage_folder.mkdir()
    request = review._request(review.STAGES[0], pack(), recipe(), PDF, units)
    intent = {"version": review.PROTOCOL_VERSION, "stage": review.STAGES[0],
        "review_binding_sha256": review.audit._sha(review.audit._json(binding)),
        "request_sha256": review.audit._sha(review.audit._json(request)), "predecessor_receipt_sha256": None}
    review.audit._write_new(stage_folder / "intent.json", review.audit._json(intent))
    seen = []
    def proof(**identity):
        seen.append(identity)
        return {**identity, "stage": "correction", "proof": "zero_exact_stage_events", "validated_journal_sha256": "c" * 64}
    with pytest.raises(review.SemanticAuditError, match="review_invalid_stage_dispatch_proof"):
        run(tmp_path, client, stage_dispatch_proof=proof)
    assert not client.requests and len(seen) == 1
    def exact_proof(**identity):
        return {**identity, "proof": "zero_exact_stage_events", "validated_journal_sha256": "c" * 64}
    assert run(tmp_path, client, stage_dispatch_proof=exact_proof).manifest_path.is_file()
    assert len(client.requests) == 3
    assert len(list(stage_folder.glob("undispatched_*.json"))) == 1


def test_chain_binds_prior_receipt_even_when_mutated_settlement_is_self_consistent(tmp_path):
    client = Client()
    run(tmp_path, client)
    stage = tmp_path / "semantic_audit/source_inventory"
    raw = json.loads((stage / "raw_response.json").read_text())
    data = json.loads(raw["raw_output"])
    data["claims"][0]["proposition"] = "A different derived proposition."
    raw["raw_output"] = json.dumps(data)
    (stage / "raw_response.json").write_text(review.audit._json(raw), encoding="utf-8")
    receipt = json.loads((stage / "raw_receipt.json").read_text())
    receipt["raw_sha256"] = review.audit._sha((stage / "raw_response.json").read_bytes())
    (stage / "raw_receipt.json").write_text(review.audit._json(receipt), encoding="utf-8")
    with pytest.raises(review.SemanticAuditError, match="source_binding_mismatch"): run(tmp_path, client)
    assert len(client.requests) == 3


def test_candidate_only_additional_line_cannot_avoid_target_unit_coverage(tmp_path):
    def missing(stage, data, payload):
        if stage == review.STAGES[2]:
            data["target_unit_coverage"].pop()
        return data
    pages = (replace(pack()[0], primary_text="نص أول.\nوعد إضافي غير مدعوم."),)
    with pytest.raises(review.SemanticAuditError, match="review_coverage"):
        run(tmp_path, Client(missing), pages)


@pytest.mark.parametrize("stage", review.STAGES)
@pytest.mark.parametrize("usage", [None, {}, {"input_tokens": 0}, {"output_tokens": 0},
    {"input_tokens": True, "output_tokens": 0}, {"input_tokens": 0, "output_tokens": -1},
    {"input_tokens": 4, "output_tokens": 2, "total_tokens": 9},
    {"input_tokens": 4, "output_tokens": 2, "cached_input_tokens": 5},
    {"input_tokens": 4, "output_tokens": 2, "reasoning_tokens": 3}])
def test_unknown_or_invalid_usage_stops_after_retaining_exact_stage_and_never_repeats(tmp_path, stage, usage):
    def unknown(current, data, payload):
        if current == stage:
            return ApiCallResult(json.dumps(data), usage, "known-response-id", effort="high")
        return data
    client = Client(unknown)
    with pytest.raises(review.SemanticAuditError, match="usage_unknown_or_unsettled"):
        run(tmp_path, client)
    count = len(client.requests)
    assert count == review.STAGES.index(stage) + 1
    folder = tmp_path / "semantic_audit" / stage
    envelope = json.loads((folder / "raw_response.json").read_text())
    assert envelope["usage"] == usage and (folder / "raw_receipt.json").is_file()
    assert not (tmp_path / "semantic_audit/manifest.json").exists()
    with pytest.raises(review.SemanticAuditError, match="usage_unknown_or_unsettled"):
        run(tmp_path, client)
    assert len(client.requests) == count


@pytest.mark.parametrize("usage,expected_total", [
    ({"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}, 0),
    ({"input_tokens": 4, "output_tokens": 2}, 18),
    ({"input_tokens": 4, "output_tokens": 2, "total_tokens": None}, 18),
])
def test_actual_zero_usage_and_existing_total_derivation_rules_are_preserved(tmp_path, usage, expected_total):
    def known(stage, data, payload):
        return ApiCallResult(json.dumps(data), deepcopy(usage), "known-response-id", effort="high")
    client = Client(known)
    result = run(tmp_path, client)
    assert len(client.requests) == 3 and result.usage["total_tokens"] == expected_total
    assert result.usage["stages"] == {stage: usage for stage in review.STAGES}


def _swap_verifier_span_pages(data, payload):
    target = {unit["page"]: unit for unit in payload["target_units"]}
    inverse = {unit["unit_id"]: [] for unit in payload["target_units"]}
    for row in data["claim_results"]:
        original_page = row["target_spans"][0]["page"]
        unit = target[3 - original_page]
        row["target_spans"] = [{**{k: unit[k] for k in ("page", "start", "end")}, "quote": unit["text"]}]
        inverse[unit["unit_id"]].append(row["claim_id"])
    data["target_unit_coverage"] = [{"unit_id": key, "claim_ids": ids} for key, ids in inverse.items()]


def test_complete_propositions_swapped_between_separate_source_pages_are_not_approved(tmp_path):
    pages = (
        replace(pack()[0], source_text="The northern office issued a notice.", original_source_text="The northern office issued a notice.", primary_text="أصدر المكتب الشمالي إشعارا."),
        replace(pack(count=2)[1], source_text="The southern office issued a notice.", original_source_text="The southern office issued a notice.", primary_text="أصدر المكتب الجنوبي إشعارا."),
    )
    def moved(stage, data, payload):
        if stage == review.STAGES[1]:
            for row, original in zip(data["pages"], reversed(pages)):
                row.update(status="corrected", corrected_text=original.primary_text, reason_codes=["agency"])
        if stage == review.STAGES[2]:
            _swap_verifier_span_pages(data, payload)
        return data
    client = Client(moved)
    with pytest.raises(review.SemanticAuditError, match="review_page_ownership"):
        run(tmp_path, client, pages)
    assert len(client.requests) == 3
    assert not (tmp_path / "semantic_audit/manifest.json").exists()
    assert not list((tmp_path / "semantic_audit").glob("page_*.txt"))


def test_image_only_claim_cannot_be_attested_on_another_page(tmp_path):
    pages = tuple(replace(page, source_text="", original_source_text="") for page in pack(count=2))
    def moved(stage, data, payload):
        if stage == review.STAGES[2]: _swap_verifier_span_pages(data, payload)
        return data
    client = Client(moved)
    with pytest.raises(review.SemanticAuditError, match="review_page_ownership"):
        run(tmp_path, client, pages)
    assert len(client.requests) == 3 and not (tmp_path / "semantic_audit/manifest.json").exists()


def test_cross_page_claim_cannot_drop_one_of_its_source_owner_pages(tmp_path):
    def dropped(stage, data, payload):
        if stage == review.STAGES[0]:
            first, second = data["claims"]
            first["source_unit_ids"] += second["source_unit_ids"]
            first["source_evidence"] += second["source_evidence"]
            data["claims"] = [first]
            for row in data["unit_coverage"]: row["claim_ids"] = [first["claim_id"]]
            data["boundaries"][0].update(relation="continuation", claim_ids=[first["claim_id"]])
        elif stage == review.STAGES[2]:
            data["claim_results"][0]["target_spans"] = data["claim_results"][0]["target_spans"][:1]
        return data
    with pytest.raises(review.SemanticAuditError, match="review_page_ownership"):
        run(tmp_path, Client(dropped), pack(count=2))
    assert not (tmp_path / "semantic_audit/manifest.json").exists()


def test_additional_context_evidence_page_does_not_become_claim_owner(tmp_path):
    def context(stage, data, payload):
        if stage == review.STAGES[0]:
            data["claims"][0]["source_evidence"].append(deepcopy(data["claims"][1]["source_evidence"][0]))
        return data
    client = Client(context)
    result = run(tmp_path, client, pack(count=2))
    payload = json.loads(client.requests[-1]["prompt_text"])
    first = payload["source_inventory"]["claims"][0]
    assert {span["page"] for span in first["source_evidence"]} == {1, 2}
    assert len(first["source_unit_ids"]) == 1
    assert result.manifest_path.is_file()
