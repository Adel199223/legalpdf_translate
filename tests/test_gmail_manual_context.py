from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from legalpdf_translate.gmail_browser_service import GmailBrowserSessionManager
from legalpdf_translate.gmail_intake import InboundMailContext

from .browser_esm_probe import run_browser_esm_json_probe
from .test_gmail_browser_service import _load_result


def test_manual_gmail_form_rebinds_source_and_subject_across_exact_messages() -> None:
    results = run_browser_esm_json_probe(r"""
const elements = new Map();
function element(id, value = "") {
  const classes = new Set();
  const node = {
    id, value, dataset: {}, textContent: id, disabled: false, handlers: {},
    classList: {
      toggle(name, on) { on ? classes.add(name) : classes.delete(name); },
      contains(name) { return classes.has(name); },
    },
    addEventListener(type, callback) { this.handlers[type] = callback; },
    setAttribute() {}, removeAttribute() {},
  };
  elements.set(id, node);
  return node;
}
const form = element("gmail-context-form");
const back = element("gmail-return-to-source");
for (const id of ["gmail-message-id", "gmail-thread-id", "gmail-subject", "gmail-account-email", "gmail-output-dir", "gmail-target-lang"]) {
  element(id);
}
element("gmail-load-message");
globalThis.document = {
  body: { dataset: {} },
  getElementById(id) { return elements.get(id) || null; },
  querySelectorAll() { return []; },
  addEventListener() {},
};
globalThis.window = {
  location: new URL("http://127.0.0.1:8890/?mode=shadow&workspace=fictional#gmail-intake"),
  addEventListener() {}, dispatchEvent() {},
  setTimeout() { return 1; }, clearTimeout() {},
};
globalThis.CustomEvent = class { constructor(type, options) { this.type = type; this.detail = options?.detail; } };
const gmail = await import(__GMAIL_MODULE_URL__);
const { appState } = await import(__STATE_MODULE_URL__);
appState.runtimeMode = "shadow";
appState.workspaceId = "fictional";
appState.activeView = "gmail-intake";
const requests = [];
const staleUrl = "https://mail.google.com/mail/u/0/#inbox/FMfictionalPrevious";
globalThis.fetch = async (path, options) => {
  if (path !== "/api/gmail/load-message") throw new Error(`Unexpected request: ${path}`);
  const request = JSON.parse(options.body);
  requests.push(request);
  const context = request.message_context;
  const subject = `Fetched ${context.message_id}`;
  const unavailable = context.message_id === "unavailable";
  const result = {
    status: unavailable ? "unavailable" : "ok",
    normalized_payload: {
      review_event_id: requests.length, message_signature: `signature-${context.message_id}`,
      load_result: {
        ok: !unavailable,
        intake_context: { ...context, subject },
        message: {
          ...context, subject,
          attachments: context.message_id === "second" ? [{ attachment_id: "a" }, { attachment_id: "b" }] : [],
        },
      },
    },
  };
  return { ok: true, status: 200, text: async () => JSON.stringify(result) };
};
gmail.initializeGmailUi({});
gmail.renderGmailBootstrap({ normalized_payload: { gmail: {
  defaults: { message_context: {} },
  click_diagnostics: { source_gmail_url: staleUrl },
} } });
function setFields(messageId, threadId) {
  elements.get("gmail-message-id").value = messageId;
  elements.get("gmail-thread-id").value = threadId;
  elements.get("gmail-account-email").value = "reader@example.test";
}
function backState() { return { title: back.title, disabled: back.disabled, hidden: back.classList.contains("hidden") }; }
async function submit() { await form.handlers.submit({ preventDefault() {} }); }
setFields("first", "first-thread");
await submit();
const first = { back: backState(), subject: elements.get("gmail-subject").value };
setFields("second", "second-thread");
await submit();
const second = { back: backState(), subject: elements.get("gmail-subject").value };
const extensionContext = {
  message_id: "second", thread_id: "second-thread", subject: "Fetched second",
  account_email: "reader@example.test", handoff_session_id: "fictional-handoff",
  source_gmail_url: "https://mail.google.com/mail/u/0/#inbox/FMfictionalSecond",
};
gmail.renderGmailBootstrap({ normalized_payload: { gmail: {
  defaults: { message_context: extensionContext },
  current_handoff_context: extensionContext,
  click_diagnostics: { source_gmail_url: staleUrl },
} } });
await submit();
const sameExtensionMessage = backState();
setFields("third", "third-thread");
await submit();
const changedExtensionMessage = backState();
setFields("unavailable", "unavailable-thread");
await submit();
const unavailableMessage = backState();
console.log(JSON.stringify({ requests, first, second, sameExtensionMessage, changedExtensionMessage, unavailableMessage }));
""", {"__GMAIL_MODULE_URL__": "gmail.js", "__STATE_MODULE_URL__": "state.js"}, timeout_seconds=30)

    hidden = {"title": "", "disabled": True, "hidden": True}
    assert results["first"] == {"back": hidden, "subject": "Fetched first"}
    assert results["second"] == {"back": hidden, "subject": "Fetched second"}
    assert [item["message_context"]["message_id"] for item in results["requests"]] == ["first", "second", "second", "third", "unavailable"]
    assert [item["message_context"]["source_gmail_url"] for item in results["requests"]] == [
        "", "", "https://mail.google.com/mail/u/0/#inbox/FMfictionalSecond", "", "",
    ]
    assert results["requests"][1]["message_context"]["subject"] == ""
    assert results["changedExtensionMessage"] == hidden
    assert results["unavailableMessage"] == hidden
    assert results["sameExtensionMessage"] == {
        "title": "https://mail.google.com/mail/u/0/#inbox/FMfictionalSecond", "disabled": False, "hidden": False,
    }


