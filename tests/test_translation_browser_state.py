import json
import shutil
import subprocess
from pathlib import Path

import pytest


def _run_translation_browser_state_probe() -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for browser translation state coverage.")

    module_url = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
        / "translation.js"
    ).as_uri()

    script = f"""
const elements = new Map();
function makeElement(initial = {{}}) {{
  return {{
    value: initial.value || "",
    textContent: initial.textContent || "",
    checked: Boolean(initial.checked),
    href: initial.href || "",
    open: Boolean(initial.open),
    dataset: {{}},
    classList: {{
      add() {{}},
      remove() {{}},
      toggle() {{}},
    }},
    setAttribute() {{}},
    removeAttribute() {{}},
  }};
}}

for (const id of [
  "translation-source-file",
  "translation-source-path",
  "translation-output-dir",
  "translation-target-lang",
  "translation-start-page",
  "translation-source-summary",
  "translation-status",
]) {{
  elements.set(id, makeElement());
}}

globalThis.document = {{
  body: {{ dataset: {{}} }},
  getElementById(id) {{
    return elements.get(id) || null;
  }},
  querySelectorAll() {{
    return [];
  }},
}};

globalThis.window = {{
  LEGALPDF_BROWSER_BOOTSTRAP: {{}},
  dispatchEvent() {{}},
  addEventListener() {{}},
  removeEventListener() {{}},
  setTimeout() {{ return 1; }},
  clearTimeout() {{}},
  location: new URL("http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#new-job"),
  history: {{
    replaceState() {{}},
  }},
}};

globalThis.CustomEvent = class CustomEvent {{
  constructor(type, init = {{}}) {{
    this.type = type;
    this.detail = init.detail;
  }}
}};

const translationModule = await import({json.dumps(module_url)});
const results = {{}};
const sourceFile = elements.get("translation-source-file");

sourceFile.value = "manual-stale.pdf";
translationModule.applyTranslationLaunch({{
  source_path: "C:/tmp/manual.pdf",
  source_filename: "manual.pdf",
  page_count: 2,
  start_page: 1,
  output_dir: "C:/tmp",
  target_lang: "EN",
}});
results.manualLaunch = {{
  sourceFileValue: sourceFile.value,
  gmailContext: translationModule.getTranslationUiSnapshot().currentGmailBatchContext,
}};

sourceFile.value = "manual-stale.pdf";
translationModule.applyTranslationLaunch({{
  source_path: "C:/tmp/gmail.pdf",
  source_filename: "gmail.pdf",
  page_count: 5,
  start_page: 2,
  output_dir: "C:/tmp/gmail",
  target_lang: "AR",
  workflow_source: "gmail_intake",
  gmail_batch_context: {{
    source: "gmail_intake",
    session_id: "gmail_batch_1",
    message_id: "msg-1",
    thread_id: "thr-1",
    attachment_id: "att-1",
    selected_attachment_filename: "gmail.pdf",
    selected_attachment_count: 1,
    selected_target_lang: "AR",
    selected_start_page: 2,
    gmail_batch_session_report_path: "C:/tmp/gmail_session.json",
  }},
}});
results.gmailLaunch = {{
  sourceFileValue: sourceFile.value,
  sourcePathValue: elements.get("translation-source-path").value,
  summaryValue: elements.get("translation-source-summary").value,
  gmailContext: translationModule.getTranslationUiSnapshot().currentGmailBatchContext,
}};

console.log(JSON.stringify(results));
"""

    completed = subprocess.run(
        [node, "--input-type=module", "-"],
        input=script,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(completed.stdout)


def test_apply_translation_launch_clears_stale_manual_file_only_for_gmail_launch() -> None:
    results = _run_translation_browser_state_probe()

    assert results["manualLaunch"]["sourceFileValue"] == "manual-stale.pdf"
    assert results["manualLaunch"]["gmailContext"] is None

    gmail_launch = results["gmailLaunch"]
    assert gmail_launch["sourceFileValue"] == ""
    assert gmail_launch["sourcePathValue"] == "C:/tmp/gmail.pdf"
    assert "Filename: gmail.pdf" in gmail_launch["summaryValue"]
    assert gmail_launch["gmailContext"]["session_id"] == "gmail_batch_1"
    assert gmail_launch["gmailContext"]["attachment_id"] == "att-1"
