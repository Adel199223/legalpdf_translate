from __future__ import annotations
import json

from .browser_esm_probe import run_browser_esm_json_probe


def _run_interpretation_review_state_probe() -> dict[str, object]:
    script = """
const reviewModule = await import(__INTERPRETATION_REVIEW_STATE_MODULE_URL__);

const reference = reviewModule.buildInterpretationReference(
  {{
    profile_id: "primary",
    travel_origin_label: "Marmelar",
    available_cities: ["Beja", "Vidigueira"],
    travel_distances_by_city: {{ Beja: 39 }},
  }},
  [
    {{
      id: "primary",
      travel_origin_label: "Marmelar",
      travel_distances_by_city: {{ Beja: 39, Cuba: 26 }},
    }},
  ],
  "primary",
);

const unknownImported = reviewModule.deriveInterpretationGuardState({{
  reference,
  caseCity: "",
  serviceCity: "",
  serviceSame: true,
  provisionalCaseCity: "Camões",
  provisionalServiceCity: "",
  includeTransport: true,
  travelKmOutbound: "",
}});

const unknownImportedDecomposed = reviewModule.deriveInterpretationGuardState({{
  reference,
  caseCity: "",
  serviceCity: "",
  serviceSame: true,
  provisionalCaseCity: "Camo\\u0303es",
  provisionalServiceCity: "",
  includeTransport: true,
  travelKmOutbound: "",
}});

const knownNeedsPrompt = reviewModule.deriveInterpretationGuardState({{
  reference,
  caseCity: "Beja",
  serviceCity: "Vidigueira",
  serviceSame: false,
  provisionalCaseCity: "",
  provisionalServiceCity: "",
  includeTransport: true,
  travelKmOutbound: "",
}});

const knownSavedDistance = reviewModule.deriveInterpretationGuardState({{
  reference,
  caseCity: "Beja",
  serviceCity: "Cuba",
  serviceSame: false,
  provisionalCaseCity: "",
  provisionalServiceCity: "",
  includeTransport: true,
  travelKmOutbound: "",
}});

const invalidDistance = reviewModule.deriveInterpretationGuardState({{
  reference,
  caseCity: "Beja",
  serviceCity: "Beja",
  serviceSame: true,
  provisionalCaseCity: "",
  provisionalServiceCity: "",
  includeTransport: true,
  travelKmOutbound: "0",
}});

const transportDisabled = reviewModule.deriveInterpretationGuardState({{
  reference,
  caseCity: "Beja",
  serviceCity: "Beja",
  serviceSame: true,
  provisionalCaseCity: "",
  provisionalServiceCity: "",
  includeTransport: false,
  travelKmOutbound: "",
}});

const workspaceModes = {{
  blank: reviewModule.deriveInterpretationWorkspaceMode({{
    snapshot: {{}},
    activeSession: null,
  }}),
  manualSeed: reviewModule.deriveInterpretationWorkspaceMode({{
    snapshot: {{
      caseNumber: "305/23.2GCBJA",
      caseCity: "Beja",
    }},
    activeSession: null,
  }}),
  gmailReview: reviewModule.deriveInterpretationWorkspaceMode({{
    snapshot: {{
      caseNumber: "305/23.2GCBJA",
    }},
    activeSession: {{
      kind: "interpretation",
      status: "prepared",
      draft_created: false,
      pdf_export: "",
    }},
  }}),
  gmailReviewEmptyPdfExportObject: reviewModule.deriveInterpretationWorkspaceMode({{
    snapshot: {{
      caseNumber: "305/23.2GCBJA",
    }},
    activeSession: {{
      kind: "interpretation",
      status: "prepared",
      draft_created: false,
      pdf_export: {{}},
    }},
  }}),
  gmailCompletedFromCompletionPayload: reviewModule.deriveInterpretationWorkspaceMode({{
    snapshot: {{
      caseNumber: "305/23.2GCBJA",
    }},
    activeSession: {{
      kind: "interpretation",
      status: "prepared",
      draft_created: false,
      pdf_export: {{}},
    }},
    hasCompletionPayload: true,
  }}),
  gmailCompleted: reviewModule.deriveInterpretationWorkspaceMode({{
    snapshot: {{
      caseNumber: "305/23.2GCBJA",
    }},
    activeSession: {{
      kind: "interpretation",
      status: "draft_ready",
      draft_created: true,
      pdf_export: "C:/tmp/out.pdf",
    }},
  }}),
}};

const drawerLayouts = {{
  gmailReview: reviewModule.deriveInterpretationDrawerLayout({{
    workspaceMode: "gmail_review",
    activeSession: {{ kind: "interpretation", status: "prepared" }},
    serviceSame: true,
    validationField: "",
  }}),
  gmailReviewServiceValidation: reviewModule.deriveInterpretationDrawerLayout({{
    workspaceMode: "gmail_review",
    activeSession: {{ kind: "interpretation", status: "prepared" }},
    serviceSame: true,
    validationField: "service_city",
  }}),
  manualSeed: reviewModule.deriveInterpretationDrawerLayout({{
    workspaceMode: "manual_seed",
    activeSession: null,
    serviceSame: true,
    validationField: "",
  }}),
  gmailCompleted: reviewModule.deriveInterpretationDrawerLayout({{
    workspaceMode: "gmail_completed",
    activeSession: {{ kind: "interpretation", status: "draft_ready", draft_created: true }},
    serviceSame: true,
    validationField: "",
  }}),
}};

const presentations = {{
  blank: reviewModule.deriveInterpretationReviewPresentation({{
    snapshot: {{}},
    activeSession: null,
    workspaceMode: "blank",
    hasReviewData: false,
  }}),
  manualSeed: reviewModule.deriveInterpretationReviewPresentation({{
    snapshot: {{
      caseNumber: "305/23.2GCBJA",
      caseCity: "Beja",
      serviceDate: "2026-03-20",
    }},
    activeSession: null,
    workspaceMode: "manual_seed",
    hasReviewData: true,
  }}),
  savedRow: reviewModule.deriveInterpretationReviewPresentation({{
    snapshot: {{
      rowId: "41",
      caseNumber: "305/23.2GCBJA",
      caseCity: "Beja",
      serviceDate: "2026-03-20",
    }},
    activeSession: null,
    workspaceMode: "manual_seed",
    hasReviewData: true,
  }}),
  gmailReview: reviewModule.deriveInterpretationReviewPresentation({{
    snapshot: {{
      caseNumber: "305/23.2GCBJA",
      caseCity: "Beja",
    }},
    activeSession: {{ kind: "interpretation", status: "prepared" }},
    workspaceMode: "gmail_review",
    hasReviewData: true,
  }}),
  gmailCompleted: reviewModule.deriveInterpretationReviewPresentation({{
    snapshot: {{
      caseNumber: "305/23.2GCBJA",
      caseCity: "Beja",
    }},
    activeSession: {{
      kind: "interpretation",
      status: "draft_ready",
      draft_created: true,
      pdf_export: "C:/tmp/out.pdf",
    }},
    workspaceMode: "gmail_completed",
    hasReviewData: true,
    completionPayload: {{ status: "ok" }},
  }}),
}};

const disclosures = {{
  defaults: reviewModule.deriveInterpretationDisclosurePresentation({{
    serviceSame: true,
    textCustomized: false,
    recipientOverride: "",
    amountsTouched: false,
    includeTransport: true,
  }}),
  customized: reviewModule.deriveInterpretationDisclosurePresentation({{
    serviceSame: false,
    textCustomized: true,
    recipientOverride: "Tribunal Judicial",
    amountsTouched: true,
    includeTransport: false,
  }}),
}};

console.log(JSON.stringify({{
  reference,
  unknownImported,
  unknownImportedDecomposed,
  knownNeedsPrompt,
  knownSavedDistance,
  invalidDistance,
  transportDisabled,
  workspaceModes,
  drawerLayouts,
  presentations,
  disclosures,
}}));
""".replace("{{", "{").replace("}}", "}")
    return run_browser_esm_json_probe(
        script,
        {"__INTERPRETATION_REVIEW_STATE_MODULE_URL__": "interpretation_review_state.js"},
        timeout_seconds=20,
    )


