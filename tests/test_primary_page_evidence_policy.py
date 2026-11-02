"""Fresh PDF extraction keeps proven date/time fields in source reading order."""
from collections import Counter
from dataclasses import replace

import fitz
import pytest

from legalpdf_translate import pdf_text_order as order, source_document as source
from legalpdf_translate.arabic_pre_tokenize import extract_locked_tokens, pretokenize_arabic_source
from legalpdf_translate.checkpoint import SemanticAuditRecipeError, ordinary_semantic_audit_recipe
from legalpdf_translate.types import ImageMode
from legalpdf_translate.workflow_semantic_audit import fresh_recipe
from tests.test_workflow_semantic_review_integration import saved_recipe


OPTIONS = {"source_field_policy": order.SOURCE_FIELD_POLICY,
           "source_question_row_policy": order.SOURCE_QUESTION_ROW_POLICY}
POLICY = order.PRIMARY_PAGE_EVIDENCE_POLICY
KEY = "primary_page_evidence_policy"
RANGE = "Between 2025-12-03 / 10:00h and 2025-12-03 / 10:45h"


def make_pdf(tmp_path, value=RANGE, *, copies=1, rotation=0):
    path = tmp_path / "form.pdf"
    with fitz.open() as doc:
        page = doc.new_page(width=600, height=840)
        page.insert_text((60, 100), "Document heading 3")
        page.insert_text((60, 160), "Appointment")
        for row in range(copies):
            y = 180 + row * 25
            page.insert_text((60, y), "Date/Time:")
            page.insert_text((160, y), value)
        page.set_rotation(rotation)
        doc.save(path)
    return path


@pytest.mark.parametrize("copies", [1, 2])
def test_public_pdf_source_keeps_printed_field_occurrences_below_heading(tmp_path, copies):
    path = make_pdf(tmp_path, copies=copies)
    old = source.extract_ordered_source_text(path, 0, **OPTIONS)
    new = source.extract_ordered_source_text(path, 0, **OPTIONS, primary_page_evidence_policy=POLICY)
    assert old.text.index(RANGE) < old.text.index("Document heading")
    assert new.text.index("Document heading") < new.text.index("Appointment") < new.text.index(RANGE)
    assert old.barcode_blocks_count - new.barcode_blocks_count == copies
    assert new.text.count(RANGE) == copies and Counter(old.text.splitlines()) == Counter(new.text.splitlines())
    def tokens(text):
        return extract_locked_tokens(pretokenize_arabic_source(text, source_field_policy=order.SOURCE_FIELD_POLICY))
    before, after = tokens(old.text), tokens(new.text)
    assert Counter(before) == Counter(after)
    assert before.index("3") > before.index("2025-12-03") and after.index("3") < after.index("2025-12-03")


@pytest.mark.parametrize("value,rotation", [
    ("2025-12-03", 0), ("2025-02-30 at 10:00h", 0), ("2025-12-03 at 26:81", 0),
    ("2025-12-03 at 10:00h RE123456789PT", 0), ("2025-12-03 at 10:00h ABC-123456", 0),
    ("2025-12-03 at 10:00h %*TRACK*%", 0), (RANGE, 90),
])
def test_ambiguous_or_rotated_field_preserves_historical_extraction(tmp_path, value, rotation):
    path = make_pdf(tmp_path, value, rotation=rotation)
    old = source.extract_ordered_source_text(path, 0, **OPTIONS)
    new = source.extract_ordered_source_text(path, 0, **OPTIONS, primary_page_evidence_policy=POLICY)
    assert not old.extraction_failed and old.barcode_blocks_count > 0
    assert new == old


def test_browser_bundle_rectangles_do_not_grant_native_baseline_proof(tmp_path, monkeypatch):
    path = tmp_path / "bundle.pdf"
    items = [dict(text=text, x=x, y=y, width=width, height=12, dir="ltr", has_eol=True)
             for text, x, y, width in [("Heading", 60, 100, 70), ("Date/Time:", 60, 180, 60),
                                       (RANGE, 160, 180, 235)]]
    evidence = dict(version=1, page_number=1, page_width=600, page_height=840, items=items)
    monkeypatch.setattr(source, "source_has_browser_pdf_bundle", lambda _: True)
    monkeypatch.setattr(source, "browser_pdf_bundle_page_text", lambda *_: evidence)
    old = source.extract_ordered_source_text(path, 0, **OPTIONS)
    new = source.extract_ordered_source_text(path, 0, **OPTIONS, primary_page_evidence_policy=POLICY)
    assert not old.extraction_failed and old.barcode_blocks_count == 1 and new == old


@pytest.mark.parametrize("mode", [ImageMode.OFF, ImageMode.AUTO, ImageMode.ALWAYS])
def test_fresh_recipe_selects_saved_evidence_policy_in_each_mode(tmp_path, mode):
    config, _, settings = saved_recipe(tmp_path)
    settings["image_mode"] = mode.value
    settings["ocr_engine"] = config.ocr_engine.value
    saved = fresh_recipe(replace(config, image_mode=mode), "gpt-5.2", settings["ordinary_auto_layout_policy"],
                         context_text="Fictional context.", context_hash=settings["ordinary_semantic_audit_recipe"]["context_sha256"])
    settings["ordinary_semantic_audit_recipe"] = saved
    assert saved[KEY] == POLICY and ordinary_semantic_audit_recipe(settings) == saved
    saved.pop(KEY)
    assert ordinary_semantic_audit_recipe(settings) == saved


@pytest.mark.parametrize("fault", ["null", "unknown", "bool", "missing_question", "old_packaging"])
def test_explicit_bad_evidence_policy_never_inherits_historical_absence(tmp_path, fault):
    config, saved, settings = saved_recipe(tmp_path)
    settings["ocr_engine"] = config.ocr_engine.value
    assert ordinary_semantic_audit_recipe(settings) == saved
    if fault == "missing_question":
        saved.pop("source_question_row_policy")
    elif fault == "old_packaging":
        saved["primary_literal_packaging_version"] = "lossless_source_components_v2"
    else:
        saved[KEY] = {"null": None, "unknown": "future", "bool": True}[fault]
    with pytest.raises(SemanticAuditRecipeError, match=KEY):
        ordinary_semantic_audit_recipe(settings)
