"""Browser bridge ownership and genuine synthetic reviewed job integration."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import threading

import pytest

from legalpdf_translate import browser_source_review as bridge_module, translation_service as jobs_module, workflow as workflow_module
from legalpdf_translate.browser_source_review import BrowserSourceReviewManager, BrowserSourceReviewError
from legalpdf_translate.openai_client import OpenAIResponsesClient
from legalpdf_translate.translation_service import TranslationJobManager, build_translation_config
from legalpdf_translate.types import OcrMode
from tests.test_ordinary_source_review_service import (
    local_only, local_pass, config_case, explicit_decision, sdk_client,
)


def bridge_case(tmp_path, monkeypatch, *, settings_present=True, **options):
    local_pass(monkeypatch)
    config = config_case(tmp_path)
    settings = tmp_path / "settings.json"
    if settings_present:
        settings.write_text('{"page_breaks":false,"ocr_mode":"auto","ocr_engine":"local_then_api"}', encoding="utf-8")
    jobs = TranslationJobManager()
    bridge = BrowserSourceReviewManager(jobs)
    owner = {"runtime_mode": "shadow", "workspace_id": "workspace-1"}
    view = bridge.prepare(**owner, config=replace(config, **options), settings_path=settings)
    return SimpleNamespace(config=config, settings=settings, jobs=jobs, bridge=bridge, owner=owner, view=view)


def submit(c):
    view = c.view
    view = c.bridge.save_page(**c.owner, review_id=view["review_id"], expected_generation=view["generation"],
        page_number=1, decision=explicit_decision(view["pages"][0]))
    return c.bridge.submit(**c.owner, review_id=view["review_id"], expected_generation=view["generation"],
        reviewer="Explicit fictional operator", accept_source=True)


def capture_jobs(monkeypatch):
    targets = []
    class Thread:
        def __init__(self, *, target, name, daemon):
            targets.append(target)
        def start(self):
            pass
    # Replace this module's dependency, not global threading.Thread used by
    # the real Workflow's worker pool.
    monkeypatch.setattr(jobs_module, "threading", SimpleNamespace(RLock=threading.RLock, Thread=Thread))
    return targets


def test_public_form_wrapper_keeps_saved_policy_and_existing_parser(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"Fictional")
    output = tmp_path / "out"
    output.mkdir()
    settings = tmp_path / "settings.json"
    settings.write_text('{"page_breaks":false,"ocr_mode":"off","ocr_engine":"api"}', encoding="utf-8")
    form = {"source_path": str(source), "output_dir": str(output), "target_lang": "EN"}
    config = build_translation_config(form_values=form, settings_path=settings)
    assert config == jobs_module._build_config_from_form(form_values=form, settings_path=settings)
    assert config.page_breaks is False and config.ocr_mode == OcrMode.OFF and config.ocr_engine.value == "api"


@pytest.mark.parametrize("kind", ["directory", "dangling_link"])
def test_existing_invalid_settings_are_not_treated_as_fresh_defaults(tmp_path, monkeypatch, kind):
    config = config_case(tmp_path)
    settings = tmp_path / "settings.json"
    if kind == "directory":
        settings.mkdir()
    else:
        try:
            settings.symlink_to(tmp_path / "missing-target.json")
        except OSError:
            pytest.skip("This environment cannot create symbolic links.")
    monkeypatch.setattr(bridge_module, "OrdinarySourceReviewService",
        lambda *_: pytest.fail("Invalid settings must fail before source acquisition."))
    jobs = TranslationJobManager()
    bridge = BrowserSourceReviewManager(jobs)
    with pytest.raises(BrowserSourceReviewError, match="settings_unavailable"):
        bridge.prepare(runtime_mode="shadow", workspace_id="workspace-1", config=config, settings_path=settings)
    assert not bridge._reviews and not jobs.list_jobs()
    assert settings.is_dir() if kind == "directory" else settings.is_symlink()


def test_views_are_json_safe_without_evidence_paths_or_bytes_and_images_are_owned(tmp_path, monkeypatch):
    c = bridge_case(tmp_path, monkeypatch)
    view = c.view
    assert view["status"] == "draft" and view["pages"][0]["decision"] is None
    encoded = json.dumps(view)
    assert "image_bytes" not in encoded and str(tmp_path) not in encoded and "draft_id" not in view
    assert c.bridge.image(**c.owner, review_id=view["review_id"], page_number=1).startswith(b"\x89PNG")
    for owner in ({"runtime_mode": "live", "workspace_id": "workspace-1"},
                  {"runtime_mode": "shadow", "workspace_id": "workspace-2"}):
        with pytest.raises(BrowserSourceReviewError, match="unavailable"):
            c.bridge.read(**owner, review_id=view["review_id"])
        with pytest.raises(BrowserSourceReviewError, match="unavailable"):
            c.bridge.image(**owner, review_id=view["review_id"], page_number=1)
        with pytest.raises(BrowserSourceReviewError, match="unavailable"):
            c.bridge.submit(**owner, review_id=view["review_id"], expected_generation=1,
                reviewer="operator", accept_source=True)


def test_scope_and_explicit_submission_selection_are_required(tmp_path, monkeypatch):
    c = bridge_case(tmp_path, monkeypatch)
    with pytest.raises(BrowserSourceReviewError, match="owner_required"):
        c.bridge.read(runtime_mode="", workspace_id="workspace-1", review_id=c.view["review_id"])
    with pytest.raises(BrowserSourceReviewError, match="owner_required"):
        c.bridge.read(runtime_mode="shadow", workspace_id="", review_id=c.view["review_id"])
    with pytest.raises(BrowserSourceReviewError, match="revision_unavailable"):
        c.bridge.start_translate(**c.owner, review_id=c.view["review_id"], revision_id="0" * 32, operation_nonce="1" * 32)
    with pytest.raises(BrowserSourceReviewError, match="submit_failed"):
        c.bridge.submit(**c.owner, review_id=c.view["review_id"], expected_generation=1,
            reviewer="operator", accept_source=True)
    assert c.jobs.list_jobs() == []
    with pytest.raises(ValueError, match="context_invalid"):
        c.jobs.start_reviewed_translate(**c.owner, config=c.config, settings_path=c.settings,
            reviewed_source_context=None, reviewed_source_loader=lambda: None)


def test_declines_keep_original_saved_ocr_policy(tmp_path, monkeypatch):
    c = bridge_case(tmp_path, monkeypatch, ocr_mode=OcrMode.OFF)
    assert c.view == {"status": "declined", "notice_codes": ["source_review_ocr_disabled"]}
    assert c.jobs.list_jobs() == []


def test_bridge_real_job_reloads_exact_context_and_resume_preserves_it(tmp_path, monkeypatch):
    c = bridge_case(tmp_path, monkeypatch)
    revision = submit(c)
    targets = capture_jobs(monkeypatch)
    real_workflow = workflow_module.TranslationWorkflow
    workflows, calls = [], []
    class FailedSDK:
        base_url = "https://api.openai.com/v1/"
        @property
        def responses(self):
            return self
        def create(self, **request):
            calls.append(request)
            raise RuntimeError("Fictional failed transport")
    def construct(**kwargs):
        assert kwargs["client"] is None
        assert kwargs["reviewed_source_context"].revision_id == revision["revision_id"]
        kwargs["client"] = (OpenAIResponsesClient(sdk_client=FailedSDK(), pre_call_jitter_seconds=0)
                            if not workflows else sdk_client(calls))
        instance = real_workflow(**kwargs)
        workflows.append(instance)
        return instance
    monkeypatch.setattr(workflow_module, "TranslationWorkflow", construct)
    monkeypatch.setattr(jobs_module, "OpenAIResponsesClient", lambda **_: pytest.fail("Reviewed jobs defer client creation to verified Workflow"))
    monkeypatch.setattr(jobs_module, "_translation_result_payload", lambda **kw: {
        "artifacts": {"run_dir": str(kw["summary"].run_dir)}})
    first = c.bridge.start_translate(**c.owner, review_id=c.view["review_id"], revision_id=revision["revision_id"], operation_nonce="1" * 32)
    assert first["status"] == "queued" and not calls
    assert "reviewed_source_context" not in json.dumps(first)
    targets.pop(0)()
    first = c.jobs.get_job(first["job_id"])
    assert first["status"] == "failed" and len(calls) == 1
    with pytest.raises(BrowserSourceReviewError, match="unavailable"):
        c.bridge.resume(runtime_mode="live", workspace_id="workspace-1", review_id=c.view["review_id"],
            job_id=first["job_id"], revision_id=revision["revision_id"])
    second = c.bridge.resume(**c.owner, review_id=c.view["review_id"], job_id=first["job_id"],
        revision_id=revision["revision_id"])
    targets.pop(0)()
    assert c.jobs.get_job(second["job_id"])["status"] == "completed"
    assert len(calls) == 2 and workflows[0]._reviewed_source_context is not workflows[1]._reviewed_source_context
    assert workflows[0]._reviewed_source_context.identity == workflows[1]._reviewed_source_context.identity
    assert list(workflows[1]._last_state.pages.values())[0]["structured_commit"]
    assert c.config.page_breaks is False


def test_queued_revision_tamper_fails_before_client_or_workflow(tmp_path, monkeypatch):
    c = bridge_case(tmp_path, monkeypatch)
    revision = submit(c)
    targets = capture_jobs(monkeypatch)
    job = c.bridge.start_translate(**c.owner, review_id=c.view["review_id"], revision_id=revision["revision_id"], operation_nonce="1" * 32)
    c.config.pdf_path.write_bytes(b"Source changed after queueing")
    monkeypatch.setattr(jobs_module, "OpenAIResponsesClient", lambda **_: pytest.fail("No client"))
    monkeypatch.setattr(workflow_module, "TranslationWorkflow", lambda **_: pytest.fail("No Workflow before verified revision reload"))
    targets.pop(0)()
    failed = c.jobs.get_job(job["job_id"])
    assert failed["status"] == "failed"
    assert failed["diagnostics"]["error"] == "ordinary_source_review_job_failed"
    assert str(tmp_path) not in json.dumps(failed["diagnostics"])


def test_explicit_restore_uses_original_config_and_exact_revision_without_reacquisition(tmp_path, monkeypatch):
    c = bridge_case(tmp_path, monkeypatch)
    revision = submit(c)
    from legalpdf_translate import ocr_engine
    monkeypatch.setattr(ocr_engine.LocalTesseractEngine, "ocr_image", lambda *_a, **_kw: pytest.fail("Restore must not reacquire OCR"))
    restarted = BrowserSourceReviewManager(c.jobs)
    with pytest.raises(BrowserSourceReviewError, match="unavailable"):
        restarted.read(**c.owner, review_id=c.view["review_id"])
    restored = restarted.restore(**c.owner, config=c.config, settings_path=c.settings, revision_id=revision["revision_id"])
    assert restored["revision_id"] == revision["revision_id"] and restored["status"] == "restored"
    targets = capture_jobs(monkeypatch)
    job = restarted.start_translate(**c.owner, review_id=restored["review_id"], revision_id=revision["revision_id"], operation_nonce="1" * 32)
    assert job["config"]["resume"] is True and len(targets) == 1


def test_existing_resume_and_rebuild_keep_context_and_reject_changed_settings_owner(tmp_path, monkeypatch):
    c = bridge_case(tmp_path, monkeypatch)
    revision = submit(c)
    capture_jobs(monkeypatch)
    first = c.bridge.start_translate(**c.owner, review_id=c.view["review_id"], revision_id=revision["revision_id"], operation_nonce="1" * 32)
    record = c.jobs._jobs[first["job_id"]]
    record.status = "failed"
    other_settings = tmp_path / "other.json"
    other_settings.write_text("{}")
    for action in (c.jobs.resume_job, c.jobs.rebuild_job):
        with pytest.raises(ValueError, match="owner_changed"):
            action(job_id=record.job_id, settings_path=other_settings)
        job = action(job_id=record.job_id, settings_path=c.settings)
        restored = c.jobs._jobs[job["job_id"]]
        assert restored._reviewed_source_context is record._reviewed_source_context
        assert restored._reviewed_source_loader is record._reviewed_source_loader
        restored.status = "failed"  # No worker is executed in this contract-only test.


def capture_lazy_client(monkeypatch):
    """Observe Workflow's actual lazy constructor; replace only its SDK boundary."""
    instances, calls = [], []

    def create(**request):
        calls.append(request)
        prompt, _ = json.JSONDecoder().raw_decode(request["input"][0]["content"][0]["text"])
        # One explicit source action can retain several original OCR lines.
        # Preserve both fictional lines when the UI groups their blocks.
        blocks = [{"id": row["id"], "text": "\n".join(
            "Case 121/26" if "Processo" in line else "Article 42"
            for line in row["text"].splitlines())} for row in prompt["blocks"]]
        return SimpleNamespace(id=f"lazy-synthetic-{len(calls)}", status="completed", model=request["model"],
            output_text=json.dumps({"blocks": blocks}), output=[],
            usage={"input_tokens": 12, "output_tokens": 8, "total_tokens": 20})

    class ObservedClient(OpenAIResponsesClient):
        def __init__(self, **kwargs):
            sdk = SimpleNamespace(base_url="https://api.openai.com/v1/", responses=SimpleNamespace(create=create))
            super().__init__(sdk_client=sdk, pre_call_jitter_seconds=0, **kwargs)
            instances.append(self)

    monkeypatch.setattr(workflow_module, "OpenAIResponsesClient", ObservedClient)
    monkeypatch.setattr(jobs_module, "OpenAIResponsesClient", lambda **_: pytest.fail("No eager reviewed client"))
    from legalpdf_translate import openai_client
    monkeypatch.setattr(openai_client, "resolve_openai_key_with_source", lambda *_a, **_kw: pytest.fail("No ambient credentials"))
    # Result enrichment is outside this constructor/dispatch regression.
    monkeypatch.setattr(jobs_module, "_translation_result_payload", lambda **kw: {
        "artifacts": {"run_dir": str(kw["summary"].run_dir)}})
    return instances, calls


