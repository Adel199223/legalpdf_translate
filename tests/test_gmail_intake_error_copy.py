from __future__ import annotations

import json

import pytest

from .browser_esm_probe import run_browser_esm_json_probe


def _render_failed_bootstrap(
    *, reason: str, subject: str, classification: str = "unavailable", context: str = "intake_context"
) -> dict[str, object]:
    # Same presenters and DOM renderers used by renderGmailBootstrap; no Gmail service.
    script = """
const result = await import(__RESULT__);
const stage = await import(__STAGE__);
const ui = await import(__UI__);
const diagnostics = await import(__DIAGNOSTICS__);
const input = __INPUT__;
const nodes = [];
function element(tagName = "div") {
  const node = {
    tagName, children: [], dataset: {}, classList: { add() {}, remove() {} },
    appendChild(child) { this.children.push(child); return child; },
    replaceChildren(...children) { this.children = children; },
  };
  let text = "";
  Object.defineProperty(node, "textContent", {
    get() { return text; },
    set(value) { text = String(value ?? ""); this.children = []; },
  });
  Object.defineProperty(node, "innerHTML", {
    set() { throw new Error("Unsafe dynamic HTML insertion"); },
  });
  nodes.push(node);
  return node;
}
const panel = element("p");
globalThis.document = {
  createElement: element,
  getElementById(id) { return id === "gmail-status" ? panel : null; },
};
const loadResult = { ok: false, classification: input.classification, status_message: input.reason };
const options = { loadResult, workflow: { label: "Translation" } };
if (input.context === "intake_context") loadResult.intake_context = { subject: input.subject };
else options[input.context] = { subject: input.subject };
const card = result.buildGmailMessageResultPresentation(options);
const status = stage.buildGmailPanelStatusPresentation({ stage: "review", loadResult });
const container = element();
ui.renderGmailMessageResultInto(container, element(), card);
diagnostics.setPanelStatus("gmail", status.gmail.tone, status.gmail.message);
function text(node) { return node.textContent + node.children.map(text).join(""); }
console.log(JSON.stringify({ card, status: status.gmail, visibleText: text(container),
  panelText: panel.textContent, createdTags: nodes.map(node => node.tagName) }));
""".replace("__INPUT__", json.dumps({
        "reason": reason, "subject": subject, "classification": classification, "context": context,
    }))
    return run_browser_esm_json_probe(script, {
        "__RESULT__": "gmail_result_presentation.js",
        "__STAGE__": "gmail_stage_presentation.js",
        "__UI__": "gmail_result_ui.js",
        "__DIAGNOSTICS__": "diagnostics_ui.js",
    })


@pytest.mark.parametrize("context", ["intake_context", "defaults", "pendingContext"])
def test_failed_bootstrap_preserves_subject_and_actionable_missing_helper_reason(context: str) -> None:
    reason = "Windows gog.exe not found. Set the Gmail helper path in Settings."
    result = _render_failed_bootstrap(reason=reason, subject="Fictional notice", context=context)
    assert result["card"]["message"] == "Fictional notice"
    assert reason in result["visibleText"]
    assert result["panelText"] == reason
    assert result["status"]["tone"] == "warn"


def test_failed_bootstrap_reason_and_subject_render_as_literal_text() -> None:
    reason = '<img src=x onerror="alert(1)"><script>bad()</script>'
    subject = '<svg onload="alert(2)">Fictional subject</svg>'
    result = _render_failed_bootstrap(reason=reason, subject=subject, classification="failed")
    assert reason in result["visibleText"]
    assert subject in result["visibleText"]
    assert result["panelText"] == reason
    assert result["status"]["tone"] == "bad"
    assert not {"img", "script", "svg"}.intersection(result["createdTags"])


def test_failed_bootstrap_without_reason_has_recovery_copy() -> None:
    result = _render_failed_bootstrap(reason=" \n ", subject="")
    expected = "Gmail message could not be loaded. Open Advanced message details to review the message and try again."
    assert result["card"]["message"] == "No subject"
    assert expected in result["visibleText"]
    assert result["panelText"] == expected


def test_successful_result_and_active_session_keep_existing_copy() -> None:
    script = """
const result = await import(__RESULT__);
const stage = await import(__STAGE__);
const success = { ok: true, status_message: "Loaded detail", message: {
  subject: "Loaded subject", attachments: [{ attachment_id: "fictional" }] } };
const card = result.buildGmailMessageResultPresentation({ loadResult: success,
  defaults: { subject: "Stale context" } });
const active = stage.buildGmailPanelStatusPresentation({ stage: "translation_running",
  activeSession: { kind: "translation", completed: false },
  loadResult: { ok: false, status_message: "Older load failure" } });
console.log(JSON.stringify({ card, active: active.gmail }));
"""
    result = run_browser_esm_json_probe(script, {
        "__RESULT__": "gmail_result_presentation.js", "__STAGE__": "gmail_stage_presentation.js",
    })
    assert result["card"]["title"] == "Gmail message ready to review."
    assert result["card"]["message"] == "Loaded subject"
    assert len(result["card"]["gridItems"]) == 4
    assert result["card"]["gridItems"][2]["value"] == 1
    assert result["active"]["message"] != "Older load failure"
