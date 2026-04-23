from __future__ import annotations

from .browser_esm_probe import run_browser_esm_json_probe


def _run_review_state_probe() -> dict[str, object]:
    script = """
const reviewModule = await import(__GMAIL_REVIEW_MODULE_URL__);

const memory = new Map();
const storage = {{
  getItem(key) {{
    return memory.has(key) ? memory.get(key) : null;
  }},
  setItem(key, value) {{
    memory.set(key, String(value));
  }},
  removeItem(key) {{
    memory.delete(key);
  }},
}};

const context = {{ runtimeMode: "live", workspaceId: "gmail-intake" }};
const results = {{}};

results.initial = reviewModule.readConsumedReviewState(storage, context);
reviewModule.writeConsumedReviewState(storage, context, {{ reviewEventId: 5, messageSignature: "sig-5" }});
results.afterWrite = reviewModule.readConsumedReviewState(storage, context);

results.openFresh = reviewModule.shouldAutoOpenReview({{
  reviewEventId: 5,
  messageSignature: "sig-5",
  consumedReviewEventId: 0,
  consumedMessageSignature: "",
  loadResult: {{ ok: true, message: {{ message_id: "msg-1" }} }},
  activeSession: null,
}});

results.noReopenSame = reviewModule.shouldAutoOpenReview({{
  reviewEventId: 5,
  messageSignature: "sig-5",
  consumedReviewEventId: 5,
  consumedMessageSignature: "sig-5",
  loadResult: {{ ok: true, message: {{ message_id: "msg-1" }} }},
  activeSession: null,
}});

results.noOpenWithSession = reviewModule.shouldAutoOpenReview({{
  reviewEventId: 6,
  messageSignature: "sig-6",
  consumedReviewEventId: 5,
  consumedMessageSignature: "sig-5",
  loadResult: {{ ok: true, message: {{ message_id: "msg-2" }} }},
  activeSession: {{ kind: "translation" }},
}});

results.openOnNewerEvent = reviewModule.shouldAutoOpenReview({{
  reviewEventId: 6,
  messageSignature: "sig-6",
  consumedReviewEventId: 5,
  consumedMessageSignature: "sig-5",
  loadResult: {{ ok: true, message: {{ message_id: "msg-2" }} }},
  activeSession: null,
}});

results.openOnResetEpoch = reviewModule.shouldAutoOpenReview({{
  reviewEventId: 1,
  messageSignature: "sig-reset",
  consumedReviewEventId: 5,
  consumedMessageSignature: "sig-5",
  loadResult: {{ ok: true, message: {{ message_id: "msg-reset" }} }},
  activeSession: null,
}});

results.stageIdle = reviewModule.deriveGmailStage({{
  loadResult: null,
  activeSession: null,
}});
results.stageReview = reviewModule.deriveGmailStage({{
  loadResult: {{ ok: true, message: {{ message_id: "msg-1" }} }},
  activeSession: null,
}});
results.stageTranslationRunning = reviewModule.deriveGmailStage({{
  loadResult: {{ ok: true, message: {{ message_id: "msg-1" }} }},
  activeSession: {{ kind: "translation", completed: false, current_item_number: 1, total_items: 2 }},
  translationUi: {{ currentJobStatus: "running", hasCompletionSurface: false, completionDrawerOpen: false }},
}});
results.stageTranslationRecovery = reviewModule.deriveGmailStage({{
  loadResult: {{ ok: true, message: {{ message_id: "msg-1" }} }},
  activeSession: {{
    kind: "translation",
    completed: false,
    current_item_number: 1,
    total_items: 2,
    current_attachment: {{ attachment: {{ filename: "sentença 305.pdf" }} }},
  }},
  translationUi: {{
    currentJobStatus: "failed",
    currentJobKind: "translate",
    currentJobHasSaveSeed: false,
    currentJobRecoveryRequired: true,
    hasCompletionSurface: false,
    completionDrawerOpen: false,
  }},
}});
results.stageTranslationSave = reviewModule.deriveGmailStage({{
  loadResult: {{ ok: true, message: {{ message_id: "msg-1" }} }},
  activeSession: {{ kind: "translation", completed: false, current_item_number: 1, total_items: 2 }},
  translationUi: {{ currentJobStatus: "completed", hasCompletionSurface: true, completionDrawerOpen: false }},
}});
results.stageTranslationFinalize = reviewModule.deriveGmailStage({{
  loadResult: {{ ok: true, message: {{ message_id: "msg-1" }} }},
  activeSession: {{ kind: "translation", completed: true, current_item_number: 2, total_items: 2 }},
}});
results.stageInterpretationReview = reviewModule.deriveGmailStage({{
  loadResult: {{ ok: true, message: {{ message_id: "msg-1" }} }},
  activeSession: {{ kind: "interpretation", completed: false }},
  interpretationUi: {{ exportReady: false }},
}});
results.stageInterpretationFinalize = reviewModule.deriveGmailStage({{
  loadResult: {{ ok: true, message: {{ message_id: "msg-1" }} }},
  activeSession: {{ kind: "interpretation", completed: false }},
  interpretationUi: {{ exportReady: true }},
}});
results.workflowTranslation = reviewModule.deriveGmailWorkflowPresentation({{
  workflowKind: "translation",
}});
results.workflowInterpretation = reviewModule.deriveGmailWorkflowPresentation({{
  workflowKind: "interpretation",
}});
results.kindPdf = reviewModule.deriveGmailAttachmentKindLabel("application/pdf");
results.kindImage = reviewModule.deriveGmailAttachmentKindLabel("image/png");
results.kindUnknown = reviewModule.deriveGmailAttachmentKindLabel("application/octet-stream");
results.stagePresentationIdle = reviewModule.deriveGmailStagePresentation({{
  stage: "idle",
  activeSession: null,
}});
results.stagePresentationReview = reviewModule.deriveGmailStagePresentation({{
  stage: "review",
  activeSession: null,
}});
results.stagePresentationPrepared = reviewModule.deriveGmailStagePresentation({{
  stage: "translation_prepared",
  activeSession: {{
    kind: "translation",
    current_attachment: {{ attachment: {{ filename: "sentença 305.pdf" }} }},
  }},
}});
results.stagePresentationRunning = reviewModule.deriveGmailStagePresentation({{
  stage: "translation_running",
  activeSession: {{
    kind: "translation",
    current_attachment: {{ attachment: {{ filename: "sentença 305.pdf" }} }},
  }},
}});
results.stagePresentationSave = reviewModule.deriveGmailStagePresentation({{
  stage: "translation_save",
  activeSession: {{ kind: "translation" }},
}});
results.stagePresentationFinalize = reviewModule.deriveGmailStagePresentation({{
  stage: "translation_finalize",
  activeSession: {{
    kind: "translation",
    finalization_state: "draft_ready",
  }},
}});
results.stagePresentationInterpretationReview = reviewModule.deriveGmailStagePresentation({{
  stage: "interpretation_review",
  activeSession: {{ kind: "interpretation" }},
}});
results.stagePresentationInterpretationFinalize = reviewModule.deriveGmailStagePresentation({{
  stage: "interpretation_finalize",
  activeSession: {{ kind: "interpretation" }},
}});
results.ctaHidden = reviewModule.deriveGmailHomeCta({{
  stage: "review",
  activeSession: null,
}});
results.ctaTranslationSave = reviewModule.deriveGmailHomeCta({{
  stage: "translation_save",
  activeSession: {{ kind: "translation", current_item_number: 1, total_items: 2 }},
}});
results.ctaTranslationRecovery = reviewModule.deriveGmailHomeCta({{
  stage: "translation_recovery",
  activeSession: {{
    kind: "translation",
    current_item_number: 1,
    total_items: 2,
    current_attachment: {{ attachment: {{ filename: "sentença 305.pdf" }} }},
  }},
}});
results.ctaTranslationFinalize = reviewModule.deriveGmailHomeCta({{
  stage: "translation_finalize",
  activeSession: {{ kind: "translation", current_item_number: 2, total_items: 2 }},
}});
results.redoHidden = reviewModule.deriveGmailRedoAction({{
  activeSession: null,
  translationUi: {{}},
}});
results.redoFresh = reviewModule.deriveGmailRedoAction({{
  activeSession: {{
    kind: "translation",
    completed: false,
    session_id: "gmail_batch_1",
    selected_target_lang: "AR",
    current_item_number: 1,
    total_items: 2,
    message: {{ message_id: "msg-1", thread_id: "thr-1" }},
    current_attachment: {{
      attachment: {{ attachment_id: "att-1", filename: "sentença 305.pdf" }},
      saved_path: "C:/tmp/sentenca_305.pdf",
      start_page: 1,
      page_count: 5,
    }},
  }},
  translationUi: {{ runtimeJobs: [] }},
}});
results.redoMatchingCompleted = reviewModule.deriveGmailRedoAction({{
  activeSession: {{
    kind: "translation",
    completed: false,
    session_id: "gmail_batch_1",
    selected_target_lang: "AR",
    current_item_number: 1,
    total_items: 2,
    message: {{ message_id: "msg-1", thread_id: "thr-1" }},
    current_attachment: {{
      attachment: {{ attachment_id: "att-1", filename: "sentença 305.pdf" }},
      saved_path: "C:/tmp/sentenca_305.pdf",
      start_page: 1,
      page_count: 5,
    }},
  }},
  translationUi: {{
    runtimeJobs: [{{
      job_id: "tx-1",
      job_kind: "translate",
      status: "completed",
      config: {{
        source_path: "C:/tmp/sentenca_305.pdf",
        gmail_batch_context: {{
          source: "gmail_intake",
          session_id: "gmail_batch_1",
          message_id: "msg-1",
          thread_id: "thr-1",
          attachment_id: "att-1",
          selected_attachment_filename: "sentença 305.pdf",
          selected_attachment_count: 2,
          selected_target_lang: "AR",
          selected_start_page: 1,
          gmail_batch_session_report_path: "C:/tmp/session.json",
        }},
      }},
    }}],
  }},
}});
results.redoMatchingRunning = reviewModule.deriveGmailRedoAction({{
  activeSession: {{
    kind: "translation",
    completed: false,
    session_id: "gmail_batch_1",
    selected_target_lang: "AR",
    current_item_number: 1,
    total_items: 2,
    message: {{ message_id: "msg-1", thread_id: "thr-1" }},
    current_attachment: {{
      attachment: {{ attachment_id: "att-1", filename: "sentença 305.pdf" }},
      saved_path: "C:/tmp/sentenca_305.pdf",
      start_page: 1,
      page_count: 5,
    }},
  }},
  translationUi: {{
    runtimeJobs: [{{
      job_id: "tx-2",
      job_kind: "translate",
      status: "running",
      config: {{
        source_path: "C:/tmp/sentenca_305.pdf",
        gmail_batch_context: {{
          source: "gmail_intake",
          session_id: "gmail_batch_1",
          message_id: "msg-1",
          thread_id: "thr-1",
          attachment_id: "att-1",
          selected_attachment_filename: "sentença 305.pdf",
          selected_attachment_count: 2,
          selected_target_lang: "AR",
          selected_start_page: 1,
          gmail_batch_session_report_path: "C:/tmp/session.json",
        }},
      }},
    }}],
  }},
}});
results.ctaInterpretationFinalize = reviewModule.deriveGmailHomeCta({{
  stage: "interpretation_finalize",
  activeSession: {{ kind: "interpretation" }},
}});
results.recoveredHidden = reviewModule.deriveRecoveredFinalizationAction({{
  restoredCompletedSession: null,
}});
results.recoveredVisible = reviewModule.deriveRecoveredFinalizationAction({{
  restoredCompletedSession: {{
    kind: "translation",
    completed: true,
    restored_from_report: true,
    finalization_state: "draft_ready",
    message: {{ subject: "Recovered batch" }},
  }},
}});
results.stableRecoveredOnly = reviewModule.shouldTreatGmailWorkspaceAsStable({{
  activeView: "gmail-intake",
  loadResult: null,
  activeSession: null,
  restoredCompletedSession: {{
    kind: "translation",
    completed: true,
    restored_from_report: true,
  }},
  pendingStatus: "",
  pendingReviewOpen: false,
}});
results.stableLoadedMessage = reviewModule.shouldTreatGmailWorkspaceAsStable({{
  activeView: "gmail-intake",
  loadResult: {{ ok: true, message: {{ message_id: "msg-1" }} }},
  activeSession: null,
  restoredCompletedSession: null,
  pendingStatus: "",
  pendingReviewOpen: false,
}});
results.stableWarmupPending = reviewModule.shouldTreatGmailWorkspaceAsStable({{
  activeView: "gmail-intake",
  loadResult: null,
  activeSession: null,
  restoredCompletedSession: null,
  pendingStatus: "warming",
  pendingReviewOpen: true,
}});

results.previewInitial = reviewModule.createClosedPreviewState();
results.previewOpened = reviewModule.openPreviewState({{
  attachmentId: "att-1",
  previewHref: "/api/gmail/attachment/att-1",
  previewMimeType: "application/pdf",
  pageCount: 5,
  currentStartPage: 2,
  editable: true,
}});
results.previewMoved = reviewModule.setPreviewStatePage(results.previewOpened, 4);
results.previewApplied = reviewModule.applyPreviewStateStartPage(results.previewMoved, 2);
results.previewClosed = reviewModule.createClosedPreviewState();
results.previewUnchangedOnClose = 2;
results.previewInspectOnly = reviewModule.openPreviewState({{
  attachmentId: "att-2",
  previewHref: "/api/gmail/attachment/att-2",
  previewMimeType: "application/pdf",
  pageCount: 7,
  currentStartPage: 3,
  editable: false,
}});
results.previewInspectOnlyMoved = reviewModule.setPreviewStatePage(results.previewInspectOnly, 6);
results.previewInspectOnlyApplied = reviewModule.applyPreviewStateStartPage(results.previewInspectOnlyMoved, 3);
results.previewIsOpen = reviewModule.isPreviewStateOpen(results.previewOpened);
results.previewClosedIsOpen = reviewModule.isPreviewStateOpen(results.previewClosed);
const makeTarget = (matches) => ({{
  closest(selector) {{
    return matches.includes(selector) ? {{ selector }} : null;
  }},
}});
results.ignoreRowFocusForSelection = reviewModule.shouldIgnoreReviewRowFocusTarget(makeTarget([".gmail-review-select"]));
results.ignoreRowFocusForStartPage = reviewModule.shouldIgnoreReviewRowFocusTarget(makeTarget([".attachment-start-page"]));
results.ignoreRowFocusForButton = reviewModule.shouldIgnoreReviewRowFocusTarget(makeTarget(["button"]));
results.keepRowFocusForPlainCell = reviewModule.shouldIgnoreReviewRowFocusTarget(makeTarget([]));

reviewModule.clearConsumedReviewState(storage, context);
results.afterClear = reviewModule.readConsumedReviewState(storage, context);

console.log(JSON.stringify(results));
""".replace("{{", "{").replace("}}", "}")
    return run_browser_esm_json_probe(
        script,
        {"__GMAIL_REVIEW_MODULE_URL__": "gmail_review_state.js"},
        timeout_seconds=20,
    )