def test_reviewed_job_actual_lazy_client_keeps_saved_transport_policy(tmp_path, monkeypatch):
    c = bridge_case(tmp_path, monkeypatch)
    settings = json.loads(c.settings.read_text(encoding="utf-8"))
    settings.update(perf_max_transport_retries=2, perf_backoff_cap_seconds=3.5)
    c.settings.write_text(json.dumps(settings), encoding="utf-8")
    revision = submit(c)
    targets = capture_jobs(monkeypatch)
    instances, calls = capture_lazy_client(monkeypatch)
    job = c.bridge.start_translate(**c.owner, review_id=c.view["review_id"], revision_id=revision["revision_id"], operation_nonce="1" * 32)
    assert not instances and not calls
    targets.pop(0)()  # Real Workflow receives client=None and constructs the client itself.
    completed = c.jobs.get_job(job["job_id"])
    assert completed["status"] == "completed", completed["diagnostics"]
    assert len(instances) == 1 and len(calls) == 1
    assert instances[0]._max_transport_retries == 2
    assert instances[0]._backoff_cap_seconds == 3.5
    run_dir = Path(completed["artifacts"]["run_dir"])
    state = json.loads((run_dir / "run_state.json").read_bytes())
    assert state["pages"]["1"]["structured_commit"]
    assert state["settings"]["ordinary_source_review"]["revision_id"] == revision["revision_id"]
    assert (run_dir / "pages/page_0001.commit.json").is_file()


