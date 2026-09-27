"""Fictional local saved-Word import through the real browser route boundary."""
from copy import deepcopy
import asyncio
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

from docx import Document
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
import fitz
import pytest

from legalpdf_translate.shadow_web import saved_docx_layout_api as api


HEADERS = {"X-LegalPDF-Runtime-Mode": "shadow", "X-LegalPDF-Workspace-Id": "layout-test"}


def fictional_files(lang="EN"):
    lines = {
        "EN": ["Fictional District Office", "Reference: AB/2026", "Important notice", "Keep this complete passage unchanged."],
        "FR": ["Bureau fictif du district", "Référence : AB/2026", "Avis important", "Conservez ce passage complet sans modification."],
        "AR": ["مكتب المقاطعة الافتراضي", "المرجع AB/2026", "إشعار مهم", "احتفظ بهذا النص الكامل دون تغيير."],
    }[lang]
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    buf = BytesIO(); document.save(buf)
    pdf = fitz.open(); page = pdf.new_page()
    for i, line in enumerate(["Fictional office", "Reference", "Notice", "Complete fictional passage"]):
        page.insert_text((45, 70 + i * 50), line)
    data = pdf.tobytes(); pdf.close()
    return data, buf.getvalue()


def actual_app(tmp_path, monkeypatch):
    from legalpdf_translate.shadow_web.app import create_shadow_app, offline_browser_app_services
    import legalpdf_translate.shadow_runtime as runtime
    import legalpdf_translate.user_settings as settings

    def forbidden(*args, **kwargs):
        pytest.fail("Saved layout route consulted settings/default outputs")

    monkeypatch.setattr(runtime, "load_gui_settings_from_path", forbidden)
    monkeypatch.setattr(settings, "load_gui_settings_from_path", forbidden)
    services = offline_browser_app_services(state_root=tmp_path)
    services = replace(services, detect_data_paths=forbidden)
    return create_shadow_app(repo_root=Path(__file__).resolve().parents[1],
        enable_live_gmail_bridge=False, services=services)


def value(response):
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    return response.json()["normalized_payload"]["saved_docx_layout"]


def import_file(client, lang="EN", nonce="a" * 32, files=None, headers=None):
    pdf, docx = files or fictional_files(lang)
    return client.post(api.PREFIX + "/imports", headers=HEADERS if headers is None else headers,
        files={"source_pdf": ("private.pdf", pdf, "application/pdf"),
               "saved_docx": ("private.docx", docx, api._KINDS["docx"])},
        data={"target_lang": lang, "import_nonce": nonce})


def reviewed_decisions(view):
    decision = deepcopy(view["decisions"])
    for para in decision["paragraphs"]:
        para["regions"] = [{"page_number": 1, "bbox_px": [40, 40, 400, 500]}]
        para["unmapped_reason"] = ""
    decision["paragraphs"][2].update(role="heading", heading_level=1, bold=True, heading_size_pt=14)
    decision["review"] = {"reviewer_kind": "operator_review", "reviewer": "Fictional operator",
        "note": "Compared every fictional source region and retained passage", "pages_reviewed": [1], "document_reviewed": True}
    ids = [p["id"] for p in view["paragraphs"]]
    decision["bands"] = [{"kind": "columns", "widths_pct": [40, 60], "gutter_pt": 12,
        "cells": [{"groups": [{"paragraph_ids": ids[:2], "panel": False}]},
                  {"groups": [{"paragraph_ids": ids[2:], "panel": True}]}]}]
    return decision


