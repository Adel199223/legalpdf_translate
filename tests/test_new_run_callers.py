"""Existing entry points run the real workflow with an injected offline provider.

Only external/configuration boundaries are replaced; constructor policy, source
extraction, block translation, publication, checkpoint and DOCX assembly are real.
"""
from __future__ import annotations

import json
from pathlib import Path
import socket
import subprocess
import threading
import time
from types import SimpleNamespace

import fitz
import pytest

from legalpdf_translate import cli
from legalpdf_translate import metadata_autofill
from legalpdf_translate import ocr_engine
from legalpdf_translate import translation_service as service
from legalpdf_translate import workflow as workflow_module
from legalpdf_translate.checkpoint import load_run_state
from legalpdf_translate.openai_client import ApiCallResult
from legalpdf_translate.structured_artifacts import validate_structured_page
from legalpdf_translate.types import ImageMode, OcrMode, RunConfig, TargetLang


SOURCE = ("O destinatario deve comparecer na audiencia e apresentar os documentos solicitados. "
          "Esta notificacao explica os deveres e os direitos da pessoa notificada. "
          "As instrucoes devem ser lidas com atencao e conservadas para futura consulta.")
TRANSLATION = ("The addressee must attend the hearing and provide the requested documents. "
               "This notice explains the duties and rights of the notified person. "
               "The instructions must be read carefully and retained for future reference.")


class OfflineProvider:
    def __init__(self, calls):
        self.calls = calls

    def create_page_response(self, **kwargs):
        self.calls.append(kwargs)
        if "response_format" in kwargs:
            payload, _ = json.JSONDecoder().raw_decode(kwargs["prompt_text"])
            text = json.dumps({"blocks": [{"id": row["id"], "text": TRANSLATION}
                                          for row in payload["blocks"]]})
        else:
            text = "```\n" + TRANSLATION + "\n```"
        return ApiCallResult(raw_output=text, usage={"input_tokens": 100, "output_tokens": 80,
            "reasoning_tokens": 20, "total_tokens": 180}, response_id="offline-call",
            response_status="completed", refused=False, model="offline-test", effort=kwargs["effort"])


@pytest.fixture
def offline(tmp_path, monkeypatch):
    assert Path(workflow_module.__file__).resolve().is_relative_to(Path(__file__).resolve().parents[1] / "src")
    def forbidden(*args, **kwargs):
        pytest.fail("Unexpected credential, authentication, OCR, network or native operation")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    # Windows asyncio's in-process wakeup socketpair uses a loopback connect.
    # Permit only that stdlib construction interval, never general networking.
    original_pair, original_connect = socket.socketpair, socket.socket.connect
    socket_scope = threading.local()
    def local_pair(*args, **kwargs):
        socket_scope.creating_pair = True
        try:
            return original_pair(*args, **kwargs)
        finally:
            socket_scope.creating_pair = False
    def guarded_connect(sock, address):
        if (getattr(socket_scope, "creating_pair", False)
                and isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}):
            return original_connect(sock, address)
        forbidden()
    monkeypatch.setattr(socket, "socketpair", local_pair)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "load_gui_settings", lambda: {})
    monkeypatch.setattr(cli, "load_gui_settings", lambda: {})
    monkeypatch.setattr(workflow_module, "run_translation_auth_test", forbidden)
    monkeypatch.setattr(workflow_module, "ocr_pdf_page_text", forbidden)
    monkeypatch.setattr(workflow_module, "ocr_pdf_page_crop_text", forbidden)
    monkeypatch.setattr(ocr_engine, "invoke_ocr_image", forbidden)
    monkeypatch.setattr(ocr_engine, "build_ocr_engine", forbidden)
    monkeypatch.setattr(service, "resolve_openai_key_with_source", forbidden)
    monkeypatch.setattr(service, "resolve_ocr_api_key", forbidden)
    # The browser save-row suggestion is auxiliary metadata, not translation.
    monkeypatch.setattr(metadata_autofill, "extract_pdf_header_metadata_priority_pages", lambda *a, **k: None)
    source = tmp_path / "notice.pdf"
    with fitz.open() as document:
        page = document.new_page()
        page.insert_textbox(fitz.Rect(40, 160, 550, 400), SOURCE, fontsize=11)
        document.save(source)
    out = tmp_path / "outputs"
    out.mkdir()
    settings = tmp_path / "settings.json"
    settings.write_text("{}", encoding="utf-8")
    calls, workflows = [], []
    provider = OfflineProvider(calls)
    real_workflow = workflow_module.TranslationWorkflow

    class InjectedWorkflow(real_workflow):
        def __init__(self, **kwargs):
            kwargs["client"] = provider
            super().__init__(**kwargs)
            workflows.append(self)

    monkeypatch.setattr(workflow_module, "TranslationWorkflow", InjectedWorkflow)
    monkeypatch.setattr(cli, "TranslationWorkflow", InjectedWorkflow)
    monkeypatch.setattr(service, "OpenAIResponsesClient", lambda **kwargs: provider)
    return SimpleNamespace(source=source, out=out, settings=settings, calls=calls,
        workflows=workflows, provider=provider, workflow_class=InjectedWorkflow)


