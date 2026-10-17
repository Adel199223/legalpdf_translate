"""Real editor module probes with safe DOM and server envelope boundaries."""
import json

import pytest

from .browser_esm_probe import run_browser_esm_json_probe
from .test_source_review_browser_state import DOM


def test_natural_editor_preserves_typing_across_passive_updates_and_safe_diff():
    result = run_browser_esm_json_probe(DOM + r"""
const {mountTextCorrection}=await import(__UI__);
if(!globalThis.crypto)globalThis.crypto=(await import('node:crypto')).webcrypto;
let job={job_id:'tx-fictional',status:'completed',result:{save_seed:{}}};
let state={parent:{sha256:'a',delivery_generation:0},source_pages:[1,2],paragraphs:[{paragraph_id:'p1',part_uri:'word/document.xml',editable:true,text:'النص [[ABC]] <img onerror=evil>'}],drafts:[],frozen:false};
const calls=[];
const request=async(url,scope,options)=>{calls.push({url,body:options.body});return {normalized_payload:{ordinary_layout:structuredClone(state)}};};
const editor=mountTextCorrection({root,getScope:()=>({runtimeMode:'shadow',workspaceId:'w1'}),getJob:()=>job,request});
await findButton('Correct translated text').fire('click');
const field=walk(root).find(n=>n.attributes['aria-label']==='Corrected paragraph text');
field.value='Arabic [[literal]] <script>never</script>';await field.fire('input');
editor.render();
const unchanged=walk(root).find(n=>n.attributes['aria-label']==='Corrected paragraph text')===field;
const pages=walk(root).find(n=>n.tagName==='SELECT');pages.value='2';await pages.fire('change');
const retained=walk(root).find(n=>n.attributes['aria-label']==='Corrected paragraph text').value;
editor.dispose();editor.render();
console.log(JSON.stringify({unchanged,retained,unsafeWrites,disposed:root.children.length===0,calls:calls.length}));
""", {"__UI__":"text_correction_ui.js"})
    assert result == {"unchanged": True, "retained": "Arabic [[literal]] <script>never</script>", "unsafeWrites": 0, "disposed": True, "calls": 1}


def test_control_rejection_explains_preserved_page_breaks_without_promising_unsupported_editor():
    result = run_browser_esm_json_probe(DOM + r"""
const {mountTextCorrection}=await import(__UI__);
if(!globalThis.crypto)globalThis.crypto=(await import('node:crypto')).webcrypto;
const job={job_id:'tx-fictional',status:'completed',result:{save_seed:{}}};
const state={parent:{sha256:'a',delivery_generation:0},source_pages:[1],paragraphs:[{paragraph_id:'p1',part_uri:'word/document.xml',editable:false,text:'Protected paragraph'}],drafts:[],frozen:false};
const request=async(url,scope,options)=>{
  if(options.body){const error=new Error('correction_paragraph_controls');error.payload={diagnostics:{error:'correction_paragraph_controls'}};throw error;}
  return {normalized_payload:{ordinary_layout:structuredClone(state)}};
};
mountTextCorrection({root,getScope:()=>({runtimeMode:'shadow',workspaceId:'w1'}),getJob:()=>job,request});
await findButton('Correct translated text').fire('click');
await findButton('Review text changes saved in Word').fire('click');
const alert=walk(root).find(n=>n.attributes.role==='alert');
console.log(JSON.stringify({message:alert.textContent,unsafeWrites}));
""", {"__UI__":"text_correction_ui.js"})
    assert "page breaks unchanged" in result["message"]
    assert "Word edits are preserved" in result["message"]
    assert "enter the corrections in this editor instead" not in result["message"]
    assert result["unsafeWrites"] == 0


@pytest.mark.parametrize("busy_count", [1, 2, 10])
def test_editor_open_retries_only_bounded_busy_reads(busy_count):
    result = run_browser_esm_json_probe(DOM + "\nconst busyCount = " + str(busy_count) + r""";
const {mountTextCorrection}=await import(__UI__);
const job={job_id:'tx-fictional',status:'completed',result:{save_seed:{}}};
const state={parent:{sha256:'a',delivery_generation:0},source_pages:[1],paragraphs:[],drafts:[],frozen:false};
let calls=0;const delays=[];
globalThis.setTimeout=(resolve,delay)=>{delays.push(delay);queueMicrotask(resolve);};
const request=async(url,scope,options)=>{
  if(options.method||options.body)throw new Error('Unexpected mutation');
  if(++calls<=busyCount){const error=new Error('busy');error.payload={diagnostics:{error:'ordinary_layout_workspace_busy'}};error.status=409;throw error;}
  return {normalized_payload:{ordinary_layout:state}};
};
mountTextCorrection({root,getScope:()=>({runtimeMode:'shadow',workspaceId:'w1'}),getJob:()=>job,request});
await findButton('Correct translated text').fire('click');
console.log(JSON.stringify({calls,delays,alert:walk(root).find(n=>n.attributes.role==='alert')?.textContent||'',
  editable:walk(root).some(n=>n.attributes['aria-label']==='Corrected paragraph text'),unsafeWrites}));
""", {"__UI__": "text_correction_ui.js"})
    assert result["calls"] == min(busy_count + 1, 3)
    assert result["delays"] == [150, 300][:min(busy_count, 2)]
    assert result["editable"] is (busy_count < 3)
    assert result["unsafeWrites"] == 0
    if busy_count < 3:
        assert result["alert"] == ""
    else:
        assert "Another document review operation is still running" in result["alert"]
        assert "Close text correction and try again" in result["alert"]
        assert "Word edits are preserved" in result["alert"]


