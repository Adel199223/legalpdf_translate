from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import legalpdf_translate.workflow as workflow_module
from legalpdf_translate.ocr_engine import OcrResult
from legalpdf_translate.openai_client import (
    ApiCallError,
    ApiCallResult,
    OpenAICredentialSourceInfo,
    TranslationAuthTestResult,
)
from legalpdf_translate.types import ImageMode, OcrEnginePolicy, OcrMode, ReasoningEffort, RunConfig, TargetLang
from legalpdf_translate.workflow import (
    TranslationWorkflow,
    _derive_cancel_halt_reason,
    classify_extracted_text_quality,
)


class _FakeClient:
    def create_page_response(self, **kwargs) -> ApiCallResult:  # noqa: ANN003
        _ = kwargs
        return ApiCallResult(
            raw_output="```\nTranslated output\n```",
            usage={"input_tokens": 10, "output_tokens": 4, "reasoning_tokens": 1, "total_tokens": 15},
            response_id="resp-test",
        )


class _CapturingClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create_page_response(self, **kwargs) -> ApiCallResult:  # noqa: ANN003
        self.calls.append(dict(kwargs))
        return ApiCallResult(
            raw_output="```\nTranslated output\n```",
            usage={"input_tokens": 10, "output_tokens": 4, "reasoning_tokens": 1, "total_tokens": 15},
            response_id="resp-test",
        )


class _FailingClient:
    def create_page_response(self, **kwargs) -> ApiCallResult:  # noqa: ANN003
        _ = kwargs
        raise ApiCallError(
            message="timeout",
            status_code=None,
            exception_class="APITimeoutError",
            transport_retries_count=2,
            last_backoff_seconds=0.0,
            total_backoff_seconds=1.5,
            rate_limit_hit=False,
        )


class _UnauthorizedPreflightClient:
    def run_translation_auth_test(self) -> TranslationAuthTestResult:
        return TranslationAuthTestResult(
            ok=False,
            status="unauthorized",
            message="OpenAI authentication failed.",
            credential_source=OpenAICredentialSourceInfo(kind="stored", name=""),
            status_code=401,
            exception_class="AuthenticationError",
        )

    def create_page_response(self, **kwargs) -> ApiCallResult:  # noqa: ANN003
        _ = kwargs
        raise AssertionError("create_page_response should not run when auth preflight fails")


class _AuthFailingPageClient:
    def run_translation_auth_test(self) -> TranslationAuthTestResult:
        return TranslationAuthTestResult(
            ok=True,
            status="ok",
            message="OpenAI translation auth test passed.",
            credential_source=OpenAICredentialSourceInfo(kind="stored", name=""),
            latency_ms=5,
        )

    def create_page_response(self, **kwargs) -> ApiCallResult:  # noqa: ANN003
        _ = kwargs
        raise ApiCallError(
            message="AuthenticationError: invalid key",
            status_code=401,
            exception_class="AuthenticationError",
            transport_retries_count=0,
            last_backoff_seconds=0.0,
            total_backoff_seconds=0.0,
            rate_limit_hit=False,
        )


def _ordered_text_result(text: str) -> SimpleNamespace:
    ratio = float(text.count("\n")) / float(max(1, len(text)))
    return SimpleNamespace(
        text=text,
        newline_to_char_ratio=ratio,
        block_count=1,
        header_blocks_count=0,
        footer_blocks_count=0,
        barcode_blocks_count=0,
        body_blocks_count=1,
        two_column_detected=False,
        extraction_failed=False,
        fragmented=False,
    )


def _config(pdf: Path, outdir: Path, *, ocr_engine: OcrEnginePolicy, max_pages: int) -> RunConfig:
    return RunConfig(
        pdf_path=pdf,
        output_dir=outdir,
        target_lang=TargetLang.EN,
        effort=ReasoningEffort.HIGH,
        image_mode=ImageMode.OFF,
        max_pages=max_pages,
        workers=2,
        resume=False,
        page_breaks=True,
        keep_intermediates=True,
        ocr_mode=OcrMode.AUTO,
        ocr_engine=ocr_engine,
        diagnostics_admin_mode=True,
    )


def _events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _helpful_text() -> str:
    repeated = ["Header Repeat"] * 12
    body = [f"Body line {idx:02d}" for idx in range(18)]
    return "\n".join(repeated + body)


