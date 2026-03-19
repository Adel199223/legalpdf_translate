function extractErrorMessage(payload) {
  return String(
    payload?.diagnostics?.error ||
      payload?.diagnostics?.message ||
      payload?.message ||
      payload?.error ||
      "",
  ).trim();
}

export async function fetchJson(path, state, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("X-LegalPDF-Runtime-Mode", state.runtimeMode);
  headers.set("X-LegalPDF-Workspace-Id", state.workspaceId);
  const response = await fetch(path, {
    ...options,
    headers,
  });
  const rawText = await response.text();
  let payload = {};
  if (rawText) {
    try {
      payload = JSON.parse(rawText);
    } catch {
      payload = {
        status: "failed",
        diagnostics: {
          error: rawText,
        },
      };
    }
  }
  if (!response.ok || payload.status === "failed") {
    const error = new Error(
      extractErrorMessage(payload) || rawText || `Request failed (${response.status}).`,
    );
    error.payload = payload;
    error.status = response.status;
    throw error;
  }
  return payload;
}
