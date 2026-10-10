import {fetchJson} from "./api.js";
import {ordinaryLayoutUrl} from "./ordinary_layout_review.js";

/** Natural-text correction, with server-owned before/after drafts. No HTML interpolation. */
export function mountTextCorrection({root,getScope,getJob,request=fetchJson,onApproved=()=>{}}) {
  const doc=root.ownerDocument;
  let owner="",epoch=0,view=null,draft=null,open=false,busy=false,error="",actions=[],region=[0,0,1,1],page=null,disposed=false,rendered=false,editor={paragraph:"",kind:"replace",text:""},approval={draftId:"",source:false,changes:false,note:""};
  const el=(tag,text)=>{const n=doc.createElement(tag);if(text!=null)n.textContent=String(text);return n;};
  const scope=()=>({...getScope(),jobId:getJob()?.job_id||""});
  const key=()=>{const s=scope();return `${s.runtimeMode}:${s.workspaceId}:${s.jobId}`;};
  const nonce=()=>crypto.randomUUID().replaceAll("-","");
  async function call(tail,body) {
    const token=epoch,s=scope();
    const result=await request(ordinaryLayoutUrl(s,tail),s,{cache:"no-store",...(body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})});
    if(token!==epoch||key()!==owner)throw new Error("correction_scope_changed");
    return result.normalized_payload.ordinary_layout;
  }
  const button=(parent,text,fn,disabled=false)=>{const b=el("button",text);b.type="button";b.disabled=disabled||busy;const bound=key();b.addEventListener("click",()=>{if(!disposed&&key()===bound)return run(fn);});parent.append(b);return b;};
  async function run(fn) {if(busy||disposed)return;const token=epoch;busy=true;error="";render(true);try{await fn();}catch(e){
    const code=e?.payload?.diagnostics?.error||e.message||"correction_failed";
    if(token!==epoch||disposed)return;error=/structure_unsupported|unsupported_content|paragraph_controls/.test(code)
      ?"Your Word file is preserved. Its structure cannot be imported safely; enter the corrections in this editor instead."
      :/stale|changed|conflict/.test(code)?"The selected document changed. Refresh the correction and compare the current copy before approving."
      :/frozen/.test(code)?"This delivery is already locked for confirmation. Its files are preserved."
      :"The correction could not be completed. Your current delivery and Word edits are preserved.";
  }finally{if(token===epoch&&!disposed){busy=false;render(true);}}}
  async function read(){view=await call("/text-corrections");page=page&&view.source_pages.includes(page)?page:view.source_pages[0];}
  function check(parent,text,change){const label=el("label"),input=el("input");input.type="checkbox";input.disabled=busy;input.addEventListener("change",()=>change(input.checked));label.append(input,el("span",text));parent.append(label);return input;}
  function source(parent){
    const label=el("label","Source page "),select=el("select");
    for(const p of view.source_pages){const option=el("option",String(p));option.value=String(p);option.selected=p===page;select.append(option);}
    select.addEventListener("change",()=>{page=Number(select.value);region=[0,0,1,1];render(true);});label.append(select);parent.append(label);
    const img=el("img");img.alt=`Original source page ${page}`;img.src=ordinaryLayoutUrl(scope(),`/text-corrections/source/${page}`);img.style.maxWidth="100%";img.draggable=false;
    const frame=el("div"),outline=el("div");frame.style.position="relative";frame.style.display="inline-block";outline.style.position="absolute";outline.style.border="2px solid #2459ad";outline.style.pointerEvents="none";
    const showRegion=()=>{outline.style.left=`${region[0]*100}%`;outline.style.top=`${region[1]*100}%`;outline.style.width=`${(region[2]-region[0])*100}%`;outline.style.height=`${(region[3]-region[1])*100}%`;};showRegion();frame.append(img,outline);
    let start=null;
    const point=e=>{const r=img.getBoundingClientRect();return [Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))];};
    img.addEventListener("pointerdown",e=>{start=point(e);img.setPointerCapture?.(e.pointerId);});
    const status=el("p",region.join(",")==="0,0,1,1"?"Source reference: whole page. Drag on the image to identify a smaller region.":"Selected source region shown by the blue outline will be recorded.");
    img.addEventListener("pointerup",e=>{if(!start)return;const end=point(e);if(Math.abs(end[0]-start[0])>.01&&Math.abs(end[1]-start[1])>.01){region=[Math.min(start[0],end[0]),Math.min(start[1],end[1]),Math.max(start[0],end[0]),Math.max(start[1],end[1])];showRegion();status.textContent="Selected source region will be recorded with the correction.";}start=null;});
    parent.append(frame,status);
  }
  function render(force=false){
    if(disposed)return;
    const eligible=getJob()?.status==="completed"&&Boolean(getJob()?.result?.save_seed);
    if(!force&&rendered&&key()===owner&&root.hidden===!eligible)return;
    rendered=true;
    if(key()!==owner){owner=key();epoch++;view=null;draft=null;actions=[];open=false;busy=false;error="";editor={paragraph:"",kind:"replace",text:""};approval={draftId:"",source:false,changes:false,note:""};}
    root.replaceChildren();root.hidden=!eligible;
    if(root.hidden)return;
    root.append(el("h3","Review and correct translated text"),el("p","Compare the translation with its source. Corrections use no additional API calls and become delivery text only after you approve the changes."));
    button(root,open?"Close text correction":"Correct translated text",async()=>{open=!open;if(open)await read();});
    if(error){const n=el("p",error);n.setAttribute("role","alert");root.append(n);}
    if(!open||!view)return;
    button(root,"Refresh correction",async()=>{await read();draft=null;actions=[];});
    if(view.frozen){root.append(el("p","Approved delivery is locked for confirmation."));return;}
    const reference=el("section");reference.setAttribute("aria-label","Original source reference");source(reference);root.append(reference);
    for(const finding of view.source_findings||[]){
      const card=el("section");card.append(el("strong","Source detail to review"),el("p",finding.literal),el("p",finding.review_status==="unresolved"?"Suggested by the layout model; compare the source before deciding.":"Reviewed for this selected output."));
      button(card,"Show source detail",async()=>{page=finding.page_number;region=[...finding.source_bbox];});
      if(finding.review_status==="unresolved"){
        button(card,"Propose correction",async()=>{page=finding.page_number;region=[...finding.source_bbox];editor={paragraph:view.paragraphs.find(r=>r.parent_paragraph_id===finding.insertion_context.paragraph_id)?.paragraph_id||view.paragraphs.find(r=>r.editable)?.paragraph_id||"",kind:finding.insertion_context.position==="before"?"insert_before":finding.insertion_context.position==="after"?"insert_after":"replace",text:finding.insertion_context.position==="within"?(view.paragraphs.find(r=>r.parent_paragraph_id===finding.insertion_context.paragraph_id)?.text||""):finding.literal};});
        button(card,"Reviewed — no change needed",async()=>{await call(`/text-corrections/findings/${finding.finding_id}`,{parent:view.parent,disposition:"reviewed_no_change",source_compared:true});await read();});
        if(view.parent.selection_id&&view.selected_kind==="text_corrected")button(card,"Correction reviewed for this detail",async()=>{await call(`/text-corrections/findings/${finding.finding_id}`,{parent:view.parent,disposition:"corrected",source_compared:true});await read();});
      }root.append(card);
    }
    if(draft){
      root.append(el("h4","Compare before and after"));
      for(const change of draft.changes){const card=el("section"),before=el("pre",change.before||"(new paragraph)"),after=el("pre",change.after||"(removed)");before.dir="auto";after.dir="auto";card.append(el("strong","Before"),before,el("strong","After"),after);if(change.formatting_reset)card.append(el("p","Mixed character emphasis is reset for this paragraph. Review its final formatting."));root.append(card);}
      if(approval.draftId!==draft.draft_id)approval={draftId:draft.draft_id,source:false,changes:false,note:""};
      const note=el("textarea");note.setAttribute("aria-label","Optional correction note");note.maxLength=2000;note.value=approval.note;note.addEventListener("input",()=>{approval.note=note.value;});
      const approve=button(root,"Approve changes",async()=>{await call(`/text-corrections/${draft.draft_id}/approve`,{approval_nonce:nonce(),source_compared:true,changes_reviewed:true,rationale:note.value});draft=null;actions=[];await read();await onApproved();},true);
      const enabled=()=>{approve.disabled=busy||!approval.source||!approval.changes;};
      const sourceCheck=check(root,"I compared every change with the source",v=>{approval.source=v;enabled();});
      const changesCheck=check(root,"I approve all text changes shown above",v=>{approval.changes=v;enabled();});sourceCheck.checked=approval.source;changesCheck.checked=approval.changes;enabled();root.append(note);
      button(root,"Cancel this correction",async()=>{await call(`/text-corrections/${draft.draft_id}/cancel`,{});draft=null;actions=[];await read();});
      return;
    }
    const target=el("select");target.setAttribute("aria-label","Translated paragraph");
    for(const row of view.paragraphs){const option=el("option",`${row.part_uri.includes("footer")?"Footer: ":row.part_uri.includes("header")?"Header: ":""}${row.text.slice(0,100)||"(empty paragraph)"}`);option.value=row.paragraph_id;option.disabled=!row.editable;target.append(option);}
    const input=el("textarea");input.dir="auto";input.maxLength=32000;input.setAttribute("aria-label","Corrected paragraph text");
    const kind=el("select");kind.setAttribute("aria-label","Correction action");
    for(const [value,text]of[["replace","Replace paragraph text"],["insert_before","Add paragraph before"],["insert_after","Add paragraph after"],["delete","Remove paragraph"]]){const o=el("option",text);o.value=value;kind.append(o);}
    target.value=view.paragraphs.some(r=>r.paragraph_id===editor.paragraph)?editor.paragraph:view.paragraphs.find(r=>r.editable)?.paragraph_id||"";kind.value=editor.kind;
    const load=()=>{input.value=kind.value==="replace"?(view.paragraphs.find(r=>r.paragraph_id===target.value)?.text||""):"";input.disabled=kind.value==="delete";};const update=()=>{load();editor={paragraph:target.value,kind:kind.value,text:input.value};};target.addEventListener("change",update);kind.addEventListener("change",update);if(editor.paragraph===target.value){input.value=editor.text;input.disabled=kind.value==="delete";}else update();input.addEventListener("input",()=>{editor.text=input.value;});
    root.append(el("h4","Edit the translation"),target,kind,input);
    button(root,"Add change to review",async()=>{if(actions.some(a=>a.paragraph_id===target.value))throw new Error("duplicate_change");actions.push({kind:kind.value,paragraph_id:target.value,text:kind.value==="delete"?"":input.value,source_page:page,source_bbox:[...region]});});
    for(const a of actions)root.append(el("p",`${a.kind==="delete"?"Remove":a.kind==="replace"?"Replace":"Add"}: ${a.text.slice(0,120)||"paragraph"}`));
    button(root,"Review these changes",async()=>{draft=await call("/text-corrections",{draft_nonce:nonce(),parent:view.parent,actions,import_word:false});},!actions.length);
    button(root,"Clear pending changes",async()=>{actions=[];},!actions.length);
    button(root,"Review text changes saved in Word",async()=>{draft=await call("/text-corrections",{draft_nonce:nonce(),parent:view.parent,actions:[],import_word:true});});
    for(const retained of view.drafts.filter(d=>d.status==="draft"&&d.parent_sha256===view.parent.sha256))button(root,"Review saved correction",async()=>{draft=retained;});
    if(view.output_review_required){
      const details=el("details");details.append(el("summary","Review the complete corrected output"));
      for(const row of view.paragraphs){const p=el("p",row.text);p.dir="auto";details.append(p);}root.append(details);
      let reviewed=false;
      const finish=button(root,"Confirm output review",async()=>{await call("/text-corrections/output-review",{selection_id:view.parent.selection_id,expected_generation:view.parent.delivery_generation,all_pages_reviewed:true});await read();await onApproved();},true);
      check(root,"I reviewed the entire corrected output, including its formatting",v=>{reviewed=v;finish.disabled=busy||!reviewed;});
      root.append(el("p","For Arabic, also complete the normal Word direction and alignment review before saving the case."));
    }
  }
  render();return {render,dispose(){disposed=true;epoch++;root.replaceChildren();}};
}
