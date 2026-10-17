"""Mounted Gmail stage controls, fictional bootstrap and local fetch only."""
import json

import pytest

from .browser_esm_probe import run_browser_esm_json_probe


DOM = r'''
const ids=new Map(), requests=[], preflightReleases=[]; let unsafeWrites=0, holdPreflight=false;
function make(tag='div',id='') {
 const handlers=new Map(), classes=new Set(); let ownText='';
 const n={id,tagName:tag.toUpperCase(),children:[],dataset:{},style:{},attributes:{},value:'',disabled:false,
  appendChild(c){this.children.push(c);return c;},append(...c){this.children.push(...c);},
  replaceChildren(...c){this.children=c;ownText='';},setAttribute(k,v){this.attributes[k]=String(v);},
  removeAttribute(k){delete this.attributes[k];},addEventListener(t,f){if(!handlers.has(t))handlers.set(t,[]);handlers.get(t).push(f);},
  querySelector(){return null;},querySelectorAll(){return [];},closest(){return null;},
  fire(t){for(const f of handlers.get(t)||[])f({target:this,currentTarget:this,preventDefault(){}});}
 };
 n.classList={add(...cs){cs.forEach(c=>classes.add(c));},remove(...cs){cs.forEach(c=>classes.delete(c));},
  toggle(c,force){const add=force===undefined?!classes.has(c):force;add?classes.add(c):classes.delete(c);return add;},contains(c){return classes.has(c);}};
 Object.defineProperty(n,'textContent',{get(){return ownText+n.children.map(c=>c.textContent).join('');},set(v){ownText=String(v);n.children=[];}});
 Object.defineProperty(n,'innerHTML',{set(){unsafeWrites++;throw new Error('Unsafe HTML');}});
 if(id)ids.set(id,n);return n;
}
const windowHandlers=new Map();
globalThis.document={body:make('body'),hidden:false,createElement:t=>make(t),getElementById:id=>ids.get(id)||null,
 querySelectorAll:()=>[],addEventListener(){}};
globalThis.window={location:{href:'http://127.0.0.1:8888/?mode=shadow&workspace=fictional'},
 addEventListener(t,f){if(!windowHandlers.has(t))windowHandlers.set(t,[]);windowHandlers.get(t).push(f);},
 dispatchEvent(e){for(const f of windowHandlers.get(e.type)||[])f(e);},
 setTimeout(){return 1;},clearTimeout(){},sessionStorage:{getItem(){return null;},setItem(){},removeItem(){}}};
globalThis.CustomEvent=class{constructor(type){this.type=type;}};
for(const id of ['gmail-resume-step','gmail-workspace-strip-action','gmail-load-translation-launch'])make('button',id);
for(const id of ['gmail-workspace-strip','gmail-workspace-strip-title','gmail-workspace-strip-copy','gmail-session-status'])make('div',id);
const backdrop=make('div','gmail-batch-finalize-drawer-backdrop');backdrop.classList.add('hidden');
globalThis.fetch=async(url,options={})=>{
 const request={url:String(url),method:options.method||'GET',body:options.body?JSON.parse(options.body):null};requests.push(request);
 if(request.url!=='/api/gmail/batch/finalize-preflight')throw new Error('Unexpected request');
 if(holdPreflight)await new Promise(resolve=>preflightReleases.push(resolve));
 return {ok:true,status:200,text:async()=>JSON.stringify({status:'ok',normalized_payload:{active_session:session,finalization_preflight:{finalization_ready:true}}})};
};
const {appState}=await import(__STATE__);appState.runtimeMode='shadow';appState.workspaceId='fictional';appState.activeView='new-job';
const gmail=await import(__GMAIL__);
const session={kind:'translation',status:'confirmed',completed:true,session_id:'fictional-session',
 finalization_state:'ready_to_finalize',finalization_preflight:{finalization_ready:true},confirmed_items:[]};
let restores=0, releaseRestore, rejectRestore;
const ui={currentJobStatus:'completed'};
gmail.initializeGmailUi({getTranslationUiSnapshot:()=>ui,restoreGmailTranslationJob:async()=>{restores++;await new Promise((resolve,reject)=>{releaseRestore=resolve;rejectRestore=reject;});}});
function hydrate(launch=null){gmail.renderGmailBootstrap({normalized_payload:{gmail:{active_session:session,suggested_translation_launch:launch}}});}
async function settle(){for(let i=0;i<30;i++)await Promise.resolve();}
'''


