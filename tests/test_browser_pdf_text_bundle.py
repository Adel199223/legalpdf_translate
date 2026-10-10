"""Browser PDF.js text evidence reaches ordinary translation without native PDF reads."""

from __future__ import annotations

import builtins
from io import BytesIO
import json
import os
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from legalpdf_translate.browser_pdf_bundle import (browser_pdf_bundle_manifest_path,
    browser_pdf_bundle_page_image_path, browser_pdf_bundle_page_text, write_browser_pdf_bundle)
from legalpdf_translate.browser_pdf_text import ordered_browser_page_text, validate_browser_page_text
from legalpdf_translate.document_structure import structure_from_ordered
from legalpdf_translate import new_translation_blocks
from legalpdf_translate.source_document import extract_ordered_source_text
from legalpdf_translate import workflow as workflow_module
from legalpdf_translate.ocr_engine import OcrResult
from legalpdf_translate.types import ImageMode, TargetLang
from tests.browser_esm_probe import run_browser_esm_json_probe
from tests.test_ordinary_auto_layout_workflow import _app, _source, _start, _wait, SOURCE


def _item(text, x, y, width, *, direction="ltr", eol=True):
    return {"text": text, "x": x, "y": y, "width": width, "height": 12,
            "dir": direction, "has_eol": eol}


def _evidence(page=1, items=None):
    return {"version": 1, "page_number": page, "page_width": 600,
            "page_height": 800, "items": items or []}


def _png():
    image = Image.new("RGB", (24, 18), "white")
    data = BytesIO()
    image.save(data, format="PNG")
    return data.getvalue()


def test_pdfjs_fragments_columns_repeated_literals_and_rtl_order_are_retained():
    items = [
        _item("Tribunal Judicial", 40, 8, 95),
        _item("Alpha", 40, 100, 28, eol=False),
        _item(" ", 68, 100, 1, eol=False),
        _item("Beta 42", 69, 100, 48),
        _item("Left 42", 40, 130, 50),
        _item("Right 42", 350, 100, 55),
        _item("مرحبا", 420, 130, 38, direction="rtl", eol=False),
        _item("بك", 390, 130, 20, direction="rtl"),
        _item("Pág. 1", 40, 780, 35),
    ]
    ordered = ordered_browser_page_text(_evidence(items=items))
    assert ordered.text == "Tribunal Judicial\nAlpha Beta 42\nLeft 42\nRight 42\nمرحبا بك\nPág. 1"
    assert ordered.two_column_detected is True
    assert ordered.text.count("42") == 3
    assert ordered.extraction_metadata["source"] == "browser_pdfjs_text"
    structural = structure_from_ordered(ordered, page_number=1, source_file_sha256="a" * 64)
    assert structural.provenance == "text_fallback" and structural.uncertain is True
    assert all(block.bbox is None for block in structural.blocks)


def test_browser_text_cannot_be_promoted_to_certain_native_structured_source(monkeypatch):
    ordered = ordered_browser_page_text(_evidence(items=[_item("Digital text 42", 40, 100, 85)]),
        preserve_structure=True)
    structured = object.__new__(new_translation_blocks.NewTranslationBlocks)
    structured.config = SimpleNamespace(pdf_path=Path("unused.pdf"))
    structured.source_hash = "a" * 64
    structured.page_identities = {1: {"source_file_sha256": "a" * 64,
                                      "image_sha256": "b" * 64,
                                      "source_type": "browser_pdf_image", "paper_size_basis": "a4_assumed"}}
    structured.reviewed_sources = {}
    structured.reviewed_evidence = None
    monkeypatch.setattr(new_translation_blocks, "source_page_dimensions", lambda *_: (600.0, 800.0))
    source = structured.make_source(number=1, ordered=ordered, text=ordered.text,
        ocr_result=None, ocr_used=False, merged=False, suspect=False)
    assert source.provenance == "text_fallback" and source.uncertain is True
    assert all(block.bbox is None for block in source.blocks)


