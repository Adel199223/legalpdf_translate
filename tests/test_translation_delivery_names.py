from pathlib import Path
from types import SimpleNamespace
import pytest
from legalpdf_translate.translation_service import translation_job_download_name
from legalpdf_translate.gmail_batch import stage_gmail_batch_translated_docx

@pytest.mark.parametrize("source,expected", [
    ("C:/mail/Notice.pdf", "Notice_AR.docx"),
    (r"C:\mail\Notice.pdf", "Notice_AR.docx"),
    ("../../nested/Legal notice.v2.pdf", "Legal notice.v2_AR.docx"),
    (".pdf", "pdf_AR.docx"),
    ("../...", "translation_AR.docx"),
    ("CON.pdf", "translation_AR.docx"),
    ("lpt9.extra.pdf", "translation_AR.docx"),
    ("<notice>:bad?.pdf", "_notice__bad__AR.docx"),
    ("Inquérito.pdf", "Inquérito_AR.docx"),
])
def test_trusted_source_name_not_selected_storage_name(source,expected):
    job={"config":{"source_path":source,"target_lang":"AR"},"result":{"save_seed":{"output_docx":"immutable/output.docx"}}}
    assert translation_job_download_name(job)==expected


def test_selected_bytes_staged_under_download_name_with_collision(tmp_path):
    selected=tmp_path/"immutable"/"output.docx";selected.parent.mkdir();selected.write_bytes(b"exact selected revision")
    session=SimpleNamespace(download_dir=tmp_path/"batch")
    job={"config":{"source_path":"original.pdf","target_lang":"FR"}}
    name=translation_job_download_name(job)
    first=stage_gmail_batch_translated_docx(session=session,translated_docx_path=selected,attachment_name=name)
    second=stage_gmail_batch_translated_docx(session=session,translated_docx_path=selected,attachment_name=name)
    assert first.name=="original_FR.docx" and second.name=="original_FR_01.docx"
    assert first.read_bytes()==second.read_bytes()==selected.read_bytes()
    # Existing Qt/internal callers retain their prior filename contract.
    legacy=stage_gmail_batch_translated_docx(session=session,translated_docx_path=selected)
    assert legacy.name=="output.docx" and legacy.read_bytes()==selected.read_bytes()

@pytest.mark.parametrize("name",["../evil.docx",r"nested\evil.docx","evil.pdf"])
def test_staging_refuses_path_names(tmp_path,name):
    selected=tmp_path/"output.docx";selected.write_bytes(b"same")
    with pytest.raises(ValueError,match="filename"):
        stage_gmail_batch_translated_docx(session=SimpleNamespace(download_dir=tmp_path/"batch"),translated_docx_path=selected,attachment_name=name)


def test_fee_filename_template_labels_keep_existing_ids():
    template=(Path(__file__).parents[1]/"src/legalpdf_translate/shadow_web/templates/index.html").read_text(encoding='utf-8')
    for field in ("gmail-final-output-filename","gmail-batch-final-output-filename"):
        assert f'<label for="{field}">Honorários DOCX filename</label>' in template
        assert f'id="{field}" type="text" placeholder="Optional filename for the honorários DOCX"' in template
    assert "Final DOCX filename" not in template


def test_windows_utf16_filename_limit_and_reserved_aliases():
    name=translation_job_download_name({"config":{"source_path":"\U0001f600"*125+".pdf","target_lang":"AR"}})
    assert len(name.encode("utf-16-le"))//2<=255
    assert name[:-8]=="\U0001f600"*80
    for source in ("COM¹.pdf","LPT².pdf"):
        assert translation_job_download_name({"config":{"source_path":source,"target_lang":"AR"}})=="translation_AR.docx"