def test_interpretation_review_state_blocks_unknown_city_and_guides_distance_prompt() -> None:
    results = _run_interpretation_review_state_probe()

    assert "Cuba" in results["reference"]["availableCities"]
    assert results["reference"]["travelDistancesByCity"]["Cuba"] == 26

    assert results["unknownImported"]["blocked"] is True
    assert results["unknownImported"]["blockedCode"] == "unknown_case_city"
    assert results["unknownImported"]["provisionalCaseCity"] == "Camões"
    assert results["unknownImportedDecomposed"]["provisionalCaseCity"] == "Camões"

    assert results["knownNeedsPrompt"]["blocked"] is False
    assert results["knownNeedsPrompt"]["distancePromptNeeded"] is True
    assert results["knownNeedsPrompt"]["effectiveServiceCity"] == "Vidigueira"

    assert results["knownSavedDistance"]["blocked"] is False
    assert results["knownSavedDistance"]["distancePromptNeeded"] is False
    assert results["knownSavedDistance"]["knownDistance"] == 26

    assert results["invalidDistance"]["blocked"] is True
    assert results["invalidDistance"]["blockedCode"] == "distance_must_be_positive"
    assert results["transportDisabled"]["distanceHint"] == "Transport sentence is turned off for this document."

    assert results["workspaceModes"] == {
        "blank": "blank",
        "manualSeed": "manual_seed",
        "gmailReview": "gmail_review",
        "gmailReviewEmptyPdfExportObject": "gmail_review",
        "gmailCompletedFromCompletionPayload": "gmail_completed",
        "gmailCompleted": "gmail_completed",
    }

    assert results["drawerLayouts"]["gmailReview"]["gmailMode"] is True
    assert results["drawerLayouts"]["gmailReview"]["sections"] == {
        "serviceOpen": False,
        "textOpen": True,
        "recipientOpen": False,
        "amountsOpen": False,
    }
    assert results["drawerLayouts"]["gmailReview"]["actions"] == {
        "showFinalizeGmail": True,
        "showGenerateDocxPdf": False,
        "showSaveRow": False,
        "showNewBlank": False,
        "showFooterClose": False,
    }

    assert results["drawerLayouts"]["gmailReviewServiceValidation"]["sections"]["serviceOpen"] is True

    assert results["drawerLayouts"]["manualSeed"]["gmailMode"] is False
    assert results["drawerLayouts"]["manualSeed"]["actions"] == {
        "showFinalizeGmail": False,
        "showGenerateDocxPdf": True,
        "showSaveRow": True,
        "showNewBlank": True,
        "showFooterClose": True,
    }

    assert results["drawerLayouts"]["gmailCompleted"]["actions"] == {
        "showFinalizeGmail": False,
        "showGenerateDocxPdf": False,
        "showSaveRow": False,
        "showNewBlank": False,
        "showFooterClose": False,
    }

    assert results["presentations"]["blank"]["drawer"]["status"] == "Upload a notification or start a blank request to begin."
    assert results["presentations"]["blank"]["actions"] == {
        "openReview": "Review details",
        "startBlank": "Start blank request",
        "refreshHistory": "Refresh history",
        "sessionPrimary": "Review details",
        "sessionSecondary": "Review Gmail message",
        "saveRow": "Save case record",
        "export": "Create fee-request document",
        "finalizeGmail": "Create Gmail reply",
    }
    assert results["presentations"]["manualSeed"]["drawer"]["status"] == (
        "Check the recovered details, then save the case record or create the fee-request document."
    )
    assert results["presentations"]["manualSeed"]["drawer"]["summaryTitle"] == "Recovered case details are ready."
    assert results["presentations"]["savedRow"]["reviewHome"]["title"] == "Saved case record loaded."
    assert results["presentations"]["savedRow"]["reviewHome"]["subtitle"] == "Review the fields below and save any edits."
    assert results["presentations"]["gmailReview"]["drawer"]["status"] == "Check the notice details, then create the Gmail reply."
    assert results["presentations"]["gmailReview"]["drawer"]["contextTitle"] == "Create the Gmail reply after review."
    assert results["presentations"]["gmailCompleted"]["drawer"]["status"] == "The Gmail reply and exported files are ready."
    assert results["presentations"]["gmailCompleted"]["actions"]["sessionPrimary"] == "View final result"
    assert results["presentations"]["gmailCompleted"]["gmailResult"] == {
        "createdTitle": "Gmail reply created.",
        "createdLabel": "Gmail reply created",
        "localOnlyTitle": "Final files are ready.",
        "localOnlyLabel": "Final files are ready",
        "warningTitle": "Gmail reply needs review.",
        "warningLabel": "Gmail reply needs review",
    }
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

    disclosure_json = json.dumps(results["disclosures"], ensure_ascii=False)
    assert "Same as case" not in disclosure_json
    assert "Auto-derived recipient" not in disclosure_json
    assert "Pages, words, rate, totals" not in disclosure_json
    assert "honorarios export" not in disclosure_json
