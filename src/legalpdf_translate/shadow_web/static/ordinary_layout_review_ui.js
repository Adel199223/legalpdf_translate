import { fetchJson } from "./api.js";
import { createOrdinaryLayoutController, ordinaryLayoutUrl } from "./ordinary_layout_review.js";
import { mountSavedDocxLayout } from "./saved_docx_layout_ui.js";
import { mountTextCorrection } from "./text_correction_ui.js";

export function ordinaryLayoutMessage(code) {
  if (/edited_layout_rebase_required/.test(code)) return "Word contains text changes. They remain preserved. Choose Review text changes in the text correction editor to compare and approve them.";
  if (/correction_output_review_required/.test(code)) return "Review the complete corrected output before saving the case.";
  if (/automatic_operation_pending_or_uncertain/.test(code)) return "An earlier layout request may have been billed. The app kept the original Word file and billing record; refresh its status before any new request.";
  if (/automatic_policy_changed|pricing_reference_expired/.test(code)) return "Automatic formatting is unavailable until the layout pricing is refreshed. Your original Word file is preserved.";
  if (/page_mapping|ambiguous_page/.test(code)) return "Confirm which translated paragraphs belong to each source page, save the review, then request a suggestion.";
  if (/budget|paid_policy|accounting|cost_limit/.test(code)) return "Layout suggestions need an available, bounded API budget. You can still review and adjust formatting locally.";
  if (/stale|conflict|changed/.test(code)) return "The document or review changed. Refresh the review and choose the current copy before continuing.";
  if (/frozen/.test(code)) return "The selected files are locked for confirmation. If confirmation failed, correct the form and retry; the files remain preserved.";
  if (/job_unavailable/.test(code)) return "The original job is unavailable. Retained review files can be inspected, but delivery cannot be changed.";
  return "The layout operation needs attention. Refresh its status before retrying. Original files remain available.";
}

