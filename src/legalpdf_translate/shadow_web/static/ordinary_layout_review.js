import { fetchJson } from "./api.js";

const copy = value => value == null ? value : JSON.parse(JSON.stringify(value));
const safeId = value => typeof value === "string" && /^[A-Za-z0-9_-]{1,100}$/.test(value);
const safeNonce = value => typeof value === "string" && /^[a-f0-9]{32}$/.test(value);
const safeCap = value => typeof value === "string" && /^\d{1,12}(?:\.\d{1,12})?$/.test(value) && /[1-9]/.test(value);
const identity = scope => `${scope.runtimeMode}:${scope.workspaceId}:${scope.jobId || ""}`;
const storageKey = scope => `legalpdf:ordinary-layout:v1:${identity(scope)}`;
const json = body => ({method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)});
const terminalSuggestion = value => ["applied_unreviewed", "failed", "incomplete", "cancelled"].includes(value?.status);

export function ordinaryLayoutUrl(scope, tail = "/layout") {
  if (!safeId(scope.jobId)) return "";
  return `/api/translation/jobs/${encodeURIComponent(scope.jobId)}${tail}?${new URLSearchParams({mode:scope.runtimeMode, workspace_id:scope.workspaceId})}`;
}

function restoredPending(value) {
  if (!value || !["prepare", "suggest", "accept", "select", "budget"].includes(value.kind) || !safeNonce(value.nonce)) return null;
  if (value.kind === "prepare") return {kind:value.kind, nonce:value.nonce};
  if (!safeNonce(value.baseline) || !Number.isSafeInteger(value.generation) || value.generation < 0) return null;
  const result = {kind:value.kind, nonce:value.nonce, baseline:value.baseline, generation:value.generation};
  if (value.kind === "budget") {
    if (!safeCap(value.cap)) return null;
    result.cap = value.cap;
  } else if (value.kind === "suggest") {
    if (!Array.isArray(value.pages) || !value.pages.length || value.pages.length > 100
      || value.pages.some(p => !Number.isInteger(p) || p < 1 || p > 100)) return null;
    result.pages = [...new Set(value.pages)].sort((a,b)=>a-b);
  } else if (value.kind === "accept") {
    if (!safeNonce(value.artifactId)) return null;
    result.artifactId = value.artifactId;
  } else {
    if (!["original", "reviewed"].includes(value.choice)
      || value.choice === "reviewed" && (!safeNonce(value.reviewId)
        || !Number.isSafeInteger(value.reviewGeneration) || value.reviewGeneration < 0 || !safeNonce(value.artifactId))
      || value.choice === "original" && (value.reviewId !== null || value.reviewGeneration !== null || value.artifactId !== null)) return null;
    Object.assign(result, {choice:value.choice,reviewId:value.reviewId,reviewGeneration:value.reviewGeneration,
      artifactId:value.choice === "reviewed" ? value.artifactId : null});
  }
  return result;
}

