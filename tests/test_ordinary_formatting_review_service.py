"""Public OCR actions -> real ordinary commits -> explicit visual decisions.

Only local OCR and SDK boundaries are synthetic. No prebuilt source review,
acceptance authority, structured commit or private formatting fixture is used.
"""
from copy import deepcopy
from dataclasses import replace
import io
import json
import threading
import traceback
from types import SimpleNamespace
import zipfile

import pytest

from legalpdf_translate import ordinary_formatting_review_service as service_module
from legalpdf_translate.checkpoint import load_run_state, settings_fingerprint
from legalpdf_translate.openai_client import OpenAIResponsesClient
from legalpdf_translate.ordinary_formatting_review_service import (
    OrdinaryFormattingReviewService, FormattingReviewServiceError,
    FormattingFragment, FormattingParagraph, FormattingTable, FormattingPageDecision,
    FormattingDocumentDecision, FormattingDocumentGroup,
)
from legalpdf_translate.ordinary_source_review_service import OrdinarySourceReviewService, SourceReviewAction
from legalpdf_translate.reviewed_formatting_writer import validate_reviewed_docx, ReviewedFormattingWriterError
from legalpdf_translate.run_docx_formatting import OPERATOR_REVIEW_PROFILE, prepare_run_docx_formatting
from legalpdf_translate.run_workspace_lock import run_workspace_slot
from legalpdf_translate.types import TargetLang
from legalpdf_translate.workflow import TranslationWorkflow
from tests.test_ordinary_source_review_service import (
    local_only, local_pass, config_case, explicit_decision,
)


def public_case(tmp_path, monkeypatch, *, lang=TargetLang.EN, count=1, folios=False, multiline=False, pipe_cells=False,
                page_breaks=True, strip_bidi_controls=True):
    local_calls = local_pass(monkeypatch)
    config = replace(config_case(tmp_path, count=count), target_lang=lang, page_breaks=page_breaks,
                     strip_bidi_controls=strip_bidi_controls)
    source_service = OrdinarySourceReviewService(config)
    draft = source_service.prepare()
    for page in draft["pages"]:
        decision = explicit_decision(page)
        actions = list(decision.actions)
        if multiline:
            actions[0] = replace(actions[0], kind="replace",
                after_text=actions[0].after_text + " 😀\nSegunda linha.",
                rationale="Fictional explicit source correction following image comparison.")
        if pipe_cells:
            actions[0] = replace(actions[0], kind="replace", after_text=actions[0].after_text + " | Referência 987",
                rationale="Fictional explicit review of the complete printed metadata row.")
        if folios:
            actions.append(SourceReviewAction("printed_folio", "transcribe", (), "Pág. 1 de 1",
                (130, 270, 190, 290), "Fictional operator transcribes the printed local folio."))
        decision = replace(decision, actions=tuple(actions), reading_order=tuple(a.id for a in actions))
        draft = source_service.save_page(draft["draft_id"], expected_generation=draft["generation"],
            page_number=page["page_number"], decision=decision)
    accepted = source_service.submit(draft["draft_id"], expected_generation=draft["generation"],
        reviewer="Fictional source operator", accept_source=True)
    context = source_service.load_context(accepted["revision_id"])
    calls = []
    def create(**request):
        calls.append(request)
        prompt, _ = json.JSONDecoder().raw_decode(request["input"][0]["content"][0]["text"])
        blocks = []
        for block in prompt["blocks"]:
            text = block["text"]
            if "Processo" in text:
                target = {TargetLang.EN: "Case 121/26", TargetLang.FR: "Affaire 121/26",
                          TargetLang.AR: "القضية [[121/26]]"}[lang]
                if multiline:
                    target += " 😀\n" + {TargetLang.EN: "The second line.", TargetLang.FR: "La deuxième ligne.",
                                           TargetLang.AR: "السطر الثاني."}[lang]
                if pipe_cells:
                    target += " | " + {TargetLang.EN: "Reference 987", TargetLang.FR: "Référence 987",
                                        TargetLang.AR: "المرجع [[987]]"}[lang]
            elif "Artigo" in text:
                target = {TargetLang.EN: "Article 42", TargetLang.FR: "Article 42",
                          TargetLang.AR: "المادة [[42]]"}[lang]
            else:
                target = {TargetLang.EN: "Page 1 of 1", TargetLang.FR: "Page 1 sur 1",
                          TargetLang.AR: "الصفحة 1 من 1"}[lang]
            blocks.append({"id": block["id"], "text": target})
        return SimpleNamespace(id=f"synthetic-{len(calls)}", status="completed", model=request["model"],
            output_text=json.dumps({"blocks": blocks}, ensure_ascii=False), usage={"input_tokens": 12, "output_tokens": 8})
    client = OpenAIResponsesClient(sdk_client=SimpleNamespace(base_url="https://api.openai.com/v1/",
        responses=SimpleNamespace(create=create)), pre_call_jitter_seconds=0)
    workflow = TranslationWorkflow(client=client, gui_settings={}, reviewed_source_context=context)
    result = workflow.run(config)
    assert result.success, result.error
    assert len(calls) == count
    service = OrdinaryFormattingReviewService(config, context)
    return SimpleNamespace(config=config, context=context, service=service, run_dir=result.run_dir,
        calls=calls, local_calls=local_calls, accounting_path=workflow._dispatch_accounting.journal_path)