@pytest.mark.parametrize("tamper_phase", ["queued", "before_authentication"])
def test_reviewed_job_tamper_prevents_actual_lazy_client(tmp_path, monkeypatch, tamper_phase):
    c = bridge_case(tmp_path, monkeypatch)
    revision = submit(c)
    targets = capture_jobs(monkeypatch)
    instances, calls = capture_lazy_client(monkeypatch)
    job = c.bridge.start_translate(**c.owner, review_id=c.view["review_id"], revision_id=revision["revision_id"], operation_nonce="1" * 32)
    mutations = []

    def mutate_source():
        mutations.append(tamper_phase)
        c.config.pdf_path.write_bytes(b"Fictional source changed before lazy client construction")

    if tamper_phase == "queued":
        mutate_source()
    else:
        # The reviewed Workflow loads the environment only after its initial
        # source verification, then rechecks evidence before lazy authentication.
        monkeypatch.setattr(workflow_module, "load_environment", mutate_source)
    targets.pop(0)()
    failed = c.jobs.get_job(job["job_id"])
    assert mutations == [tamper_phase]
    assert failed["status"] == "failed"
    assert failed["diagnostics"]["error"] == "ordinary_source_review_job_failed"
    assert not instances and not calls


def test_submitted_read_recovers_only_this_handles_revision_after_lost_response(tmp_path, monkeypatch):
    c = bridge_case(tmp_path, monkeypatch)
    submitted = submit(c)  # Simulate losing this response before the UI receives it.
    recovered = c.bridge.read(**c.owner, review_id=c.view["review_id"])
    assert recovered["submitted"] is True
    assert recovered["revision_ids"] == [submitted["revision_id"]]
    assert "revision_id" not in recovered  # Read exposes choices; it does not select one.
    assert c.jobs.list_jobs() == []
    with pytest.raises(BrowserSourceReviewError, match="submit_failed"):
        c.bridge.submit(**c.owner, review_id=c.view["review_id"], expected_generation=recovered["generation"],
            reviewer="Fictional operator", accept_source=True)

    other = c.bridge.prepare(**c.owner, config=c.config, settings_path=c.settings)
    other_read = c.bridge.read(**c.owner, review_id=other["review_id"])
    assert other["review_id"] != c.view["review_id"]
    assert other_read["submitted"] is False and "revision_ids" not in other_read
    with pytest.raises(BrowserSourceReviewError, match="revision_unavailable"):
        c.bridge.start_translate(**c.owner, review_id=other["review_id"], revision_id=submitted["revision_id"], operation_nonce="1" * 32)
    with pytest.raises(BrowserSourceReviewError, match="unavailable"):
        c.bridge.read(runtime_mode="shadow", workspace_id="another-workspace", review_id=c.view["review_id"])
    assert c.jobs.list_jobs() == []


