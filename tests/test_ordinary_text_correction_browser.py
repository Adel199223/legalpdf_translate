"""Real editor module probes with safe DOM and server envelope boundaries."""
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
