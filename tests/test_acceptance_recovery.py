from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from legalpdf_translate.acceptance_continuation import AcceptanceContinuation, AcceptancePageJournal
from legalpdf_translate import acceptance_recovery as recovery
from legalpdf_translate.document_structure import PageStructure, StructureBlock
from legalpdf_translate.formatting_support import digest_text, fingerprint
from legalpdf_translate.structured_artifacts import StructuredArtifactError, validate_structured_page
from legalpdf_translate.translation_structure import build_structured_page_prompt, structured_system_instructions
from legalpdf_translate.types import TargetLang


def pin(path):
    return recovery.PinnedJSON(path, hashlib.sha256(path.read_bytes()).hexdigest())


@pytest.fixture
def case(tmp_path):
    source = PageStructure(page_number=5, source_sha256=digest_text("Decisão\nPedido admitido."),
        source_text_sha256=digest_text("Decisão\nPedido admitido."), source_file_sha256="a" * 64,
        blocks=[StructureBlock("p0005_b0001", "Decisão"), StructureBlock("p0005_b0002", "Pedido admitido.")])
    rows = [{"id": b.id, "text": b.text} for b in source.blocks]
    request = {"instructions": structured_system_instructions(TargetLang.FR),
        "prompt_text": build_structured_page_prompt(source_blocks=rows, page_number=5, total_pages=9),
        "effort": "high"}
    old = tmp_path / "old"
    old.mkdir()
    journal = AcceptancePageJournal(old,
        policy=AcceptanceContinuation("b" * 64, tuple(range(1, 10)), (5,), lambda _: "c" * 64),
        protocol_identity={"protocol": "legal_blocks_v2", "fingerprint": "d" * 64},
        page_number=5, page_fingerprint="e" * 64)
    journal.begin(1, request, "c" * 64)
    journal.save_response(1, result=SimpleNamespace(
        raw_output=json.dumps({"blocks": [{"id": rows[0]["id"], "text": "Décision"},
            {"id": rows[1]["id"], "text": "Demande admise."}]}), response_status="completed",
        refused=False, usage={"input_tokens": 30, "output_tokens": 20}, model="historical-model", effort="high"),
        usage={"attempt_1": {"input_tokens": 30, "output_tokens": 20}}, metadata={"api_calls_count": 1})
    prefs = tmp_path / "preferences.json"
    prefs.write_text("{}", encoding="utf-8")
    return dict(intent=pin(journal._path("primary.intent")), response=pin(journal._path("primary.response")),
        preferences=pin(prefs), historical_identity=journal.identity, request_sha256=fingerprint(request),
        source_structure=source, source_structure_sha256=source.fingerprint, source_guard=lambda: None,
        validator_binding="f" * 64, lang=TargetLang.FR, pages_dir=tmp_path / "pages")


def rewrite_envelope(case, key, change):
    path = case[key].path
    record = json.loads(path.read_bytes())
    change(record)
    record["sha256"] = fingerprint({k: v for k, v in record.items() if k != "sha256"})
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    case[key] = pin(path)


def test_exact_recovery_idempotent_originals_unchanged_no_resume(case):
    originals = {name: case[name].path.read_bytes() for name in ("intent", "response", "preferences")}
    first = recovery.recover_saved_page(**case)
    assert recovery.recover_saved_page(**case) == first
    assert first["commit"]["protocol_identity"]["protocol"] == recovery.RECOVERY_VERSION
    assert first["commit"]["page_result"] is None
    assert first["provenance"]["recovery_provider_dispatch_count"] == 0
    assert first["provenance"]["historical_model"] == "historical-model"
    assert first["provenance"]["historical_usage"]["attempt_1"]["input_tokens"] == 30
    assert not first["provenance"]["full_case_complete"]
    for name, contents in originals.items():
        assert case[name].path.read_bytes() == contents


@pytest.mark.parametrize("key", ["intent", "response", "preferences"])
@pytest.mark.parametrize("missing", [False, True])
def test_missing_or_changed_evidence_rejected(case, key, missing):
    if missing:
        case[key].path.unlink()
    else:
        case[key].path.write_text('{"changed":true}', encoding="utf-8")
    with pytest.raises(StructuredArtifactError):
        recovery.recover_saved_page(**case)
    assert not case["pages_dir"].exists()


@pytest.mark.parametrize("change", [
    lambda r: r["identity"].update(page_number=6),
    lambda r: r["payload"].update(intent_sha256="0" * 64),
    lambda r: r["payload"]["response"].update(response_status="incomplete"),
    lambda r: r["payload"]["response"].update(refused=True),
    lambda r: r["payload"]["response"].update(raw_output='{"blocks":[]}'),
    lambda r: r["payload"]["response"].update(raw_output=json.dumps({"blocks": [
        {"id": "p0005_b0001", "text": "Décision"}, {"id": "p0005_b0001", "text": "Décision"}]})),
])
def test_invalid_saved_response_rejected(case, change):
    rewrite_envelope(case, "response", change)
    with pytest.raises((StructuredArtifactError, ValueError)):
        recovery.recover_saved_page(**case)
    assert not case["pages_dir"].exists()


@pytest.mark.parametrize("field", ["request_sha256", "source_structure_sha256", "lang", "historical_identity"])
def test_wrong_bindings_rejected(case, field):
    case[field] = {"lang": TargetLang.EN, "historical_identity": {"page_number": 6}}.get(field, "0" * 64)
    with pytest.raises(StructuredArtifactError):
        recovery.recover_saved_page(**case)


