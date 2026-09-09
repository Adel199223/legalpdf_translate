"""Synthetic pixel/TSV policy tests; no real OCR or model-quality claim."""
from copy import deepcopy
import hashlib
import io

from PIL import Image, ImageDraw
import pytest

from legalpdf_translate.document_structure import structure_from_tesseract_tsv, text_sha256
from legalpdf_translate.source_layout_eligibility import derive_layout_eligibility, valid_layout_eligibility


def simple_page():
    """Return (source, PNG, identity) for same-pass parser/integration fixtures."""
    width, height = 600, 840
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    rows = ["level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext",
            f"1\t1\t0\t0\t0\t0\t0\t0\t{width}\t{height}\t-1\t"]
    phrases = [(1, 1, 40, "Tribunal Judicial"), (2, 1, 140, "O destinatário deve apresentar documentos."),
               (2, 2, 160, "O prazo começa após a receção."), (3, 1, 775, "Largo do Exemplo - Beja")]
    evidence = []
    for group, line, top, text in phrases:
        left = 55
        for number, word in enumerate(text.split(), 1):
            word_width = max(6, len(word) * 4)
            box = [left, top, left + word_width, top + 10]
            draw.rectangle((left + 1, top + 1, left + word_width - 1, top + 9), fill="black")
            rows.append(f"5\t1\t{group}\t1\t{line}\t{number}\t{left}\t{top}\t{word_width}\t10\t99\t{word}")
            evidence.append({"block_id": f"p0001_b{group:04d}", "text": word, "bbox_px": box,
                             "confidence": 99.0, "group": [group, 1, line], "word_number": number})
            left += word_width + 6
    tsv = "\n".join(rows) + "\n"
    source = structure_from_tesseract_tsv(tsv, source_file_sha256="a" * 64)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    pixels = buffer.getvalue()
    image_hash = hashlib.sha256(pixels).hexdigest()
    identity = {"source_file_sha256": "a" * 64, "image_sha256": image_hash,
                "source_type": "browser_pdf_image", "paper_size_basis": "a4_assumed"}
    source.uncertain = True
    source.metadata.update(local_pass="pt_latin_primary", psm=6, language_pack="por+eng+fra",
        selected_text_sha256=text_sha256(source.text), image_sha256=image_hash,
        text_binding="ordered_non_whitespace_tokens", warnings=["local_ocr_reading_order_requires_review"],
        source_page_identity=identity,
        ocr_word_evidence={"version": 1, "tsv_sha256": hashlib.sha256(tsv.encode()).hexdigest(),
                           "image_size_px": [width, height], "words": evidence})
    return source, pixels, identity


def test_simple_eligibility_keeps_uncertainty_and_source_bytes():
    source, pixels, identity = simple_page()
    before = deepcopy(source.to_dict())
    record = derive_layout_eligibility(source, image_bytes=pixels, source_identity=identity)
    assert record["status"] == "eligible_simple_flow", record
    assert valid_layout_eligibility(source, record)
    assert source.uncertain and source.to_dict() == before
    assert record["scope"] == ["simple_flow", "section_furniture", "confirmed_continuation"]


@pytest.mark.parametrize("mutation", [
    lambda s: s.metadata["ocr_word_evidence"]["words"][0].update(confidence=89),
    lambda s: s.metadata["ocr_word_evidence"]["words"][0].update(text="Different"),
    lambda s: s.metadata["ocr_word_evidence"]["words"][0].update(block_id="p0001_b0002"),
    lambda s: s.metadata["ocr_word_evidence"]["words"][1].update(word_number=1),
    lambda s: s.metadata["ocr_word_evidence"]["words"][0].update(bbox_px=[1, 1, 2, 2]),
    lambda s: s.metadata.update(warnings=["unknown_layout_problem"]),
    lambda s: s.metadata.update(document_boundary_review_required=True),
    lambda s: setattr(s.blocks[1], "uncertain", True),
    lambda s: setattr(s.blocks[1], "document_start", True),
    lambda s: setattr(s.blocks[1], "text", s.blocks[1].text + " extra"),
    lambda s: s.metadata.pop("ocr_word_evidence"),
    lambda s: s.metadata.update(psm=3),
    lambda s: s.metadata.update(text_binding="unknown"),
    lambda s: s.metadata["source_page_identity"].update(source_type="pdf"),
])
def test_source_gate_rejects_uncertain_or_mismatched_evidence(mutation):
    source, pixels, identity = simple_page()
    mutation(source)
    record = derive_layout_eligibility(source, image_bytes=pixels, source_identity=identity)
    assert record["status"] == "needs_review"
    assert not valid_layout_eligibility(source, record)


