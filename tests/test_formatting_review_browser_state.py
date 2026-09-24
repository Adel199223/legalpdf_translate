"""Formatting UI authoring probes; execute only in the parent browser-test pass.

The established Node runner remains outside subprocess-forbidding offline suites.
No production/native/provider boundary is relaxed for these tests.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from .browser_esm_probe import run_browser_esm_json_probe
from .test_source_review_browser_state import DOM


MODULES = {"__CONTROLLER__": "formatting_review.js", "__UI__": "formatting_review_ui.js"}
PRELUDE = r"""
const core = await import(__CONTROLLER__);
const ui = await import(__UI__);
if (!globalThis.crypto) globalThis.crypto = (await import("node:crypto")).webcrypto;
const copy = (v) => JSON.parse(JSON.stringify(v));
const scope = {runtimeMode: "shadow", workspaceId: "workspace-1"};
const job = {job_id: "tx-owned", runtime_mode: "shadow", workspace_id: "workspace-1", status: "completed", actions: {formatting_review: true}};
const memory = () => { const data = new Map(); return {
  getItem: (k) => data.get(k) || null, setItem: (k, v) => data.set(k, v), removeItem: (k) => data.delete(k), data,
}; };
const envelope = (formatting_review) => ({normalized_payload: {formatting_review: copy(formatting_review)}});
const fragment = {parent_number: 1, source_range: [0, 4], target_range: [0, 4], bbox_px: [10, 10, 100, 30],
  role: "body", alignment: "left", bold: false, italic: false, review_note: "Explicit visual comparison"};
const pageDecision = {...ui.blankFormattingPage(), fragments: [fragment], body: [{fragment_number: 1}],
  full_page_review_completed: true, source_target_mapping_reviewed: true, reviewer: "Operator", review_note: "Page checked"};
const documentDecision = {...ui.blankFormattingDocument(), groups: [{start_page: 1, end_page: 1}],
  all_pages_reviewed: true, reviewer: "Operator", review_note: "All pages checked"};
const draft = {status: "draft", review_id: "a".repeat(32), job_id: job.job_id, generation: 1, page_matched_derivative: true,
  rebuild_operations: [], artifacts: [],
  reviewer_kind: "operator_review", source_revision_id: "e".repeat(32), offset_unit: "unicode_codepoint",
  geometry_status: "not_verified", rendered_layout_acceptance: "not_evaluated", layout_review_required: true, notice_codes: [],
  pages: [{page_number: 1, image_size_px: [200, 300], source_provenance: "ocr", source_uncertain: true, image_available: true,
    parents: [{parent_number: 1, source_text: "Case", target_text: "Case"}], decision: pageDecision}], document_decision: documentDecision};
"""


def probe(script: str, *, data=None):
    return run_browser_esm_json_probe(PRELUDE + "\nconst data = " + json.dumps(data, ensure_ascii=True) + ";\n" + script, MODULES)


def test_unicode_selection_and_fragment_ownership_remapping_preserve_exact_values():
    result = probe(r"""
const text = "A😀e\u0301 ملف 121/26";
const selected = ui.selectedCodepointRange(text, 1, 5);
const rtlStart = text.indexOf("ملف");
const rtl = ui.selectedCodepointRange(text, rtlStart, text.length);
let splitRejected = false;
try { ui.selectedCodepointRange(text, 2, 3); } catch { splitRejected = true; }
const original = {...pageDecision, fragments: [fragment, {...fragment, role: "header"}, {...fragment, role: "folio"}],
  header: [2], body: [{column_widths: [40, 60], rows: [[[1], []]], column_gaps_px: [12]}], footer: [3], folio_fragment_number: 3};
const moved = ui.moveFormattingFragment(original, 1, 1);
const removed = ui.removeFormattingFragment(moved, 1);
const bad = copy(original); bad.body[0].rows[0][1] = [1];
console.log(JSON.stringify({selected, selectedText: ui.codepointSlice(text, selected), rtlText: ui.codepointSlice(text, rtl), splitRejected,
  original, moved, removed, duplicateProblem: ui.formattingPageProblem(draft.pages[0], bad), blank: ui.blankFormattingPage()}));
""")
    assert result["selected"] == [1, 4] and result["selectedText"] == "😀e\u0301"
    assert result["rtlText"] == "ملف 121/26" and result["splitRejected"]
    assert result["moved"]["header"] == [1] and result["moved"]["body"][0]["rows"] == [[[2], []]]
    assert result["removed"]["header"] == [] and result["removed"]["body"][0]["rows"] == [[[1], []]]
    assert result["removed"]["footer"] == [2] and result["removed"]["folio_fragment_number"] == 2
    assert result["original"]["header"] == [2] and result["original"]["body"][0]["column_gaps_px"] == [12]
    assert result["duplicateProblem"] and not result["blank"]["full_page_review_completed"]
    assert not result["removed"]["source_target_mapping_reviewed"]


def test_build_nonce_is_persisted_and_reload_requires_exact_server_operation_and_owned_artifact():
    result = probe(r"""
const calls = [], storage = memory(); let attempts = 0, associations = true;
const revision = {...draft, status: "submitted", revision_id: "b".repeat(32)};
const artifact = {artifact_id: "d".repeat(32), revision_id: revision.revision_id, kinds: ["output_docx", "source_map", "assembly_receipt"]};
const operation = {operation_nonce: "c".repeat(32), revision_id: revision.revision_id, status: "built", artifact_id: artifact.artifact_id};
const request = async (url, owner, options) => {
  const body = options.body ? JSON.parse(options.body) : null; calls.push({url, owner, body});
  if (url.endsWith("/prepare")) return envelope(draft);
  if (url.endsWith("/submit")) return envelope(revision);
  if (url.endsWith("/rebuild")) {
    if (![...storage.data.values()].some((raw) => raw.includes(body.operation_nonce))) throw new Error("Nonce not persisted");
    attempts += 1; if (attempts === 1) throw new Error("Fictional lost response");
    return envelope({...revision, status: "built", rebuild_operations: [operation], artifacts: [
      {...artifact, artifact_id: "f".repeat(32)}, artifact]});
  }
  return envelope({...revision, rebuild_operations: associations ? [operation] : [], artifacts: [artifact]});
};
const options = {getScope: () => scope, getJob: () => job, request, storage, createNonce: () => "c".repeat(32)};
const c = core.createFormattingReviewController(options);
await c.prepare(null); const choiceRejected = calls.length === 0;
await c.prepare(true); await c.submit("Operator", false); const notAccepted = c.snapshot();
await c.submit("Operator", true); await c.rebuild();
const restored = core.createFormattingReviewController({...options, createNonce: () => { throw new Error("Never replace"); }});
await restored.rebuild(); const beforeRead = attempts;
associations = false; await restored.read(); await restored.rebuild(); const unknown = restored.snapshot();
associations = true; await restored.read(); await restored.rebuild();
const href = restored.artifactUrl();
associations = false; await restored.read(); const noStaleDownload = restored.artifactUrl();
console.log(JSON.stringify({choiceRejected, notAccepted, beforeRead, unknown, attempts, href, noStaleDownload,
  builds: calls.filter((row) => row.url.endsWith("/rebuild")), stored: [...storage.data.values()]}));
""")
    assert result["choiceRejected"] and not result["notAccepted"]["revisionId"]
    assert result["beforeRead"] == 1 and result["unknown"]["errorCode"] == "formatting_review_unknown_build"
    assert result["attempts"] == 2 and len(result["builds"]) == 2
    assert all(row["body"] == {"revision_id": "b" * 32, "operation_nonce": "c" * 32} for row in result["builds"])
    assert "/" + "d" * 32 + "/output_docx?" in result["href"] and not result["noStaleDownload"]
    assert all("Operator" not in raw and "Case" not in raw and "source_path" not in raw for raw in result["stored"])


def test_lost_page_and_document_saves_use_canonical_values_and_stale_job_responses_are_discarded():
    result = probe(r"""
const reorder = (value) => Array.isArray(value) ? value.map(reorder) : value && typeof value === "object"
  ? Object.fromEntries(Object.keys(value).sort().map((key) => [key, reorder(value[key])])) : value;
