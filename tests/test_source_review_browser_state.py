"""Source review UI probes; real public flow uses only local OCR/SDK boundaries.

Node probes use the existing browser ESM runner. They are authored for the
parent's browser-test pass, outside any offline harness that forbids subprocesses.
No subprocess permission or boundary is relaxed by these tests.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from .browser_esm_probe import run_browser_esm_json_probe


MODULES = {"__CONTROLLER__": "source_review.js", "__UI__": "source_review_ui.js"}
PRELUDE = r"""
const core = await import(__CONTROLLER__);
const ui = await import(__UI__);
if (!globalThis.crypto) globalThis.crypto = (await import("node:crypto")).webcrypto;
const copy = (v) => JSON.parse(JSON.stringify(v));
const scope = {runtimeMode: "shadow", workspaceId: "workspace-1"};
const memory = () => { const data = new Map(); return {
  getItem: (k) => data.get(k) || null, setItem: (k, v) => data.set(k, v), removeItem: (k) => data.delete(k),
  values: () => [...data.values()], data,
}; };
const envelope = (source_review) => ({normalized_payload: {source_review: copy(source_review)}});
"""


def probe(script: str, *, data=None):
    return run_browser_esm_json_probe(PRELUDE + "\nconst data = " + json.dumps(data, ensure_ascii=True) + ";\n" + script, MODULES)


DOM = r"""
let unsafeWrites = 0;
const doc = { createElement: (tag) => make(tag) };
function make(tag) {
  const handlers = new Map();
  let ownText = "";
  const node = { tagName: tag.toUpperCase(), ownerDocument: doc, children: [], style: {}, attributes: {},
    value: "", checked: false, disabled: false, hidden: false, complete: true,
    append(...items) { this.children.push(...items); },
    replaceChildren(...items) { ownText = ""; this.children = items; },
    setAttribute(key, value) { this.attributes[key] = value; },
    addEventListener(type, handler) { if (!handlers.has(type)) handlers.set(type, []); handlers.get(type).push(handler); },
    querySelector(tag) { return walk(this).find((n) => n !== this && n.tagName === tag.toUpperCase()) || null; },
    getBoundingClientRect() { return {left: 10, top: 20, width: 100, height: 150}; },
    async fire(type, extra={}) {
      if (this.disabled) throw new Error("Attempted disabled control: " + this.textContent);
      for (const fn of handlers.get(type) || []) await fn({target: this, button: 0, preventDefault() {}, ...extra});
    },
  };
  Object.defineProperty(node, "textContent", {get: () => ownText + node.children.map((n) => n.textContent || "").join(""),
    set: (value) => { ownText = String(value); node.children = []; }});
  Object.defineProperty(node, "innerHTML", {set: () => { unsafeWrites += 1; throw new Error("Unsafe HTML write"); }});
  return node;
}
function walk(node) { return [node, ...node.children.flatMap(walk)]; }
function findButton(label) { const node = walk(root).find((n) => n.tagName === "BUTTON" && n.textContent === label); if (!node) throw new Error("Missing button: " + label); return node; }
function fieldControl(label, tag="INPUT") {
  const wrapper = walk(root).find((n) => n.tagName === "LABEL" && n.children[0]?.textContent === label);
  if (!wrapper) throw new Error("Missing field: " + label);
  return wrapper.querySelector(tag);
}
async function fill(label, value, tag="INPUT", event="input") { const node = fieldControl(label, tag); node.value = value; await node.fire(event); }
async function check(label, value=true) {
  const wrapper = walk(root).find((n) => n.tagName === "LABEL" && n.children[1]?.textContent === label);
  if (!wrapper) throw new Error("Missing checkbox: " + label);
  const node = wrapper.querySelector("input"); node.checked = value; await node.fire("change");
}
const root = make("section");
const prepareButton = make("button");
"""


def test_controller_pins_paid_nonce_before_send_and_reload_only_recovers_exact_operation():
    result = probe(r"""
const storage = memory();
const calls = [];
let setup = {source_path: "fictional/private.pdf", target_lang: "AR", page_breaks: false};
let generation = 2;
const decision = {...ui.blankSourcePageDecision(), full_page_review_completed: true,
  reading_order_reviewed: true, boundary_decision: "start", boundary_rationale: "Explicit boundary", reviewer: "Operator"};
const draft = {status: "draft", review_id: "a".repeat(32), reviewer_kind: "operator_review", generation,
  pages: [{page_number: 1, decision}], notice_codes: []};
const revision = {status: "submitted", review_id: draft.review_id, revision_id: "b".repeat(32), reviewer_kind: "operator_review", generation};
const job = {job_id: "tx-owned", runtime_mode: "shadow", workspace_id: "workspace-1", status: "queued"};
let first = true, nonceCount = 0;
const request = async (url, owner, options) => {
  const body = options.body ? JSON.parse(options.body) : null;
  calls.push({url, owner: copy(owner), body});
  if (url.endsWith("/prepare")) return envelope(draft);
  if (url.endsWith("/submit")) return envelope(revision);
  if (url.endsWith("/translate")) {
    if (!storage.values().some((v) => v.includes(body.operation_nonce))) throw new Error("Nonce not stored first");
    if (first) { first = false; throw new Error("Fictional private transport failure"); }
    return {normalized_payload: {job}};
  }
  return envelope({review_id: draft.review_id, status: "submitted", revision_ids: [revision.revision_id],
    translation_operations: [{operation_nonce: "c".repeat(32), revision_id: revision.revision_id, job_id: job.job_id, status: "started"}]});
};
const options = {getScope: () => scope, getSetup: () => setup, manualReady: () => true, request, storage,
  createNonce: () => { nonceCount += 1; return "c".repeat(32); }};