def test_bundle_v2_pins_source_and_text_sidecar_without_native_pdf_imports(tmp_path, monkeypatch):
    source = tmp_path / "digital.pdf"
    source.write_bytes(b"%PDF-1.7\nfictional digital source")
    manifest = write_browser_pdf_bundle(source_path=source, page_count=1, pages=[{
        "page_number": 1, "mime_type": "image/png", "width_px": 24, "height_px": 18,
        "image_bytes": _png(), "text_content": _evidence(items=[_item("Digital source 42", 40, 100, 90)]),
    }])
    original_import = builtins.__import__

    def no_native(name, globals=None, locals=None, fromlist=(), level=0):
        if str(name).split(".", 1)[0] in {"fitz", "pymupdf", "mupdf"}:
            raise AssertionError("Bundle text extraction imported a native PDF runtime")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", no_native)
    assert extract_ordered_source_text(source, 0).text == "Digital source 42"
    assert browser_pdf_bundle_page_text(source, 1)["items"][0]["text"] == "Digital source 42"
    manifest_path = browser_pdf_bundle_manifest_path(source)
    original_manifest = manifest_path.read_bytes()
    damaged_manifest = json.loads(original_manifest)
    damaged_manifest["page_count"] = 0
    manifest_path.write_text(json.dumps(damaged_manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="pages are invalid"):
        extract_ordered_source_text(source, 0)
    manifest_path.write_bytes(original_manifest)
    sidecar = source.with_name(source.name + ".browser_pdf_bundle") / manifest["pages"][0]["text_path"]
    sidecar.write_bytes(sidecar.read_bytes().replace(b"Digital", b"Changed"))
    with pytest.raises(ValueError, match="sidecar changed"):
        extract_ordered_source_text(source, 0)
    source_stat = source.stat()
    source.write_bytes(b"%PDF-1.7\nfictional digital sourcE")
    os.utime(source, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
    with pytest.raises(ValueError, match="source hash changed"):
        extract_ordered_source_text(source, 0)


def test_invalid_later_page_preserves_published_bundle_generation(tmp_path):
    source = tmp_path / "digital.pdf"
    source.write_bytes(b"%PDF-1.7\nfictional two-page source")
    initial = write_browser_pdf_bundle(source_path=source, page_count=2, pages=[{
        "page_number": number, "mime_type": "image/png", "width_px": 24, "height_px": 18,
        "image_bytes": _png(), "text_content": _evidence(number, [_item(f"Page {number}", 40, 100, 50)]),
    } for number in (1, 2)])
    initial_bytes = browser_pdf_bundle_manifest_path(source).read_bytes()
    initial_image = browser_pdf_bundle_page_image_path(source, 1)
    assert initial_image is not None
    with pytest.raises(ValueError, match="dimensions are invalid"):
        write_browser_pdf_bundle(source_path=source, page_count=2, pages=[{
            "page_number": number, "mime_type": "image/png",
            "width_px": 24 if number == 1 else "bad", "height_px": 18,
            "image_bytes": _png(), "text_content": _evidence(number, [_item("Changed", 40, 100, 50)]),
        } for number in (1, 2)])
    assert browser_pdf_bundle_manifest_path(source).read_bytes() == initial_bytes
    assert browser_pdf_bundle_page_image_path(source, 1) == initial_image
    assert extract_ordered_source_text(source, 0).text == "Page 1"
    assert initial["pages"][0]["text_path"].startswith("generations/")


def test_bad_browser_text_page_identity_and_geometry_reject():
    for change in ({"version": True}, {"page_number": True},
                   {"items": [_item("bad", 0, float("nan"), 5)]}):
        evidence = _evidence(items=[_item("valid", 20, 50, 30)])
        evidence.update(change)
        with pytest.raises(ValueError, match="Browser PDF text"):
            validate_browser_page_text(evidence, page_number=1)


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.delenv("LEGALPDF_TRANSLATION_PROTOCOL", raising=False)
    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "run_translation_auth_test",
        lambda *a, **k: pytest.fail("Unexpected authentication call"))
    monkeypatch.setattr(workflow_module, "resolve_openai_key_with_source",
        lambda *a, **k: pytest.fail("Unexpected ambient credentials"))


@pytest.mark.parametrize("kind,image_mode,text,expected_calls,image_expected,ocr_success", [
    ("digital", "off", SOURCE, 1, False, False),
    ("digital", "auto", SOURCE, 1, True, False),
    ("digital", "always", SOURCE, 1, True, False),
    ("vector", "always", "", 1, True, False),
    ("vector", "off", "", 0, False, False),
    ("vector", "auto", "", 1, True, True),
])
def test_real_browser_upload_bundle_then_ordinary_dispatch(
    tmp_path, monkeypatch, kind, image_mode, text, expected_calls, image_expected, ocr_success,
):
    source = tmp_path / "source.pdf"
    _source(source, (kind,))
    app, manager, sdk, layout_requests = _app(tmp_path, monkeypatch, ("English source 42",), (1,))
    if ocr_success:
        monkeypatch.setattr(workflow_module.TranslationWorkflow, "_resolve_ocr_engine_for_reason",
            lambda *_args, **_kwargs: (object(), True))
        monkeypatch.setattr(workflow_module, "ocr_pdf_page_text",
            lambda *_args, **_kwargs: OcrResult(
                text="Recovered OCR text from the source page", engine="api", failed_reason=None, chars=39,
                quality_score=.95))
    headers = {"X-LegalPDF-Runtime-Mode": "shadow", "X-LegalPDF-Workspace-Id": "fictional"}
    output = tmp_path / "output"
    output.mkdir()
    with TestClient(app) as client:
        upload = client.post("/api/translation/upload-source", headers=headers,
            files={"file": ("source.pdf", source.read_bytes(), "application/pdf")})
        assert upload.status_code == 200, upload.text
        staged = Path(upload.json()["normalized_payload"]["source_path"])
        evidence = _evidence(items=[_item(text, 40, 100, max(1, len(text) * 4))] if text else [])
        manifest = {"source_path": str(staged), "page_count": 1,
            "pages": [{"page_number": 1, "file_name": "page_0001.png", "mime_type": "image/png",
                       "width_px": 24, "height_px": 18, "text_content": evidence}]}
        bundle = client.post("/api/browser-pdf/bundle", headers=headers,
            data={"manifest": json.dumps(manifest)},
            files={"page_images": ("page_0001.png", _png(), "image/png")})
        assert bundle.status_code == 200, bundle.text
        retained = json.loads(browser_pdf_bundle_manifest_path(staged).read_text(encoding="utf-8"))
        assert retained["version"] == 2 and len(retained["source_sha256"]) == 64
        job_id = _start(client, staged, output, "EN", start=1, end=1, image_mode=image_mode,
                        ocr_mode="always" if ocr_success else "off")
        settled = _wait(manager, job_id)
        assert len(sdk.requests) == expected_calls, (settled["status_text"], settled["logs"][-3:])
        if text or ocr_success:
            assert settled["status"] == "completed"
            assert (text or "Recovered OCR text") in json.dumps(sdk.requests, ensure_ascii=False)
            assert len(layout_requests) == 1
        elif image_mode == "always":
            assert settled["status"] == "completed"
            assert "image_url" in json.dumps(sdk.requests)
            assert len(layout_requests) == 1
        else:
            assert settled["status"] == "failed"
            assert "Enable page images or OCR" in settled["status_text"]
            assert len(layout_requests) == 0
        if expected_calls:
            request = json.dumps(sdk.requests[0], ensure_ascii=False)
            assert ("image_url" in request) is image_expected
            if image_expected:
                assert "whole source page" in request
                assert "\"detail\": \"high\"" in request
                assert "source_coverage_notice" not in settled["diagnostics"]
            elif image_mode == "off":
                assert "coverage is limited to extractable text" in settled["status_text"]
                assert "Visible text in drawings or images can be missing" in settled["diagnostics"]["source_coverage_notice"]
            run_dir = Path(settled["result"]["artifacts"]["run_dir"])
            run_state = json.loads((run_dir / "run_state.json").read_text(encoding="utf-8"))
            page = run_state["pages"]["1"]
            assert page["source_coverage_verified"] is False
            assert page["source_coverage_image_supplied"] is image_expected
            if image_mode == "auto" and image_expected:
                assert page["image_decision_reason"] == "ordinary_full_page_visual_source"
            if ocr_success:
                assert page["source_route"] == "ocr"


def test_historical_auto_heuristic_remains_text_only_without_ordinary_policy():
    workflow = workflow_module.TranslationWorkflow(translation_protocol="legacy_text_v1")
    used, reason = workflow._resolve_page_image_usage(
        config=SimpleNamespace(image_mode=ImageMode.AUTO, target_lang=TargetLang.EN),
        ordered_text=SOURCE, source_text=SOURCE, extraction_failed=False, fragmented=False,
        two_column_detected=False, ocr_chars=0, ocr_quality_score=0.0)
    assert used is False and reason == "not_needed"


@pytest.mark.parametrize("ocr_success", [False, True])
def test_required_auto_image_render_failure_stops_before_provider(tmp_path, monkeypatch, ocr_success):
    source = tmp_path / "source.pdf"
    _source(source, ("digital",))
    app, manager, sdk, layout_requests = _app(tmp_path, monkeypatch, ("English source 42",), (1,))
    if ocr_success:
        monkeypatch.setattr(workflow_module.TranslationWorkflow, "_resolve_ocr_engine_for_reason",
            lambda *_args, **_kwargs: (object(), True))
        monkeypatch.setattr(workflow_module, "ocr_pdf_page_text",
            lambda *_args, **_kwargs: OcrResult(
                text="Recovered OCR text from the source page", engine="api", failed_reason=None,
                chars=39, quality_score=.95))
    monkeypatch.setattr(workflow_module, "render_page_image_data_url",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("fictional render failure")))
    headers = {"X-LegalPDF-Runtime-Mode": "shadow", "X-LegalPDF-Workspace-Id": "fictional"}
    output = tmp_path / "output"
    output.mkdir()
    with TestClient(app) as client:
        upload = client.post("/api/translation/upload-source", headers=headers,
            files={"file": ("source.pdf", source.read_bytes(), "application/pdf")})
        assert upload.status_code == 200
        staged = Path(upload.json()["normalized_payload"]["source_path"])
        manifest = {"source_path": str(staged), "page_count": 1,
            "pages": [{"page_number": 1, "file_name": "page_0001.png", "mime_type": "image/png",
                       "width_px": 24, "height_px": 18,
                       "text_content": _evidence(items=[] if ocr_success else [_item(SOURCE, 40, 100, 300)])}]}
        bundle = client.post("/api/browser-pdf/bundle", headers=headers,
            data={"manifest": json.dumps(manifest)},
            files={"page_images": ("page_0001.png", _png(), "image/png")})
        assert bundle.status_code == 200
        job = _wait(manager, _start(client, staged, output, "EN", start=1, end=1,
                                    image_mode="auto", ocr_mode="always" if ocr_success else "off"))
        assert job["status"] == "failed"
        assert "required full-page image is unavailable" in job["status_text"]
        assert len(sdk.requests) == 0 and len(layout_requests) == 0
        run_dir = Path(job["result"]["artifacts"]["run_dir"])
        page = json.loads((run_dir / "run_state.json").read_text(encoding="utf-8"))["pages"]["1"]
        if ocr_success:
            assert page["ocr_engine_used"] == "api" and page["ocr_used"] is True
        assert page["source_coverage_basis"] == "required_full_page_image_unavailable"