def test_classify_extracted_text_quality_direct_text_ok() -> None:
    text = (
        "This agreement is made on the date set forth below between the parties.\n"
        "Each party agrees to comply with the obligations listed in Sections 1 through 8.\n"
        "Notices must be delivered in writing to the addresses listed in this agreement."
    )
    stats = classify_extracted_text_quality(text)
    assert stats["ocr_required"] is False
    assert stats["ocr_helpful"] is False
    assert list(stats["signals"]) == []


def test_classify_extracted_text_quality_required_for_empty_or_garbage() -> None:
    stats_empty = classify_extracted_text_quality("")
    assert stats_empty["ocr_required"] is True

    garbage = "\uFFFD\uFFFD\uFFFD\uFFFD\uFFFD\uFFFD\uFFFD"
    stats_garbage = classify_extracted_text_quality(garbage)
    assert stats_garbage["ocr_required"] is True


def test_classify_extracted_text_quality_helpful_requires_two_signals() -> None:
    stats = classify_extracted_text_quality(_helpful_text())
    assert stats["ocr_required"] is False
    assert stats["ocr_helpful"] is True
    assert len(list(stats["signals"])) >= 2


def test_classify_extracted_text_quality_address_list_exemption() -> None:
    text = "\n".join(
        [
            "John Doe",
            "100 Main Street",
            "Suite 120",
            "Springfield, CA 90210",
            "Attn: Legal Department",
            "Ref: Contract 4452",
            "1. Services",
            "2. Fees",
            "3. Term",
            "4. Notices",
            "5. Governing Law",
            "Header",
        ]
    )
    stats = classify_extracted_text_quality(text)
    assert stats["ocr_required"] is False
    assert stats["ocr_helpful"] is False


def test_auto_mode_direct_text_skips_lazy_ocr_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)
    monkeypatch.setattr(workflow_module, "load_system_instructions", lambda _lang: "SYS")
    monkeypatch.setattr(
        workflow_module,
        "extract_ordered_page_text",
        lambda _pdf, _idx: _ordered_text_result(
            "This page has enough extracted text to remain on the direct-text route in auto mode."
        ),
    )
    monkeypatch.setattr(workflow_module, "should_include_image", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        workflow_module,
        "ocr_pdf_page_text",
        lambda *_args, **_kwargs: OcrResult(text="", engine="none", failed_reason="unused", chars=0),
    )

    build_calls = {"count": 0}

    def _build_should_not_run(_cfg):  # type: ignore[no-untyped-def]
        build_calls["count"] += 1
        raise AssertionError("build_ocr_engine should not be called for direct-text auto pages")

    monkeypatch.setattr(workflow_module, "build_ocr_engine", _build_should_not_run)

    summary = TranslationWorkflow(client=_FakeClient()).run(
        _config(pdf, outdir, ocr_engine=OcrEnginePolicy.LOCAL_THEN_API, max_pages=1)
    )
    assert summary.success is True
    assert summary.run_summary_path is not None
    summary_payload = json.loads(summary.run_summary_path.read_text(encoding="utf-8"))
    assert build_calls["count"] == 0
    assert summary_payload["pipeline"]["ocr_requested"] is False
    assert summary_payload["pipeline"]["ocr_preflight_checked"] is False

    event_types = {str(item.get("event_type", "")) for item in _events(summary.run_dir / "run_events.jsonl")}
    assert "ocr_preflight_checked" not in event_types
    assert "ocr_required_but_unavailable" not in event_types
    assert "ocr_helpful_but_unavailable" not in event_types