let current = copy(draft), calls = 0;
const c = core.createFormattingReviewController({getScope: () => scope, getJob: () => job, storage: memory(), request: async (url, owner, options) => {
  calls += 1;
  if (url.endsWith("/prepare")) return envelope(current);
  if (options.method === "POST") {
    const body = JSON.parse(options.body); current.generation += 1;
    if (url.includes("/pages/")) { current.pages[0].decision = reorder(body.decision); current.document_decision = null; }
    else current.document_decision = reorder(body.decision);
    throw new Error("Saved; response lost");
  }
  return envelope(current);
}});
await c.prepare(true); c.markDirty(1); await c.savePage(1, pageDecision); await c.read(); const page = c.snapshot();
c.markDirty(); await c.saveDocument(documentDecision); await c.read(); const document = c.snapshot();
c.markDirty(1); await c.savePage(1, {...pageDecision, reviewer: "Local reviewer"});
current.generation += 1; current.pages[0].decision.reviewer = "Other operator";
await c.read(); const conflict = c.snapshot(); const before = calls; const discarded = c.discardConflict();
let activeJob = {...job}, resolve;
const delayed = new Promise((done) => { resolve = done; });
const stale = core.createFormattingReviewController({getScope: () => scope, getJob: () => activeJob, storage: memory(), request: async () => delayed});
const preparing = stale.prepare(true); activeJob = {...job, job_id: "tx-other"}; stale.sync(); resolve(envelope(draft)); await preparing;
console.log(JSON.stringify({page, document, conflict, discarded, discardRequests: calls - before, stale: stale.snapshot()}));
""")
    assert not result["page"]["dirty"] and not result["page"]["pendingKind"]
    assert not result["document"]["dirty"] and not result["document"]["pendingKind"]
    assert result["conflict"]["conflict"] and result["conflict"]["pendingKind"] == "page"
    assert result["discarded"] == {"kind": "page", "pageNumber": 1} and result["discardRequests"] == 0
    assert result["stale"]["owner"]["jobId"] == "tx-other" and result["stale"]["view"] is None


def test_pending_submit_read_requires_same_request_retry_before_claiming_its_revision():
    result = probe(r"""
const submits = [], storage = memory();
const revision = {...draft, status: "submitted", revision_id: "b".repeat(32)};
const options = {getScope: () => scope, getJob: () => job, storage, request: async (url, owner, options) => {
  if (url.endsWith("/prepare")) return envelope(draft);
  if (url.endsWith("/submit")) {
    submits.push(JSON.parse(options.body));
    if (submits.length === 1) throw new Error("Uncertain response");
  }
  return envelope(revision);
}};
const c = core.createFormattingReviewController(options);
await c.prepare(true); await c.submit("Exact reviewer", true); await c.read();
const pending = c.snapshot(); await c.submit("Different reviewer", true); const blockedCount = submits.length;
await c.submit("Exact reviewer", true); const completed = c.snapshot();
const restored = core.createFormattingReviewController(options); await restored.read();
console.log(JSON.stringify({pending, blockedCount, submits, completed, restored: restored.snapshot()}));
""")
    assert result["pending"]["pendingKind"] == "submit" and not result["pending"]["revisionId"]
    assert result["pending"]["view"]["revision_id"] == "b" * 32
    assert result["blockedCount"] == 1 and result["submits"][0] == result["submits"][1]
    assert result["completed"]["revisionId"] == "b" * 32 and not result["completed"]["pendingKind"]
    assert result["restored"]["revisionId"] == "b" * 32 and result["restored"]["restored"]


def test_restored_draft_explicit_new_submission_enables_one_first_build():
    result = probe(DOM + r"""
const storage = memory(), calls = []; let nonces = 0;
const revision = {...draft, status: "submitted", revision_id: "b".repeat(32)};
const options = {getScope: () => scope, getJob: () => job, storage,
  createNonce: () => { nonces += 1; return "c".repeat(32); },
  request: async (url, owner, options) => {
    const body = options.body ? JSON.parse(options.body) : null; calls.push({url, body});
    if (url.endsWith("/submit")) return envelope(revision);
    if (url.endsWith("/rebuild")) {
      if (![...storage.data.values()].some((raw) => raw.includes(body.operation_nonce))) throw new Error("Nonce not persisted");
      return envelope({...revision, status: "pending", rebuild_operations: [{operation_nonce: body.operation_nonce,
        revision_id: revision.revision_id, status: "pending"}], artifacts: []});
    }
    return envelope({...draft, rebuild_operations: [], artifacts: []});
  }};
const initial = core.createFormattingReviewController(options); await initial.prepare(true);
const mounted = ui.mountFormattingReview({...options, root, prepareButton});
await prepareButton.fire("click"); await findButton("Read current formatting review").fire("click");
const restored = mounted.controller.snapshot();
await fill("Formatting acceptance reviewer", "Operator");
await check("I accept these complete formatting decisions for this exact translation");
await findButton("Accept formatting revision").fire("click");
const submitted = mounted.controller.snapshot(), buildDisabled = findButton("Build DOCX from this revision").disabled;
await findButton("Build DOCX from this revision").fire("click");
console.log(JSON.stringify({restored, submitted, buildDisabled, nonces, unsafeWrites,
  builds: calls.filter((row) => row.url.endsWith("/rebuild")), final: mounted.controller.snapshot()}));
""")
    assert result["restored"]["restored"] and result["restored"]["verified"]
    assert not result["submitted"]["restored"] and not result["buildDisabled"]
    assert result["nonces"] == 1 and len(result["builds"]) == 1
    assert result["builds"][0]["body"] == {"revision_id": "b" * 32, "operation_nonce": "c" * 32}
    assert result["final"]["associated"] and result["unsafeWrites"] == 0


def test_rejected_submit_needs_authoritative_draft_read_and_explicit_discard_to_edit():
    result = probe(DOM + r"""
const calls = [], storage = memory();
const mounted = ui.mountFormattingReview({root, prepareButton, getScope: () => scope, getJob: () => job, storage,
  request: async (url, owner, options) => {
    calls.push({url, body: options.body ? JSON.parse(options.body) : null});
    if (url.endsWith("/submit")) throw new Error("browser_formatting_review_operation_failed");
    return envelope({...draft, rebuild_operations: [], artifacts: []});
  }});
await prepareButton.fire("click"); await mounted.controller.prepare(true);
await fill("Formatting acceptance reviewer", "Operator");
await check("I accept these complete formatting decisions for this exact translation");
await findButton("Accept formatting revision").fire("click");
const failed = mounted.controller.snapshot();
const beforeReadDiscard = mounted.controller.discardUnsubmitted?.() || null;
await findButton("Read current formatting review").fire("click");
const confirmed = mounted.controller.snapshot(), beforeDiscard = calls.length;
const button = walk(root).find((node) => node.tagName === "BUTTON" && node.textContent === "Discard the unsubmitted request and continue editing");
if (button) await button.fire("click");
console.log(JSON.stringify({failed, beforeReadDiscard, confirmed, buttonFound: Boolean(button),
  discardRequests: calls.length - beforeDiscard, final: mounted.controller.snapshot(),
  editDisabled: fieldControl("Page formatting reviewer", "INPUT").disabled,
  accepted: walk(root).find((node) => node.tagName === "LABEL"
    && node.children[1]?.textContent === "I accept these complete formatting decisions for this exact translation").querySelector("input").checked,
  unsafeWrites}));
""")
    assert result["failed"]["pendingKind"] == "submit" and not result["beforeReadDiscard"]
    assert result["confirmed"].get("canDiscardSubmission") and result["buttonFound"]
    assert result["confirmed"]["pendingKind"] == "submit", "Read alone must not abandon the request"
    assert result["discardRequests"] == 0 and not result["final"]["pendingKind"]
    assert not result["editDisabled"] and not result["accepted"] and result["unsafeWrites"] == 0


@pytest.mark.parametrize("kind", ["page", "document"])
def test_rejected_save_needs_fresh_read_and_explicit_discard_without_losing_local_edits(kind):
    result = probe(DOM + r"""
const calls = [], storage = memory(); let reject = true;
const saved = {...copy(draft), rebuild_operations: [], artifacts: []};
const mounted = ui.mountFormattingReview({root, prepareButton, getScope: () => scope, getJob: () => job, storage,
  request: async (url, owner, options) => {
    const body = options.body ? JSON.parse(options.body) : null; calls.push({url, body});
    if (url.includes("/pages/") || url.endsWith("/document")) {
      if (reject) throw new Error("browser_formatting_review_operation_failed");
      saved.generation += 1;
      if (data.kind === "page") saved.pages[0].decision = body.decision;
      else saved.document_decision = body.decision;
    }
    return envelope(saved);
  }});
