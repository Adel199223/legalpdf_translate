from __future__ import annotations

from copy import deepcopy

import pytest

from legalpdf_translate.document_structure import PageStructure, StructureBlock, text_sha256
from legalpdf_translate.section_furniture import MAX_PAGES, plan_section_furniture


def _pair(number, *, header="Tribunal Judicial de Cidade", footer=True, document_start=False,
          file_hash="b" * 64, signature_before_header=False, variant="", metadata=None):
    rows = []
    if signature_before_header:
        rows.append(dict(text="Assinatura preservada", role="signature", bbox=(70, 50, 260, 72)))
    if header:
        rows.append(dict(text=header, role="header", bbox=(180, 95, 400, 115), alignment="center"))
    rows.append(dict(text="Texto integral da decisão, sem qualquer abreviação.", role="paragraph",
                     bbox=(70, 165, 530, 205), alignment="justify"))
    if footer:
        rows.extend([
            dict(text="Largo da Justiça, 1", role="address", bbox=(150, 802, 410, 810)),
            dict(text="Telef: 210000000 - E-mail: tribunal@example.invalid", role="footer",
                 bbox=(130, 812, 450, 820)),
        ])
    page = PageStructure(number, "a" * 64, [StructureBlock(f"p{number:04d}_b{i:04d}", **row)
                         for i, row in enumerate(rows, 1)], source_file_sha256=file_hash,
                         document_start=document_start, metadata=metadata or {})
    if document_start:
        page.blocks[0].document_start = True
    page.source_sha256 = page.source_text_sha256 = text_sha256(page.text)
    source = page.to_dict()
    target = deepcopy(source)
    for row in target["blocks"]:
        row["text"] = ("Target label " + variant if row["role"] == "header"
                       else "Target " + row["text"])
    _target_hash(target)
    return source, target


def _target_hash(target):
    target["translation_sha256"] = text_sha256("\n".join(b["text"] for b in target["blocks"]))


def _source_hash(source, target):
    source["source_sha256"] = source["source_text_sha256"] = text_sha256("\n".join(b["text"] for b in source["blocks"]))
    target["source_sha256"] = target["source_text_sha256"] = source["source_sha256"]


def _adopted(plan):
    return [s for s in plan["sections"] if s["consolidated"]]


def test_repeated_parts_are_source_bound_exact_once_deterministic_and_nonmutating():
    pairs = [_pair(n) for n in (1, 2, 3)]
    original = deepcopy(pairs)
    plan = plan_section_furniture(pairs)
    assert plan == plan_section_furniture(pairs)
    assert pairs == original
    assert not plan["review_required"]
    section, = _adopted(plan)
    assert (section["start_index"], section["end_index_exclusive"]) == (0, 3)
    assert section["page_numbers"] == [1, 2, 3]
    assert section["source_file_sha256"] == "b" * 64
    assert len(section["parts"]["header"]["aliases"]) == 3
    assert len(section["parts"]["footer"]["aliases"]) == 6
    for page, (source, target) in zip(plan["pages"], pairs):
        ids = page["adopted_header_ids"] + page["adopted_footer_ids"]
        assert len(ids) == len(set(ids)) == 3
        assert all(b["id"] not in ids for b in source["blocks"] if b["role"] == "paragraph")


def test_earliest_target_label_is_explicit_canonical_and_all_variants_survive():
    pairs = [_pair(1, variant="first"), _pair(2, variant="second")]
    plan = plan_section_furniture(pairs)
    part = _adopted(plan)[0]["parts"]["header"]
    assert part["canonical_blocks"][0]["text"] == "Target label first"
    assert part["canonical_page_index"] == 0
    assert [a["target_variant"] for a in part["aliases"]] == [False, True]
    assert [a["original_target_text"] for a in part["aliases"]] == ["Target label first", "Target label second"]
    assert all(a["source_text_sha256"] == text_sha256(pairs[0][0]["blocks"][0]["text"]) for a in part["aliases"])
    assert all(a["target_text_sha256"] == text_sha256(a["original_target_text"]) for a in part["aliases"])
    assert plan["review_required"]
    assert all(p["review_required"] and "section_furniture_target_variant_standardized" in p["warnings"]
               for p in plan["pages"])