def test_reviewed_translate_nonce_returns_one_job_and_owned_recovery_view(tmp_path, monkeypatch):
    c = bridge_case(tmp_path, monkeypatch)
    revision = submit(c)
    targets = capture_jobs(monkeypatch)
    arguments = {**c.owner, "review_id": c.view["review_id"], "revision_id": revision["revision_id"],
                 "operation_nonce": "a" * 32}
    first = c.bridge.start_translate(**arguments)
    assert len(targets) == 1
    entry = c.bridge._entry("shadow", "workspace-1", c.view["review_id"])
    # Recovery must work while source-service operations cannot take the run slot.
    monkeypatch.setattr(entry.service, "read", lambda *_a, **_kw: pytest.fail("No source reread during operation recovery"))
    monkeypatch.setattr(entry.service, "load_context", lambda *_a, **_kw: pytest.fail("No repeated dispatch preflight"))
    second = c.bridge.start_translate(**arguments)
    assert second["job_id"] == first["job_id"] and len(targets) == 1
    recovered = c.bridge.read(**c.owner, review_id=c.view["review_id"])
    assert recovered["translation_operations"] == [{"operation_nonce": "a" * 32,
        "revision_id": revision["revision_id"], "status": "started", "job_id": first["job_id"]}]
    assert recovered["translation_jobs"] == [{"job_id": first["job_id"], "revision_id": revision["revision_id"]}]
    with pytest.raises(BrowserSourceReviewError, match="operation_revision_changed"):
        c.bridge.start_translate(**{**arguments, "revision_id": "b" * 32})
    with pytest.raises(BrowserSourceReviewError, match="unavailable"):
        c.bridge.start_translate(**{**arguments, "workspace_id": "other-workspace"})
    assert len(targets) == 1