const controller = core.createSourceReviewController(options);
await controller.prepare();
await controller.submit("Operator", false);
const refused = calls.filter((r) => r.url.endsWith("/submit")).length === 0;
await controller.submit("Operator", true);
await controller.translate();
const failed = controller.snapshot();
const restored = core.createSourceReviewController({...options, createNonce: () => { throw new Error("No replacement nonce"); }});
const beforeRecoveryRead = calls.length; await restored.translate();
const unverifiedBlocked = calls.length === beforeRecoveryRead;
await restored.read();
await restored.translate();
await restored.translate();
const paid = calls.filter((r) => r.url.endsWith("/translate"));
const clean = core.createSourceReviewController({...options, storage: memory()});
await clean.prepare(); await clean.submit("Operator", true);
const noNonceStore = memory();
noNonceStore.setItem("legalpdf:source-review:v1:shadow:workspace-1", JSON.stringify({version: 1, ...scope,
  reviewId: draft.review_id, revisionId: revision.revision_id, operationNonce: "", jobId: ""}));
const reloadNoNonce = core.createSourceReviewController({...options, storage: noNonceStore});
const before = calls.length; await reloadNoNonce.translate();
console.log(JSON.stringify({refused, nonceCount, unverifiedBlocked, failedCode: failed.errorCode, paid,
  restored: restored.snapshot(), noNonceNewRequest: calls.length !== before, reloadCode: reloadNoNonce.snapshot().errorCode,
  persisted: storage.values(), cleanHasNonce: clean.snapshot().operationNonce}));
""")
    assert result["refused"] and result["nonceCount"] == 1
    assert result["unverifiedBlocked"]
    assert result["failedCode"] == "source_review_operation_failed"
    assert len(result["paid"]) == 3
    assert all(row["body"] == {"revision_id": "b" * 32, "operation_nonce": "c" * 32} for row in result["paid"])
    assert result["restored"]["recoveryOnly"] and result["restored"]["jobId"] == "tx-owned"
    assert result["restored"]["operationAssociated"]
    assert not result["noNonceNewRequest"] and result["reloadCode"] == "source_review_recovery_only"
    assert not result["cleanHasNonce"]
    assert all("private.pdf" not in value and "Operator" not in value for value in result["persisted"])


def test_restored_nonce_requires_fresh_exact_server_association_before_recovery_post():
    result = probe(DOM + r"""
const revisionId = "b".repeat(32), nonce = "c".repeat(32), reviewId = "a".repeat(32);
const key = "legalpdf:source-review:v1:shadow:workspace-1";
const stored = () => { const storage = memory(); storage.setItem(key, JSON.stringify({version: 1, ...scope,
  reviewId, revisionId, operationNonce: nonce, jobId: ""})); return storage; };
const exact = {operation_nonce: nonce, revision_id: revisionId, status: "started", job_id: "tx-owned"};
const cases = [[], [{...exact, operation_nonce: "d".repeat(32)}],
  [{...exact, revision_id: "e".repeat(32)}], [exact, exact]];
const failures = [];
for (const operations of cases) {
  let posts = 0;
  const controller = core.createSourceReviewController({getScope: () => scope, getSetup: () => ({}),
    manualReady: () => true, storage: stored(), createNonce: () => { throw new Error("No new nonce"); },
    request: async (url, owner, options) => {
      if (options.method === "POST") { posts += 1; throw new Error("Unexpected recovery dispatch"); }
      return envelope({review_id: reviewId, status: "submitted", revision_ids: [revisionId], translation_operations: operations});
    }});
  await controller.read(); const afterRead = controller.snapshot(); await controller.translate();
  failures.push({posts, afterRead, afterTranslate: controller.snapshot()});
}
// The visible control must agree with the callable controller gate.
let serverHasOperation = false, posts = 0;
const mounted = ui.mountSourceReview({root, prepareButton, getScope: () => scope, getSetup: () => ({}),
  manualReady: () => true, storage: stored(), request: async (url, owner, options) => {
    if (options.method === "POST") { posts += 1; return {normalized_payload: {job: {
      job_id: "tx-owned", runtime_mode: "shadow", workspace_id: "workspace-1"}}}; }
    // Omit the operations field entirely after a previously associated read:
    // the merged display view must not become fresh server evidence.
    return envelope({review_id: reviewId, status: "submitted", revision_ids: [revisionId],
      ...(serverHasOperation ? {translation_operations: [exact]} : {})});
  }});
await mounted.controller.read();
const unassociatedDisabled = findButton("Recover this exact translation start").disabled;
serverHasOperation = true; await mounted.controller.read();
const associatedEnabled = !findButton("Recover this exact translation start").disabled;
await findButton("Recover this exact translation start").fire("click");
serverHasOperation = false; await mounted.controller.read();
const freshReadDisabled = findButton("Recover this exact translation start").disabled;
await mounted.controller.translate();
console.log(JSON.stringify({failures, unassociatedDisabled, associatedEnabled, freshReadDisabled, posts,
  final: mounted.controller.snapshot()}));
""")
    assert all(row["posts"] == 0 for row in result["failures"])
    assert all(not row["afterRead"]["operationAssociated"] for row in result["failures"])
    for row in result["failures"][:2]:
        assert row["afterRead"]["reviewVerified"] and row["afterRead"]["operationUnknown"]
        assert row["afterTranslate"]["errorCode"] == "browser_source_review_operation_outcome_unknown"
    for row in result["failures"][2:]:
        assert not row["afterRead"]["reviewVerified"]
        assert row["afterRead"]["errorCode"] == "source_review_no_original_request"
    assert result["unassociatedDisabled"] and result["associatedEnabled"] and result["freshReadDisabled"]
    assert result["posts"] == 1 and not result["final"]["operationAssociated"]


def test_confirmed_job_upload_handoff_does_not_hide_setup_drift_or_authorize_unassociated_dispatch():
    result = probe(r"""