def page_decision(page, *, table=False, folios=False, split_lines=False):
    fragments = []
    for parent in page["parents"]:
        left, right = parent["source_text"], parent["target_text"]
        spans = [(0, len(left), 0, len(right))]
        if split_lines and parent["parent_number"] == 1:
            a, b = left.index("\n") + 1, right.index("\n") + 1
            spans = [(0, a, 0, b), (a, len(left), b, len(right))]
        for source_start, source_end, target_start, target_end in spans:
            number = len(fragments) + 1
            folio = folios and parent is page["parents"][-1]
            box = ((130, 270, 190, 290) if folio else
                (10 + (number - 1) * 100, 10, 90 + (number - 1) * 100, 30) if table else
                (10, 10 + (number - 1) * 40, 190, 30 + (number - 1) * 40))
            fragments.append(FormattingFragment(parent["parent_number"], (source_start, source_end),
                (target_start, target_end), box, "folio" if folio else "body", "left", False, False,
                "Fictional operator independently compares both selections and the image box."))
    count = len(fragments)
    body_numbers = tuple(range(1, count if folios else count + 1))
    body = ((FormattingTable((50, 50), (((1,), (2,)),)),) if table else
            tuple(FormattingParagraph(n) for n in body_numbers))
    return FormattingPageDecision(tuple(fragments), (), body, (count,) if folios else (),
        count if folios else None, True, True, "Fictional formatting operator", "Complete independent page comparison.")


def completed_draft(case, *, table=False, folios=False, split_lines=False, source_gaps=False):
    draft = case.service.prepare()
    assert draft["status"] == "draft"
    for page in draft["pages"]:
        draft = case.service.save_page(draft["draft_id"], expected_generation=draft["generation"],
            page_number=page["page_number"], decision=page_decision(page, table=table, folios=folios, split_lines=split_lines))
    groups = tuple(FormattingDocumentGroup(n, n) for n in range(1, len(draft["pages"]) + 1))
    return case.service.save_document(draft["draft_id"], expected_generation=draft["generation"],
        decision=FormattingDocumentDecision(groups, True, False, source_gaps,
            "Fictional document operator", "All boundaries and explicit local folio selections reviewed."))


def submit(case, draft):
    return case.service.submit(draft["draft_id"], expected_generation=draft["generation"],
                               reviewer="Fictional final operator", accept_formatting=True)


def originals(case):
    paths = [case.run_dir / "run_state.json", case.accounting_path, *sorted((case.run_dir / "pages").iterdir())]
    return {path: path.read_bytes() for path in paths if path.is_file()}