def test_reviewed_translate_uncertain_dispatch_retains_nonce_without_redispatch(tmp_path, monkeypatch):
    c = bridge_case(tmp_path, monkeypatch)
    revision = submit(c)
    targets = capture_jobs(monkeypatch)
    real_start = c.jobs.start_reviewed_translate
    attempted = []

    def start_then_raise(**kwargs):
        attempted.append(real_start(**kwargs)["job_id"])
        raise RuntimeError("Fictional private content that must not enter recovery diagnostics")

    monkeypatch.setattr(c.jobs, "start_reviewed_translate", start_then_raise)
    arguments = {**c.owner, "review_id": c.view["review_id"], "revision_id": revision["revision_id"],
                 "operation_nonce": "c" * 32}
    with pytest.raises(BrowserSourceReviewError, match="translation_start_failed"):
        c.bridge.start_translate(**arguments)
    with pytest.raises(BrowserSourceReviewError, match="operation_outcome_unknown"):
        c.bridge.start_translate(**arguments)
    assert len(attempted) == len(targets) == 1
    recovered = c.bridge.read(**c.owner, review_id=c.view["review_id"])
    assert recovered["translation_operations"] == [{"operation_nonce": "c" * 32,
        "revision_id": revision["revision_id"], "status": "unknown", "job_id": None}]
    assert recovered["translation_jobs"] == []
    assert "private content" not in json.dumps(recovered)