const storage = memory(); let owner = {...scope}, ready = true;
let setup = {source_path: "fictional/private.pdf", target_lang: "EN", page_breaks: false};
const decision = {...ui.blankSourcePageDecision(), full_page_review_completed: true, reading_order_reviewed: true,
  boundary_decision: "start", boundary_rationale: "Explicit first page", reviewer: "Operator"};
const draft = {status: "draft", review_id: "a".repeat(32), reviewer_kind: "operator_review", generation: 2,
  pages: [{page_number: 1, decision}]};
const revision = {...draft, status: "submitted", revision_id: "b".repeat(32)};
const job = {job_id: "tx-owned", runtime_mode: "shadow", workspace_id: "workspace-1", status: "completed"};
const operation = {operation_nonce: "c".repeat(32), revision_id: revision.revision_id, status: "started", job_id: job.job_id};
const serverView = (operations) => ({review_id: draft.review_id, status: "submitted", revision_ids: [revision.revision_id], translation_operations: operations});
let readMode = "normal", resolveRead, sends = 0;
const request = async (url) => {
  if (url.endsWith("/prepare")) return envelope(draft);
  if (url.endsWith("/submit")) return envelope(revision);
  if (url.endsWith("/translate")) { sends += 1; return {normalized_payload: {job}}; }
  if (readMode === "pending") return new Promise((resolve) => { resolveRead = resolve; });
  if (readMode === "failed") throw new Error("Fictional failed read");
  return envelope(serverView(readMode === "missing" ? [] : readMode === "mismatched"
    ? [{...operation, revision_id: "d".repeat(32)}] : [operation]));
};
let c;
c = core.createSourceReviewController({getScope: () => owner, getSetup: () => setup, manualReady: () => ready,
  storage, request, createNonce: () => "c".repeat(32), onJob: () => {
    // Normal renderTranslationJob clears temporary uploaded-file state.
    ready = false; c.sync();
  }});
await c.prepare(); await c.submit("Operator", true); await c.translate(); const handedOff = c.snapshot();
readMode = "pending"; const reading = c.read(); c.sync(); const duringRead = c.snapshot();
await c.translate(); const sendsWhileReading = sends;
resolveRead(envelope(serverView([operation]))); await reading; await c.translate(); const recovered = c.snapshot();
readMode = "failed"; await c.read(); const failedRead = c.snapshot(); await c.translate();
readMode = "mismatched"; await c.read(); const mismatchedRead = c.snapshot(); await c.translate();
readMode = "missing"; await c.read(); await c.translate(); const unassociated = c.snapshot();
const sendsAfterUnassociated = sends;
setup = {...setup, page_breaks: true}; c.sync(); const changedSetup = c.snapshot();
owner = {...scope, workspaceId: "workspace-2"}; c.sync(); const changedOwner = c.snapshot();
// A browser-stored job and nonce do not restore the UI-only handoff marker.
const restored = core.createSourceReviewController({getScope: () => scope, getSetup: () => setup,
  manualReady: () => false, storage, request, createNonce: () => { throw new Error("No replacement nonce"); }});
await restored.read(); await restored.translate(); const restoredState = restored.snapshot();
// Losing the manual source before any confirmed job remains a real drift.
let beforeReady = true, beforeSends = 0;
const before = core.createSourceReviewController({getScope: () => scope, getSetup: () => setup,
  manualReady: () => beforeReady, storage: memory(), createNonce: () => "f".repeat(32), request: async (url) => {
    if (url.endsWith("/prepare")) return envelope(draft);
    if (url.endsWith("/submit")) return envelope(revision);
    beforeSends += 1; return {normalized_payload: {job}};
  }});
await before.prepare(); await before.submit("Operator", true); beforeReady = false; before.sync(); await before.translate();
console.log(JSON.stringify({handedOff, duringRead, sendsWhileReading, recovered, failedRead, mismatchedRead,
  unassociated, sendsAfterUnassociated, changedSetup, changedOwner, restoredState, before: before.snapshot(), beforeSends,
  sends, stored: storage.values()}));
""")
    assert result["handedOff"]["operationAssociated"] and result["handedOff"]["jobId"] == "tx-owned"
    assert not result["handedOff"]["invalidated"] and not result["handedOff"]["errorCode"]
    assert result["duringRead"]["busy"] and not result["duringRead"]["reviewVerified"]
    assert not result["duringRead"]["operationAssociated"] and not result["duringRead"]["invalidated"]
    assert result["sendsWhileReading"] == 1 and not result["recovered"]["invalidated"]
    assert not result["failedRead"]["operationAssociated"] and not result["failedRead"]["reviewVerified"]
    assert not result["mismatchedRead"]["operationAssociated"] and not result["mismatchedRead"]["reviewVerified"]
    assert result["unassociated"]["errorCode"] == "source_review_setup_changed"
    assert result["sendsAfterUnassociated"] == result["sends"] == 2
    assert result["changedSetup"]["invalidated"] and result["changedSetup"]["errorCode"] == "source_review_setup_changed"
    assert result["changedOwner"]["scope"]["workspaceId"] == "workspace-2" and not result["changedOwner"]["jobId"]
    assert result["restoredState"]["errorCode"] == "browser_source_review_operation_outcome_unknown"
    assert result["beforeSends"] == 0 and result["before"]["invalidated"]
    assert all("uploadHandedOff" not in raw for raw in result["stored"])


def test_decision_semantics_ignore_object_order_but_preserve_array_order_values_and_editor_refresh():
    result = probe(DOM + r"""