@pytest.mark.parametrize("engine_policy", [OcrEnginePolicy.API, OcrEnginePolicy.LOCAL_THEN_API])
def test_helpful_route_is_local_only_even_when_policy_allows_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    engine_policy: OcrEnginePolicy,
) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)
    monkeypatch.setattr(workflow_module, "load_system_instructions", lambda _lang: "SYS")
    monkeypatch.setattr(workflow_module, "extract_ordered_page_text", lambda _pdf, _idx: _ordered_text_result(_helpful_text()))
    monkeypatch.setattr(workflow_module, "should_include_image", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        workflow_module,
        "ocr_pdf_page_text",
        lambda *_args, **_kwargs: OcrResult(text="OCR text", engine="local", failed_reason=None, chars=8),
    )

    captured_policies: list[str] = []

    class _FakeEngine:
        def ocr_image(self, image_bytes: bytes, lang_hint: str | None = None) -> OcrResult:
            _ = image_bytes, lang_hint
            return OcrResult(text="OCR text", engine="local", failed_reason=None, chars=8)

    def _build_engine(cfg):  # type: ignore[no-untyped-def]
        captured_policies.append(str(cfg.policy.value))
        return _FakeEngine()

    monkeypatch.setattr(workflow_module, "build_ocr_engine", _build_engine)

    summary = TranslationWorkflow(client=_FakeClient()).run(_config(pdf, outdir, ocr_engine=engine_policy, max_pages=1))
    assert summary.success is True
    assert captured_policies == ["local"]

    run_state = json.loads((summary.run_dir / "run_state.json").read_text(encoding="utf-8"))
    page = run_state["pages"]["1"]
    assert page["ocr_request_reason"] == "helpful"
    assert page["ocr_requested"] is True
    assert page["ocr_used"] is True
    assert page["source_route"] == "ocr"


def test_helpful_unavailable_falls_back_without_warning_and_required_build_cached_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 2)
    monkeypatch.setattr(workflow_module, "load_system_instructions", lambda _lang: "SYS")
    monkeypatch.setattr(
        workflow_module,
        "extract_ordered_page_text",
        lambda _pdf, _idx: _ordered_text_result(_helpful_text()),
    )
    monkeypatch.setattr(workflow_module, "should_include_image", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        workflow_module,
        "ocr_pdf_page_text",
        lambda *_args, **_kwargs: OcrResult(text="", engine="none", failed_reason="unused", chars=0),
    )

    calls = {"count": 0}

    def _missing_local(_cfg):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        raise RuntimeError("missing")

    monkeypatch.setattr(workflow_module, "build_ocr_engine", _missing_local)

    summary = TranslationWorkflow(client=_FakeClient()).run(
        _config(pdf, outdir, ocr_engine=OcrEnginePolicy.LOCAL_THEN_API, max_pages=2)
    )
    assert summary.success is True
    assert calls["count"] == 1
    assert summary.run_summary_path is not None
    summary_payload = json.loads(summary.run_summary_path.read_text(encoding="utf-8"))
    assert summary_payload["pipeline"]["ocr_requested_pages"] == 0
    assert summary_payload["pipeline"]["ocr_helpful_pages"] == 2
    assert summary_payload["pipeline"]["ocr_preflight_checked"] is True

    run_state = json.loads((summary.run_dir / "run_state.json").read_text(encoding="utf-8"))
    for page in run_state["pages"].values():
        assert page["ocr_request_reason"] == "helpful"
        assert page["ocr_requested"] is False
        assert page["ocr_used"] is False
        assert page["ocr_failed_reason"] == "helpful_unavailable"
        assert page["source_route"] == "direct_text"

    events = _events(summary.run_dir / "run_events.jsonl")
    event_types = [str(item.get("event_type", "")) for item in events]
    assert "ocr_preflight_checked" in event_types
    assert "ocr_helpful_but_unavailable" in event_types
    assert "ocr_required_but_unavailable" not in event_types
    for event in events:
        if str(event.get("event_type", "")) == "ocr_helpful_but_unavailable":
            assert event.get("warning") in (None, "")


