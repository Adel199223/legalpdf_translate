"""Opt-in field rows use a unique baseline witness, never global y rounding."""
from copy import deepcopy

import pytest

from legalpdf_translate.pdf_text_order import build_text_blocks_from_page_dict, SOURCE_FIELD_POLICY


def line(text, x, y, baseline, width=80, *, direction=(1., 0.)):
    return {"bbox": [x, y, x + width, y + 12], "dir": direction,
        "spans": [{"text": text, "origin": [x, baseline]}]}


def source(lines, width=595):
    return {"width": width, "blocks": [{"type": 0, "bbox": [20, 20, 550, 500], "lines": lines}]}


def text(data, policy=SOURCE_FIELD_POLICY):
    return build_text_blocks_from_page_dict(data, source_field_policy=policy)[0].text


def fixture():
    return source([line("Naturalidade:", 60, 409.17, 418.8, 60),
        line("Morada:", 60, 422.13, 431.76, 35),
        line("Avenida Clara, 10, 1.º Andar", 173, 422.09, 431.76, 190),
        line("Código Postal:1234 567 Cidade", 60, 435.0, 444.6, 180)])


def test_tiny_font_top_difference_does_not_invert_same_baseline_field_values():
    data = fixture()
    original = deepcopy(data)
    legacy = text(data, None)
    current = text(data)
    assert legacy.splitlines()[1:3] == ["Avenida Clara, 10, 1.º Andar", "Morada:"]
    assert current.splitlines()[1:3] == ["Morada:", "Avenida Clara, 10, 1.º Andar"]
    assert sorted(legacy.splitlines()) == sorted(current.splitlines())
    assert data == original


@pytest.mark.parametrize("mutation", ["different_baseline", "large_top_difference", "overlap", "far_column",
    "competing_label", "competing_value", "rotated", "missing_origin", "label_not_standalone", "nonadjacent_raw",
    "tab", "hard_separator"])
def test_ambiguous_columns_tables_and_unrelated_lines_keep_exact_legacy_order(mutation):
    data = fixture()
    rows = data["blocks"][0]["lines"]
    if mutation == "different_baseline": rows[2]["spans"][0]["origin"][1] += 1
    if mutation == "large_top_difference": rows[2]["bbox"][1] -= 1
    if mutation == "overlap": rows[2]["bbox"][0] = 90
    if mutation == "far_column": rows[2]["bbox"] = [310, 422.09, 500, 434.09]
    if mutation == "competing_label": rows.append(line("Nome:", 400, 422.1, 431.76, 35))
    if mutation == "competing_value": rows.append(line("Other cell", 400, 422.1, 431.76, 70))
    if mutation == "rotated": rows[2]["dir"] = (0., 1.)
    if mutation == "missing_origin": rows[2]["spans"][0].pop("origin")
    if mutation == "label_not_standalone": rows[1]["spans"][0]["text"] = "Morada: other words"
    if mutation == "nonadjacent_raw": rows.insert(2, line("Independent left column", 60, 450, 460, 150))
    if mutation == "tab": rows[2]["spans"][0]["text"] += "\tOther cell"
    if mutation == "hard_separator": rows[2]["spans"][0]["text"] += "\u2028Other row"
    assert text(data) == text(data, None)


def test_pairs_are_never_claimed_across_original_pdf_blocks():
    data = fixture()
    rows = data["blocks"][0]["lines"]
    data["blocks"] = [{"type": 0, "bbox": row["bbox"], "lines": [row]} for row in rows]
    assert [p.text for p in build_text_blocks_from_page_dict(data, source_field_policy=SOURCE_FIELD_POLICY)] == [
        p.text for p in build_text_blocks_from_page_dict(data)]


def test_wrapper_omits_absent_policy_but_forwards_explicit_pdf_policy(tmp_path, monkeypatch):
    from legalpdf_translate import pdf_text_order, source_document
    path = tmp_path / "fictional.pdf"
    path.write_bytes(b"%PDF-fictional")
    calls = []
    monkeypatch.setattr(pdf_text_order, "extract_ordered_page_text", lambda *args, **kwargs: calls.append(kwargs) or "fake")
    assert source_document.extract_ordered_source_text(path, 0) == "fake"
    assert source_document.extract_ordered_source_text(path, 0, source_field_policy=SOURCE_FIELD_POLICY) == "fake"
    assert calls == [{}, {"source_field_policy": SOURCE_FIELD_POLICY}]


def test_invalid_field_policy_is_not_silently_admitted():
    with pytest.raises(ValueError, match="source field policy"):
        text(fixture(), "unknown")