@pytest.mark.parametrize("lang", [TargetLang.EN, TargetLang.FR, TargetLang.AR])
def test_public_operator_pipeline_independent_unicode_ranges_and_strict_package(tmp_path, monkeypatch, lang):
    case = public_case(tmp_path, monkeypatch, lang=lang, multiline=True)
    before, settings = originals(case), deepcopy(settings_fingerprint(case.config))
    first = case.service.prepare()
    assert first["document_decision"] is None and all(p["decision"] is None for p in first["pages"])
    assert case.service.image(first["draft_id"], page_number=1).startswith(b"\x89PNG")
    assert "😀" in first["pages"][0]["parents"][0]["source_text"]
    assert "source_image_bytes" not in json.dumps(first)
    draft = completed_draft(case, split_lines=True, source_gaps=True)
    spans = draft["pages"][0]["decision"]["fragments"][0]
    assert spans["source_range"] != spans["target_range"]
    revision = submit(case, draft)["revision_id"]
    restored = OrdinaryFormattingReviewService(case.config, case.context)
    assert restored.inspect(revision)["status"] == "ready"
    output = restored.rebuild(revision)
    assert output["status"] == "built"
    mapping = json.loads(output["source_map"].read_bytes())
    assert mapping["reviewer_kind"] == "operator_review"
    assert mapping["source_geometry_status"] == "not_verified"
    assert mapping["rendered_layout_acceptance"] == "not_evaluated" and mapping["layout_review_required"]
    with run_workspace_slot(case.run_dir):
        state = load_run_state(case.run_dir / "run_state.json")
        ready = prepare_run_docx_formatting(case.run_dir, case.config, state, revision_id=revision,
                                            review_profile=OPERATOR_REVIEW_PROFILE)
        strict = prepare_run_docx_formatting(case.run_dir, case.config, state, revision_id=revision)
    assert strict.status == "declined"
    validate_reviewed_docx(output["output_docx"].read_bytes(), output["source_map"].read_bytes(),
        projection=ready.projection, expected_reviewer_kind="operator_review")
    with pytest.raises(ReviewedFormattingWriterError):
        validate_reviewed_docx(output["output_docx"].read_bytes(), output["source_map"].read_bytes(), projection=ready.projection)
    folder = case.run_dir / "formatting_reviews" / revision
    assert (folder / "source_review.json").read_bytes() == case.context.source_review_json
    assert (folder / "source_decision_evidence.bin").read_bytes() == case.context.decision_evidence
    assert json.loads((folder / "review_evidence.bin").read_bytes())["source_context"] == case.context.identity
    assert originals(case) == before and settings_fingerprint(case.config) == settings
    assert len(case.calls) == len(case.local_calls) == 1


def test_explicit_table_owners_create_editable_cells(tmp_path, monkeypatch):
    case = public_case(tmp_path, monkeypatch)
    draft = completed_draft(case, table=True)
    revision = submit(case, draft)["revision_id"]
    result = case.service.rebuild(revision)
    with zipfile.ZipFile(io.BytesIO(result["output_docx"].read_bytes())) as package:
        xml = package.read("word/document.xml")
    assert b"<w:tbl>" in xml and xml.count(b"<w:tc>") == 2
    assert b"<w:drawing" not in xml


def test_pipe_cell_boundaries_require_explicit_document_policy(tmp_path, monkeypatch):
    case = public_case(tmp_path, monkeypatch, pipe_cells=True)
    draft = case.service.prepare()
    page = draft["pages"][0]
    first, second = page["parents"]
    left, right = first["source_text"], first["target_text"]
    source_cut, target_cut = left.index("|") + 2, right.index("|") + 2
    fragments = (
        FormattingFragment(1, (0, source_cut), (0, target_cut), (10, 10, 90, 30), "body", "left", False, False, "First cell reviewed."),
        FormattingFragment(1, (source_cut, len(left)), (target_cut, len(right)), (100, 10, 190, 30), "body", "left", False, False, "Second cell reviewed."),
        FormattingFragment(2, (0, len(second["source_text"])), (0, len(second["target_text"])),
            (10, 50, 190, 70), "body", "left", False, False, "Independent paragraph reviewed."))
    decision = FormattingPageDecision(fragments, (), (FormattingTable((50, 50), (((1,), (2,)),)), FormattingParagraph(3)),
        (), None, True, True, "operator", "Complete metadata row and paragraph review.")
    draft = case.service.save_page(draft["draft_id"], expected_generation=draft["generation"], page_number=1, decision=decision)
    document = FormattingDocumentDecision((FormattingDocumentGroup(1, 1),), True, False, False, "operator", "All document reviewed.")
    draft = case.service.save_document(draft["draft_id"], expected_generation=draft["generation"], decision=document)
    with pytest.raises(FormattingReviewServiceError):
        submit(case, draft)
    # A failed pure validation has not frozen a submission intent; the operator
    # can explicitly select the supported pipe-cell policy and submit once.
    draft = case.service.save_document(draft["draft_id"], expected_generation=draft["generation"],
        decision=replace(document, allow_pipe_cell_boundaries=True))
    revision = submit(case, draft)["revision_id"]
    assert case.service.rebuild(revision)["status"] == "built"


