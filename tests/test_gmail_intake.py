from __future__ import annotations

import http.client
import json
import shutil
import socket
import subprocess
import time
from pathlib import Path

import pytest

from legalpdf_translate.gmail_intake import InboundMailContext, LocalGmailIntakeBridge


def _reserve_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _request(
    *,
    method: str,
    port: int,
    token: str,
    body: object | None = None,
    content_type: str = "application/json",
) -> tuple[int, dict[str, object]]:
    encoded_body = b"" if body is None else json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": content_type,
    }
    if encoded_body:
        headers["Content-Length"] = str(len(encoded_body))

    deadline = time.time() + 1.0
    while True:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2.0)
        try:
            connection.request(method, "/gmail-intake", body=encoded_body or None, headers=headers)
            response = connection.getresponse()
            payload = json.loads(response.read().decode("utf-8"))
            return response.status, payload
        except ConnectionRefusedError:
            if time.time() >= deadline:
                raise
            time.sleep(0.02)
        finally:
            connection.close()


def _run_background_logic_probe() -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for Gmail extension background coverage.")

    background_path = (
        Path(__file__).resolve().parents[1]
        / "extensions"
        / "gmail_intake"
        / "background.js"
    )

    script = f"""
const fs = await import("node:fs");
const vm = await import("node:vm");

const backgroundPath = {json.dumps(str(background_path))};
const backgroundSource = fs.readFileSync(backgroundPath, "utf8");

function loadBackground({{
  fetchImpl,
  nativeImpl = async () => ({{}}),
  storageGetImpl = async () => ({{}}),
  sessionStorageGetImpl = async () => ({{}}),
  queryImpl = async () => [],
  executeScriptImpl = async () => undefined,
  sendMessageImpl = async () => ({{ ok: true }}),
  reloadImpl = async () => undefined,
}}) {{
  const tabOps = [];
  const sentMessages = [];
  const chrome = {{
    action: {{
      onClicked: {{
        addListener(_handler) {{
          // The probe calls test hooks directly.
        }},
      }},
    }},
    tabs: {{
      sendMessage: async (tabId, payload) => {{
        sentMessages.push({{ tabId, payload }});
        return await sendMessageImpl(tabId, payload);
      }},
      query: async (query) => {{
        tabOps.push({{ type: "query", query }});
        return await queryImpl(query);
      }},
      update: async (...args) => {{
        tabOps.push({{ type: "update", args }});
        return {{}};
      }},
      reload: async (...args) => {{
        tabOps.push({{ type: "reload", args }});
        await reloadImpl(...args);
        return {{}};
      }},
      create: async (args) => {{
        tabOps.push({{ type: "create", args }});
        return {{ id: 91, windowId: 7 }};
      }},
    }},
    windows: {{
      update: async (...args) => {{
        tabOps.push({{ type: "windowUpdate", args }});
        return {{}};
      }},
    }},
    runtime: {{
      sendNativeMessage: nativeImpl,
    }},
    scripting: {{
      executeScript: async (args) => {{
        tabOps.push({{ type: "executeScript", args }});
        return await executeScriptImpl(args);
      }},
    }},
    storage: {{
      local: {{
        get: storageGetImpl,
        set: async () => undefined,
      }},
      session: {{
        get: sessionStorageGetImpl,
        set: async () => undefined,
      }},
    }},
  }};

  const context = {{
    console,
    URL,
    fetch: fetchImpl,
    chrome,
    setTimeout,
    clearTimeout,
    Date,
  }};
  context.globalThis = context;
  context.__LEGALPDF_TEST__ = true;
  vm.createContext(context);
  new vm.Script(backgroundSource, {{ filename: backgroundPath }}).runInContext(context);
  return {{
    hooks: context.__legalPdfGmailIntakeBackgroundTestHooks,
    tabOps,
    sentMessages,
  }};
}}

const browserUrl = "http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake";
const shellAssetVersion = "asset-20260330";
const launchSessionSchemaVersion = 3;
const gmailContext = {{
  message_id: "msg-1",
  thread_id: "thread-1",
  subject: "Subject",
}};
const config = {{
  bridgePort: 8765,
  bridgeToken: "shared-token",
}};
const nativeResponse = {{
  ui_owner: "browser_app",
  browser_url: browserUrl,
}};

function workspaceReadyFetch() {{
  return async (url, options = {{}}) => {{
    const targetUrl = String(url || "");
    const method = String(options.method || "GET").toUpperCase();
    if (targetUrl === "http://127.0.0.1:8765/gmail-intake" && method === "POST") {{
      return {{
        ok: true,
        status: 200,
        json: async () => ({{ message: "Gmail intake accepted." }}),
      }};
    }}
    if (targetUrl.includes("/api/bootstrap/shell")) {{
      return {{
        ok: true,
        status: 200,
        json: async () => ({{
          normalized_payload: {{
            shell: {{
              ready: true,
              runtime_mode: "live",
              workspace_id: "gmail-intake",
              asset_version: shellAssetVersion,
              extension_launch_session_schema_version: launchSessionSchemaVersion,
            }},
            gmail: {{
              pending_status: "",
              pending_review_open: false,
            }},
          }},
          diagnostics: {{
            gmail_bridge_sync: {{}},
          }},
          capability_flags: {{
            gmail_bridge: {{
              current_mode: {{
                prepare_response: {{}},
              }},
            }},
          }},
        }}),
      }};
    }}
    if (targetUrl.includes("/api/gmail/bootstrap")) {{
      return {{
        ok: true,
        status: 200,
        json: async () => ({{
          normalized_payload: {{
            pending_status: "",
            pending_review_open: false,
            load_result: {{
              ok: true,
              intake_context: {{
                message_id: "msg-1",
                thread_id: "thread-1",
              }},
            }},
          }},
          diagnostics: {{
            gmail_bridge_sync: {{}},
          }},
          capability_flags: {{
            gmail_bridge: {{
              current_mode: {{
                prepare_response: {{}},
              }},
            }},
          }},
        }}),
      }};
    }}
    throw new Error(`unexpected fetch ${{targetUrl}}`);
  }};
}}

function workspacePendingFetch() {{
  return async (url, options = {{}}) => {{
    const targetUrl = String(url || "");
    const method = String(options.method || "GET").toUpperCase();
    if (targetUrl === "http://127.0.0.1:8765/gmail-intake" && method === "POST") {{
      return {{
        ok: true,
        status: 200,
        json: async () => ({{ message: "Gmail intake accepted." }}),
      }};
    }}
    if (targetUrl.includes("/api/bootstrap/shell")) {{
      return {{
        ok: true,
        status: 200,
        json: async () => ({{
          normalized_payload: {{
            shell: {{
              ready: true,
              runtime_mode: "live",
              workspace_id: "gmail-intake",
              asset_version: shellAssetVersion,
              extension_launch_session_schema_version: launchSessionSchemaVersion,
            }},
            gmail: {{
              pending_status: "warming",
              pending_review_open: true,
              pending_intake_context: {{
                message_id: "msg-1",
                thread_id: "thread-1",
              }},
            }},
          }},
          diagnostics: {{
            gmail_bridge_sync: {{}},
          }},
          capability_flags: {{
            gmail_bridge: {{
              current_mode: {{
                prepare_response: {{}},
              }},
            }},
          }},
        }}),
      }};
    }}
    if (targetUrl.includes("/api/gmail/bootstrap")) {{
      return {{
        ok: true,
        status: 200,
        json: async () => ({{
          normalized_payload: {{
            pending_status: "warming",
            pending_review_open: true,
            pending_intake_context: {{
              message_id: "msg-1",
              thread_id: "thread-1",
            }},
            load_result: {{}},
          }},
          diagnostics: {{
            gmail_bridge_sync: {{}},
          }},
          capability_flags: {{
            gmail_bridge: {{
              current_mode: {{
                prepare_response: {{}},
              }},
            }},
          }},
        }}),
      }};
    }}
    throw new Error(`unexpected fetch ${{targetUrl}}`);
  }};
}}

function clientReadyPayload(
  status,
  message = "",
  assetVersion = shellAssetVersion,
  launchSessionId = "",
  handoffSessionId = "",
  schemaVersion = launchSessionSchemaVersion,
) {{
  return {{
    marker: {{
      status,
      workspaceId: "gmail-intake",
      runtimeMode: "live",
      activeView: "gmail-intake",
      gmailHandoffState: status === "ready" ? "loaded" : "warming",
      buildSha: "5c9842e",
      assetVersion,
      launchSessionId,
      handoffSessionId,
      launchSessionSchemaVersion: schemaVersion,
      bootstrappedAt: status === "ready" ? "2026-03-30T12:00:00Z" : null,
      message,
    }},
    dataset: {{
      clientReady: status,
      clientWorkspace: "gmail-intake",
      clientRuntimeMode: "live",
      clientActiveView: "gmail-intake",
      clientBuildSha: "5c9842e",
      clientAssetVersion: assetVersion,
      clientLaunchSession: launchSessionId,
      clientHandoffSession: handoffSessionId,
      clientLaunchSessionSchemaVersion: String(schemaVersion),
    }},
    href: browserUrl,
  }};
}}

function executeScriptSequence(states) {{
  let index = 0;
  return async () => [{{
    result: states[Math.min(index++, states.length - 1)],
  }}];
}}

const transport = loadBackground({{
  fetchImpl: async () => {{
  throw new Error("offline");
  }},
}});
await transport.hooks.postContext(11, gmailContext, config, nativeResponse, "", false, browserUrl, false);

const rejected = loadBackground({{
  fetchImpl: async () => ({{
  ok: false,
  status: 401,
  json: async () => ({{ message: "Rejected by bridge." }}),
  }}),
}});
await rejected.hooks.postContext(12, gmailContext, config, nativeResponse, "", false, browserUrl, false);

const lockRun = loadBackground({{
  fetchImpl: async () => ({{
  ok: true,
  status: 200,
  json: async () => ({{ message: "ok" }}),
  }}),
}});
const hooks = lockRun.hooks;
hooks.handoffInFlight.clear();
const originalDateNow = Date.now;
let now = 1000;
Date.now = () => now;
const first = hooks.claimHandoffLock(21, gmailContext);
now = 1000 + hooks.LAUNCH_READINESS_WAIT_MS + 1;
const afterLaunchBudget = hooks.claimHandoffLock(21, gmailContext);
now = 1000 + hooks.HANDOFF_LOCK_MAX_AGE_MS + 1;
const afterFullBudget = hooks.claimHandoffLock(21, gmailContext);
Date.now = originalDateNow;

const nativeUnavailableDeadBridge = loadBackground({{
  fetchImpl: async () => {{
    throw new Error("offline");
  }},
  nativeImpl: async () => {{
    throw new Error("native host missing");
  }},
  storageGetImpl: async () => ({{
    bridgePort: 8765,
    bridgeToken: "shared-token",
  }}),
}});
const nativeUnavailableDeadBridgeResult = await nativeUnavailableDeadBridge.hooks.resolveBridgeConfigForClick();

const nativeUnavailableLiveBridge = loadBackground({{
  fetchImpl: async () => ({{
    ok: false,
    status: 405,
    json: async () => ({{ message: "Use POST /gmail-intake." }}),
  }}),
  nativeImpl: async () => {{
    throw new Error("native host missing");
  }},
  storageGetImpl: async () => ({{
    bridgePort: 8765,
    bridgeToken: "shared-token",
  }}),
}});
const nativeUnavailableLiveBridgeResult = await nativeUnavailableLiveBridge.hooks.resolveBridgeConfigForClick();

const nativeLaunchInProgress = loadBackground({{
  fetchImpl: async () => {{
    throw new Error("offline");
  }},
  nativeImpl: async () => ({{
    ok: false,
    reason: "launch_in_progress",
    launch_in_progress: true,
    launch_lock_ttl_ms: 4200,
    launch_session_id: "launch-123",
    ui_owner: "browser_app",
    browser_url: browserUrl,
    browser_open_owned_by: "server_boot",
  }}),
}});
const nativeLaunchInProgressResult = await nativeLaunchInProgress.hooks.resolveBridgeConfigForClick();

const foreignLaunchNoCreate = loadBackground({{
  queryImpl: async () => [],
}});
await foreignLaunchNoCreate.hooks.rememberActiveBrowserLaunchSession(browserUrl, {{
  launchSessionId: "launch-foreign-1",
  owner: "server_boot",
  ttlMs: 4200,
}});
const foreignLaunchNoCreateResult = await foreignLaunchNoCreate.hooks.openOrFocusBrowserApp(browserUrl);
const extensionOwnedLaunchedWaitResult = foreignLaunchNoCreate.hooks.shouldWaitForLaunchedBrowserTab({{
  nativeResponse: {{
    ui_owner: "browser_app",
    launched: true,
    browser_url: browserUrl,
    browser_open_owned_by: "extension",
  }},
  browserUrl,
  launchSessionId: "launch-extension-1",
  browserOpenOwnedBy: "extension",
}});
const foreignOwnedLaunchedWaitResult = foreignLaunchNoCreate.hooks.shouldWaitForLaunchedBrowserTab({{
  nativeResponse: {{
    ui_owner: "browser_app",
    launched: true,
    browser_url: browserUrl,
    browser_open_owned_by: "server_boot",
  }},
  browserUrl,
  launchSessionId: "launch-foreign-1",
  browserOpenOwnedBy: "server_boot",
}});

const settleNoCreate = loadBackground({{
  fetchImpl: async () => ({{
    ok: true,
    status: 200,
    json: async () => ({{ message: "ok" }}),
  }}),
}});
const settleNoCreateResult = await settleNoCreate.hooks.settleBrowserAppHandoff(browserUrl, false, false);

const unrelatedLocalhostTab = {{
  id: 88,
  windowId: 16,
  url: "http://127.0.0.1:8877/?mode=live&workspace=new-job#new-job",
}};

const strictWorkspaceNoHijack = loadBackground({{
  queryImpl: async () => [unrelatedLocalhostTab],
}});
const strictWorkspaceNoHijackResult = await strictWorkspaceNoHijack.hooks.openOrFocusBrowserApp(browserUrl);

const readyTab = {{
  id: 77,
  windowId: 15,
  url: browserUrl,
}};

const staleExactWorkspaceTab = {{
  id: 93,
  windowId: 19,
  url: browserUrl,
}};

const staleQueriedExactTab = loadBackground({{
  queryImpl: async () => [staleExactWorkspaceTab],
  executeScriptImpl: executeScriptSequence([
    clientReadyPayload("ready", "", shellAssetVersion, "launch-old"),
  ]),
}});
await staleQueriedExactTab.hooks.rememberActiveBrowserLaunchSession(browserUrl, {{
  launchSessionId: "launch-new",
  owner: "extension",
  ttlMs: 4200,
}});
const staleQueriedExactTabResult = await staleQueriedExactTab.hooks.openOrFocusBrowserApp(browserUrl, {{
  launchSessionId: "launch-new",
  browserOpenOwnedBy: "extension",
}});

const stalePendingExactTab = loadBackground({{
  queryImpl: async () => [staleExactWorkspaceTab],
  executeScriptImpl: executeScriptSequence([
    clientReadyPayload("ready", "", shellAssetVersion, "launch-old"),
  ]),
}});
await stalePendingExactTab.hooks.rememberPendingBrowserSurface(browserUrl, staleExactWorkspaceTab, {{
  launchSessionId: "launch-old",
  browserOpenOwnedBy: "extension",
  resolutionStrategy: "exact_workspace_match",
  surfaceCandidateSource: "pending_surface",
  surfaceCandidateValid: true,
}});
await stalePendingExactTab.hooks.rememberActiveBrowserLaunchSession(browserUrl, {{
  launchSessionId: "launch-new",
  owner: "extension",
  ttlMs: 4200,
}});
const stalePendingExactTabResult = await stalePendingExactTab.hooks.openOrFocusBrowserApp(browserUrl, {{
  launchSessionId: "launch-new",
  browserOpenOwnedBy: "extension",
}});

const currentFreshPendingTab = loadBackground({{
  queryImpl: async () => [readyTab],
}});
await currentFreshPendingTab.hooks.rememberPendingBrowserSurface(browserUrl, readyTab, {{
  launchSessionId: "launch-current",
  browserOpenOwnedBy: "extension",
  resolutionStrategy: "created_exact_tab",
  surfaceCandidateSource: "fresh_exact_tab",
  surfaceCandidateValid: true,
  freshTabCreatedAfterInvalidation: true,
}});
await currentFreshPendingTab.hooks.rememberActiveBrowserLaunchSession(browserUrl, {{
  launchSessionId: "launch-current",
  owner: "extension",
  ttlMs: 4200,
}});
const currentFreshPendingTabResult = await currentFreshPendingTab.hooks.openOrFocusBrowserApp(browserUrl, {{
  launchSessionId: "launch-current",
  browserOpenOwnedBy: "extension",
}});

const hydratedImmediate = loadBackground({{
  fetchImpl: workspaceReadyFetch(),
  queryImpl: async () => [readyTab],
  executeScriptImpl: executeScriptSequence([
    clientReadyPayload("ready"),
  ]),
}});
const hydratedImmediateResult = await hydratedImmediate.hooks.postContext(
  13,
  gmailContext,
  config,
  nativeResponse,
  "",
  false,
  browserUrl,
  false,
);

let hydratedAfterReloadSawReload = false;
const hydratedAfterReload = loadBackground({{
  fetchImpl: workspaceReadyFetch(),
  queryImpl: async () => [readyTab],
  executeScriptImpl: async () => [{{
    result: clientReadyPayload(
      "ready",
      "",
      hydratedAfterReloadSawReload ? shellAssetVersion : "asset-stale-old",
    ),
  }}],
  reloadImpl: async () => {{
    hydratedAfterReloadSawReload = true;
  }},
}});
const hydratedAfterReloadResult = await hydratedAfterReload.hooks.postContext(
  14,
  gmailContext,
  config,
  nativeResponse,
  "",
  false,
  browserUrl,
  false,
);

const hydratedNever = loadBackground({{
  fetchImpl: workspaceReadyFetch(),
  queryImpl: async () => [readyTab],
  executeScriptImpl: executeScriptSequence([
    clientReadyPayload("warming"),
    clientReadyPayload("warming"),
    clientReadyPayload("warming"),
  ]),
}});
const hydratedNeverResult = await hydratedNever.hooks.postContext(
  15,
  gmailContext,
  config,
  nativeResponse,
  "",
  false,
  browserUrl,
  false,
);

let hydratedStaleNeverSawReload = false;
const hydratedStaleNever = loadBackground({{
  fetchImpl: workspaceReadyFetch(),
  queryImpl: async () => [readyTab],
  executeScriptImpl: async () => [{{
    result: clientReadyPayload(
      "ready",
      "",
      hydratedStaleNeverSawReload ? "asset-stale-after-reload" : "asset-stale-before-reload",
    ),
  }}],
  reloadImpl: async () => {{
    hydratedStaleNeverSawReload = true;
  }},
}});
const hydratedStaleNeverResult = await hydratedStaleNever.hooks.postContext(
  16,
  gmailContext,
  config,
  nativeResponse,
  "",
  false,
  browserUrl,
  false,
);

const pendingWithoutSurface = loadBackground({{
  fetchImpl: workspacePendingFetch(),
  queryImpl: async () => [unrelatedLocalhostTab],
  executeScriptImpl: executeScriptSequence([
    clientReadyPayload("warming"),
  ]),
}});
const pendingWithoutSurfaceResult = await pendingWithoutSurface.hooks.postContext(
  17,
  gmailContext,
  config,
  nativeResponse,
  "",
  false,
  browserUrl,
  false,
);

console.log(JSON.stringify({{
  transport: {{
    tabOps: transport.tabOps,
    sentMessages: transport.sentMessages,
  }},
  rejected: {{
    tabOps: rejected.tabOps,
    sentMessages: rejected.sentMessages,
  }},
  lock: {{
    launchReadinessMs: hooks.LAUNCH_READINESS_WAIT_MS,
    handoffLockMaxAgeMs: hooks.HANDOFF_LOCK_MAX_AGE_MS,
    first,
    afterLaunchBudget,
    afterFullBudget,
  }},
  nativeUnavailableDeadBridgeResult,
  nativeUnavailableLiveBridgeResult,
  nativeLaunchInProgressResult,
  foreignLaunchNoCreate: {{
    result: foreignLaunchNoCreateResult,
    tabOps: foreignLaunchNoCreate.tabOps,
  }},
  extensionOwnedLaunchedWaitResult,
  foreignOwnedLaunchedWaitResult,
  settleNoCreate: {{
    result: settleNoCreateResult,
    tabOps: settleNoCreate.tabOps,
  }},
  strictWorkspaceNoHijack: {{
    result: strictWorkspaceNoHijackResult,
    tabOps: strictWorkspaceNoHijack.tabOps,
  }},
  staleQueriedExactTab: {{
    result: staleQueriedExactTabResult,
    tabOps: staleQueriedExactTab.tabOps,
  }},
  stalePendingExactTab: {{
    result: stalePendingExactTabResult,
    tabOps: stalePendingExactTab.tabOps,
  }},
  currentFreshPendingTab: {{
    result: currentFreshPendingTabResult,
    tabOps: currentFreshPendingTab.tabOps,
  }},
  hydratedImmediate: {{
    result: hydratedImmediateResult,
    tabOps: hydratedImmediate.tabOps,
    sentMessages: hydratedImmediate.sentMessages,
  }},
  hydratedAfterReload: {{
    result: hydratedAfterReloadResult,
    tabOps: hydratedAfterReload.tabOps,
    sentMessages: hydratedAfterReload.sentMessages,
  }},
  hydratedNever: {{
    result: hydratedNeverResult,
    tabOps: hydratedNever.tabOps,
    sentMessages: hydratedNever.sentMessages,
  }},
  hydratedStaleNever: {{
    result: hydratedStaleNeverResult,
    tabOps: hydratedStaleNever.tabOps,
    sentMessages: hydratedStaleNever.sentMessages,
  }},
  pendingWithoutSurface: {{
    result: pendingWithoutSurfaceResult,
    tabOps: pendingWithoutSurface.tabOps,
    sentMessages: pendingWithoutSurface.sentMessages,
  }},
}}));
"""

    completed = subprocess.run(
        [node, "--input-type=module", "-"],
        input=script,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(completed.stdout)


def test_local_gmail_intake_bridge_accepts_valid_context() -> None:
    accepted: list[InboundMailContext] = []
    bridge = LocalGmailIntakeBridge(
        port=_reserve_port(),
        token="shared-token",
        on_context=accepted.append,
    )
    bridge.start()
    try:
        status, payload = _request(
            method="POST",
            port=bridge.port,
            token="shared-token",
            body={
                "message_id": "18f43f6f2f8c0a11",
                "thread_id": "18f43f6f2f8c0a10",
                "subject": "Urgent filing",
                "account_email": "lawyer@example.com",
            },
        )
        assert bridge.url == f"http://127.0.0.1:{bridge.port}/gmail-intake"
        assert status == 200
        assert payload["status"] == "accepted"
        assert accepted == [
            InboundMailContext(
                message_id="18f43f6f2f8c0a11",
                thread_id="18f43f6f2f8c0a10",
                subject="Urgent filing",
                account_email="lawyer@example.com",
            )
        ]
    finally:
        bridge.stop()
    assert bridge.is_running is False


def test_local_gmail_intake_bridge_rejects_invalid_token() -> None:
    accepted: list[InboundMailContext] = []
    bridge = LocalGmailIntakeBridge(
        port=_reserve_port(),
        token="shared-token",
        on_context=accepted.append,
    )
    bridge.start()
    try:
        status, payload = _request(
            method="POST",
            port=bridge.port,
            token="wrong-token",
            body={
                "message_id": "msg-1",
                "thread_id": "thread-1",
                "subject": "",
            },
        )
        assert status == 401
        assert payload["code"] == "invalid_token"
        assert accepted == []
    finally:
        bridge.stop()


def test_local_gmail_intake_bridge_rejects_unknown_payload_fields() -> None:
    bridge = LocalGmailIntakeBridge(
        port=_reserve_port(),
        token="shared-token",
        on_context=lambda _context: None,
    )
    bridge.start()
    try:
        status, payload = _request(
            method="POST",
            port=bridge.port,
            token="shared-token",
            body={
                "message_id": "msg-1",
                "thread_id": "thread-1",
                "subject": "Subject",
                "extra": "not-allowed",
            },
        )
        assert status == 400
        assert payload["code"] == "invalid_payload"
        assert "Unknown keys" in str(payload["message"])
    finally:
        bridge.stop()


def test_local_gmail_intake_bridge_rejects_blank_message_identity() -> None:
    bridge = LocalGmailIntakeBridge(
        port=_reserve_port(),
        token="shared-token",
        on_context=lambda _context: None,
    )
    bridge.start()
    try:
        status, payload = _request(
            method="POST",
            port=bridge.port,
            token="shared-token",
            body={
                "message_id": "   ",
                "thread_id": "thread-1",
                "subject": "Subject",
            },
        )
        assert status == 400
        assert payload["code"] == "invalid_payload"
        assert payload["message"] == "message_id must be non-empty."
    finally:
        bridge.stop()


def test_local_gmail_intake_bridge_requires_localhost_binding() -> None:
    bridge = LocalGmailIntakeBridge(
        port=_reserve_port(),
        token="shared-token",
        on_context=lambda _context: None,
        host="0.0.0.0",
    )
    with pytest.raises(ValueError, match="127.0.0.1"):
        bridge.start()


def test_gmail_extension_manifest_is_gmail_only_and_localhost_only() -> None:
    extension_dir = Path(__file__).resolve().parents[1] / "extensions" / "gmail_intake"
    manifest = json.loads((extension_dir / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["manifest_version"] == 3
    assert manifest["permissions"] == ["activeTab", "nativeMessaging", "scripting", "storage", "tabs"]
    assert manifest["host_permissions"] == ["http://127.0.0.1/*"]
    assert manifest["key"].startswith("MIIBIjAN")
    assert manifest["options_page"] == "options.html"
    assert manifest["background"]["service_worker"] == "background.js"
    assert manifest["content_scripts"] == [
        {
            "matches": ["https://mail.google.com/*"],
            "js": ["content.js"],
            "run_at": "document_idle",
        }
    ]


def test_gmail_extension_scripts_keep_stage_one_contract_markers() -> None:
    extension_dir = Path(__file__).resolve().parents[1] / "extensions" / "gmail_intake"
    background_js = (extension_dir / "background.js").read_text(encoding="utf-8")
    content_js = (extension_dir / "content.js").read_text(encoding="utf-8")

    assert "Authorization" in background_js
    assert "http://127.0.0.1:" in background_js
    assert "/gmail-intake" in background_js
    assert "chrome.scripting.executeScript" in background_js
    assert 'type: "gmail-intake-ping"' in background_js
    assert 'files: ["content.js"]' in background_js
    assert "showFallbackBanner" in background_js
    assert "chrome.runtime.sendNativeMessage" in background_js
    assert "LEGALPDF_BROWSER_CLIENT_READY" in background_js
    assert "/api/bootstrap/shell/ready" in background_js
    assert "chrome.storage.session" in background_js
    assert "pendingBrowserSurfaces" in background_js
    assert "client_shell_not_hydrated" not in background_js
    assert "stale_browser_assets" not in background_js
    assert "chrome.tabs.reload" in background_js
    assert "com.legalpdf.gmail_focus" in background_js
    assert 'action: "prepare_gmail_intake"' in background_js
    assert "chrome.storage.local.get" in background_js
    assert "includeToken" in background_js
    assert "requestFocus" in background_js
    assert "browser_server_ready" in background_js
    assert "launch_timeout" in background_js
    assert "auto-launch is not available from this checkout" in background_js
    assert "Gmail bridge is not configured in LegalPDF Translate." in background_js
    assert "LegalPDF Translate native host is unavailable. Reload the extension or open the options page." in background_js
    assert "extension cannot open the app automatically right now" in background_js
    assert "candidates.find((tab) => Number.isInteger(tab.id))" in background_js
    assert "ensureBrowserTabVisible" in background_js
    assert "confirmBrowserWorkspaceSurfaceBeforeBridgePost" in background_js
    assert "handoff_session_id: context.handoff_session_id ?? undefined" in background_js
    assert "Bridge token is missing in extension options." not in background_js
    assert background_js.index("chrome.runtime.sendNativeMessage") < background_js.index("await postContext")
    assert "[data-message-id][data-legacy-message-id]" in content_js
    assert "data-legacy-thread-id" in content_js
    assert "h2.hP" in content_js
    assert "__legalPdfGmailIntakeLoaded" in content_js
    assert 'message.type === "gmail-intake-ping"' in content_js


def test_gmail_extension_background_preserves_failure_contract_and_lock_budget() -> None:
    results = _run_background_logic_probe()

    assert results["transport"]["tabOps"] == []
    assert results["transport"]["sentMessages"] == [
        {
            "tabId": 11,
            "payload": {
                "type": "gmail-intake-status",
                "kind": "error",
                "message": "LegalPDF Translate is not listening on http://127.0.0.1:8765/gmail-intake.",
            },
        }
    ]

    assert results["rejected"]["tabOps"] == []
    assert results["rejected"]["sentMessages"] == [
        {
            "tabId": 12,
            "payload": {
                "type": "gmail-intake-status",
                "kind": "error",
                "message": "Rejected by bridge.",
            },
        }
    ]

    assert results["lock"]["handoffLockMaxAgeMs"] > results["lock"]["launchReadinessMs"]
    assert results["lock"]["first"]["ok"] is True
    assert results["lock"]["afterLaunchBudget"] == {
        "ok": False,
        "key": "21:msg-1",
        "staleRecovered": False,
    }
    assert results["lock"]["afterFullBudget"]["ok"] is True
    assert results["lock"]["afterFullBudget"]["key"] == "21:msg-1"
    assert results["lock"]["afterFullBudget"]["staleRecovered"] is True

    assert results["nativeUnavailableDeadBridgeResult"] == {
        "ok": False,
        "degradedMode": True,
        "nativeResponse": None,
        "messageKind": "error",
        "message": (
            "LegalPDF Translate native host is unavailable, so the extension cannot open the app "
            "automatically right now. Open LegalPDF Translate once to repair the focus helper, "
            "then click the extension again."
        ),
    }
    assert results["nativeUnavailableLiveBridgeResult"] == {
        "ok": True,
        "degradedMode": True,
        "nativeResponse": None,
        "config": {
            "bridgePort": 8765,
            "bridgeToken": "shared-token",
        },
    }
    assert results["nativeLaunchInProgressResult"] == {
        "ok": False,
        "degradedMode": False,
        "nativeResponse": {
            "ok": False,
            "reason": "launch_in_progress",
            "launch_in_progress": True,
            "launch_lock_ttl_ms": 4200,
            "launch_session_id": "launch-123",
            "ui_owner": "browser_app",
            "browser_url": "http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake",
            "browser_open_owned_by": "server_boot",
        },
        "launchInProgress": True,
        "messageKind": "info",
        "message": (
            "LegalPDF Translate is already starting the browser app for this Gmail handoff. "
            "Please wait up to 5s before clicking again; it will reuse the same launch instead of opening another window."
        ),
    }
    assert results["foreignLaunchNoCreate"]["result"] is False
    assert results["foreignLaunchNoCreate"]["tabOps"] == [
        {
            "type": "query",
            "query": {
                "url": "http://127.0.0.1:8877/*",
            },
        }
    ]
    assert results["extensionOwnedLaunchedWaitResult"] is False
    assert results["foreignOwnedLaunchedWaitResult"] is True
    assert results["settleNoCreate"]["result"] is False
    assert results["settleNoCreate"]["tabOps"] == [
        {
            "type": "query",
            "query": {
                "url": "http://127.0.0.1:8877/*",
            },
        }
    ]
    assert results["strictWorkspaceNoHijack"]["result"] is True
    assert results["strictWorkspaceNoHijack"]["tabOps"] == [
        {
            "type": "query",
            "query": {
                "url": "http://127.0.0.1:8877/*",
            },
        },
        {
            "type": "create",
            "args": {
                "url": "http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake",
                "active": True,
            },
        },
        {
            "type": "update",
            "args": [
                91,
                {
                    "active": True,
                },
            ],
        },
        {
            "type": "windowUpdate",
            "args": [
                7,
                {
                    "focused": True,
                },
            ],
        },
    ]
    assert results["staleQueriedExactTab"]["result"] is True
    assert results["staleQueriedExactTab"]["tabOps"] == [
        {
            "type": "query",
            "query": {
                "url": "http://127.0.0.1:8877/*",
            },
        },
        {
            "type": "executeScript",
            "args": {
                "target": {
                    "tabId": 93,
                },
            },
        },
        {
            "type": "create",
            "args": {
                "url": "http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake",
                "active": True,
            },
        },
        {
            "type": "update",
            "args": [
                91,
                {
                    "active": True,
                },
            ],
        },
        {
            "type": "windowUpdate",
            "args": [
                7,
                {
                    "focused": True,
                },
            ],
        },
    ]
    assert results["stalePendingExactTab"]["result"] is True
    assert results["stalePendingExactTab"]["tabOps"] == [
        {
            "type": "query",
            "query": {
                "url": "http://127.0.0.1:8877/*",
            },
        },
        {
            "type": "executeScript",
            "args": {
                "target": {
                    "tabId": 93,
                },
            },
        },
        {
            "type": "create",
            "args": {
                "url": "http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake",
                "active": True,
            },
        },
        {
            "type": "update",
            "args": [
                91,
                {
                    "active": True,
                },
            ],
        },
        {
            "type": "windowUpdate",
            "args": [
                7,
                {
                    "focused": True,
                },
            ],
        },
    ]
    assert results["currentFreshPendingTab"]["result"] is True
    assert results["currentFreshPendingTab"]["tabOps"] == [
        {
            "type": "query",
            "query": {
                "url": "http://127.0.0.1:8877/*",
            },
        },
        {
            "type": "update",
            "args": [
                77,
                {
                    "active": True,
                },
            ],
        },
        {
            "type": "windowUpdate",
            "args": [
                15,
                {
                    "focused": True,
                },
            ],
        },
    ]

    assert results["hydratedImmediate"]["result"] == {
        "holdLock": False,
        "outcome": "loaded",
    }
    assert not any(op["type"] == "reload" for op in results["hydratedImmediate"]["tabOps"])
    assert results["hydratedImmediate"]["sentMessages"][-1] == {
        "tabId": 13,
        "payload": {
            "type": "gmail-intake-status",
            "kind": "success",
            "message": "Gmail intake accepted.",
        },
    }

    assert results["hydratedAfterReload"]["result"] == {
        "holdLock": False,
        "outcome": "workspace_surface_unconfirmed",
    }
    assert [op for op in results["hydratedAfterReload"]["tabOps"] if op["type"] == "reload"] == []
    assert results["hydratedAfterReload"]["sentMessages"][-1] == {
        "tabId": 14,
        "payload": {
            "type": "gmail-intake-status",
            "kind": "error",
            "message": (
                "LegalPDF Translate opened, but the Gmail workspace tab is still running stale browser assets. "
                "Expected asset version: asset-20260330. Tab asset version: asset-stale-old. "
                "Please focus the LegalPDF tab and click the extension again."
            ),
        },
    }

    assert results["hydratedNever"]["result"] == {
        "holdLock": True,
        "outcome": "warming",
    }
    assert [op for op in results["hydratedNever"]["tabOps"] if op["type"] == "reload"] == []
    assert results["hydratedNever"]["sentMessages"][-1] == {
        "tabId": 15,
        "payload": {
            "type": "gmail-intake-status",
            "kind": "info",
            "message": (
                "Gmail intake accepted. LegalPDF Translate received the Gmail handoff and is still loading "
                "the exact Gmail message. Please wait a few seconds, then click the extension again only if it stays stuck."
            ),
        },
    }

    assert results["hydratedStaleNever"]["result"] == {
        "holdLock": False,
        "outcome": "workspace_surface_unconfirmed",
    }
    assert [op for op in results["hydratedStaleNever"]["tabOps"] if op["type"] == "reload"] == []
    assert results["hydratedStaleNever"]["sentMessages"][-1] == {
        "tabId": 16,
        "payload": {
            "type": "gmail-intake-status",
            "kind": "error",
            "message": (
                "LegalPDF Translate opened, but the Gmail workspace tab is still running stale browser assets. "
                "Expected asset version: asset-20260330. Tab asset version: asset-stale-before-reload. "
                "Please focus the LegalPDF tab and click the extension again."
            ),
        },
    }

    assert results["pendingWithoutSurface"]["result"] == {
        "holdLock": False,
        "outcome": "workspace_surface_unconfirmed",
    }
    assert results["pendingWithoutSurface"]["sentMessages"][-1] == {
        "tabId": 17,
        "payload": {
            "type": "gmail-intake-status",
            "kind": "error",
            "message": (
                "LegalPDF Translate did not confirm that the Gmail workspace tab opened correctly. "
                "Please focus the LegalPDF tab and click the extension again. "
                "The browser app may still need manual focus."
            ),
        },
    }


def test_gmail_extension_options_page_is_diagnostics_first() -> None:
    extension_dir = Path(__file__).resolve().parents[1] / "extensions" / "gmail_intake"
    options_js = (extension_dir / "options.js").read_text(encoding="utf-8")
    options_html = (extension_dir / "options.html").read_text(encoding="utf-8")

    assert 'action: "prepare_gmail_intake"' in options_js
    assert "requestFocus: false" in options_js
    assert "includeToken: false" in options_js
    assert "Auto-configured from LegalPDF Translate" in options_js
    assert "Native host unavailable" in options_js
    assert "formatNativeHostError" in options_js
    assert "toolbar clicks can auto-start the app" in options_js
    assert "Launch Target" in options_html
    assert "Auto-launch" in options_html
    assert "Native Host Error" in options_html
    assert "Refresh Diagnostics" in options_html
    assert "Raw bridge tokens stay hidden here." in options_html
    assert "Legacy fallback" in options_html
    assert "bridgeToken" not in options_html


def test_browser_pdf_asset_urls_use_static_root_without_nested_vendor_segment() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for browser PDF asset URL coverage.")

    module_path = Path(__file__).resolve().parents[1] / "src" / "legalpdf_translate" / "shadow_web" / "static" / "browser_pdf.js"
    script = f"""
import {{ pathToFileURL }} from "node:url";

globalThis.window = {{
  location: {{ origin: "http://127.0.0.1:8877" }},
  LEGALPDF_BROWSER_BOOTSTRAP: {{
    buildSha: "6e823b2",
    staticBasePath: "/static/",
  }},
}};

const moduleUrl = pathToFileURL({json.dumps(str(module_path))}).href;
const browserPdf = await import(moduleUrl);
const resolved = browserPdf.resolveBrowserPdfAssetUrls();
console.log(JSON.stringify(resolved));
"""
    completed = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["moduleUrl"] == "http://127.0.0.1:8877/static/vendor/pdfjs/pdf.mjs?v=6e823b2"
    assert payload["workerUrl"] == "http://127.0.0.1:8877/static/vendor/pdfjs/pdf.worker.mjs?v=6e823b2"
    assert "/vendor/pdfjs/vendor/pdfjs/" not in payload["workerUrl"]


def test_browser_pdf_asset_urls_accept_absolute_static_base_path() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for browser PDF asset URL coverage.")

    module_path = Path(__file__).resolve().parents[1] / "src" / "legalpdf_translate" / "shadow_web" / "static" / "browser_pdf.js"
    script = f"""
import {{ pathToFileURL }} from "node:url";

globalThis.window = {{
  location: {{ origin: "http://127.0.0.1:8877" }},
  LEGALPDF_BROWSER_BOOTSTRAP: {{
    buildSha: "6e823b2",
    staticBasePath: "http://127.0.0.1:8877/static/",
  }},
}};

const moduleUrl = pathToFileURL({json.dumps(str(module_path))}).href;
const browserPdf = await import(moduleUrl);
const resolved = browserPdf.resolveBrowserPdfAssetUrls();
console.log(JSON.stringify(resolved));
"""
    completed = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["moduleUrl"] == "http://127.0.0.1:8877/static/vendor/pdfjs/pdf.mjs?v=6e823b2"
    assert payload["workerUrl"] == "http://127.0.0.1:8877/static/vendor/pdfjs/pdf.worker.mjs?v=6e823b2"
    assert "/http://127.0.0.1:8877/static/" not in payload["workerUrl"]


def test_browser_pdf_asset_urls_stay_under_versioned_static_prefix() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for browser PDF asset URL coverage.")

    module_path = Path(__file__).resolve().parents[1] / "src" / "legalpdf_translate" / "shadow_web" / "static" / "browser_pdf.js"
    script = f"""
import {{ pathToFileURL }} from "node:url";

globalThis.window = {{
  location: {{ origin: "http://127.0.0.1:8877" }},
  LEGALPDF_BROWSER_BOOTSTRAP: {{
    buildSha: "6e823b2",
    assetVersion: "asset-20260330",
    staticBasePath: "http://127.0.0.1:8877/static-build/asset-20260330/",
  }},
}};

const moduleUrl = pathToFileURL({json.dumps(str(module_path))}).href;
const browserPdf = await import(moduleUrl);
const resolved = browserPdf.resolveBrowserPdfAssetUrls();
console.log(JSON.stringify(resolved));
"""
    completed = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["moduleUrl"] == "http://127.0.0.1:8877/static-build/asset-20260330/vendor/pdfjs/pdf.mjs?v=asset-20260330"
    assert payload["workerUrl"] == "http://127.0.0.1:8877/static-build/asset-20260330/vendor/pdfjs/pdf.worker.mjs?v=asset-20260330"
    assert "/vendor/pdfjs/vendor/pdfjs/" not in payload["workerUrl"]


def test_browser_pdf_worker_bootstrap_preserves_raw_worker_failure_and_uses_blob_wrapper_fallback() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for browser PDF bootstrap coverage.")

    module_path = Path(__file__).resolve().parents[1] / "src" / "legalpdf_translate" / "shadow_web" / "static" / "browser_pdf.js"
    script = f"""
import {{ pathToFileURL }} from "node:url";

globalThis.window = {{
  location: {{ origin: "http://127.0.0.1:8877" }},
  LEGALPDF_BROWSER_BOOTSTRAP: {{
    buildSha: "6e823b2",
    assetVersion: "asset-20260330",
    staticBasePath: "http://127.0.0.1:8877/static-build/asset-20260330/",
  }},
}};

const moduleUrl = pathToFileURL({json.dumps(str(module_path))}).href;
const browserPdf = await import(moduleUrl);
const assetUrls = browserPdf.resolveBrowserPdfAssetUrls();
const preflight = await browserPdf.preflightBrowserPdfAssetUrls({{
  assetUrls,
  fetchImpl: async (url) => ({{
    ok: true,
    status: 200,
    headers: {{
      get(name) {{
        return name === "content-type" ? "application/javascript" : "";
      }},
    }},
    body: {{ cancel() {{}} }},
  }}),
}});
const createdUrls = [];
const revokedUrls = [];
const pdfjsModule = {{
  GlobalWorkerOptions: {{
    workerSrc: "",
    workerPort: null,
  }},
}};
const result = await browserPdf.bootstrapBrowserPdfWorker({{
  pdfjsModule,
  assetUrls,
  preflight,
  workerFactory: (url, options) => {{
    createdUrls.push({{ url, type: options.type }});
    if (url === assetUrls.workerUrl) {{
      throw new TypeError("Failed to fetch dynamically imported module");
    }}
    return {{
      url,
      addEventListener() {{}},
      removeEventListener() {{}},
      terminate() {{}},
    }};
  }},
  blobFactory: (parts, options) => ({{ parts, options }}),
  createObjectUrl: (blob) => {{
    const wrapper = `blob:pdf-worker-wrapper:${{blob.parts.join("")}}`;
    createdUrls.push({{ url: wrapper, type: "blob-wrapper" }});
    return wrapper;
  }},
  revokeObjectUrl: (url) => {{
    revokedUrls.push(url);
  }},
  setTimeoutImpl: (callback) => {{
    callback();
    return 1;
  }},
  clearTimeoutImpl: () => undefined,
}});

console.log(JSON.stringify({{
  preflight,
  result,
  workerSrc: pdfjsModule.GlobalWorkerOptions.workerSrc,
  workerPortUrl: pdfjsModule.GlobalWorkerOptions.workerPort?.url || "",
  createdUrls,
  revokedUrls,
}}));
"""
    completed = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["preflight"]["module"]["contentType"] == "application/javascript"
    assert payload["preflight"]["worker"]["contentType"] == "application/javascript"
    assert payload["result"]["workerBootPhase"] == "worker_bootstrap_blob_wrapper"
    assert "Failed to fetch dynamically imported module" in payload["result"]["rawBrowserError"]
    assert payload["workerSrc"] == "http://127.0.0.1:8877/static-build/asset-20260330/vendor/pdfjs/pdf.worker.mjs?v=asset-20260330"
    assert payload["workerPortUrl"].startswith("blob:pdf-worker-wrapper:")
    assert payload["revokedUrls"] == [payload["workerPortUrl"]]


def test_browser_pdf_error_normalization_and_gmail_runtime_guard_keep_worker_and_provenance_details() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for browser PDF diagnostics coverage.")

    browser_pdf_path = Path(__file__).resolve().parents[1] / "src" / "legalpdf_translate" / "shadow_web" / "static" / "browser_pdf.js"
    guard_path = Path(__file__).resolve().parents[1] / "src" / "legalpdf_translate" / "shadow_web" / "static" / "gmail_runtime_guard.js"
    script = f"""
import {{ pathToFileURL }} from "node:url";

globalThis.window = {{
  location: {{ origin: "http://127.0.0.1:8877" }},
  LEGALPDF_BROWSER_BOOTSTRAP: {{
    buildSha: "6e823b2",
    assetVersion: "asset-20260330",
    staticBasePath: "http://127.0.0.1:8877/static-build/asset-20260330/",
  }},
}};

const browserPdf = await import(pathToFileURL({json.dumps(str(browser_pdf_path))}).href);
const runtimeGuard = await import(pathToFileURL({json.dumps(str(guard_path))}).href);

const normalized = browserPdf.normalizeBrowserPdfError(
  new Error('Setting up fake worker failed: "Failed to fetch dynamically imported module".'),
  {{
    phase: "worker_boot",
    workerBootPhase: "worker_bootstrap_blob_wrapper",
    rawBrowserError: "TypeError: Failed to fetch dynamically imported module",
    workerFetchStatus: 200,
    workerContentType: "application/javascript",
    moduleFetchStatus: 200,
    moduleContentType: "application/javascript",
    attemptedUrl: "http://127.0.0.1:8877/static-build/asset-20260330/vendor/pdfjs/pdf.worker.mjs?v=asset-20260330",
  }},
);
const diagnostics = browserPdf.browserPdfDiagnosticsFromError(normalized);
const guard = runtimeGuard.deriveGmailLiveRuntimeGuard({{
  runtime: {{
    live_data: true,
    build_branch: "feat/lichtfeld-wsl-setup",
    build_sha: "6e823b2",
  }},
  buildIdentity: {{
    branch: "feat/lichtfeld-wsl-setup",
    head_sha: "6e823b2",
    is_canonical: false,
    canonical_branch: "main",
    worktree_path: "C:/Users/FA507/.codex/legalpdf_translate",
    canonical_worktree_path: "C:/Users/FA507/.codex/legalpdf_translate",
    reasons: ["branch mismatch"],
  }},
}});

console.log(JSON.stringify({{ diagnostics, guard }}));
"""
    completed = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["diagnostics"]["error"] == "browser_pdf_worker_load_failed"
    assert payload["diagnostics"]["worker_boot_phase"] == "worker_bootstrap_blob_wrapper"
    assert payload["diagnostics"]["raw_browser_error"] == "TypeError: Failed to fetch dynamically imported module"
    assert payload["guard"]["active"] is True
    assert payload["guard"]["blocked"] is True
    assert payload["guard"]["canonicalBranch"] == "main"
    assert "branch mismatch" in payload["guard"]["details"][-1]