def test_required_route_builds_policy_engine_once_for_multiple_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 2)
    monkeypatch.setattr(workflow_module, "load_system_instructions", lambda _lang: "SYS")
    monkeypatch.setattr(workflow_module, "extract_ordered_page_text", lambda _pdf, _idx: _ordered_text_result(""))
    monkeypatch.setattr(workflow_module, "should_include_image", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        workflow_module,
        "ocr_pdf_page_text",
        lambda *_args, **_kwargs: OcrResult(text="", engine="none", failed_reason="empty_result", chars=0),
    )

    calls = {"count": 0, "policies": []}

    class _FakeEngine:
        def ocr_image(self, image_bytes: bytes, lang_hint: str | None = None) -> OcrResult:
            _ = image_bytes, lang_hint
            return OcrResult(text="", engine="none", failed_reason="unused", chars=0)

    def _build_engine(cfg):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        calls["policies"].append(str(cfg.policy.value))
        return _FakeEngine()

    monkeypatch.setattr(workflow_module, "build_ocr_engine", _build_engine)

    summary = TranslationWorkflow(client=_FakeClient()).run(
        _config(pdf, outdir, ocr_engine=OcrEnginePolicy.LOCAL_THEN_API, max_pages=2)
    )
    assert summary.success is True
    assert calls["count"] == 1
    assert calls["policies"] == ["local_then_api"]

    summary_payload = json.loads((summary.run_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary_payload["pipeline"]["ocr_required_pages"] == 2
    assert summary_payload["pipeline"]["ocr_preflight_checked"] is True


def test_ocr_success_uses_text_route_without_auto_attaching_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)
    monkeypatch.setattr(workflow_module, "load_system_instructions", lambda _lang: "SYS")
    monkeypatch.setattr(workflow_module, "extract_ordered_page_text", lambda _pdf, _idx: _ordered_text_result(""))

    class _FakeEngine:
        def ocr_image(self, image_bytes: bytes, lang_hint: str | None = None) -> OcrResult:
            _ = image_bytes, lang_hint
            return OcrResult(text="Recovered OCR text", engine="api", failed_reason=None, chars=18)

    monkeypatch.setattr(workflow_module, "build_ocr_engine", lambda _cfg: _FakeEngine())
    monkeypatch.setattr(
        workflow_module,
        "ocr_pdf_page_text",
        lambda *_args, **_kwargs: OcrResult(
            text="Recovered OCR text with enough usable content to skip image attachment.",
            engine="api",
            failed_reason=None,
            chars=68,
            quality_score=0.91,
        ),
    )

    def _render_should_not_run(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("render_page_image_data_url should not be called when OCR text is sufficient")

    monkeypatch.setattr(workflow_module, "render_page_image_data_url", _render_should_not_run)

    config = RunConfig(
        pdf_path=pdf,
        output_dir=outdir,
        target_lang=TargetLang.EN,
        effort=ReasoningEffort.HIGH,
        image_mode=ImageMode.AUTO,
        max_pages=1,
        workers=1,
        resume=False,
        page_breaks=True,
        keep_intermediates=True,
        ocr_mode=OcrMode.AUTO,
        ocr_engine=OcrEnginePolicy.API,
        diagnostics_admin_mode=True,
    )

    summary = TranslationWorkflow(client=_FakeClient()).run(config)
    assert summary.success is True

    run_state = json.loads((summary.run_dir / "run_state.json").read_text(encoding="utf-8"))
    page = run_state["pages"]["1"]
    assert page["source_route"] == "ocr"
    assert page["ocr_used"] is True
    assert page["image_used"] is False
    assert page["image_decision_reason"] == "ocr_success_text_sufficient"


def test_text_only_pages_use_text_timeout_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)
    monkeypatch.setattr(workflow_module, "load_system_instructions", lambda _lang: "SYS")
    monkeypatch.setattr(workflow_module, "load_gui_settings", lambda: {"perf_timeout_text_seconds": 480, "perf_timeout_image_seconds": 720})
    monkeypatch.setattr(workflow_module, "extract_ordered_page_text", lambda _pdf, _idx: _ordered_text_result(""))
    monkeypatch.setattr(
        workflow_module,
        "ocr_pdf_page_text",
        lambda *_args, **_kwargs: OcrResult(
            text="Recovered OCR text with enough usable content to skip image attachment.",
            engine="api",
            failed_reason=None,
            chars=68,
            quality_score=0.91,
        ),
    )
    monkeypatch.setattr(workflow_module, "build_ocr_engine", lambda _cfg: object())

    client = _CapturingClient()
    config = RunConfig(
        pdf_path=pdf,
        output_dir=outdir,
        target_lang=TargetLang.EN,
        effort=ReasoningEffort.HIGH,
        image_mode=ImageMode.AUTO,
        max_pages=1,
        workers=1,
        resume=False,
        page_breaks=True,
        keep_intermediates=True,
        ocr_mode=OcrMode.AUTO,
        ocr_engine=OcrEnginePolicy.API,
        diagnostics_admin_mode=True,
    )

    summary = TranslationWorkflow(client=client).run(config)
    assert summary.success is True
    assert len(client.calls) == 1
    assert float(client.calls[0]["timeout_seconds"]) == pytest.approx(480.0, abs=0.1)
    assert client.calls[0]["image_data_url"] is None


def test_image_backed_pages_use_image_timeout_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)
    monkeypatch.setattr(workflow_module, "load_system_instructions", lambda _lang: "SYS")
    monkeypatch.setattr(workflow_module, "load_gui_settings", lambda: {"perf_timeout_text_seconds": 480, "perf_timeout_image_seconds": 720})
    monkeypatch.setattr(
        workflow_module,
        "extract_ordered_page_text",
        lambda _pdf, _idx: _ordered_text_result("Direct text route with enough content to avoid OCR."),
    )
    monkeypatch.setattr(
        workflow_module,
        "render_page_image_data_url",
        lambda *_args, **_kwargs: SimpleNamespace(
            data_url="data:image/jpeg;base64,ZmFrZQ==",
            image_format="jpg",
            encoded_bytes=4,
            width_px=100,
            height_px=100,
            compress_steps=0,
        ),
    )

    client = _CapturingClient()
    config = RunConfig(
        pdf_path=pdf,
        output_dir=outdir,
        target_lang=TargetLang.EN,
        effort=ReasoningEffort.HIGH,
        image_mode=ImageMode.ALWAYS,
        max_pages=1,
        workers=1,
        resume=False,
        page_breaks=True,
        keep_intermediates=True,
        ocr_mode=OcrMode.OFF,
        ocr_engine=OcrEnginePolicy.API,
        diagnostics_admin_mode=True,
    )

    summary = TranslationWorkflow(client=client).run(config)
    assert summary.success is True
    assert len(client.calls) == 1
    assert float(client.calls[0]["timeout_seconds"]) == pytest.approx(720.0, abs=0.1)
    assert str(client.calls[0]["image_data_url"]).startswith("data:image/jpeg;base64,")