const reorder = (value) => Array.isArray(value) ? value.map(reorder)
  : value && typeof value === "object" ? Object.fromEntries(Object.keys(value).sort().map((key) => [key, reorder(value[key])])) : value;
const decision = {...ui.blankSourcePageDecision(), reviewer: "Original operator", boundary_decision: "start", boundary_rationale: "Reviewed",
  full_page_review_completed: true, reading_order_reviewed: true,
  actions: [{id: "a1", kind: "retain", baseline_block_ids: ["b1", "b2"], after_text: "ملف 😀\nArtigo 42",
    region_px: [10,10,100,50], rationale: "Compared"}], reading_order: ["a1"]};
const page = {page_number: 1, image_size_px: [200,300], baseline_text: "ملف 😀\nArtigo 42",
  baseline_blocks: [{id: "b1", text: "ملف 😀"}, {id: "b2", text: "Artigo 42"}],
  word_evidence: {words: []}, decision};
const draft = {status: "draft", review_id: "a".repeat(32), reviewer_kind: "operator_review", generation: 1, pages: [page]};
const reordered = reorder({...decision, reviewer_kind: "operator_review"});
const reversedBlocks = copy(reordered); reversedBlocks.actions[0].baseline_block_ids.reverse();
const changedText = copy(reordered); changedText.actions[0].after_text += " ";
const changedPrimitive = copy(reordered); changedPrimitive.full_page_review_completed = 1;
const changedKeys = copy(reordered); changedKeys.unexpected = null;
const equal = core.sourceDecisionsEqual(decision, reordered);
const negatives = [reversedBlocks, changedText, changedPrimitive, changedKeys].map((v) => core.sourceDecisionsEqual(decision, v));
let saved, posts = 0;
const mounted = ui.mountSourceReview({root, prepareButton, getScope: () => scope,
  getSetup: () => ({source_path: "one.pdf"}), manualReady: () => true, storage: memory(),
  request: async (url, owner, options) => {
    if (url.endsWith("/prepare")) return envelope(draft);
    if (url.includes("/pages/")) {
      posts += 1;
      const body = JSON.parse(options.body);
      saved = {...draft, generation: 2, pages: [{...page, decision: reorder({...body.decision, reviewer_kind: "operator_review"})}]};
      throw new Error("Saved successfully; response lost");
    }
    return envelope(saved);
  }});
await prepareButton.fire("click");
await fill("Page reviewer", "Explicit operator");
await check("I reviewed the complete page image for missing or invented text");
await check("I checked the reading order shown above");
await findButton("Save page decisions").fire("click");
const lost = mounted.controller.snapshot();
await findButton("Read current review / recover response").fire("click");
const recovered = mounted.controller.snapshot();
// A clean editor must adopt a later saved generation too. A key-order false
// mismatch would retain the old dirty editor despite controller recovery.
saved = {...saved, generation: 3, pages: [{...page, decision: {...saved.pages[0].decision, reviewer: "Later explicit operator"}}]};
await findButton("Read current review / recover response").fire("click");
console.log(JSON.stringify({equal, negatives, lost, recovered, posts,
  displayedReviewer: fieldControl("Page reviewer").value, unsafeWrites}));
""")
    assert result["equal"] and not any(result["negatives"])
    assert result["lost"]["dirty"] and result["lost"]["pendingKind"] == "save"
    assert not result["recovered"]["dirty"] and not result["recovered"]["pendingKind"]
    assert not result["recovered"]["pendingPageConflict"] and result["posts"] == 1
    assert result["displayedReviewer"] == "Later explicit operator" and result["unsafeWrites"] == 0


def test_controller_drops_stale_scope_response_and_blocks_changed_setup_or_pending_submission():
    result = probe(r"""
let owner = {...scope}, setup = {source_path: "one.pdf", page_breaks: false};
let resolve;
const delayed = new Promise((done) => { resolve = done; });
const draft = {review_id: "a".repeat(32), reviewer_kind: "operator_review", generation: 1, status: "draft", pages: []};
const controller = core.createSourceReviewController({getScope: () => owner, getSetup: () => setup,
  manualReady: () => true, storage: memory(), request: async () => delayed});
const preparing = controller.prepare();
owner = {...scope, workspaceId: "another"}; controller.sync(); resolve(envelope(draft)); await preparing;
const scopeState = controller.snapshot();
owner = {...scope};
const calls = [];
const complete = {...ui.blankSourcePageDecision(), full_page_review_completed: true, reading_order_reviewed: true,
  boundary_decision: "start", boundary_rationale: "Checked", reviewer: "Operator"};
const reviewed = {...draft, pages: [{page_number: 1, decision: complete}]};
const c = core.createSourceReviewController({getScope: () => owner, getSetup: () => setup, manualReady: () => true, storage: memory(),
  request: async (url, state, options) => { calls.push(url); return envelope(reviewed); }});
await c.prepare(); setup = {...setup, page_breaks: true}; c.sync(); await c.submit("Operator", true);
const changed = c.snapshot();
const pendingCalls = [];
let read = false;
const p = core.createSourceReviewController({getScope: () => owner, getSetup: () => setup, manualReady: () => true, storage: memory(),
  request: async (url, state, options) => {
    pendingCalls.push({url, body: options.body ? JSON.parse(options.body) : null});
    if (url.endsWith("/prepare")) return envelope(reviewed);
    if (url.endsWith("/submit")) throw new Error("Transport lost");
    return envelope({...reviewed, submitted: false, submission: {status: "pending", revision_id: "b".repeat(32), generation: 1, reviewer: "Exact operator"}});
  }});