@pytest.mark.parametrize("lang", [TargetLang.EN, TargetLang.FR, TargetLang.AR])
def test_explicit_document_groups_bind_printed_local_folios(tmp_path, monkeypatch, lang):
    case = public_case(tmp_path, monkeypatch, lang=lang, count=2, folios=True)
    draft = completed_draft(case, folios=True)
    revision = submit(case, draft)["revision_id"]
    result = case.service.rebuild(revision)
    assert result["status"] == "built"
    manifest = json.loads((case.run_dir / "formatting_reviews" / revision / "formatting.json").read_bytes())
    assert manifest["document_groups"] == [{"start_page": 1, "end_page": 1}, {"start_page": 2, "end_page": 2}]
    assert [page["folio_fragment_id"] for page in manifest["pages"]] == ["p0001_f0003", "p0002_f0003"]


def test_generation_and_completion_are_explicit_and_page_changes_reset_document_review(tmp_path, monkeypatch):
    case = public_case(tmp_path, monkeypatch)
    first = case.service.prepare()
    with pytest.raises(FormattingReviewServiceError, match="incomplete_review"):
        submit(case, first)
    complete = completed_draft(case)
    decision = page_decision(complete["pages"][0])
    with pytest.raises(FormattingReviewServiceError, match="stale_generation"):
        case.service.save_page(complete["draft_id"], expected_generation=1, page_number=1, decision=decision)
    changed = case.service.save_page(complete["draft_id"], expected_generation=complete["generation"], page_number=1, decision=decision)
    assert changed["document_decision"] is None
    with pytest.raises(FormattingReviewServiceError, match="incomplete_review"):
        submit(case, changed)
    complete = completed_draft(case)
    with pytest.raises(FormattingReviewServiceError, match="explicit_acceptance_required"):
        case.service.submit(complete["draft_id"], expected_generation=complete["generation"], reviewer="operator", accept_formatting=False)
    submit(case, complete)
    with pytest.raises(FormattingReviewServiceError, match="draft_submitted"):
        case.service.save_page(complete["draft_id"], expected_generation=complete["generation"], page_number=1, decision=decision)


@pytest.mark.parametrize("stage", ["after_adapter", "after_revision_receipt", "after_draft_receipt", "lost_response"])
def test_exact_submit_recovery_after_publication_boundaries_and_restart(tmp_path, monkeypatch, stage):
    case = public_case(tmp_path, monkeypatch)
    draft = completed_draft(case)
    adapter, write = service_module.submit_run_formatting_review, service_module._write
    adapter_calls = []
    def publish(*args, **kwargs):
        result = adapter(*args, **kwargs)
        adapter_calls.append(result)
        if stage == "after_adapter":
            raise OSError("Synthetic lost adapter return")
        return result
    def persist(path, value):
        result = write(path, value)
        if ((stage == "after_revision_receipt" and path.parent.name == "revisions")
                or (stage == "after_draft_receipt" and path.name == "submitted.json")):
            raise OSError("Synthetic lost receipt return")
        return result
    with monkeypatch.context() as scope:
        scope.setattr(service_module, "submit_run_formatting_review", publish)
        scope.setattr(service_module, "_write", persist)
        if stage == "lost_response":
            submit(case, draft)  # Discard the completed response as a disconnected browser would.
        else:
            with pytest.raises(FormattingReviewServiceError):
                submit(case, draft)
    assert len(adapter_calls) == 1
    before = originals(case)
    restored = OrdinaryFormattingReviewService(case.config, case.context)
    with pytest.raises(FormattingReviewServiceError, match="submission_inputs_changed"):
        restored.submit(draft["draft_id"], expected_generation=draft["generation"],
            reviewer="A different final operator", accept_formatting=True)
    recovered = restored.read(draft["draft_id"])
    assert recovered["status"] == "submitted" and recovered["revision_id"] == adapter_calls[0]
    monkeypatch.setattr(service_module, "submit_run_formatting_review", lambda *_a, **_kw: pytest.fail("Must recover, never resubmit"))
    repeated = restored.submit(draft["draft_id"], expected_generation=draft["generation"],
        reviewer="Fictional final operator", accept_formatting=True)
    assert repeated["revision_id"] == recovered["revision_id"]
    assert restored.inspect(repeated["revision_id"])["status"] == "ready"
    assert len(list((case.run_dir / "formatting_reviews").glob("*/revision.json"))) == 1
    assert originals(case) == before


