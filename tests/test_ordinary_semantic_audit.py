"""Fictional document tests: no providers, credentials, native apps or private text."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from legalpdf_translate import ordinary_semantic_audit as audit


IMAGE = "data:image/png;base64,aW1hZ2U="
PDF = "a" * 64
RECIPE = audit.SemanticAuditRecipe("gpt-5.2", "high", effort_policy="adaptive")


def token(value):
    return "\u2066[[" + value + "]]\u2069"


def page(number=1, **kwargs):
    return replace(audit.SemanticAuditPage(number, "O requerente pediu uma resposta.", (), IMAGE,
                   "طلب مقدم الطلب جوابا."), **kwargs)


def payload(pages, *, corrections=None):
    corrections = corrections or {}
    return json.dumps({"version": audit.AUDIT_VERSION, "pages": [
        {"page_number": p.page_number, "status": "corrected" if p.page_number in corrections else "no_change",
         "corrected_text": corrections.get(p.page_number, ""),
         "reason_codes": ["actor_recipient"] if p.page_number in corrections else []} for p in pages]}, ensure_ascii=False)


class Client:
    model = "gpt-5.2"

    def __init__(self, raw, **overrides):
        self.calls = []
        self.result = SimpleNamespace(raw_output=raw, usage={"input_tokens": 123, "output_tokens": 44},
            response_id="fake-response", response_status="completed", refused=False, incomplete_reason=None,
            model="gpt-5.2-2025-12-11", effort="high", attempt_usage=[], **overrides)

    def create_page_response(self, **request):
        self.calls.append(request)
        return self.result


def run(tmp_path, pages, client, **kwargs):
    return audit.run_semantic_audit(pages=pages, recipe=RECIPE, pdf_sha256=PDF,
        evidence_dir=tmp_path / "audit", client=client, **kwargs)


def test_complete_unchanged_audit_retains_primary_and_reuses_without_client(tmp_path):
    pages = [page(2), page(3)]
    client = Client(payload(pages))
    result = run(tmp_path, pages, client)
    assert len(client.calls) == 1
    assert result.selected_text_by_page == {2: pages[0].primary_text, 3: pages[1].primary_text}
    assert result.usage == {"input_tokens": 123, "output_tokens": 44}
    assert result.response_id == "fake-response" and not result.reused
    before = {p.name: p.read_bytes() for p in result.manifest_path.parent.iterdir()}
    loaded = audit.load_semantic_audit(pages=pages, recipe=RECIPE, pdf_sha256=PDF,
        evidence_dir=result.manifest_path.parent)
    assert loaded.reused and loaded.selected_text_by_page == result.selected_text_by_page
    assert before == {p.name: p.read_bytes() for p in result.manifest_path.parent.iterdir()}
    assert loaded.binding_sha256 == audit.semantic_audit_source_fingerprint(pages, RECIPE, PDF)
    assert json.loads(result.manifest_path.read_text(encoding="utf-8"))["human_review_complete"] is False


def test_correction_selects_new_owned_candidate_and_preserves_primary(tmp_path):
    pages = [page()]
    original_file = tmp_path / "primary.txt"
    original_file.write_text(pages[0].primary_text, encoding="utf-8")
    correction = "طلب المدعى عليه جوابا."
    result = run(tmp_path, pages, Client(payload(pages, corrections={1: correction})))
    assert result.selected_text_by_page[1] == correction
    assert (result.manifest_path.parent / "page_0001.txt").read_text(encoding="utf-8") == correction
    assert original_file.read_text(encoding="utf-8") == pages[0].primary_text


def test_request_contains_all_pages_images_originals_and_cross_page_context():
    pages = [page(3, source_text="continuação", source_text_kind="pretokenized", original_source_text="Continuação original"),
             page(4, source_text="novo documento", primary_text="محضر مستقل")]
    request = audit.build_semantic_audit_request(pages, RECIPE, PDF)
    parsed = json.loads(request["prompt_text"])
    assert [p["page_number"] for p in parsed["pages"]] == [3, 4]
    assert [p["image_position"] for p in parsed["pages"]] == [1, 2]
    assert parsed["pages"][0]["source_text"] == "continuação"
    assert parsed["pages"][0]["original_source_text"] == "Continuação original"
    assert request["image_data_urls"] == (IMAGE, IMAGE)
    assert request["max_output_tokens"] == 32000 and request["timeout_seconds"] == 480
    assert request["response_format"]["strict"] is True
    for concept in ["cross-page grammar", "local folios", "document boundaries", "do not paraphrase", "untrusted document data"]:
        assert concept in request["instructions"]


@pytest.mark.parametrize("change", ["missing", "duplicate", "reordered", "extra", "wrong_type"])
def test_response_must_cover_exact_ordered_source_pages(change):
    pages = [page(2), page(3)]
    data = json.loads(payload(pages))
    if change == "missing": data["pages"].pop()
    if change == "duplicate": data["pages"][1] = data["pages"][0]
    if change == "reordered": data["pages"].reverse()
    if change == "extra": data["pages"].append(data["pages"][0])
    if change == "wrong_type": data["pages"][0]["page_number"] = "2"
    with pytest.raises(audit.SemanticAuditError, match="page_coverage"):
        audit.validate_semantic_audit_response(json.dumps(data), pages)


@pytest.mark.parametrize("change", ["version", "unknown_field", "no_change_text", "unknown_reason", "duplicate_reason",
                                   "empty_correction", "no_correction_reason", "code_fence", "unknown_status"])
def test_strict_schema_and_decision_contract(change):
    pages = [page()]
    data = json.loads(payload(pages))
    record = data["pages"][0]
    if change == "version": data["version"] = "future"
    if change == "unknown_field": record["human_review_complete"] = True
    if change == "no_change_text": record["corrected_text"] = "نص"
    if change == "unknown_reason": record["reason_codes"] = ["custom_reference_answer"]
    if change == "duplicate_reason": record["reason_codes"] = ["agency", "agency"]
    if change in {"empty_correction", "no_correction_reason", "code_fence"}:
        record.update(status="corrected", corrected_text="نص", reason_codes=["agency"])
        if change == "empty_correction": record["corrected_text"] = ""
        if change == "no_correction_reason": record["reason_codes"] = []
        if change == "code_fence": record["corrected_text"] = "```نص```"
    if change == "unknown_status": record["status"] = []
    with pytest.raises(audit.SemanticAuditError, match="response_shape"):
        audit.validate_semantic_audit_response(json.dumps(data), pages)


@pytest.mark.parametrize("raw", ["not json", '{"version":"x","version":"y","pages":[]}',
                               '{"version":NaN,"pages":[]}'])
def test_invalid_or_ambiguous_json_is_rejected(raw):
    with pytest.raises(audit.SemanticAuditError, match="invalid_json"):
        audit.validate_semantic_audit_response(raw, [page()])


def test_whole_response_validated_before_any_correction_evaluation(monkeypatch):
    pages = [page(1), page(2)]
    raw = json.loads(payload(pages, corrections={1: "نص مصحح"}))
    raw["pages"][1]["status"] = "unresolved"
    monkeypatch.setattr(audit, "evaluate_output", lambda *a, **k: pytest.fail("premature correction evaluation"))
    with pytest.raises(audit.SemanticAuditError, match="unresolved"):
        audit.validate_semantic_audit_response(json.dumps(raw), pages)


def test_correction_cannot_delete_additional_primary_literal():
    primary = "نص " + token("Required") + " " + token("Selim Example")
    pages = [page(source_text=token("Required"), source_text_kind="pretokenized",
                  expected_ar_tokens=("Required",), primary_text=primary)]
    raw = payload(pages, corrections={1: "نص " + token("Required")})
    with pytest.raises(audit.SemanticAuditError, match="correction_literal_or_language_failure"):
        audit.validate_semantic_audit_response(raw, pages)


def test_correction_cannot_move_literal_to_another_page():
    pages = [page(1, source_text="7", expected_ar_tokens=("7",), primary_text="نص " + token("7")), page(2)]
    with pytest.raises(audit.SemanticAuditError, match="correction_literal_or_language_failure"):
        audit.validate_semantic_audit_response(payload(pages, corrections={1: "نص", 2: "نص " + token("7")}), pages)


def test_exact_pretokenized_source_not_rebuilt(monkeypatch):
    captured = "نص " + token("7")
    pages = [page(source_text=captured, original_source_text="raw 7", source_text_kind="pretokenized",
                  expected_ar_tokens=("7",), primary_text="نص " + token("7"))]
    real = audit.evaluate_output
    seen = []
    def evaluate(*args, **kwargs):
        seen.append(kwargs["ar_source_text"])
        return real(*args, **kwargs)
    monkeypatch.setattr(audit, "evaluate_output", evaluate)
    monkeypatch.setattr(audit, "pretokenize_arabic_source", lambda _: pytest.fail("rebuilt captured source"))
    selected, _ = audit.validate_semantic_audit_response(payload(pages, corrections={1: "نص مصحح " + token("7")}), pages)
    assert seen == [captured] and token("7") in selected[1]


def test_new_actionable_citation_omission_is_rejected_with_number_preserved():
    pages = [page(source_text="artigo 7", expected_ar_tokens=("7",), primary_text="المادة " + token("7"))]
    with pytest.raises(audit.SemanticAuditError, match="new_actionable_quality_failure"):
        audit.validate_semantic_audit_response(payload(pages, corrections={1: "نص " + token("7")}), pages)


@pytest.mark.parametrize("source,primary,correction,expected", [
    ("artigo 7; artigo 8", "المادة {7}؛ نص {8}", "نص {7}؛ المادة {8}", ("7", "8")),
    ("artigo 7; artigo 7; artigo 8", "المادة {7}؛ المادة {7}؛ نص {8}",
     "المادة {7}؛ نص {7}؛ المادة {8}", ("7", "7", "8")),
    ("1. pedido\n2. resposta", "{1}. طلب\nنص {2}", "نص {1}\n{2}. جواب", ("1", "2")),
    ("[7] [8]", "[{7}] نص {8}", "نص {7} [{8}]", ("7", "8")),
])
def test_equal_aggregate_defects_cannot_swap_source_backed_anchor_identity_or_multiplicity(source, primary, correction, expected):
    for value in set(expected):
        primary = primary.replace("{" + value + "}", token(value))
        correction = correction.replace("{" + value + "}", token(value))
    pages = [page(source_text=source, expected_ar_tokens=expected, primary_text=primary)]
    before = audit.run_all_quality_checks(source_text=source, output_text=primary, target_lang="AR")
    after = audit.run_all_quality_checks(source_text=source, output_text=correction, target_lang="AR")
    for field in ("numeric_mismatches_count", "citation_actionable_missing_count", "bidi_actionable_count"):
        assert before[field] == after[field]
    with pytest.raises(audit.SemanticAuditError, match="new_actionable_quality_failure"):
        audit.validate_semantic_audit_response(payload(pages, corrections={1: correction}), pages)


def test_correction_may_restore_missing_anchor_while_preserving_preexisting_ones():
    pages = [page(source_text="artigo 7; artigo 8", expected_ar_tokens=("7", "8"),
                  primary_text="المادة " + token("7") + "؛ نص " + token("8"))]
    corrected = "المادة " + token("7") + "؛ المادة " + token("8")
    selected, _ = audit.validate_semantic_audit_response(payload(pages, corrections={1: corrected}), pages)
    assert selected[1] == corrected


@pytest.mark.parametrize("field", ["numeric_mismatches_count", "citation_actionable_missing_count", "bidi_actionable_count",
                                  "visible_replacement_char_count"])
def test_actionable_quality_guard_compares_to_primary_not_blanket_zero(monkeypatch, field):
    pages = [page()]
    fields = ["numeric_mismatches_count", "citation_actionable_missing_count", "bidi_actionable_count", "visible_replacement_char_count"]
    def checks(**kwargs):
        return {key: (2 if kwargs["output_text"] == "نص مصحح" and key == field else 1) for key in fields}
    monkeypatch.setattr(audit, "run_all_quality_checks", checks)
    with pytest.raises(audit.SemanticAuditError, match="new_actionable_quality_failure"):
        audit.validate_semantic_audit_response(payload(pages, corrections={1: "نص مصحح"}), pages)
    monkeypatch.setattr(audit, "run_all_quality_checks", lambda **kwargs: {key: 1 for key in fields})
    selected, _ = audit.validate_semantic_audit_response(payload(pages, corrections={1: "نص مصحح"}), pages)
    assert selected[1] == "نص مصحح"


@pytest.mark.parametrize("field,value,code", [("refused", True, "provider_refusal"),
    ("response_status", "incomplete", "provider_incomplete"), ("incomplete_reason", "max_output_tokens", "provider_incomplete")])
def test_refusal_and_incomplete_retained_without_repurchase(tmp_path, field, value, code):
    pages = [page()]
    client = Client(payload(pages))
    setattr(client.result, field, value)
    for _ in range(2):
        with pytest.raises(audit.SemanticAuditError, match=code): run(tmp_path, pages, client)
    assert len(client.calls) == 1
    assert (tmp_path / "audit/raw_response.json").is_file()
    assert not (tmp_path / "audit/manifest.json").exists()


@pytest.mark.parametrize("refused,status,code", [(True, "completed", "provider_refusal"),
                                             (False, "incomplete", "provider_incomplete")])
def test_client_raised_rejection_is_retained_with_usage_and_never_repeated(tmp_path, refused, status, code):
    class RejectedResponse(RuntimeError):
        pass
    pages = [page()]
    client = Client(payload(pages))
    error = RejectedResponse("PRIVATE REFUSAL TEXT")
    for key, value in vars(client.result).items():
        if key != "raw_output": setattr(error, key, value)
    error.refused, error.response_status = refused, status
    def reject(**kwargs):
        client.calls.append(kwargs)
        raise error
    client.create_page_response = reject
    for _ in range(2):
        with pytest.raises(audit.SemanticAuditError, match=code) as failure: run(tmp_path, pages, client)
        assert "PRIVATE" not in str(failure.value)
    assert len(client.calls) == 1
    retained = json.loads((tmp_path / "audit/raw_response.json").read_text(encoding="utf-8"))
    assert retained["usage"] == client.result.usage
    assert retained["raw_response_available"] is False
    assert "PRIVATE" not in json.dumps(retained)


def test_cancelled_settled_response_recovers_locally_only_after_explicit_resume(tmp_path):
    from legalpdf_translate.openai_client import ApiCallError

    pages = [page()]
    raw = payload(pages, corrections={1: "طلب المدعى عليه جوابا."})
    client = Client(raw)
    error = ApiCallError("Cancelled", None, "CancelledError", 0, 0.0, 0.0, False,
        usage=client.result.usage, response_id="fake-response", response_status="completed",
        raw_output=raw, model="gpt-5.2-2025-12-11", effort="high")

    def cancelled(**kwargs):
        client.calls.append(kwargs)
        raise error

    client.create_page_response = cancelled
    with pytest.raises(audit.SemanticAuditError, match="operation_cancelled"):
        run(tmp_path, pages, client)
    directory = tmp_path / "audit"
    assert (directory / "raw_response.json").is_file()
    assert (directory / "raw_receipt.json").is_file()
    assert not (directory / "manifest.json").exists()
    assert not list(directory.glob("page_*.txt"))
    before = (directory / "raw_response.json").read_bytes()
    resumed = audit.load_semantic_audit(pages=pages, recipe=RECIPE, pdf_sha256=PDF,
        evidence_dir=directory)
    assert resumed.reused
    assert resumed.selected_text_by_page[1] == "طلب المدعى عليه جوابا."
    assert len(client.calls) == 1
    assert (directory / "raw_response.json").read_bytes() == before


def test_zero_dispatch_resume_requires_explicit_bound_durable_journal_proof(tmp_path):
    pages = [page()]
    client = Client(payload(pages))
    create = client.create_page_response
    client.create_page_response = lambda **_: (_ for _ in ()).throw(RuntimeError("before dispatch"))
    with pytest.raises(audit.SemanticAuditError, match="provider_operation_unsettled"):
        run(tmp_path, pages, client)
    original = (tmp_path / "audit/intent.json").read_bytes()
    client.create_page_response = create
    with pytest.raises(audit.SemanticAuditError, match="unsettled_intent"):
        run(tmp_path, pages, client)
    assert not client.calls
    result = run(tmp_path, pages, client, undispatched_journal_sha256="b" * 64)
    assert result.reused and len(client.calls) == 1
    assert (tmp_path / "audit/intent.json").read_bytes() == original
    markers = list((tmp_path / "audit").glob("undispatched_resume_*.json"))
    assert len(markers) == 1
    proof = json.loads(markers[0].read_text(encoding="utf-8"))
    assert proof["binding_sha256"] == result.binding_sha256
    assert proof["validated_journal_sha256"] == "b" * 64


@pytest.mark.parametrize("artifact", ["raw_response.json", "raw_receipt.json", "page_0001.txt",
                                     "manifest.json", "raw_response.json.pending"])
def test_zero_dispatch_proof_cannot_repurchase_partial_or_published_evidence(tmp_path, artifact):
    pages = [page()]
    client = Client(payload(pages))
    create = client.create_page_response
    client.create_page_response = lambda **_: (_ for _ in ()).throw(RuntimeError("before dispatch"))
    with pytest.raises(audit.SemanticAuditError, match="provider_operation_unsettled"):
        run(tmp_path, pages, client)
    client.create_page_response = create
    (tmp_path / "audit" / artifact).write_text("retained", encoding="utf-8")
    with pytest.raises(audit.SemanticAuditError, match="unsettled_intent"):
        run(tmp_path, pages, client, undispatched_journal_sha256="b" * 64)
    assert not client.calls


def test_unresolved_retained_and_no_selected_pages_published(tmp_path):
    pages = [page(1), page(2)]
    data = json.loads(payload(pages, corrections={1: "نص مصحح"}))
    data["pages"][1]["status"] = "unresolved"
    client = Client(json.dumps(data))
    for _ in range(2):
        with pytest.raises(audit.SemanticAuditError, match="unresolved"): run(tmp_path, pages, client)
    assert len(client.calls) == 1
    assert list((tmp_path / "audit").glob("page_*.txt")) == []


@pytest.mark.parametrize("file", ["page_0001.txt", "raw_response.json", "manifest.json", "raw_receipt.json"])
def test_corruption_fails_without_any_repeat_provider_call(tmp_path, file):
    pages = [page()]
    client = Client(payload(pages))
    run(tmp_path, pages, client)
    (tmp_path / "audit" / file).write_text("corrupt", encoding="utf-8")
    with pytest.raises(audit.SemanticAuditError): run(tmp_path, pages, client)
    assert len(client.calls) == 1


@pytest.mark.parametrize("change", ["pdf", "source", "original", "primary", "image", "tokens", "kind", "recipe"])
def test_manifest_is_bound_to_every_source_and_recipe_input(tmp_path, change):
    pages = [page()]
    client = Client(payload(pages))
    run(tmp_path, pages, client)
    recipe, pdf = RECIPE, PDF
    changed = {"source": {"source_text": "Outra fonte."}, "original": {"original_source_text": "Original distinto"},
        "primary": {"primary_text": "نص آخر"}, "image": {"image_data_url": "data:image/png;base64,b3RoZXI="},
        "tokens": {"expected_ar_tokens": ("Required",)}, "kind": {"source_text_kind": "pretokenized"}}
    if change in changed: pages = [replace(pages[0], **changed[change])]
    if change == "pdf": pdf = "b" * 64
    if change == "recipe": recipe = replace(recipe, reasoning_effort="xhigh")
    with pytest.raises(audit.SemanticAuditError, match="source_binding_mismatch"):
        audit.run_semantic_audit(pages=pages, recipe=recipe, pdf_sha256=pdf, evidence_dir=tmp_path / "audit", client=client)
    assert len(client.calls) == 1


def test_unknown_provider_outcome_blocks_repurchase_and_hides_error_text(tmp_path):
    pages = [page()]
    client = Client(payload(pages))
    def fail(**kwargs):
        client.calls.append(kwargs)
        raise RuntimeError("PRIVATE PROVIDER CONTENT")
    client.create_page_response = fail
    with pytest.raises(audit.SemanticAuditError, match="provider_operation_unsettled") as error:
        run(tmp_path, pages, client)
    assert "PRIVATE" not in str(error.value)
    with pytest.raises(audit.SemanticAuditError, match="unsettled_intent"): run(tmp_path, pages, client)
    assert len(client.calls) == 1


def test_complete_raw_response_recovers_locally_after_manifest_publication_failure(tmp_path, monkeypatch):
    pages = [page()]
    client = Client(payload(pages, corrections={1: "نص مصحح"}))
    write = audit._write_new
    def interrupted(path, content):
        if path.name == "manifest.json": raise audit.SemanticAuditError("injected_interruption")
        write(path, content)
    monkeypatch.setattr(audit, "_write_new", interrupted)
    with pytest.raises(audit.SemanticAuditError, match="injected_interruption"): run(tmp_path, pages, client)
    assert not (tmp_path / "audit/manifest.json").exists()
    monkeypatch.setattr(audit, "_write_new", write)
    result = audit.load_semantic_audit(pages=pages, recipe=RECIPE, pdf_sha256=PDF, evidence_dir=tmp_path / "audit")
    assert result.reused and result.selected_text_by_page[1] == "نص مصحح"
    assert len(client.calls) == 1


def test_settled_receipt_required_even_if_raw_file_was_written(tmp_path, monkeypatch):
    pages = [page()]
    client = Client(payload(pages))
    write = audit._write_new
    def interrupted(path, content):
        if path.name == "raw_receipt.json": raise audit.SemanticAuditError("injected_interruption")
        write(path, content)
    monkeypatch.setattr(audit, "_write_new", interrupted)
    with pytest.raises(audit.SemanticAuditError): run(tmp_path, pages, client)
    monkeypatch.setattr(audit, "_write_new", write)
    with pytest.raises(audit.SemanticAuditError, match="unsettled_intent"): run(tmp_path, pages, client)
    assert len(client.calls) == 1


def test_manifest_published_last_after_all_selected_hashes_exist(tmp_path, monkeypatch):
    pages = [page(1), page(2)]
    write = audit._write_new
    def observe(path, content):
        if path.name == "manifest.json":
            for p in pages: assert (path.parent / f"page_{p.page_number:04d}.txt").is_file()
        write(path, content)
    monkeypatch.setattr(audit, "_write_new", observe)
    run(tmp_path, pages, Client(payload(pages)))


@pytest.mark.parametrize("target", ["page_0001.txt", "manifest.json"])
@pytest.mark.parametrize("conflicting", [False, True])
def test_interruption_after_staging_fsync_before_link_recovers_without_repurchase(tmp_path, monkeypatch, target, conflicting):
    pages = [page()]
    client = Client(payload(pages))
    publish = audit.os.link
    staged = []
    def interrupt(source, destination):
        if Path(destination).name == target and not staged:
            # _write_new has already flushed and fsynced these complete bytes.
            assert Path(source).is_file() and Path(source).read_bytes()
            staged.append(Path(source))
            raise OSError("injected process interruption")
        publish(source, destination)
    monkeypatch.setattr(audit.os, "link", interrupt)
    with pytest.raises(audit.SemanticAuditError, match="evidence_write_failure"):
        run(tmp_path, pages, client)
    assert len(staged) == 1 and not (tmp_path / "audit" / target).exists()
    if conflicting:
        staged[0].write_text("conflicting retained beforeimage", encoding="utf-8")
    retained_beforeimage = staged[0].read_bytes()
    monkeypatch.setattr(audit.os, "link", publish)
    result = audit.load_semantic_audit(pages=pages, recipe=RECIPE, pdf_sha256=PDF, evidence_dir=tmp_path / "audit")
    assert result.reused and result.selected_text_by_page == {1: pages[0].primary_text}
    assert result.manifest_path.is_file() and len(client.calls) == 1
    assert staged[0].read_bytes() == retained_beforeimage


def test_interruption_before_raw_publication_never_repeats_provider(tmp_path, monkeypatch):
    pages = [page()]
    client = Client(payload(pages))
    publish = audit.os.link
    def interrupt(source, destination):
        if Path(destination).name == "raw_response.json": raise OSError("injected raw interruption")
        publish(source, destination)
    monkeypatch.setattr(audit.os, "link", interrupt)
    with pytest.raises(audit.SemanticAuditError, match="evidence_write_failure"): run(tmp_path, pages, client)
    staged = list((tmp_path / "audit").glob("raw_response.json.*.pending"))
    assert len(staged) == 1
    before = staged[0].read_bytes()
    monkeypatch.setattr(audit.os, "link", publish)
    with pytest.raises(audit.SemanticAuditError, match="unsettled_intent"): run(tmp_path, pages, client)
    assert len(client.calls) == 1 and staged[0].read_bytes() == before


@pytest.mark.parametrize("pages,recipe,pdf,code", [
    ([], RECIPE, PDF, "page_bound"), ([page(n + 1) for n in range(13)], RECIPE, PDF, "page_bound"),
    ([page(2), page(1)], RECIPE, PDF, "page_order"), ([page(1), page(1)], RECIPE, PDF, "page_order"),
    ([page()], replace(RECIPE, timeout_seconds=float("inf")), PDF, "invalid_recipe"),
    ([page()], replace(RECIPE, timeout_seconds=481), PDF, "invalid_recipe"),
    ([page()], replace(RECIPE, max_output_tokens=32001), PDF, "invalid_recipe"),
    ([page()], RECIPE, "bad", "invalid_pdf_hash"), ([page(image_data_url="https://example.test/image")], RECIPE, PDF, "invalid_image"),
    ([page(image_data_url="data:image/png;base64,=broken=")], RECIPE, PDF, "invalid_image"),
    ([page(source_text="x" * (audit.MAX_TEXT_CHARS + 1))], RECIPE, PDF, "source_pack_bound")])
def test_finite_bounds_fail_before_dispatch(pages, recipe, pdf, code):
    with pytest.raises(audit.SemanticAuditError, match=code):
        audit.build_semantic_audit_request(pages, recipe, pdf)


def test_no_client_loader_cannot_purchase_missing_audit(tmp_path):
    with pytest.raises(audit.SemanticAuditError, match="retained_audit_missing"):
        audit.load_semantic_audit(pages=[page()], recipe=RECIPE, pdf_sha256=PDF, evidence_dir=tmp_path / "absent")
    assert not (tmp_path / "absent/intent.json").exists()


def test_total_image_bound_and_missing_image_fail_explicitly(monkeypatch):
    with pytest.raises(audit.SemanticAuditError, match="invalid_image"):
        audit.build_semantic_audit_request([page(image_data_url=None)], RECIPE, PDF)
    monkeypatch.setattr(audit, "MAX_IMAGE_BYTES", 8)
    with pytest.raises(audit.SemanticAuditError, match="source_pack_bound"):
        audit.build_semantic_audit_request([page(1), page(2)], RECIPE, PDF)


def test_frozen_pack_does_not_retain_mutable_page_or_token_lists(tmp_path):
    inventory = []
    pages = [page(expected_ar_tokens=inventory)]
    original = pages[0]
    client = Client(payload(pages))
    send = client.create_page_response
    def mutate_external_pack(**kwargs):
        inventory.append("Unexpected")
        pages[:] = [page(2)]
        return send(**kwargs)
    client.create_page_response = mutate_external_pack
    result = run(tmp_path, pages, client)
    assert original.expected_ar_tokens == ()
    assert result.selected_text_by_page == {1: original.primary_text}


def test_model_mismatch_does_not_even_create_intent(tmp_path):
    client = Client(payload([page()]))
    client.model = "other-model"
    with pytest.raises(audit.SemanticAuditError, match="client_model_mismatch"): run(tmp_path, [page()], client)
    assert not client.calls and not (tmp_path / "audit/intent.json").exists()


def test_image_off_request_is_explicitly_text_only_and_omits_client_image_argument(tmp_path):
    recipe = replace(RECIPE, configured_image_mode="off")
    pages = [page(3, image_data_url=None, visual_coverage="text_only_configured_image_off"),
             page(4, image_data_url=None, visual_coverage="text_only_configured_image_off")]
    client = Client(payload(pages))
    result = audit.run_semantic_audit(pages=pages, recipe=recipe, pdf_sha256=PDF, evidence_dir=tmp_path / "audit", client=client)
    request = client.calls[0]
    assert "image_data_urls" not in request and "image_data_url" not in request
    pack = json.loads(request["prompt_text"])
    assert pack["configured_image_mode"] == "off" and pack["source_image_policy"] == "configured_image_mode_v1"
    assert all(p["image_position"] is None and p["visual_evidence_available"] is False for p in pack["pages"])
    assert all(p["visual_coverage"] == "text_only_configured_image_off" for p in pack["pages"])
    assert "no images or\nvisual evidence are available" in request["instructions"]
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert all(p["image_sha256"] is None and p["visual_coverage"] == "text_only_configured_image_off"
               for p in manifest["binding"]["pages"])
    restored = audit.load_semantic_audit(pages=pages, recipe=recipe, pdf_sha256=PDF, evidence_dir=tmp_path / "audit")
    assert restored.reused and len(client.calls) == 1
    assert restored.binding_sha256 != audit.semantic_audit_source_fingerprint([page(3), page(4)], RECIPE, PDF)


@pytest.mark.parametrize("mode", ["auto", "always"])
def test_image_auto_and_always_still_require_each_source_image(mode):
    with pytest.raises(audit.SemanticAuditError, match="invalid_image"):
        audit.build_semantic_audit_request([page(1), page(2, image_data_url=None)],
                                          replace(RECIPE, configured_image_mode=mode), PDF)


@pytest.mark.parametrize("page_overrides,recipe_overrides", [
    ({"image_data_url": None}, {"configured_image_mode": "off"}),
    ({}, {"configured_image_mode": "off"}),
    ({"visual_coverage": "text_only_configured_image_off"}, {}),
])
def test_explicit_visual_coverage_and_configured_mode_must_agree(page_overrides, recipe_overrides):
    with pytest.raises(audit.SemanticAuditError, match="invalid_image_policy"):
        audit.build_semantic_audit_request([page(**page_overrides)], replace(RECIPE, **recipe_overrides), PDF)
