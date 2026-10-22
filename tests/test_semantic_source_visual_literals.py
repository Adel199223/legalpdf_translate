"""Synthetic raster label through real correction, bidi, owner and quality guards."""
import base64
from dataclasses import replace
from io import BytesIO

import pytest

from legalpdf_translate import ordinary_semantic_review as review
from legalpdf_translate.output_normalize import LRI, PDI
from tests.test_ordinary_semantic_review import pack
from tests.test_ordinary_semantic_unit_refs import Client
from tests.test_ordinary_semantic_source_review_policy import run, snapshot


def token(value):
    return LRI + "[[" + value + "]]" + PDI


def visual_page():
    # This is a fictional valid PNG. The mock does not prove vision accuracy;
    # the test proves image-only evidence reaches unchanged product guards.
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (160, 80), "white")
    ImageDraw.Draw(image).text((24, 20), "Z", fill="black")
    encoded = BytesIO()
    image.save(encoded, format="PNG")
    data_url = "data:image/png;base64," + base64.b64encode(encoded.getvalue()).decode()
    return replace(pack()[0], source_text="A fictional office issued notice [[W]].",
        original_source_text="A fictional office issued notice W.", expected_ar_tokens=("W",),
        primary_text="أصدر المكتب إشعارا " + token("W") + ".", image_data_url=data_url)


def visual_claim():
    return {"claim_id": "visual_label", "source_unit_ids": [], "context_unit_ids": [],
        "source_image_evidence": [{"kind": "image", "page": 1, "bbox": [.1, .15, .4, .5]}],
        "proposition": "Visible margin routing label Z.", "axes": {"actor_recipient": "",
            "polarity_modality": "literal visual observation only", "temporal_state": "unspecified",
            "participant_number": "unspecified", "conditions": ""}, "unresolved": False}


def visual_response(stage, data, payload, *, defect=None):
    if stage == "source_inventory" and defect != "inventory_omission":
        data["claims"].append(visual_claim())
    elif stage == "correction":
        if defect != "candidate_omission":
            text = payload["primary_pages"][0]["text"] + "\n" + token("904" if defect == "numeric_guard" else "Z")
            if defect == "literal_loss": text = text.replace(token("W"), "")
            data["pages"][0] = {"page_number": 1, "status": "corrected", "corrected_text": text,
                                "reason_codes": ["omission"]}
        for claim in data["claim_coverage"]:
            if claim["claim_id"] == "visual_label": claim["status"] = "corrected"
    elif stage == "verification":
        if defect == "inventory_omission":
            data["inventory_errors"] = [{"source_unit_ids": [],
                "reason": "A separate readable margin label on source page 1 was omitted from the inventory."}]
        elif defect == "candidate_omission":
            next(row for row in data["claim_results"] if row["claim_id"] == "visual_label")["status"] = "missing"
        elif defect == "wrong_owner":
            next(row for row in data["claim_results"] if row["claim_id"] == "visual_label")["target_unit_ids"] = ["T002"]
    return data


def test_real_image_only_literal_corrects_and_verifies_without_bypassing_any_guard(tmp_path, monkeypatch):
    from legalpdf_translate import ordinary_semantic_audit as audit
    evaluator, quality = audit.evaluate_output, audit.run_all_quality_checks
    evaluated, checked = [], []
    def observe_evaluator(*args, **kwargs):
        result = evaluator(*args, **kwargs)
        evaluated.append((kwargs, result))
        return result
    def observe_quality(**kwargs):
        checked.append(kwargs)
        return quality(**kwargs)
    monkeypatch.setattr(audit, "evaluate_output", observe_evaluator)
    monkeypatch.setattr(audit, "run_all_quality_checks", observe_quality)
    page = visual_page()
    client = Client(visual_response)
    result = run(tmp_path / "audit", client, (page,))
    selected = result.selected_text_by_page[1]
    assert selected == page.primary_text + "\n" + token("Z")
    assert len(evaluated) == 1 and evaluated[0][1].ok
    assert evaluated[0][0]["primary_normalized_text"] == page.primary_text
    assert evaluated[0][0]["expected_ar_tokens"] == ["W"]
    assert "literal_wrapper_policy" not in evaluated[0][0]
    assert len(checked) == 2 and checked[0]["output_text"] == page.primary_text
    assert checked[1]["output_text"] == selected
    assert len(client.requests) == 3
    before = snapshot(tmp_path / "audit")
    assert run(tmp_path / "audit", pages=(page,)).reused
    assert snapshot(tmp_path / "audit") == before


@pytest.mark.parametrize("defect,error,calls", [
    ("literal_loss", "correction_literal_or_language_failure", 2),
    ("numeric_guard", "new_actionable_quality_failure", 2),
    ("candidate_omission", "review_independent_verification_failed", 3),
    ("inventory_omission", "review_independent_verification_failed", 3),
])
def test_visual_policy_keeps_real_loss_numeric_and_independent_omission_failures_closed(tmp_path, defect, error, calls):
    client = Client(lambda stage, data, payload: visual_response(stage, data, payload, defect=defect))
    with pytest.raises(review.SemanticAuditError, match=error):
        run(tmp_path / "audit", client, (visual_page(),))
    assert len(client.requests) == calls and not (tmp_path / "audit/manifest.json").exists()
    before = snapshot(tmp_path / "audit")
    with pytest.raises(review.SemanticAuditError, match=error):
        run(tmp_path / "audit", client, (visual_page(),))
    assert len(client.requests) == calls and snapshot(tmp_path / "audit") == before


def test_image_only_claim_cannot_be_invented_for_image_off(tmp_path):
    page = replace(visual_page(), image_data_url=None, visual_coverage="text_only_configured_image_off")
    from tests.test_ordinary_semantic_review import recipe
    client = Client(visual_response)
    with pytest.raises(review.SemanticAuditError, match="review_evidence"):
        run(tmp_path / "audit", client, (page,), recipe(configured_image_mode="off"))
    assert len(client.requests) == 1


def test_visual_claim_target_must_remain_on_its_image_owner_page(tmp_path):
    second = replace(visual_page(), page_number=2, primary_text="نص صفحة منفصلة.")
    client = Client(lambda stage, data, payload: visual_response(stage, data, payload, defect="wrong_owner"))
    # Put the wrong target on page 2 explicitly rather than relying on its short ID.
    original = client.damage
    def wrong_owner(stage, data, payload):
        data = original(stage, data, payload)
        if stage == "verification":
            target = next(unit["unit_id"] for unit in payload["target_units"] if unit["page"] == 2)
            next(row for row in data["claim_results"] if row["claim_id"] == "visual_label")["target_unit_ids"] = [target]
        return data
    client.damage = wrong_owner
    with pytest.raises(review.SemanticAuditError, match="review_page_ownership"):
        run(tmp_path / "audit", client, (visual_page(), second))
    assert not (tmp_path / "audit/manifest.json").exists()
