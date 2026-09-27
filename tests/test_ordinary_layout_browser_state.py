"""Real browser modules with fictional owned API responses and no provider/native calls."""
import json

from .browser_esm_probe import run_browser_esm_json_probe
from .test_source_review_browser_state import DOM
from .test_saved_docx_layout_browser_state import PRELUDE as SAVED_PRELUDE

MODULES = {"__ORDINARY__":"ordinary_layout_review.js", "__ORDINARY_UI__":"ordinary_layout_review_ui.js",
           "__CORE__":"saved_docx_layout.js", "__UI__":"saved_docx_layout_ui.js"}
PRELUDE = SAVED_PRELUDE + r'''
const ordinary = await import(__ORDINARY__), ordinaryUi = await import(__ORDINARY_UI__);
scope.jobId='fictional-job';
let serial=0;
const nonce=()=> (++serial).toString(16).padStart(32,'0');
const baseline='e'.repeat(32), artifactId='f'.repeat(32);
const prepared=()=>({job_id:scope.jobId,status:'prepared',baseline_id:baseline,preparation_nonce:baseline,generation:1,
 review:complete(),delivery_generation:0,delivery:null,frozen:null,selected_pages:[1],output_reviews:[],suggestions:[],
 attached:true,stale:false,suggestion_capability:{available:true,model:'fictional-model',max_page_cost_usd:'0.812',max_operation_cost_usd:'2.436'}});
const ordinaryEnvelope=v=>({normalized_payload:{ordinary_layout:copy(v)}});
'''


def probe(script):
    return run_browser_esm_json_probe(PRELUDE + script, MODULES)


def test_paid_request_nonce_survives_lost_response_without_background_redispatch():
    result=probe(r'''
let saved=prepared(), lost=true;const calls=[], storage=memory();
const operation={status:'applied_unreviewed',operation_nonce:null,generation:2};
const options={getScope:()=>scope,storage,createNonce:nonce,request:async(url,owner,opts)=>{
 const body=opts.body?JSON.parse(opts.body):null;calls.push({url,body});
 if(body){operation.operation_nonce=body.operation_nonce;saved.generation=2;saved.review.generation=2;if(lost){lost=false;throw new Error('Response lost');}return ordinaryEnvelope(operation);}
 if(path(url).includes('/suggestions/'))return ordinaryEnvelope(operation);
 return ordinaryEnvelope(saved);
}};
const first=ordinary.createOrdinaryLayoutController(options);await first.read();await first.suggest([1]);const pending=first.snapshot();
const reopened=ordinary.createOrdinaryLayoutController(options);const beforeRead=calls.length;await reopened.read();
console.log(JSON.stringify({pending,recovered:reopened.snapshot(),background:calls.slice(beforeRead),posts:calls.filter(c=>c.body),stored:[...storage.data.values()]}));
''')
    assert result["pending"]["pending"]["kind"] == "suggest"
    assert result["pending"]["verified"] is False
    assert result["recovered"]["pending"] is None
    assert result["recovered"]["verified"] is True
    assert len(result["posts"]) == 1
    assert result["posts"][0]["body"]["baseline_id"] == "e"*32
    assert all(item["body"] is None for item in result["background"])
    assert all("Fictional notice" not in data for data in result["stored"])


def test_scope_change_drops_pending_response_and_never_reuses_another_job_selection():
    result=probe(r'''
let release;const storage=memory();
const c=ordinary.createOrdinaryLayoutController({getScope:()=>scope,storage,request:()=>new Promise(resolve=>{release=resolve;})});
const pending=c.read();scope.jobId='different-job';c.sync();release(ordinaryEnvelope({...prepared(),job_id:'fictional-job'}));await pending;
console.log(JSON.stringify({state:c.snapshot(),generation:c.deliveryGeneration()}));
''')
    assert result["state"]["scope"]["jobId"] == "different-job"
    assert result["state"]["view"] is None
    assert result["generation"] is None


def test_explicit_budget_authorization_is_nonce_bound_and_never_sent_by_read():
    result=probe(r'''
let saved=prepared();saved.suggestion_capability={available:false};
saved.budget={authorization_available:true,authorized:false,translation_cost_usd:'0.125',minimum_cap_usd:'0.937'};
const calls=[],storage=memory();let lose=true;
const options={getScope:()=>scope,storage,createNonce:nonce,request:async(url,owner,opts)=>{
 const body=opts.body?JSON.parse(opts.body):null;calls.push({url,body});
 if(body){saved.budget={...saved.budget,authorized:true,authorization_available:false,authorization_nonce:body.authorization_nonce,cap_usd:body.cap_usd};
   if(lose){lose=false;throw new Error('Response lost');}}
 return ordinaryEnvelope(saved);
}};
const c=ordinary.createOrdinaryLayoutController(options);await c.read();const before=calls.length;
await c.authorizeBudget('1.750');
const reload=ordinary.createOrdinaryLayoutController(options);await reload.read();
console.log(JSON.stringify({before,posts:calls.filter(c=>c.body),state:reload.snapshot()}));
''')
    assert result["before"] == 1
    assert len(result["posts"]) == 1
    assert result["posts"][0]["body"] == {
        "baseline_id":"e"*32,"expected_generation":1,
        "authorization_nonce":"0"*31+"1","cap_usd":"1.750",
    }
    assert result["state"]["pending"] is None
    assert result["state"]["view"]["budget"]["cap_usd"] == "1.750"