@pytest.mark.parametrize("lang", ["EN", "FR", "AR"])
def test_real_import_save_build_download_and_restart_preserve_original_bytes(tmp_path, monkeypatch, lang):
    files = fictional_files(lang)
    before = tuple(files)
    app = actual_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        capabilities = value(client.get(api.PREFIX + "/capabilities", headers=HEADERS))
        assert capabilities
        imported = value(import_file(client, lang, files=files))
        assert value(import_file(client, lang, files=files))["review_id"] == imported["review_id"]
        rid = imported["review_id"]
        base = api.PREFIX + "/reviews/" + rid
        assert value(client.get(api.PREFIX + "/reviews", headers=HEADERS))[0]["review_id"] == rid
        image = client.get(base + "/pages/1/image", headers=HEADERS)
        assert image.status_code == 200 and image.content.startswith(b"\x89PNG")
        saved = value(client.post(base + "/decisions", headers=HEADERS, json={
            "expected_generation": imported["generation"], "save_nonce": "b" * 32,
            "decisions": reviewed_decisions(imported)}))
        build_payload = {"expected_generation": saved["generation"], "operation_nonce": "c" * 32, "review_confirmed": True}
        built = value(client.post(base + "/builds", headers=HEADERS, json=build_payload))
        assert built["artifacts"]
        artifact = built["artifacts"][0]
        response = client.get(base + f"/artifacts/{artifact['artifact_id']}/docx", headers=HEADERS)
        assert response.status_code == 200 and response.content.startswith(b"PK")
        assert "attachment" in response.headers["content-disposition"]
        with ZipFile(BytesIO(files[1])) as original, ZipFile(BytesIO(response.content)) as result:
            assert all(original.read(name) == result.read(name) for name in original.namelist() if name != "word/document.xml")
        assert files == before
        other = {**HEADERS, "X-LegalPDF-Workspace-Id": "other"}
        assert client.get(base, headers=other).status_code != 200
    # A new app/service instance must rediscover exact saved review and nonce.
    with TestClient(actual_app(tmp_path, monkeypatch)) as client:
        reopened = value(client.get(base, headers=HEADERS))
        assert reopened["generation"] == saved["generation"]
        replay = value(client.post(base + "/builds", headers=HEADERS, json=build_payload))
        assert replay["artifacts"] == built["artifacts"]
        assert client.get(base + "/artifacts/" + artifact["artifact_id"] + "/receipt", headers=HEADERS).status_code == 200


def fake_app(factory):
    context = SimpleNamespace(repo_root=Path("fictional"), build_identity=None,
        services=SimpleNamespace(saved_docx_layout_factory=factory,
                                 saved_docx_layout_root=lambda **_: Path("fictional-root")))
    app = FastAPI()
    api.SavedDocxLayoutRoutes(app, context_for=lambda request: context)
    return app


def test_scope_checked_before_import_body_and_no_paths_or_text_in_errors():
    calls = []
    def factory(*args, **kwargs):
        calls.append(kwargs)
        raise RuntimeError("fictional private content must never appear")
    with TestClient(fake_app(factory)) as client:
        response = client.post(api.PREFIX + "/imports", content=b"not multipart")
        assert response.status_code == 422 and calls == []
        response = client.get(api.PREFIX + "/reviews", headers=HEADERS)
        assert response.status_code == 422
        assert response.json()["diagnostics"] == {"error": "saved_docx_layout_operation_failed"}
        assert "private content" not in response.text
        assert client.get(api.PREFIX + "/reviews?mode=live", headers=HEADERS).status_code == 422


class RecordingService:
    def __init__(self):
        self.imports = []
    def import_document(self, *args):
        self.imports.append(args)
        return {"review_id": "d" * 32}


def test_multipart_bounds_before_parse_and_per_file_limits(monkeypatch):
    service = RecordingService()
    with TestClient(fake_app(lambda *a, **k: service)) as client:
        monkeypatch.setattr(api, "MAX_REQUEST_BYTES", 12)
        response = import_file(client, files=(b"pdf", b"docx"))
        assert response.status_code == 413 and not service.imports
        monkeypatch.setattr(api, "MAX_REQUEST_BYTES", 4096)
        monkeypatch.setattr(api, "MAX_DOCX_BYTES", 3)
        response = import_file(client, files=(b"pdf", b"docx"))
        assert response.status_code == 413 and not service.imports
        monkeypatch.setattr(api, "MAX_DOCX_BYTES", 4)
        assert import_file(client, files=(b"pdf", b"docx")).status_code == 200
        assert service.imports == [(b"pdf", b"docx", "EN", "a" * 32)]