def test_gmail_review_state_storage_and_auto_open_rules() -> None:
    results = _run_review_state_probe()

    assert results["initial"] == {"reviewEventId": 0, "messageSignature": ""}
    assert results["afterWrite"] == {"reviewEventId": 5, "messageSignature": "sig-5"}
    assert results["openFresh"] is True
    assert results["noReopenSame"] is False
    assert results["noOpenWithSession"] is False
    assert results["openOnNewerEvent"] is True
    assert results["openOnResetEpoch"] is True
    assert results["stageIdle"] == "idle"
    assert results["stageReview"] == "review"
    assert results["stageTranslationRunning"] == "translation_running"
    assert results["stageTranslationRecovery"] == "translation_recovery"
    assert results["stageTranslationSave"] == "translation_save"
    assert results["stageTranslationFinalize"] == "translation_finalize"
    assert results["stageInterpretationReview"] == "interpretation_review"
    assert results["stageInterpretationFinalize"] == "interpretation_finalize"
    assert results["workflowTranslation"]["label"] == "Translation"
    assert results["workflowTranslation"]["prepareLabel"] == "Continue with selected attachments"
    assert results["workflowInterpretation"]["label"] == "Interpretation"
    assert results["workflowInterpretation"]["prepareLabel"] == "Continue with selected notice"
    assert results["kindPdf"] == "PDF"
    assert results["kindImage"] == "Image"
    assert results["kindUnknown"] == "Unknown"
    assert "Open this from Gmail" in results["stagePresentationIdle"]["description"]
    assert "Choose your workflow" in results["stagePresentationReview"]["description"]
    assert results["stagePresentationPrepared"]["title"] == "Translation is ready to start."
    assert "sentença 305.pdf" in results["stagePresentationPrepared"]["description"]
    assert results["stagePresentationRunning"]["title"] == "Translation is running."
    assert results["stagePresentationSave"]["title"] == "Review and save this attachment."
    assert results["stagePresentationFinalize"]["title"] == "Finalize Gmail reply."
    assert results["stagePresentationInterpretationReview"]["title"] == "Interpretation details are ready."
    assert "create the Gmail reply" in results["stagePresentationInterpretationReview"]["description"]
    assert results["stagePresentationInterpretationFinalize"]["title"] == "Create Gmail reply."
    assert "final files are ready" in results["stagePresentationInterpretationFinalize"]["description"]
    assert results["ctaHidden"]["visible"] is False
    assert results["ctaTranslationRecovery"]["visible"] is True
    assert results["ctaTranslationRecovery"]["action"] == "resume-translation-recovery"
    assert results["ctaTranslationRecovery"]["label"] == "Resume Recovery"
    assert results["ctaTranslationRecovery"]["title"] == "Translation needs attention."
    assert results["ctaTranslationSave"]["visible"] is True
    assert results["ctaTranslationSave"]["action"] == "resume-translation-save"
    assert results["ctaTranslationSave"]["label"] == "Resume Current Step"
    assert results["ctaTranslationFinalize"]["action"] == "resume-translation-finalize"
    assert results["ctaTranslationFinalize"]["label"] == "Resume Current Step"
    assert results["ctaInterpretationFinalize"]["action"] == "resume-interpretation-finalize"
    assert results["recoveredHidden"]["visible"] is False
    assert results["recoveredVisible"]["visible"] is True
    assert results["recoveredVisible"]["action"] == "open-restored-translation-finalize"
    assert results["recoveredVisible"]["label"] == "Open Last Finalization Result"
    assert results["recoveredVisible"]["title"] == "Last Gmail reply is still available."
    assert "Recovered batch" in results["recoveredVisible"]["description"]
    assert results["stableRecoveredOnly"] is False
    assert results["stableLoadedMessage"] is True
    assert results["stableWarmupPending"] is False
    assert results["redoHidden"]["visible"] is False
    assert results["redoFresh"]["visible"] is True
    assert results["redoFresh"]["enabled"] is True
    assert results["redoFresh"]["action"] == "redo-current-translation"
    assert results["redoMatchingCompleted"]["enabled"] is True
    assert results["redoMatchingCompleted"]["matchingJob"]["job_id"] == "tx-1"
    assert "keeps the earlier files" in results["redoMatchingCompleted"]["description"]
    assert results["redoMatchingRunning"]["enabled"] is False
    assert results["redoMatchingRunning"]["blocked"] is True
    assert results["redoMatchingRunning"]["matchingJob"]["job_id"] == "tx-2"
    assert results["previewInitial"] == {
        "open": False,
        "attachmentId": "",
        "previewHref": "",
        "previewMimeType": "",
        "page": 1,
        "pageCount": 0,
        "editable": False,
    }
    assert results["previewOpened"] == {
        "open": True,
        "attachmentId": "att-1",
        "previewHref": "/api/gmail/attachment/att-1",
        "previewMimeType": "application/pdf",
        "page": 2,
        "pageCount": 5,
        "editable": True,
    }
    assert results["previewMoved"]["page"] == 4
    assert results["previewApplied"] == 4
    assert results["previewUnchangedOnClose"] == 2
    assert results["previewInspectOnly"]["page"] == 1
    assert results["previewInspectOnlyMoved"]["page"] == 1
    assert results["previewInspectOnlyApplied"] == 1
    assert results["previewIsOpen"] is True
    assert results["previewClosedIsOpen"] is False
    assert results["ignoreRowFocusForSelection"] is True
    assert results["ignoreRowFocusForStartPage"] is True
    assert results["ignoreRowFocusForButton"] is True
    assert results["keepRowFocusForPlainCell"] is False
    assert results["afterClear"] == {"reviewEventId": 0, "messageSignature": ""}