def test_failed_run_summary_includes_failure_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)
    monkeypatch.setattr(workflow_module, "load_system_instructions", lambda _lang: "SYS")
    monkeypatch.setattr(
        workflow_module,
        "load_gui_settings",
        lambda: {"perf_timeout_text_seconds": 480, "perf_timeout_image_seconds": 720},
    )
    monkeypatch.setattr(workflow_module, "extract_ordered_page_text", lambda _pdf, _idx: _ordered_text_result(""))
    monkeypatch.setattr(
        workflow_module,
        "ocr_pdf_page_text",
        lambda *_args, **_kwargs: OcrResult(
            text="Recovered OCR text with enough usable content to skip image attachment.",
            engine="api",
            failed_reason=None,
            chars=68,
            quality_score=0.91,
        ),
    )
    monkeypatch.setattr(workflow_module, "build_ocr_engine", lambda _cfg: object())

    config = RunConfig(
        pdf_path=pdf,
        output_dir=outdir,
        target_lang=TargetLang.EN,
        effort=ReasoningEffort.HIGH,
        image_mode=ImageMode.AUTO,
        max_pages=1,
        workers=1,
        resume=False,
        page_breaks=True,
        keep_intermediates=True,
        ocr_mode=OcrMode.AUTO,
        ocr_engine=OcrEnginePolicy.API,
        diagnostics_admin_mode=True,
    )

    summary = TranslationWorkflow(client=_FailingClient()).run(config)
    assert summary.success is False
    payload = json.loads((summary.run_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert payload["suspected_cause"] != "rate_limiting"
    assert "runtime_failure" in str(payload["halt_reason"])
    failure_context = payload["failure_context"]
    assert failure_context["page_number"] == 1
    assert failure_context["request_type"] == "text_only"
    assert failure_context["request_timeout_budget_seconds"] == 480.0
    assert failure_context["exception_class"] == "APITimeoutError"
    assert failure_context["cancel_requested_before_failure"] is False


def test_translate_auth_preflight_failure_stops_before_page_processing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)
    monkeypatch.setattr(workflow_module, "load_system_instructions", lambda _lang: "SYS")
    monkeypatch.setattr(
        workflow_module,
        "load_gui_settings",
        lambda: {"perf_timeout_text_seconds": 480, "perf_timeout_image_seconds": 720},
    )

    def _extract_should_not_run(_pdf, _idx):  # type: ignore[no-untyped-def]
        raise AssertionError("Page extraction should not run when translation auth preflight fails")

    monkeypatch.setattr(workflow_module, "extract_ordered_page_text", _extract_should_not_run)

    config = RunConfig(
        pdf_path=pdf,
        output_dir=outdir,
        target_lang=TargetLang.EN,
        effort=ReasoningEffort.HIGH,
        image_mode=ImageMode.OFF,
        max_pages=1,
        workers=1,
        resume=False,
        page_breaks=True,
        keep_intermediates=True,
        ocr_mode=OcrMode.AUTO,
        ocr_engine=OcrEnginePolicy.LOCAL_THEN_API,
        diagnostics_admin_mode=True,
    )

    summary = TranslationWorkflow(client=_UnauthorizedPreflightClient()).run(config)

    assert summary.success is False
    assert summary.failed_page is None
    assert summary.error == "authentication_failure"
    assert summary.run_summary_path is not None
    payload = json.loads(summary.run_summary_path.read_text(encoding="utf-8"))
    assert payload["run_status"] == "authentication_failure"
    assert payload["suspected_cause"] == "authentication_failure"
    failure_context = payload["failure_context"]
    assert failure_context["scope"] == "preflight"
    assert failure_context["status_code"] == 401
    assert failure_context["exception_class"] == "AuthenticationError"
    assert failure_context["credential_source"] == {"kind": "stored", "name": ""}
    assert failure_context["message"] == "OpenAI authentication failed."
    event_types = {str(item.get("event_type", "")) for item in _events(summary.run_dir / "run_events.jsonl")}
    assert "translate_auth_preflight_failed" in event_types


def test_page_level_auth_failure_is_classified_as_authentication_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)
    monkeypatch.setattr(workflow_module, "load_system_instructions", lambda _lang: "SYS")
    monkeypatch.setattr(
        workflow_module,
        "load_gui_settings",
        lambda: {"perf_timeout_text_seconds": 480, "perf_timeout_image_seconds": 720},
    )
    monkeypatch.setattr(
        workflow_module,
        "extract_ordered_page_text",
        lambda _pdf, _idx: _ordered_text_result(
            "This page has enough extracted text to stay on the direct-text route."
        ),
    )
    monkeypatch.setattr(workflow_module, "should_include_image", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        workflow_module,
        "resolve_openai_key_with_source",
        lambda *_args, **_kwargs: (
            "stored-key",
            OpenAICredentialSourceInfo(kind="stored", name=""),
        ),
    )

    config = RunConfig(
        pdf_path=pdf,
        output_dir=outdir,
        target_lang=TargetLang.EN,
        effort=ReasoningEffort.HIGH,
        image_mode=ImageMode.OFF,
        max_pages=1,
        workers=1,
        resume=False,
        page_breaks=True,
        keep_intermediates=True,
        ocr_mode=OcrMode.AUTO,
        ocr_engine=OcrEnginePolicy.LOCAL_THEN_API,
        diagnostics_admin_mode=True,
    )

    summary = TranslationWorkflow(client=_AuthFailingPageClient()).run(config)

    assert summary.success is False
    assert summary.failed_page == 1
    assert summary.error == "authentication_failure"
    payload = json.loads((summary.run_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert payload["run_status"] == "authentication_failure"
    assert payload["suspected_cause"] == "authentication_failure"
    failure_context = payload["failure_context"]
    assert failure_context["scope"] == "page"
    assert failure_context["page_number"] == 1
    assert failure_context["error"] == "authentication_failure"
    assert failure_context["status_code"] == 401
    assert failure_context["exception_class"] == "AuthenticationError"
    assert failure_context["credential_source"] == {"kind": "stored", "name": ""}


def test_cancel_halt_reason_prefers_timeout_after_cancel() -> None:
    run_state = SimpleNamespace(
        pages={
            "1": {
                "cancel_requested_before_failure": True,
                "exception_class": "APITimeoutError",
                "transport_retries_count": 2,
            }
        }
    )
    assert _derive_cancel_halt_reason(run_state) == "cancelled_after_request_timeout"


def test_cancel_halt_reason_prefers_transport_retry_when_no_timeout() -> None:
    run_state = SimpleNamespace(
        pages={
            "1": {
                "cancel_requested_before_failure": True,
                "exception_class": "APIConnectionError",
                "transport_retries_count": 1,
            }
        }
    )
    assert _derive_cancel_halt_reason(run_state) == "cancelled_during_transport_retry"
