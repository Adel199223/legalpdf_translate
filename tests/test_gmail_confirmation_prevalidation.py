"""Confirmation validation uses fictional fixtures without external calls."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
import sqlite3
from tests.test_translation_completion_metrics import completion_seed
from tests.test_ordinary_layout_service import make_case, built, select
from tests.test_ordinary_layout_delivery_integration import snapshot
from tests.test_gmail_browser_service import _load_result
from legalpdf_translate.gmail_batch import GmailBatchSession, DownloadedGmailAttachment, gmail_batch_consistency_signature
from legalpdf_translate import gmail_browser_service, translation_service

@pytest.fixture
def confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(translation_service, "build_translation_capability_flags", lambda **_: {})
    monkeypatch.setattr(gmail_browser_service, "build_gmail_browser_capability_flags", lambda **_: {})
    case = make_case(tmp_path, monkeypatch); select(case, built(case))
    job = snapshot(case, tmp_path)
    source = tmp_path / "source.pdf"; source.write_bytes(case.job.source_pdf)
    job["config"] = {"source_path": str(source), "start_page": 1}
    loaded = _load_result(message_id="fictional-message", thread_id="fictional-thread", subject="Fictional", account_email="fictional@example.test", attachment_ids=("fictional-attachment",))
    session = GmailBatchSession(intake_context=loaded.intake_context, message=loaded.message, gog_path=loaded.gog_path,
        account_email=loaded.account_email, downloaded_attachments=(DownloadedGmailAttachment(loaded.message.attachments[0], source, 1, 1),),
        download_dir=tmp_path, selected_target_lang="EN", effective_output_dir=tmp_path)
    gmail = gmail_browser_service.GmailBrowserSessionManager()
    workspace = gmail._workspace(runtime_mode="shadow", workspace_id="fixture"); workspace.batch_session = session
    values = deepcopy(job["result"]["save_seed"])
    def submit(edits=None, row_id=None):
        return gmail.confirm_current_batch_translation(runtime_mode="shadow", workspace_id="fixture", settings_path=tmp_path/"settings.json",
            job_log_db_path=tmp_path/"jobs.sqlite", translation_jobs=SimpleNamespace(get_job=lambda _: deepcopy(job)), job_id=case.job.job_id,
            form_values={**values, **(edits or {})}, row_id=row_id, ordinary_layout_manager=case.manager,
            baseline_id=case.view["baseline_id"], expected_delivery_generation=1)
    return SimpleNamespace(case=case, job=job, session=session, workspace=workspace, submit=submit, root=tmp_path, values=values)

@pytest.mark.parametrize("kind", ["invalid_rate", "invalid_date", "missing_row", "foreign_row", "inconsistent_session"])
def test_invalid_confirmation_is_side_effect_free_and_retryable(confirmation, kind):
    x=confirmation; edits={}; row_id=None
    if kind == "invalid_rate": edits={"rate_per_word":"invalid-number"}
    elif kind == "invalid_date": edits={"translation_date":"2026-13-99"}
    elif kind == "missing_row": row_id=424242
    elif kind == "foreign_row":
        foreign={**x.values,"run_id":"another-fictional-run"}
        created=translation_service.save_translation_row(settings_path=x.root/"settings.json",job_log_db_path=x.root/"jobs.sqlite",
            form_values=foreign,seed_payload=foreign)
        row_id=created["saved_result"]["row_id"]
    else:
        x.session.consistency_signature=gmail_batch_consistency_signature(case_number="DIFFERENT",case_entity="Court",case_city="City",court_email="court@example.test")
    pins={path:path.read_bytes() for path in (x.root/"jobs.sqlite",x.root/"settings.json") if path.exists()}
    with pytest.raises(ValueError): x.submit(edits,row_id)
    assert x.case.manager.state(x.case.job.job_id)["frozen"] is None
    assert x.session.confirmed_items == [] and x.workspace.current_batch_index == 0
    assert not list((x.root/"_draft_attachments").glob("*"))
    for path in (x.root/"jobs.sqlite",x.root/"settings.json"):
        assert path.read_bytes() == pins[path] if path in pins else not path.exists()
    x.session.consistency_signature=None
    assert x.submit()["status"] == "ok"
    assert len(x.session.confirmed_items) == 1 and x.workspace.current_batch_index == 1
    assert x.case.manager.state(x.case.job.job_id)["frozen"] is not None

def test_io_failure_after_valid_preflight_preserves_retry_bound_lock(confirmation, monkeypatch):
    x=confirmation; real=gmail_browser_service.stage_gmail_batch_translated_docx
    monkeypatch.setattr(gmail_browser_service,"stage_gmail_batch_translated_docx",lambda **_: (_ for _ in ()).throw(OSError("fictional disk failure")))
    with pytest.raises(OSError):x.submit()
    frozen=x.case.manager.state(x.case.job.job_id)["frozen"]
    assert frozen and not x.session.confirmed_items
    monkeypatch.setattr(gmail_browser_service,"stage_gmail_batch_translated_docx",real)
    assert x.submit()["status"] == "ok"
    assert x.case.manager.state(x.case.job.job_id)["frozen"] == frozen


def test_unowned_legacy_row_edit_still_uses_existing_migration(tmp_path, monkeypatch):
    database=tmp_path/"legacy.sqlite"
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE job_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, completed_at TEXT NOT NULL, case_number TEXT, entity TEXT, city TEXT, lang TEXT, pages INTEGER, word_count INTEGER, rate_per_word REAL, expected_total REAL, amount_paid REAL, api_cost REAL, profit REAL)")
        conn.execute("INSERT INTO job_runs (completed_at, case_number, entity, city, lang, pages, word_count, rate_per_word, expected_total, amount_paid, api_cost, profit) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("2026-02-11T10:30:00","FICTIONAL-LEGACY","Fictional court","Fictional city","EN",1,100,.08,8,0,1,7))
    monkeypatch.setattr(translation_service,"build_translation_capability_flags",lambda **_: {})
    seed=completion_seed(tmp_path/"not-needed-for-historical-edit.docx")
    result=translation_service.save_translation_row(settings_path=tmp_path/"settings.json",job_log_db_path=database,
        form_values={**seed,"word_count":125,"expected_total":10},seed_payload=seed,row_id=1)
    assert result["saved_result"]["row_id"] == 1
    with sqlite3.connect(database) as conn:
        assert {"run_id","target_lang"} <= {row[1] for row in conn.execute("PRAGMA table_info(job_runs)")}
        assert conn.execute("SELECT word_count, profit FROM job_runs WHERE id=1").fetchone() == (125,7)
