from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import legalpdf_translate.workflow as workflow_module
from legalpdf_translate.ocr_engine import OcrResult
from legalpdf_translate.openai_client import ApiCallResult
from legalpdf_translate.types import ImageMode, OcrEnginePolicy, OcrMode, ReasoningEffort, RunConfig, TargetLang
from legalpdf_translate.workflow import TranslationWorkflow, classify_extracted_text_quality


class _FakeClient:
    def create_page_response(self, **kwargs) -> ApiCallResult:  # noqa: ANN003
        _ = kwargs
        return ApiCallResult(
            raw_output="```\nTranslated output\n```",
            usage={"input_tokens": 10, "output_tokens": 4, "reasoning_tokens": 1, "total_tokens": 15},
            response_id="resp-test",
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