@pytest.mark.parametrize("change", ["file", "geometry", "paper"])
def test_section_identity_binds_source_file_geometry_and_paper(change):
    pairs = [_pair(1), _pair(2)]
    old_id = _adopted(plan_section_furniture(pairs))[0]["section_id"]
    for pair in pairs:
        for page in pair:
            if change == "file": page["source_file_sha256"] = "d" * 64
            elif change == "geometry": page["blocks"][0]["bbox"][0] += 1
            else: page["width_pt"] += 1
    assert _adopted(plan_section_furniture(pairs))[0]["section_id"] != old_id


def test_first_header_document_start_is_supported_without_cross_document_adoption():
    plan = plan_section_furniture([_pair(1, document_start=True), _pair(2),
                                   _pair(3, document_start=True), _pair(4)])
    assert [s["page_numbers"] for s in _adopted(plan)] == [[1, 2], [3, 4]]
    assert plan["pages"][0]["adopted_header_ids"] == ["p0001_b0001"]
    assert not plan["review_required"]


@pytest.mark.parametrize("which", ["header", "footer"])
def test_header_only_and_footer_only_groups_are_supported(which):
    options = {"footer": False} if which == "header" else {"header": None}
    section, = _adopted(plan_section_furniture([_pair(1, **options), _pair(2, **options)]))
    assert section["parts"][which] is not None
    assert section["parts"]["footer" if which == "header" else "header"] is None


def test_headerless_middle_page_ends_old_section_and_does_not_inherit():
    pairs = [_pair(1), _pair(2), _pair(3, header=None, footer=False), _pair(4), _pair(5)]
    plan = plan_section_furniture(pairs)
    assert [s["page_numbers"] for s in plan["sections"]] == [[1, 2], [3], [4, 5]]
    assert len(_adopted(plan)) == 2
    assert plan["pages"][2]["adopted_header_ids"] == plan["pages"][2]["adopted_footer_ids"] == []
    assert plan["sections"][1]["parts"] == {"header": None, "footer": None}


@pytest.mark.parametrize("options", [
    {"header": "Tribunal Judicial de Outra Cidade"}, {"footer": False},
    {"header": None}, {"file_hash": "c" * 64}, {"document_start": True},
])
def test_changed_or_missing_furniture_file_and_document_start_partition(options):
    pairs = [_pair(1), _pair(2), _pair(3, **options), _pair(4, **{k:v for k,v in options.items() if k != "document_start"})]
    plan = plan_section_furniture(pairs)
    assert [s["page_numbers"] for s in plan["sections"]] == [[1, 2], [3, 4]]
    assert len(_adopted(plan)) == 2


def test_no_furniture_interval_can_be_contiguous_but_is_never_adopted():
    plan = plan_section_furniture([_pair(1, header=None, footer=False), _pair(2, header=None, footer=False)])
    assert len(plan["sections"]) == 1
    assert not _adopted(plan)
    assert not plan["review_required"]


def test_none_and_nonconsecutive_pages_are_barriers():
    plan = plan_section_furniture([_pair(1), _pair(2), None, _pair(4), _pair(5), _pair(8)])
    assert [s["page_numbers"] for s in plan["sections"]] == [[1, 2], [], [4, 5], [8]]
    assert len(_adopted(plan)) == 2
    assert plan["pages"][2]["review_required"]
    assert plan["pages"][2]["adopted_header_ids"] == []


def test_top_header_can_follow_signature_without_adopting_signature():
    pairs = [_pair(4, signature_before_header=True), _pair(5)]
    plan = plan_section_furniture(pairs)
    assert len(_adopted(plan)) == 1
    assert plan["pages"][0]["adopted_header_ids"] == ["p0004_b0002"]
    assert "p0004_b0001" not in plan["pages"][0]["adopted_footer_ids"]