def test_uncertain_incomplete_adapter_publication_stays_pending_without_replay(tmp_path, monkeypatch):
    case = public_case(tmp_path, monkeypatch)
    draft = completed_draft(case)
    attempts = []
    def interrupted(*_args, **_kwargs):
        attempts.append(1)
        raise OSError("Synthetic interrupted adapter before completed revision")
    monkeypatch.setattr(service_module, "submit_run_formatting_review", interrupted)
    with pytest.raises(FormattingReviewServiceError):
        submit(case, draft)
    restored = OrdinaryFormattingReviewService(case.config, case.context)
    assert restored.read(draft["draft_id"])["status"] == "submission_pending"
    with pytest.raises(FormattingReviewServiceError, match="submission_publication_unresolved"):
        restored.submit(draft["draft_id"], expected_generation=draft["generation"],
            reviewer="Fictional final operator", accept_formatting=True)
    with pytest.raises(FormattingReviewServiceError, match="draft_submission_started"):
        restored.save_page(draft["draft_id"], expected_generation=draft["generation"], page_number=1,
            decision=page_decision(draft["pages"][0]))
    assert attempts == [1]


@pytest.mark.parametrize("field", ["reviewer", "formatting_manifest_sha256", "review_evidence_sha256"])
def test_selected_revision_must_remain_joined_to_exact_submission_intent(tmp_path, monkeypatch, field):
    case = public_case(tmp_path, monkeypatch)
    draft = completed_draft(case)
    revision = submit(case, draft)["revision_id"]
    path = case.run_dir / "visual_formatting_reviews/drafts" / draft["draft_id"] / "submit_intent.json"
    intent = json.loads(path.read_bytes())
    intent[field] = "Changed reviewer" if field == "reviewer" else "0" * 64
    path.write_text(json.dumps(intent), encoding="utf-8")
    monkeypatch.setattr(service_module, "build_run_reviewed_docx", lambda *_a, **_kw: pytest.fail("Intent mismatch must not build"))
    for operation in (case.service.inspect, case.service.rebuild):
        with pytest.raises(FormattingReviewServiceError):
            operation(revision)
    with pytest.raises(FormattingReviewServiceError):
        case.service.read(draft["draft_id"])


@pytest.mark.parametrize("record_name,error", [("intent", "submission_intent_changed"), ("receipt", "revision_owner_changed")])
def test_persisted_bool_generation_is_rejected_as_invalid_schema(tmp_path, monkeypatch, record_name, error):
    case = public_case(tmp_path, monkeypatch)
    draft = completed_draft(case)
    revision = submit(case, draft)["revision_id"]
    root = case.run_dir / "visual_formatting_reviews"
    path = (root / "drafts" / draft["draft_id"] / "submit_intent.json" if record_name == "intent"
            else root / "revisions" / (revision + ".json"))
    record = json.loads(path.read_bytes())
    record["generation"] = True
    path.write_text(json.dumps(record), encoding="utf-8")
    for operation in (case.service.inspect, case.service.rebuild):
        with pytest.raises(FormattingReviewServiceError, match=error):
            operation(revision)


