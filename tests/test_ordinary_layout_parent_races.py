"""Embedded editor lifetime tests through the actual parent DOM flow."""

from .test_ordinary_layout_browser_state import probe
from .test_source_review_browser_state import DOM


def test_late_disposed_editor_read_cannot_replace_another_jobs_editor():
    result = probe(DOM + r'''
const a=prepared(), b=prepared();
a.job_id='job-a';b.job_id='job-b';b.baseline_id='d'.repeat(32);b.review.review_id='c'.repeat(32);
a.review.paragraphs[0].text='OLD_OWNER_ONLY';b.review.paragraphs[0].text='NEW_OWNER_ONLY';
let job={job_id:'job-a',job_kind:'translate',status:'completed',result:{save_seed:{}},ordinary_layout:a};
let releaseOld=null;const calls=[];
const request=async(url,owner,opts={})=>{
 calls.push({url,method:opts.method||'GET'});
 if(path(url).endsWith('/layout'))return ordinaryEnvelope(owner.jobId==='job-a'?a:b);
 if(path(url).endsWith('/reviews/'+a.review.review_id))return new Promise(resolve=>{releaseOld=()=>resolve(envelope(a.review));});
 if(path(url).endsWith('/reviews/'+b.review.review_id))return envelope(b.review);
 throw new Error('Unexpected request '+url);
};
const mounted=ordinaryUi.mountOrdinaryLayoutReview({root,getScope:()=>scope,getJob:()=>job,request});
const settle=async()=>{for(let i=0;i<40;i++)await Promise.resolve();};
mounted.update();await findButton('Review source layout').fire('click');await settle();
if(!releaseOld)throw new Error('Old read not started');
job={job_id:'job-b',job_kind:'translate',status:'completed',result:{save_seed:{}},ordinary_layout:b};
mounted.update();await findButton('Review source layout').fire('click');await settle();
const before=root.textContent;
releaseOld();await settle();
console.log(JSON.stringify({before,after:root.textContent,current:mounted.controller.snapshot(),calls,unsafeWrites}));
''')
    assert "NEW_OWNER_ONLY" in result["before"]
    assert "NEW_OWNER_ONLY" in result["after"]
    assert "OLD_OWNER_ONLY" not in result["after"]
    assert result["current"]["view"]["job_id"] == "job-b"
    assert all(call["method"] == "GET" for call in result["calls"])
    assert result["unsafeWrites"] == 0


def test_frozen_embedded_review_does_not_offer_a_new_build_after_incomplete_attempt():
    result = probe(DOM + r'''
const view=complete(), pendingNonce='1'.repeat(32), storage=memory();
view.builds=[{operation_nonce:pendingNonce,generation:view.generation,status:'incomplete'}];
storage.setItem(`legalpdf:saved-docx-layout:v1:${scope.runtimeMode}:${scope.workspaceId}`,JSON.stringify({
 reviewId:view.review_id,pending:{kind:'build',nonce:pendingNonce,generation:view.generation}}));
const mounted=ui.mountSavedDocxLayout({root,getScope:()=>scope,storage,embedded:true,readOnly:()=>true,
 request:async()=>envelope(view)});
await mounted.controller.read();
const retry=findButton('Start a new build attempt after the incomplete attempt');
console.log(JSON.stringify({disabled:retry.disabled,unsafeWrites}));
''')
    assert result["disabled"] is True
    assert result["unsafeWrites"] == 0


def test_disposed_saved_controller_preserves_recovery_pointer_but_ignores_late_save():
    result = probe(r'''
let release;const storage=memory(),calls=[],states=[];let saved=complete();
const c=core.createSavedDocxLayoutController({getScope:()=>scope,storage,createNonce:nonce,
 onChange:s=>states.push(s),request:async(url,owner,opts={})=>{
  calls.push({url,method:opts.method||'GET'});
  if(opts.method==='POST')return new Promise(resolve=>{release=()=>resolve(envelope({...saved,generation:2}));});
  return envelope(saved);
 }});
await c.open(saved.review_id);const d=copy(c.snapshot().decisions);d.review.note='Fictional unsent local note';c.edit(d,{reviewOnly:true});
const saving=c.save();const emitted=states.length;
c.dispose();release();await saving;
await c.read();await c.save();await c.build();await c.open('d'.repeat(32));
console.log(JSON.stringify({statesAfterDispose:states.length-emitted,calls,stored:[...storage.data.values()],state:c.snapshot()}));
''')
    assert result["statesAfterDispose"] == 0
    assert [row["method"] for row in result["calls"]] == ["GET", "POST"]
    assert result["state"]["verified"] is False
    assert result["state"]["pending"]["kind"] == "save"
    assert all("Fictional unsent" not in entry for entry in result["stored"])