export function mountOrdinaryLayoutReview({root, getScope, getJob, contentReviewBlocked = () => false,
  request = fetchJson, onDeliveryChange = () => {}}) {
  if (!root) return null;
  const doc = root.ownerDocument || document;
  let controller, editor = null, editorKey = "", panelOpen = false, selectedPages = new Set(), outputChecks = new Set(),
    lastOwner = "", lastSelection = "", localError = "", localStatus = "", refreshingEditor = false, disposed = false, nativeOpening = false, editorReadOnly = false;
  const el = (tag, text, cls) => {const n = doc.createElement(tag); if (text != null) n.textContent = String(text); if (cls) n.className = cls; return n;};
  const header = el("div"), actions = el("div"), editorRoot = el("section"), outputs = el("div");
  editorRoot.setAttribute("aria-label", "This translation's source layout review");
  const correctionRoot=el("section");correctionRoot.setAttribute("aria-label","Translation text correction");
  root.append(header, correctionRoot, actions, editorRoot, outputs);
  const correction=mountTextCorrection({root:correctionRoot,getScope,getJob,request,onApproved:async()=>{await controller.read();}});
  const scope = () => ({...getScope(),jobId:getJob()?.job_id || ""});
  const ownerKey = () => {const s=scope();return `${s.runtimeMode}:${s.workspaceId}:${s.jobId}`;};
  const button = (parent,text,action,disabled=false) => {
    const b = el("button",text); b.type = "button"; b.disabled = disabled;
    const owner=ownerKey();
    b.addEventListener("click",async () => {
      if(disposed||b.disabled||owner!==ownerKey())return;
      localError = "";localStatus = "";
      try {await action();} catch(error) {if(!disposed&&owner===ownerKey())localError = error?.message || "Layout action failed.";}
      if(!disposed&&owner===ownerKey())render();
    });
    parent.append(b); return b;
  };
  const checkbox = (parent,text,checked,change,disabled=false) => {
    const label=el("label"), n=el("input"); n.type="checkbox"; n.checked=checked; n.disabled=disabled;
    n.addEventListener("change",()=>change(n.checked)); label.append(n,el("span",text)); parent.append(label); return n;
  };
  const editorBusy = () => {const s=editor?.controller.snapshot(); return Boolean(s?.busy || s?.dirty || s?.pending || s?.conflict);};
  const isEditorReadOnly = () => {const s=controller.snapshot();return Boolean(s.busy||s.pending||!s.verified||s.view?.frozen||s.view?.stale||!s.view?.attached);};
  async function refreshReview() {
    await controller.read();
    if (editor && !editorBusy()) await editor.controller.read();
  }
  async function recoverPending() {
    const owner=ownerKey();
    await controller.read();
    if(disposed||owner!==ownerKey())return;
    let state=controller.snapshot();
    if(state.verified&&state.pending)await controller.retry();
    if(disposed||owner!==ownerKey())return;
    state=controller.snapshot();
    if(state.verified&&state.view?.review){panelOpen=true;selectedPages=new Set(state.view.selected_pages||[]);}
    if(editor&&!editorBusy())await editor.controller.read();
  }
  function mountEditor(state) {
    const view=state.view;
    const key=`${state.scope.runtimeMode}:${state.scope.workspaceId}:${state.scope.jobId}:${view?.baseline_id || ""}`;
    if (!view?.review || !panelOpen || view?.delivery?.kind==="text_corrected") {editorRoot.hidden=true; return;}
    editorRoot.hidden=false;
    const locked=isEditorReadOnly();
    if (key===editorKey) {if(locked!==editorReadOnly){editorReadOnly=locked;editor.render();}return;}
    editor?.dispose(); editor=null; editorKey=key; editorRoot.replaceChildren();
    editorReadOnly=locked;
    editor=mountSavedDocxLayout({root:editorRoot,embedded:true,storageNamespace:`ordinary-${state.scope.jobId}-${view.baseline_id}`,
      getScope,request,readOnly:isEditorReadOnly,
      onStateChange: s => {
        if (!editor || refreshingEditor || s.busy || s.dirty || s.pending || !s.verified) return;
        renderActions();
        if (s.view?.generation !== controller.snapshot().view?.generation) {
          refreshingEditor=true; controller.read().finally(()=>{refreshingEditor=false; renderActions();});
        }
      }});
    const current=editor.controller.snapshot();
    if (current.reviewId===view.review.review_id) editor.controller.read();
    else editor.controller.open(view.review.review_id);
  }
  function renderActions() {
    if (!controller) return;
    const state=controller.snapshot(), view=state.view;
    actions.replaceChildren(); outputs.replaceChildren();
    if (!panelOpen || !view?.review || view?.delivery?.kind==="text_corrected") return;
    const locked=state.busy || nativeOpening || Boolean(view.frozen) || !state.verified || view.stale || !view.attached;
    const busy=locked || editorBusy() || Boolean(state.pending);
    actions.append(el("h3","1. Review the source layout"),el("p","Review the source beside the current translation. Suggestions preserve the wording and require your review."));
    if(view.automatic_candidate) actions.append(el("p","The normal Word download is automatically formatted from source-image suggestions. It is unreviewed; inspect the complete Word copy before case delivery or further editing."));
    const budget=view.budget;
    if(budget?.authorized) actions.append(el("p",`API budget: USD ${budget.cap_usd ?? "—"} maximum for this run, including its translation. Remaining: USD ${budget.remaining_usd ?? "unavailable"}.${budget.shared_existing_cap?" Existing shared budget applies.":""}`));
    if(budget?.authorization_available&&!budget.authorized&&!view.frozen) {
      const box=el("details");box.open=true;box.append(el("summary","Set a maximum API cost for this run"));
      box.append(el("p",`Translation cost already recorded: USD ${budget.translation_cost_usd}. This limit includes that cost and every layout suggestion for this run.`));
      const label=el("label"), cap=el("input");cap.type="number";cap.min=String(budget.minimum_cap_usd);cap.step="0.001";
      cap.value=String(budget.suggested_cap_usd ?? budget.minimum_cap_usd ?? "");cap.disabled=busy;
      label.append(el("span","Maximum total API cost (USD)"),cap);box.append(label);
      const authorize=button(box,"Set this API limit",()=>controller.authorizeBudget(cap.value),true);
      checkbox(box,"I authorize this limit for the current run",false,value=>{authorize.disabled=busy||!value;},busy);
      actions.append(box);
    }
    if (!view.frozen) {
      const policy=view.suggestion_capability;
      if (policy?.available) {
        const pages=el("div",null,"saved-layout-toolbar");
        for (const page of view.selected_pages || []) checkbox(pages,`Page ${page}`,selectedPages.has(page),value=>{value?selectedPages.add(page):selectedPages.delete(page);renderActions();},busy);
        actions.append(pages);
        const max=Number(policy.max_page_cost_usd)*selectedPages.size;
        const over=max>Number(policy.max_operation_cost_usd);
        actions.append(el("p",`${policy.model}: at most USD ${Number.isFinite(max)?max.toFixed(3):"—"} for these ${selectedPages.size} page(s). Source images and current translated text are sent for layout suggestions.`));
        if (over) actions.append(el("p","Choose fewer pages to stay within this operation's limit."));
        button(actions,"Suggest source layout",async()=>{await controller.suggest([...selectedPages].sort((a,b)=>a-b));if(editor&&!editorBusy())await editor.controller.read();},busy||!selectedPages.size||over);
      } else actions.append(el("p",ordinaryLayoutMessage(policy?.reason || "paid_policy_unavailable")));
    }
    const operation=state.operation || view.suggestions?.at(-1);
    if (operation) actions.append(el("p",operation.status==="applied_unreviewed"
      ? "Suggestions are ready in the editor below. Review every source page and save the plan before building."
      : operation.status==="cancelled"&&operation.applied_unreviewed
      ? "Suggestions stopped. Changes from completed pages are ready in the editor below and still require your review."
      : `Suggestion status: ${operation.status}. ${operation.error_code?ordinaryLayoutMessage(operation.error_code):"Refresh status to recover an interrupted request."}`));
    button(actions,"Refresh layout status",refreshReview,state.busy);
    outputs.append(el("h3","2. Review the Word copy and choose delivery"),el("p","Open or download a built copy and inspect every page without changing its wording. Then choose it for the case record and Gmail draft. If wording needs correction, update the ordinary translation and prepare a new layout review."));
    const review=editor?.controller.snapshot().view || view.review;
    for (const artifact of review.artifacts || []) {
      const row=el("div",null,"result-card"), current=artifact.generation===view.generation;
      row.append(el("strong",`Formatted copy · review ${artifact.generation}`));
      const url=editor?.controller.artifactUrl(artifact);
      if(url) {const a=el("a","Download this Word copy");a.href=url;a.download="";row.append(a);}
      button(row,"Open a copy in Word for visual review",async()=>{
        const owner=ownerKey();nativeOpening=true;render();
        try {
          const response=await request(ordinaryLayoutUrl(scope(),"/layout/open"),getScope(),{
            method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({baseline_id:view.baseline_id,
              artifact_id:artifact.artifact_id,expected_generation:artifact.generation})});
          if(disposed||owner!==ownerKey())return;
          const result=response?.normalized_payload?.ordinary_layout?.open_result;
          if(result?.ok!==true)throw new Error(result?.message || "Word could not open this copy for visual review. Download the copy or retry after checking Word.");
          localStatus=result.message || "A separate copy opened in Word for visual review. Inspect all its pages without changing the wording.";
        } finally {if(!disposed&&owner===ownerKey())nativeOpening=false;}
      },busy||!current);
      const accepted=view.output_reviews?.some(r=>r.request?.artifact_id===artifact.artifact_id&&r.request?.generation===artifact.generation);
      checkbox(row,"I inspected every page of this Word copy",accepted||outputChecks.has(artifact.artifact_id),value=>{
        value?outputChecks.add(artifact.artifact_id):outputChecks.delete(artifact.artifact_id);renderActions();
      },busy||!current||accepted);
      button(row,"Use this copy for delivery",async()=>{
        const owner=ownerKey();
        if(!accepted) await controller.acceptOutput(artifact.artifact_id);
        if(disposed||owner!==ownerKey())return;
        const s=controller.snapshot();
        if(s.verified&&!s.pending&&s.view.baseline_id===view.baseline_id&&s.view.generation===artifact.generation
          &&s.view.output_reviews?.some(r=>r.request?.artifact_id===artifact.artifact_id)) await controller.select("reviewed",artifact.artifact_id);
      },busy||!current||(!accepted&&!outputChecks.has(artifact.artifact_id)));
      outputs.append(row);
    }
    const fallback=el("details");fallback.append(el("summary","Keep the current translation's layout"),el("p","Choose this only if the current layout is sufficient. The app preserves this choice in the delivery record."));
    let ordinaryConfirmed=false;
    const keep=button(fallback,"Use current translation for delivery",()=>controller.select("original"),true);
    checkbox(fallback,"I reviewed the current document and want to keep its layout",false,value=>{ordinaryConfirmed=value;keep.disabled=busy||!ordinaryConfirmed;},busy);
    outputs.append(fallback);
  }
  function render() {
    if (!controller || disposed) return;
    const state=controller.snapshot(), job=getJob();
    correction.render();
    const owner=`${state.scope.runtimeMode}:${state.scope.workspaceId}:${state.scope.jobId}`;
    if(owner!==lastOwner){lastOwner=owner;editor?.dispose();editor=null;editorKey="";panelOpen=false;selectedPages=new Set();outputChecks=new Set();lastSelection="";localError="";localStatus="";nativeOpening=false;editorRoot.replaceChildren();}
    root.hidden=!(job?.status==="completed"&&job.job_kind==="translate"&&job.result?.save_seed);
    root.classList?.toggle("hidden",root.hidden);
    header.replaceChildren();
    if(root.hidden){editorRoot.hidden=true;actions.replaceChildren();outputs.replaceChildren();return;}
    const view=state.view;
    header.append(el("h3","Source layout and delivery"));
    if (view?.suggestions?.some(item=>item.source_layout_review_required)) {
      header.append(el("p","Source layout needs review: an optional decorative rule could not be safely applied; its text was retained.","saved-layout-status"));
    }
    header.append(el("p",view?.delivery&&!view.delivery.stale&&!view.stale
      ? `${view.delivery.kind==="text_corrected"?"Approved text correction":view.delivery.kind==="reviewed"?"Reviewed formatted copy":view.delivery.kind==="automatic_unreviewed_edited"?"Word-edited formatted copy (source layout unreviewed)":view.delivery.kind==="automatic_unreviewed"?"Automatic formatted copy (unreviewed)":"Current translation"} selected · ${view.delivery.word_count} words${view.frozen?" · files locked for confirmation":""}.`
      : view?.review?"Choose a reviewed copy for delivery after checking its layout.":"Compare headers, headings, emphasis, notice panels, columns and spacing with the source before delivery."));
    if(state.error||localError){const warning=el("p",localError||ordinaryLayoutMessage(state.error),"saved-layout-error");warning.setAttribute("role","alert");header.append(warning);}
    if(localStatus)header.append(el("p",localStatus,"saved-layout-status"));
    if(state.busy)header.append(el("p","Working…","saved-layout-status"));
    if(state.pending){
      header.append(el("p","An operation is awaiting a confirmed result. Recovery checks its saved status before retrying the same operation."));
      button(header,"Recover the same operation",recoverPending,state.busy||nativeOpening);
      if(state.pending.kind==="suggest"){
        header.append(el("p","Stopping waits for the current page to finish. Completed page suggestions still need review, and the current request may incur its reserved cost."));
        button(header,"Stop after current page",()=>controller.cancelSuggestion(),state.cancelBusy||state.operation?.status==="cancel_requested");
      }
    }
    if(view?.automatic_alias) header.append(el("p","This job reuses the same verified formatted copy and saved layout cost. To change its layout, return to the original job and rebase the review there."));
    if(contentReviewBlocked())header.append(el("p","Complete the Arabic wording review above before starting source-layout review."));
    if(!view?.automatic_alias&&view?.delivery?.kind!=="text_corrected")button(header,panelOpen?"Hide layout review":"Review source layout",async()=>{
      const owner=ownerKey();
      if(panelOpen){panelOpen=false;return;}
      if(!controller.snapshot().view)await controller.read();
      if(disposed||owner!==ownerKey())return;
      if(controller.snapshot().view?.status==="unprepared")await controller.prepare();
      if(disposed||owner!==ownerKey())return;
      panelOpen=true;
      selectedPages=new Set(controller.snapshot().view?.selected_pages || []);
    },state.busy||contentReviewBlocked());
    if(view?.stale&&!view.frozen)button(header,"Use the latest saved Word changes",async()=>{await controller.prepare();},state.busy||Boolean(state.pending)||editorBusy());
    mountEditor(state);renderActions();
    const selection=controller.canUseDelivery()?`${owner}:${view.delivery.selection_id}`:"";
    if(selection&&selection!==lastSelection){lastSelection=selection;onDeliveryChange(view.delivery,view);}
  }
  controller=createOrdinaryLayoutController({getScope:scope,request,onChange:render});render();
  function update(job=getJob()) {if(disposed)return;controller.sync(); if(job?.ordinary_layout)controller.receive(job.ordinary_layout);else render();}
  return {controller,update,render,refresh:refreshReview,dispose:()=>{disposed=true;controller.dispose();editor?.dispose();correction.dispose();}};
}
