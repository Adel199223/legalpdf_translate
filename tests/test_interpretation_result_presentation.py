from __future__ import annotations

from .browser_esm_probe import run_browser_esm_json_probe


def test_interpretation_result_presentation_builds_export_and_gmail_cards() -> None:
    script = r"""
const resultPresentation = await import(__INTERPRETATION_RESULT_PRESENTATION_MODULE_URL__);

const malicious = "<img src=x onerror=alert(1)><script>bad()</script>";
const presentation = {
  export: {
    readyLabel: `Ready ${malicious}`,
    localOnlyLabel: `Local only ${malicious}`,
    failedLabel: `Failed ${malicious}`,
    readyTitle: `Ready title ${malicious}`,
    localOnlyTitle: `Local title ${malicious}`,
    failedTitle: `Failed title ${malicious}`,
    pdfReadyLabel: `PDF ready ${malicious}`,
  },
  drawer: {
    gmailResultEmpty: `No Gmail result ${malicious}`,
  },
  gmailResult: {
    createdTitle: `Gmail reply created ${malicious}`,
    localOnlyTitle: `Local-only Gmail reply ${malicious}`,
    warningTitle: `Gmail reply needs attention ${malicious}`,
    createdLabel: `Created ${malicious}`,
    localOnlyLabel: `Local only ${malicious}`,
    warningLabel: `Needs attention ${malicious}`,
  },
};

const cases = {
  exportNullSafe: resultPresentation.buildInterpretationExportResultPresentation(),
  exportOk: resultPresentation.buildInterpretationExportResultPresentation({
    payload: {
      status: "ok",
      normalized_payload: {
        docx_path: `C:/cases/result ${malicious}.docx`,
        pdf_path: `C:/cases/result ${malicious}.pdf`,
      },
      diagnostics: {
        pdf_export: {
          ok: true,
          failure_message: `Ignored ${malicious}`,
        },
      },
    },
    presentation,
  }),
  exportLocalOnly: resultPresentation.buildInterpretationExportResultPresentation({
    payload: {
      status: "local_only",
      normalized_payload: {},
      diagnostics: {
        pdf_export: {
          ok: false,
          failure_message: `PDF failure ${malicious}`,
        },
      },
    },
    presentation,
  }),
  exportLocalOnlyFallback: resultPresentation.buildInterpretationExportResultPresentation({
    payload: {
      status: "local_only",
      diagnostics: {
        pdf_export: {
          ok: false,
        },
      },
    },
    presentation,
  }),
  exportFailed: resultPresentation.buildInterpretationExportResultPresentation({
    payload: {
      status: `error_${malicious}`,
      diagnostics: {
        pdf_export: {
          ok: false,
        },
      },
    },
    presentation,
  }),
  gmailNullSafe: resultPresentation.buildInterpretationGmailResultPresentation(),
  gmailOk: resultPresentation.buildInterpretationGmailResultPresentation({
    payload: {
      status: "ok",
      normalized_payload: {
        docx_path: `C:/cases/gmail ${malicious}.docx`,
        pdf_path: `C:/cases/gmail ${malicious}.pdf`,
        gmail_draft_result: {
          message: `Draft ready ${malicious}`,
        },
      },
    },
    presentation,
  }),
  gmailLocalOnly: resultPresentation.buildInterpretationGmailResultPresentation({
    payload: {
      status: "local_only",
      normalized_payload: {
        draft_prereqs: {
          message: `Draft prerequisites ${malicious}`,
        },
      },
    },
    presentation,
  }),
  gmailWarningPdfFallback: resultPresentation.buildInterpretationGmailResultPresentation({
    payload: {
      status: "warning",
      normalized_payload: {
        pdf_path: `C:/cases/fallback ${malicious}.pdf`,
      },
    },
    presentation,
  }),
  gmailWarningDocxFallback: resultPresentation.buildInterpretationGmailResultPresentation({
    payload: {
      status: "error",
      normalized_payload: {
        docx_path: `C:/cases/fallback ${malicious}.docx`,
      },
    },
    presentation,
  }),
  gmailEmpty: resultPresentation.buildInterpretationGmailResultPresentation({
    payload: {
      status: "error",
      normalized_payload: {},
    },
    presentation,
  }),
};

console.log(JSON.stringify({
  exportTypes: {
    exportResult: typeof resultPresentation.buildInterpretationExportResultPresentation,
    gmailResult: typeof resultPresentation.buildInterpretationGmailResultPresentation,
  },
  cases,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {
            "__INTERPRETATION_RESULT_PRESENTATION_MODULE_URL__": (
                "interpretation_result_presentation.js"
            )
        },
        timeout_seconds=20,
    )

    assert results["exportTypes"] == {
        "exportResult": "function",
        "gmailResult": "function",
    }
    assert results["cases"]["exportNullSafe"] == {
        "title": "The fee-request document could not be created.",
        "message": "",
        "chip": {"label": "Needs review", "tone": "bad"},
        "items": [
            {"label": "DOCX", "value": "Unavailable", "className": "word-break"},
            {"label": "PDF", "value": "Unavailable", "className": "word-break"},
            {"label": "PDF Export", "value": "Unavailable", "className": ""},
        ],
    }
    assert results["cases"]["exportOk"] == {
        "title": "Ready title <img src=x onerror=alert(1)><script>bad()</script>",
        "message": "",
        "chip": {
            "label": "Ready <img src=x onerror=alert(1)><script>bad()</script>",
            "tone": "ok",
        },
        "items": [
            {
                "label": "DOCX",
                "value": "C:/cases/result <img src=x onerror=alert(1)><script>bad()</script>.docx",
                "className": "word-break",
            },
            {
                "label": "PDF",
                "value": "C:/cases/result <img src=x onerror=alert(1)><script>bad()</script>.pdf",
                "className": "word-break",
            },
            {
                "label": "PDF Export",
                "value": "PDF ready <img src=x onerror=alert(1)><script>bad()</script>",
                "className": "",
            },
        ],
    }
    assert results["cases"]["exportLocalOnly"] == {
        "title": "PDF failure <img src=x onerror=alert(1)><script>bad()</script>",
        "message": "",
        "chip": {
            "label": "Local only <img src=x onerror=alert(1)><script>bad()</script>",
            "tone": "warn",
        },
        "items": [
            {"label": "DOCX", "value": "Unavailable", "className": "word-break"},
            {"label": "PDF", "value": "Unavailable", "className": "word-break"},
            {
                "label": "PDF Export",
                "value": "PDF failure <img src=x onerror=alert(1)><script>bad()</script>",
                "className": "",
            },
        ],
    }
    assert results["cases"]["exportLocalOnlyFallback"]["title"] == (
        "Local title <img src=x onerror=alert(1)><script>bad()</script>"
    )
    assert results["cases"]["exportLocalOnlyFallback"]["items"][2]["value"] == "Unavailable"
    assert results["cases"]["exportFailed"] == {
        "title": "Failed title <img src=x onerror=alert(1)><script>bad()</script>",
        "message": "",
        "chip": {
            "label": "Failed <img src=x onerror=alert(1)><script>bad()</script>",
            "tone": "bad",
        },
        "items": [
            {"label": "DOCX", "value": "Unavailable", "className": "word-break"},
            {"label": "PDF", "value": "Unavailable", "className": "word-break"},
            {"label": "PDF Export", "value": "Unavailable", "className": ""},
        ],
    }
    assert results["cases"]["gmailNullSafe"] == {
        "title": "Gmail reply created.",
        "message": "Gmail reply details will appear here after the final step.",
        "chip": {"label": "Gmail reply created", "tone": "ok"},
        "items": [
            {"label": "DOCX", "value": "Unavailable", "className": "word-break"},
            {"label": "PDF", "value": "Unavailable", "className": "word-break"},
            {"label": "Reply status", "value": "Gmail reply created", "className": ""},
        ],
    }
    assert results["cases"]["gmailOk"] == {
        "title": "Gmail reply created <img src=x onerror=alert(1)><script>bad()</script>",
        "message": "Draft ready <img src=x onerror=alert(1)><script>bad()</script>",
        "chip": {
            "label": "Created <img src=x onerror=alert(1)><script>bad()</script>",
            "tone": "ok",
        },
        "items": [
            {
                "label": "DOCX",
                "value": "C:/cases/gmail <img src=x onerror=alert(1)><script>bad()</script>.docx",
                "className": "word-break",
            },
            {
                "label": "PDF",
                "value": "C:/cases/gmail <img src=x onerror=alert(1)><script>bad()</script>.pdf",
                "className": "word-break",
            },
            {
                "label": "Reply status",
                "value": "Created <img src=x onerror=alert(1)><script>bad()</script>",
                "className": "",
            },
        ],
    }
    assert results["cases"]["gmailLocalOnly"]["title"] == (
        "Local-only Gmail reply <img src=x onerror=alert(1)><script>bad()</script>"
    )
    assert results["cases"]["gmailLocalOnly"]["message"] == (
        "Draft prerequisites <img src=x onerror=alert(1)><script>bad()</script>"
    )
    assert results["cases"]["gmailLocalOnly"]["chip"] == {
        "label": "Local only <img src=x onerror=alert(1)><script>bad()</script>",
        "tone": "warn",
    }
    assert results["cases"]["gmailLocalOnly"]["items"] == [
        {"label": "DOCX", "value": "Unavailable", "className": "word-break"},
        {"label": "PDF", "value": "Unavailable", "className": "word-break"},
        {
            "label": "Reply status",
            "value": "Local only <img src=x onerror=alert(1)><script>bad()</script>",
            "className": "",
        },
    ]
    assert results["cases"]["gmailWarningPdfFallback"]["message"] == (
        "C:/cases/fallback <img src=x onerror=alert(1)><script>bad()</script>.pdf"
    )
    assert results["cases"]["gmailWarningPdfFallback"]["items"] == [
        {"label": "DOCX", "value": "Unavailable", "className": "word-break"},
        {
            "label": "PDF",
            "value": "C:/cases/fallback <img src=x onerror=alert(1)><script>bad()</script>.pdf",
            "className": "word-break",
        },
        {
            "label": "Reply status",
            "value": "Needs attention <img src=x onerror=alert(1)><script>bad()</script>",
            "className": "",
        },
    ]
    assert results["cases"]["gmailWarningDocxFallback"]["message"] == (
        "C:/cases/fallback <img src=x onerror=alert(1)><script>bad()</script>.docx"
    )
    assert results["cases"]["gmailEmpty"]["message"] == (
        "No Gmail result <img src=x onerror=alert(1)><script>bad()</script>"
    )