await prepareButton.fire("click"); await mounted.controller.prepare(true);
const label = data.kind === "page" ? "Page formatting reviewer" : "Document formatting reviewer";
const saveLabel = data.kind === "page" ? "Save page formatting" : "Save document review";
const local = "Local reviewer <img src=x onerror=alert(1)>";
await fill(label, local); await findButton(saveLabel).fire("click");
const failed = mounted.controller.snapshot(), beforeRead = mounted.controller.discardUnsaved?.() || null;
await findButton("Read current formatting review").fire("click");
const confirmed = mounted.controller.snapshot(), stillLocked = fieldControl(label, "INPUT").disabled;
const beforeDiscard = calls.length;
const discard = walk(root).find((node) => node.tagName === "BUTTON" && node.textContent === "Discard the unsaved request and continue editing");
if (discard) await discard.fire("click");
const afterDiscard = mounted.controller.snapshot(), editable = !fieldControl(label, "INPUT").disabled;
const retainedReviewer = fieldControl(label, "INPUT").value, discardRequests = calls.length - beforeDiscard;
if (discard) { reject = false; await fill(label, local + " corrected"); await findButton(saveLabel).fire("click"); }
console.log(JSON.stringify({failed, beforeRead, confirmed, stillLocked, discardFound: Boolean(discard),
  afterDiscard, editable, retainedReviewer, discardRequests, unsafeWrites, final: mounted.controller.snapshot(),
  saves: calls.filter((row) => row.url.includes("/pages/") || row.url.endsWith("/document"))}));
""", data={"kind": kind})
    assert result["failed"]["pendingKind"] == kind and result["beforeRead"] is None
    assert result["confirmed"].get("canDiscardSave") and result["discardFound"]
    assert result["confirmed"]["pendingKind"] == kind and result["stillLocked"], "A read alone must not discard the request"
    assert not result["afterDiscard"]["pendingKind"] and result["afterDiscard"]["dirty"]
    assert result["editable"] and result["discardRequests"] == 0 and result["unsafeWrites"] == 0
    assert result["retainedReviewer"] == "Local reviewer <img src=x onerror=alert(1)>"
    assert len(result["saves"]) == 2 and not result["final"]["pendingKind"]
    original, corrected = (row["body"] for row in result["saves"])
    assert original["expected_generation"] == corrected["expected_generation"] == 1
    assert corrected["decision"] == {**original["decision"], "reviewer": original["decision"]["reviewer"] + " corrected"}


def test_pending_save_discard_refuses_unproven_changed_or_published_drafts():
    result = probe(r"""
const outcomes = [];
for (const kind of ["page", "document"]) for (const scenario of ["read_failed", "changed_generation", "pending", "published", "build_present", "artifact_present", "operations_missing", "artifacts_missing"]) {
  let calls = 0;
  const c = core.createFormattingReviewController({getScope: () => scope, getJob: () => job, storage: memory(), request: async (url, owner, options) => {
    calls += 1;
    if (url.endsWith("/prepare")) return envelope(draft);
    if (options.method === "POST" || scenario === "read_failed") throw new Error("Fictional failure");
    const view = {...copy(draft), rebuild_operations: [], artifacts: []};
    if (scenario === "changed_generation") view.generation += 2;
    if (scenario === "pending") view.status = "submission_pending";
    if (scenario === "published") Object.assign(view, {status: "submitted", revision_id: "b".repeat(32)});
    if (scenario === "build_present") view.rebuild_operations = [{operation_nonce: "c".repeat(32)}];
    if (scenario === "artifact_present") view.artifacts = [{artifact_id: "d".repeat(32)}];
    if (scenario === "operations_missing") delete view.rebuild_operations;
    if (scenario === "artifacts_missing") delete view.artifacts;
    return envelope(view);
  }});
  await c.prepare(true); c.markDirty(kind === "page" ? 1 : null);
  if (kind === "page") await c.savePage(1, pageDecision); else await c.saveDocument(documentDecision);
  await c.read(); const before = calls, discarded = c.discardUnsaved?.() || null;
  outcomes.push({kind, scenario, discarded, state: c.snapshot(), discardRequests: calls - before});
}
console.log(JSON.stringify(outcomes));
""")
    for row in result:
        assert row["discarded"] is None and not row["state"].get("canDiscardSave"), row["scenario"]
        assert row["state"]["pendingKind"] == row["kind"] and row["state"]["dirty"]
        assert row["discardRequests"] == 0


def test_pending_save_discard_proof_is_invalidated_and_cannot_forget_observed_changes():
    result = probe(r"""
const outcomes = [];
for (const action of ["busy", "failed_read", "retry", "inspect", "owner", "published_then_draft", "changed_then_draft"]) {
  let activeJob = {...job}, calls = 0, reading = "draft", resolveRead;
  const c = core.createFormattingReviewController({getScope: () => scope, getJob: () => activeJob, storage: memory(), request: async (url, owner, options) => {
    calls += 1;
    if (url.endsWith("/prepare")) return envelope(draft);
    if (options.method === "POST" || reading === "failed") throw new Error("Fictional failure");
    const view = {...copy(draft), rebuild_operations: [], artifacts: []};
    if (reading === "busy") return new Promise((resolve) => { resolveRead = resolve; });
    if (reading === "published") view.status = "submission_pending";
    if (reading === "changed") view.generation += 2;
    return envelope(view);
  }});
  await c.prepare(true); c.markDirty(1); await c.savePage(1, pageDecision); await c.read();
  const confirmed = c.snapshot(); let task;
  if (action === "busy") { reading = "busy"; task = c.read(); }
  if (action === "failed_read") { reading = "failed"; await c.read(); }
  if (action === "retry") await c.savePage(1, pageDecision);
  if (action === "inspect") await c.inspect();
  if (action === "owner") activeJob = {...job, job_id: "tx-other"};
  if (action.endsWith("_then_draft")) {
    reading = action.startsWith("published") ? "published" : "changed"; await c.read();
    reading = "draft"; await c.read();
  }
  const before = calls, discarded = c.discardUnsaved?.() || null, state = c.snapshot();
  if (task) { resolveRead(envelope({...draft, rebuild_operations: [], artifacts: []})); await task; }
  outcomes.push({action, confirmed, discarded, state, discardRequests: calls - before});
}
console.log(JSON.stringify(outcomes));
""")
    for row in result:
        assert row["confirmed"].get("canDiscardSave"), row["action"]
        assert row["discarded"] is None and not row["state"].get("canDiscardSave"), row["action"]
        assert row["discardRequests"] == 0


def test_matching_saved_decision_cannot_acknowledge_observed_changes_or_publication():
    result = probe(r"""
const outcomes = [];
for (const kind of ["page", "document"]) for (const scenario of ["earlier_generation", "earlier_publication", "same_pending", "same_revision", "same_build", "same_artifact", "missing_operations", "missing_artifacts"]) {
  let reads = 0, saves = 0;
  const decision = {...(kind === "page" ? pageDecision : documentDecision), reviewer: "Exact pending reviewer"};
  const c = core.createFormattingReviewController({getScope: () => scope, getJob: () => job, storage: memory(), request: async (url, owner, options) => {
    if (url.endsWith("/prepare")) return envelope(draft);
    if (options.method === "POST") { saves += 1; throw new Error("Fictional lost save response"); }
    reads += 1;
    const view = {...copy(draft), generation: 2};
    if (kind === "page") view.pages[0].decision = copy(decision); else view.document_decision = copy(decision);
    if (scenario === "earlier_generation" && reads === 1) view.generation = 3;
    if (scenario === "earlier_publication" && reads === 1) { view.generation = 1; view.status = "submission_pending"; }
    if (scenario === "same_pending") view.status = "submission_pending";
    if (scenario === "same_revision") Object.assign(view, {status: "submitted", revision_id: "b".repeat(32)});
    if (scenario === "same_build") view.rebuild_operations = [{operation_nonce: "c".repeat(32)}];
    if (scenario === "same_artifact") view.artifacts = [{artifact_id: "d".repeat(32)}];
    if (scenario === "missing_operations") delete view.rebuild_operations;
    if (scenario === "missing_artifacts") delete view.artifacts;
    return envelope(view);
  }});
  await c.prepare(true); c.markDirty(kind === "page" ? 1 : null);
  if (kind === "page") await c.savePage(1, decision); else await c.saveDocument(decision);
  await c.read(); if (scenario.startsWith("earlier_")) await c.read();
  outcomes.push({kind, scenario, state: c.snapshot(), discarded: c.discardUnsaved(), saves});
}
console.log(JSON.stringify(outcomes));
""")
    for row in result:
        assert row["state"]["pendingKind"] == row["kind"] and row["state"]["dirty"], row["scenario"]
        assert not row["state"]["canDiscardSave"] and row["discarded"] is None
        assert row["saves"] == 1


def test_uncertain_submission_reads_cannot_discard_or_grant_new_build_authority():
    result = probe(r"""