await p.prepare(); await p.submit("Exact operator", true); await p.read();
await p.submit("Changed operator", true); await p.submit("Exact operator", false); await p.submit("Exact operator", true);
console.log(JSON.stringify({scopeState, changed, calls, submits: pendingCalls.filter((c) => c.url.endsWith("/submit")), pending: p.snapshot()}));
""")
    assert result["scopeState"]["scope"]["workspaceId"] == "another"
    assert result["scopeState"]["view"] is None and not result["scopeState"]["reviewId"]
    assert result["changed"]["invalidated"] and result["changed"]["errorCode"] == "source_review_setup_changed"
    assert len(result["calls"]) == 1
    assert len(result["submits"]) == 2 and result["submits"][0]["body"] == result["submits"][1]["body"]
    assert result["pending"]["pendingKind"] == "submit"


def test_controller_keeps_other_page_dirty_and_storage_failure_prevents_dispatch():
    result = probe(r"""
const decision = {...ui.blankSourcePageDecision(), full_page_review_completed: true, reading_order_reviewed: true,
  boundary_decision: "start", boundary_rationale: "Checked", reviewer: "Operator"};
let draft = {review_id: "a".repeat(32), reviewer_kind: "operator_review", generation: 1, status: "draft",
  pages: [{page_number: 1, decision}, {page_number: 2, decision}]};
const calls = [];
const storage = memory();
const c = core.createSourceReviewController({getScope: () => scope, getSetup: () => ({source_path: "private.pdf"}),
  manualReady: () => true, storage, createNonce: () => "c".repeat(32), request: async (url, scope, options) => {
    calls.push(url);
    if (url.includes("/pages/")) draft = {...draft, generation: draft.generation + 1};
    if (url.endsWith("/submit")) return envelope({review_id: draft.review_id, revision_id: "b".repeat(32), reviewer_kind: "operator_review"});
    return envelope(draft);
  }});
await c.prepare(); c.markDirty(1); c.markDirty(2); await c.savePage(1, decision);
await c.submit("Operator", true); const dirty = c.snapshot();
await c.savePage(2, decision); await c.submit("Operator", true);
storage.setItem = () => { throw new Error("Quota exceeded"); };
await c.translate(); const first = c.snapshot(); await c.translate();
console.log(JSON.stringify({dirty, first, final: c.snapshot(), calls}));
""")
    assert result["dirty"]["dirty"] and result["dirty"]["errorCode"] == "source_review_pages_incomplete"
    assert not any(path.endswith("/translate") for path in result["calls"])
    assert result["first"]["operationNonce"] == result["final"]["operationNonce"] == "c" * 32
    assert result["final"]["errorCode"] == "source_review_storage_unavailable"


def _ui_operator_probe(draft, *, setup, accepted=None):
    return probe(DOM + r"""
const calls = [];
const storage = memory();
const mounted = ui.mountSourceReview({root, prepareButton, getScope: () => scope,
  getSetup: () => data.setup, manualReady: () => true, storage, createNonce: () => "c".repeat(32),
  request: async (url, owner, options) => {
    const body = options.body ? JSON.parse(options.body) : null;
    calls.push({url, scope: copy(owner), body});
    if (url.endsWith("/prepare")) return envelope(data.draft);
    if (url.endsWith("/submit") && data.accepted) return envelope(data.accepted);
    throw new Error("source_review_probe_capture"); // Capture wire input before Python sends it to the real service.
  }});
await prepareButton.fire("click");
const initial = {checks: walk(root).filter((n) => n.tagName === "INPUT" && n.type === "checkbox").map((n) => n.checked),
  actions: mounted.controller.snapshot().view.pages[0].decision, images: walk(root).filter((n) => n.tagName === "IMG").map((n) => n.src),
  actionAccessibleName: fieldControl("Action", "SELECT").attributes["aria-label"],
  fieldNames: walk(root).filter((n) => n.className === "source-review-field").map((n) => ({label: n.children[0].textContent,
    name: (n.querySelector("input") || n.querySelector("select") || n.querySelector("textarea")).attributes["aria-label"]}))};
if (!data.draft.pages[0].decision) {
  for (const [index, block] of data.draft.pages[0].baseline_blocks.entries()) await check(`${index + 1}. ${block.text}`);
  await fill("Action", "retain", "SELECT", "change");
  await findButton("Use selected word bounds as this action region").fire("click");
  await fill("Why is this action correct?", "Compared every selected line with the displayed fictional image.");
  await findButton("Add this explicit action").fire("click");
  await fill("Page reviewer", "Fictional UI operator");
  await fill("Page boundary", "start", "SELECT", "change");
  await fill("Boundary explanation", "Explicit first-page boundary review.");
  await check("I reviewed the complete page image for missing or invented text");
  await check("I checked the reading order shown above");
  await findButton("Save page decisions").fire("click");
} else {
  await fill("Whole-source reviewer", "Fictional UI operator");
  await check("I accept the complete reviewed source for this translation");
  await findButton("Accept reviewed source").fire("click");
  if (data.accepted) await findButton("Translate reviewed source").fire("click");
}
console.log(JSON.stringify({calls, initial, unsafeWrites, text: root.textContent,
  tags: walk(root).map((n) => n.tagName), persisted: storage.values()}));