@pytest.mark.parametrize("defect", ["source_hash", "target_hash", "file_hash", "missing_target_digest", "empty_target",
                                  "missing_block", "role", "bbox", "unknown_role", "uncertain", "interior_start"])
def test_stale_partial_or_uncertain_source_target_binding_fails_closed(defect):
    first, second = _pair(1), _pair(2)
    s, t = second
    if defect == "source_hash": s["source_sha256"] = "c" * 64
    elif defect == "target_hash": t["translation_sha256"] = "c" * 64
    elif defect == "file_hash": t["source_file_sha256"] = "c" * 64
    elif defect == "missing_target_digest": t["translation_sha256"] = None
    elif defect == "empty_target": t["blocks"][1]["text"] = ""; _target_hash(t)
    elif defect == "missing_block": t["blocks"].pop(); _target_hash(t)
    elif defect == "role": t["blocks"][0]["role"] = "paragraph"
    elif defect == "bbox": t["blocks"][0]["bbox"][0] += 1
    elif defect == "unknown_role": s["blocks"][0]["role"] = t["blocks"][0]["role"] = "unknown"
    elif defect == "uncertain": s["blocks"][0]["uncertain"] = t["blocks"][0]["uncertain"] = True
    else: s["blocks"][1]["document_start"] = t["blocks"][1]["document_start"] = True
    plan = plan_section_furniture([first, second])
    assert not _adopted(plan)
    assert plan["pages"][1]["review_required"]
    assert not plan["pages"][1]["adopted_header_ids"]


@pytest.mark.parametrize("text", ["Processo 999/20.2ABCD", "Tribunal Judicial - Processo 999/20.2ABCD",
                                  "Tribunal Judicial - prazo de recurso de dez dias", "Despacho judicial"])
def test_case_metadata_and_legal_content_are_never_promoted_from_header_role(text):
    plan = plan_section_furniture([_pair(1, header=text), _pair(2, header=text)])
    assert not _adopted(plan)
    assert plan["review_required"]


def test_reference_and_table_cells_remain_body_even_at_page_edge():
    pairs = [_pair(1), _pair(2)]
    for s, t in pairs:
        number=s["page_number"]
        for page in (s,t):
            page["blocks"].append(StructureBlock(f"p{number:04d}_b0099", "Processo 1/2020", role="reference", bbox=(60,40,300,55)).to_dict())
            page["blocks"].append(StructureBlock(f"p{number:04d}_b0100", "Legal table", role="table_cell", bbox=(60,780,300,800), table_id="t",row=0,col=0).to_dict())
        _source_hash(s,t);_target_hash(t)
    plan=plan_section_furniture(pairs)
    assert len(_adopted(plan))==1
    assert all(not any(i.endswith(("b0099","b0100")) for i in p["adopted_header_ids"]+p["adopted_footer_ids"]) for p in plan["pages"])


def test_substantive_footer_cannot_be_removed_with_contact_lines():
    pairs=[_pair(1),_pair(2)]
    for s,t in pairs:
        s["blocks"][-1]["text"] += " Prazo de recurso: dez dias."
        _source_hash(s,t)
    plan=plan_section_furniture(pairs)
    assert not _adopted(plan)
    assert plan["review_required"]


@pytest.mark.parametrize("text", ["Tribunal Judicial de Cidade\nNão pode conduzir.",
                                  "Tribunal Judicial - Compareça amanhã na secretaria.",
                                  "Tribunal Judicial condena o arguido.",
                                  "Tribunal Judicial\nTexto não institucional"])
def test_institution_prefix_cannot_hide_mixed_operative_source_prose(text):
    plan = plan_section_furniture([_pair(1, header=text), _pair(2, header=text)])
    assert not _adopted(plan)
    assert plan["review_required"]


