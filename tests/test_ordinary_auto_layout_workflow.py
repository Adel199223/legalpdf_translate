"""Fresh ordinary browser jobs through translation, layout, and normal delivery."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from threading import Event
import time
from types import SimpleNamespace
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from decimal import Decimal

from lxml import etree

import fitz
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
import pytest

from legalpdf_translate import translation_service, workflow as workflow_module
from legalpdf_translate.openai_client import OpenAIResponsesClient
from legalpdf_translate.ordinary_auto_layout_artifacts import bind_raw_page_map
from legalpdf_translate.ordinary_layout_contracts import PROPOSAL_VERSION
from legalpdf_translate.shadow_web import app as browser
from tests.test_workflow_dispatch_accounting import FakeSDK


SOURCE = (
    "O documento apresenta os factos e as circunstancias do processo. "
    "A pessoa deve comparecer no tribunal e cumprir as condicoes indicadas. "
    "A decisao continua a aplicar-se durante o periodo determinado."
)
TRANSLATIONS = {
    "EN": ("English page two alpha 42", "English page three beta 73"),
    "FR": ("Francais page deux alpha 42", "Francais page trois beta 73"),
    "AR": ("العربية الصفحة الثانية 42", "العربية الصفحة الثالثة 73"),
}
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _source(path: Path, kinds: tuple[str, ...]) -> None:
    image = Image.new("RGB", (1000, 1400), "white")
    draw = ImageDraw.Draw(image)
    draw.text((80, 100), SOURCE, fill="black")
    encoded = BytesIO()
    image.save(encoded, format="PNG")
    with fitz.open() as pdf:
        for kind in kinds:
            page = pdf.new_page()
            if kind == "digital":
                page.insert_textbox(fitz.Rect(45, 70, 550, 300), SOURCE, fontsize=11)
            elif kind == "raster":
                page.insert_image(page.rect, stream=encoded.getvalue())
            else:
                assert kind == "vector"
                # Path outlines have visible source marks but no selectable text.
                for row in range(16):
                    y = 90 + row * 22
                    for column in range(24):
                        x = 45 + column * 19
                        page.draw_rect(fitz.Rect(x, y, x + 12, y + 12), color=(0, 0, 0), width=.8)
        pdf.save(path)


def _rich_source(path: Path) -> None:
    with fitz.open() as pdf:
        cover = pdf.new_page()
        cover.insert_text((50, 85), "Fictional cover outside selected source range")
        for columns in (2, 3):
            page = pdf.new_page()
            width = page.rect.width / columns
            for column in range(columns):
                x = 35 + column * width
                for row in range(6):
                    page.insert_text((x, 80 + row * 30),
                        f"Fictional source section {columns} column {column + 1} line {row + 1}", fontsize=9)
        pdf.save(path)


def _docx_text(data: bytes) -> str:
    with ZipFile(BytesIO(data)) as package:
        body = ET.fromstring(package.read("word/document.xml"))
    return "".join(node.text or "" for node in body.iter(W + "t"))


def _right_align_arabic_paragraph(data: bytes) -> bytes:
    with ZipFile(BytesIO(data)) as source:
        document = etree.fromstring(source.read("word/document.xml"))
        paragraph = next(node for node in document.iter(W + "p")
            if any("\u0600" <= (letter or "") <= "\u06ff"
                   for text in node.iter(W + "t") for letter in (text.text or "")))
        properties = paragraph.find(W + "pPr")
        if properties is None:
            properties = etree.Element(W + "pPr")
            paragraph.insert(0, properties)
        for local, value in (("bidi", "1"), ("jc", "right"), ("keepNext", "1")):
            setting = properties.find(W + local)
            if setting is None:
                setting = etree.SubElement(properties, W + local)
            setting.set(W + "val", value)
        modified = etree.tostring(document, xml_declaration=True, encoding="UTF-8", standalone=True)
        output = BytesIO()
        with ZipFile(output, "w") as target:
            for member in source.infolist():
                target.writestr(member, modified if member.filename == "word/document.xml"
                                else source.read(member.filename))
    edited = output.getvalue()
    assert edited != data and _docx_text(edited) == _docx_text(data)
    return edited


def _proposal(review: dict, page: int, columns: int = 0) -> dict:
    rows = []
    for choice in review["decisions"]["paragraphs"]:
        if {region["page_number"] for region in choice["regions"]} != {page}:
            continue
        row = {key: value for key, value in choice.items()
               if key not in {"regions", "unmapped_reason"}}
        row["bbox"] = [.08, .08, .92, .9]
        if not rows:
            row.update(role="heading", heading_level=1, heading_size_pt=12, bold=True)
        rows.append(row)
    assert rows, f"Page {page} lacks independently mapped translated paragraphs"
    if columns:
        break_ids = {item["id"] for item in review["paragraphs"] if item["has_page_break"]}
        layout_rows = [row for row in rows if row["paragraph_id"] not in break_ids]
        break_rows = [row for row in rows if row["paragraph_id"] in break_ids]
        assert len(layout_rows) >= columns
        role_order = ("institution", "reference", "recipient", "heading", "list",
                      "body", "source_folio", "signature")
        for index, row in enumerate(layout_rows):
            row["role"] = role_order[min(index, len(role_order) - 1)]
            if row["role"] == "heading":
                row.update(heading_level=1, heading_size_pt=12, bold=True)
            else:
                row.update(heading_level=0, heading_size_pt=None)
        # Cells must own contiguous runs to preserve physical reading order.
        chunk_size = (len(layout_rows) + columns - 1) // columns
        chunks = [layout_rows[index * chunk_size:(index + 1) * chunk_size]
                  for index in range(columns)]
        bands = [{"kind": "columns", "widths_pct": [50, 50] if columns == 2 else [34, 33, 33],
                  "gutter_pt": 12, "cells": [{"groups": [{"paragraph_ids": [row["paragraph_id"]
                    for row in chunk], "panel": index == 0}]} for index, chunk in enumerate(chunks)]}]
        if break_rows:
            bands.append({"kind": "flow", "groups": [{"paragraph_ids": [row["paragraph_id"]
                for row in break_rows], "panel": False}]})
    else:
        bands = [{"kind": "flow", "groups": [{"paragraph_ids": [row["paragraph_id"]],
            "panel": index == 0} for index, row in enumerate(rows)]}]
    return {"version": PROPOSAL_VERSION, "page_number": page, "paragraphs": rows,
            "bands": bands}


class DistinctPageSDK(FakeSDK):
    def __init__(self, translations: tuple[str, ...]):
        super().__init__()
        self.translations = translations

    def create(self, **request):
        self.requests.append(request)
        text = self.translations[len(self.requests) - 1]
        return SimpleNamespace(id=f"fictional-translation-{len(self.requests)}", model="gpt-5.2",
            status="completed", service_tier="default", output=[],
            output_text=f"```text\n{text}\n```",
            usage={"input_tokens": 100, "output_tokens": 60, "total_tokens": 160,
                   "input_tokens_details": {"cached_tokens": 0},
                   "output_tokens_details": {"reasoning_tokens": 0}})


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.delenv("LEGALPDF_TRANSLATION_PROTOCOL", raising=False)
    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "run_translation_auth_test",
                        lambda *a, **k: pytest.fail("Unexpected authentication call"))
    monkeypatch.setattr(workflow_module, "resolve_openai_key_with_source",
                        lambda *a, **k: pytest.fail("Unexpected ambient credentials"))


def _app(tmp_path: Path, monkeypatch, outputs: tuple[str, ...], pages: tuple[int, ...],
         *, failed_page: int | None = None, failure: str | None = None,
         columns_by_page: dict[int, int] | None = None,
         hold_first_page: tuple[Event, Event] | None = None):
    sdk = DistinctPageSDK(outputs)
    monkeypatch.setattr(translation_service, "OpenAIResponsesClient", lambda **_:
        OpenAIResponsesClient(sdk_client=sdk, max_transport_retries=0,
                              pre_call_jitter_seconds=0))
    manager = translation_service.TranslationJobManager()
    slot = {}
    layout_requests = []

    def provider(job, policy):
        def create(**request):
            page = pages[min(len(layout_requests), len(pages) - 1)]
            layout_requests.append(request)
            if page == pages[0] and hold_first_page is not None:
                entered, release = hold_first_page
                entered.set()
                if not release.wait(20):
                    raise TimeoutError("fictional held layout was not released")
            if page == failed_page and failure == "timeout":
                raise TimeoutError("fictional layout transport timeout")
            if page == failed_page and failure == "malformed":
                content = "{malformed"
            else:
                layout = slot["app"].state.ordinary_layouts.manager_for_context(
                    slot["app"].state.shadow_context, job.mode, job.workspace_id)
                content = json.dumps(_proposal(layout.service.state(job.job_id)["review"], page,
                                               (columns_by_page or {}).get(page, 0)))
            response_status = "incomplete" if page == failed_page and failure == "incomplete" else "completed"
            return SimpleNamespace(id=f"fictional-layout-{page}", model=policy.model,
                status=response_status, service_tier="default", output=[], output_text=content,
                refusal="fictional refusal" if page == failed_page and failure == "refused" else None,
                incomplete_details=SimpleNamespace(reason="max_output_tokens") if response_status == "incomplete" else None,
                usage=None if page == failed_page and failure == "unknown_usage" else {
                       "input_tokens": 80, "output_tokens": 60, "total_tokens": 140,
                       "input_tokens_details": {"cached_tokens": 0},
                       "output_tokens_details": {"reasoning_tokens": 0}})
        return OpenAIResponsesClient(model=policy.model, sdk_client=SimpleNamespace(
            base_url="https://api.openai.com/v1/", responses=SimpleNamespace(create=create)),
            max_transport_retries=0, pre_call_jitter_seconds=0)

    services = replace(browser.offline_browser_app_services(state_root=tmp_path / "browser"),
        translation_jobs_factory=lambda: manager, ordinary_layout_provider_factory=provider,
        arabic_reviews_factory=browser.ArabicDocxReviewManager)
    app = browser.create_shadow_app(repo_root=tmp_path / "repo", services=services,
                                    enable_live_gmail_bridge=False)
    slot["app"] = app
    return app, manager, sdk, layout_requests


def _start(client, source, output, lang, *, start, end, image_mode, ocr_mode="off",
           page_breaks=False, resume=False):
    body = {"mode": "shadow", "workspace_id": "fictional", "form_values": {
        "source_path": str(source), "output_dir": str(output), "target_lang": lang,
        "image_mode": image_mode, "ocr_mode": ocr_mode, "workers": 1,
        "start_page": start, "end_page": end, "resume": resume, "page_breaks": page_breaks}}
    response = client.post("/api/translation/jobs/translate", json=body)
    assert response.status_code == 200, response.text
    return response.json()["normalized_payload"]["job"]["job_id"]


def _wait(manager, job_id):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        job = manager.get_job(job_id)
        if job and job["status"] in {"completed", "failed", "cancelled"}:
            return job
        time.sleep(.01)
    pytest.fail("Browser translation did not settle in time")


@pytest.mark.parametrize("lang,kinds,start,end,image_mode", [
    ("EN", ("digital", "digital"), 1, 2, "off"),
    ("FR", ("digital", "raster", "digital"), 2, 3, "always"),
    ("AR", ("vector", "raster"), 1, 2, "always"),
])
def test_fresh_browser_job_auto_layout_download_and_raw_binding(
    tmp_path, monkeypatch, lang, kinds, start, end, image_mode,
):
    source = tmp_path / "fictional.pdf"
    output = tmp_path / "output"
    output.mkdir()
    _source(source, kinds)
    selected = tuple(range(start, end + 1))
    translations = TRANSLATIONS[lang]
    app, manager, translation_sdk, layout_requests = _app(tmp_path, monkeypatch,
        translations, selected)
    if lang == "EN":
        monkeypatch.setattr(workflow_module, "build_ocr_engine",
                            lambda *a, **k: pytest.fail("Digital OCR-auto built an OCR engine"))
        monkeypatch.setattr(workflow_module, "ocr_pdf_page_text",
                            lambda *a, **k: pytest.fail("Digital OCR-auto dispatched OCR"))
    with TestClient(app) as client:
        job_id = _start(client, source, output, lang, start=start, end=end,
                        image_mode=image_mode, ocr_mode="auto" if lang == "EN" else "off")
        job = _wait(manager, job_id)
        assert job["status"] == "completed", job
        assert job["result"]["automatic_layout"]["status"] == "automatic_unreviewed", (job["result"]["automatic_layout"], job["diagnostics"])
        assert len(translation_sdk.requests) == len(selected)
        assert len(layout_requests) == len(selected)
        if "raster" in kinds or "vector" in kinds:
            assert any("image" in json.dumps(request) for request in translation_sdk.requests)
        scope = "?mode=shadow&workspace=fictional"
        status = client.get(f"/api/translation/jobs/{job_id}" + scope)
        assert status.status_code == 200, status.text
        shown = status.json()["normalized_payload"]["job"]
        assert shown.get("delivery", {}).get("kind") == "automatic_unreviewed", shown.get("diagnostics", {}).get("word_count_warning")
        assert shown["delivery"]["generation"] == 0
        download = client.get(f"/api/translation/jobs/{job_id}/artifact/output_docx" + scope)
        assert download.status_code == 200, download.text
        assert sha256(download.content).hexdigest() == shown["delivery"]["sha256"]
        text = _docx_text(download.content).replace("\u200e", "").replace("\u200f", "")
        for translated in translations:
            assert translated in text
        raw = manager.trusted_ordinary_layout_job(job_id, runtime_mode="shadow",
            workspace_id="fictional")
        assert raw.selected_pages == selected
        assert sha256(raw.original_docx).hexdigest() == raw.binding["original_sha256"]
        assert raw.original_docx != download.content
        assert raw.page_groups and tuple(sorted(raw.page_groups)) == selected
        assert job["result"]["save_seed"]["output_docx"] == shown["result"]["save_seed"]["output_docx"]
        if lang == "EN":
            candidate_path = Path(shown["artifacts"]["output_docx"])
            original_candidate = candidate_path.read_bytes()
            try:
                candidate_path.write_bytes(original_candidate + b"local tamper")
                stale_download = client.get(f"/api/translation/jobs/{job_id}/artifact/output_docx" + scope)
                assert stale_download.status_code != 200
            finally:
                candidate_path.write_bytes(original_candidate)
            seed = shown["result"]["save_seed"]
            save = {"mode": "shadow", "workspace_id": "fictional", "job_id": job_id,
                "baseline_id": shown["ordinary_layout"]["baseline_id"],
                "expected_delivery_generation": shown["delivery"]["generation"],
                "form_values": {**seed, "rate_per_word": ".027", "expected_total_mode": "auto"}}
            stale = client.post("/api/translation/save-row", json={**save,
                "expected_delivery_generation": shown["delivery"]["generation"] + 1})
            assert stale.status_code != 200
            saved = client.post("/api/translation/save-row", json=save)
            assert saved.status_code == 200, saved.text
            assert saved.json()["saved_result"]["row_id"]
            rebuilt = client.post(f"/api/translation/jobs/{job_id}/rebuild" + scope)
            assert rebuilt.status_code == 200, rebuilt.text
            rebuild_job = _wait(manager, rebuilt.json()["normalized_payload"]["job"]["job_id"])
            assert rebuild_job["status"] == "completed", rebuild_job
            assert rebuild_job["result"]["automatic_layout"]["status"] == "automatic_unreviewed"
            rebuilt_id = rebuild_job["job_id"]
            rebuilt_status = client.get(f"/api/translation/jobs/{rebuilt_id}" + scope)
            assert rebuilt_status.status_code == 200, rebuilt_status.text
            assert rebuilt_status.json()["normalized_payload"]["job"]["delivery"]["kind"] == "automatic_unreviewed"
            rebuilt_download = client.get(f"/api/translation/jobs/{rebuilt_id}/artifact/output_docx" + scope)
            assert rebuilt_download.status_code == 200 and sha256(rebuilt_download.content).hexdigest() == shown["delivery"]["sha256"]
            assert len(translation_sdk.requests) == len(selected)
            assert len(layout_requests) == len(selected)
        if lang == "AR":
            seed = shown["result"]["save_seed"]
            save = {
                "mode": "shadow", "workspace_id": "fictional", "job_id": job_id,
                "baseline_id": shown["ordinary_layout"]["baseline_id"],
                "expected_delivery_generation": shown["delivery"]["generation"],
                "form_values": {**seed, "rate_per_word": ".027", "expected_total_mode": "auto"}}
            blocked = client.post("/api/translation/save-row", json=save)
            assert blocked.status_code != 200
            data_path = app.state.shadow_context.services.detect_data_paths(
                mode="shadow", repo=app.state.shadow_context.repo_root,
                identity=app.state.shadow_context.build_identity).job_log_db_path
            before_db = data_path.read_bytes() if data_path.is_file() else None
            working_copy = Path(job["result"]["automatic_layout"]["review_copy_path"])
            assert working_copy.is_file()
            working_copy.unlink()
            missing_copy = client.post("/api/translation/save-row", json=save)
            assert missing_copy.status_code != 200
            assert "not found" in missing_copy.text.lower()
            assert (data_path.read_bytes() if data_path.is_file() else None) == before_db


def test_arabic_automatic_resume_alias_word_edit_continue_and_save(tmp_path, monkeypatch):
    source = tmp_path / "fictional_arabic.pdf"
    output = tmp_path / "output"
    output.mkdir()
    _source(source, ("digital",))
    app, manager, translation_sdk, layout_requests = _app(tmp_path, monkeypatch,
        TRANSLATIONS["AR"][:1], (1,))
    scope = "?mode=shadow&workspace=fictional"
    with TestClient(app) as client:
        original_id = _start(client, source, output, "AR", start=1, end=1, image_mode="off")
        original = _wait(manager, original_id)
        assert original["status"] == "completed"
        assert original["result"]["automatic_layout"]["status"] == "automatic_unreviewed"
        resumed_id = _start(client, source, output, "AR", start=1, end=1,
                            image_mode="off", resume=True)
        resumed = _wait(manager, resumed_id)
        assert resumed["status"] == "completed" and resumed["job_kind"] == "translate"
        assert resumed["result"]["automatic_layout"]["status"] == "automatic_unreviewed"
        assert len(translation_sdk.requests) == 1 and len(layout_requests) == 1
        original_docx = client.get(f"/api/translation/jobs/{original_id}/artifact/output_docx" + scope)
        resumed_docx = client.get(f"/api/translation/jobs/{resumed_id}/artifact/output_docx" + scope)
        assert original_docx.status_code == resumed_docx.status_code == 200
        assert resumed_docx.content == original_docx.content
        status = client.get(f"/api/translation/jobs/{resumed_id}" + scope)
        assert status.status_code == 200, status.text
        shown = status.json()["normalized_payload"]["job"]
        assert shown["delivery"]["kind"] == "automatic_unreviewed"
        origin_working = Path(original["result"]["automatic_layout"]["review_copy_path"])
        alias_working = Path(resumed["result"]["automatic_layout"]["review_copy_path"])
        assert origin_working != alias_working
        assert origin_working.read_bytes() == alias_working.read_bytes() == original_docx.content
        edited = _right_align_arabic_paragraph(alias_working.read_bytes())
        alias_working.write_bytes(edited)
        assert origin_working.read_bytes() == original_docx.content
        save = {"mode": "shadow", "workspace_id": "fictional", "job_id": resumed_id,
            "baseline_id": shown["ordinary_layout"]["baseline_id"],
            "expected_delivery_generation": shown["delivery"]["generation"],
            "form_values": {**shown["result"]["save_seed"], "rate_per_word": ".027",
                            "expected_total_mode": "auto"}}
        assert client.post("/api/translation/save-row", json=save).status_code != 200
        wrong_continuation = client.post("/api/translation/arabic-review/continue", json={
            "mode": "shadow", "workspace_id": "fictional", "job_id": resumed_id,
            "continuation": "continue_without_changes"})
        assert wrong_continuation.status_code != 200
        continued = client.post("/api/translation/arabic-review/continue", json={
            "mode": "shadow", "workspace_id": "fictional", "job_id": resumed_id,
            "continuation": "continue_now"})
        assert continued.status_code == 200, continued.text
        assert continued.json()["normalized_payload"]["arabic_review"]["resolved"] is True
        edited_download = client.get(f"/api/translation/jobs/{resumed_id}/artifact/output_docx" + scope)
        assert edited_download.status_code == 200 and edited_download.content == edited
        origin_download = client.get(f"/api/translation/jobs/{original_id}/artifact/output_docx" + scope)
        assert origin_download.status_code == 200 and origin_download.content == original_docx.content
        adopted = client.get(f"/api/translation/jobs/{resumed_id}" + scope)
        assert adopted.status_code == 200, adopted.text
        assert adopted.json()["normalized_payload"]["job"]["delivery"]["kind"] == "automatic_unreviewed_edited"
        saved = client.post("/api/translation/save-row", json=save)
        assert saved.status_code == 200, saved.text
        assert saved.json()["saved_result"]["row_id"]
        assert len(translation_sdk.requests) == 1 and len(layout_requests) == 1


def test_rich_nonfirst_page_breaks_columns_exact_fragments_and_combined_save_cost(tmp_path, monkeypatch):
    source = tmp_path / "fictional_columns.pdf"
    output = tmp_path / "output"
    output.mkdir()
    _rich_source(source)
    repeated = "The same clause belongs to its own physical source page."
    translations = (
        "\n".join(("Example Public Office", "Reference 12/2026/AB", "To the recipient office",
            "NOTICE OF PROCEDURE", "1. Important condition remains binding for this whole paragraph.",
            repeated, "Page 2 of 3", "Signed, Example Clerk")),
        "\n".join(("Example Appeals Office", "Reference 73/2026/CD", "To the second recipient",
            "ORDER AND REASONS", "2. A longer condition continues through the following decision.",
            repeated, "Page 3 of 3", "Signed, Example Registrar")),
    )
    app, manager, translation_sdk, layout_requests = _app(tmp_path, monkeypatch,
        translations, (2, 3), columns_by_page={2: 2, 3: 3})
    scope = "?mode=shadow&workspace=fictional"
    with TestClient(app) as client:
        job_id = _start(client, source, output, "EN", start=2, end=3,
                        image_mode="off", page_breaks=True)
        job = _wait(manager, job_id)
        assert job["status"] == "completed", job
        assert job["result"]["automatic_layout"]["status"] == "automatic_unreviewed", job["result"]["automatic_layout"]
        assert len(translation_sdk.requests) == len(layout_requests) == 2
        shown_response = client.get(f"/api/translation/jobs/{job_id}" + scope)
        assert shown_response.status_code == 200, shown_response.text
        shown = shown_response.json()["normalized_payload"]["job"]
        assert shown["delivery"]["kind"] == "automatic_unreviewed"
        raw = manager.trusted_ordinary_layout_job(job_id, runtime_mode="shadow",
            workspace_id="fictional")
        assert raw.selected_pages == (2, 3)
        assert all(len(raw.page_groups[page]) >= 8 for page in (2, 3))
        source_map = manager.trusted_ordinary_raw_map(job_id, runtime_mode="shadow",
            workspace_id="fictional")
        snapshot = bind_raw_page_map(raw.original_docx, source_map,
            source_pdf_sha256=raw.binding["source_sha256"], selected_pages=(2, 3), target_lang="EN")
        assert any(row.has_page_break for row in snapshot.paragraphs)
        layout = app.state.ordinary_layouts.manager_for_context(app.state.shadow_context,
            "shadow", "fictional")
        review_id = layout.service.state(job_id)["review"]["review_id"]
        candidate_id = job["result"]["automatic_layout"]["candidate_id"]
        candidate = layout.service.saved.verified_unreviewed_candidate(review_id, candidate_id)
        download = client.get(f"/api/translation/jobs/{job_id}/artifact/output_docx" + scope)
        assert download.status_code == 200 and download.content == candidate.docx_bytes
        assert sha256(download.content).hexdigest() == shown["delivery"]["sha256"]
        with ZipFile(BytesIO(raw.original_docx)) as original, ZipFile(BytesIO(download.content)) as rendered:
            assert original.namelist() == rendered.namelist()
            assert all(original.read(name) == rendered.read(name)
                       for name in original.namelist() if name != "word/document.xml")
            root = etree.fromstring(rendered.read("word/document.xml"))
        rows = candidate.source_map["paragraphs"]
        assert [row["paragraph_id"] for row in rows] == [row.id for row in snapshot.paragraphs]
        assert len({row["location"] for row in rows}) == len(rows)
        assert [row["raw_source_page_number"] for row in rows] == [row.page_number for row in snapshot.paragraphs]
        assert {row["raw_source_page_number"] for row in rows if row["raw_source_page_number"] is not None} == {2, 3}
        assert sum("w:tbl" in row["location"] for row in rows) >= 12
        assert len(list(root.iter(W + "tbl"))) >= 2
        located_text = []
        for entry, raw_row in zip(rows, snapshot.paragraphs):
            matches = root.getroottree().xpath(entry["location"], namespaces=root.nsmap)
            assert len(matches) == 1
            tokens = []
            for node in matches[0].iter():
                if node.tag == W + "t":
                    tokens.append(node.text or "")
                elif node.tag == W + "br":
                    tokens.append("\x0c" if node.get(W + "type") == "page" else "\n")
                elif node.tag == W + "tab":
                    tokens.append("\t")
            text = "".join(tokens)
            assert text == raw_row.text
            located_text.append(text)
        normalized_text = [text.rstrip("\x0c") for text in located_text]
        assert normalized_text.count(repeated) == 2
        assert [(row.page_number, row.text) for row in snapshot.paragraphs if row.text == repeated] == [
            (2, repeated), (3, repeated)]
        for fragment in translations[0].splitlines() + translations[1].splitlines():
            if fragment != repeated:
                assert normalized_text.count(fragment) == 1
        assert candidate.receipt["document_reviewed"] is False
        assert shown["layout_costs"]["complete"] is True
        translation_cost = Decimal(str(job["result"]["save_seed"]["api_cost"]))
        layout_cost = Decimal(str(shown["layout_costs"]["known_cost_usd"]))
        combined_cost = Decimal(str(shown["result"]["save_seed"]["api_cost"]))
        assert layout_cost > 0 and combined_cost == translation_cost + layout_cost
        save = client.post("/api/translation/save-row", json={"mode": "shadow",
            "workspace_id": "fictional", "job_id": job_id,
            "baseline_id": shown["ordinary_layout"]["baseline_id"],
            "expected_delivery_generation": shown["delivery"]["generation"],
            "form_values": {**shown["result"]["save_seed"], "rate_per_word": ".027",
                            "expected_total_mode": "auto"}})
        assert save.status_code == 200, save.text
        assert Decimal(str(save.json()["normalized_payload"]["api_cost"])) == combined_cost


@pytest.mark.parametrize("source_kind", ["raster", "vector"])
def test_standalone_text_unavailable_source_uses_image_without_ocr(tmp_path, monkeypatch, source_kind):
    source = tmp_path / "fictional_image_source.pdf"
    output = tmp_path / "output"
    output.mkdir()
    _source(source, (source_kind,))
    with fitz.open(source) as document:
        assert document[0].get_text().strip() == ""
    translated = "Standalone fictional image translation 19"
    app, manager, translation_sdk, layout_requests = _app(tmp_path, monkeypatch,
        (translated,), (1,))
    monkeypatch.setattr(workflow_module, "build_ocr_engine",
                        lambda *a, **k: pytest.fail("OCR-off built an OCR engine"))
    monkeypatch.setattr(workflow_module, "ocr_pdf_page_text",
                        lambda *a, **k: pytest.fail("OCR-off dispatched OCR"))
    with TestClient(app) as client:
        job_id = _start(client, source, output, "EN", start=1, end=1,
                        image_mode="always", ocr_mode="off")
        job = _wait(manager, job_id)
        assert job["status"] == "completed", job
        assert job["result"]["automatic_layout"]["status"] == "automatic_unreviewed"
        assert len(translation_sdk.requests) == len(layout_requests) == 1
        assert "image" in json.dumps(translation_sdk.requests[0])
        download = client.get(f"/api/translation/jobs/{job_id}/artifact/output_docx"
                              "?mode=shadow&workspace=fictional")
        assert download.status_code == 200 and translated in _docx_text(download.content)


def test_browser_cancel_during_first_layout_stops_before_second_page_and_keeps_raw(tmp_path, monkeypatch):
    source = tmp_path / "fictional_cancel.pdf"
    output = tmp_path / "output"
    output.mkdir()
    _source(source, ("digital", "digital"))
    entered, release = Event(), Event()
    app, manager, translation_sdk, layout_requests = _app(tmp_path, monkeypatch,
        TRANSLATIONS["EN"], (1, 2), hold_first_page=(entered, release))
    scope = "?mode=shadow&workspace=fictional"
    with TestClient(app) as client:
        job_id = _start(client, source, output, "EN", start=1, end=2, image_mode="off")
        try:
            assert entered.wait(20), "First layout request was not reached"
            active = manager.get_job(job_id)
            assert active["status"] == "formatting" and active["actions"]["cancel"]
            cancelled = client.post(f"/api/translation/jobs/{job_id}/cancel" + scope)
            assert cancelled.status_code == 200, cancelled.text
        finally:
            release.set()
        job = _wait(manager, job_id)
        assert job["status"] == "completed", job
        assert job["result"]["automatic_layout"]["status"] == "raw_fallback"
        assert "cancel" in job["status_text"].lower()
        assert len(translation_sdk.requests) == 2 and len(layout_requests) == 1
        raw = manager.trusted_ordinary_layout_job(job_id, runtime_mode="shadow",
            workspace_id="fictional")
        download = client.get(f"/api/translation/jobs/{job_id}/artifact/output_docx" + scope)
        assert download.status_code == 200 and download.content == raw.original_docx
        shown_response = client.get(f"/api/translation/jobs/{job_id}" + scope)
        assert shown_response.status_code == 200, shown_response.text
        shown = shown_response.json()["normalized_payload"]["job"]
        assert shown["ordinary_layout"]["delivery"] is None
        save = client.post("/api/translation/save-row", json={"mode": "shadow",
            "workspace_id": "fictional", "job_id": job_id,
            "baseline_id": shown["ordinary_layout"]["baseline_id"],
            "expected_delivery_generation": shown["ordinary_layout"]["delivery_generation"],
            "form_values": {**shown["result"]["save_seed"], "rate_per_word": ".027",
                            "expected_total_mode": "auto"}})
        assert save.status_code != 200


@pytest.mark.parametrize("failure", ["malformed", "unknown_usage", "timeout", "refused", "incomplete"])
def test_failed_layout_preserves_normal_raw_download_and_bounded_dispatch(tmp_path, monkeypatch, failure):
    source = tmp_path / "fictional.pdf"
    output = tmp_path / "output"
    output.mkdir()
    _source(source, ("digital", "digital"))
    app, manager, translation_sdk, layout_requests = _app(tmp_path, monkeypatch,
        TRANSLATIONS["EN"], (1, 2), failed_page=2, failure=failure)
    with TestClient(app) as client:
        job_id = _start(client, source, output, "EN", start=1, end=2, image_mode="off")
        job = _wait(manager, job_id)
        assert job["status"] == "completed", job
        assert job["result"]["automatic_layout"]["status"] == "raw_fallback"
        assert len(translation_sdk.requests) == 2
        assert len(layout_requests) == 2
        raw = manager.trusted_ordinary_layout_job(job_id, runtime_mode="shadow",
            workspace_id="fictional")
        download = client.get(f"/api/translation/jobs/{job_id}/artifact/output_docx"
                              "?mode=shadow&workspace=fictional")
        assert download.status_code == 200, download.text
        assert download.content == raw.original_docx
        assert job["result"]["automatic_layout"]["reason"]
        status = client.get(f"/api/translation/jobs/{job_id}?mode=shadow&workspace=fictional")
        assert status.status_code == 200, status.text
        shown = status.json()["normalized_payload"]["job"]
        save = client.post("/api/translation/save-row", json={
            "mode": "shadow", "workspace_id": "fictional", "job_id": job_id,
            "baseline_id": shown["ordinary_layout"]["baseline_id"],
            "expected_delivery_generation": shown["ordinary_layout"]["delivery_generation"],
            "form_values": {**shown["result"]["save_seed"], "rate_per_word": ".027",
                            "expected_total_mode": "auto"}})
        assert save.status_code != 200
