"""Synthetic wording on source-shaped geometry, never model-response evidence."""
from __future__ import annotations

from copy import deepcopy

import pytest

from legalpdf_translate.document_layout import (
    attach_page_layout, derive_page_layout, source_folio_ids, validate_page_layout,
)
from legalpdf_translate.document_structure import PageStructure, StructureBlock, text_sha256
from legalpdf_translate.section_furniture import plan_section_furniture


def _rehash(source):
    source["source_sha256"] = source["source_text_sha256"] = text_sha256(
        "\n".join(b["text"] for b in source["blocks"]))
    return source


def synthetic_source(number=5):
    """Twenty complete synthetic blocks; rounded, source-shaped point boxes.

    Four standalone separators deliberately retain their existing paragraph
    role. A source's printed folio may differ from its physical PDF page.
    """
    rows = [
        ("Ministério Público - Procuradoria da Comarca de Exemplo", "header", (138.96, 99, 470.16, 109.44)),
        ("Procuradoria de Exemplo", "header", (176.04, 113.04, 433.44, 122.04)),
        ("Documentos:", "heading", (70.92, 150.84, 165.96, 160.20)),
        ("1) Documento completo preservado.", "list_item", (107.28, 171, 524.16, 201.24)),
        ("2) Outro documento completo.", "list_item", (106.56, 211.32, 395.28, 222.84)),
        ("Testemunhas:", "heading", (70.92, 252, 168.48, 261.36)),
        ("a) Pessoa Exemplo;", "list_item", (107.28, 272.52, 203.76, 283.32)),
        ("b) Outra Pessoa, com identificação preservada.", "list_item", (106.92, 292.68, 524.52, 321.12)),
        ("*", "paragraph", (295.56, 333.36, 299.88, 338.04)),
        ("*", "paragraph", (295.56, 353.52, 299.88, 358.20)),
        ("O texto da decisão permanece integral e editável.", "paragraph", (70.92, 373.68, 524.16, 425.16)),
        ("*", "paragraph", (295.56, 455.04, 299.88, 459.72)),
        ("*", "paragraph", (295.56, 475.20, 299.88, 479.88)),
        ("Os fundamentos devem ser mantidos por inteiro.", "paragraph", (71.28, 515.16, 524.16, 567)),
        ("As condições não podem ser eliminadas ou resumidas.", "paragraph", (71.28, 576, 524.52, 668.16)),
        ("A informação subsequente mantém a mesma associação.", "paragraph", (71.28, 677.16, 524.16, 749.16)),
        ("- Condição integral preservada.", "list_item", (143.28, 758.16, 398.88, 769.32)),
        ("Largo do Exemplo, 1 - 1000-001 Cidade", "footer", (224.64, 803.16, 363.24, 810.36)),
        (f"{number - 2}/5", "footer", (531, 807.48, 547.20, 815.40)),
        ("Telef: 210000000 - E-mail: tribunal@example.invalid", "footer", (185.04, 812.88, 402.48, 820.08)),
    ]
    blocks = [StructureBlock(f"p{number:04d}_b{i:04d}", text, role=role, bbox=box,
                             alignment="center" if role in {"header", "footer"} else "left",
                             bold=role in {"header", "heading"})
              for i, (text, role, box) in enumerate(rows, 1)]
    source = PageStructure(number, "a" * 64, blocks, width_pt=595.44, height_pt=841.68,
                           source_file_sha256="b" * 64, provenance="synthetic_reviewed_geometry")
    return _rehash(source.to_dict())


def synthetic_pair(number=5):
    source = synthetic_source(number)
    target = deepcopy(source)
    for block in target["blocks"]:
        if block["role"] == "header":
            block["text"] = "الجهة القضائية المختصة" if block["id"].endswith("0001") else "مكتب الجهة القضائية"
        elif block["role"] not in {"footer"} and block["text"] != "*":
            block["text"] = "النص الكامل محفوظ وقابل للتحرير."
    target["translation_sha256"] = text_sha256("\n".join(b["text"] for b in target["blocks"]))
    return source, target


def test_source_shaped_folio_does_not_create_false_body_columns_or_lose_coverage():
    source = synthetic_source()
    before = deepcopy(source)
    assert source_folio_ids(source) == frozenset({"p0005_b0019"})
    attached = attach_page_layout(source).to_dict()
    layout = attached["metadata"].pop("layout")
    assert layout["status"] == "flow" and layout["warnings"] == []
    assert not layout["review_required"]
    assert validate_page_layout(layout, source) == layout
    assert attached == source == before
    assert len(attached["blocks"]) == len({b["id"] for b in attached["blocks"]}) == 20