@pytest.mark.parametrize("code,diagnostic", [
    ("ordinary_layout_correction_parent_stale", True),
    ("ordinary_layout_workspace_busy_extra", True),
    ("ordinary_layout_workspace_busy", False),
])
def test_editor_open_preserves_other_errors_without_retry(code, diagnostic):
    result = run_browser_esm_json_probe(DOM + "\nconst config = " + json.dumps({"code": code, "diagnostic": diagnostic}) + r""";
const {mountTextCorrection}=await import(__UI__);
let calls=0;const delays=[];
globalThis.setTimeout=(resolve,delay)=>{delays.push(delay);queueMicrotask(resolve);};
const request=async()=>{calls++;const error=new Error(config.code);error.status=409;
  if(config.diagnostic)error.payload={diagnostics:{error:config.code}};throw error;};
mountTextCorrection({root,getScope:()=>({runtimeMode:'shadow',workspaceId:'w1'}),
  getJob:()=>({job_id:'tx-fictional',status:'completed',result:{save_seed:{}}}),request});
await findButton('Correct translated text').fire('click');
console.log(JSON.stringify({calls,delays,alert:walk(root).find(n=>n.attributes.role==='alert').textContent,unsafeWrites}));
""", {"__UI__": "text_correction_ui.js"})
    assert result["calls"] == 1
    assert result["delays"] == []
    assert result["unsafeWrites"] == 0
    if "stale" in code:
        assert "selected document changed" in result["alert"]


def test_editor_does_not_retry_busy_mutation_or_explicit_refresh():
    result = run_browser_esm_json_probe(DOM + r"""
const {mountTextCorrection}=await import(__UI__);
if(!globalThis.crypto)globalThis.crypto=(await import('node:crypto')).webcrypto;
const state={parent:{sha256:'a',delivery_generation:0},source_pages:[1],paragraphs:[],drafts:[],frozen:false};
const calls=[],delays=[];
globalThis.setTimeout=(resolve,delay)=>{delays.push(delay);queueMicrotask(resolve);};
const request=async(url,scope,options)=>{calls.push(options.method||'GET');
  if(calls.length>1){const error=new Error('busy');error.payload={diagnostics:{error:'ordinary_layout_workspace_busy'}};throw error;}
  return {normalized_payload:{ordinary_layout:state}};};
mountTextCorrection({root,getScope:()=>({runtimeMode:'shadow',workspaceId:'w1'}),
  getJob:()=>({job_id:'tx-fictional',status:'completed',result:{save_seed:{}}}),request});
await findButton('Correct translated text').fire('click');
await findButton('Review text changes saved in Word').fire('click');
await findButton('Refresh correction').fire('click');
console.log(JSON.stringify({calls,delays,unsafeWrites}));
""", {"__UI__": "text_correction_ui.js"})
    assert result == {"calls": ["GET", "POST", "GET"], "delays": [], "unsafeWrites": 0}


@pytest.mark.parametrize("stop", ["owner", "dispose"])
def test_editor_busy_retry_stops_when_owner_changes_or_editor_is_disposed(stop):
    result = run_browser_esm_json_probe(DOM + "\nconst stop = " + json.dumps(stop) + r""";
const {mountTextCorrection}=await import(__UI__);
let job={job_id:'tx-fictional',status:'completed',result:{save_seed:{}}};
let calls=0;const delays=[];
const request=async()=>{calls++;const error=new Error('busy');error.payload={diagnostics:{error:'ordinary_layout_workspace_busy'}};throw error;};
const editor=mountTextCorrection({root,getScope:()=>({runtimeMode:'shadow',workspaceId:'w1'}),getJob:()=>job,request});
globalThis.setTimeout=(resolve,delay)=>{delays.push(delay);
  if(stop==='owner'){job={...job,job_id:'tx-next'};editor.render();}else editor.dispose();
  queueMicrotask(resolve);};
await findButton('Correct translated text').fire('click');
console.log(JSON.stringify({calls,delays,alert:walk(root).some(n=>n.attributes.role==='alert'),unsafeWrites}));
""", {"__UI__": "text_correction_ui.js"})
    assert result == {"calls": 1, "delays": [150], "alert": False, "unsafeWrites": 0}