def test_first_generation_intent_never_treats_true_as_integer_one(tmp_path, monkeypatch):
    case = public_case(tmp_path, monkeypatch)
    draft = case.service.prepare()
    folder = case.run_dir / "visual_formatting_reviews/drafts" / draft["draft_id"]
    parents = json.loads((folder / "parents.json").read_bytes())
    generation_raw = (folder / "000001.json").read_bytes()
    # Deliberately malformed persistence only; this does not inject an accepted
    # source/commit/review fixture. With bool equality the old path said pending.
    import hashlib
    intent = {"version": service_module.VERSION, "owner": parents["owner"], "draft_id": draft["draft_id"],
        "generation": True, "generation_sha256": hashlib.sha256(generation_raw).hexdigest(),
        "reviewer": "operator", "formatting_manifest_sha256": "0" * 64, "review_evidence_sha256": "0" * 64}
    (folder / "submit_intent.json").write_text(json.dumps(intent), encoding="utf-8")
    with pytest.raises(FormattingReviewServiceError, match="submission_intent_changed"):
        case.service.read(draft["draft_id"])


def test_utf16_cut_and_incomplete_partitions_cannot_publish(tmp_path, monkeypatch):
    case = public_case(tmp_path, monkeypatch, multiline=True)
    draft = case.service.prepare()
    page = draft["pages"][0]
    decision = page_decision(page, split_lines=True)
    first, second, *tail = decision.fragments
    # JavaScript UTF-16 end is one larger because the first line has an astral character.
    bad = replace(decision, fragments=(replace(first, source_range=(0, first.source_range[1] + 1)),
        replace(second, source_range=(second.source_range[0] + 1, second.source_range[1])), *tail))
    draft = case.service.save_page(draft["draft_id"], expected_generation=draft["generation"], page_number=1, decision=bad)
    draft = case.service.save_document(draft["draft_id"], expected_generation=draft["generation"],
        decision=FormattingDocumentDecision((FormattingDocumentGroup(1, 1),), True, False, False, "operator", "Reviewed."))
    with pytest.raises(FormattingReviewServiceError):
        submit(case, draft)
    assert not (case.run_dir / "formatting_reviews").exists()


def test_duplicate_owners_and_changed_document_boundaries_are_rejected(tmp_path, monkeypatch):
    case = public_case(tmp_path, monkeypatch, count=2, folios=True)
    first = case.service.prepare()
    decision = page_decision(first["pages"][0], folios=True)
    with pytest.raises(FormattingReviewServiceError):
        case.service.save_page(first["draft_id"], expected_generation=first["generation"], page_number=1,
            decision=replace(decision, body=(FormattingParagraph(1), FormattingParagraph(1))))
    draft = completed_draft(case, folios=True)
    # Both genuine source decisions say "start". A single two-page document
    # would invent a continuation and reinterpret the two printed 1-of-1 folios.
    draft = case.service.save_document(draft["draft_id"], expected_generation=draft["generation"],
        decision=FormattingDocumentDecision((FormattingDocumentGroup(1, 2),), True, False, False,
            "operator", "Fictional inconsistent grouping for rejection."))
    with pytest.raises(FormattingReviewServiceError):
        submit(case, draft)
    assert not (case.run_dir / "formatting_reviews").exists()


def test_partial_saved_run_declines_and_running_evidence_blocks(tmp_path, monkeypatch):
    case = public_case(tmp_path, monkeypatch)
    path = case.run_dir / "run_state.json"
    state = json.loads(path.read_bytes())
    state["run_status"] = "paused"
    path.write_text(json.dumps(state), encoding="utf-8")
    assert case.service.prepare() == {"status": "declined", "notice_codes": ["reviewed_profile_unsupported_selection"]}
    state["run_status"] = "running"
    path.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(FormattingReviewServiceError, match="run_busy"):
        case.service.prepare()


