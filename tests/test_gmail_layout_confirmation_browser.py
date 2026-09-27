"""Real Gmail confirmation events with fictional UI state and local fetch only."""

import json

import pytest

from .browser_esm_probe import run_browser_esm_json_probe


DOM = r'''
const ids=new Map(),requests=[];let unsafeWrites=0;
function make(tag='div',id=''){
 const handlers=new Map();let ownText='';
 const n={id,tagName:tag.toUpperCase(),children:[],dataset:{},style:{},attributes:{},value:'',disabled:false,
  appendChild(child){this.children.push(child);return child;},append(...children){this.children.push(...children);},
  replaceChildren(...children){this.children=children;ownText='';},setAttribute(k,v){this.attributes[k]=String(v);},
  removeAttribute(k){delete this.attributes[k];},addEventListener(type,fn){if(!handlers.has(type))handlers.set(type,[]);handlers.get(type).push(fn);},
  querySelector(){return null;},querySelectorAll(){return [];},closest(){return null;},
  async fire(type){for(const fn of handlers.get(type)||[])await fn({target:this,preventDefault(){}});}
 };
 n.classList={add(){},remove(){},toggle(){},contains(){return false;}};
 Object.defineProperty(n,'textContent',{get(){return ownText+n.children.map(c=>c.textContent).join('');},set(v){ownText=String(v);n.children=[];}});
 Object.defineProperty(n,'innerHTML',{set(){unsafeWrites++;throw new Error('Unsafe HTML');}});
 if(id)ids.set(id,n);return n;
}
globalThis.document={body:make('body'),hidden:false,createElement:tag=>make(tag),getElementById:id=>ids.get(id)||null,
 querySelectorAll:()=>[],addEventListener(){}};
globalThis.window={location:{href:'http://127.0.0.1:8888/?mode=shadow&workspace=fictional'},
 addEventListener(){},dispatchEvent(){},setTimeout(){return 1;},clearTimeout(){},sessionStorage:{getItem(){return null;},setItem(){},removeItem(){}}};
globalThis.CustomEvent=class{constructor(type){this.type=type;}};
make('button','gmail-confirm-translation');make('div','gmail-session-status');make('pre','gmail-session-diagnostics');
make('input','translation-row-id').value='42';
globalThis.fetch=async(url,options={})=>{
 if(String(url)!=='/api/gmail/batch/confirm-current')throw new Error('Unexpected request '+url);
 requests.push({url:String(url),body:JSON.parse(options.body)});
 return {ok:true,status:200,text:async()=>JSON.stringify({status:'ok',normalized_payload:{}})};
};
const {appState}=await import(__STATE__);appState.runtimeMode='shadow';appState.workspaceId='fictional';
const gmail=await import(__GMAIL__);
const ui={currentJobId:'fictional-job',currentJobKind:'translate',currentJobStatus:'completed',currentJobHasSaveSeed:true,
 ordinaryLayoutReady:true,ordinaryLayout:{status:'prepared',baseline_id:'a'.repeat(32),generation:1,delivery_generation:1,
 delivery:{kind:'reviewed',stale:false},stale:false}};
let collects=0;
'''


@pytest.mark.parametrize("scenario", ["pending_before", "newer_selection", "job_switch", "pending_after", "workspace_switch"])
def test_gmail_confirmation_rechecks_current_layout_after_collecting_form_values(scenario):
    result = run_browser_esm_json_probe(DOM + "\nconst scenario=" + json.dumps(scenario) + r''';
if(scenario==='pending_before')ui.ordinaryLayoutReady=false;
gmail.initializeGmailUi({getTranslationUiSnapshot:()=>structuredClone(ui),getCurrentTranslationJobId:()=>ui.currentJobId,
 collectCurrentTranslationSaveValues:async()=>{
  collects++;await Promise.resolve();
  if(scenario==='newer_selection'){ui.ordinaryLayout.delivery_generation=2;ui.ordinaryLayout.generation=3;}
  if(scenario==='job_switch')ui.currentJobId='another-job';
  if(scenario==='pending_after')ui.ordinaryLayoutReady=false;
  if(scenario==='workspace_switch')appState.workspaceId='another-workspace';
  return {case_number:'FICTIONAL/26',word_count:123};
 }});
await ids.get('gmail-confirm-translation').fire('click');
console.log(JSON.stringify({requests,collects,unsafeWrites,message:ids.get('gmail-session-status').textContent}));
''', {"__GMAIL__": "gmail.js", "__STATE__": "state.js"})
    assert result["unsafeWrites"] == 0
    assert result["collects"] == (0 if scenario == "pending_before" else 1)
    if scenario == "newer_selection":
        assert len(result["requests"]) == 1
        body = result["requests"][0]["body"]
        assert body["job_id"] == "fictional-job"
        assert body["baseline_id"] == "a" * 32
        assert body["expected_delivery_generation"] == 2
    else:
        assert result["requests"] == []
        assert result["message"]