const outcomes = [];
for (const scenario of ["pending", "published", "changed_generation", "build_present", "read_failed"]) {
  const storage = memory(); let reads = 0, submits = 0, builds = 0;
  const c = core.createFormattingReviewController({getScope: () => scope, getJob: () => job, storage,
    request: async (url) => {
      if (url.endsWith("/prepare")) return envelope(draft);
      if (url.endsWith("/submit")) { submits += 1; throw new Error("Response uncertain"); }
      if (url.endsWith("/rebuild")) { builds += 1; throw new Error("Must not dispatch"); }
      reads += 1;
      if (scenario === "read_failed") throw new Error("Read unavailable");
      const view = {...draft, rebuild_operations: [], artifacts: []};
      if (scenario === "pending") view.status = "submission_pending";
      if (scenario === "published") Object.assign(view, {status: "submitted", revision_id: "b".repeat(32)});
      if (scenario === "changed_generation") view.generation += 1;
      if (scenario === "build_present") view.rebuild_operations = [{operation_nonce: "c".repeat(32), revision_id: "b".repeat(32)}];
      return envelope(view);
    }});
  await c.prepare(true); await c.submit("Original reviewer", true); await c.read();
  const discarded = c.discardUnsubmitted?.() || null; await c.rebuild();
  outcomes.push({scenario, discarded, state: c.snapshot(), reads, submits, builds});
}
console.log(JSON.stringify(outcomes));
""")
    for row in result:
        assert row["discarded"] is None and row["state"]["pendingKind"] == "submit", row["scenario"]
        assert not row["state"].get("canDiscardSubmission") and not row["state"]["revisionId"]
        assert row["submits"] == row["reads"] == 1 and row["builds"] == 0


def test_reading_or_resubmitting_restored_published_revision_does_not_mint_build():
    result = probe(r"""
const storage = memory(); let builds = 0, nonces = 0;
const revision = {...draft, status: "submitted", revision_id: "b".repeat(32), rebuild_operations: [], artifacts: []};
const options = {getScope: () => scope, getJob: () => job, storage,
  createNonce: () => { nonces += 1; return "c".repeat(32); }, request: async (url) => {
    if (url.endsWith("/prepare")) return envelope(draft);
    if (url.endsWith("/rebuild")) { builds += 1; throw new Error("Must not dispatch"); }
    return envelope(revision);
  }};
const initial = core.createFormattingReviewController(options); await initial.prepare(true); await initial.submit("Operator", true);
const restored = core.createFormattingReviewController(options); await restored.read(); await restored.rebuild();
const readOnly = restored.snapshot(); await restored.submit("Operator", true); await restored.rebuild();
console.log(JSON.stringify({readOnly, final: restored.snapshot(), builds, nonces}));
""")
    assert result["readOnly"]["restored"] and result["final"]["restored"]
    assert result["final"]["errorCode"] == "formatting_review_unknown_build"
    assert result["builds"] == result["nonces"] == 0


def test_restored_lost_submit_requires_exact_ack_and_cannot_replace_known_build():
    result = probe(r"""
const outcomes = [];
for (const recordedBuild of [false, true]) {
  const storage = memory(), bodies = []; let published = false, builds = 0, nonces = 0;
  const revision = {...draft, status: "submitted", revision_id: "b".repeat(32)};
  const options = {getScope: () => scope, getJob: () => job, storage,
    createNonce: () => { nonces += 1; return "c".repeat(32); }, request: async (url, owner, options) => {
      if (url.endsWith("/prepare")) return envelope(draft);
      if (url.endsWith("/submit")) {
        bodies.push(JSON.parse(options.body)); published = true;
        if (bodies.length === 1) throw new Error("Published; response lost");
        // The real submit response has no generation or operation inventory.
        return envelope({status: "submitted", review_id: draft.review_id, job_id: job.job_id,
          reviewer_kind: "operator_review", revision_id: revision.revision_id});
      }
      if (url.endsWith("/rebuild")) { builds += 1; throw new Error("Retain this exact pending build"); }
      return envelope({...published ? revision : draft, rebuild_operations: published && recordedBuild
        ? [{operation_nonce: "f".repeat(32), revision_id: revision.revision_id, status: "pending"}] : [], artifacts: []});
    }};
  const initial = core.createFormattingReviewController(options); await initial.prepare(true);
  const restored = core.createFormattingReviewController(options); await restored.read();
  await restored.submit("Exact reviewer", true); await restored.read();
  const uncertain = restored.snapshot(); await restored.rebuild(); const beforeRetry = builds;
  await restored.submit("Different reviewer", true); const changedReviewerCount = bodies.length;
  await restored.submit("Exact reviewer", true); const acknowledged = restored.snapshot(); await restored.rebuild();
  outcomes.push({recordedBuild, uncertain, beforeRetry, changedReviewerCount, bodies, acknowledged, builds, nonces});
}
console.log(JSON.stringify(outcomes));
""")
    for row in result:
        assert row["uncertain"]["restored"] and row["uncertain"]["pendingKind"] == "submit"
        assert not row["uncertain"]["revisionId"] and not row["uncertain"]["canDiscardSubmission"]
        assert row["beforeRetry"] == 0 and row["changedReviewerCount"] == 1
        assert len(row["bodies"]) == 2 and row["bodies"][0] == row["bodies"][1]
        assert not row["acknowledged"]["pendingKind"]
        assert row["acknowledged"]["restored"] is row["recordedBuild"]
        assert row["builds"] == row["nonces"] == (0 if row["recordedBuild"] else 1)


def test_confirmed_discard_permission_is_invalidated_by_failed_read_or_owner_change():
    result = probe(r"""
const outcomes = [];
for (const changedOwner of [false, true]) {
  let activeJob = {...job}, failRead = false, requests = 0;
  const c = core.createFormattingReviewController({getScope: () => scope, getJob: () => activeJob, storage: memory(),
    request: async (url) => {
      requests += 1;
      if (url.endsWith("/submit") || failRead) throw new Error("Fictional failure");
      return envelope({...draft, rebuild_operations: [], artifacts: []});
    }});
  await c.prepare(true); await c.submit("Operator", true); await c.read();
  const confirmed = c.snapshot();
  if (changedOwner) activeJob = {...job, job_id: "tx-other"};
  else { failRead = true; await c.read(); }
  const before = requests, discarded = c.discardUnsubmitted();
  outcomes.push({changedOwner, confirmed, discarded, state: c.snapshot(), discardRequests: requests - before});
}
console.log(JSON.stringify(outcomes));
""")
    for row in result:
        assert row["confirmed"]["canDiscardSubmission"]
        assert row["discarded"] is None and not row["state"]["canDiscardSubmission"]
        assert row["discardRequests"] == 0
        if not row["changedOwner"]:
            assert row["state"]["pendingKind"] == "submit" and not row["state"]["verified"]


def test_observed_publication_cannot_be_discarded_after_a_contradictory_draft_read():
    result = probe(r"""
const outcomes = [];
for (const observedStatus of ["submission_pending", "submitted"]) {
  let reads = 0, submits = 0;
  const revision = {...draft, status: "submitted", revision_id: "b".repeat(32)};
  const c = core.createFormattingReviewController({getScope: () => scope, getJob: () => job, storage: memory(),
    request: async (url) => {
      if (url.endsWith("/prepare")) return envelope(draft);
      if (url.endsWith("/submit")) {
        submits += 1; if (submits < 3) throw new Error("Acknowledgement uncertain");
        return envelope(revision);
      }
      reads += 1;
      const view = {...draft, rebuild_operations: [], artifacts: []};
      if (reads === 1) {
        view.status = observedStatus;
        if (observedStatus === "submitted") view.revision_id = revision.revision_id;
      }
      // Healthy service intent is durable. A contradictory response must not
      // undo an already observed publication when preserving uncertainty.
      return envelope(view);
    }});
  await c.prepare(true); await c.submit("Same reviewer", true); await c.read();
  await c.submit("Same reviewer", true); await c.read();
  const contradicted = c.snapshot(), discarded = c.discardUnsubmitted();
  await c.submit("Same reviewer", true);
  outcomes.push({observedStatus, contradicted, discarded, submits, final: c.snapshot()});
}
console.log(JSON.stringify(outcomes));
""")
    for row in result:
        assert not row["contradicted"]["canDiscardSubmission"] and row["discarded"] is None
        assert row["contradicted"]["pendingKind"] == "submit" and row["submits"] == 3
        assert not row["final"]["pendingKind"] and row["final"]["revisionId"] == "b" * 32


def test_stale_revision_check_or_build_failure_disables_previous_download_until_fresh_read():
    result = probe(r"""
