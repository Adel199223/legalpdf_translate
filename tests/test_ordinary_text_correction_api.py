"""Real local browser routes, selected download, Save and Gmail confirmation."""
from copy import deepcopy
from dataclasses import replace
import hashlib
from types import SimpleNamespace

from fastapi.testclient import TestClient

from legalpdf_translate.shadow_web import app as browser
from legalpdf_translate import translation_service, gmail_browser_service
from legalpdf_translate.gmail_batch import GmailBatchSession, DownloadedGmailAttachment
from tests.test_gmail_browser_service import _load_result
from tests.test_ordinary_layout_service import make_case, nonce
from tests.test_ordinary_layout_delivery_integration import snapshot
from tests.test_ordinary_text_correction import action


def test_normal_correction_download_save_and_gmail_reuse_same_row(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    job = snapshot(case, tmp_path)
    original = deepcopy(job)
    source = tmp_path / "source.pdf"; source.write_bytes(case.job.source_pdf)
    job["config"] = {"source_path": str(source), "start_page": 1}
    jobs = SimpleNamespace(get_job=lambda identity: deepcopy(job) if identity == job["job_id"] else None)
    gmail = gmail_browser_service.GmailBrowserSessionManager()
    loaded = _load_result(message_id="fictional-message", thread_id="fictional-thread", subject="Fictional",
        account_email="fictional@example.test", attachment_ids=("fictional-attachment",))
    session = GmailBatchSession(intake_context=loaded.intake_context, message=loaded.message, gog_path=loaded.gog_path,
        account_email=loaded.account_email, downloaded_attachments=(DownloadedGmailAttachment(loaded.message.attachments[0], source, 1, 1),),
        download_dir=tmp_path, selected_target_lang="EN", effective_output_dir=tmp_path)
    gmail._workspace(runtime_mode="shadow", workspace_id="fixture").batch_session = session
    services = replace(browser.offline_browser_app_services(state_root=tmp_path / "browser"),
        translation_jobs_factory=lambda: jobs, gmail_sessions_factory=lambda: gmail,
        ordinary_layout_factory=lambda *args, **kwargs: case.manager)
    for module in (translation_service, browser):
        monkeypatch.setattr(module, "build_translation_capability_flags", lambda **_: {})
    monkeypatch.setattr(gmail_browser_service, "build_gmail_browser_capability_flags", lambda **_: {})
    case.manager.provider_factory = lambda *_: (_ for _ in ()).throw(AssertionError("No paid correction"))
    app = browser.create_shadow_app(repo_root=tmp_path / "repo", services=services, enable_live_gmail_bridge=False)
    scope = "?mode=shadow&workspace=fixture"
    base = f"/api/translation/jobs/{job['job_id']}"
    with TestClient(app) as client:
        state = client.get(base + "/text-corrections" + scope).json()["normalized_payload"]["ordinary_layout"]
        body = {"draft_nonce": nonce(), "parent": state["parent"], "actions": [action(state["paragraphs"][0]["paragraph_id"], "Corrected fictional notice R")], "import_word": False}
        drafted = client.post(base + "/text-corrections" + scope, json=body)
        assert drafted.status_code == 200, drafted.text
        draft = drafted.json()["normalized_payload"]["ordinary_layout"]
        assert client.post(base + "/text-corrections" + scope, json=body).json() == drafted.json()
        approval = {"approval_nonce": nonce(), "source_compared": True, "changes_reviewed": True, "rationale": ""}
        selected = client.post(base + f"/text-corrections/{draft['draft_id']}/approve" + scope, json=approval)
        assert selected.status_code == 200, selected.text
        view = selected.json()["normalized_payload"]["ordinary_layout"]
        from legalpdf_translate.word_automation import WordAutomationResult
        opened_paths = []
        monkeypatch.setattr("legalpdf_translate.word_automation.open_docx_in_word",
            lambda path: opened_paths.append(path) or WordAutomationResult(True, "open", "Fictional owned copy"))
        parent = client.get(base + "/text-corrections" + scope).json()["normalized_payload"]["ordinary_layout"]["parent"]
        assert client.post(base + "/text-corrections/word/open" + scope, json={"parent": state["parent"]}).status_code == 409
        assert not opened_paths
        assert client.post(base + "/text-corrections/word/open" + scope, json={"parent": parent}).status_code == 200
        assert len(opened_paths) == 1 and opened_paths[0].name == "working.docx"
        assert client.post(base + "/text-corrections/word/check" + scope, json={"parent": parent}).status_code == 200
        assert client.post(base + f"/text-corrections/{draft['draft_id']}/approve" + scope, json=approval).json() == selected.json()
        download = client.get(base + "/artifact/output_docx" + scope)
        assert hashlib.sha256(download.content).hexdigest() == view["delivery"]["sha256"]
        form = {**job["result"]["save_seed"], "target_lang": "EN", "expected_total_mode": "auto", "rate_per_word": ".027", "word_count": 999}
        request = {"job_id": job["job_id"], "form_values": form, "baseline_id": view["baseline_id"], "expected_delivery_generation": 1}
        assert client.post("/api/translation/save-row" + scope, json=request).status_code != 200
        reviewed = client.post(base + "/text-corrections/output-review" + scope, json={"selection_id": view["delivery"]["selection_id"], "expected_generation": 1, "all_pages_reviewed": True})
        assert reviewed.status_code == 200, reviewed.text
        saved = client.post("/api/translation/save-row" + scope, json=request)
        assert saved.status_code == 200, saved.text
        row = saved.json()["saved_result"]["row_id"]
        assert saved.json()["saved_result"]["word_count"] == view["delivery"]["word_count"]
        confirmed = client.post("/api/gmail/batch/confirm-current" + scope, json={**request, "row_id": row})
        assert confirmed.status_code == 200, confirmed.text
        item = session.confirmed_items[0]
        assert item.joblog_row_id == row and item.delivery_sha256 == hashlib.sha256(download.content).hexdigest()
        assert item.staged_translated_docx_path.read_bytes() == download.content
        assert job["result"]["save_seed"] == original["result"]["save_seed"]
