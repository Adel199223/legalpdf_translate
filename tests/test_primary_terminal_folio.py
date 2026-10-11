from pathlib import Path
from zipfile import ZipFile
import pytest
from docx import Document
from legalpdf_translate.docx_writer import assemble_docx
from legalpdf_translate.types import TargetLang

def build(tmp_path,labels,**options):
    pages=tmp_path/"pages";pages.mkdir()
    for page,label in labels.items():(pages/f"page_{page:04d}.txt").write_text("Body words.\n"+label,encoding="utf-8")
    out=tmp_path/"out.docx";assemble_docx(pages,out,lang=TargetLang.AR,page_breaks=True,terminal_folio_policy="terminal_labeled_folio_v1",page_numbers=list(labels),**options)
    with ZipFile(out) as z:parts={n:z.read(n) for n in z.namelist()}
    return out,parts

@pytest.mark.parametrize("labels",[{1:"الصفحة 1"},{2:"Page 2 / 7",7:"الصفحة ٧ / ٧"}])
def test_complete_labeled_folios_preserved_without_generated_page(tmp_path,labels):
    out,parts=build(tmp_path,labels)
    assert not any(b" PAGE " in raw for name,raw in parts.items() if name.startswith("word/footer"))
    text="\n".join(p.text for p in Document(out).paragraphs)
    for label in labels.values():assert label in text.replace("\u200e", "")

@pytest.mark.parametrize("labels",[{1:"1"},{1:"Article 1"},{1:"Page 2"},{1:"Page 1 reply required"},{2:"Page 2 / 7",7:"End"}])
def test_uncertain_or_incomplete_labels_keep_generated_page(tmp_path,labels):
    _,parts=build(tmp_path,labels);assert any(b"PAGE" in raw for name,raw in parts.items() if name.startswith("word/footer"))

def test_partial_keeps_page(tmp_path):
    _,parts=build(tmp_path,{1:"Page 1"},partial_output=True);assert any(b"PAGE" in raw for name,raw in parts.items() if name.startswith("word/footer"))

def test_legacy_default_is_unchanged(tmp_path):
    pages=tmp_path/"pages";pages.mkdir();(pages/"page_0001.txt").write_text("Body.\nPage 1")
    out=tmp_path/"old.docx";assemble_docx(pages,out,lang=TargetLang.EN,page_breaks=True)
    with ZipFile(out) as z:assert any(b"PAGE" in z.read(n) for n in z.namelist() if n.startswith("word/footer"))

@pytest.mark.parametrize("policy_kind,keep_page",[("current",False),("historical",True),("absent",True)])
def test_new_workflow_rebuild_uses_retained_recipe(tmp_path,policy_kind,keep_page):
    from types import SimpleNamespace
    from legalpdf_translate.workflow import TranslationWorkflow
    from legalpdf_translate.ordinary_auto_layout import frozen_automatic_layout_policy,_optional_hint_policy
    workflow=object.__new__(TranslationWorkflow)
    workflow._prepare_docx_layout=lambda *a,**k:{}
    workflow._record_docx_layout_review=lambda *a,**k:{}
    workflow._ordinary_auto_layout_policy=None
    policy=frozen_automatic_layout_policy() if policy_kind=="current" else _optional_hint_policy("ordinary_optional_layout_hint_normalization_v2",emphasis_normalization=True) if policy_kind=="historical" else None
    settings={"ordinary_auto_layout_policy":policy}
    if policy_kind=="current": settings["primary_assembly_recipe"]={"version":"terminal_labeled_folio_v1","ordinary_auto_layout_policy":policy}
    state=SimpleNamespace(settings=settings,pages={"1":{"status":"done"}},selection_page_count=1)
    pages=tmp_path/"pages";pages.mkdir();(pages/"page_0001.txt").write_text("Body.\nPage 1")
    config=SimpleNamespace(target_lang=TargetLang.EN,page_breaks=True,strip_bidi_controls=True)
    out,_=workflow._assemble_run_docx(config,pages_dir=pages,output_path=tmp_path/"out.docx",output_dir=tmp_path,run_dir=tmp_path,run_state=state,assembly_options={})
    with ZipFile(out) as z:assert any(b"PAGE" in z.read(n) for n in z.namelist() if n.startswith("word/footer")) is keep_page

def test_structured_furniture_recipe_is_not_changed_by_terminal_text_hint():
    from types import SimpleNamespace
    from legalpdf_translate.docx_writer import _terminal_labeled_folios_cover
    assert not _terminal_labeled_folios_cover([SimpleNamespace(number=1,text="Body.\nPage 1",structure={"blocks":[]})])