const revision = {...draft, status: "submitted", revision_id: "b".repeat(32)};
const artifact = {artifact_id: "d".repeat(32), revision_id: revision.revision_id, kinds: ["output_docx"]};
const built = {...revision, status: "built", artifacts: [artifact], rebuild_operations: [
  {operation_nonce: "c".repeat(32), revision_id: revision.revision_id, artifact_id: artifact.artifact_id, status: "built"}]};
let failBuild = false;
const c = core.createFormattingReviewController({getScope: () => scope, getJob: () => job, storage: memory(), createNonce: () => "c".repeat(32),
  request: async (url) => {
    if (url.endsWith("/prepare")) return envelope(draft);
    if (url.endsWith("/submit")) return envelope(revision);
    if (url.includes("/revisions/") || url.endsWith("/rebuild") && failBuild) throw new Error("reviewed_profile_stale_edited_target");
    return envelope(built);
  }});
await c.prepare(true); await c.submit("Operator", true); await c.rebuild(); const good = c.artifactUrl();
await c.inspect(); const afterInspect = {href: c.artifactUrl(), state: c.snapshot()};
await c.read(); const refreshed = c.artifactUrl(); failBuild = true; await c.rebuild();
console.log(JSON.stringify({good, afterInspect, refreshed, afterBuild: {href: c.artifactUrl(), state: c.snapshot()}}));
""")
    assert result["good"] and result["refreshed"]
    assert not result["afterInspect"]["href"] and not result["afterInspect"]["state"]["verified"]
    assert not result["afterBuild"]["href"] and result["afterBuild"]["state"]["errorCode"] == "reviewed_profile_stale_edited_target"


def _dom_page_probe(view, *, selected_job=None):
    return probe(DOM + r"""
const calls = [];
const selectionReadOnly = [];
const mounted = ui.mountFormattingReview({root, prepareButton, getScope: () => scope, getJob: () => data.job || job,
  storage: memory(), request: async (url, owner, options) => {
    calls.push({url, owner, body: options.body ? JSON.parse(options.body) : null});
    if (url.endsWith("/prepare")) return envelope(data.view);
    throw new Error("Capture explicit DOM decisions for the public API");
  }});
await prepareButton.fire("click");
await fill("Page layout for this review", "matched", "SELECT", "change");
await findButton("Prepare formatting review").fire("click");
const initialChecks = walk(root).filter((node) => node.type === "checkbox").map((node) => node.checked);
for (const [index, parent] of data.view.pages[0].parents.entries()) {
  await fill("Source / target block", String(parent.parent_number), "SELECT", "change");
  let area = fieldControl("Source text", "TEXTAREA"); area.selectionStart = 0; area.selectionEnd = area.value.length;
  selectionReadOnly.push(area.readOnly);
  await findButton("Use selected source text").fire("click");
  area = fieldControl("Translation text", "TEXTAREA"); area.selectionStart = 0; area.selectionEnd = area.value.length;
  selectionReadOnly.push(area.readOnly);
  await findButton("Use selected translation text").fire("click");
  for (const [label, value] of [["Region left (px)", 10], ["Region top (px)", 10 + index * 40], ["Region right (px)", 190], ["Region bottom (px)", 30 + index * 40]]) await fill(label, String(value));
  await fill("Fragment role", "body", "SELECT", "change"); await fill("Text alignment", "left", "SELECT", "change");
  await fill("Fragment review explanation", "Explicit comparison of this complete fictional source and translation.");
  await findButton("Add this explicit fragment").fire("click");
  await fill("New body paragraph", String(index + 1), "SELECT", "change");
  await findButton("Add selected body paragraph").fire("click");
}
await fill("Page formatting reviewer", "Fictional formatting operator"); await fill("Page review explanation", "Reviewed the complete page.");
await check("I reviewed the complete page image and its formatting"); await check("I checked every source-to-translation text selection");
await findButton("Save page formatting").fire("click");
console.log(JSON.stringify({calls, initialChecks, unsafeWrites, selectionReadOnly, text: root.textContent,
  readOnly: walk(root).filter((node) => node.tagName === "TEXTAREA").every((node) => node.readOnly),
  labelled: walk(root).filter((node) => node.tagName === "LABEL").every((node) => {
    const control = node.querySelector("input") || node.querySelector("select") || node.querySelector("textarea");
    return control && node.htmlFor === control.id && Boolean(control.attributes["aria-label"]);
  }),
  images: walk(root).filter((node) => node.tagName === "IMG").map((node) => node.src)}));
""", data={"view": view, "job": selected_job})


def test_dom_requires_independent_selections_safe_text_and_explicit_page_acceptance():
    text = '<img src=x onerror="alert(1)"> ملف 😀 e\u0301 121/26'
    view = {"status": "draft", "review_id": "a" * 32, "job_id": "tx-owned", "generation": 1,
        "page_matched_derivative": True, "reviewer_kind": "operator_review", "document_decision": None,
        "pages": [{"page_number": 1, "image_size_px": [200, 300], "source_provenance": "ocr", "source_uncertain": True,
            "parents": [{"parent_number": 1, "source_text": text, "target_text": "Fictional translation 😀"}], "decision": None}]}
    result = _dom_page_probe(view)
    decision = result["calls"][-1]["body"]["decision"]
    assert result["unsafeWrites"] == 0 and not any(result["initialChecks"])
    assert result["readOnly"] and result["labelled"] and text in result["text"] and result["selectionReadOnly"] == [True, True]
    assert decision["fragments"][0]["source_range"] == [0, len(text)]
    assert decision["fragments"][0]["target_range"] == [0, len("Fictional translation 😀")]
    assert decision["body"] == [{"fragment_number": 1}] and decision["full_page_review_completed"] is True
    assert decision["source_target_mapping_reviewed"] is True
    assert result["calls"][-1]["url"].endswith("/pages/1")


def test_ordinary_actions_remain_separate_from_formatting_hooks():
    root = Path(__file__).resolve().parents[1] / "src/legalpdf_translate/shadow_web"
    translation = (root / "static/translation.js").read_text(encoding="utf-8")
    ordinary = translation.split("async function handleTranslate() {", 1)[1].split("async function handleResume", 1)[0]
    assert '"/api/translation/jobs/translate"' in ordinary and "formatting" not in ordinary
    assert '"translation-formatting-review-panel"' in translation
    ui = (root / "static/formatting_review_ui.js").read_text(encoding="utf-8")
    assert "innerHTML" not in ui and "insertAdjacentHTML" not in ui
    assert "readOnly: true" in ui and "server restart cannot restore" in ui
    assert 'id="translation-formatting-review-prepare" disabled' in (root / "templates/index.html").read_text(encoding="utf-8")


def test_unfinished_fragment_edit_blocks_reordering_and_clears_document_completion():
    result = probe(DOM + r"""
const page = {...draft.pages[0], decision: {...pageDecision, fragments: [fragment, {...fragment, review_note: "Second original", bbox_px: [10,40,100,60]}],
  body: [{fragment_number: 1}, {fragment_number: 2}]}};
const prepared = {...draft, pages: [page]};
let captured;
const mounted = ui.mountFormattingReview({root, prepareButton, getScope: () => scope, getJob: () => job, storage: memory(),
  request: async (url, owner, options) => {
    if (url.endsWith("/prepare")) return envelope(prepared);
    captured = JSON.parse(options.body); throw new Error("Capture only");
  }});