""", data={"draft": draft, "setup": setup, "accepted": accepted})


def test_actual_dom_operator_actions_to_public_service_context_and_workflow(tmp_path, monkeypatch):
    # Keep native subprocess calls blocked inside OCR, without modifying the
    # shared stdlib subprocess module used by the existing Node probe runner.
    from legalpdf_translate import ocr_engine as ocr, workflow as workflow_module
    from tests.test_shadow_web_source_review_api import api_case, upload, form, view, HEADERS, PREFIX

    def forbidden(*_args, **_kwargs):
        raise AssertionError("UI source review must not call native extraction, real provider auth or paid OCR")

    monkeypatch.delenv("LEGALPDF_TRANSLATION_PROTOCOL", raising=False)
    monkeypatch.setattr(workflow_module, "load_gui_settings", lambda: {})
    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    for name in ("run_translation_auth_test", "extract_ordered_page_text", "resolve_openai_key_with_source"):
        monkeypatch.setattr(workflow_module, name, forbidden)
    monkeypatch.setattr(ocr, "subprocess", SimpleNamespace(run=forbidden))
    monkeypatch.setattr(ocr, "build_ocr_engine", forbidden)
    monkeypatch.setattr(ocr, "resolve_ocr_api_key", forbidden)
    monkeypatch.setattr(ocr, "which", lambda _: "synthetic-tesseract")
    monkeypatch.setattr(ocr, "_text_quality_score", lambda _: 0.99)
    c = api_case(tmp_path, monkeypatch)
    saved_settings = c.settings.read_bytes()
    with TestClient(c.app) as client:
        source = upload(client)
        setup = form(c, source)
        draft = view(client.post(PREFIX + "/prepare", headers=HEADERS, json={"form_values": setup}))
        assert not c.clients and not c.sdk_calls
        first = _ui_operator_probe(draft, setup=setup)
        assert first["initial"]["actions"] is None and not any(first["initial"]["checks"])
        assert first["unsafeWrites"] == 0
        image_response = client.get(first["initial"]["images"][0])
        assert image_response.status_code == 200 and image_response.content.startswith(b"\x89PNG\r\n\x1a\n")
        assert image_response.headers["cache-control"] == "no-store"
        wire = first["calls"][-1]
        assert wire["url"] == f"{PREFIX}/{draft['review_id']}/pages/1"
        assert wire["scope"] == {"runtimeMode": "shadow", "workspaceId": "workspace-1"}
        assert set(wire["body"]) == {"expected_generation", "decision"}
        saved = view(client.post(wire["url"], headers=HEADERS, json=wire["body"]))
        # Read the genuine canonical on-disk decision, whose object key order
        # differs from the typed DOM request. No review or commit is fabricated.
        canonical_read = view(client.get(f"{PREFIX}/{draft['review_id']}", headers=HEADERS))
        recovered = probe(r"""
const calls = [];
const c = core.createSourceReviewController({getScope: () => scope, getSetup: () => data.setup,
  manualReady: () => true, storage: memory(), request: async (url, owner, options) => {
    calls.push(url);
    if (url.endsWith("/prepare")) return envelope(data.draft);
    if (url.includes("/pages/")) throw new Error("The real page save completed; only its response was lost");
    return envelope(data.canonical);
  }});
await c.prepare(); c.markDirty(1); await c.savePage(1, data.decision);
const lost = c.snapshot(); await c.read();
const persisted = data.canonical.pages[0].decision;
const {reviewer_kind, ...withoutDecoration} = persisted;
console.log(JSON.stringify({lost, recovered: c.snapshot(), calls,
  semanticMatch: core.sourceDecisionsEqual(data.decision, persisted),
  originalStringMatch: JSON.stringify(data.decision) === JSON.stringify(withoutDecoration)}));