@pytest.mark.parametrize("trigger", ["gmail-workspace-strip-action", "gmail-resume-step"])
def test_completed_session_finalize_opens_with_unavailable_launch_control(trigger):
    result = run_browser_esm_json_probe(DOM + "\nconst trigger=" + json.dumps(trigger) + r''';
hydrate();
const before={action:ids.get(trigger).dataset.gmailAction||ids.get(trigger).dataset.gmailStripAction,
 triggerDisabled:ids.get(trigger).disabled,launchDisabled:ids.get('gmail-load-translation-launch').disabled};
ids.get(trigger).fire('click');await settle();
console.log(JSON.stringify({before,open:!backdrop.classList.contains('hidden'),aria:backdrop.attributes['aria-hidden'],
 bodyState:document.body.dataset.gmailBatchFinalizeDrawer,requests,restores,unsafeWrites,
 launchStillDisabled:ids.get('gmail-load-translation-launch').disabled}));
''', {"__GMAIL__": "gmail.js", "__STATE__": "state.js"})
    assert result["before"] == {"action": "resume-translation-finalize", "triggerDisabled": False, "launchDisabled": True}
    assert result["open"] is True
    assert result["aria"] == "false"
    assert result["bodyState"] == "open"
    assert result["launchStillDisabled"] is True
    assert result["restores"] == result["unsafeWrites"] == 0
    assert result["requests"] == [{"url": "/api/gmail/batch/finalize-preflight", "method": "POST", "body": {"force_refresh": False}}]


def test_stage_guard_keeps_disabled_trigger_and_cross_trigger_inflight_protection():
    result = run_browser_esm_json_probe(DOM + r'''
session.completed=false;session.status='prepared';ui.currentJobStatus='failed';hydrate({source_path:'fictional.pdf'});
const strip=ids.get('gmail-workspace-strip-action'),resume=ids.get('gmail-resume-step'),launch=ids.get('gmail-load-translation-launch');
resume.disabled=true;resume.fire('click');await settle();const disabledStarts=restores;
resume.disabled=false;strip.fire('click');await settle();const firstStarts=restores;
// A normal state refresh can re-enable DOM controls while the first recovery awaits.
hydrate({source_path:'fictional.pdf'});resume.fire('click');launch.fire('click');await settle();const overlappingStarts=restores;
releaseRestore();await settle();
console.log(JSON.stringify({disabledStarts,firstStarts,overlappingStarts,requests,unsafeWrites,
 controlsReleased:!strip.disabled&&!resume.disabled&&!launch.disabled}));
''', {"__GMAIL__": "gmail.js", "__STATE__": "state.js"})
    assert result["disabledStarts"] == 0
    assert result["firstStarts"] == result["overlappingStarts"] == 1
    assert result["controlsReleased"] is True
    assert result["requests"] == []
    assert result["unsafeWrites"] == 0


def test_finalize_stage_guard_waits_for_preflight_across_rehydrated_controls():
    result = run_browser_esm_json_probe(DOM + r'''
hydrate();holdPreflight=true;
const strip=ids.get('gmail-workspace-strip-action'),resume=ids.get('gmail-resume-step');
strip.fire('click');await settle();
const pending={requests:requests.length,buttonsBusy:strip.disabled&&resume.disabled};
// Bootstrap rendering can legitimately re-enable the buttons while the POST waits.
hydrate();resume.fire('click');strip.fire('click');await settle();const overlappingRequests=requests.length;
holdPreflight=false;preflightReleases.forEach(resolve=>resolve());await settle();
console.log(JSON.stringify({pending,overlappingRequests,requests,unsafeWrites,
 open:!backdrop.classList.contains('hidden'),controlsReleased:!strip.disabled&&!resume.disabled,
 launchStillDisabled:ids.get('gmail-load-translation-launch').disabled}));
''', {"__GMAIL__": "gmail.js", "__STATE__": "state.js"})
    assert result["pending"] == {"requests": 1, "buttonsBusy": True}
    assert result["overlappingRequests"] == 1
    assert len(result["requests"]) == 1
    assert result["requests"][0]["url"] == "/api/gmail/batch/finalize-preflight"
    assert result["open"] is True
    assert result["controlsReleased"] is True
    assert result["launchStillDisabled"] is True
    assert result["unsafeWrites"] == 0


def test_stage_guard_releases_after_failed_recovery_without_retrying_it():
    result = run_browser_esm_json_probe(DOM + r'''
session.completed=false;session.status='prepared';ui.currentJobStatus='failed';hydrate({source_path:'fictional.pdf'});
ids.get('gmail-workspace-strip-action').fire('click');await settle();
rejectRestore(new Error('Fictional retained recovery unavailable'));await settle();
const afterFailure={restores,message:ids.get('gmail-session-status').textContent,
 enabled:!ids.get('gmail-resume-step').disabled&&!ids.get('gmail-workspace-strip-action').disabled};
ids.get('gmail-resume-step').fire('click');await settle();const explicitSecondStarts=restores;
releaseRestore();await settle();
console.log(JSON.stringify({afterFailure,explicitSecondStarts,requests,unsafeWrites}));
''', {"__GMAIL__": "gmail.js", "__STATE__": "state.js"})
    assert result["afterFailure"]["restores"] == 1
    assert result["afterFailure"]["enabled"] is True
    assert result["afterFailure"]["message"] == "Fictional retained recovery unavailable"
    assert result["explicitSecondStarts"] == 2
    assert result["requests"] == []
    assert result["unsafeWrites"] == 0