await prepareButton.fire("click"); await fill("Page layout for this review", "matched", "SELECT", "change");
await findButton("Prepare formatting review").fire("click");
const edits = walk(root).filter((node) => node.tagName === "BUTTON" && node.textContent === "Edit fragment");
await edits[1].fire("click");
const reorders = walk(root).filter((node) => node.tagName === "BUTTON" && node.textContent.startsWith("Move fragment"));
const allMovesDisabled = reorders.every((node) => node.disabled);
let rejectedDisabledClick = false;
try { await reorders.find((node) => node.textContent === "Move fragment earlier").fire("click"); } catch { rejectedDisabledClick = true; }
await fill("Fragment review explanation", "Second explicitly edited");
await findButton("Save this fragment edit").fire("click");
const documentCheck = walk(root).find((node) => node.tagName === "LABEL" && node.children[1]?.textContent === "I reviewed every page, its text mappings and the document groups").querySelector("input");
const documentCleared = !documentCheck.checked;
await check("I reviewed the complete page image and its formatting"); await check("I checked every source-to-translation text selection");
await findButton("Save page formatting").fire("click");
console.log(JSON.stringify({allMovesDisabled, rejectedDisabledClick, documentCleared, captured, state: mounted.controller.snapshot()}));
""")
    assert result["allMovesDisabled"] and result["rejectedDisabledClick"] and result["documentCleared"]
    assert result["captured"]["decision"]["fragments"][0]["review_note"] == "Explicit visual comparison"
    assert result["captured"]["decision"]["fragments"][1]["review_note"] == "Second explicitly edited"
    assert result["captured"]["decision"]["body"] == [{"fragment_number": 1}, {"fragment_number": 2}]
    assert result["state"]["documentDirty"]


def test_external_page_save_invalidates_visible_document_completion_on_new_generation_read():
    result = probe(DOM + r"""
let current = copy(draft);
const mounted = ui.mountFormattingReview({root, prepareButton, getScope: () => scope, getJob: () => job, storage: memory(),
  request: async () => envelope(current)});
await prepareButton.fire("click"); await fill("Page layout for this review", "matched", "SELECT", "change");
await findButton("Prepare formatting review").fire("click");
const completion = () => walk(root).find((node) => node.tagName === "LABEL" && node.children[1]?.textContent === "I reviewed every page, its text mappings and the document groups").querySelector("input").checked;
const before = completion();
current = {...current, generation: 2, document_decision: null, pages: [{...current.pages[0], decision: {...pageDecision, review_note: "Another explicit page edit"}}]};
await findButton("Read current formatting review").fire("click");
const after = completion();
console.log(JSON.stringify({before, after, preservedReviewer: fieldControl("Document formatting reviewer").value,
  preservedGroup: fieldControl("Group 1 first page").value, state: mounted.controller.snapshot()}));
""")
    assert result["before"] and not result["after"]
    assert result["preservedReviewer"] == "Operator" and result["preservedGroup"] == 1
    assert result["state"]["view"]["document_decision"] is None


def test_table_controls_emit_explicit_cell_ownership_widths_and_measured_column_gaps():
    result = probe(DOM + r"""
const prepared = {...draft, document_decision: null, pages: [{...draft.pages[0], decision: {...pageDecision,
  fragments: [fragment, {...fragment, bbox_px: [130,10,190,30]}], body: [], full_page_review_completed: false, source_target_mapping_reviewed: false}}]};
let captured;
const mounted = ui.mountFormattingReview({root, prepareButton, getScope: () => scope, getJob: () => job, storage: memory(),
  request: async (url, owner, options) => {
    if (url.endsWith("/prepare")) return envelope(prepared);
    captured = JSON.parse(options.body); throw new Error("Capture table controls");
  }});
await prepareButton.fire("click"); await fill("Page layout for this review", "matched", "SELECT", "change");
await findButton("Prepare formatting review").fire("click");
await fill("New table columns", "2", "SELECT", "change"); await findButton("Add empty table").fire("click");
await fill("Column 1 width (%)", "50"); await fill("Column 2 width (%)", "50");
await check("I want to preserve measured spaces between these columns");
await fill("Reviewed space after column 1 (px)", "30");
async function assign(label, number) {
  const group = walk(root).find((node) => node.className === "formatting-review-owner" && node.children[0]?.textContent === label);
  const selector = group.querySelector("select"); selector.value = String(number); await selector.fire("change");
  await walk(group).find((node) => node.tagName === "BUTTON" && node.textContent === "Assign selected fragment here").fire("click");
}
await assign("Row 1, column 1", 1); await assign("Row 1, column 2", 2);
await check("I reviewed the complete page image and its formatting"); await check("I checked every source-to-translation text selection");
await findButton("Save page formatting").fire("click");
console.log(JSON.stringify({captured, unsafeWrites}));
""")
    assert result["unsafeWrites"] == 0
    assert result["captured"]["decision"]["body"] == [{"column_widths": [50, 50], "rows": [[[1], [2]]], "column_gaps_px": [30]}]
    assert result["captured"]["decision"]["full_page_review_completed"]


def _dom_document_probe(view, *, selected_job, accepted=None, built=None):
    return probe(DOM + r"""
const calls = [];
const mounted = ui.mountFormattingReview({root, prepareButton, getScope: () => scope, getJob: () => data.job,
  storage: memory(), createNonce: () => "c".repeat(32), request: async (url, owner, options) => {
    calls.push({url, owner, body: options.body ? JSON.parse(options.body) : null});
    if (url.endsWith("/prepare")) return envelope(data.view);
    if (url.endsWith("/submit") && data.accepted) return envelope(data.accepted);
    if (url.endsWith("/rebuild") && data.built) return envelope(data.built);
    throw new Error("Capture explicit document operation for actual public API");
  }});
await prepareButton.fire("click"); await fill("Page layout for this review", "matched", "SELECT", "change");
await findButton("Prepare formatting review").fire("click");
if (!data.view.document_decision) {
  await findButton("Add document group").fire("click");
  await fill("Group 1 first page", "1"); await fill("Group 1 last page", String(data.view.pages.length));
  await fill("Text separators inside reviewed table cells", "no", "SELECT", "change");
  await fill("Vertical spacing between source regions", "no", "SELECT", "change");
  await fill("Document formatting reviewer", "Fictional formatting operator");
  await fill("Document review explanation", "Compared all source pages and translations; reviewed every document boundary.");
  await check("I reviewed every page, its text mappings and the document groups");
  await findButton("Save document review").fire("click");
} else {
  await fill("Formatting acceptance reviewer", "Fictional formatting operator");
  await check("I accept these complete formatting decisions for this exact translation");
  await findButton("Accept formatting revision").fire("click");
  if (data.accepted) await findButton("Build DOCX from this revision").fire("click");
}
console.log(JSON.stringify({calls, href: mounted.controller.artifactUrl(), unsafeWrites, state: mounted.controller.snapshot()}));
""", data={"view": view, "job": selected_job, "accepted": accepted, "built": built})


def test_actual_dom_to_owned_formatting_api_build_and_download_preserves_original_run(tmp_path, monkeypatch):
    from legalpdf_translate import ocr_engine as ocr, workflow as workflow_module
    from tests.test_shadow_web_formatting_review_api import (
        formatting_api_case, completed_reviewed_job, prefix, view, HEADERS,
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Formatting UI test must not invoke credentials, provider auth, native extraction or OCR")

    monkeypatch.delenv("LEGALPDF_TRANSLATION_PROTOCOL", raising=False)
    monkeypatch.setattr(workflow_module, "load_gui_settings", lambda: {})
    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    for name in ("run_translation_auth_test", "extract_ordered_page_text", "resolve_openai_key_with_source"):
        monkeypatch.setattr(workflow_module, name, forbidden)
    # Isolate only OCR's native boundary. Do not replace stdlib subprocess.run:
    # the established Node browser probe must retain its normal runner.
    monkeypatch.setattr(ocr, "subprocess", SimpleNamespace(run=forbidden))
    monkeypatch.setattr(ocr, "build_ocr_engine", forbidden)
    monkeypatch.setattr(ocr, "resolve_ocr_api_key", forbidden)
    monkeypatch.setattr(ocr, "which", lambda _: "synthetic-tesseract")
    monkeypatch.setattr(ocr, "_text_quality_score", lambda _: 0.99)
    c = formatting_api_case(tmp_path, monkeypatch)
    with TestClient(c.app) as client:
        # This helper creates genuine public source review evidence and actual
        # Workflow commits through synthetic local OCR and SDK boundaries.
        job = completed_reviewed_job(client, c)
        assert job["actions"]["formatting_review"]
        before = {path: path.read_bytes() for path in c.run_dir.rglob("*") if path.is_file()}
        before[c.settings] = c.settings.read_bytes()
        original = Path(job["artifacts"]["output_docx"])
        before[original] = original.read_bytes()
        base = prefix(job)
        draft = view(client.post(base + "/prepare", headers=HEADERS, json={"page_matched_derivative": True}))
        assert draft["formatting_derivative"]["original_page_breaks"] is False
        assert len(draft["pages"]) == 1 and draft["pages"][0]["decision"] is None
        page_probe = _dom_page_probe(draft, selected_job=job)
        wire = page_probe["calls"][-1]
        assert wire["url"] == base + f"/{draft['review_id']}/pages/1"
        assert set(wire["body"]) == {"expected_generation", "decision"}
        saved_page = view(client.post(wire["url"], headers=HEADERS, json=wire["body"]))
        image = client.get(page_probe["images"][0])
        assert image.status_code == 200 and image.content.startswith(b"\x89PNG")
        document_probe = _dom_document_probe(saved_page, selected_job=job)
        wire = document_probe["calls"][-1]
        assert wire["url"] == base + f"/{draft['review_id']}/document"
        saved_document = view(client.post(wire["url"], headers=HEADERS, json=wire["body"]))
        acceptance_probe = _dom_document_probe(saved_document, selected_job=job)
        wire = acceptance_probe["calls"][-1]
        assert wire["body"]["accept_formatting"] is True
        accepted = view(client.post(wire["url"], headers=HEADERS, json=wire["body"]))
        assert accepted["reviewer_kind"] == "operator_review"
        build_probe = _dom_document_probe(saved_document, selected_job=job, accepted=accepted)
        wire = build_probe["calls"][-1]
        assert wire["body"] == {"revision_id": accepted["revision_id"], "operation_nonce": "c" * 32}
        built = view(client.post(wire["url"], headers=HEADERS, json=wire["body"]))
        repeated = view(client.post(wire["url"], headers=HEADERS, json=wire["body"]))
        assert repeated == built and built["status"] == "built"
        download_probe = _dom_document_probe(saved_document, selected_job=job, accepted=accepted, built=built)
        downloaded = client.get(download_probe["href"])
        assert downloaded.status_code == 200 and downloaded.content.startswith(b"PK")
        assert downloaded.headers["cache-control"] == "no-store"
        assert downloaded.headers["content-disposition"].startswith("attachment;")
        assert built["geometry_status"] == "not_verified" and built["rendered_layout_acceptance"] == "not_evaluated"
        assert all(p["unsafeWrites"] == 0 for p in (page_probe, document_probe, acceptance_probe, build_probe, download_probe))
        assert {path: path.read_bytes() for path in before} == before
        latest_job = client.get(f"/api/translation/jobs/{job['job_id']}", headers=HEADERS).json()["normalized_payload"]["job"]
        assert latest_job["artifacts"]["output_docx"] == str(original)
    assert len(c.clients) == len(c.sdk_calls) == len(c.local_calls) == 1


def test_opening_formatting_review_dismisses_only_its_originating_overflow_menu():
    result = probe(DOM + r"""