/** Only opaque owner-scoped identifiers/nonces survive browser reloads. */
export function createOrdinaryLayoutController({getScope, request = fetchJson,
  storage = globalThis.localStorage, createNonce = () => crypto.randomUUID().replaceAll("-", ""), onChange = () => {}}) {
  let scope, epoch = 0, state, requiresRead = false, disposed = false;
  const persist = () => {try {storage?.setItem(storageKey(scope), JSON.stringify({pending:state.pending}));} catch { /* Server records remain authoritative. */ }};
  const snapshot = () => copy(state);
  const emit = () => {if (!disposed) onChange(snapshot());};
  function sync() {
    if (disposed) return false;
    const next = getScope();
    if (scope && identity(scope) === identity(next)) return false;
    scope = {runtimeMode:next.runtimeMode,workspaceId:next.workspaceId,jobId:next.jobId || ""}; epoch += 1; requiresRead = false;
    let retained = null;
    try {retained = restoredPending(JSON.parse(storage?.getItem(storageKey(scope)) || "{}").pending);} catch { /* Invalid pointers are ignored. */ }
    state = {scope,view:null,busy:false,cancelBusy:false,error:"",verified:false,pending:retained,operation:null}; emit(); return true;
  }
  function accept(view, passive = false) {
    if (!view || view.job_id !== scope.jobId || !Number.isSafeInteger(view.generation) || view.generation < 0
      || !Number.isSafeInteger(view.delivery_generation) || view.delivery_generation < 0
      || !["unprepared", "prepared"].includes(view.status)
      || view.status === "prepared" && (!safeNonce(view.baseline_id) || !safeNonce(view.review?.review_id)
        || view.review.generation !== view.generation)) throw new Error("invalid_layout_response");
    const previous = state.view;
    if (passive && previous && previous.baseline_id !== view.baseline_id) {
      requiresRead = true; state.verified = false; state.error = "ordinary_layout_baseline_changed"; return false;
    }
    if (passive && requiresRead) return false;
    if (previous && previous.baseline_id === view.baseline_id
      && (view.generation < previous.generation || view.delivery_generation < previous.delivery_generation)) {
      if (passive) return false;
      throw new Error("ordinary_layout_stale_response");
    }
    requiresRead = false;
    state.view = copy(view); state.verified = true;
    const p = state.pending;
    if (p?.kind === "prepare" && view.preparation_nonce === p.nonce
      || p?.kind === "accept" && view.output_reviews?.some(r => r.acceptance_nonce === p.nonce)
      || p?.kind === "budget" && view.budget?.authorization_nonce === p.nonce
      || p?.kind === "select" && view.delivery?.selection_id === p.nonce) clearPending();
    return true;
  }
  function clearPending() {state.pending = null; persist();}
  async function run(action) {
    sync(); if (disposed || state.busy || !safeId(scope.jobId)) return null;
    const token = epoch, owner = copy(scope); state.busy = true; state.error = ""; emit();
    const call = async (tail, options = {}) => {
      const response = await request(ordinaryLayoutUrl(owner, tail), owner, {cache:"no-store",...options});
      if (token !== epoch || identity(owner) !== identity(getScope())) {sync(); throw new Error("stale_scope");}
      const value = response?.normalized_payload?.ordinary_layout;
      if (value == null) throw new Error("invalid_layout_response");
      return value;
    };
    try {return await action(call);}
    catch (error) {
      if (token === epoch) {
        const code = error?.payload?.diagnostics?.error || error?.payload?.diagnostics?.code || error?.message;
        state.error = typeof code === "string" && /^[a-z0-9_]{1,120}$/.test(code) ? code : "ordinary_layout_operation_failed";
        state.verified = false;
      }
      return null;
    } finally {if (token === epoch) {state.busy = false; emit();}}
  }
  async function read() {
    return run(async call => {
      accept(await call("/layout"));
      if (state.pending?.kind === "suggest") {
        const result = await call(`/layout/suggestions/${state.pending.nonce}`);
        state.operation = copy(result);
        if (terminalSuggestion(result)) clearPending();
      }
    });
  }
  function stage(kind, values = {}) {
    sync(); if (disposed || state.busy || state.pending) return false;
    if (kind !== "prepare" && (!state.verified || !state.view?.baseline_id || state.view.stale || state.view.frozen)) return false;
    state.pending = {kind,nonce:createNonce(),...values}; persist(); return true;
  }
  async function dispatch() {
    return run(async call => {
      const p = state.pending; if (!p) return;
      let tail, body;
      if (p.kind === "prepare") {tail = "/layout/prepare"; body = {prepare_nonce:p.nonce};}
      else if (p.kind === "budget") {tail = "/layout/budget"; body = {baseline_id:p.baseline,expected_generation:p.generation,authorization_nonce:p.nonce,cap_usd:p.cap};}
      else if (p.kind === "suggest") {tail = "/layout/suggestions"; body = {baseline_id:p.baseline,expected_generation:p.generation,operation_nonce:p.nonce,page_numbers:p.pages};}
      else if (p.kind === "accept") {tail = "/layout/output-review"; body = {baseline_id:p.baseline,expected_generation:p.generation,artifact_id:p.artifactId,acceptance_nonce:p.nonce,all_pages_reviewed:true};}
      else {tail = "/delivery"; body = {baseline_id:p.baseline,expected_delivery_generation:p.generation,selection_nonce:p.nonce,kind:p.choice,
        review_id:p.reviewId,artifact_id:p.artifactId,expected_review_generation:p.reviewGeneration,keep_ordinary_confirmed:p.choice === "original"};}
      let value;
      try {value = await call(tail, json(body));}
      catch (error) {
        // Only the original nonpaid SELECT POST can prove a prewrite refusal.
        // A failed status read after a successful POST is still uncertain.
        const code = error?.payload?.diagnostics?.error || error?.payload?.diagnostics?.code;
        if (p.kind !== "select" || error?.status !== 409
          || !["ordinary_layout_baseline_stale", "ordinary_layout_delivery_generation_conflict"].includes(code)) throw error;
        const fresh = await call("/layout");
        accept(fresh); // Validates the owner, schema and monotonic generations.
        if (!state.pending) return snapshot(); // A matching nonce proves success.
        if (state.pending.kind === "select" && state.pending.nonce === p.nonce
          && fresh.baseline_id === p.baseline && fresh.delivery_generation === p.generation) {
          clearPending(); state.error = code; return snapshot();
        }
        throw error;
      }
      if (p.kind === "suggest") {
        state.operation = copy(value);
        if (terminalSuggestion(value)) clearPending();
        accept(await call("/layout"));
      } else {accept(value); accept(await call("/layout"));}
      return snapshot();
    });
  }
  const base = () => ({baseline:state.view.baseline_id,generation:state.view.generation});
  const prepare = async () => {if (stage("prepare")) return dispatch(); return null;};
  const suggest = async pages => {sync(); if (state.view?.suggestion_capability?.available && stage("suggest",{...base(),pages})) return dispatch(); return null;};
  const acceptOutput = async artifactId => {sync(); if (state.view && stage("accept",{...base(),artifactId})) return dispatch(); return null;};
  const authorizeBudget = async cap => {
    sync(); if (disposed || state.busy || state.pending) return null;
    const value = typeof cap === "string" ? cap.trim() : "";
    if (!safeCap(value)) {state.error = "ordinary_layout_invalid_budget"; emit(); return null;}
    if (state.view && stage("budget",{...base(),cap:value})) return dispatch(); return null;
  };
  const select = async (choice, artifactId = null) => {
    sync(); if (state.view && stage("select",{...base(),generation:state.view.delivery_generation,
      choice,artifactId:choice === "reviewed" ? artifactId : null,
      reviewId:choice === "reviewed" ? state.view.review.review_id : null,
      reviewGeneration:choice === "reviewed" ? state.view.generation : null})) return dispatch(); return null;
  };
  async function cancelSuggestion() {
    sync();
    if(disposed||state.cancelBusy||state.pending?.kind!=="suggest"||state.operation?.status==="cancel_requested")return null;
    const p=copy(state.pending),owner=copy(scope),token=epoch;
    state.cancelBusy=true;state.error="";emit();
    try {
      const response=await request(ordinaryLayoutUrl(owner,`/layout/suggestions/${p.nonce}/cancel`),owner,
        {cache:"no-store",...json({baseline_id:p.baseline,expected_generation:p.generation})});
      if(token!==epoch||identity(owner)!==identity(getScope())){sync();return null;}
      const value=response?.normalized_payload?.ordinary_layout;
      if(!value||value.operation_nonce!==p.nonce||value.baseline_id!==p.baseline
        ||value.status!=="cancel_requested"&&!terminalSuggestion(value))throw new Error("invalid_layout_response");
      // A completed main request may already have supplied the terminal receipt.
      if(state.pending?.nonce===p.nonce){
        state.operation=copy(value);
        if(terminalSuggestion(value))clearPending();
      }
      return copy(value);
    } catch(error) {
      if(token===epoch){
        const code=error?.payload?.diagnostics?.error||error?.payload?.diagnostics?.code||error?.message;
        state.error=typeof code==="string"&&/^[a-z0-9_]{1,120}$/.test(code)?code:"ordinary_layout_operation_failed";
      }
      return null;
    } finally {if(token===epoch){state.cancelBusy=false;emit();}}
  }
  function canUseDelivery() {return Boolean(!disposed && !state.busy && !state.pending && state.verified && state.view?.delivery && !state.view.stale && !state.view.delivery.stale);}
  function deliveryGeneration() {return canUseDelivery() ? state.view.delivery_generation : null;}
  function receive(view) {
    sync(); if (disposed || !view || state.busy) return;
    try {accept(view, true);} catch {requiresRead = true; state.verified = false; state.error = "invalid_layout_response";}
    emit();
  }
  function dispose() {disposed = true; epoch += 1; state.busy = false; state.cancelBusy = false; state.verified = false;}
  sync();
  return {snapshot,sync,read,prepare,suggest,acceptOutput,select,authorizeBudget,cancelSuggestion,retry:dispatch,deliveryGeneration,canUseDelivery,receive,dispose};
}