""", data={"setup": setup, "draft": draft, "canonical": canonical_read, "decision": wire["body"]["decision"]})
        assert recovered["lost"]["pendingKind"] == "save" and recovered["lost"]["dirty"]
        assert recovered["semanticMatch"] and not recovered["originalStringMatch"]
        assert not recovered["recovered"]["pendingKind"] and not recovered["recovered"]["dirty"]
        assert not recovered["recovered"]["pendingPageConflict"] and len(recovered["calls"]) == 3
        second = _ui_operator_probe(saved, setup=setup)
        wire = second["calls"][-1]
        assert wire["url"].endswith("/submit") and wire["body"]["accept_source"] is True
        accepted = view(client.post(wire["url"], headers=HEADERS, json=wire["body"]))
        assert accepted["reviewer_kind"] == "operator_review" and not c.sdk_calls and not c.clients
        third = _ui_operator_probe(saved, setup=setup, accepted=accepted)
        wire = third["calls"][-1]
        assert wire["body"] == {"revision_id": accepted["revision_id"], "operation_nonce": "c" * 32}
        job_response = client.post(wire["url"], headers=HEADERS, json=wire["body"])
        assert job_response.status_code == 200, job_response.text
        job = job_response.json()["normalized_payload"]["job"]
        repeated = client.post(wire["url"], headers=HEADERS, json=wire["body"])
        assert repeated.json()["normalized_payload"]["job"]["job_id"] == job["job_id"]
        assert len(c.queued) == 1
        c.queued.pop(0)()
        completed = c.jobs.get_job(job["job_id"])
    assert completed["status"] == "completed", completed["diagnostics"]
    assert len(c.local_calls) == len(c.clients) == len(c.sdk_calls) == 1
    assert c.settings.read_bytes() == saved_settings
    run = Path(completed["artifacts"]["run_dir"])
    checkpoint = json.loads((run / "run_state.json").read_bytes())
    assert checkpoint["settings"]["page_breaks"] is False
    assert checkpoint["settings"]["ordinary_source_review"]["revision_id"] == accepted["revision_id"]
    assert checkpoint["pages"]["1"]["structured_commit"]
    assert (run / "pages/page_0001.commit.json").is_file()
    source_structure = json.loads((run / "pages/page_0001.source_structure.json").read_bytes())
    assert source_structure["metadata"]["reviewed_source"]["review_kind"] == "operator_review"
    journals = list((run / "accounting").glob("*/dispatch_accounting.json"))
    assert len(journals) == 1
    events = json.loads(journals[0].read_bytes())["events"]
    assert len([event for event in events if event["event"] == "begin"]) == 1
    assert len([event for event in events if event["event"] == "finish"]) == 1
    assert not (run / "acceptance_private").exists()


def test_safe_dom_keeps_unicode_text_and_uses_explicit_word_region_adoption():
    text = '<img src=x onerror="alert(1)"> ملف 😀 121/26 & Artigo 42'
    page = {"page_number": 1, "image_size_px": [200, 300], "baseline_text": text,
        "baseline_blocks": [{"id": "b1", "text": text}], "word_evidence": {"words": [{"block_id": "b1", "bbox_px": [10, 10, 190, 30]}]},
        "decision": None}
    result = _ui_operator_probe({"status": "draft", "review_id": "a" * 32, "reviewer_kind": "operator_review",
        "generation": 1, "pages": [page]}, setup={"source_path": "private.pdf", "page_breaks": False})
    decision = result["calls"][-1]["body"]["decision"]
    assert decision["actions"][0]["after_text"] == text
    assert result["unsafeWrites"] == 0 and result["tags"].count("IMG") == 1 and "SCRIPT" not in result["tags"]
    assert result["initial"]["actionAccessibleName"] == "Action"
    assert result["initial"]["fieldNames"] and all(row["label"] == row["name"] for row in result["initial"]["fieldNames"])
    assert text in result["text"]
    assert all("private.pdf" not in row and text not in row for row in result["persisted"])
    scaled = probe(r"""
const page = data;
const a = ui.sourceActionFromInput(page, {id: "a1", kind: "retain", baseline_block_ids: ["b1"],
  region_px: ui.selectedWordRegion(page, ["b1"]), rationale: "Explicit comparison"});
const decision = {...ui.blankSourcePageDecision(), actions: [a], reading_order: [a.id], reviewer: "Operator", boundary_rationale: "Checked"};
console.log(JSON.stringify({point: ui.imagePoint(60, 95, {left:10, top:20, width:100, height:150}, [200,300]),
  region: a.region_px, beforeChecks: [decision.full_page_review_completed, decision.reading_order_reviewed],
  problem: ui.sourceDecisionProblem(page, decision)}));
""", data=page)
    assert scaled == {"point": [100, 150], "region": [10, 10, 190, 30], "beforeChecks": [False, False], "problem": ""}


def test_editing_saved_action_clears_visible_checks_and_conflicted_save_has_explicit_recovery():
    result = probe(DOM + r"""
const decision = {...ui.blankSourcePageDecision(), reviewer: "Previous operator", boundary_decision: "start", boundary_rationale: "Reviewed",
  full_page_review_completed: true, reading_order_reviewed: true,
  actions: [{id: "a1", kind: "retain", baseline_block_ids: ["b1"], after_text: "Fictional text",
    region_px: [10,10,100,30], rationale: "Compared"}], reading_order: ["a1"]};
const page = {page_number: 1, image_size_px: [200,300], baseline_text: "Fictional text",
  baseline_blocks: [{id: "b1", text: "Fictional text"}], word_evidence: {words: [{block_id: "b1", bbox_px: [10,10,100,30]}]}, decision};
const draft = {status: "draft", review_id: "a".repeat(32), reviewer_kind: "operator_review", generation: 1, pages: [page]};
const mounted = ui.mountSourceReview({root, prepareButton, getScope: () => scope, getSetup: () => ({source_path: "one.pdf"}),
  manualReady: () => true, storage: memory(), request: async () => envelope(draft)});
await prepareButton.fire("click");
await findButton("Edit action").fire("click");
const checks = walk(root).filter((n) => n.tagName === "LABEL" && n.children[1]?.textContent?.startsWith("I "))
  .map((n) => n.querySelector("input").checked);
const dirty = mounted.controller.snapshot().dirty;
await findButton("Save page decisions").fire("click");
const unfinished = root.textContent.includes("Finish or cancel the unfinished action");

let requestCount = 0;
const c = core.createSourceReviewController({getScope: () => scope, getSetup: () => ({}), manualReady: () => true, storage: memory(),
  request: async (url) => {
    requestCount += 1;
    if (url.endsWith("/prepare")) return envelope(draft);
    if (url.includes("/pages/")) throw new Error("Transport lost");
    return envelope({...draft, generation: 3, pages: [{...page, decision: {...decision, reviewer: "Other explicit operator"}}]});
  }});
await c.prepare(); c.markDirty(1); await c.savePage(1, decision); await c.read();
const before = c.snapshot(); const count = requestCount; const discardedPage = c.discardConflictedPage();
console.log(JSON.stringify({checks, dirty, unfinished, unsafeWrites, before, discardedPage, after: c.snapshot(), discardRequests: requestCount - count}));
""")
    assert not any(result["checks"]) and result["dirty"] and result["unfinished"]
    assert result["unsafeWrites"] == 0
    assert result["before"]["pendingPageConflict"] and result["before"]["pendingKind"] == "save"
    assert result["discardedPage"] == 1 and result["discardRequests"] == 0
    assert not result["after"]["pendingKind"] and not result["after"]["dirty"]


def test_busy_dom_does_not_request_page_images_and_failed_read_restores_review():
    result = probe(DOM + r"""
