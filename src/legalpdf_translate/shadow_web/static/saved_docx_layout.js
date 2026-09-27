import { fetchJson } from "./api.js";

const PREFIX = "/api/saved-docx-layout";
const copy = (value) => value == null ? value : JSON.parse(JSON.stringify(value));
const ownerKey = (owner) => `${owner.runtimeMode}:${owner.workspaceId}`;
const pointerKey = (owner) => `legalpdf:saved-docx-layout:v1:${ownerKey(owner)}`;
const safeId = (value) => typeof value === "string" && /^[A-Za-z0-9_-]{1,100}$/.test(value);
const canonical = (value) => JSON.stringify(value, (_key, item) => item && typeof item === "object" && !Array.isArray(item)
  ? Object.fromEntries(Object.keys(item).sort().map((key) => [key, item[key]])) : item);

export function savedLayoutUrl(path, owner) {
  const params = new URLSearchParams({ mode: owner.runtimeMode, workspace_id: owner.workspaceId });
  return `${PREFIX}${path}?${params}`;
}

/** Owns only this independent local review. Browser persistence contains pointers, never document text. */
export function createSavedDocxLayoutController({ getScope, request = fetchJson,
  storage = globalThis.localStorage, createNonce = () => crypto.randomUUID().replaceAll("-", ""), onChange = () => {} }) {
  let owner, epoch = 0, state, pendingPayload = null;
  function emit() { onChange(snapshot()); }
  function persist() {
    try { storage?.setItem(pointerKey(owner), JSON.stringify({ reviewId: state.reviewId, pending: state.pending })); }
    catch { /* The server's review list remains the recovery authority. */ }
  }
  function sync() {
    const next = { runtimeMode: getScope().runtimeMode, workspaceId: getScope().workspaceId };
    if (owner && ownerKey(owner) === ownerKey(next)) return false;
    owner = next; epoch += 1; pendingPayload = null;
    let pointer = {};
    try { pointer = JSON.parse(storage?.getItem(pointerKey(owner)) || "{}"); } catch { /* Ignore invalid pointer. */ }
    state = { owner, reviewId: safeId(pointer.reviewId) ? pointer.reviewId : "", pending: null,
      view: null, decisions: null, reviews: [], capabilities: null, busy: false, dirty: false,
      verified: false, conflict: false, editBaseGeneration: null, canAbandonBuild: false, errorCode: "", restored: true };
    const p = pointer.pending;
    if (p && ["import", "save", "build"].includes(p.kind) && safeId(p.nonce)
      && Number.isSafeInteger(p.generation) && p.generation >= 0) state.pending = p;
    emit(); return true;
  }
  function snapshot() { return { ...copy(state), pendingSavePayloadAvailable: pendingPayload != null }; }
  function fail(code) { state.errorCode = code; emit(); return null; }
  function accept(view, { replace = true } = {}) {
    if (!view || !safeId(view.review_id) || !Number.isSafeInteger(view.generation)) throw new Error("invalid_response");
    if (state.reviewId && view.review_id !== state.reviewId) throw new Error("invalid_response");
    state.reviewId = view.review_id; state.view = copy(view); state.verified = true;
    if (replace) { state.decisions = copy(view.decisions); state.dirty = false; state.editBaseGeneration = null; }
    persist();
  }
  async function run(operation) {
    sync(); if (state.busy) return null;
    const token = epoch; const scope = copy(owner); state.busy = true; state.errorCode = ""; emit();
    const call = async (path, options = {}) => {
      const result = await request(savedLayoutUrl(path, scope), scope, { cache: "no-store", ...options });
      if (token !== epoch || ownerKey(scope) !== ownerKey(getScope())) { sync(); throw new Error("stale_scope"); }
      const value = result?.normalized_payload?.saved_docx_layout;
      if (value == null) throw new Error("invalid_response");
      return value;
    };
    try { return await operation(call); }
    catch (error) {
      if (token === epoch) {
        const code = error?.payload?.diagnostics?.code || error?.payload?.diagnostics?.error || error?.code;
        state.errorCode = typeof code === "string" && /^[a-z0-9_]{1,100}$/.test(code) ? code : "saved_layout_operation_failed";
        state.conflict = error?.status === 409 || /conflict/.test(state.errorCode);
        if (state.pending?.kind === "save" && [400, 422].includes(error?.status)) clearPending();
        else if (state.pending) { state.verified = false; state.canAbandonBuild = false; }
      }
      return null;
    } finally { if (token === epoch) { state.busy = false; emit(); } }
  }
  const json = (body) => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  function reviewPath(tail = "") { return `/reviews/${encodeURIComponent(state.reviewId)}${tail}`; }
  function clearPending() { state.pending = null; pendingPayload = null; persist(); }
  function associatedBuild() {
    if (!state.verified || state.pending?.kind !== "build") return null;
    const matches = (state.view?.builds || []).filter((item) => item.operation_nonce === state.pending.nonce
      && item.generation === state.pending.generation);
    return matches.length === 1 ? matches[0] : null;
  }
  function edit(decisions, { reviewOnly = false } = {}) {
    sync(); if (!state.verified || state.busy || state.pending || state.conflict) return false;
    if (!state.dirty) state.editBaseGeneration = state.view.generation;
    state.decisions = copy(decisions);
    if (!reviewOnly) { state.decisions.review.document_reviewed = false; state.decisions.review.pages_reviewed = []; }
    state.dirty = true; emit(); return true;
  }
  async function initialize() {
    return run(async (call) => {
      state.capabilities = await call("/capabilities");
      const result = await call("/reviews"); state.reviews = Array.isArray(result) ? result : result.reviews || [];
      if (state.pending?.kind === "import") {
        const matches = state.reviews.filter((item) => item.import_nonce === state.pending.nonce && safeId(item.review_id));
        if (matches.length === 1) {
          const recovered = await call(`/reviews/${encodeURIComponent(matches[0].review_id)}`);
          if (recovered.import_nonce !== state.pending.nonce) throw new Error("invalid_response");
          state.reviewId = ""; accept(recovered); clearPending(); state.conflict = false;
        }
      }
    });
  }
  async function open(reviewId) {
    sync(); if (!safeId(reviewId) || state.busy || state.dirty || state.pending) return fail("saved_layout_pending_changes");
    state.reviewId = reviewId; state.view = null; state.decisions = null; state.verified = false; persist();
    return read();
  }
  async function read() {
    sync();
    if (!state.reviewId) return fail("saved_layout_choose_review");
    return run(async (call) => {
      const view = await call(reviewPath());
      const local = state.dirty || state.pending?.kind === "save";
      accept(view, { replace: !local });
      if (local && state.decisions == null) state.decisions = copy(view.decisions);
      state.conflict = Boolean(state.dirty && state.editBaseGeneration !== view.generation);
      if (state.pending?.kind === "save") {
        const saved = (view.saves || []).find((item) => item.save_nonce === state.pending.nonce);
        if (saved && saved.generation === state.pending.generation + 1 && saved.generation === view.generation
          && (!pendingPayload || canonical(pendingPayload) === canonical(view.decisions))) {
          clearPending(); state.decisions = copy(view.decisions); state.dirty = false; state.conflict = false; state.editBaseGeneration = null;
        }
        else if (view.generation !== state.pending.generation) state.conflict = true;
      }
      if (state.pending?.kind === "build") {
        const attempt = associatedBuild();
        state.conflict = view.generation !== state.pending.generation && !attempt;
        state.canAbandonBuild = !attempt;
        if (attempt?.status === "built") clearPending();
      }
    });
  }
  async function importFiles(sourcePdf, savedDocx, targetLang) {
    sync();
    if (state.busy) return null;
    if (!sourcePdf || !savedDocx || !["EN", "FR", "AR"].includes(targetLang)) return fail("saved_layout_choose_files");
    if (state.dirty || state.pending && state.pending.kind !== "import") return fail("saved_layout_pending_changes");
    if (sourcePdf.size > 64 * 1024 ** 2 || savedDocx.size > 32 * 1024 ** 2) return fail("saved_layout_file_too_large");
    if (!state.pending) { state.pending = { kind: "import", nonce: createNonce(), generation: 0 }; persist(); }
    return run(async (call) => {
      const form = new FormData(); form.append("source_pdf", sourcePdf); form.append("saved_docx", savedDocx);
      form.append("target_lang", targetLang); form.append("import_nonce", state.pending.nonce);
      const view = await call("/imports", { method: "POST", body: form });
      state.reviewId = ""; accept(view); clearPending(); state.restored = false; state.conflict = false;
    });
  }
  async function save() {
    sync();
    if (state.busy) return null;
    if ((!state.verified && !(state.pending?.kind === "save" && pendingPayload)) || state.conflict || state.pending && state.pending.kind !== "save") return fail("saved_layout_read_current_review");
    if (state.pending && !pendingPayload) return fail("saved_layout_recover_save");
    if (!state.pending) {
      pendingPayload = copy(state.decisions);
      state.pending = { kind: "save", nonce: createNonce(), generation: state.view.generation }; persist();
    }
    return run(async (call) => {
      const result = await call(reviewPath("/decisions"), json({ expected_generation: state.pending.generation,
        save_nonce: state.pending.nonce, decisions: pendingPayload }));
      accept(result); clearPending(); state.restored = false;
    });
  }
  async function build({ newAttempt = false } = {}) {
    sync();
    if (state.busy) return null;
    if (!state.verified || state.dirty || state.conflict || state.pending && state.pending.kind !== "build") return fail("saved_layout_save_review_first");
    if (!state.view?.decisions?.review?.document_reviewed) return fail("saved_layout_review_incomplete");
    if (newAttempt) {
      if (associatedBuild()?.status !== "incomplete") return fail("saved_layout_read_current_review");
      clearPending();
    }
    if (!state.pending) { state.pending = { kind: "build", nonce: createNonce(), generation: state.view.generation }; persist(); }
    return run(async (call) => {
      const result = await call(reviewPath("/builds"), json({ expected_generation: state.pending.generation,
        operation_nonce: state.pending.nonce, review_confirmed: true }));
      accept(result);
      if (associatedBuild()?.status === "built") clearPending();
    });
  }
  function discardChanges() {
    sync();
    if (!state.verified || state.busy || state.pending?.kind === "build" && !state.canAbandonBuild || state.pending?.kind === "import") return false;
    state.decisions = copy(state.view.decisions); state.dirty = false; state.conflict = false; state.editBaseGeneration = null; state.canAbandonBuild = false; clearPending(); emit(); return true;
  }
  function startNewImport() {
    sync(); if (state.busy || state.dirty || state.pending && state.pending.kind !== "import") return false;
    clearPending(); state.reviewId = ""; state.view = state.decisions = null; state.verified = false; state.conflict = false; state.errorCode = ""; persist(); emit(); return true;
  }
  function artifactUrl(artifact, kind = "docx") {
    sync(); if (!state.verified || !safeId(artifact?.artifact_id) || !["docx", "source_map", "receipt"].includes(kind)) return "";
    const owned = (state.view.artifacts || []).find((item) => item.artifact_id === artifact.artifact_id);
    const build = (state.view.builds || []).find((item) => item.artifact_id === artifact.artifact_id && item.status === "built");
    if (!owned || !build || owned.generation !== build.generation) return "";
    return savedLayoutUrl(reviewPath(`/artifacts/${encodeURIComponent(artifact.artifact_id)}/${kind}`), owner);
  }
  function imageUrl(pageNumber) {
    sync(); return state.verified && state.view.pages.some((p) => p.page_number === pageNumber)
      ? savedLayoutUrl(reviewPath(`/pages/${pageNumber}/image`), owner) : "";
  }
  sync();
  return { snapshot, sync, initialize, importFiles, open, read, edit, save, build, discardChanges, startNewImport, artifactUrl, imageUrl };
}

export { canonical as canonicalSavedLayoutDecision };