@pytest.mark.parametrize("nonce", [None, "", "../review", "d" * 129, "D" * 32])
def test_reviewed_translate_requires_bounded_explicit_nonce(tmp_path, monkeypatch, nonce):
    c = bridge_case(tmp_path, monkeypatch)
    revision = submit(c)
    targets = capture_jobs(monkeypatch)
    with pytest.raises(BrowserSourceReviewError, match="invalid_id"):
        c.bridge.start_translate(**c.owner, review_id=c.view["review_id"], revision_id=revision["revision_id"],
            operation_nonce=nonce)
    assert targets == [] and c.jobs.list_jobs() == []


def test_same_review_image_read_does_not_fail_queued_context_loader(tmp_path, monkeypatch):
    c = bridge_case(tmp_path, monkeypatch)
    revision = submit(c)
    targets = capture_jobs(monkeypatch)
    entry = c.bridge._entry("shadow", "workspace-1", c.view["review_id"])
    slot_held, image_release, loader_stage = (threading.Event() for _ in range(3))
    trace, image_results, workflow_contexts = [], [], []
    image_name, worker_name = "synthetic-image-request", "synthetic-job-loader"
    original_lock = entry.lock

    class ObservedLock:
        def __enter__(self):
            if threading.current_thread().name == worker_name:
                trace.append("background_loader_waiting_for_same_review_lock")
                loader_stage.set()
            return original_lock.__enter__()

        def __exit__(self, *args):
            return original_lock.__exit__(*args)

    entry.lock = ObservedLock()
    original_draft = entry.service._draft

    def held_image_draft(*args, **kwargs):
        # Production service.read() has already acquired its genuine run slot.
        if threading.current_thread().name == image_name:
            trace.append("image_service_read_holds_real_run_slot")
            slot_held.set()
            assert image_release.wait(10), "Coordinator did not release synthetic image read"
        return original_draft(*args, **kwargs)

    monkeypatch.setattr(entry.service, "_draft", held_image_draft)
    original_load = entry.service.load_context

    def observed_load(*args, **kwargs):
        try:
            return original_load(*args, **kwargs)
        except Exception as exc:
            if threading.current_thread().name == worker_name:
                trace.append({"background_exception_type": type(exc).__name__, "message": str(exc)})
            raise
        finally:
            if threading.current_thread().name == worker_name:
                loader_stage.set()

    monkeypatch.setattr(entry.service, "load_context", observed_load)

    def image_request():
        try:
            image_results.append(c.bridge.image(**c.owner, review_id=c.view["review_id"], page_number=1))
        except BaseException as exc:
            image_results.append(exc)

    original_start = c.jobs.start_reviewed_translate
    image_thread = threading.Thread(target=image_request, name=image_name)

    def queue_and_schedule_image(**kwargs):
        job = original_start(**kwargs)
        # start_translate still holds entry.lock. Image waits until it releases.
        assert original_lock._is_owned()
        trace.append("image_scheduled_while_start_owns_review_lock")
        image_thread.start()
        return job

    monkeypatch.setattr(c.jobs, "start_reviewed_translate", queue_and_schedule_image)

    class NoProviderWorkflow:
        def __init__(self, **kwargs):
            assert kwargs["client"] is None
            assert kwargs["reviewed_source_context"].revision_id == revision["revision_id"]
            workflow_contexts.append(kwargs["reviewed_source_context"].identity)

        def run(self, config):
            return SimpleNamespace(success=True, error=None)

    monkeypatch.setattr(workflow_module, "TranslationWorkflow", NoProviderWorkflow)
    monkeypatch.setattr(jobs_module, "_translation_result_payload", lambda **kwargs: {})
    arguments = {**c.owner, "review_id": c.view["review_id"], "revision_id": revision["revision_id"], "operation_nonce": "a" * 32}
    job = c.bridge.start_translate(**arguments)
    worker = threading.Thread(target=targets.pop(0), name=worker_name)
    try:
        assert slot_held.wait(10), "Image did not acquire real source-read slot"
        worker.start()
        assert loader_stage.wait(10), "Loader neither contended nor reached the source loader"
    finally:
        image_release.set()
        image_thread.join(10)
        if worker.ident is not None:
            worker.join(10)
    assert not image_thread.is_alive() and not worker.is_alive()
    assert len(image_results) == 1 and isinstance(image_results[0], bytes)
    observed = c.jobs.get_job(job["job_id"])
    assert observed["status"] == "completed", (trace, observed["diagnostics"])
    assert len(workflow_contexts) == 1
    assert c.bridge.start_translate(**arguments)["job_id"] == job["job_id"]
    assert len(c.jobs.list_jobs()) == 1 and not targets