def test_selection_posts_exact_artifact_generation_and_review_receipt():
    result=probe(r'''
let saved=prepared();const calls=[];
const c=ordinary.createOrdinaryLayoutController({getScope:()=>scope,storage:memory(),createNonce:nonce,request:async(url,owner,opts)=>{
 const body=opts.body?JSON.parse(opts.body):null;calls.push({url,body});
 if(path(url).endsWith('/output-review'))saved.output_reviews.push({acceptance_nonce:body.acceptance_nonce,request:{artifact_id:body.artifact_id,generation:body.expected_generation}});
 if(path(url).endsWith('/delivery')&&body){saved.delivery_generation+=1;saved.delivery={selection_id:body.selection_nonce,kind:body.kind,artifact_id:body.artifact_id,word_count:120,stale:false};}
 return ordinaryEnvelope(saved);
}});
await c.read();await c.acceptOutput(artifactId);await c.select('reviewed',artifactId);
console.log(JSON.stringify({posts:calls.filter(c=>c.body),state:c.snapshot(),generation:c.deliveryGeneration()}));
''')
    assert [item["body"].get("all_pages_reviewed") for item in result["posts"]] == [True,None]
    body=result["posts"][1]["body"]
    assert body["artifact_id"]=="f"*32 and body["expected_review_generation"]==1
    assert body["expected_delivery_generation"]==0 and body["baseline_id"]=="e"*32
    assert result["generation"]==1 and result["state"]["pending"] is None


def test_actual_dom_prepares_bound_review_suggests_builds_reviews_and_selects():
    result=probe(DOM+r'''
let saved=null, seenDelivery=null;const calls=[];
const job={job_id:scope.jobId,job_kind:'translate',status:'completed',result:{save_seed:{}}};
const request=async(url,owner,opts={})=>{
 const body=opts.body?JSON.parse(opts.body):null;calls.push({url,body});const p=path(url);
 if(p.endsWith('/layout/prepare')){saved=prepared();saved.baseline_id=saved.preparation_nonce=body.prepare_nonce;return ordinaryEnvelope(saved);}
 if(p.endsWith('/layout/suggestions')){saved.generation+=1;saved.review.generation=saved.generation;saved.review.decisions.review.document_reviewed=false;saved.review.decisions.review.pages_reviewed=[];saved.review.paragraphs[0].text='<script>fictional</script>';return ordinaryEnvelope({status:'applied_unreviewed',generation:saved.generation});}
 if(p.endsWith('/layout/output-review')){saved.output_reviews.push({acceptance_nonce:body.acceptance_nonce,request:{artifact_id:body.artifact_id,generation:body.expected_generation}});return ordinaryEnvelope(saved);}
 if(p.endsWith('/layout/open'))return ordinaryEnvelope({open_result:{ok:true,message:'Opened for visual review.'}});
 if(p.endsWith('/delivery')&&body){saved.delivery_generation+=1;saved.delivery={kind:body.kind,selection_id:body.selection_nonce,artifact_id:body.artifact_id,word_count:120,stale:false};return ordinaryEnvelope(saved);}
 if(p.endsWith('/layout'))return ordinaryEnvelope(saved||{job_id:scope.jobId,status:'unprepared',generation:0,delivery_generation:0,review:null});
 if(p.endsWith('/decisions')){saved.review.decisions=body.decisions;saved.review.generation+=1;saved.generation=saved.review.generation;saved.review.saves.push({save_nonce:body.save_nonce,generation:saved.generation});}
 if(p.endsWith('/builds')){saved.review.builds.push({operation_nonce:body.operation_nonce,generation:saved.generation,status:'built',artifact_id:artifactId});saved.review.artifacts.push({artifact_id:artifactId,generation:saved.generation,kinds:['docx']});}
 return envelope(saved.review);
};
const mounted=ordinaryUi.mountOrdinaryLayoutReview({root,getScope:()=>scope,getJob:()=>job,request,onDeliveryChange:d=>{seenDelivery=d;}});
const settle=async()=>{for(let i=0;i<30;i++)await Promise.resolve();};
await findButton('Review source layout').fire('click');await settle();
const uploadCount=walk(root).filter(n=>n.tagName==='INPUT'&&n.type==='file').length;
await findButton('Suggest source layout').fire('click');await settle();
const unsafeTextShown=root.textContent.includes('<script>fictional</script>');
for(const label of ['I reviewed every visible group on this source page','I reviewed all wording, source associations, layout ownership and retained differences']){const node=fieldControl(label);node.checked=true;await node.fire('change');}
await findButton('Save formatting review').fire('click');await settle();
await findButton('Build separate Word copy').fire('click');await settle();
const beforeReview=findButton('Use this copy for delivery').disabled;
await findButton('Open a copy in Word for visual review').fire('click');
await check('I inspected every page of this Word copy');
await findButton('Use this copy for delivery').fire('click');await settle();
console.log(JSON.stringify({uploadCount,unsafeTextShown,unsafeWrites,beforeReview,seenDelivery,posts:calls.filter(c=>c.body),state:mounted.controller.snapshot()}));
''')
    assert result["uploadCount"]==0
    assert result["unsafeTextShown"] and result["unsafeWrites"]==0
    assert result["beforeReview"] is True
    assert result["seenDelivery"]["kind"]=="reviewed"
    assert result["state"]["pending"] is None
    endings=[item["url"].split("?")[0].rsplit("/",1)[1] for item in result["posts"]]
    assert endings==["prepare","suggestions","decisions","builds","open","output-review","delivery"]
