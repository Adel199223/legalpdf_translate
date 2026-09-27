"""Local saved-Word UI probes: real ES modules and DOM actions, no app runtime."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from .browser_esm_probe import run_browser_esm_json_probe
from .test_source_review_browser_state import DOM


MODULES = {"__CORE__": "saved_docx_layout.js", "__UI__": "saved_docx_layout_ui.js"}
PRELUDE = r"""
const core = await import(__CORE__), ui = await import(__UI__);
if (!globalThis.crypto) globalThis.crypto = (await import('node:crypto')).webcrypto;
const copy = (v) => JSON.parse(JSON.stringify(v));
const scope = {runtimeMode:'shadow', workspaceId:'fictional-layout'};
const memory = () => { const data = new Map(); return { data,
  getItem:(k)=>data.get(k)||null, setItem:(k,v)=>data.set(k,v), removeItem:(k)=>data.delete(k) }; };
const envelope = (v) => ({normalized_payload:{saved_docx_layout:copy(v)}});
const reviewId = 'a'.repeat(32);
const paragraphs = ['Fictional notice 😀 example', 'Avis fictif avec caractères', 'نص تجريبي فقط', 'End\f'].map((text,i)=>({id:`p${String(i+1).padStart(6,'0')}`,ordinal:i+1,text,has_page_break:i===3}));
const decisions = {version:'saved_docx_layout_decisions_v1', paragraphs: paragraphs.map((p)=>({paragraph_id:p.id,regions:[],unmapped_reason:'',role:'body',alignment:'inherit',space_before_pt:null,space_after_pt:null,heading_level:0,heading_size_pt:null,bold:false,italic:false,underline:false,emphasis:[]})),bands:[{kind:'flow',groups:[{paragraph_ids:paragraphs.map((p)=>p.id),panel:false}]}],review:{reviewer_kind:'operator_review',reviewer:'',note:'',pages_reviewed:[],document_reviewed:false}};
const draft = {review_id:reviewId, generation:0,status:'imported',target_lang:'EN',paragraphs,decisions,
  pages:[{page_number:1,width_px:200,height_px:300}],builds:[],artifacts:[],saves:[],qualifications:[]};
const complete = () => {const v=copy(draft);v.status='reviewed';v.generation=1;v.decisions.paragraphs.forEach(p=>{p.regions=[{page_number:1,bbox_px:[10,10,100,100]}];});v.decisions.review={reviewer_kind:'operator_review',reviewer:'Fictional operator',note:'Every source group checked',pages_reviewed:[1],document_reviewed:true};return v;};
const path = (url) => new URL(url,'http://localhost').pathname;
"""


def probe(script: str, *, data=None):
    return run_browser_esm_json_probe(PRELUDE + "\nconst data=" + json.dumps(data, ensure_ascii=True) + ";\n" + script, MODULES)


def test_unicode_regions_and_contiguous_layout_preserve_controls_and_physical_order():
    result = probe(r"""
const t='A😀 e\u0301 مِلَف 121/26'; const start=t.indexOf('م');
const range=ui.selectedCodepointRange(t,start,t.length);let surrogate=false;
try{ui.selectedCodepointRange(t,2,3);}catch{surrogate=true;}
const columns=[{kind:'columns',widths_pct:[40,60],gutter_pt:12,cells:[{groups:[{paragraph_ids:['p000001','p000002'],panel:false}]},{groups:[{paragraph_ids:['p000003'],panel:false}]}]}];
const arranged=ui.replaceLayoutRange(decisions,paragraphs,0,2,columns);
const panel=ui.setNoticePanelRange(arranged,paragraphs,1,1);let split=false,breakRejected=false;
try{ui.replaceLayoutRange(panel,paragraphs,0,0,[{kind:'flow',groups:[{paragraph_ids:['p000001'],panel:false}]}]);}catch{split=true;}
try{ui.setNoticePanelRange(panel,paragraphs,3,3);}catch{breakRejected=true;}
console.log(JSON.stringify({range,text:Array.from(t).slice(...range).join(''),surrogate,split,breakRejected,panel,
  ids:ui.flattenedParagraphIds(panel.bands),rect:ui.rectangleFromPointer({x:90,y:140},{x:20,y:30},{left:10,top:20,width:100,height:150},{width_px:200,height_px:300})}));
