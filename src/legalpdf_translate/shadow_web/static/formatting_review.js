import { fetchJson } from "./api.js";

const ID = /^[a-f0-9]{32}$/;
const clone = (value) => JSON.parse(JSON.stringify(value));
function freeze(value) {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    Object.values(value).forEach(freeze); Object.freeze(value);
  }
  return value;
}
export function formattingValuesEqual(left, right) {
  if (left === right) return true;
  if (left === null || right === null || typeof left !== "object" || typeof right !== "object") return false;
  if (Array.isArray(left) || Array.isArray(right)) return Array.isArray(left) && Array.isArray(right)
    && left.length === right.length && left.every((value, index) => formattingValuesEqual(value, right[index]));
  const keys = Object.keys(left).sort(), other = Object.keys(right).sort();
  return keys.length === other.length && keys.every((key, index) => key === other[index] && formattingValuesEqual(left[key], right[key]));
}
export function formattingReviewMessage(code) {
  const messages = {
    formatting_review_explicit_choice_required: "Choose whether to use the saved page breaks or create a page-matched derivative.",
    formatting_review_review_required: "Save every page and the document review, then explicitly accept the formatting.",
    formatting_review_pending_request: "An earlier response is uncertain. Read the review, then recover only that same request.",
    formatting_review_stale_generation: "The saved review changed. Read it before deciding which local changes to keep.",
    formatting_review_unknown_build: "The build outcome is unknown. Read this exact operation; a replacement build will not be sent.",
    formatting_review_storage_unavailable: "Browser recovery storage is unavailable. No build request was sent.",
    formatting_review_unverified: "Read this review from the server before continuing.",
    formatting_review_owner_changed: "The selected job or workspace changed. This review belongs to its original job.",
    formatting_review_run_busy: "This run is busy. Wait for its current operation, then read the review again.",
    browser_formatting_review_unavailable: "This browser review handle is unavailable. A server restart cannot restore it here.",
    reviewed_profile_requires_page_breaks: "This saved run has no page breaks. Choose a separate page-matched derivative explicitly to review this layout.",
    reviewed_profile_requires_bidi_stripping: "This formatting profile needs bidi controls removed. The saved setting is preserved, so this run cannot use the profile.",
    reviewed_profile_unsupported_selection: "Formatting review currently needs a completed whole-document translation.",
    reviewed_profile_unsupported_protocol: "This run does not contain the required reviewed source and structured translation commits.",
    reviewed_profile_unsupported_source_reviewer: "This feature requires an explicitly operator-reviewed source.",
    reviewed_profile_unsupported_source_provenance: "This source does not contain the supported browser image and reviewed source evidence.",
    reviewed_profile_stale_edited_target: "The saved translation text changed. These mappings are stale; prepare and review new mappings for the edited translation.",
    reviewed_profile_stale_review: "The source or translation bindings changed. This formatting revision cannot be reused.",
  };
  return messages[code] || "Formatting review could not complete this operation. Check complete source and target coverage, whole characters and legal references, regions and fragment ownership, then read the current saved review.";
}
function nonce() {
  if (!globalThis.crypto?.getRandomValues) throw new Error("formatting_review_storage_unavailable");
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (n) => n.toString(16).padStart(2, "0")).join("");
}
function ownerOf(scope, job) {
  if (!["live", "shadow"].includes(scope?.runtimeMode) || typeof scope.workspaceId !== "string"
      || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,126}[A-Za-z0-9]$|^[A-Za-z0-9]$/.test(scope.workspaceId)
      || !job?.job_id || typeof job.job_id !== "string" || job.job_id.length > 200
      || job.runtime_mode !== scope.runtimeMode || job.workspace_id !== scope.workspaceId) return null;
  return {runtimeMode: scope.runtimeMode, workspaceId: scope.workspaceId, jobId: job.job_id};
}
const keyOf = (owner) => owner ? JSON.stringify(owner) : "";
const storageKey = (owner) => `legalpdf:formatting-review:v1:${encodeURIComponent(keyOf(owner))}`;
const routeOf = (owner) => `/api/translation/jobs/${encodeURIComponent(owner.jobId)}/formatting-reviews`;
export function formattingPageComplete(page) {
  return page?.decision?.full_page_review_completed === true && page.decision.source_target_mapping_reviewed === true;
}
export function createFormattingReviewController({getScope, getJob, request = fetchJson, storage = null,
  onChange = () => {}, createNonce = nonce} = {}) {
  let owner = ownerOf(getScope(), getJob()), epoch = 0, pending = null, state;
  const dirtyPages = new Set();
  function reset() {
    state = {view: null, reviewId: "", revisionId: "", operationNonce: "", artifactId: "", busy: false,
      errorCode: "", verified: false, restored: false, associated: false, pendingKind: "", conflict: false,
      dirty: false, documentDirty: false};
    pending = null; dirtyPages.clear();
  }
  const snapshot = () => ({...state, owner: owner ? {...owner} : null});
  const emit = () => onChange(snapshot());
  function persist() {
    if (!storage || !owner) throw new Error("formatting_review_storage_unavailable");
    storage.setItem(storageKey(owner), JSON.stringify({version: 1, ...owner, reviewId: state.reviewId,
      revisionId: state.revisionId, operationNonce: state.operationNonce, artifactId: state.artifactId}));
  }
  function restore() {
    if (!owner) return;
    try {
      const raw = storage?.getItem(storageKey(owner));
      if (!raw || raw.length > 2048) return;
      const row = JSON.parse(raw);
      if (Object.keys(row).sort().join() !== "artifactId,jobId,operationNonce,reviewId,revisionId,runtimeMode,version,workspaceId"
          || row.version !== 1 || row.jobId !== owner.jobId || row.runtimeMode !== owner.runtimeMode || row.workspaceId !== owner.workspaceId
          || !ID.test(row.reviewId) || ![row.revisionId, row.operationNonce, row.artifactId].every((v) => v === "" || typeof v === "string" && ID.test(v))
          || row.operationNonce && !row.revisionId || row.artifactId && !row.operationNonce) return;
      Object.assign(state, {reviewId: row.reviewId, revisionId: row.revisionId, operationNonce: row.operationNonce,
        artifactId: row.artifactId, restored: true});
    } catch { /* Browser metadata is never review authority. */ }
  }
  function sync() {
    const next = ownerOf(getScope(), getJob());
    if (keyOf(next) !== keyOf(owner)) { epoch += 1; owner = next; reset(); restore(); emit(); }
  }
  const current = (ticket) => epoch === ticket.epoch && keyOf(owner) === keyOf(ticket.owner)
    && keyOf(ownerOf(getScope(), getJob())) === keyOf(ticket.owner);
  async function perform(action) {
    sync(); if (state.busy) return snapshot();
    const ticket = {epoch, owner: owner ? {...owner} : null};
    state.busy = true; state.errorCode = ""; emit();
    try {
      if (!owner) throw new Error("formatting_review_owner_changed");
      await action(ticket);
    } catch (error) {
      const code = error?.payload?.diagnostics?.error || error?.message;
      if (current(ticket)) state.errorCode = typeof code === "string" && /^(formatting_review|browser_formatting_review|reviewed_profile)_[a-z_]+$/.test(code)
        ? code : "formatting_review_operation_failed";
    } finally { if (current(ticket)) { state.busy = false; emit(); } }
    return snapshot();
  }
  async function send(ticket, suffix, body) {
    const response = await request(routeOf(ticket.owner) + suffix, ticket.owner,
      body === undefined ? {} : {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
    sync(); if (!current(ticket)) return null;
    const view = response.normalized_payload?.formatting_review;
    if (!view || view.job_id !== owner.jobId || (state.reviewId && view.review_id !== state.reviewId)) {
      throw new Error("formatting_review_owner_changed");
    }
    return view;
  }
  function merge(view) {
    if (view.status !== "declined" && view.reviewer_kind !== "operator_review") throw new Error("formatting_review_unverified");
    state.view = freeze({...state.view, ...clone(view)});
  }
  function editable() {
    if (!state.verified || !ID.test(state.reviewId)) throw new Error("formatting_review_unverified");
    if (state.revisionId || state.operationNonce || state.view?.status === "submission_pending") throw new Error("formatting_review_pending_request");
  }
  async function prepare(choice) {
    return perform(async (ticket) => {
      if (typeof choice !== "boolean") throw new Error("formatting_review_explicit_choice_required");
      if (state.reviewId || getJob()?.status !== "completed") throw new Error("formatting_review_review_required");
      const view = await send(ticket, "/prepare", {page_matched_derivative: choice}); if (!view) return;
      if (view.status === "declined") { merge(view); return; }
      if (!ID.test(view.review_id) || view.page_matched_derivative !== choice) throw new Error("formatting_review_unverified");
      state.reviewId = view.review_id; merge(view); state.verified = true; persist();
    });
  }
  async function read() {
    return perform(async (ticket) => {
      if (!ID.test(state.reviewId)) throw new Error("formatting_review_unverified");
      state.verified = false; state.associated = false;
      const view = await send(ticket, `/${state.reviewId}`); if (!view) return;
      merge(view); if (view.status === "declined") return;
      if (pending && ["page", "document"].includes(pending.kind) && view.generation === pending.body.expected_generation + 1) {
        const saved = pending.kind === "page" ? view.pages?.find((p) => p.page_number === pending.pageNumber)?.decision : view.document_decision;
        if (formattingValuesEqual(saved, pending.body.decision)) {
          if (pending.kind === "page") dirtyPages.delete(pending.pageNumber); else state.documentDirty = false;
          pending = null; state.pendingKind = ""; state.dirty = dirtyPages.size > 0 || state.documentDirty;
        }
      }
      state.conflict = Boolean(pending && ["page", "document"].includes(pending.kind) && view.generation > pending.body.expected_generation);
      if (view.revision_id) {
        if (!ID.test(view.revision_id) || state.revisionId && state.revisionId !== view.revision_id) throw new Error("formatting_review_unverified");
        // A read proves an existing revision, not which reviewer submitted it.
        // Retain an uncertain original submit until an explicit same-request
        // retry lets the service verify its exact reviewer and generation.
        if (pending?.kind !== "submit") state.revisionId = view.revision_id;
      } else if (state.revisionId) throw new Error("formatting_review_unverified");
      if (state.operationNonce) {
        const matches = view.rebuild_operations?.filter((op) => op.operation_nonce === state.operationNonce) || [];
        if (matches.length > 1 || matches.length === 1 && matches[0].revision_id !== state.revisionId) throw new Error("formatting_review_unverified");
        state.associated = matches.length === 1;
        const artifact = view.artifacts?.find((row) => row.artifact_id === matches[0]?.artifact_id && row.revision_id === state.revisionId);
        state.artifactId = artifact && ID.test(artifact.artifact_id) ? artifact.artifact_id : "";
      }
      state.verified = true; persist();
    });
  }
  async function save(kind, decision, pageNumber = null) {
    return perform(async (ticket) => {
      editable();
      const suffix = `/${state.reviewId}/` + (kind === "page" ? `pages/${pageNumber}` : "document");
      const body = {expected_generation: state.view.generation, decision: clone(decision)};
      if (pending && (pending.kind !== kind || pending.suffix !== suffix || !formattingValuesEqual(pending.body, body))) throw new Error("formatting_review_pending_request");
      pending = {kind, suffix, pageNumber, body}; state.pendingKind = kind;
      const view = await send(ticket, suffix, body); if (!view) return;
      merge(view); if (view.status === "declined") return;
      if (kind === "page") dirtyPages.delete(pageNumber); else state.documentDirty = false;
      state.dirty = dirtyPages.size > 0 || state.documentDirty; pending = null; state.pendingKind = ""; state.conflict = false;
    });
  }
  async function submit(reviewer, accepted) {
    return perform(async (ticket) => {
      if (!state.verified || accepted !== true || typeof reviewer !== "string" || !reviewer.trim() || state.dirty || state.operationNonce
          || !state.view?.pages?.length || !state.view.pages.every(formattingPageComplete) || state.view.document_decision?.all_pages_reviewed !== true) {
        throw new Error("formatting_review_review_required");
      }
      const body = {expected_generation: pending?.kind === "submit" ? pending.body.expected_generation : state.view.generation,
        reviewer, accept_formatting: true};
      if (state.view.status === "submission_pending" && pending?.kind !== "submit") throw new Error("formatting_review_pending_request");
      if (pending && (pending.kind !== "submit" || !formattingValuesEqual(pending.body, body))) throw new Error("formatting_review_pending_request");
      pending = {kind: "submit", body}; state.pendingKind = "submit";
      const view = await send(ticket, `/${state.reviewId}/submit`, body); if (!view) return;
      merge(view); if (view.status === "declined") return;
      if (!ID.test(view.revision_id) || state.revisionId && state.revisionId !== view.revision_id) throw new Error("formatting_review_unverified");
      state.revisionId = view.revision_id; pending = null; state.pendingKind = ""; persist();
    });
  }
  async function inspect() {
    return perform(async (ticket) => {
      if (!state.verified || !ID.test(state.revisionId)) throw new Error("formatting_review_unverified");
      state.verified = false;
      const view = await send(ticket, `/${state.reviewId}/revisions/${state.revisionId}`); if (!view) return;
      if (view.status !== "declined" && view.revision_id !== state.revisionId) throw new Error("formatting_review_unverified");
      merge(view);
      if (view.status !== "declined") state.verified = true;
    });
  }
  async function rebuild() {
    return perform(async (ticket) => {
      if (!state.verified || !ID.test(state.revisionId) || state.dirty || pending) throw new Error("formatting_review_unverified");
      if (state.restored && !state.associated) throw new Error("formatting_review_unknown_build");
      if (!state.operationNonce) { const value = createNonce(); if (!ID.test(value)) throw new Error("formatting_review_storage_unavailable"); state.operationNonce = value; }
      try { persist(); } catch { throw new Error("formatting_review_storage_unavailable"); }
      state.verified = false;
      const view = await send(ticket, `/${state.reviewId}/rebuild`, {revision_id: state.revisionId, operation_nonce: state.operationNonce});
      if (!view) return;
      if (view.revision_id !== state.revisionId) throw new Error("formatting_review_unverified");
      merge(view);
      const operations = view.rebuild_operations?.filter((row) => row.operation_nonce === state.operationNonce) || [];
      if (operations.length !== 1 || operations[0].revision_id !== state.revisionId) throw new Error("formatting_review_unverified");
      state.associated = true;
      // Join this operation to its artifact; other builds are never selected.
      const artifact = view.artifacts?.find((row) => row.artifact_id === operations[0].artifact_id
        && row.revision_id === state.revisionId && ID.test(row.artifact_id));
      if (view.status === "built" && !artifact) throw new Error("formatting_review_unverified");
      state.artifactId = artifact?.artifact_id || ""; state.verified = true; persist();
    });
  }
  function markDirty(pageNumber = null) {
    if (!state.verified || state.revisionId || state.view?.status === "submission_pending") return;
    if (pageNumber === null) state.documentDirty = true; else dirtyPages.add(pageNumber);
    state.dirty = true;
  }
  function discardConflict() {
    if (state.busy || !state.conflict || !pending) return null;
    const result = {kind: pending.kind, pageNumber: pending.pageNumber};
    if (pending.kind === "page") dirtyPages.delete(pending.pageNumber); else state.documentDirty = false;
    pending = null; state.pendingKind = ""; state.conflict = false; state.dirty = dirtyPages.size > 0 || state.documentDirty;
    return result;
  }
  function imageUrl(pageNumber) {
    return owner && state.verified && ID.test(state.reviewId) && Number.isInteger(pageNumber)
      ? routeOf(owner) + `/${state.reviewId}/pages/${pageNumber}/image?mode=${owner.runtimeMode}&workspace=${encodeURIComponent(owner.workspaceId)}` : "";
  }
  function artifactUrl(kind = "output_docx") {
    const descriptor = state.view?.artifacts?.find((row) => row.artifact_id === state.artifactId && row.revision_id === state.revisionId && row.kinds?.includes(kind));
    return state.verified && owner && descriptor && ID.test(state.artifactId)
      ? routeOf(owner) + `/${state.reviewId}/artifacts/${state.artifactId}/${kind}?mode=${owner.runtimeMode}&workspace=${encodeURIComponent(owner.workspaceId)}` : "";
  }
  reset(); restore();
  return {snapshot, sync, prepare, read, savePage: (number, decision) => save("page", decision, number),
    saveDocument: (decision) => save("document", decision), submit, inspect, rebuild, markDirty, discardConflict, imageUrl, artifactUrl};
}