def test_target_mutation_after_ready_preparation_cannot_use_normal_writer(tmp_path, monkeypatch):
    case = public_case(tmp_path, monkeypatch)
    draft = completed_draft(case)
    revision = submit(case, draft)["revision_id"]
    build = service_module.build_run_reviewed_docx
    def change_before_build(*args, **kwargs):
        path = case.run_dir / "pages/page_0001.txt"
        path.write_text(path.read_text(encoding="utf-8") + "\nLater edit.", encoding="utf-8")
        return build(*args, **kwargs)
    monkeypatch.setattr(service_module, "build_run_reviewed_docx", change_before_build)
    existing = set(case.config.output_dir.glob("*.docx"))
    with pytest.raises(FormattingReviewServiceError):
        case.service.rebuild(revision)
    assert set(case.config.output_dir.glob("*.docx")) == existing


@pytest.mark.parametrize("setting,code", [("page_breaks", "reviewed_profile_requires_page_breaks"),
    ("strip_bidi_controls", "reviewed_profile_requires_bidi_stripping")])
def test_saved_unsupported_preferences_decline_without_mutation(tmp_path, monkeypatch, setting, code):
    case = public_case(tmp_path, monkeypatch, **{setting: False})
    before = originals(case)
    result = case.service.prepare()
    assert result["status"] == "declined" and code in result["notice_codes"]
    assert getattr(case.config, setting) is False and originals(case) == before
    assert not (case.run_dir / "visual_formatting_reviews").exists()


def test_target_edit_invalidates_draft_and_revision_without_fallback(tmp_path, monkeypatch):
    case = public_case(tmp_path, monkeypatch)
    draft = completed_draft(case)
    revision = submit(case, draft)["revision_id"]
    target = case.run_dir / "pages/page_0001.txt"
    target.write_text(target.read_text(encoding="utf-8") + "\nExplicit target edit.", encoding="utf-8")
    monkeypatch.setattr(service_module, "build_run_reviewed_docx", lambda *_a, **_kw: pytest.fail("Stale mapping must not build"))
    for result in (case.service.read(draft["draft_id"]), case.service.inspect(revision), case.service.rebuild(revision)):
        assert result["status"] == "declined" and "reviewed_profile_stale_edited_target" in result["notice_codes"]


@pytest.mark.parametrize("mutation", ["source", "commit", "generation", "revision", "settings"])
def test_integrity_failures_never_build_or_leak_content(tmp_path, monkeypatch, mutation):
    case = public_case(tmp_path, monkeypatch)
    draft = completed_draft(case)
    revision = submit(case, draft)["revision_id"]
    folder = case.run_dir / "visual_formatting_reviews/drafts" / draft["draft_id"]
    paths = {"source": case.config.pdf_path, "commit": case.run_dir / "pages/page_0001.commit.json",
        "generation": folder / f"{draft['generation']:06d}.json",
        "revision": case.run_dir / "formatting_reviews" / revision / "formatting.json",
        "settings": case.run_dir / "run_state.json"}
    paths[mutation].write_bytes(b"Fictional private details must not escape")
    monkeypatch.setattr(service_module, "build_run_reviewed_docx", lambda *_a, **_kw: pytest.fail("Integrity failure must not build"))
    with pytest.raises(FormattingReviewServiceError) as caught:
        case.service.rebuild(revision)
    assert "private details" not in "".join(traceback.format_exception(caught.value))


def test_owner_ids_and_concurrent_run_are_enforced(tmp_path, monkeypatch):
    case = public_case(tmp_path, monkeypatch)
    draft = case.service.prepare()
    for bad in ("../outside", "", True):
        with pytest.raises(FormattingReviewServiceError):
            case.service.read(bad)
    wrong = OrdinaryFormattingReviewService(replace(case.config, workers=2), case.context)
    with pytest.raises(FormattingReviewServiceError, match="draft_owner_changed"):
        wrong.read(draft["draft_id"])
    outcomes = []
    with run_workspace_slot(case.run_dir):
        def competing():
            try:
                case.service.read(draft["draft_id"])
            except FormattingReviewServiceError as error:
                outcomes.append(str(error))
        thread = threading.Thread(target=competing)
        thread.start()
        thread.join(timeout=5)
        assert not thread.is_alive()
    assert outcomes == ["formatting_review_run_busy"]