def test_wrong_raster_rejected_even_with_same_dimensions():
    source, pixels, identity = simple_page()
    record = derive_layout_eligibility(source, image_bytes=pixels + b"x", source_identity=identity)
    assert record["reasons"] == ["ocr_input_raster_mismatch"]


@pytest.mark.parametrize("shape", ["horizontal", "vertical", "unexplained"])
def test_pixel_rulings_or_unrecognized_regions_rejected(shape):
    source, pixels, identity = simple_page()
    image = Image.open(io.BytesIO(pixels)).convert("RGB")
    draw = ImageDraw.Draw(image)
    box = {"horizontal": (50, 300, 500, 300), "vertical": (500, 280, 500, 600), "unexplained": (480, 420, 490, 430)}[shape]
    draw.rectangle(box, fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    changed = buffer.getvalue()
    source.metadata["image_sha256"] = hashlib.sha256(changed).hexdigest()
    source.metadata["source_page_identity"]["image_sha256"] = source.metadata["image_sha256"]
    record = derive_layout_eligibility(source, image_bytes=changed, source_identity=identity)
    assert record["reasons"] == ["raster_has_unexplained_ink_or_rulings"]


@pytest.mark.parametrize("field", ["policy", "status", "record_sha256"])
def test_modified_record_rejected(field):
    source, pixels, identity = simple_page()
    record = derive_layout_eligibility(source, image_bytes=pixels, source_identity=identity)
    record[field] = "modified"
    assert not valid_layout_eligibility(source, record)


def test_record_cannot_be_reused_after_same_text_geometry_change():
    source, pixels, identity = simple_page()
    record = derive_layout_eligibility(source, image_bytes=pixels, source_identity=identity)
    source.blocks[1].bbox = tuple(n + 2 for n in source.blocks[1].bbox)
    assert not valid_layout_eligibility(source, record)


def test_target_can_reuse_source_proof_without_certifying_translation():
    source, pixels, identity = simple_page()
    record = derive_layout_eligibility(source, image_bytes=pixels, source_identity=identity)
    target = deepcopy(source)
    for block in target.blocks:
        block.text = "Unreviewed target text"
    target.translation_sha256 = text_sha256(target.text)
    assert valid_layout_eligibility(target, record)
    assert target.uncertain


def _sync_source_from_words(source):
    """Make malformed geometry internally consistent, not merely stale."""
    width, height = source.metadata["ocr_word_evidence"]["image_size_px"]
    for block in source.blocks:
        words = [word for word in source.metadata["ocr_word_evidence"]["words"] if word["block_id"] == block.id]
        block.text = " ".join(word["text"] for word in words)
        boxes = [word["bbox_px"] for word in words]
        block.bbox = (min(b[0] for b in boxes) / width * source.width_pt,
                      min(b[1] for b in boxes) / height * source.height_pt,
                      max(b[2] for b in boxes) / width * source.width_pt,
                      max(b[3] for b in boxes) / height * source.height_pt)
    source.source_sha256 = source.source_text_sha256 = text_sha256(source.text)
    source.metadata["selected_text_sha256"] = text_sha256(source.text)


@pytest.mark.parametrize("case,reason", [
    ("column", "multiple_body_columns_or_alignment"),
    ("overlap", "line_overlap_or_reading_order"),
    ("table", "unresolved_table_text"),
])
def test_consistent_complex_geometry_still_rejected(case, reason):
    source, pixels, identity = simple_page()
    words = source.metadata["ocr_word_evidence"]["words"]
    for word in words:
        if word["group"] == [2, 1, 2]:
            if case == "column":
                word["bbox_px"][0] += 200
                word["bbox_px"][2] += 200
            elif case == "overlap":
                word["bbox_px"][1] -= 20
                word["bbox_px"][3] -= 20
    if case == "table":
        words[2]["text"] += "|"
    _sync_source_from_words(source)
    record = derive_layout_eligibility(source, image_bytes=pixels, source_identity=identity)
    assert record["reasons"] == [reason]
    assert not valid_layout_eligibility(source, record)


def test_certain_page_does_not_bypass_missing_word_evidence():
    source, pixels, identity = simple_page()
    source.uncertain = False
    source.metadata.pop("ocr_word_evidence")
    record = derive_layout_eligibility(source, image_bytes=pixels, source_identity=identity)
    assert record["status"] == "needs_review"


def test_rehashed_eligible_status_does_not_bypass_source_gates():
    from legalpdf_translate.source_layout_eligibility import _digest
    source, pixels, identity = simple_page()
    record = derive_layout_eligibility(source, image_bytes=pixels, source_identity=identity)
    source.blocks[1].uncertain = True
    record["record_sha256"] = _digest({key: value for key, value in record.items() if key != "record_sha256"})
    assert not valid_layout_eligibility(source, record)


@pytest.mark.parametrize("change", [
    lambda record: record.update(version=True),
    lambda record: record["pixel_diagnostics"].update(version=True),
    lambda record: record["pixel_diagnostics"].update(maximum_horizontal_stroke_px=601),
    lambda record: record["pixel_diagnostics"].update(maximum_vertical_stroke_px=841),
    lambda record: record["pixel_diagnostics"].update(maximum_horizontal_stroke_px=0),
    lambda record: record["pixel_diagnostics"].update(maximum_vertical_stroke_px=0),
    lambda record: record["pixel_diagnostics"].update(dark_pixels=True),
])
def test_malformed_rehashed_record_is_not_eligible(change):
    from legalpdf_translate.source_layout_eligibility import _digest
    source, pixels, identity = simple_page()
    record = derive_layout_eligibility(source, image_bytes=pixels, source_identity=identity)
    change(record)
    record["record_sha256"] = _digest({key: value for key, value in record.items() if key != "record_sha256"})
    assert not valid_layout_eligibility(source, record)


@pytest.mark.parametrize("change", [
    lambda source: source.metadata.update(warnings=[{}]),
    lambda source: source.metadata.update(local_pass={}),
    lambda source: source.metadata.update(image_sha256=[]),
    lambda source: source.metadata["source_page_identity"].update(extra=float("nan")),
    lambda source: source.metadata["ocr_word_evidence"].update(version=True),
    lambda source: source.metadata["ocr_word_evidence"]["words"][0].update(confidence=True),
    lambda source: source.metadata.update(extraction_version=float("nan")),
    lambda source: source.metadata.update(extraction_version="unknown_version"),
    lambda source: source.metadata.pop("extraction_version"),
    lambda source: source.metadata.update(psm=6.0),
    lambda source: source.metadata.update(psm=11.0),
    lambda source: source.metadata.update(psm=True),
])
def test_malformed_optional_metadata_fails_closed(change):
    source, pixels, identity = simple_page()
    change(source)
    record = derive_layout_eligibility(source, image_bytes=pixels, source_identity=identity)
    assert record["status"] == "needs_review"
    assert not valid_layout_eligibility(source, record)


@pytest.mark.parametrize("key", ["local_pass", "language_pack"])
def test_unserializable_binding_has_content_free_failure_record(key):
    source, pixels, identity = simple_page()
    source.metadata[key] = "\ud800"
    record = derive_layout_eligibility(source, image_bytes=pixels, source_identity=identity)
    assert record["status"] == "needs_review"
    assert record["bindings"] == {} and record["pixel_diagnostics"] == {}
    assert record["reasons"] == ["invalid_layout_eligibility_evidence"]
    assert not valid_layout_eligibility(source, record)


def test_returned_record_does_not_alias_input_identity_or_metadata():
    source, pixels, identity = simple_page()
    before = deepcopy(source.to_dict())
    identity_before = deepcopy(identity)
    record = derive_layout_eligibility(source, image_bytes=pixels, source_identity=identity)
    record["bindings"]["source_identity"]["image_sha256"] = "b" * 64
    record["bindings"]["extraction"]["warnings"].append("changed_by_consumer")
    assert source.to_dict() == before and identity == identity_before