@pytest.mark.parametrize("text", ["Telef: 210000000 - Não pode conduzir.",
                                  "Telef: 210000000 - Compareça amanhã.",
                                  "Largo da Justiça - Apresente o documento."])
def test_contact_prefix_cannot_hide_mixed_operative_source_prose(text):
    pairs = [_pair(1), _pair(2)]
    for source, target in pairs:
        source["blocks"][-1]["text"] = text
        _source_hash(source, target)
    plan = plan_section_furniture(pairs)
    assert not _adopted(plan)
    assert plan["review_required"]


@pytest.mark.parametrize("change", ["geometry", "alignment", "role"])
def test_unstable_source_furniture_does_not_get_deduplicated(change):
    pairs=[_pair(1),_pair(2)]
    for page in pairs[1]:
        if change=="geometry": page["blocks"][0]["bbox"][1]+=10
        elif change=="alignment": page["blocks"][0]["alignment"]="left"
        else: page["blocks"][-2]["role"]="footer"
    plan=plan_section_furniture(pairs)
    assert not _adopted(plan)
    assert plan["review_required"]


def test_transitive_geometry_drift_cannot_expand_one_group_indefinitely():
    pairs=[_pair(i) for i in range(1,5)]
    for offset,pair in enumerate(pairs):
        for page in pair:
            page["blocks"][0]["bbox"][0]+=3*offset
    plan=plan_section_furniture(pairs)
    assert [s["page_numbers"] for s in plan["sections"]]==[[1,2],[3,4]]


@pytest.mark.parametrize("dimension", ["width_pt", "height_pt"])
def test_transitive_paper_size_drift_is_anchored_to_first_page(dimension):
    pairs = [_pair(i) for i in range(1, 5)]
    for offset, pair in enumerate(pairs):
        for page in pair:
            page[dimension] += offset
    assert [s["page_numbers"] for s in plan_section_furniture(pairs)["sections"]] == [[1, 2], [3, 4]]


@pytest.mark.parametrize("block_index,text", [(0, "X" * 601), (-1, "X" * 601),
                                              (0, "\n".join(["line"] * 9))])
@pytest.mark.parametrize("occurrence", [0, 1])
def test_oversized_target_furniture_stays_in_body_for_review(block_index, text, occurrence):
    pairs = [_pair(1), _pair(2)]
    target = pairs[occurrence][1]
    target["blocks"][block_index]["text"] = text
    _target_hash(target)
    plan = plan_section_furniture(pairs)
    assert not _adopted(plan)
    assert plan["pages"][occurrence]["review_required"]
    assert not plan["pages"][occurrence]["adopted_header_ids"]


def test_regions_are_preserved_and_never_become_section_furniture():
    pairs=[_pair(1,metadata={"layout":{"status":"regions","review_required":False,"bands":[{}]}}),_pair(2)]
    plan=plan_section_furniture(pairs)
    assert not _adopted(plan)
    assert not plan["pages"][0]["review_required"]
    assert "section_furniture_region_preserved" in plan["pages"][0]["warnings"]


def test_page_matching_disables_consolidation():
    plan=plan_section_furniture([_pair(1),_pair(2)],page_breaks=True)
    assert not _adopted(plan)
    assert all(not p["adopted_header_ids"] and not p["adopted_footer_ids"] for p in plan["pages"])


def test_source_exact_means_whitespace_and_accents_are_not_normalized_for_adoption():
    assert not _adopted(plan_section_furniture([_pair(1),_pair(2,header="Tribunal  Judicial de Cidade")]))


def test_bounded_input_and_boolean_option():
    with pytest.raises(ValueError):plan_section_furniture([None]*(MAX_PAGES+1))
    with pytest.raises(ValueError):plan_section_furniture("not pages")
    with pytest.raises(ValueError):plan_section_furniture([],page_breaks=1)
    assert plan_section_furniture([])["sections"]==[]