def test_completed_off_coverage_notice_survives_arabic_review_copy():
    result = run_browser_esm_json_probe(r'''
const {deriveTranslationCompletionPresentation}=await import(__MODULE__);
const job={job_kind:"translate",status:"completed",diagnostics:{source_coverage_notice:
  "Page images were off; coverage is limited to extractable text."},
  result:{save_seed:{run_id:"fictional"}}};
const state=deriveTranslationCompletionPresentation({job,
  arabicReview:{required:true,resolved:false,message:"Review Arabic formatting."}});
console.log(JSON.stringify({drawer:state.drawerStatus,copy:state.resultCopy,save:state.saveStatus}));
''', {"__MODULE__": "translation_completion_presentation.js"})
    assert all("coverage is limited to extractable text" in result[key]
               for key in ("drawer", "copy", "save"))


def test_pdfjs_get_text_content_reaches_existing_multipart_manifest():
    result = run_browser_esm_json_probe(r'''
const {renderPdfPageBlob,uploadBrowserPdfBundle}=await import(__MODULE__);
globalThis.document={createElement:()=>({getContext:()=>({}),toBlob:(callback)=>callback(new Blob(["png"],{type:"image/png"}))})};
let called=0, uploaded=null;
const page={getViewport:({scale})=>({width:600*scale,height:800*scale,
  convertToViewportPoint:(x,y)=>[x,800-y]}),
  getTextContent:async()=>{called++;return {items:[{str:"Digital",transform:[1,0,0,1,40,700],width:35,height:12,dir:"ltr",hasEOL:false},
    {str:" source 42",transform:[1,0,0,1,75,700],width:65,height:12,dir:"ltr",hasEOL:true}]};},
  render:()=>({promise:Promise.resolve()})};
globalThis.fetch=async(_path,options)=>{uploaded=JSON.parse(options.body.get("manifest"));return {
  ok:true,status:200,text:async()=>JSON.stringify({status:"ok",normalized_payload:{page_count:1}})};};
const rendered=await renderPdfPageBlob({getPage:async()=>page},1);
await uploadBrowserPdfBundle({appState:{runtimeMode:"shadow",workspaceId:"fictional"},
  sourcePath:"C:/uploads/digital.pdf",pageCount:1,renderedPages:[rendered]});
console.log(JSON.stringify({called,page:uploaded.pages[0],images:rendered.blob.size}));
''', {"__MODULE__": "browser_pdf.js"})
    assert result["called"] == 1
    assert result["page"]["text_content"]["items"][0]["text"] == "Digital"
    assert result["page"]["text_content"]["items"][1]["text"] == " source 42"
    assert result["page"]["text_content"]["page_number"] == 1
    assert result["images"] > 0
