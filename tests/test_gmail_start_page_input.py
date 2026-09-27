"""Actual Gmail event bindings and request payloads; no server/PDF runtime."""

from .browser_esm_probe import run_browser_esm_json_probe


def test_input_before_submit_uses_latest_start_page_without_blur_or_editor_replacement():
    result = run_browser_esm_json_probe(r"""
import fs from 'node:fs/promises';
// This copy belongs only to the ESM probe's temporary workspace. Keep gmail.js
// and its event/request builders real; PDF decoding is outside this regression.
await fs.writeFile(new URL('./browser_pdf.js', __GMAIL__), `
export async function ensureBrowserPdfBundleFromUrl() { return {page_count:12}; }
export async function renderBrowserPdfPreviewToCanvas() { throw new Error('Unexpected PDF canvas'); }
export function browserPdfDiagnosticsFromError() { return {}; }
`);
const ids=new Map(), requests=[]; let unsafeWrites=0;
function walk(n){ return [n,...n.children.flatMap(walk)]; }
function make(tag='div',id=''){
 const handlers=new Map(); let ownText='';
 const n={id,tagName:tag.toUpperCase(),children:[],dataset:{},style:{},attributes:{},value:'',checked:false,disabled:false,
  appendChild(child){child.parentNode=this;this.children.push(child);return child;},
  append(...children){children.forEach(c=>this.appendChild(c));},
  replaceChildren(...children){this.children=[];ownText='';children.forEach(c=>this.appendChild(c));},
  setAttribute(k,v){this.attributes[k]=String(v);},removeAttribute(k){delete this.attributes[k];},
  addEventListener(type,fn){if(!handlers.has(type))handlers.set(type,[]);handlers.get(type).push(fn);},
  closest(selector){
   const key=selector.match(/^\[data-(.+)\]$/)?.[1]?.replace(/-([a-z])/g,(_,c)=>c.toUpperCase());
   return key && Object.hasOwn(this.dataset,key)?this:this.parentNode?.closest(selector)||null;
  },
  querySelector(selector){return walk(this).find(x=>x!==this && (selector.startsWith('[')?x.closest(selector)===x:x.tagName===selector.toUpperCase()))||null;},
  querySelectorAll(selector){return walk(this).filter(x=>x!==this && x.closest(selector)===x);},
  async fire(type,target=this){for(const fn of handlers.get(type)||[])await fn({target,preventDefault(){},stopPropagation(){}});},
  focus(){document.activeElement=this;},
 };
 n.classList={add(){},remove(){},toggle(){},contains(){return false;}};
 Object.defineProperty(n,'textContent',{get(){return ownText+n.children.map(c=>c.textContent).join('');},set(v){ownText=String(v);n.children=[];}});
 Object.defineProperty(n,'innerHTML',{set(){unsafeWrites++;throw new Error('Unsafe HTML');}});
 if(id)ids.set(id,n);return n;
}
globalThis.document={body:make('body'),activeElement:null,hidden:false,createElement:tag=>make(tag),
 getElementById:id=>ids.get(id)||[...ids.values()].flatMap(walk).find(n=>n.id===id)||null,
 querySelectorAll:()=>[],addEventListener(){}};
const storage=new Map();
globalThis.window={location:{href:'http://127.0.0.1:8888/?mode=shadow&workspace=fictional'},
 addEventListener(){},dispatchEvent(){},setTimeout(){return 1;},clearTimeout(){},
 sessionStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)}};
globalThis.CustomEvent=class{constructor(type){this.type=type;}};
for(const id of ['gmail-attachment-list','gmail-review-detail','gmail-prepare-form'])make('div',id);
make('select','gmail-workflow-kind').value='translation';
make('select','gmail-target-lang').value='AR';
globalThis.fetch=async(url,options={})=>{
 const body=options.body?JSON.parse(options.body):null;requests.push({url:String(url),body});
 let normalized_payload={};
 if(String(url)==='/api/gmail/preview-attachment')normalized_payload={preview_path:'fictional.pdf',preview_href:'/fictional.pdf',page_count:12};
 else if(String(url)!=='/api/gmail/prepare-session')throw new Error('Unexpected request '+url);
 return {ok:true,status:200,text:async()=>JSON.stringify({status:'ok',normalized_payload})};
};
const state=await import(__STATE__);state.appState.runtimeMode='shadow';state.appState.workspaceId='fictional';
const gmail=await import(__GMAIL__);gmail.initializeGmailUi({});
gmail.renderGmailBootstrap({normalized_payload:{gmail:{defaults:{workflow_kind:'translation',target_lang:'AR'},
 load_result:{ok:true,message:{message_id:'fictional-message',attachments:[
 {attachment_id:'fictional-pdf',filename:'fictional.pdf',mime_type:'application/pdf',size_bytes:120},
 ]}},review_event_id:0}}});
const list=ids.get('gmail-attachment-list'),detail=ids.get('gmail-review-detail'),form=ids.get('gmail-prepare-form');
const checkbox=list.querySelector('[data-attachment-checkbox]');checkbox.checked=true;await list.fire('change',checkbox);
const editor=(container,key)=>container.querySelector(`[data-${key}-start-page]`);
const observations=[];
async function typeAndSubmit(container,key,value,event='input'){
 const node=editor(container,key);if(!node)throw new Error('Missing editor '+key);
 node.focus();node.value=value;await container.fire(event,node);
 const preserved=document.activeElement===node && editor(container,key)===node;
 const beforeSubmit=node.value;
 await form.fire('submit');
 const posted=requests.filter(r=>r.url==='/api/gmail/prepare-session').at(-1);
 if(!posted)throw new Error('No prepare request');
 observations.push({value,beforeSubmit,preserved,page:posted.body.selections[0].start_page});
}
await typeAndSubmit(list,'attachment','2');
await typeAndSubmit(detail,'detail','4');
// Multiple keystrokes must not replace the active control midway through typing.
let node=editor(detail,'detail');node.focus();node.value='';await detail.fire('input',node);
const emptyPreserved=node.value==='' && document.activeElement===node && editor(detail,'detail')===node;
node.value='1';await detail.fire('input',node);node.value='12';await detail.fire('input',node);
await form.fire('submit');
const multiDigit=requests.filter(r=>r.url==='/api/gmail/prepare-session').at(-1).body.selections[0].start_page;
await typeAndSubmit(list,'attachment','99');
await typeAndSubmit(detail,'detail','3','change');
// Two visible editors: the last input event owns the value; stale peer DOM must
// not overwrite it during submission.
await typeAndSubmit(list,'attachment','7');
console.log(JSON.stringify({observations,emptyPreserved,multiDigit,unsafeWrites,
  prepareCount:requests.filter(r=>r.url==='/api/gmail/prepare-session').length}));
""", {"__GMAIL__": "gmail.js", "__STATE__": "state.js"})
    assert [row["page"] for row in result["observations"]] == [2, 4, 12, 3, 7]
    assert all(row["preserved"] for row in result["observations"])
    assert [row["beforeSubmit"] for row in result["observations"]] == ["2", "4", "99", "3", "7"]
    assert result["emptyPreserved"] and result["multiDigit"] == 12
    assert result["prepareCount"] == 6 and result["unsafeWrites"] == 0