const menu = {open: true}, otherMenu = {open: true}, scrollStates = [];
prepareButton.closest = (selector) => selector === "details.action-overflow-menu" ? menu : null;
root.scrollIntoView = () => scrollStates.push({originMenuOpen: menu.open, otherMenuOpen: otherMenu.open});
let requests = 0;
const mounted = ui.mountFormattingReview({root, prepareButton, getScope: () => scope, getJob: () => job,
  storage: memory(), request: async () => { requests += 1; throw new Error("No request from opening panel"); }});
await prepareButton.fire("click");
const first = {menuOpen: menu.open, otherOpen: otherMenu.open, panelVisible: !root.hidden};
menu.open = true;
await prepareButton.fire("click");
prepareButton.closest = () => null;
await prepareButton.fire("click");
console.log(JSON.stringify({first, menuOpen: menu.open, otherOpen: otherMenu.open, scrollStates,
  requests, unsafeWrites, state: mounted.controller.snapshot()}));
""")
    assert result["first"] == {"menuOpen": False, "otherOpen": True, "panelVisible": True}
    assert not result["menuOpen"] and result["otherOpen"]
    assert len(result["scrollStates"]) == 3
    assert all(not row["originMenuOpen"] and row["otherMenuOpen"] for row in result["scrollStates"])
    assert result["requests"] == result["unsafeWrites"] == 0
    assert not result["state"]["reviewId"] and not result["state"]["operationNonce"]


def test_busy_formatting_operations_do_not_request_images_and_preserve_exact_recovery():
    result = probe(DOM + r"""
const imageRequests = [];
doc.createElement = (tag) => {
  const node = make(tag);
  if (node.tagName === "IMG") {
    let src = "";
    Object.defineProperty(node, "src", {get: () => src, set: (value) => {
      src = value; imageRequests.push(value);
    }});
  }
  return node;
};
const revision = {...draft, status: "submitted", revision_id: "b".repeat(32)};
const storage = memory(), requests = [], phases = [];
let pending, nonceCount = 0;
const mounted = ui.mountFormattingReview({root, prepareButton, getScope: () => scope, getJob: () => job, storage,
  createNonce: () => { nonceCount += 1; return "c".repeat(32); },
  request: async (url, owner, options) => {
    requests.push({url, body: options.body ? JSON.parse(options.body) : null});
    if (url.endsWith("/prepare")) return envelope(draft);
    if (url.endsWith("/submit")) return envelope(revision);
    return new Promise((resolve, reject) => { pending = {resolve, reject}; });
  }});
const imageCount = () => walk(root).filter((node) => node.tagName === "IMG").length;
function capture(name, before) {
  phases.push({name, beforeRequests: before, pendingRequests: imageRequests.length,
    pendingImages: imageCount(), busy: mounted.controller.snapshot().busy,
    footerPresent: walk(root).some((node) => node.className === "formatting-review-submit"),
    readDisabled: findButton("Read current formatting review").disabled});
}
await prepareButton.fire("click");
await fill("Page layout for this review", "matched", "SELECT", "change");
await findButton("Prepare formatting review").fire("click");
await fill("Formatting acceptance reviewer", "Fictional operator");
await check("I accept these complete formatting decisions for this exact translation");
await findButton("Accept formatting revision").fire("click");
let before = imageRequests.length;
let task = findButton("Read current formatting review").fire("click");
capture("read", before);
pending.resolve(envelope(revision)); await task;
const successfulRead = {requests: imageRequests.length - before, images: imageCount(), verified: mounted.controller.snapshot().verified};
before = imageRequests.length;
task = findButton("Check this exact revision").fire("click");
capture("inspect", before);
pending.reject(new Error("Fictional inspect transport failure")); await task;
const failedInspect = {images: imageCount(), verified: mounted.controller.snapshot().verified, busy: mounted.controller.snapshot().busy};
task = findButton("Read current formatting review").fire("click");
pending.resolve(envelope(revision)); await task;
const recoveredInspect = {images: imageCount(), verified: mounted.controller.snapshot().verified};
before = imageRequests.length;
task = findButton("Build DOCX from this revision").fire("click");
capture("rebuild", before);
const pendingBuild = mounted.controller.snapshot();
pending.reject(new Error("browser_formatting_review_run_busy")); await task;
const failedBuild = mounted.controller.snapshot();
task = findButton("Read current formatting review").fire("click");
pending.resolve(envelope({...revision, rebuild_operations: [], artifacts: []})); await task;
const recoveredBuild = mounted.controller.snapshot();
task = findButton("Recover this exact DOCX build").fire("click");
const artifact = {artifact_id: "d".repeat(32), revision_id: revision.revision_id,
  kinds: ["output_docx", "source_map", "assembly_receipt"]};
pending.resolve(envelope({...revision, status: "built", artifacts: [artifact], rebuild_operations: [{
  operation_nonce: "c".repeat(32), revision_id: revision.revision_id, artifact_id: artifact.artifact_id}]}));
await task;
console.log(JSON.stringify({phases, successfulRead, failedInspect, recoveredInspect, pendingBuild, failedBuild,
  recoveredBuild, final: mounted.controller.snapshot(), nonceCount,
  rebuildRequests: requests.filter((row) => row.url.endsWith("/rebuild")), unsafeWrites}));
""")
    for phase in result["phases"]:
        assert phase["pendingRequests"] == phase["beforeRequests"], phase["name"]
        assert phase["pendingImages"] == 0, phase["name"]
        assert phase["busy"] and phase["footerPresent"] and phase["readDisabled"]
    assert result["successfulRead"] == {"requests": 1, "images": 1, "verified": True}
    assert result["failedInspect"] == {"images": 0, "verified": False, "busy": False}
    assert result["recoveredInspect"] == {"images": 1, "verified": True}
    assert result["pendingBuild"]["busy"] and result["pendingBuild"]["operationNonce"] == "c" * 32
    assert result["failedBuild"]["errorCode"] == "browser_formatting_review_run_busy"
    assert not result["failedBuild"]["busy"] and not result["failedBuild"]["verified"]
    assert result["failedBuild"]["operationNonce"] == result["recoveredBuild"]["operationNonce"] == "c" * 32
    assert result["recoveredBuild"]["verified"] and not result["recoveredBuild"]["associated"]
    requests = result["rebuildRequests"]
    assert len(requests) == 2
    assert requests[0]["body"] == requests[1]["body"] == {
        "revision_id": "b" * 32, "operation_nonce": "c" * 32,
    }
    assert result["nonceCount"] == 1 and result["unsafeWrites"] == 0
    assert result["final"]["associated"] and result["final"]["artifactId"] == "d" * 32


@pytest.mark.parametrize("reject_corrected_save", [False, True])
def test_corrected_local_table_warning_clears_without_hiding_server_error_or_skipping_recovery(reject_corrected_save):
    result = probe(DOM + r"""