def test_passive_layout_snapshots_never_roll_back_or_reverify_a_changed_baseline():
    result = probe(r'''
let saved=prepared();saved.generation=4;saved.review.generation=4;saved.delivery_generation=3;
saved.delivery={selection_id:'1'.repeat(32),kind:'reviewed',stale:false,word_count:123};
const c=ordinary.createOrdinaryLayoutController({getScope:()=>scope,storage:memory(),request:async()=>ordinaryEnvelope(saved)});
await c.read();
const earlier=copy(saved);earlier.generation=3;earlier.review.generation=3;
c.receive(earlier);const oldReview=c.snapshot();
c.receive({...copy(saved),delivery_generation:2,delivery:null});const oldDelivery=c.snapshot();
const changed={...copy(saved),baseline_id:'d'.repeat(32),generation:1,delivery_generation:0,delivery:null};
changed.review.generation=1;
c.receive(changed);const cross=c.snapshot();c.receive(saved);const repeated=c.snapshot();
saved=changed;await c.read();const refreshed=c.snapshot();
let threw=false;try{c.receive({...copy(saved),generation:-1});}catch{threw=true;}
const invalid=c.snapshot();c.receive(saved);const afterInvalid=c.snapshot();await c.read();
console.log(JSON.stringify({oldReview,oldDelivery,cross,repeated,refreshed,threw,invalid,afterInvalid,final:c.snapshot()}));
''')
    assert result["oldReview"]["view"]["generation"] == 4
    assert result["oldDelivery"]["view"]["delivery_generation"] == 3
    assert result["oldDelivery"]["view"]["delivery"]["word_count"] == 123
    for key in ("cross", "repeated"):
        assert result[key]["verified"] is False
        assert result[key]["view"]["baseline_id"] == "e" * 32
    assert result["refreshed"]["verified"] is True
    assert result["refreshed"]["view"]["baseline_id"] == "d" * 32
    assert result["threw"] is False
    assert result["invalid"]["error"] == "invalid_layout_response"
    assert result["afterInvalid"]["verified"] is False
    assert result["final"]["verified"] is True


def test_invalid_budget_decimal_never_creates_a_pending_operation():
    result = probe(r'''
const calls=[],storage=memory(),saved=prepared();
const c=ordinary.createOrdinaryLayoutController({getScope:()=>scope,storage,createNonce:nonce,request:async(url,owner,opts={})=>{
 calls.push({url,body:opts.body});return ordinaryEnvelope(saved);
}});await c.read();const cases=[];
for(const value of ['', ' ', '1e0', '-1', 'NaN', '0', '0.000', '1.2.3', '<script>', '1'.repeat(13)]){
 await c.authorizeBudget(value);cases.push(c.snapshot());
}
console.log(JSON.stringify({cases,posts:calls.filter(c=>c.body),serial,stored:[...storage.data.values()]}));
''')
    assert not result["posts"] and result["serial"] == 0
    assert all(row["pending"] is None and row["error"] == "ordinary_layout_invalid_budget" for row in result["cases"])
    assert not result["stored"]


def test_budget_dom_uses_exact_server_suggested_cap_without_rounding():
    result = probe(DOM + r'''
const saved=prepared();saved.selected_pages=[1,2,3];saved.suggestion_capability={available:false};
saved.budget={authorization_available:true,authorized:false,translation_cost_usd:'0.123456789',
 minimum_cap_usd:'0.935456789',max_page_cost_usd:'0.812',suggested_cap_usd:'2.559456789'};
const job={job_id:scope.jobId,job_kind:'translate',status:'completed',result:{save_seed:{}},ordinary_layout:saved};
const mounted=ordinaryUi.mountOrdinaryLayoutReview({root,getScope:()=>scope,getJob:()=>job,
 request:async url=>path(url).endsWith('/layout')?ordinaryEnvelope(saved):envelope(saved.review)});
mounted.update();await findButton('Review source layout').fire('click');
console.log(JSON.stringify({value:fieldControl('Maximum total API cost (USD)').value,unsafeWrites}));
''')
    assert result["value"] == "2.559456789"
    assert result["unsafeWrites"] == 0


