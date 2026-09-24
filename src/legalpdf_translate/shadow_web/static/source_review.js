import { fetchJson } from "./api.js";

const BASE = "/api/translation/source-reviews";
const ID = /^[a-f0-9]{32}$/;
const clone = (value) => JSON.parse(JSON.stringify(value));
function frozenView(value) {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    Object.values(value).forEach(frozenView);
    Object.freeze(value);
  }
  return value;
}
const messages = {
  source_review_disabled: "Source review is unavailable in this app session.",
  source_review_ocr_disabled: "Local source review needs OCR enabled. Change the saved OCR setting explicitly, then prepare again.",
  source_review_local_baseline_unavailable: "A local OCR baseline is unavailable under the current settings. Source review will not call paid OCR.",
  source_review_retained_evidence_required: "Source review needs Keep intermediates enabled. Change that setting explicitly, then prepare again.",
  source_review_full_browser_source_required: "Choose a manually uploaded PDF with all browser-rendered pages for source review.",
  source_review_full_selection_required: "Source review currently requires the whole PDF. Change the page selection explicitly before preparing.",
  source_review_local_evidence_unavailable: "Local OCR could not retain the required text and word evidence for this document.",
  source_review_run_owner_conflict: "Settings changed after source review began. Prepare a new source review for the changed settings using a new upload or run.",
  source_review_saved_run_owner_unavailable: "This run already has saved work without a browser review owner. Choose a new upload or run.",
  browser_source_review_unavailable: "This review handle is unavailable. Browser review handles cannot be restored after a server restart.",
  source_review_independent_workspace: "Keep this tab for the existing review and its recovery details. To review another document, duplicate this tab, change workspace= in its address to a different name, and upload the document there. Keep mode= unchanged. This opens independent work and does not recover the existing run.",
  browser_source_review_operation_outcome_unknown: "The translation start outcome is unknown. Check the exact operation again; a replacement start will not be sent.",
  source_review_storage_unavailable: "Browser session recovery storage is unavailable. This attempt cannot send a translation request; retain the existing operation for recovery.",
  source_review_setup_changed: "The source or setup changed. This review cannot start a new translation with the changed setup.",
  source_review_recovery_only: "Recovery only after reload: check the existing review or exact translation operation. A new reviewed start needs the original setup in the original page session.",
  source_review_explicit_acceptance_required: "Confirm the whole source explicitly before submitting it.",
  source_review_pages_incomplete: "Save and complete every page review, including reading order, boundaries and any findings.",
  source_review_no_original_request: "The original request is unavailable. Read the review state before continuing; do not create a replacement translation start.",
  browser_source_review_save_failed: "The page was not saved. Check block coverage, text, regions, order and review fields, then read the current generation.",
  browser_source_review_submit_failed: "Source submission did not complete. Read its current state, then retry only the same explicit submission.",
  browser_source_review_prepare_failed: "Source preparation did not complete. Its outcome is uncertain; no automatic retry or claim reset was performed.",
};

export function sourceReviewMessage(code) {
  return messages[code] || "Source review could not complete this operation. Read the current state and check your explicit decisions.";
}

export function newSourceReviewId() {
  if (!globalThis.crypto?.getRandomValues) throw new Error("source_review_storage_unavailable");
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (n) => n.toString(16).padStart(2, "0")).join("");
}

function scopeOf(value) {
  const mode = value?.runtimeMode;
  const workspace = value?.workspaceId;
  if (!["live", "shadow"].includes(mode) || typeof workspace !== "string"
      || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,126}[A-Za-z0-9]$|^[A-Za-z0-9]$/.test(workspace)) {
    throw new Error("source_review_no_original_request");
  }
  return { runtimeMode: mode, workspaceId: workspace };
}

const scopeKey = (scope) => `${scope.runtimeMode}:${scope.workspaceId}`;
const storageKey = (scope) => `legalpdf:source-review:v1:${scopeKey(scope)}`;

function errorCode(error) {
  const code = error?.payload?.diagnostics?.error || error?.message;
  return typeof code === "string" && /^(source_review|browser_source_review)_[a-z_]+$/.test(code)
    ? code : "source_review_operation_failed";
}

export function pageReviewComplete(page) {
  const decision = page?.decision;
  return Boolean(decision && decision.full_page_review_completed === true
    && decision.reading_order_reviewed === true && ["start", "continuation"].includes(decision.boundary_decision)
    && String(decision.reviewer || "").trim() && String(decision.boundary_rationale || "").trim()
    && Array.isArray(decision.findings) && decision.findings.every((f) => f.status === "resolved"));
}