""")
    assert result["text"] == "مِلَف 121/26" and result["surrogate"]
    assert result["split"] and result["breakRejected"]
    assert result["ids"] == [f"p{i:06d}" for i in range(1, 5)]
    assert result["panel"]["bands"][0]["cells"][0]["groups"] == [
        {"paragraph_ids": ["p000001"], "panel": False}, {"paragraph_ids": ["p000002"], "panel": True}]
    assert result["rect"] == [20, 20, 160, 240]


def test_exact_save_retry_restart_receipt_and_scope_clear_never_persist_wording():
    result = probe(r"""
const storage=memory(), requests=[];let saved=copy(draft),fail=true;
const options={getScope:()=>scope,storage,createNonce:()=> 'b'.repeat(32), request:async(url,owner,options)=>{
 const body=options.body?JSON.parse(options.body):null;requests.push({url,owner,body});
 if(path(url).endsWith('/decisions')){saved={...saved,generation:1,decisions:body.decisions,saves:[{save_nonce:body.save_nonce,generation:1}]};if(fail){fail=false;throw new Error('Lost response');}}
 return envelope(saved);
}};
const c=core.createSavedDocxLayoutController(options);await c.open(reviewId);const d=copy(c.snapshot().decisions);d.review.note='Private fictional wording';c.edit(d,{reviewOnly:true});await c.save();const pending=c.snapshot();await c.save();
const restored=core.createSavedDocxLayoutController(options);await restored.read();const recovered=restored.snapshot();
scope.workspaceId='different-workspace';restored.sync();
console.log(JSON.stringify({pending,recovered,cleared:restored.snapshot(),posts:requests.filter(r=>r.body),stored:[...storage.data.values()]}));
""")
    assert result["pending"]["pending"]["kind"] == "save"
    assert len(result["posts"]) == 2 and result["posts"][0]["body"] == result["posts"][1]["body"]
    assert result["recovered"]["view"]["generation"] == 1
    assert result["cleared"]["view"] is None and result["cleared"]["decisions"] is None
    assert all("Private" not in raw and "Fictional notice" not in raw for raw in result["stored"])


def test_import_dom_uses_two_files_and_language_then_list_recovers_lost_response_after_reload():
    result = probe(DOM + r"""
const storage=memory(),calls=[];let imported=false;
const options={getScope:()=>scope,storage,createNonce:()=> 'b'.repeat(32),request:async(url,owner,options)=>{
 calls.push({path:path(url),owner,fields:options.body instanceof FormData?[...options.body.keys()]:null,
   lang:options.body instanceof FormData?options.body.get('target_lang'):null,
   nonce:options.body instanceof FormData?options.body.get('import_nonce'):null});
 if(path(url).endsWith('/imports')){imported=true;throw new Error('Lost import response');}
 if(path(url).endsWith('/capabilities'))return envelope({available:true});
 if(path(url).endsWith('/reviews'))return envelope(imported?[{review_id:reviewId,import_nonce:'b'.repeat(32),target_lang:'FR',page_count:1,status:'imported'}]:[]);
 return envelope({...draft,target_lang:'FR',import_nonce:'b'.repeat(32)});
}};
const mounted=ui.mountSavedDocxLayout({root,...options});
const pdf=fieldControl('Original source PDF (up to 64 MiB)'),word=fieldControl('Current saved Word document (up to 32 MiB)');
pdf.files=[new Blob(['fictional pdf'],{type:'application/pdf'})];word.files=[new Blob(['fictional docx'])];await pdf.fire('change');await word.fire('change');
await fill('Word document language','FR','SELECT','change');await findButton('Import for formatting').fire('click');
const restored=core.createSavedDocxLayoutController({...options,createNonce:()=>{throw new Error('No replacement nonce');}});await restored.initialize();
console.log(JSON.stringify({calls,state:restored.snapshot(),stored:[...storage.data.values()],unsafeWrites}));
""")
    imports = [call for call in result["calls"] if call["path"].endswith("/imports")]
    assert len(imports) == 1
    assert imports[0]["fields"] == ["source_pdf", "saved_docx", "target_lang", "import_nonce"]
    assert imports[0]["lang"] == "FR" and imports[0]["nonce"] == "b" * 32
    assert result["state"]["pending"] is None and result["state"]["view"]["target_lang"] == "FR"
    assert result["unsafeWrites"] == 0 and all("fictional pdf" not in value for value in result["stored"])


def test_lost_save_recovers_after_restart_and_conflict_requires_explicit_discard():
    result = probe(r"""