def test_provider_reordered_rows_restored_by_exact_source_ids(case):
    rewrite_envelope(case, "response", lambda r: r["payload"]["response"].update(raw_output=json.dumps({"blocks": [
        {"id": "p0005_b0002", "text": "Demande admise."}, {"id": "p0005_b0001", "text": "Décision"}]})))
    recovery.recover_saved_page(**case)
    assert (case["pages_dir"] / "page_0005.txt").read_text(encoding="utf-8") == "Décision\nDemande admise."


def test_source_prompt_association_not_just_caller_pin(case):
    case["source_structure"].blocks[0].text = "Outra decisão"
    case["source_structure_sha256"] = case["source_structure"].fingerprint
    with pytest.raises(StructuredArtifactError, match="source_prompt_mismatch"):
        recovery.recover_saved_page(**case)


def test_unmatched_glossary_suffix_rejected(case):
    rewrite_envelope(case, "intent", lambda r: r["payload"]["request"].update(
        prompt_text=r["payload"]["request"]["prompt_text"] + "\nunbound instruction"))
    intent = case["intent"].read()
    case["request_sha256"] = fingerprint(intent["payload"]["request"])
    rewrite_envelope(case, "response", lambda r: r["payload"].update(intent_sha256=intent["sha256"]))
    with pytest.raises(StructuredArtifactError, match="glossary_prompt_mismatch"):
        recovery.recover_saved_page(**case)


def test_visible_text_edit_rejected(case, monkeypatch):
    original = recovery.validate_block
    monkeypatch.setattr(recovery, "validate_block", lambda *args: original(*args) + " change")
    with pytest.raises(StructuredArtifactError, match="changed_visible_translation"):
        recovery.recover_saved_page(**case)


def test_source_guard_drift_prevents_commit(case):
    calls = []
    def guard():
        calls.append(1)
        if len(calls) == 3:
            raise StructuredArtifactError("source_changed")
    case["source_guard"] = guard
    with pytest.raises(StructuredArtifactError, match="source_changed"):
        recovery.recover_saved_page(**case)
    with pytest.raises(StructuredArtifactError):
        validate_structured_page(case["pages_dir"], 5)


def test_conflicting_partial_bundle_never_overwritten(case):
    case["pages_dir"].mkdir()
    target = case["pages_dir"] / "page_0005.txt"
    target.write_text("keep me", encoding="utf-8")
    with pytest.raises(StructuredArtifactError):
        recovery.recover_saved_page(**case)
    assert target.read_text(encoding="utf-8") == "keep me"


def test_real_writer_partial_docx_and_style(case, tmp_path):
    from docx import Document
    result = recovery.recover_saved_page(**case)
    output = recovery.assemble_recovered_page(case["pages_dir"], tmp_path / "docx", recovery=result,
        evidence_guard=case["source_guard"])
    doc = Document(output)
    assert "Décision" in "\n".join(p.text for p in doc.paragraphs)
    assert doc.styles["Normal"].font.name == "Times New Roman"
    assert doc.styles["Normal"].font.size.pt == 10.5
    assert doc.sections[0].left_margin.cm == pytest.approx(1.7, abs=0.005)
    assert doc.sections[0].top_margin.cm == pytest.approx(1.5, abs=0.005)
    report = json.loads((output.parent / "recovery_review.json").read_bytes())
    assert report["assembly_stats"]["structure_fallback_count"] == 0
    assert report["rendered_layout_acceptance"] == "not_evaluated"
    assert report["full_case_complete"] is False
    with pytest.raises(FileExistsError):
        recovery.assemble_recovered_page(case["pages_dir"], output.parent, recovery=result, evidence_guard=lambda: None)


@pytest.mark.parametrize("fault", ["fallback", "changed_commit", "false_complete"])
def test_writer_failure_cannot_claim_accepted_docx(case, tmp_path, fault):
    result = recovery.recover_saved_page(**case)
    if fault == "false_complete":
        result["provenance"]["full_case_complete"] = True
    def writer(folder, output, **kwargs):
        assert kwargs["page_numbers"] == [5]
        assert kwargs["partial_output"] is True
        assert kwargs["derive_source_continuations"] is True
        if fault == "changed_commit":
            (folder / "page_0005.txt").write_text("changed", encoding="utf-8")
        kwargs["stats"].update(structured_page_count=0, structure_fallback_count=1)
    with pytest.raises(StructuredArtifactError):
        recovery.assemble_recovered_page(case["pages_dir"], tmp_path / "docx", recovery=result,
            evidence_guard=lambda: None, writer=writer)
    assert not (tmp_path / "docx" / "recovery_review.json").exists()


@pytest.mark.parametrize("suffix", ["layout.json", "layout_eligibility.json"])
@pytest.mark.parametrize("when", ["before", "during"])
def test_unbound_layout_derivatives_rejected(case, tmp_path, suffix, when):
    result = recovery.recover_saved_page(**case)
    sidecar = case["pages_dir"] / f"page_0005.{suffix}"
    if when == "before":
        sidecar.write_text("{}", encoding="utf-8")
    def writer(*args, **kwargs):
        sidecar.write_text("{}", encoding="utf-8")
        kwargs["stats"].update(structured_page_count=1, structure_fallback_count=0)
    with pytest.raises(StructuredArtifactError, match="unbound_layout_derivative"):
        recovery.assemble_recovered_page(case["pages_dir"], tmp_path / "docx", recovery=result,
            evidence_guard=lambda: None, writer=writer)
    assert not (tmp_path / "docx" / "recovery_review.json").exists()