def test_duplicate_unknown_and_truncated_multipart_parts_decline(monkeypatch):
    service = RecordingService()
    with TestClient(fake_app(lambda *a, **k: service)) as client:
        common = [("source_pdf", ("x.pdf", b"pdf")), ("saved_docx", ("x.docx", b"docx")),
                  ("target_lang", (None, "EN")), ("import_nonce", (None, "a" * 32))]
        for extra in [[("source_pdf", ("duplicate.pdf", b"pdf"))], [("path", (None, "C:/private"))]]:
            assert client.post(api.PREFIX + "/imports", headers=HEADERS, files=common + extra).status_code == 422
        response = client.post(api.PREFIX + "/imports", headers={**HEADERS, "Content-Type": "multipart/form-data; boundary=a"},
            content=b'--a\r\nContent-Disposition: form-data; name="source_pdf"; filename="x"\r\n\r\npdf')
        assert response.status_code == 422 and not service.imports
        monkeypatch.setattr(api, "MAX_HEADER_BYTES", 10)
        assert import_file(client, files=(b"pdf", b"docx")).status_code == 413


def test_json_and_endpoint_validation_precedes_mutation(monkeypatch):
    service = SimpleNamespace(save_decisions=lambda *_: pytest.fail("Invalid save reached service"),
                              build=lambda *_: pytest.fail("Invalid build reached service"))
    base = api.PREFIX + "/reviews/" + "a" * 32
    with TestClient(fake_app(lambda *a, **k: service)) as client:
        for content in [b'{"expected_generation":1,"expected_generation":2}', b'{"x":NaN}', b'[]']:
            assert client.post(base + "/decisions", headers=HEADERS, content=content).status_code == 422
        payload = {"expected_generation": True, "save_nonce": "b" * 32, "decisions": {}}
        assert client.post(base + "/decisions", headers=HEADERS, json=payload).status_code == 422
        monkeypatch.setattr(api, "MAX_JSON_BYTES", 3)
        assert client.post(base + "/decisions", headers=HEADERS, content=b"1234").status_code == 413
        assert client.get(base + "/artifacts/" + "b" * 32 + "/settings", headers=HEADERS).status_code == 404


def test_default_root_resolver_does_not_load_settings(tmp_path, monkeypatch):
    import legalpdf_translate.user_settings as settings
    import legalpdf_translate.shadow_runtime as runtime
    monkeypatch.setattr(settings, "settings_path", lambda: tmp_path / "settings.json")
    monkeypatch.setattr(settings, "load_gui_settings_from_path", lambda *_: pytest.fail("settings read"))
    monkeypatch.setattr(runtime, "load_gui_settings_from_path", lambda *_: pytest.fail("settings read"))
    assert api.default_saved_docx_layout_root(mode="live", repo=tmp_path, identity=None) == tmp_path
    assert not (tmp_path / "settings.json").exists()


def test_missing_renderer_is_reported_consistently_without_import():
    service = SimpleNamespace(capabilities=lambda: {"available": False, "status": "unavailable"})
    with TestClient(fake_app(lambda *a, **k: service)) as client:
        response = client.get(api.PREFIX + "/capabilities", headers=HEADERS)
        assert value(response)["available"] is False
        assert response.json()["capability_flags"]["saved_docx_layout"]["status"] == "unavailable"


def test_actual_chunked_stream_limit_ignores_lying_content_length(monkeypatch):
    writes = []
    class Parser:
        def __init__(self, *_args, **_kwargs):
            pass
        def write(self, chunk):
            writes.append(chunk)
        def finalize(self):
            pytest.fail("Oversized request finalized")
    monkeypatch.setattr(api, "MAX_REQUEST_BYTES", 5)
    monkeypatch.setattr(api, "MultipartParser", Parser)
    messages = iter([{"type": "http.request", "body": b"123", "more_body": True},
                     {"type": "http.request", "body": b"456", "more_body": False}])
    async def receive():
        return next(messages)
    request = Request({"type": "http", "method": "POST", "path": "/imports",
        "headers": [(b"content-type", b"multipart/form-data; boundary=x"), (b"content-length", b"1")]}, receive)
    with pytest.raises(api.SavedDocxLayoutAPIError) as error:
        asyncio.run(api._import_payload(request))
    assert error.value.code == "request_too_large" and error.value.status == 413
    assert writes == [b"123"]  # The crossing chunk never reaches the parser.