const storage=memory();let saved=copy(draft),mode='lost';
const options={getScope:()=>scope,storage,createNonce:()=> 'b'.repeat(32),request:async(url,owner,options)=>{
 if(options.method==='POST'){const body=JSON.parse(options.body);saved={...saved,generation:1,decisions:body.decisions,saves:[{save_nonce:body.save_nonce,generation:1}]};throw new Error('Lost');}return envelope(saved);
}};
const c=core.createSavedDocxLayoutController(options);await c.open(reviewId);await c.save();
const restored=core.createSavedDocxLayoutController(options);await restored.read();const recovered=restored.snapshot();
const d=copy(restored.snapshot().decisions);d.review.note='Local edit';restored.edit(d,{reviewOnly:true});await restored.save();
saved.generation=3;saved.decisions.review.note='Other tab';await restored.read();const conflict=restored.snapshot();
const discard=restored.discardChanges();console.log(JSON.stringify({recovered,conflict,discard,final:restored.snapshot()}));
""")
    assert result["recovered"]["pending"] is None and not result["recovered"]["dirty"]
    assert result["conflict"]["conflict"] and result["conflict"]["decisions"]["review"]["note"] == "Local edit"
    assert result["discard"] and result["final"]["decisions"]["review"]["note"] == "Other tab"


def test_build_response_loss_reuses_nonce_and_only_associated_artifacts_download():
    result = probe(r"""
const storage=memory(),posts=[];let saved=complete(),fail=true;
const options={getScope:()=>scope,storage,createNonce:()=> 'c'.repeat(32),request:async(url,owner,options)=>{
 if(options.method==='POST'){const body=JSON.parse(options.body);posts.push(body);
 if(![...storage.data.values()].some(v=>v.includes(body.operation_nonce)))throw new Error('Missing durable pointer');
 saved.builds=[{operation_nonce:body.operation_nonce,generation:1,status:'built',artifact_id:'d'.repeat(32)}];saved.artifacts=[{artifact_id:'d'.repeat(32),generation:1,kinds:['docx','source_map','receipt']}];
 if(fail){fail=false;throw new Error('Lost build response');}}return envelope(saved);
}};
const c=core.createSavedDocxLayoutController(options);await c.open(reviewId);await c.build();
const recovered=core.createSavedDocxLayoutController({...options,createNonce:()=>{throw new Error('No new nonce');}});await recovered.read();
const artifact=recovered.snapshot().view.artifacts[0],url=recovered.artifactUrl(artifact);saved.builds=[];await recovered.read();
console.log(JSON.stringify({posts,url,pending:recovered.snapshot().pending,unassociated:recovered.artifactUrl(artifact),foreign:recovered.artifactUrl({artifact_id:'e'.repeat(32)})}));
""")
    assert result["posts"] == [{"expected_generation": 1, "operation_nonce": "c" * 32, "review_confirmed": True}]
    assert "/artifacts/" + "d" * 32 + "/docx?" in result["url"]
    assert "mode=shadow" in result["url"] and "workspace_id=fictional-layout" in result["url"]
    assert not result["unassociated"] and not result["foreign"]


def test_stale_scope_response_is_discarded_and_no_request_uses_provider_job_readiness():
    result = probe(r"""
