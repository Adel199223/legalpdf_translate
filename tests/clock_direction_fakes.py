"""Fictional raw input only; derivatives use public product binding/build APIs."""
from io import BytesIO
from hashlib import sha256
from docx import Document
from docx.shared import Pt
from lxml import etree
import fitz

from legalpdf_translate import saved_docx_layout as model
from legalpdf_translate.docx_writer import _configure_styles, _add_page_number_footer
from legalpdf_translate.ordinary_auto_layout_artifacts import bind_raw_page_map


def split_inputs():
    doc=Document();_configure_styles(doc,'AR');_add_page_number_footer(doc,'AR')
    paragraph=doc.add_paragraph()
    etree.SubElement(paragraph._p.get_or_add_pPr(),model.W+'bidi').set(model.W+'val','1')
    for text,rtl in [('موعد خيالي يبدأ عند ',1),('\u200e09\u200e',0),(':',1),('\u200e30h\u200e',0),
                     (' وينتهي عند ',1),('\u200e10\u200e',0),(':',1),('\u200e45h\u200e',0),('.',1)]:
        run=paragraph.add_run(text);run.font.name='Arial';run.font.size=Pt(11)
        etree.SubElement(run._r.get_or_add_rPr(),model.W+'rtl').set(model.W+'val',str(rtl))
    folio=doc.add_paragraph('الصفحة 1 / 1')
    etree.SubElement(folio._p.get_or_add_pPr(),model.W+'bidi').set(model.W+'val','1')
    stream=BytesIO();doc.save(stream);raw=stream.getvalue()
    with fitz.open() as pdf:
        page=pdf.new_page(width=595,height=842)
        page.insert_text((50,90),'Fictional appointment begins at 09:30h and ends at 10:45h.')
        page.insert_text((260,790),'Page 1 / 1');source=pdf.tobytes()
    mapping={'version':1,'docx_sha256':sha256(raw).hexdigest(),'source_page_count':1,
        'pages':[{'source_page_number':1,'source_file_sha256':sha256(source).hexdigest(),
            'blocks':[{'location':{'kind':'body_paragraph','paragraph_index':i}} for i in range(2)]}]}
    snapshot=bind_raw_page_map(raw,mapping,source_pdf_sha256=sha256(source).hexdigest(),selected_pages=(1,),target_lang='AR')
    frames=[{'page_number':1,'width_px':595,'height_px':842,'image_sha256':'a'*64}]
    decisions=model.default_decisions(snapshot.saved_snapshot,frames)
    for row in decisions['paragraphs']:row['regions']=[{'page_number':1,'bbox_px':[50,80,550,250]}]
    decisions['paragraphs'][-1].update(role='source_folio',regions=[{'page_number':1,'bbox_px':[250,780,350,810]}])
    evidence={'version':'ordinary_auto_layout_evidence_v1','document_reviewed':False,'rendered_layout_acceptance':'not_evaluated',
        'source_folio_direction_version':'numeric_run_ltr_v3',
        'source_evidence':{'version':'ordinary_source_evidence_v1','pages':[{'page_number':1,'findings':[],
            'layout':[{'kind':'source_footer','paragraph_ids':[snapshot.paragraphs[-1].id],'bbox':[.1,.9,.9,.99]}],
            'source_coverage_verified':False}]}}
    return raw,mapping,snapshot,frames,decisions,evidence,source
