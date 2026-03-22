from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


def _run_interpretation_review_state_probe() -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for interpretation review-state coverage.")

    module_url = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
        / "interpretation_review_state.js"
    ).as_uri()

    script = f"""
const reviewModule = await import({json.dumps(module_url)});

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

console.log(JSON.stringify({{
  reference,
  unknownImported,
  unknownImportedDecomposed,
  knownNeedsPrompt,
  knownSavedDistance,
  invalidDistance,
  workspaceModes,
  drawerLayouts,
}}));
"""

    completed = subprocess.run(
        [node, "--input-type=module", "-"],
        input=script,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return json.loads(completed.stdout)


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