let resolve;const delayed=new Promise(done=>{resolve=done;});const c=core.createSavedDocxLayoutController({getScope:()=>scope,storage:memory(),request:async()=>delayed});
const opening=c.open(reviewId);scope.runtimeMode='live';c.sync();resolve(envelope(draft));await opening;
console.log(JSON.stringify(c.snapshot()));
""")
    assert result["owner"]["runtimeMode"] == "live" and result["view"] is None
    assert result["decisions"] is None and not result["busy"]


def test_build_busy_and_incomplete_conflicts_recover_only_after_read_and_explicit_action():
    result = probe(r"""
let saved=complete(),scenario='busy',n=0;const posts=[];
const c=core.createSavedDocxLayoutController({getScope:()=>scope,storage:memory(),createNonce:()=>String(++n).padStart(32,'a'),request:async(url,owner,options)=>{
 if(options.method==='POST'){
  const body=JSON.parse(options.body);posts.push(body);
  if(scenario==='busy'){const e=new Error('busy');e.status=409;e.payload={diagnostics:{error:'saved_docx_layout_busy'}};throw e;}
  if(scenario==='incomplete'){saved.builds=[{operation_nonce:body.operation_nonce,generation:1,status:'incomplete'}];const e=new Error('incomplete');e.status=409;e.payload={diagnostics:{error:'saved_docx_layout_build_incomplete'}};throw e;}
  saved.builds=[...saved.builds,{operation_nonce:body.operation_nonce,generation:1,status:'built',artifact_id:'d'.repeat(32)}];saved.artifacts=[{artifact_id:'d'.repeat(32),generation:1,kinds:['docx']}];
 }return envelope(saved);
}});
await c.open(reviewId);await c.build();const busy=c.snapshot();await c.read();const afterBusyRead=c.snapshot(),before=posts.length;
scenario='incomplete';await c.build();await c.read();const incomplete=c.snapshot();const beforeNew=posts.length;
scenario='success';await c.build({newAttempt:true});console.log(JSON.stringify({busy,afterBusyRead,before,incomplete,beforeNew,posts,final:c.snapshot()}));
""")
    assert result["busy"]["conflict"] and not result["afterBusyRead"]["conflict"]
    assert result["before"] == 1 and result["beforeNew"] == 2
    assert result["posts"][0] == result["posts"][1]
    assert result["posts"][2]["operation_nonce"] != result["posts"][1]["operation_nonce"]
    assert not result["incomplete"]["conflict"] and result["final"]["pending"] is None


def test_reloaded_save_that_never_arrived_displays_saved_decisions_and_explicit_dom_discard():
    result = probe(DOM + r"""
const storage=memory();storage.setItem('legalpdf:saved-docx-layout:v1:shadow:fictional-layout',JSON.stringify({reviewId,pending:{kind:'save',nonce:'b'.repeat(32),generation:0}}));
let requests=0;const mounted=ui.mountSavedDocxLayout({root,getScope:()=>scope,storage,request:async()=>{requests++;return envelope(draft);}});
await findButton('Read current saved review').fire('click');const before=mounted.controller.snapshot(),retryDisabled=findButton('Retry the exact save').disabled;
await findButton('Discard local edits and use the last read saved review').fire('click');
console.log(JSON.stringify({before,retryDisabled,requests,after:mounted.controller.snapshot(),unsafeWrites}));
""")
    assert result["before"]["decisions"] and result["before"]["pending"]["kind"] == "save"
    assert result["retryDisabled"] and result["requests"] == 1
    assert result["after"]["pending"] is None and not result["after"]["conflict"]
    assert result["unsafeWrites"] == 0


def test_repeated_reads_do_not_rebase_stale_unsaved_edits_and_absent_build_can_be_abandoned():
    result = probe(r"""
