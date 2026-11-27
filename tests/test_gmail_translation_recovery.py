from .browser_esm_probe import run_browser_esm_json_probe


def test_recovery_requires_full_binding_and_refetches_without_dispatch() -> None:
    result = run_browser_esm_json_probe(r"""
const {matchesGmailTranslation,fetchGmailTranslationForRecovery}=await import(__MODULE__);
const {deriveGmailStage}=await import(__REVIEW__);
const binding={session_id:"batch-a",message_id:"message",thread_id:"thread",attachment_id:"attachment",selected_target_lang:"AR",selected_start_page:1};
const launch={source_path:"C:/source.pdf",target_lang:"AR",start_page:1,gmail_batch_context:binding};
const job={job_id:"tx-a",job_kind:"translate",config:{...launch},status:"failed"};
const checks={exact:matchesGmailTranslation(job,launch)};
for(const key of ["session_id","message_id","thread_id","attachment_id"]){
  checks[key]=matchesGmailTranslation({...job,config:{...job.config,gmail_batch_context:{...binding,[key]:"other"}}},launch);
}
for(const [key,value] of [["source_path","C:/other.pdf"],["target_lang","FR"],["start_page",2]]){
  checks[key]=matchesGmailTranslation({...job,config:{...job.config,[key]:value}},launch);
}
checks.noBinding=matchesGmailTranslation({...job,config:{source_path:launch.source_path}},launch);
let calls=[];
const loaded=await fetchGmailTranslationForRecovery(launch,async(path)=>{
  calls.push(path);return {normalized_payload:path.endsWith("history")?{active_jobs:[job]}:{job}};
},{});
let mismatch="";
try {await fetchGmailTranslationForRecovery(launch,async(path)=>({normalized_payload:path.endsWith("history")?{active_jobs:[job]}:{job:{...job,config:{...job.config,target_lang:"FR"}}}}),{});}catch(error){mismatch=error.message;}
const activeSession={kind:"translation",session_id:binding.session_id,selected_target_lang:"AR",message:{message_id:"message",thread_id:"thread"},current_attachment:{saved_path:launch.source_path,start_page:1,attachment:{attachment_id:"attachment",filename:"source.pdf"}}};
const unrelatedStage=deriveGmailStage({activeSession,translationUi:{currentJobId:"unrelated",currentJobStatus:"failed",currentJobRecoveryRequired:true,hasPreparedLaunch:true,preparedLaunchSourcePath:launch.source_path,currentGmailBatchContext:binding,runtimeJobs:[]}});
const freshStage=deriveGmailStage({activeSession,suggestedTranslationLaunch:launch,translationUi:{runtimeJobs:[],hasPreparedLaunch:false}});
const failedStage=deriveGmailStage({activeSession,suggestedTranslationLaunch:launch,translationUi:{runtimeJobs:[job],hasPreparedLaunch:false}});
console.log(JSON.stringify({checks,calls,id:loaded.job_id,mismatch,unrelatedStage,freshStage,failedStage}));
""", {"__MODULE__": "gmail_translation_recovery.js", "__REVIEW__": "gmail_review_state.js"})
    assert result["checks"].pop("exact") is True
    assert not any(result["checks"].values())
    assert result["calls"] == ["/api/translation/history", "/api/translation/jobs/tx-a"]
    assert result["id"] == "tx-a"
    assert "no longer matches" in result["mismatch"]
    assert result["unrelatedStage"] == "translation_prepared"
    assert result["freshStage"] == "translation_prepared"
    assert result["failedStage"] == "translation_recovery"