def test_queued_context_loader_still_rejects_external_run_slot_without_retry(tmp_path, monkeypatch):
    from legalpdf_translate.run_workspace_lock import run_workspace_slot

    c = bridge_case(tmp_path, monkeypatch)
    revision = submit(c)
    targets = capture_jobs(monkeypatch)
    entry = c.bridge._entry("shadow", "workspace-1", c.view["review_id"])
    arguments = {**c.owner, "review_id": c.view["review_id"], "revision_id": revision["revision_id"],
                 "operation_nonce": "b" * 32}
    job = c.bridge.start_translate(**arguments)
    original_load = entry.service.load_context
    attempts = []

    def observed_load(selected):
        attempts.append(selected)
        return original_load(selected)

    monkeypatch.setattr(entry.service, "load_context", observed_load)
    monkeypatch.setattr(workflow_module, "TranslationWorkflow",
                        lambda **_: pytest.fail("External run-slot conflict must fail before Workflow"))
    held, release, finished = (threading.Event() for _ in range(3))

    def external_operation():
        with run_workspace_slot(entry.service.run_dir):
            held.set()
            assert release.wait(10), "Coordinator did not release external synthetic owner"

    def queued_job():
        try:
            targets.pop(0)()
        finally:
            finished.set()

    external = threading.Thread(target=external_operation)
    worker = threading.Thread(target=queued_job)
    external.start()
    try:
        assert held.wait(10)
        worker.start()
        # The unrelated owner's slot remains held. No retry or wait is added.
        assert finished.wait(5), "Loader waited for an unrelated run-slot owner"
        failed = c.jobs.get_job(job["job_id"])
        assert failed["status"] == "failed"
        assert failed["diagnostics"] == {"error": "ordinary_source_review_job_failed", "kind": "translate"}
        assert attempts == [revision["revision_id"]]
        assert c.bridge.start_translate(**arguments)["job_id"] == job["job_id"]
        assert attempts == [revision["revision_id"]] and not targets
    finally:
        release.set()
        external.join(10)
        if worker.ident is not None:
            worker.join(10)
    assert not external.is_alive() and not worker.is_alive()