def test_lost_prepare_has_visible_read_first_same_nonce_recovery_after_reload():
    result = probe(DOM + r'''
globalThis.localStorage=memory();let saved=null,lost=true,failRead=false;const calls=[];
const job={job_id:scope.jobId,job_kind:'translate',status:'completed',result:{save_seed:{}}};
const request=async(url,owner,opts={})=>{
 const body=opts.body?JSON.parse(opts.body):null;calls.push({url,body});
 if(path(url).endsWith('/layout/prepare')){
  if(lost){lost=false;throw new Error('fictional_response_lost');}
  saved=prepared();saved.preparation_nonce=body.prepare_nonce;return ordinaryEnvelope(saved);
 }
 if(path(url).endsWith('/layout')){
  if(failRead)throw new Error('fictional_read_failed');
  return ordinaryEnvelope(saved||{job_id:scope.jobId,status:'unprepared',generation:0,delivery_generation:0,review:null});
 }
 return envelope(saved.review);
};
let mounted=ordinaryUi.mountOrdinaryLayoutReview({root,getScope:()=>scope,getJob:()=>job,request});
await findButton('Review source layout').fire('click');const first=mounted.controller.snapshot();
mounted.dispose();root.replaceChildren();mounted=ordinaryUi.mountOrdinaryLayoutReview({root,getScope:()=>scope,getJob:()=>job,request});
const visible=Boolean(findButton('Recover the same operation'));
failRead=true;await findButton('Recover the same operation').fire('click');const postsAfterReadFailure=calls.filter(c=>c.body).length;
failRead=false;const before=calls.length;await findButton('Recover the same operation').fire('click');
for(let i=0;i<40;i++)await Promise.resolve();
console.log(JSON.stringify({visible,postsAfterReadFailure,first,final:mounted.controller.snapshot(),recovery:calls.slice(before),posts:calls.filter(c=>c.body),text:root.textContent,unsafeWrites}));
''')
    assert result["visible"] is True
    assert result["postsAfterReadFailure"] == 1
    assert result["recovery"][0]["body"] is None
    assert len(result["posts"]) == 2
    assert result["posts"][0]["body"] == result["posts"][1]["body"]
    assert result["final"]["pending"] is None
    assert result["final"]["verified"] is True
    assert "Review the source layout" in result["text"]
    assert result["unsafeWrites"] == 0


def test_original_selection_recovery_uses_null_review_fields_and_blocks_old_delivery():
    result = probe(r'''
const saved=prepared(),storage=memory(),calls=[];let release;
saved.delivery_generation=1;saved.delivery={selection_id:'a'.repeat(32),kind:'reviewed',stale:false};
const options={getScope:()=>scope,storage,createNonce:nonce,request:async(url,owner,opts={})=>{
 const body=opts.body?JSON.parse(opts.body):null;calls.push({url,body});
 if(body)return new Promise(resolve=>{release=()=>{saved.delivery_generation=2;saved.delivery={selection_id:body.selection_nonce,kind:body.kind,stale:false};resolve(ordinaryEnvelope(saved));};});
 return ordinaryEnvelope(saved);
}};
const c=ordinary.createOrdinaryLayoutController(options);await c.read();const action=c.select('original',artifactId);
const pendingUsable=Boolean(c.canUseDelivery());
const reload=ordinary.createOrdinaryLayoutController(options);await reload.read();const restoredUsable=Boolean(reload.canUseDelivery());
release();await action;await reload.read();
const key=`legalpdf:ordinary-layout:v1:${scope.runtimeMode}:${scope.workspaceId}:${scope.jobId}`;
storage.setItem(key,JSON.stringify({pending:{kind:'select',nonce:'b'.repeat(32),baseline,generation:1,choice:'original',reviewId:'a'.repeat(32),reviewGeneration:1,artifactId:null}}));
const malformed=ordinary.createOrdinaryLayoutController(options).snapshot();
console.log(JSON.stringify({posts:calls.filter(c=>c.body),pendingUsable,restoredUsable,final:reload.snapshot(),malformed}));
''')
    assert result["pendingUsable"] is False and result["restoredUsable"] is False
    assert len(result["posts"]) == 1
    body = result["posts"][0]["body"]
    assert body["review_id"] is None and body["artifact_id"] is None and body["expected_review_generation"] is None
    assert body["keep_ordinary_confirmed"] is True
    assert result["final"]["pending"] is None
    assert result["malformed"]["pending"] is None


