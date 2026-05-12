from __future__ import annotations

from .browser_esm_probe import run_browser_esm_json_probe


def test_interpretation_review_presentation_module_builds_review_surfaces() -> None:
    script = r"""
const presentation = await import(__INTERPRETATION_REVIEW_PRESENTATION_MODULE_URL__);

const malicious = "<img src=x onerror=alert(1)><script>bad()</script>";
const maliciousPresentation = {
  gmailResult: {
    createdTitle: `Created title ${malicious}`,
    createdLabel: `Created label ${malicious}`,
    localOnlyTitle: `Local title ${malicious}`,
    localOnlyLabel: `Local label ${malicious}`,
    warningTitle: `Warning title ${malicious}`,
    warningLabel: `Warning label ${malicious}`,
  },
};

const reviewSurfaces = {
  nullSafe: presentation.deriveInterpretationReviewPresentation(),
  blank: presentation.deriveInterpretationReviewPresentation({
    snapshot: {},
    activeSession: null,
    workspaceMode: "blank",
    hasReviewData: false,
  }),
  manualSeed: presentation.deriveInterpretationReviewPresentation({
    snapshot: {
      caseNumber: "305/23.2GCBJA",
      caseCity: "Beja",
      serviceDate: "2026-03-20",
    },
    activeSession: null,
    workspaceMode: "manual_seed",
    hasReviewData: true,
  }),
  savedRow: presentation.deriveInterpretationReviewPresentation({
    snapshot: {
      rowId: "41",
      caseNumber: "305/23.2GCBJA",
      caseCity: "Beja",
      serviceDate: "2026-03-20",
    },
    activeSession: null,
    workspaceMode: "manual_seed",
    hasReviewData: true,
  }),
  gmailReview: presentation.deriveInterpretationReviewPresentation({
    snapshot: {
      caseNumber: "305/23.2GCBJA",
      caseCity: "Beja",
    },
    activeSession: { kind: "interpretation", status: "prepared" },
    workspaceMode: "gmail_review",
    hasReviewData: true,
  }),
  gmailCompleted: presentation.deriveInterpretationReviewPresentation({
    snapshot: {
      caseNumber: "305/23.2GCBJA",
      caseCity: "Beja",
    },
    activeSession: {
      kind: "interpretation",
      status: "draft_ready",
      draft_created: true,
      pdf_export: { pdf_path: "C:/tmp/out.pdf" },
    },
    workspaceMode: "gmail_completed",
    hasReviewData: true,
    completionPayload: { status: "ok" },
  }),
  maliciousInvalid: presentation.deriveInterpretationReviewPresentation({
    snapshot: malicious,
    activeSession: malicious,
    workspaceMode: `unknown_${malicious}`,
    hasReviewData: false,
    completionPayload: malicious,
  }),
};

const disclosures = {
  nullSafe: presentation.deriveInterpretationDisclosurePresentation(malicious),
  defaults: presentation.deriveInterpretationDisclosurePresentation({
    serviceSame: true,
    textCustomized: false,
    recipientOverride: "",
    amountsTouched: false,
    includeTransport: true,
  }),
  customized: presentation.deriveInterpretationDisclosurePresentation({
    serviceSame: false,
    textCustomized: true,
    recipientOverride: `Tribunal ${malicious}`,
    amountsTouched: true,
    includeTransport: false,
  }),
};

const drawerLayouts = {
  nullSafe: presentation.deriveInterpretationDrawerLayout(),
  gmailReview: presentation.deriveInterpretationDrawerLayout({
    workspaceMode: "gmail_review",
    activeSession: { kind: "interpretation", status: "prepared" },
    serviceSame: true,
    validationField: "",
  }),
  gmailReviewServiceValidation: presentation.deriveInterpretationDrawerLayout({
    workspaceMode: "gmail_review",
    activeSession: { kind: "interpretation", status: "prepared" },
    serviceSame: true,
    validationField: "service_city",
  }),
  manualSeed: presentation.deriveInterpretationDrawerLayout({
    workspaceMode: "manual_seed",
    activeSession: null,
    serviceSame: true,
    validationField: "",
  }),
  gmailCompleted: presentation.deriveInterpretationDrawerLayout({
    workspaceMode: "gmail_completed",
    activeSession: { kind: "interpretation", status: "draft_ready", draft_created: true },
    serviceSame: true,
    validationField: "",
  }),
};

const chips = {
  nullSafe: presentation.buildInterpretationSessionChip(),
  ready: presentation.buildInterpretationSessionChip({
    session: { kind: "interpretation" },
    workspaceMode: "gmail_review",
  }),
  maliciousStatus: presentation.buildInterpretationSessionChip({
    session: { kind: "interpretation", status: `draft_ready_${malicious}` },
    workspaceMode: "gmail_review",
  }),
  completedOk: presentation.buildInterpretationSessionChip({
    session: { kind: "interpretation", status: "prepared" },
    workspaceMode: "gmail_completed",
    completionPayload: { status: "ok" },
    presentation: maliciousPresentation,
  }),
  completedWarning: presentation.buildInterpretationSessionChip({
    session: { kind: "interpretation", draft_failure_reason: `No draft ${malicious}` },
    workspaceMode: "gmail_completed",
    presentation: maliciousPresentation,
  }),
};

const completionCards = {
  nullSafe: presentation.buildInterpretationCompletionCardPresentation(),
  hidden: presentation.buildInterpretationCompletionCardPresentation({
    activeSession: { kind: "interpretation", draft_created: true },
    workspaceMode: "gmail_review",
    completionPayload: {
      status: "ok",
      normalized_payload: {
        gmail_draft_result: { message: `Hidden draft ${malicious}` },
        pdf_path: `C:/hidden-${malicious}.pdf`,
        docx_path: `C:/hidden-${malicious}.docx`,
      },
    },
    presentation: maliciousPresentation,
  }),
  okPayload: presentation.buildInterpretationCompletionCardPresentation({
    activeSession: { kind: "interpretation", status: "prepared" },
    workspaceMode: "gmail_completed",
    completionPayload: {
      status: "ok",
      normalized_payload: {
        gmail_draft_result: { message: `Draft ${malicious}` },
        pdf_path: " C:/tmp/final.pdf ",
        docx_path: " C:/tmp/final.docx ",
      },
    },
    presentation: maliciousPresentation,
  }),
  localOnlyPrereq: presentation.buildInterpretationCompletionCardPresentation({
    activeSession: { kind: "interpretation" },
    workspaceMode: "gmail_completed",
    completionPayload: {
      status: "local_only",
      normalized_payload: {
        draft_prereqs: { message: `Prereq ${malicious}` },
        pdfPath: " C:/tmp/local.pdf ",
        docxPath: " C:/tmp/local.docx ",
      },
    },
    presentation: maliciousPresentation,
  }),
  warningFallback: presentation.buildInterpretationCompletionCardPresentation({
    activeSession: { kind: "interpretation", status: "draft_failed" },
    workspaceMode: "gmail_completed",
    completionPayload: {
      status: "draft_unavailable",
      normalized_payload: {},
    },
    presentation: maliciousPresentation,
  }),
};

console.log(JSON.stringify({
  exportTypes: {
    deriveInterpretationDisclosurePresentation: typeof presentation.deriveInterpretationDisclosurePresentation,
    deriveInterpretationReviewPresentation: typeof presentation.deriveInterpretationReviewPresentation,
    buildInterpretationSessionChip: typeof presentation.buildInterpretationSessionChip,
    buildInterpretationCompletionCardPresentation: typeof presentation.buildInterpretationCompletionCardPresentation,
    deriveInterpretationDrawerLayout: typeof presentation.deriveInterpretationDrawerLayout,
  },
  reviewSurfaces,
  disclosures,
  drawerLayouts,
  chips,
  completionCards,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {
            "__INTERPRETATION_REVIEW_PRESENTATION_MODULE_URL__": (
                "interpretation_review_presentation.js"
            )
        },
        timeout_seconds=20,
    )

    assert results["exportTypes"] == {
        "deriveInterpretationDisclosurePresentation": "function",
        "deriveInterpretationReviewPresentation": "function",
        "buildInterpretationSessionChip": "function",
        "buildInterpretationCompletionCardPresentation": "function",
        "deriveInterpretationDrawerLayout": "function",
    }

    blank = results["reviewSurfaces"]["blank"]
    assert blank["workspaceMode"] == "blank"
    assert blank["gmailMode"] is False
    assert blank["reviewDataReady"] is False
    assert blank["rowLoaded"] is False
    assert blank["drawer"]["summaryTitle"] == "Upload a notification or start a blank request to begin."

    assert results["reviewSurfaces"]["manualSeed"]["reviewHome"]["title"] == (
        "Recovered case details are ready."
    )
    saved_row = results["reviewSurfaces"]["savedRow"]
    assert saved_row["rowLoaded"] is True
    assert saved_row["reviewHome"]["title"] == "Saved case record loaded."

    gmail_review = results["reviewSurfaces"]["gmailReview"]
    assert gmail_review["gmailMode"] is True
    assert gmail_review["home"]["status"] == "Review the notice details, then create the Gmail reply."
    assert gmail_review["actions"]["sessionPrimary"] == "Review details"
    assert gmail_review["drawer"]["summaryTitle"] == "Notice details are ready to review."

    gmail_completed = results["reviewSurfaces"]["gmailCompleted"]
    assert gmail_completed["workspaceMode"] == "gmail_completed"
    assert gmail_completed["home"]["resultTitle"] == "Gmail reply ready"
    assert gmail_completed["actions"]["sessionPrimary"] == "View final result"
    assert gmail_completed["drawer"]["status"] == "The Gmail reply and exported files are ready."

    malicious_invalid = results["reviewSurfaces"]["maliciousInvalid"]
    assert malicious_invalid["workspaceMode"] == "blank"
    assert malicious_invalid["reviewDataReady"] is False
    assert malicious_invalid["drawer"]["title"] == "Review Interpretation Request"

    assert results["disclosures"]["nullSafe"] == results["disclosures"]["defaults"]
    assert results["disclosures"]["defaults"] == {
        "serviceSummary": "Using the case details",
        "textSummary": "Optional wording and filename",
        "recipientSummary": "Recipient is filled automatically",
        "amountsSummary": "Optional amounts and internal totals",
        "transportDisabledHint": "",
    }
    assert results["disclosures"]["customized"] == {
        "serviceSummary": "Custom service details ready",
        "textSummary": "Custom document options ready",
        "recipientSummary": "Custom recipient text ready",
        "amountsSummary": "Amounts and totals ready",
        "transportDisabledHint": "Transport sentence is turned off for this document.",
    }

    assert results["drawerLayouts"]["gmailReview"]["actions"]["showFinalizeGmail"] is True
    assert results["drawerLayouts"]["gmailReview"]["actions"]["showGenerateDocxPdf"] is False
    assert results["drawerLayouts"]["gmailReview"]["sections"]["serviceOpen"] is False
    assert (
        results["drawerLayouts"]["gmailReviewServiceValidation"]["sections"]["serviceOpen"]
        is True
    )
    assert results["drawerLayouts"]["manualSeed"]["actions"]["showSaveRow"] is True
    assert results["drawerLayouts"]["gmailCompleted"]["actions"]["showFinalizeGmail"] is False

    assert results["chips"]["nullSafe"] == {"tone": "info", "label": "Ready"}
    assert results["chips"]["ready"] == {"tone": "info", "label": "Ready"}
    assert results["chips"]["maliciousStatus"] == {
        "tone": "info",
        "label": "draft ready <img src=x onerror=alert(1)><script>bad()</script>",
    }
    assert results["chips"]["completedOk"] == {
        "tone": "ok",
        "label": "Created label <img src=x onerror=alert(1)><script>bad()</script>",
    }
    assert results["chips"]["completedWarning"] == {
        "tone": "bad",
        "label": "Warning label <img src=x onerror=alert(1)><script>bad()</script>",
    }

    assert results["completionCards"]["nullSafe"] == {
        "completed": False,
        "title": "",
        "message": "",
        "chip": {"tone": "info", "label": "Ready"},
        "docxPath": "",
        "pdfPath": "",
    }
    assert results["completionCards"]["hidden"]["completed"] is False
    assert results["completionCards"]["okPayload"] == {
        "completed": True,
        "title": "Created title <img src=x onerror=alert(1)><script>bad()</script>",
        "message": "Draft <img src=x onerror=alert(1)><script>bad()</script>",
        "chip": {
            "tone": "ok",
            "label": "Created label <img src=x onerror=alert(1)><script>bad()</script>",
        },
        "docxPath": "C:/tmp/final.docx",
        "pdfPath": "C:/tmp/final.pdf",
    }
    assert results["completionCards"]["localOnlyPrereq"]["title"] == (
        "Local title <img src=x onerror=alert(1)><script>bad()</script>"
    )
    assert results["completionCards"]["localOnlyPrereq"]["chip"]["tone"] == "warn"
    assert results["completionCards"]["warningFallback"]["title"] == (
        "Warning title <img src=x onerror=alert(1)><script>bad()</script>"
    )