@pytest.mark.parametrize("text", ["3/5", "3 de 5", "Pág. 3 de 5", "Página: 3", "Page 3 of 5", "page 3 sur 5"])
def test_exact_labelled_or_fraction_folio_is_positive_without_physical_number_assumption(text):
    source = synthetic_source(5)
    source["blocks"][18]["text"] = text
    _rehash(source)
    assert source_folio_ids(source) == frozenset({"p0005_b0019"})
    assert derive_page_layout(source)["status"] == "flow"


@pytest.mark.parametrize("text", [
    "3", "03/05", "0/5", "6/5", "3/0", "3/10000", "10000/10000", "3/5/7", "3/5.",
    "Ref. 3/5", "Referência: 3/5", "Artigo 3/5", "Lei 3/5", "Página 3 da decisão",
    "3/5 deve pagar", "Pág. 3: deve comparecer", "3 de 5 dias", "3/5\n4/5", "3\nde 5",
    "08.07.2026", "EUR 3/5", "[[3/5]]",
])
def test_bare_malformed_reference_citation_operative_or_wrapped_text_stays_geometry(text):
    source = synthetic_source()
    source["blocks"][18]["text"] = text
    _rehash(source)
    assert source_folio_ids(source) == frozenset()
    layout = derive_page_layout(source)
    assert layout["status"] == "needs_review"
    assert layout["warnings"] == ["ambiguous_side_by_side_geometry"]


@pytest.mark.parametrize("change", [
    "body_role", "table", "block_uncertain", "page_uncertain", "missing_box", "wrong_zone",
    "wide", "tall", "outside", "empty_box", "continuation", "document_start", "interior_start",
    "boundary_review", "missing_file", "wrong_text_hash", "stale_text", "translation",
])
def test_folio_exemption_requires_complete_certain_original_source_evidence(change):
    source = synthetic_source()
    block = source["blocks"][18]
    if change == "body_role": block["role"] = "paragraph"
    elif change == "table": block.update(role="table_cell", table_id="t1", row=0, col=0)
    elif change == "block_uncertain": block["uncertain"] = True
    elif change == "page_uncertain": source["uncertain"] = True
    elif change == "missing_box": block["bbox"] = None
    elif change == "wrong_zone": block["bbox"] = [531, 100, 547, 110]
    elif change == "wide": block["bbox"] = [100, 807, 547, 815]
    elif change == "tall": block["bbox"] = [531, 700, 547, 815]
    elif change == "outside": block["bbox"] = [531, 840, 547, 860]
    elif change == "empty_box": block["bbox"] = [531, 807, 531, 815]
    elif change == "continuation": block["continuation_of"] = source["blocks"][17]["id"]
    elif change == "document_start": block["document_start"] = True
    elif change == "interior_start": source["blocks"][10]["document_start"] = True
    elif change == "boundary_review": source["metadata"]["document_boundary_review_required"] = True
    elif change == "missing_file": source["source_file_sha256"] = ""
    elif change == "wrong_text_hash": source["source_text_sha256"] = "c" * 64
    elif change == "stale_text": block["text"] = "2/5"
    elif change == "translation": source["translation_sha256"] = source["source_sha256"]
    assert source_folio_ids(source) == frozenset()


@pytest.mark.parametrize("role,text", [("footer", "3/5"), ("footer", "Page 4"), ("paragraph", "3/5")])
def test_duplicate_or_conflicting_page_labels_never_choose_a_folio_owner(role, text):
    source = synthetic_source()
    duplicate = deepcopy(source["blocks"][18])
    duplicate.update(id="p0005_b0021", role=role, text=text, bbox=[20, 807, 55, 815])
    source["blocks"].append(duplicate)
    _rehash(source)
    assert source_folio_ids(source) == frozenset()
    assert derive_page_layout(source)["review_required"]


def test_folio_exemption_does_not_suppress_separate_real_body_parallel_text():
    source = synthetic_source()
    source["blocks"][10]["bbox"] = [70, 374, 250, 425]
    source["blocks"][13]["bbox"] = [330, 374, 525, 425]
    assert source_folio_ids(source) == frozenset({"p0005_b0019"})
    layout = derive_page_layout(source)
    assert layout["status"] == "needs_review"
    assert layout["warnings"] == ["ambiguous_side_by_side_geometry"]