def test_saved_and_parent_pointers_are_isolated_by_mode_workspace_and_job():
    result = probe(r'''
const storage=memory(),owners=[{runtimeMode:'shadow',workspaceId:'one',jobId:'job-a'},
 {runtimeMode:'shadow',workspaceId:'one',jobId:'job-b'},{runtimeMode:'shadow',workspaceId:'two',jobId:'job-a'},
 {runtimeMode:'live',workspaceId:'one',jobId:'job-a'}];
const snapshots=[];
for(let i=0;i<owners.length;i++){
 const owner=owners[i],id=(i+1).toString(16).repeat(32);
 const saved=complete();saved.review_id=id;
 const c=core.createSavedDocxLayoutController({getScope:()=>owner,storage,storageNamespace:`ordinary-${owner.jobId}-${baseline}`,request:async()=>envelope(saved)});
 await c.open(id);c.dispose();
 const parent=ordinary.createOrdinaryLayoutController({getScope:()=>owner,storage,createNonce:()=>id,request:async()=>{throw new Error('fictional_response_lost');}});
 await parent.prepare();
}
for(const owner of owners){
 const c=core.createSavedDocxLayoutController({getScope:()=>owner,storage,storageNamespace:`ordinary-${owner.jobId}-${baseline}`});
 const parent=ordinary.createOrdinaryLayoutController({getScope:()=>owner,storage});
 snapshots.push({reviewId:c.snapshot().reviewId,pending:parent.snapshot().pending});
}
console.log(JSON.stringify({snapshots,keys:[...storage.data.keys()]}));
''')
    assert len(result["keys"]) == 8
    for index, snapshot in enumerate(result["snapshots"], 1):
        assert snapshot["reviewId"] == str(index) * 32
        assert snapshot["pending"] == {"kind": "prepare", "nonce": str(index) * 32}


def test_native_open_false_is_visible_and_does_not_accept_or_select_artifact():
    result = probe(DOM + r'''
const saved=prepared();saved.review.artifacts=[{artifact_id:artifactId,generation:1,kinds:['docx']}];const posts=[];
const job={job_id:scope.jobId,job_kind:'translate',status:'completed',result:{save_seed:{}},ordinary_layout:saved};
const mounted=ordinaryUi.mountOrdinaryLayoutReview({root,getScope:()=>scope,getJob:()=>job,request:async(url,owner,opts={})=>{
 if(opts.body){posts.push(JSON.parse(opts.body));return ordinaryEnvelope({artifact_id:artifactId,generation:1,
  open_result:{ok:false,message:'Fictional Word owner unavailable <script>unsafe</script>',failure_code:'word_owner_unavailable'}});}
 return path(url).endsWith('/layout')?ordinaryEnvelope(saved):envelope(saved.review);
}});
mounted.update();await findButton('Review source layout').fire('click');for(let i=0;i<40;i++)await Promise.resolve();
await findButton('Open a copy in Word for visual review').fire('click');
console.log(JSON.stringify({posts,text:root.textContent,disabled:findButton('Use this copy for delivery').disabled,unsafeWrites}));
''')
    assert len(result["posts"]) == 1
    assert "Fictional Word owner unavailable <script>unsafe</script>" in result["text"]
    assert "without changing its wording" in result["text"]
    assert result["disabled"] is True and result["unsafeWrites"] == 0