def test_current_gmail_context_without_source_url_blocks_stale_fallbacks() -> None:
    result = run_browser_esm_json_probe(r"""
const handoff = await import(__HANDOFF_MODULE_URL__);
const current = { message_id: "new-message", thread_id: "new-thread", subject: "Fetched subject", source_gmail_url: "" };
const stale = { message_id: "old-message", source_gmail_url: "https://mail.google.test/old" };
console.log(JSON.stringify({
  source: handoff.deriveGmailSourceUrl({
    currentHandoffContext: current, defaults: { message_context: stale },
    pendingIntakeContext: stale, clickDiagnostics: stale,
  }),
  defaults: handoff.deriveGmailBootstrapMessageContext({ bootstrap: {
    current_handoff_context: current, defaults: { message_context: stale },
  } }),
}));
""", {"__HANDOFF_MODULE_URL__": "gmail_handoff_state.js"})
    assert result["source"] == ""
    assert result["defaults"]["message_id"] == "new-message"


@pytest.mark.parametrize("changed_field", ["message_id", "thread_id", "account_email"])
def test_manual_gmail_payload_drops_inherited_source_on_identity_change(changed_field: str) -> None:
    script = r"""
const { buildGmailLoadMessageRequestPayload } = await import(__PAYLOAD_MODULE_URL__);
const currentMessageContext = {
  message_id: "fictional-message", thread_id: "fictional-thread", subject: "Previous subject",
  account_email: "reader@example.test", source_gmail_url: "https://mail.google.test/previous",
};
const changed = { ...currentMessageContext, [__CHANGED_FIELD__]: "different" };
const result = buildGmailLoadMessageRequestPayload({
  messageId: changed.message_id, threadId: changed.thread_id, subject: changed.subject,
  accountEmail: changed.account_email, sourceGmailUrl: currentMessageContext.source_gmail_url,
  currentMessageContext,
});
console.log(JSON.stringify(result));
""".replace("__CHANGED_FIELD__", repr(changed_field))
    result = run_browser_esm_json_probe(script, {"__PAYLOAD_MODULE_URL__": "gmail_request_payloads.js"})
    assert result["message_context"]["source_gmail_url"] == ""
    assert result["message_context"]["subject"] == ""


def test_manual_gmail_manager_uses_fetched_metadata_and_new_context(tmp_path: Path, monkeypatch) -> None:
    import legalpdf_translate.gmail_browser_service as gmail_service

    monkeypatch.setattr(gmail_service, "assess_gmail_draft_prereqs", lambda **_: SimpleNamespace(
        ready=False, message="offline", gog_path=None, account_email="", accounts=(),
    ))
    monkeypatch.setattr(gmail_service, "build_gmail_browser_capability_flags", lambda **_: {})
    loaded_contexts = []

    def offline_fetch(**kwargs):
        context = kwargs["intake_context"]
        loaded_contexts.append(context)
        result = _load_result(
            message_id=context.message_id, thread_id=context.thread_id, subject=f"Fetched {context.message_id}",
            account_email="reader@example.test", attachment_ids=("first", "second"),
        )
        result.intake_context = context
        return result

    monkeypatch.setattr(gmail_service, "load_gmail_message_from_intake", offline_fetch)
    manager = GmailBrowserSessionManager()
    first_context = InboundMailContext(
        message_id="first-message", thread_id="first-thread", subject="Old first subject",
        account_email="reader@example.test", handoff_session_id="fictional-handoff",
        source_gmail_url="https://mail.google.test/first",
    )
    manager.accept_bridge_intake(runtime_mode="shadow", workspace_id="fictional", settings_path=tmp_path / "settings.json", context=first_context)
    reloaded = manager.load_message(runtime_mode="shadow", workspace_id="fictional", settings_path=tmp_path / "settings.json", context_payload={
        "message_id": "first-message", "thread_id": "first-thread", "subject": "Old first subject",
        "account_email": "reader@example.test", "source_gmail_url": "https://mail.google.test/first",
    })
    assert reloaded["normalized_payload"]["load_result"]["intake_context"]["source_gmail_url"] == "https://mail.google.test/first"
    changed = manager.load_message(runtime_mode="shadow", workspace_id="fictional", settings_path=tmp_path / "settings.json", context_payload={
        "message_id": "second-message", "thread_id": "second-thread", "subject": "Old first subject",
        "account_email": "reader@example.test", "source_gmail_url": "",
    })
    payload = changed["normalized_payload"]["load_result"]
    assert payload["intake_context"]["subject"] == payload["message"]["subject"] == "Fetched second-message"
    assert payload["intake_context"]["source_gmail_url"] == ""
    assert len(payload["message"]["attachments"]) == 2
    bootstrap = manager.build_bootstrap(runtime_mode="shadow", workspace_id="fictional", settings_path=tmp_path / "settings.json", outputs_dir=tmp_path)["normalized_payload"]
    assert bootstrap["current_handoff_context"] == bootstrap["defaults"]["message_context"] == payload["intake_context"]
    assert bootstrap["handoff_session_id"] == ""
    assert bootstrap["pending_intake_context"] == {}
    assert len(loaded_contexts) == 3


