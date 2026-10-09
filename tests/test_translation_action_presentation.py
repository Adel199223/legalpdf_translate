from __future__ import annotations

from .browser_esm_probe import run_browser_esm_json_probe


def test_recovery_quote_uses_current_raw_snapshot_and_never_historical_suggestion_policy():
    script = r"""
const p = await import(__TRANSLATION_ACTION_PRESENTATION_MODULE_URL__);
const base = {job_id:'tx-raw', actions:{recover_layout:true}, ordinary_layout:{suggestion_capability:{max_page_cost_usd:'0.812'}}};
console.log(JSON.stringify({
 old:p.deriveTranslationActionState(base).recoverLayoutLabel,
 current:p.deriveTranslationActionState({...base,diagnostics:{layout_recovery_quote:{available:true,max_page_cost_usd:'1.148'}}}).recoverLayoutLabel,
 unavailable:p.deriveTranslationActionState({...base,diagnostics:{layout_recovery_quote:{available:false,max_page_cost_usd:'1.148'}}}).recoverLayoutLabel,
 invalid:p.deriveTranslationActionState({...base,diagnostics:{layout_recovery_quote:{available:true,max_page_cost_usd:'<script>'}}}).recoverLayoutLabel
}));
"""
    result = run_browser_esm_json_probe(script,
        {"__TRANSLATION_ACTION_PRESENTATION_MODULE_URL__": "translation_action_presentation.js"})
    assert result == {'old':'Recover Source Layout (current price bound unavailable)',
        'current':'Recover Source Layout (paid; up to USD1.148/page; prior charges remain)',
        'unavailable':'Recover Source Layout (current price bound unavailable)',
        'invalid':'Recover Source Layout (current price bound unavailable)'}


def test_translation_action_presentation_module_builds_primary_action_state() -> None:
    script = r"""
const presentation = await import(__TRANSLATION_ACTION_PRESENTATION_MODULE_URL__);
const malicious = "<img src=x onerror=alert(1)><script>bad()</script>";

const cases = {
  idle: presentation.deriveTranslationActionState(),
  nullSafe: presentation.deriveTranslationActionState(null, null),
  uploadingLocal: presentation.deriveTranslationActionState(null, {
    sourceState: {
      status: "manual-uploading",
      ready: false,
      replacingPrepared: false,
    },
  }),
  uploadingReplacement: presentation.deriveTranslationActionState(null, {
    sourceState: {
      status: "manual-uploading",
      ready: false,
      replacingPrepared: true,
    },
  }),
  preparedGmail: presentation.deriveTranslationActionState(null, {
    sourceState: {
      status: "prepared-ready",
      ready: true,
      fromGmail: true,
    },
  }),
  preparedLocal: presentation.deriveTranslationActionState(null, {
    sourceState: {
      status: "prepared-ready",
      ready: true,
      fromGmail: false,
    },
  }),
  manualReady: presentation.deriveTranslationActionState(null, {
    sourceState: {
      status: "manual-ready",
      ready: true,
    },
  }),
  manualErrorMalicious: presentation.deriveTranslationActionState(null, {
    sourceState: {
      status: "manual-error",
      ready: false,
      message: `Could not stage ${malicious}`,
    },
  }),
  activeRunning: presentation.deriveTranslationActionState({
    job_id: "tx-running",
    status: "running",
    actions: {
      cancel: true,
      resume: true,
      rebuild: true,
    },
  }, {
    sourceState: {
      status: "manual-ready",
      ready: true,
    },
  }),
  currentJobIdFallback: presentation.deriveTranslationActionState({
    status: "failed",
    actions: {
      resume: true,
      rebuild: true,
    },
  }, {
    currentJobId: "tx-fallback",
    sourceState: {
      status: "empty",
      ready: false,
    },
  }),
  cancelledReady: presentation.deriveTranslationActionState({
    job_id: "tx-cancelled",
    status: "cancelled",
    actions: {
      cancel: true,
    },
  }, {
    sourceState: {
      status: "manual-ready",
      ready: true,
    },
  }),
};

console.log(JSON.stringify({
  exportType: typeof presentation.deriveTranslationActionState,
  cases,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__TRANSLATION_ACTION_PRESENTATION_MODULE_URL__": "translation_action_presentation.js"},
        timeout_seconds=20,
    )

    assert results["exportType"] == "function"

    assert results["cases"]["idle"] == {
        "sourceState": "empty",
        "helperText": "Choose a PDF or image to enable Start Translate.",
        "startEnabled": False,
        "analyzeEnabled": False,
        "cancelEnabled": False,
        "resumeEnabled": False,
        "rebuildEnabled": False,
        "recoverLayoutEnabled": False,
        "recoverLayoutLabel": "Recover Source Layout",
    }
    assert results["cases"]["nullSafe"] == results["cases"]["idle"]

    assert results["cases"]["uploadingLocal"]["helperText"] == (
        "Checking the document before translation starts..."
    )
    assert results["cases"]["uploadingLocal"]["startEnabled"] is False
    assert results["cases"]["uploadingLocal"]["analyzeEnabled"] is False

    assert results["cases"]["uploadingReplacement"]["helperText"] == "Checking the replacement document..."
    assert results["cases"]["uploadingReplacement"]["startEnabled"] is False

    assert results["cases"]["preparedGmail"]["helperText"] == (
        "Gmail attachment is prepared. Review settings, then start translation."
    )
    assert results["cases"]["preparedGmail"]["startEnabled"] is True
    assert results["cases"]["preparedGmail"]["analyzeEnabled"] is True

    assert results["cases"]["preparedLocal"]["helperText"] == (
        "The prepared document is ready. Confirm the language and output folder, then start translation."
    )
    assert results["cases"]["preparedLocal"]["startEnabled"] is True

    assert results["cases"]["manualReady"]["helperText"] == (
        "The document is ready. Confirm the language and output folder, then start translation."
    )
    assert results["cases"]["manualReady"]["startEnabled"] is True

    manual_error = results["cases"]["manualErrorMalicious"]
    assert manual_error["helperText"] == "Could not stage <img src=x onerror=alert(1)><script>bad()</script>"
    assert manual_error["startEnabled"] is False
    assert manual_error["analyzeEnabled"] is False

    active = results["cases"]["activeRunning"]
    assert active["helperText"] == (
        "A translation run is already in progress. Cancel it or wait for it to finish before starting another one."
    )
    assert active["startEnabled"] is False
    assert active["analyzeEnabled"] is False
    assert active["cancelEnabled"] is True
    assert active["resumeEnabled"] is True
    assert active["rebuildEnabled"] is True

    fallback = results["cases"]["currentJobIdFallback"]
    assert fallback["helperText"] == "Choose a PDF or image to enable Start Translate."
    assert fallback["resumeEnabled"] is True
    assert fallback["rebuildEnabled"] is True
    assert fallback["cancelEnabled"] is False

    cancelled = results["cases"]["cancelledReady"]
    assert cancelled["helperText"] == (
        "The document is ready. Confirm the language and output folder, then start translation."
    )
    assert cancelled["startEnabled"] is True
    assert cancelled["cancelEnabled"] is True