def test_stop_after_current_page_is_available_during_busy_suggestion_and_recovers_terminal():
    result = probe(DOM + r'''
let saved=prepared(),finish;const calls=[];
const job={job_id:scope.jobId,job_kind:'translate',status:'completed',result:{save_seed:{}},ordinary_layout:saved};
const mounted=ordinaryUi.mountOrdinaryLayoutReview({root,getScope:()=>scope,getJob:()=>job,request:async(url,owner,opts={})=>{
 const body=opts.body?JSON.parse(opts.body):null;calls.push({url,body});
 if(path(url).endsWith('/cancel'))return ordinaryEnvelope({operation_nonce:path(url).split('/').at(-2),baseline_id:baseline,status:'cancel_requested'});
 if(path(url).endsWith('/suggestions')&&body)return new Promise(resolve=>{finish=()=>{
  saved.generation=2;saved.review.generation=2;resolve(ordinaryEnvelope({operation_nonce:body.operation_nonce,baseline_id:baseline,
   status:'cancelled',completed_pages:[1],applied_unreviewed:true,generation:2}));
 };});
 return path(url).endsWith('/layout')?ordinaryEnvelope(saved):envelope(saved.review);
}});
mounted.update();await findButton('Review source layout').fire('click');for(let i=0;i<40;i++)await Promise.resolve();
const action=findButton('Suggest source layout').fire('click');await Promise.resolve();
const stop=findButton('Stop after current page'),during=mounted.controller.snapshot();
const enabled=!stop.disabled;await stop.fire('click');const acknowledged=mounted.controller.snapshot();
const disabledAfter=findButton('Stop after current page').disabled;
finish();await action;for(let i=0;i<40;i++)await Promise.resolve();
console.log(JSON.stringify({enabled,during,acknowledged,disabledAfter,final:mounted.controller.snapshot(),calls,text:root.textContent,unsafeWrites}));
''')
    assert result["enabled"] is True and result["during"]["busy"] is True
    assert result["acknowledged"]["pending"]["kind"] == "suggest"
    assert result["disabledAfter"] is True
    assert result["final"]["pending"] is None
    assert result["final"]["operation"]["status"] == "cancelled"
    posts = [item for item in result["calls"] if item["body"]]
    assert len(posts) == 2
    assert posts[1]["body"] == {"baseline_id": "e" * 32, "expected_generation": 1}
    assert posts[1]["url"].split("?")[0].endswith(posts[0]["body"]["operation_nonce"] + "/cancel")
    assert "completed pages" in result["text"] and result["unsafeWrites"] == 0


def test_old_review_button_cannot_prepare_a_new_job_after_its_read_finishes():
    result = probe(DOM + r'''
let job={job_id:'job-a',job_kind:'translate',status:'completed',result:{save_seed:{}}},release;
const calls=[],unprepared=id=>({job_id:id,status:'unprepared',generation:0,delivery_generation:0,review:null});
const mounted=ordinaryUi.mountOrdinaryLayoutReview({root,getScope:()=>scope,getJob:()=>job,request:async(url,owner,opts={})=>{
 calls.push({url,body:opts.body||null});
 if(owner.jobId==='job-a')return new Promise(resolve=>{release=()=>resolve(ordinaryEnvelope(unprepared('job-a')));});
 return ordinaryEnvelope(unprepared('job-b'));
}});
const action=findButton('Review source layout').fire('click');
job={...job,job_id:'job-b',ordinary_layout:unprepared('job-b')};mounted.update();release();await action;
console.log(JSON.stringify({calls,state:mounted.controller.snapshot(),text:root.textContent}));
''')
    assert len(result["calls"]) == 1
    assert result["calls"][0]["body"] is None
    assert result["state"]["view"]["job_id"] == "job-b"
    assert result["state"]["pending"] is None
    assert "Hide layout review" not in result["text"]


def test_cancelled_suggestion_recovery_only_reads_and_rejects_wrong_cancel_identity():
    result = probe(r'''
const saved=prepared(),storage=memory(),calls=[];let operationNonce,terminal=false;
const options={getScope:()=>scope,storage,createNonce:nonce,request:async(url,owner,opts={})=>{
 const body=opts.body?JSON.parse(opts.body):null;calls.push({url,body});
 if(path(url).endsWith('/cancel'))return ordinaryEnvelope({status:'cancel_requested',operation_nonce:'f'.repeat(32),baseline_id:baseline});
 if(body){operationNonce=body.operation_nonce;throw new Error('fictional_response_lost');}
 if(path(url).includes('/suggestions/'))return ordinaryEnvelope({status:terminal?'cancelled':'started',
  operation_nonce:operationNonce,baseline_id:baseline,completed_pages:[],applied_unreviewed:false});
 return ordinaryEnvelope(saved);
}};
const first=ordinary.createOrdinaryLayoutController(options);await first.read();await first.suggest([1]);
await first.cancelSuggestion();const invalid=first.snapshot();
terminal=true;const reload=ordinary.createOrdinaryLayoutController(options);const before=calls.length;await reload.read();
console.log(JSON.stringify({invalid,recovered:reload.snapshot(),recovery:calls.slice(before),posts:calls.filter(c=>c.body)}));
''')
    assert result["invalid"]["error"] == "invalid_layout_response"
    assert result["invalid"]["pending"]["kind"] == "suggest"
    assert result["recovered"]["pending"] is None
    assert result["recovered"]["operation"]["status"] == "cancelled"
    assert all(item["body"] is None for item in result["recovery"])
    assert len(result["posts"]) == 2