// An IMG src assignment is the browser request boundary. Keep every assignment,
// including images detached again by a later render during the same operation.
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
const decision = {...ui.blankSourcePageDecision(), reviewer: "Fictional operator",
  boundary_decision: "start", boundary_rationale: "Reviewed complete page",
  full_page_review_completed: true, reading_order_reviewed: true,
  actions: [{id: "a1", kind: "retain", baseline_block_ids: ["b1"], after_text: "Fictional text",
    region_px: [10,10,100,30], rationale: "Compared"}], reading_order: ["a1"]};
const page = {page_number: 1, image_size_px: [200,300], baseline_text: "Fictional text",
  baseline_blocks: [{id: "b1", text: "Fictional text"}], word_evidence: {words: []}, decision};
const draft = {status: "draft", review_id: "a".repeat(32), reviewer_kind: "operator_review",
  generation: 1, pages: [page]};
const storage = memory(), requests = [];
let rejectRead, rejectTranslate;
const mounted = ui.mountSourceReview({root, prepareButton, getScope: () => scope,
  getSetup: () => ({source_path: "fictional.pdf"}), manualReady: () => true, storage,
  createNonce: () => "c".repeat(32), request: async (url, owner, options) => {
    requests.push(url);
    if (url.endsWith("/prepare")) return envelope(draft);
    if (url.endsWith("/submit")) return envelope({...draft, revision_id: "b".repeat(32)});
    if (url.endsWith("/translate")) return new Promise((resolve, reject) => { rejectTranslate = reject; });
    return new Promise((resolve, reject) => { rejectRead = reject; });
  }});
const imageCount = () => walk(root).filter((node) => node.tagName === "IMG").length;
await prepareButton.fire("click");
const initial = {requests: imageRequests.length, images: imageCount()};
const reading = findButton("Read current review / recover response").fire("click");
const readingState = {requests: imageRequests.length, images: imageCount(), busy: mounted.controller.snapshot().busy,
  readDisabled: findButton("Read current review / recover response").disabled,
  footerDisabled: fieldControl("Whole-source reviewer").disabled};
rejectRead(new Error("Fictional read failed before any translation dispatch"));
await reading;
const readFailed = {requests: imageRequests.length, images: imageCount(), state: mounted.controller.snapshot(),
  readDisabled: findButton("Read current review / recover response").disabled};
await fill("Whole-source reviewer", "Fictional operator");
await check("I accept the complete reviewed source for this translation");
await findButton("Accept reviewed source").fire("click");
const beforeTranslate = imageRequests.length;
const translating = findButton("Translate reviewed source").fire("click");
const translatingState = {requests: imageRequests.length, images: imageCount(), state: mounted.controller.snapshot(),
  startDisabled: findButton("Translate reviewed source").disabled,
  nonceStored: storage.values().some((value) => value.includes("c".repeat(32)))};
rejectTranslate(new Error("Fictional translation response lost"));
await translating;
const translateFailed = {requests: imageRequests.length, images: imageCount(), state: mounted.controller.snapshot(),
  recoveryDisabled: findButton("Recover this exact translation start").disabled,
  readDisabled: findButton("Read current review / recover response").disabled};
console.log(JSON.stringify({initial, readingState, readFailed, beforeTranslate, translatingState, translateFailed,
  translateRequests: requests.filter((url) => url.endsWith("/translate")).length, unsafeWrites}));
""")
    assert result["initial"] == {"requests": 1, "images": 1}
    reading = result["readingState"]
    assert reading == {"requests": 1, "images": 0, "busy": True,
                       "readDisabled": True, "footerDisabled": True}
    restored = result["readFailed"]
    assert restored["requests"] == 2 and restored["images"] == 1
    assert not restored["state"]["busy"] and not restored["state"]["operationNonce"]
    assert restored["state"]["errorCode"] == "source_review_operation_failed"
    assert not restored["readDisabled"]
    translating = result["translatingState"]
    assert translating["requests"] == result["beforeTranslate"] and translating["images"] == 0
    assert translating["state"]["busy"] and translating["startDisabled"] and translating["nonceStored"]
    failed = result["translateFailed"]
    assert failed["requests"] == result["beforeTranslate"] and failed["images"] == 0
    assert failed["state"]["operationNonce"] == translating["state"]["operationNonce"] == "c" * 32
    assert not failed["state"]["busy"] and not failed["recoveryDisabled"] and not failed["readDisabled"]
    assert result["translateRequests"] == 1 and result["unsafeWrites"] == 0


def test_ordinary_translate_contract_and_new_panel_are_separate_static_hooks():
    root = Path(__file__).resolve().parents[1] / "src/legalpdf_translate/shadow_web"
    translation = (root / "static/translation.js").read_text(encoding="utf-8")
    ordinary = translation.split("async function handleTranslate() {", 1)[1].split("async function handleResume", 1)[0]
    assert '"/api/translation/jobs/translate"' in ordinary
    assert "JSON.stringify({ form_values: formValues })" in ordinary
    assert "source_review" not in ordinary and "revision_id" not in ordinary
    template = (root / "templates/index.html").read_text(encoding="utf-8")
    assert 'id="translation-source-review-panel" hidden' in template
    assert 'id="translation-source-review-prepare" disabled' in template
    ui = (root / "static/source_review_ui.js").read_text(encoding="utf-8")
    assert "innerHTML" not in ui and "insertAdjacentHTML" not in ui
    assert "server restart cannot restore" in ui