def policy(monkeypatch, structured):
    if structured:
        monkeypatch.setenv("LEGALPDF_TRANSLATION_PROTOCOL", "legal_blocks_v2")
    else:
        monkeypatch.delenv("LEGALPDF_TRANSLATION_PROTOCOL", raising=False)


def config(fixture):
    return RunConfig(pdf_path=fixture.source, output_dir=fixture.out, target_lang=TargetLang.EN,
        image_mode=ImageMode.OFF, ocr_mode=OcrMode.OFF, workers=1, resume=False,
        page_breaks=False, keep_intermediates=True)


def assert_completed(fixture, structured):
    assert len(fixture.workflows) == 1
    workflow = fixture.workflows[0]
    state = load_run_state(workflow._last_paths.run_state_path)
    assert state.run_status == "completed", state.to_dict()
    assert state.pages["1"]["status"] == "done"
    assert Path(state.final_docx_path_abs).is_file()
    assert fixture.calls and all(("response_format" in call) is structured for call in fixture.calls)
    assert workflow._translation_protocol == ("legal_blocks_v2" if structured else "legacy_text_v1")
    if structured:
        assert state.protocol_identity["protocol"] == "legal_blocks_v2"
        commit = validate_structured_page(workflow._last_paths.pages_dir, 1,
            protocol_identity=state.protocol_identity, expected_commit=state.pages["1"]["structured_commit"])
        assert commit["source_file_sha256"] == state.pdf_fingerprint
        assert state.pages["1"]["fidelity_review_status"] == "not_evaluated"
    else:
        assert state.protocol_identity == {}
        assert not tuple(workflow._last_paths.pages_dir.glob("*.commit.json"))


def form(fixture):
    return {"source_path": str(fixture.source), "output_dir": str(fixture.out), "target_lang": "EN",
        "effort": "high", "image_mode": "off", "ocr_mode": "off", "ocr_engine": "local_then_api",
        "workers": 1, "resume": False, "keep_intermediates": True, "page_breaks": False,
        "diagnostics_admin_mode": False}


def await_job(manager, job_id):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        job = manager.get_job(job_id)
        if job["status"] not in {"queued", "running", "cancel_requested"}:
            return job
        time.sleep(.01)
    pytest.fail("Offline translation job did not finish")


@pytest.mark.parametrize("structured", [False, True])
def test_actual_browser_service_uses_internal_policy_without_new_form_values(offline, monkeypatch, structured):
    policy(monkeypatch, structured)
    manager = service.TranslationJobManager()
    values = form(offline)
    snapshot = dict(values)
    started = manager.start_translate(runtime_mode="shadow", workspace_id="offline-new-runs",
        form_values=values, settings_path=offline.settings)
    job = await_job(manager, started["job_id"])
    assert job["status"] == "completed", job
    assert values == snapshot and "translation_protocol" not in job["config"]
    assert job["config"]["effort"] == "high" and job["config"]["ocr_engine"] == "local_then_api"
    assert job["config"]["page_breaks"] is False
    assert_completed(offline, structured)