def test_genuine_two_column_regions_keep_the_folio_and_every_block():
    blocks = [StructureBlock(f"p0005_b{i:04d}", f"Body {i}", bbox=box)
              for i, box in enumerate([(40, 100, 240, 130), (340, 100, 550, 130),
                                        (40, 160, 240, 190), (340, 160, 550, 190)], 1)]
    blocks.append(StructureBlock("p0005_b0005", "3/5", role="footer", bbox=(530, 800, 550, 810)))
    source = PageStructure(5, "a" * 64, blocks, source_file_sha256="b" * 64).to_dict()
    _rehash(source)
    assert source_folio_ids(source) == frozenset({"p0005_b0005"})
    layout = derive_page_layout(source)
    assert layout["status"] == "regions"
    owned = [identity for band in layout["bands"] for region in band["regions"] for identity in region["block_ids"]]
    assert len(owned) == len(set(owned)) == 5
    assert set(owned) == {b["id"] for b in source["blocks"]}
    assert validate_page_layout(layout, source) == layout


def test_semantic_table_cells_are_never_folios_or_removed_from_coverage():
    source = synthetic_source()
    for index, col in ((17, 0), (18, 1)):
        source["blocks"][index].update(role="table_cell", table_id="t1", row=0, col=col)
    assert source_folio_ids(source) == frozenset()
    attached = attach_page_layout(source).to_dict()
    assert [(b["id"], b["text"], b["table_id"], b["row"], b["col"]) for b in attached["blocks"]] == [
        (b["id"], b["text"], b["table_id"], b["row"], b["col"]) for b in source["blocks"]]
    assert len(attached["blocks"]) == 20


def test_changing_folios_do_not_poison_repeated_contact_signatures_or_input_coverage():
    pairs = [synthetic_pair(n) for n in (5, 6)]
    for source, target in pairs:
        target["metadata"]["layout"] = derive_page_layout(source)
    before = deepcopy(pairs)
    plan = plan_section_furniture(pairs)
    assert plan["policy"] == "source_section_furniture_v4"
    assert not plan["review_required"]
    section, = plan["sections"]
    assert section["consolidated"] and section["page_numbers"] == [5, 6]
    for page in plan["pages"]:
        prefix = f"p{page['page_number']:04d}_b"
        assert page["adopted_header_ids"] == [prefix + "0001", prefix + "0002"]
        assert page["adopted_footer_ids"] == [prefix + "0018", prefix + "0020"]
        assert prefix + "0019" not in page["adopted_footer_ids"]
    assert len(section["parts"]["footer"]["aliases"]) == 4
    assert pairs == before
    assert all(len(source["blocks"]) == len(target["blocks"]) == 20 for source, target in pairs)


@pytest.mark.parametrize("page_breaks", [False, True])
def test_single_page_adopts_only_footer_unless_explicitly_page_matched(page_breaks):
    source, target = synthetic_pair()
    target["metadata"]["layout"] = derive_page_layout(source)
    plan = plan_section_furniture([(source, target)], page_breaks=page_breaks)
    assert not plan["review_required"]
    assert plan["sections"][0]["consolidated"] is (not page_breaks)
    assert plan["pages"][0]["adopted_header_ids"] == []
    assert plan["pages"][0]["adopted_footer_ids"] == ([] if page_breaks else ["p0005_b0018", "p0005_b0020"])
    assert plan["sections"][0]["parts"]["header"] is None


def test_explicit_page_matching_still_prevents_multi_page_furniture_consolidation():
    plan = plan_section_furniture([synthetic_pair(n) for n in (5, 6)], page_breaks=True)
    assert not plan["review_required"]
    assert not any(s["consolidated"] for s in plan["sections"])


@pytest.mark.parametrize("text", ["Deve pagar no prazo de 5 dias.", "Artigo 281.º: obrigação integral.",
                                  "Telef: 210000000; deve comparecer."])
def test_positive_folio_never_licenses_operative_footer_adoption(text):
    pairs = []
    for number in (5, 6):
        source, target = synthetic_pair(number)
        source["blocks"][19]["text"] = text
        _rehash(source)
        target["source_sha256"] = target["source_text_sha256"] = source["source_sha256"]
        assert source_folio_ids(source) == frozenset({f"p{number:04d}_b0019"})
        pairs.append((source, target))
    plan = plan_section_furniture(pairs)
    assert plan["review_required"]
    assert not any(s["consolidated"] for s in plan["sections"])
    assert all(p["warnings"] == ["section_furniture_source_evidence_unavailable"] for p in plan["pages"])