let saved=complete();const c=core.createSavedDocxLayoutController({getScope:()=>scope,storage:memory(),request:async()=>envelope(saved)});
await c.open(reviewId);const local=copy(c.snapshot().decisions);local.review.note='Local draft';c.edit(local,{reviewOnly:true});
saved.generation=2;saved.decisions.review.note='Other tab';await c.read();const first=c.snapshot();await c.read();const second=c.snapshot();
c.discardChanges();const resolved=c.snapshot();
const storage=memory();storage.setItem('legalpdf:saved-docx-layout:v1:shadow:fictional-layout',JSON.stringify({reviewId,pending:{kind:'build',nonce:'c'.repeat(32),generation:1}}));
const pending=core.createSavedDocxLayoutController({getScope:()=>scope,storage,request:async()=>envelope(saved)});const beforeRead=pending.discardChanges();await pending.read();const current=pending.snapshot();const discarded=pending.discardChanges();
console.log(JSON.stringify({first,second,resolved,beforeRead,current,discarded,final:pending.snapshot()}));
""")
    assert result["first"]["conflict"] and result["second"]["conflict"]
    assert result["second"]["decisions"]["review"]["note"] == "Local draft"
    assert result["resolved"]["decisions"]["review"]["note"] == "Other tab"
    assert not result["beforeRead"] and result["current"]["canAbandonBuild"]
    assert result["discarded"] and result["final"]["pending"] is None


def test_dom_declines_browser_normalized_crlf_phrase_offsets_but_keeps_paragraph_styling():
    result = probe(DOM + r"""
const create=doc.createElement;
doc.createElement=(tag)=>{const node=create(tag);if(tag==='textarea'){let value='';Object.defineProperty(node,'value',{
 get:()=>value,set:(next)=>{value=String(next).replace(/\r\n?/g,'\n');}});}return node;};
const saved=copy(draft);saved.paragraphs[0].text='Fictional\r\nnotice';
const mounted=ui.mountSavedDocxLayout({root,getScope:()=>scope,storage:memory(),request:async()=>envelope(saved)});
await mounted.controller.open(reviewId);const text=fieldControl('Select exact phrase in immutable text','TEXTAREA');
text.selectionStart=10;text.selectionEnd=16;await findButton('Add phrase bold').fire('click');
const errorShown=root.textContent.includes('This browser normalizes line endings'),before=mounted.controller.snapshot();
const bold=fieldControl('Add bold to selected paragraphs');bold.checked=true;await bold.fire('change');
console.log(JSON.stringify({errorShown,before,after:mounted.controller.snapshot(),unsafeWrites}));
""")
    assert result["errorShown"] and result["before"]["decisions"]["paragraphs"][0]["emphasis"] == []
    assert result["after"]["decisions"]["paragraphs"][0]["bold"]
    assert result["after"]["view"]["paragraphs"][0]["text"] == "Fictional\r\nnotice"
    assert result["unsafeWrites"] == 0


def test_dom_mapping_styles_columns_phrase_review_build_and_hostile_text_safe():
    result = probe(DOM + r"""