@pytest.mark.parametrize("incoming_account,fetched_account,current_account,preserve", [
    ("reader-a@example.test", "reader-b@example.test", "reader-a@example.test", False),
    ("reader-a@example.test", "reader-b@example.test", None, False),
    ("reader-a@example.test", "reader-a@example.test", "reader-a@example.test", True),
    (" Reader-A@Example.Test ", "reader-a@example.test", "READER-A@example.test", True),
    (None, "reader-a@example.test", None, False),
])
def test_fetched_identity_drift_cannot_relabel_source_provenance(
    incoming_account, fetched_account, current_account, preserve,
) -> None:
    manager = GmailBrowserSessionManager()
    context = InboundMailContext(
        message_id="fictional-message", thread_id="fictional-thread", subject="Incoming subject",
        account_email=incoming_account, source_gmail_url="https://mail.google.test/account-a-source",
        handoff_session_id="fictional-handoff-a",
    )
    result = _load_result(message_id=context.message_id, thread_id=context.thread_id,
        subject="Fetched subject", account_email=fetched_account, attachment_ids=("attachment",))
    result.intake_context = context
    if current_account is not None:
        manager._set_pending_intake(runtime_mode="shadow", workspace_id="fictional",
            context=replace(context, account_email=current_account))
    manager._store_loaded_result(runtime_mode="shadow", workspace_id="fictional", result=result)
    workspace = manager._workspace(runtime_mode="shadow", workspace_id="fictional")
    assert result.intake_context.account_email == fetched_account
    assert result.intake_context.subject == "Fetched subject"
    assert result.intake_context.source_gmail_url == (context.source_gmail_url if preserve else None)
    assert result.intake_context.handoff_session_id == (context.handoff_session_id if preserve else None)
    assert workspace.current_handoff_context["account_email"] == fetched_account
    assert workspace.current_handoff_context["source_gmail_url"] == (context.source_gmail_url if preserve else "")
    assert workspace.current_handoff_context["handoff_session_id"] == (context.handoff_session_id if preserve else "")


def test_current_handoff_account_drift_falls_back_to_verified_incoming_context() -> None:
    manager = GmailBrowserSessionManager()
    context = InboundMailContext(
        message_id="fictional-message", thread_id="fictional-thread", subject="Incoming subject",
        account_email="reader-a@example.test", source_gmail_url="https://mail.google.test/source-a",
        handoff_session_id="fictional-handoff-a",
    )
    result = _load_result(message_id=context.message_id, thread_id=context.thread_id,
        subject="Fetched subject", account_email=context.account_email, attachment_ids=("attachment",))
    result.intake_context = context
    manager._set_pending_intake(runtime_mode="shadow", workspace_id="fictional", context=replace(context,
        account_email="reader-b@example.test", source_gmail_url="https://mail.google.test/source-b",
        handoff_session_id="fictional-handoff-b"))
    manager._store_loaded_result(runtime_mode="shadow", workspace_id="fictional", result=result)
    stored = manager._workspace(runtime_mode="shadow", workspace_id="fictional").current_handoff_context
    assert stored["account_email"] == context.account_email
    assert stored["source_gmail_url"] == context.source_gmail_url
    assert stored["handoff_session_id"] == context.handoff_session_id


@pytest.mark.parametrize("changed_field", ["message_id", "thread_id"])
def test_fetched_message_identity_drift_clears_incoming_provenance(changed_field) -> None:
    manager = GmailBrowserSessionManager()
    context = InboundMailContext(
        message_id="fictional-message", thread_id="fictional-thread", subject="Incoming subject",
        account_email="reader@example.test", source_gmail_url="https://mail.google.test/source",
        handoff_session_id="fictional-handoff",
    )
    identity = {"message_id": context.message_id, "thread_id": context.thread_id, changed_field: "different"}
    result = _load_result(**identity, subject="Fetched subject", account_email=context.account_email,
        attachment_ids=("attachment",))
    result.intake_context = context
    manager._set_pending_intake(runtime_mode="shadow", workspace_id="fictional", context=context)
    manager._store_loaded_result(runtime_mode="shadow", workspace_id="fictional", result=result)
    assert getattr(result.intake_context, changed_field) == "different"
    assert result.intake_context.source_gmail_url is None
    assert result.intake_context.handoff_session_id is None
    stored = manager._workspace(runtime_mode="shadow", workspace_id="fictional").current_handoff_context
    assert stored["source_gmail_url"] == stored["handoff_session_id"] == ""