function sameJsonValue(left, right) {
  if (left === right) return true;
  if (left === null || right === null || typeof left !== "object" || typeof right !== "object") return false;
  if (Array.isArray(left) || Array.isArray(right)) {
    return Array.isArray(left) && Array.isArray(right) && left.length === right.length
      && left.every((value, index) => sameJsonValue(value, right[index]));
  }
  const keys = Object.keys(left).sort();
  const otherKeys = Object.keys(right).sort();
  return keys.length === otherKeys.length && keys.every((key, index) => key === otherKeys[index]
    && sameJsonValue(left[key], right[key]));
}

export function sourceDecisionsEqual(left, right) {
  if (!left || !right) return left === right;
  const { reviewer_kind: _leftKind, ...leftDecision } = left;
  const { reviewer_kind: _rightKind, ...rightDecision } = right;
  return sameJsonValue(leftDecision, rightDecision);
}

/** Local UI state is not review authority. The backend verifies every binding. */
export function createSourceReviewController({
  getScope, getSetup, manualReady, request = fetchJson, onChange = () => {}, onJob = () => {},
  storage = null, createNonce = newSourceReviewId,
} = {}) {
  let scope = scopeOf(getScope());
  let epoch = 0;
  let originalSetup = null;
  let uploadHandedOff = false; // UI cleanup only; never dispatch authority.
  let pending = null; // Private decision/request bytes stay in this page's memory only.
  const dirtyPages = new Set();
  let state;

  function reset() {
    state = { view: null, reviewId: "", revisionId: "", operationNonce: "", jobId: "",
      busy: false, errorCode: "", invalidated: false, recoveryOnly: false, dirty: false,
      pendingKind: "", pendingPageConflict: false, operationUnknown: false, operationAssociated: false, reviewVerified: false };
    originalSetup = null;
    uploadHandedOff = false;
    pending = null;
    dirtyPages.clear();
  }
  // Source views can be large. Share the immutable retained view; copy only
  // mutable controller metadata rather than all page evidence on every input.
  function snapshot() { return { ...state, scope: { ...scope } }; }
  function emit() { onChange(snapshot()); }
  function store() {
    if (!storage || !state.reviewId) throw new Error("source_review_storage_unavailable");
    storage.setItem(storageKey(scope), JSON.stringify({ version: 1, ...scope,
      reviewId: state.reviewId, revisionId: state.revisionId,
      operationNonce: state.operationNonce, jobId: state.jobId }));
  }
  function restore() {
    try {
      const raw = storage?.getItem(storageKey(scope));
      if (!raw || raw.length > 2048) return;
      const row = JSON.parse(raw);
      if (Object.keys(row).sort().join() !== "jobId,operationNonce,reviewId,revisionId,runtimeMode,version,workspaceId"
          || row.version !== 1 || row.runtimeMode !== scope.runtimeMode || row.workspaceId !== scope.workspaceId
          || !ID.test(row.reviewId) || ![row.revisionId, row.operationNonce].every((s) => s === "" || (typeof s === "string" && ID.test(s)))
          || (row.operationNonce && !row.revisionId) || typeof row.jobId !== "string" || row.jobId.length > 200) return;
      Object.assign(state, { reviewId: row.reviewId, revisionId: row.revisionId,
        operationNonce: row.operationNonce, jobId: row.jobId, recoveryOnly: true });
    } catch { /* Invalid browser metadata never restores source authority. */ }
  }
  function current(ticket) {
    return epoch === ticket.epoch && scopeKey(scope) === scopeKey(ticket.scope)
      && scopeKey(scopeOf(getScope())) === scopeKey(ticket.scope);
  }
  function checkSetup() {
    if (state.recoveryOnly || originalSetup === null) throw new Error("source_review_recovery_only");
    if (state.invalidated || !manualReady() || JSON.stringify(getSetup()) !== originalSetup) {
      throw new Error("source_review_setup_changed");
    }
  }
  function sync() {
    const actual = scopeOf(getScope());
    if (scopeKey(actual) !== scopeKey(scope)) {
      epoch += 1;
      scope = actual;
      reset();
      restore();
      emit();
    } else if (originalSetup !== null && !state.invalidated
        && ((!manualReady() && !uploadHandedOff) || JSON.stringify(getSetup()) !== originalSetup)) {
      epoch += 1;
      state.busy = false;
      state.invalidated = true;
      state.errorCode = "source_review_setup_changed";
      emit();
    }
  }
  async function perform(kind, action) {
    sync();
    if (state.busy) return snapshot();
    const ticket = { epoch, scope: { ...scope } };
    state.busy = true;
    state.errorCode = "";
    emit();
    try {
      await action(ticket);
    } catch (error) {
      if (current(ticket)) state.errorCode = errorCode(error);
    } finally {
      if (current(ticket)) {
        state.busy = false;
        emit();
      }
    }
    return snapshot();
  }
  async function send(ticket, route, body) {
    const payload = await request(route, ticket.scope, body === undefined ? {} : {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    sync();
    if (!current(ticket)) return null;
    return payload.normalized_payload || {};
  }
  function mergeView(view) {
    if (!view || view.review_id !== state.reviewId) throw new Error("source_review_no_original_request");
    state.view = frozenView({ ...state.view, ...clone(view) });
    const submission = view.submission;
    if (submission?.status === "completed" && ID.test(submission.revision_id)
        && view.revision_ids?.includes(submission.revision_id)) state.revisionId = submission.revision_id;
  }
  async function read() {
    return perform("read", async (ticket) => {
      if (!ID.test(state.reviewId)) throw new Error("source_review_no_original_request");
      state.reviewVerified = false;
      state.operationAssociated = false;
      const payload = await send(ticket, `${BASE}/${state.reviewId}`);
      if (!payload) return;
      const received = payload.source_review;
      mergeView(received);
      if (pending?.kind === "save" && state.view.generation === pending.body.expected_generation + 1) {
        const page = state.view.pages?.find((p) => p.page_number === pending.pageNumber);
        if (sourceDecisionsEqual(page?.decision, pending.body.decision)) {
          dirtyPages.delete(pending.pageNumber);
          pending = null;
          state.pendingKind = "";
          state.dirty = dirtyPages.size > 0;
        }
      }
      state.pendingPageConflict = Boolean(pending?.kind === "save"
        && Number.isInteger(state.view.generation) && state.view.generation > pending.body.expected_generation);
      if (state.operationNonce) {
        const matches = received.translation_operations?.filter((row) => row.operation_nonce === state.operationNonce) || [];
        if (matches.length > 1) throw new Error("source_review_no_original_request");
        const op = matches[0];
        if (op && op.revision_id !== state.revisionId) throw new Error("source_review_no_original_request");
        state.operationAssociated = Boolean(op);
        state.operationUnknown = !op || op.status !== "started";
        if (op?.status === "started" && typeof op.job_id === "string") state.jobId = op.job_id;
      }
      if (state.revisionId && !received.revision_ids?.includes(state.revisionId)) {
        throw new Error("source_review_no_original_request");
      }
      state.reviewVerified = true;
      store();
    });
  }
  async function savePage(pageNumber, decision) {
    return perform("save", async (ticket) => {
      checkSetup();
      if (!state.view || state.revisionId || state.view.submission || state.operationNonce
          || (pending && pending.kind !== "save")) throw new Error("source_review_no_original_request");
      const route = `${BASE}/${state.reviewId}/pages/${pageNumber}`;
      const body = { expected_generation: state.view.generation, decision: clone(decision) };
      if (pending && (pending.route !== route || !sameJsonValue(pending.body, body))) {
        throw new Error("source_review_no_original_request");
      }
      pending = { kind: "save", route, pageNumber, body };
      state.pendingKind = "save";
      const payload = await send(ticket, route, body);
      if (!payload) return;
      mergeView(payload.source_review);
      pending = null;
      state.pendingKind = "";
      state.pendingPageConflict = false;
      dirtyPages.delete(pageNumber);
      state.dirty = dirtyPages.size > 0;
    });
  }
  async function submit(reviewer, acceptSource) {
    return perform("submit", async (ticket) => {
      if (acceptSource !== true) throw new Error("source_review_explicit_acceptance_required");
      if (!state.view || state.dirty || !String(reviewer || "").trim()
          || state.operationNonce || (pending && pending.kind !== "submit")) throw new Error("source_review_pages_incomplete");
      const exact = state.view.submission;
      if (!exact) {
        checkSetup();
        if (!state.view.pages?.length || !state.view.pages.every(pageReviewComplete)) throw new Error("source_review_pages_incomplete");
      } else if (reviewer !== exact.reviewer) throw new Error("source_review_no_original_request");
      const route = `${BASE}/${state.reviewId}/submit`;
      const body = { expected_generation: exact?.generation ?? state.view.generation, reviewer, accept_source: true };
      if (pending && !sameJsonValue(pending.body, body)) throw new Error("source_review_no_original_request");
      pending = { kind: "submit", route, body };
      state.pendingKind = "submit";
      const payload = await send(ticket, route, body);
      if (!payload) return;
      const result = payload.source_review;
      if (!ID.test(result?.revision_id) || result.reviewer_kind !== "operator_review") throw new Error("source_review_no_original_request");
      mergeView(result);
      state.revisionId = result.revision_id;
      state.view = frozenView({ ...state.view, submitted: true });
      state.reviewVerified = true;
      pending = null;
      state.pendingKind = "";
      store();
    });
  }
  async function translate() {
    return perform("translate", async (ticket) => {
      if (!ID.test(state.revisionId) || !ID.test(state.reviewId) || state.dirty || pending) {
        throw new Error("source_review_no_original_request");
      }
      if (!state.operationNonce) {
        checkSetup();
        if (!state.reviewVerified) throw new Error("source_review_no_original_request");
        const nonce = createNonce();
        if (!ID.test(nonce)) throw new Error("source_review_storage_unavailable");
        state.operationNonce = nonce;
      }
      if (!state.reviewVerified) throw new Error("source_review_no_original_request");
      if (!state.operationAssociated) {
        // Browser storage proves no dispatch. A reload can only replay a nonce
        // that the backend has already associated with this exact revision.
        if (state.recoveryOnly) throw new Error("browser_source_review_operation_outcome_unknown");
        checkSetup();
      }
      // Persist before every send. Failure cannot generate a replacement nonce.
      try { store(); } catch { throw new Error("source_review_storage_unavailable"); }
      const payload = await send(ticket, `${BASE}/${state.reviewId}/translate`,
        { revision_id: state.revisionId, operation_nonce: state.operationNonce });
      if (!payload) return;
      const job = payload.job;
      if (!job?.job_id || job.runtime_mode !== scope.runtimeMode || job.workspace_id !== scope.workspaceId) {
        throw new Error("source_review_no_original_request");
      }
      state.jobId = job.job_id;
      state.operationUnknown = false;
      state.operationAssociated = true;
      uploadHandedOff = true;
      store();
      onJob(job);
    });
  }
  async function prepare() {
    return perform("prepare", async (ticket) => {
      if (!manualReady() || state.reviewId || state.operationNonce) throw new Error("source_review_no_original_request");
      const form = clone(getSetup());
      originalSetup = JSON.stringify(form);
      const payload = await send(ticket, `${BASE}/prepare`, { form_values: form });
      if (!payload) return;
      const result = payload.source_review;
      if (result?.status === "declined") {
        state.view = frozenView(clone(result));
        originalSetup = null;
        return;
      }
      if (!ID.test(result?.review_id) || result.reviewer_kind !== "operator_review") throw new Error("source_review_no_original_request");
      state.reviewId = result.review_id;
      state.view = frozenView(clone(result));
      state.reviewVerified = true;
      store();
    });
  }
  function markDirty(pageNumber) {
    if (state.view && !state.revisionId && !state.view.submission) {
      dirtyPages.add(pageNumber);
      state.dirty = true;
    }
  }
  function discardLocalReview() {
    // Explicit local UI reset only. Backend artifacts/claims and paid-operation
    // records are never deleted, reassigned or replayed.
    if (state.busy || state.operationNonce || pending) return false;
    try { storage?.removeItem(storageKey(scope)); } catch { return false; }
    epoch += 1;
    reset();
    emit();
    return true;
  }
  function discardConflictedPage() {
    if (state.busy || pending?.kind !== "save" || !state.pendingPageConflict) return null;
    const pageNumber = pending.pageNumber;
    pending = null;
    state.pendingKind = "";
    state.pendingPageConflict = false;
    dirtyPages.delete(pageNumber);
    state.dirty = dirtyPages.size > 0;
    state.errorCode = "";
    return pageNumber;
  }
  reset();
  restore();
  return { snapshot, sync, prepare, read, savePage, submit, translate, markDirty, discardLocalReview, discardConflictedPage };
}
