const DEFAULT_BRIDGE_PORT = 8765;

function normalizePort(value) {
  const parsed = Number.parseInt(String(value ?? DEFAULT_BRIDGE_PORT), 10);
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 65535) {
    return DEFAULT_BRIDGE_PORT;
  }
  return parsed;
}

async function loadOptions() {
  const stored = await chrome.storage.local.get(["bridgePort", "bridgeToken"]);
  document.getElementById("bridgeToken").value = String(stored.bridgeToken ?? "").trim();
  document.getElementById("bridgePort").value = String(normalizePort(stored.bridgePort));
}

async function saveOptions() {
  const token = String(document.getElementById("bridgeToken").value ?? "").trim();
  const port = normalizePort(document.getElementById("bridgePort").value);
  await chrome.storage.local.set({
    bridgePort: port,
    bridgeToken: token
  });
  document.getElementById("bridgePort").value = String(port);
  document.getElementById("status").textContent = "Saved.";
  window.setTimeout(() => {
    document.getElementById("status").textContent = "";
  }, 2000);
}

document.addEventListener("DOMContentLoaded", () => {
  void loadOptions();
  document.getElementById("saveButton").addEventListener("click", () => {
    void saveOptions();
  });
});
