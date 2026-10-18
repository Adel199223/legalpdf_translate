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
    assert result["card"]["message"] == "Message details unavailable"
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


@pytest.mark.parametrize("reason", [
    'oauth2: "invalid_grant" "Token has been expired or revoked."',
    '{"error":"invalid_grant","error_description":"Token has been expired or revoked."}',
])
def test_auth_failure_has_shared_reconnect_copy_without_transport_details(reason: str) -> None:
    result = _render_failed_bootstrap(reason=reason, subject="Fictional request", classification="failed")
    expected = "Gmail access has expired or was revoked. Reconnect your Gmail account, then load this message again."
    assert result["panelText"] == expected
    assert expected in result["visibleText"]
    assert reason not in result["visibleText"]


@pytest.mark.parametrize("reason", [
    '{"error":"remote failure","url":"https://example.test/private"}',
    "GET https://example.test/private: upstream failure",
    "Transport failed\nTraceback: fictional private path",
])
def test_transport_details_stay_out_of_main_failure_copy(reason: str) -> None:
    result = _render_failed_bootstrap(reason=reason, subject="")
    assert reason not in result["visibleText"]
    assert "Open Advanced message details" in result["panelText"]


@pytest.mark.parametrize("http_status,payload_status,load_result,recovered", [
    (200, "failed", {"ok": False}, True),
    (403, "failed", {"ok": False}, False),
    (500, "failed", {"ok": False}, False),
    (200, "failed", {"ok": True}, False),
    (200, "failed", None, False),
    (200, "error", {"ok": False}, False),
])
def test_only_structured_application_load_failures_are_recovered(http_status, payload_status, load_result, recovered) -> None:
    script = """
const { gmailFailedLoadPayload } = await import(__FAILURE__);
const error = __ERROR__;
console.log(JSON.stringify({ recovered: gmailFailedLoadPayload(error) === error.payload }));
""".replace("__ERROR__", json.dumps({"status": http_status, "payload": {
        "status": payload_status, "normalized_payload": {"load_result": load_result},
    }}))
    assert run_browser_esm_json_probe(script, {"__FAILURE__": "gmail_load_failure.js"})["recovered"] is recovered


@pytest.mark.parametrize("load_status", ["failed", "unavailable"])
def test_mounted_manual_load_failure_replaces_pending_state_and_retains_safe_diagnostics(load_status: str) -> None:
    script = r'''
const ids = new Map(); let unsafeWrites = 0;
function make(tag = "div", id = "") {
  const classes = new Set(), handlers = new Map(); let ownText = "";
  const node = { id, children: [], dataset: {}, value: "", style: {}, disabled: false,
    appendChild(c) { this.children.push(c); return c; },
    replaceChildren(...c) { this.children = c; ownText = ""; },
    setAttribute() {}, removeAttribute() {}, querySelectorAll() { return []; },
    addEventListener(t, f) { handlers.set(t, f); },
    async fire(t) { await handlers.get(t)?.({ preventDefault() {} }); },
    classList: { add(...cs) { cs.forEach(c => classes.add(c)); }, remove(...cs) { cs.forEach(c => classes.delete(c)); },
      toggle(c, on) { on ? classes.add(c) : classes.delete(c); }, contains(c) { return classes.has(c); } },
  };
  Object.defineProperty(node, "textContent", { get() { return ownText + node.children.map(c => c.textContent).join(""); },
    set(v) { ownText = String(v ?? ""); node.children = []; } });
  Object.defineProperty(node, "innerHTML", { set() { unsafeWrites++; throw new Error("Unsafe HTML"); } });
  if (id) ids.set(id, node); return node;
}
globalThis.document = { body: make("body"), hidden: false, createElement: t => make(t),
  getElementById: id => ids.get(id) || null, querySelectorAll: () => [], addEventListener() {} };
globalThis.window = { location: new URL("http://127.0.0.1:8888/?mode=shadow&workspace=fictional#gmail-intake"),
  addEventListener() {}, dispatchEvent() {}, setTimeout() { return 1; }, clearTimeout() {} };
globalThis.CustomEvent = class { constructor(type) { this.type = type; } };
for (const id of ["gmail-context-form", "gmail-load-message", "gmail-message-result", "gmail-status", "gmail-diagnostics",
  "gmail-hint", "gmail-details", "gmail-intake-details", "gmail-message-details-hint", "gmail-prepare-session",
  "gmail-message-id", "gmail-thread-id", "gmail-subject", "gmail-account-email"]) make("div", id);
const { appState } = await import(__STATE__);
appState.runtimeMode = "shadow"; appState.workspaceId = "fictional"; appState.activeView = "gmail-intake";
const gmail = await import(__GMAIL__);
gmail.initializeGmailUi({});
gmail.renderGmailBootstrap({ normalized_payload: { gmail: { defaults: { message_context: { message_id: "fictional-message" } } } } });
const before = ids.get("gmail-message-result").textContent;
ids.get("gmail-message-id").value = "fictional-message";
const rawReason = 'GET https://example.test/private: oauth2: "invalid_grant" "Token has been expired or revoked." <img src=x onerror=alert(1)>';
const payload = { status: __LOAD_STATUS__, normalized_payload: { load_result: {
  ok: false, classification: __LOAD_STATUS__, status_message: rawReason, message: null,
  intake_context: { message_id: "fictional-message", subject: "" },
}, message: null, review_event_id: 2 }, capability_flags: { gmail: { status: "ready" } } };
let calls = 0;
globalThis.fetch = async (url) => {
  if (url !== "/api/gmail/load-message") throw new Error("Unexpected request");
  calls++;
  return { ok: true, status: 200, text: async () => JSON.stringify(payload) };
};
await ids.get("gmail-context-form").fire("submit");
const after = { card: ids.get("gmail-message-result").textContent, panel: ids.get("gmail-status").textContent,
  hint: ids.get("gmail-hint").textContent, diagnostics: ids.get("gmail-diagnostics").textContent,
  diagnosticsOpen: ids.get("gmail-details").open, prepareDisabled: ids.get("gmail-prepare-session").disabled,
  drawerOpen: document.body.dataset.gmailReviewDrawer };
console.log(JSON.stringify({ before, after, rawReason, calls, unsafeWrites }));
'''.replace("__LOAD_STATUS__", json.dumps(load_status))
    result = run_browser_esm_json_probe(script, {"__STATE__": "state.js", "__GMAIL__": "gmail.js"})
    assert "Gmail message found." in result["before"]
    after = result["after"]
    assert "Gmail message needs attention." in after["card"]
    assert "Message details unavailable" in after["card"]
    assert "Reconnect your Gmail account" in after["panel"]
    assert after["hint"] == after["panel"]
    for stale in ("Gmail message found.", "Subject unavailable", "Ready soon", result["rawReason"]):
        assert stale not in after["card"] + after["panel"] + after["hint"]
    assert json.loads(after["diagnostics"])["normalized_payload"]["load_result"]["status_message"] == result["rawReason"]
    assert after["diagnosticsOpen"] is True
    assert after["prepareDisabled"] is True
    assert after["drawerOpen"] != "open"
    assert result["calls"] == 1
    assert result["unsafeWrites"] == 0
