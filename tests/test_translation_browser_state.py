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
    innerHTML: initial.innerHTML || "",
    checked: Boolean(initial.checked),
    href: initial.href || "",
    open: Boolean(initial.open),
    disabled: Boolean(initial.disabled),
    hidden: Boolean(initial.hidden),
    className: initial.className || "",
    dataset: {{}},
    style: {{}},
    children: [],
    classList: {{
      add() {{}},
      remove() {{}},
      toggle() {{}},
      contains() {{ return false; }},
    }},
    setAttribute() {{}},
    removeAttribute() {{}},
    appendChild(node) {{ this.children.push(node); return node; }},
    replaceChildren(...nodes) {{ this.children = nodes; }},
    addEventListener() {{}},
    removeEventListener() {{}},
    querySelector() {{ return null; }},
  }};
}}

for (const id of [
  "translation-source-file",
  "translation-source-path",
  "translation-output-dir",
  "translation-target-lang",
  "translation-image-mode",
  "translation-ocr-mode",
  "translation-ocr-engine",
  "translation-start-page",
  "translation-source-summary",
  "translation-status",
]) {{
  elements.set(id, makeElement());
}}

for (const [id, checked] of [
  ["translation-resume", true],
  ["translation-keep-intermediates", false],
  ["translation-page-breaks", true],
]) {{
  elements.set(id, makeElement({{ checked }}));
}}

globalThis.document = {{
  body: {{ dataset: {{}} }},
  getElementById(id) {{
    if (!elements.has(id)) {{
      elements.set(id, makeElement());
    }}
    return elements.get(id);
  }},
  querySelectorAll() {{
    return [];
  }},
  createElement() {{
    return makeElement();
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

translationModule.renderTranslationJob({{
  job_id: "tx-old-failed",
  job_kind: "translate",
  status: "failed",
  status_text: "Translate failed",
  config: {{
    source_path: "C:/tmp/old-gmail.pdf",
    target_lang: "FR",
    start_page: 1,
    gmail_batch_context: {{
      source: "gmail_intake",
      session_id: "gmail_batch_old",
      message_id: "msg-old",
      thread_id: "thr-old",
      attachment_id: "att-old",
      selected_attachment_filename: "old-gmail.pdf",
      selected_attachment_count: 1,
      selected_target_lang: "FR",
      selected_start_page: 1,
      gmail_batch_session_report_path: "C:/tmp/old_session.json",
    }},
  }},
  diagnostics: {{
    error: "Old failed job",
  }},
  actions: {{
    resume: true,
    rebuild: true,
  }},
}});
results.staleJobBeforePrepare = translationModule.getTranslationUiSnapshot();

sourceFile.value = "manual-stale.pdf";
translationModule.applyTranslationLaunch({{
  source_path: "C:/tmp/manual.pdf",
  source_filename: "manual.pdf",
  page_count: 2,
  start_page: 1,
  output_dir: "C:/tmp",
  target_lang: "EN",
  image_mode: "off",
  ocr_mode: "off",
  ocr_engine: "local",
  resume: true,
  keep_intermediates: false,
}});
results.manualLaunch = {{
  sourceFileValue: sourceFile.value,
  resumeChecked: elements.get("translation-resume").checked,
  keepIntermediatesChecked: elements.get("translation-keep-intermediates").checked,
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
  image_mode: "auto",
  ocr_mode: "auto",
  ocr_engine: "local_then_api",
  resume: false,
  keep_intermediates: true,
  auto_start: false,
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
  outputDirValue: elements.get("translation-output-dir").value,
  targetLangValue: elements.get("translation-target-lang").value,
  imageModeValue: elements.get("translation-image-mode").value,
  ocrModeValue: elements.get("translation-ocr-mode").value,
  ocrEngineValue: elements.get("translation-ocr-engine").value,
  resumeChecked: elements.get("translation-resume").checked,
  keepIntermediatesChecked: elements.get("translation-keep-intermediates").checked,
  summaryValue: elements.get("translation-source-summary").value,
  resultHtml: elements.get("translation-result").innerHTML,
  snapshot: translationModule.getTranslationUiSnapshot(),
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

    stale_job = results["staleJobBeforePrepare"]
    assert stale_job["currentJobId"] == "tx-old-failed"
    assert stale_job["currentJobFailed"] is True
    assert stale_job["currentGmailBatchContext"]["attachment_id"] == "att-old"

    assert results["manualLaunch"]["sourceFileValue"] == "manual-stale.pdf"
    assert results["manualLaunch"]["resumeChecked"] is True
    assert results["manualLaunch"]["keepIntermediatesChecked"] is False
    assert results["manualLaunch"]["gmailContext"] is None

    gmail_launch = results["gmailLaunch"]
    assert gmail_launch["sourceFileValue"] == ""
    assert gmail_launch["sourcePathValue"] == "C:/tmp/gmail.pdf"
    assert gmail_launch["outputDirValue"] == "C:/tmp/gmail"
    assert gmail_launch["targetLangValue"] == "AR"
    assert gmail_launch["imageModeValue"] == "auto"
    assert gmail_launch["ocrModeValue"] == "auto"
    assert gmail_launch["ocrEngineValue"] == "local_then_api"
    assert gmail_launch["resumeChecked"] is False
    assert gmail_launch["keepIntermediatesChecked"] is True
    assert "Filename: gmail.pdf" in gmail_launch["summaryValue"]
    assert "Resume: off" in gmail_launch["summaryValue"]
    assert "Keep intermediates: on" in gmail_launch["summaryValue"]
    assert "Prepared Gmail attachment is ready to start." in gmail_launch["resultHtml"]
    assert gmail_launch["snapshot"]["currentJobId"] == ""
    assert gmail_launch["snapshot"]["currentJobFailed"] is False
    assert gmail_launch["snapshot"]["hasPreparedLaunch"] is True
    assert gmail_launch["snapshot"]["preparedLaunchAttachmentId"] == "att-1"
    assert gmail_launch["gmailContext"]["session_id"] == "gmail_batch_1"
    assert gmail_launch["gmailContext"]["attachment_id"] == "att-1"