const requests=[];let saved=copy(draft);saved.paragraphs[2].text='<img src=x onerror=alert(1)> نص تجريبي';
const mounted=ui.mountSavedDocxLayout({root,getScope:()=>scope,storage:memory(),createNonce:()=> 'c'.repeat(32),request:async(url,owner,options)=>{
 const body=options.body?JSON.parse(options.body):null;requests.push({url,body});
 if(path(url).endsWith('/decisions'))saved={...saved,status:'reviewed',generation:1,decisions:body.decisions,saves:[{save_nonce:body.save_nonce,generation:1}]};
 if(path(url).endsWith('/builds'))saved={...saved,status:'built',builds:[{operation_nonce:body.operation_nonce,generation:1,status:'built',artifact_id:'d'.repeat(32)}],artifacts:[{artifact_id:'d'.repeat(32),generation:1,kinds:['docx','source_map','receipt']}]};
 return envelope(saved);
}});
const change=async(label,value,tag='INPUT')=>fill(label,value,tag,'change');
const tick=async(label,value=true)=>{const node=fieldControl(label);node.checked=value;await node.fire('change');};
await mounted.controller.open(reviewId);
await change('Range ends at paragraph','4');
const image=walk(root).find(n=>n.tagName==='IMG');await image.fire('pointerdown',{clientX:15,clientY:25});await image.fire('pointerup',{clientX:100,clientY:150});
await findButton('Associate selected region').fire('click');
await change('Range ends at paragraph','3');await change('Paragraphs in left column','2');await findButton('Create two physical columns').fire('click');
await findButton('Paragraph 2').fire('click');await findButton('Use a shaded notice panel').fire('click');
await change('Role','heading','SELECT');await change('Heading size (pt; blank preserves original)','14');
await findButton('Paragraph 1').fire('click');const phrase=fieldControl('Select exact phrase in immutable text','TEXTAREA');const immutable=phrase.readOnly;
phrase.selectionStart=10;phrase.selectionEnd=16;await findButton('Add phrase bold').fire('click');
let nextPhrase=fieldControl('Select exact phrase in immutable text','TEXTAREA');nextPhrase.selectionStart=10;nextPhrase.selectionEnd=16;await findButton('Add phrase underline').fire('click');
nextPhrase=fieldControl('Select exact phrase in immutable text','TEXTAREA');nextPhrase.selectionStart=0;nextPhrase.selectionEnd=9;await findButton('Add phrase italic').fire('click');
await tick('I reviewed every visible group on this source page');await change('Reviewer','Fictional operator');await change('Review note and retained source differences','All fictional page groups compared','TEXTAREA');
await tick('I reviewed all wording, source associations, layout ownership and retained differences');
await findButton('Save formatting review').fire('click');await findButton('Build separate Word copy').fire('click');
console.log(JSON.stringify({requests,immutable,unsafeWrites,final:mounted.controller.snapshot(),links:walk(root).filter(n=>n.tagName==='A').map(n=>n.href),hostileShown:root.textContent.includes('<img src=x onerror=alert(1)>')}));
""")
    assert result["immutable"] and result["unsafeWrites"] == 0 and result["hostileShown"]
    posts = [r for r in result["requests"] if r["body"]]
    assert len(posts) == 2
    saved = posts[0]["body"]["decisions"]
    assert all(p["regions"] == [{"page_number": 1, "bbox_px": [10, 10, 180, 260]}] for p in saved["paragraphs"])
    assert saved["bands"][0]["cells"][0]["groups"][1] == {"paragraph_ids": ["p000002"], "panel": True}
    assert saved["paragraphs"][1]["heading_size_pt"] == 14
    assert saved["paragraphs"][0]["emphasis"] == [
        {"start": 0, "end": 9, "bold": False, "italic": True, "underline": False},
        {"start": 10, "end": 16, "bold": True, "italic": False, "underline": True}]
    assert saved["review"]["document_reviewed"] and len(result["links"]) == 3
    assert not any(key in posts[0]["body"] for key in ("mode", "workspace_id", "job_id", "replacement_text"))


def test_disclosure_mount_is_outside_translation_task_and_has_no_readiness_dependency():
    base = Path(__file__).resolve().parents[1] / "src/legalpdf_translate/shadow_web"
    template = (base / "templates/index.html").read_text(encoding="utf-8")
    app = (base / "static/app.js").read_text(encoding="utf-8")
    controller = (base / "static/saved_docx_layout.js").read_text(encoding="utf-8")
    assert template.index('id="saved-docx-layout-disclosure"') < template.index('data-task-panel="translation"')
    assert 'mountSavedDocxLayout({ root: document.getElementById("saved-docx-layout-editor"), getScope: () => appState });' in app
    assert "getJob" not in controller and "provider" not in controller


@pytest.mark.parametrize("language", ["EN", "FR", "AR"])
def test_dom_authored_decisions_pass_real_owned_api_service_writer_and_download(tmp_path, monkeypatch, language):
    """Replay actual DOM-authored request bodies through the real isolated HTTP/service boundary."""
    from io import BytesIO
    from zipfile import ZipFile
    from fastapi.testclient import TestClient
    from legalpdf_translate import saved_docx_layout_service as service_module
    from .test_saved_docx_layout_service import fake_prepare
    from .test_shadow_web_saved_docx_layout_api import HEADERS, actual_app, fictional_files, import_file, value

    monkeypatch.setattr(service_module, "_prepare_import", fake_prepare)
    files = fictional_files(language)
    with TestClient(actual_app(tmp_path, monkeypatch)) as client:
        imported = value(import_file(client, language, files=files))
        result = probe(DOM + r"""