@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize("queue", [False, True])
def test_actual_cli_and_queue_share_policy_and_existing_flags(offline, monkeypatch, structured, queue, tmp_path):
    policy(monkeypatch, structured)
    arguments = ["--lang", "EN", "--outdir", str(offline.out), "--ocr-mode", "off",
        "--images", "off", "--workers", "1", "--resume", "false", "--page-breaks", "false"]
    if queue:
        manifest = tmp_path / "queue.json"
        manifest.write_text(json.dumps([{"job_id": "one", "pdf": str(offline.source),
            "lang": "EN", "outdir": str(offline.out)}]), encoding="utf-8")
        arguments += ["--queue-manifest", str(manifest)]
    else:
        arguments += ["--pdf", str(offline.source)]
    assert cli.main(arguments) == 0
    assert "translation_protocol" not in vars(cli.build_arg_parser().parse_args(arguments))
    assert_completed(offline, structured)


@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize("queue", [False, True])
def test_actual_qt_workers_share_policy_without_showing_ui(offline, monkeypatch, structured, queue, tmp_path):
    from legalpdf_translate.qt_gui import worker as qt_worker
    policy(monkeypatch, structured)
    monkeypatch.setattr(qt_worker, "TranslationWorkflow", offline.workflow_class)
    monkeypatch.setattr(qt_worker, "OpenAIResponsesClient", lambda **kwargs: offline.provider)
    if queue:
        manifest = tmp_path / "qt_queue.json"
        manifest.write_text(json.dumps([{"job_id": "one", "pdf": str(offline.source)}]), encoding="utf-8")
        worker = qt_worker.QueueRunWorker(manifest_path=manifest, rerun_failed_only=False,
            build_config=lambda payload: config(offline), max_transport_retries=0, backoff_cap_seconds=1)
    else:
        worker = qt_worker.TranslationRunWorker(config=config(offline),
            max_transport_retries=0, backoff_cap_seconds=1)
    finished, errors = [], []
    worker.finished.connect(finished.append)
    worker.error.connect(errors.append)
    worker.run()
    assert not errors and len(finished) == 1, errors
    assert finished[0].success
    assert_completed(offline, structured)


def test_actual_browser_route_dispatches_unchanged_payload_to_real_service(offline, monkeypatch):
    from fastapi.testclient import TestClient
    from legalpdf_translate.shadow_web import app as browser
    policy(monkeypatch, True)
    # Do not run app lifespan, listener probes, Gmail or native review managers.
    monkeypatch.setattr(browser, "detect_runtime_build_identity", lambda **k: SimpleNamespace())
    monkeypatch.setattr(browser, "detect_shadow_runtime_paths", lambda **k: SimpleNamespace())
    monkeypatch.setattr(browser, "run_browser_automation_preflight", lambda **k: {})
    monkeypatch.setattr(browser, "GmailBrowserSessionManager", lambda: SimpleNamespace())
    monkeypatch.setattr(browser, "ArabicDocxReviewManager", lambda: SimpleNamespace())
    monkeypatch.setattr(browser, "BrowserLiveGmailBridgeManager", lambda **k: SimpleNamespace())
    target = SimpleNamespace(mode="shadow", workspace_id="offline-route",
        data_paths=SimpleNamespace(settings_path=offline.settings))
    monkeypatch.setattr(browser, "_active_target", lambda *a, **k: target)
    monkeypatch.setattr(browser, "_merge_response", lambda context, target, response: response)
    monkeypatch.setattr(browser, "build_translation_capability_flags", lambda **k: {})
    app = browser.create_shadow_app(repo_root=offline.out, enable_live_gmail_bridge=False)
    # A non-context-managed TestClient does not enter app lifespan. Requests
    # travel through ASGI in process: no browser, socket listener or server.
    client = TestClient(app)
    payload = {"mode": "shadow", "workspace_id": "offline-route", "form_values": form(offline)}
    response = client.post("/api/translation/jobs/translate", json=payload)
    assert response.status_code == 200, response.text
    packet = response.json()
    assert set(packet) == {"status", "normalized_payload", "diagnostics", "capability_flags"}
    manager = app.state.shadow_context.translation_jobs
    job = await_job(manager, packet["normalized_payload"]["job"]["job_id"])
    assert job["status"] == "completed", job
    assert "translation_protocol" not in payload["form_values"]
    assert job["config"]["target_lang"] == "EN" and job["config"]["effort"] == "high"
    assert_completed(offline, True)
    client.close()