const calls = [], storage = memory(); let reject = data.reject, nonces = 0;
const fragments = Array.from({length: 4}, (_, index) => ({...fragment, parent_number: index + 1,
  bbox_px: [10 + (index % 3) * 60, 10 + Math.floor(index / 3) * 50, 50 + (index % 3) * 60, 30 + Math.floor(index / 3) * 50]}));
let saved = {...copy(draft), document_decision: null, pages: [{...copy(draft.pages[0]),
  parents: fragments.map((item) => ({parent_number: item.parent_number, source_text: "Case", target_text: "Case"})),
  decision: {...copy(pageDecision), fragments, body: [
    {column_widths: [34, 33, 33], rows: [[[1], [2], [3]]], column_gaps_px: [12, 12]},
    {column_widths: [100], rows: [[[4]]]}]}}]};
const mounted = ui.mountFormattingReview({root, prepareButton, getScope: () => scope, getJob: () => job, storage,
  createNonce: () => { nonces += 1; return "c".repeat(32); }, request: async (url, owner, options) => {
    const body = options.body ? JSON.parse(options.body) : null; calls.push({url, body});
    if (url.includes("/pages/")) {
      if (reject) throw new Error("browser_formatting_review_run_busy");
      saved = {...saved, generation: saved.generation + 1, document_decision: null,
        pages: [{...saved.pages[0], decision: copy(body.decision)}]};
    } else if (url.endsWith("/document")) {
      saved = {...saved, generation: saved.generation + 1, document_decision: copy(body.decision)};
    } else if (url.endsWith("/submit")) {
      saved = {...saved, status: "submitted", revision_id: "b".repeat(32)};
    } else if (url.endsWith("/rebuild")) {
      if (![...storage.data.values()].some((raw) => raw.includes(body.operation_nonce))) throw new Error("Nonce not persisted");
      saved = {...saved, status: "built", rebuild_operations: [{operation_nonce: body.operation_nonce,
        revision_id: saved.revision_id, status: "built", artifact_id: "d".repeat(32)}],
        artifacts: [{artifact_id: "d".repeat(32), revision_id: saved.revision_id, kinds: ["output_docx"]}]};
    }
    return envelope(saved);
  }});
const statusText = () => walk(root).find((node) => node.className === "formatting-review-status")?.textContent;
const checkboxInput = (label) => walk(root).find((node) => node.tagName === "LABEL" && node.children[1]?.textContent === label).querySelector("input");
const pagePosts = () => calls.filter((row) => row.url.includes("/pages/"));
await prepareButton.fire("click"); await mounted.controller.prepare(true);
await findButton("Save page formatting").fire("click");
const firstWarning = statusText(), firstPagePosts = pagePosts().length;
await findButton("Save page formatting").fire("click");
const repeatedWarning = statusText(), repeatedPagePosts = pagePosts().length;
const spacing = walk(root).filter((node) => node.tagName === "LABEL"
  && node.children[1]?.textContent === "I want to preserve measured spaces between these columns")[1].querySelector("input");
spacing.checked = true; await spacing.fire("change");
const checksInvalidated = !checkboxInput("I reviewed the complete page image and its formatting").checked
  && !checkboxInput("I checked every source-to-translation text selection").checked;
await check("I reviewed the complete page image and its formatting");
await check("I checked every source-to-translation text selection");
await findButton("Save page formatting").fire("click");
const correctedAttemptStatus = statusText(); let recovery = null;
if (data.reject) {
  const failed = mounted.controller.snapshot(), beforeReadDiscard = mounted.controller.discardUnsaved();
  const locked = fieldControl("Page formatting reviewer").disabled;
  await findButton("Read current formatting review").fire("click");
  const afterRead = mounted.controller.snapshot(), beforeDiscard = calls.length;
  await findButton("Discard the unsaved request and continue editing").fire("click");
  recovery = {failed, beforeReadDiscard, locked, afterRead, discardRequests: calls.length - beforeDiscard,
    afterDiscard: mounted.controller.snapshot(), stillReviewed: checkboxInput("I reviewed the complete page image and its formatting").checked};
  reject = false; await findButton("Save page formatting").fire("click");
}
const afterPage = statusText();
await findButton("Add document group").fire("click");
await fill("Group 1 first page", "1"); await fill("Group 1 last page", "1");
await fill("Text separators inside reviewed table cells", "no", "SELECT", "change");
await fill("Vertical spacing between source regions", "no", "SELECT", "change");
await fill("Document formatting reviewer", "Operator"); await fill("Document review explanation", "All fictional pages checked");
await check("I reviewed every page, its text mappings and the document groups");
await findButton("Save document review").fire("click"); const afterDocument = statusText();
await fill("Formatting acceptance reviewer", "Operator");
await check("I accept these complete formatting decisions for this exact translation");
await findButton("Accept formatting revision").fire("click"); const afterSubmit = statusText();
await findButton("Build DOCX from this revision").fire("click"); const afterBuild = statusText();
const link = walk(root).find((node) => node.tagName === "A" && node.textContent === "Download this reviewed DOCX");
console.log(JSON.stringify({firstWarning, firstPagePosts, repeatedWarning, repeatedPagePosts, checksInvalidated, correctedAttemptStatus, recovery,
  statuses: [afterPage, afterDocument, afterSubmit, afterBuild], pagePosts: pagePosts(),
  documents: calls.filter((row) => row.url.endsWith("/document")), submits: calls.filter((row) => row.url.endsWith("/submit")),
  builds: calls.filter((row) => row.url.endsWith("/rebuild")), nonces, href: link?.href, unsafeWrites,
  final: mounted.controller.snapshot(), expectedServerMessage: core.formattingReviewMessage("browser_formatting_review_run_busy")}));
""", data={"reject": reject_corrected_save})
    warning = "When using measured column spacing, review and enter it for every table on this page."
    assert result["firstWarning"] == warning and result["firstPagePosts"] == 0
    assert result["repeatedWarning"] == warning and result["repeatedPagePosts"] == 0
    assert result["checksInvalidated"]
    assert all(status and warning not in status for status in result["statuses"])
    if reject_corrected_save:
        assert result["correctedAttemptStatus"] == result["expectedServerMessage"]
        recovery = result["recovery"]
        assert recovery["failed"]["errorCode"] == "browser_formatting_review_run_busy"
        assert recovery["failed"]["pendingKind"] == "page" and recovery["locked"]
        assert recovery["beforeReadDiscard"] is None
        assert recovery["afterRead"]["pendingKind"] == "page" and recovery["afterRead"]["canDiscardSave"]
        assert recovery["discardRequests"] == 0 and not recovery["afterDiscard"]["pendingKind"]
        assert recovery["afterDiscard"]["dirty"] and recovery["stillReviewed"]
    else:
        assert result["correctedAttemptStatus"] != warning and result["recovery"] is None
    assert len(result["pagePosts"]) == (2 if reject_corrected_save else 1)
    decisions = [row["body"]["decision"] for row in result["pagePosts"]]
    assert all(decision == decisions[0] for decision in decisions)
    assert decisions[0]["body"] == [
        {"column_widths": [34, 33, 33], "rows": [[[1], [2], [3]]], "column_gaps_px": [12, 12]},
        {"column_widths": [100], "rows": [[[4]]], "column_gaps_px": []},
    ]
    assert decisions[0]["full_page_review_completed"] and decisions[0]["source_target_mapping_reviewed"]
    assert len(result["documents"]) == len(result["submits"]) == len(result["builds"]) == result["nonces"] == 1
    assert result["builds"][0]["body"] == {"revision_id": "b" * 32, "operation_nonce": "c" * 32}
    assert "/" + "d" * 32 + "/output_docx?" in result["href"]
    assert result["final"]["verified"] and result["final"]["associated"] and not result["final"]["pendingKind"]
    assert result["unsafeWrites"] == 0