scope.workspaceId='layout-test';let current=copy(data),nonce=0;const requests=[];
const mounted=ui.mountSavedDocxLayout({root,getScope:()=>scope,storage:memory(),createNonce:()=>String(++nonce).padStart(32,'b'),request:async(url,owner,options)=>{
 const body=options.body?JSON.parse(options.body):null;
 if(body){requests.push({url,body});if(path(url).endsWith('/decisions'))current={...current,generation:current.generation+1,decisions:body.decisions,status:'reviewed',saves:[{save_nonce:body.save_nonce,generation:current.generation+1}]};}
 return envelope(current);
}});
const change=async(label,value,tag='INPUT')=>fill(label,value,tag,'change');
const tick=async(label)=>{const n=fieldControl(label);n.checked=true;await n.fire('change');};
await mounted.controller.open(data.review_id);await change('Range ends at paragraph','4');
const image=walk(root).find(n=>n.tagName==='IMG');await image.fire('pointerdown',{clientX:15,clientY:25});await image.fire('pointerup',{clientX:100,clientY:150});await findButton('Associate selected region').fire('click');
await change('Paragraphs in left column','2');await findButton('Create two physical columns').fire('click');
await findButton('Paragraph 3').fire('click');await findButton('Use a shaded notice panel').fire('click');await change('Role','heading','SELECT');await change('Heading size (pt; blank preserves original)','14');
const phrase=fieldControl('Select exact phrase in immutable text','TEXTAREA');phrase.selectionStart=0;phrase.selectionEnd=phrase.value.length;await findButton('Add phrase bold').fire('click');
await tick('I reviewed every visible group on this source page');await change('Reviewer','Fictional browser reviewer');await change('Review note and retained source differences','All fictional source groups compared','TEXTAREA');await tick('I reviewed all wording, source associations, layout ownership and retained differences');
await findButton('Save formatting review').fire('click');await findButton('Build separate Word copy').fire('click');console.log(JSON.stringify({requests,unsafeWrites}));
""", data=imported)
        assert result["unsafeWrites"] == 0 and len(result["requests"]) == 2
        saved_request, build_request = result["requests"]
        saved = value(client.post(saved_request["url"], headers=HEADERS, json=saved_request["body"]))
        assert saved["decisions"]["review"]["document_reviewed"]
        built = value(client.post(build_request["url"], headers=HEADERS, json=build_request["body"]))
        artifact = built["artifacts"][0]
        response = client.get(f"/api/saved-docx-layout/reviews/{imported['review_id']}/artifacts/{artifact['artifact_id']}/docx", headers=HEADERS)
        assert response.status_code == 200
        with ZipFile(BytesIO(files[1])) as original, ZipFile(BytesIO(response.content)) as output:
            assert all(original.read(name) == output.read(name) for name in original.namelist() if name != "word/document.xml")
        receipt_response = client.get(f"/api/saved-docx-layout/reviews/{imported['review_id']}/artifacts/{artifact['artifact_id']}/receipt", headers=HEADERS)
        assert receipt_response.status_code == 200
        assert json.loads(receipt_response.content)["rendered_layout_acceptance"] == "not_evaluated"
