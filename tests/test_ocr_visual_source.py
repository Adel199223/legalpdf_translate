from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

from legalpdf_translate import ordinary_ocr_visual_source as source
from legalpdf_translate.arabic_pre_tokenize import extract_locked_tokens, pretokenize_arabic_source
from legalpdf_translate.checkpoint import sha256_of_file

CASE = "304/25.3ABCD"
BAD = "304/25.3ACD"
REF = "718662"
HEADER = f"{CASE} [{REF}]"
LOC = "Palácio da Justiça - Rua do Sol"
MAIL = "porto.correio@tribunal.org.pt"
URL = "https://exemplo.pt/gqJa"


def projection():
    raw = (f"TRIBUNAL\nPalácio de Justiça - Rua do Sol\nporto. correio@tribunal.gov.pt\n"
           f"Processo nº {BAD}\nReferência deste documento: {REF}\n"
           "inquérito ou durante a investigação não foi")
    groups = [("head", [HEADER]), ("address", [LOC]), ("email", [MAIL]), ("case", [f"Processo no {CASE}"]),
              ("condition", ["inquérito se durante a investigação não for"])]
    return raw, groups


def test_distinct_header_and_labelled_owner():
    raw, groups = projection()
    effective, obligations = source._derive(raw, groups)
    assert effective.startswith(HEADER+"\nTRIBUNAL")
    assert effective.count(CASE) == effective.count(REF) == 2
    assert effective.count("["+REF+"]") == 1
    assert LOC in effective and MAIL in effective and BAD not in effective
    assert effective.endswith("inquérito se durante a investigação não for")
    assert obligations["headers"] == [[CASE, REF]]
    assert obligations["conditions"] == ["inquérito se durante a investigação não for"]
    cooked = pretokenize_arabic_source(source.prepared_source(effective, {"obligations":obligations}))
    assert extract_locked_tokens(cooked).count(CASE) == 2
    assert LOC in extract_locked_tokens(cooked)


@pytest.mark.parametrize("suffix", [f"\nOutra referência: {REF}", f"\nProcesso nº {BAD}",
                                    "\nporto. correio@tribunal.gov.pt"])
def test_ambiguous_owners_require_review(suffix):
    raw, groups = projection()
    with pytest.raises(ValueError, match="requires_review"):
        source._derive(raw+suffix, groups)


def test_bare_or_unbound_header():
    raw, groups = projection()
    text, obligations = source._derive(raw, [("head", [f"{CASE} {REF}"]), *groups[1:]])
    assert not obligations["headers"] and not text.startswith(CASE)
    with pytest.raises(ValueError, match="requires_review"):
        source._derive(raw.replace("Referência deste documento:", "Valor:"), groups)


def test_sidebar_keeps_both_sides_of_uncertain_phone_and_menu():
    old = "Outro corpo.\nLink: https://exemplo.pt/gqJja (abreviado)"
    groups = [("side", ["Contactos disponíveis", "Telefone 300 502 502 /chamada para a rede fixa)",
                        "Antes de ligar, vá a www.seg-social.pt", "Proteção jurídica", "Nomeação e pagamento"]),
              ("url", [f"Link: {URL} (abreviado)"])]
    value, ob = source._derive(old, groups)
    assert value.startswith("Contactos disponíveis\nTelefone 300 502 502 chamada para a rede fixa\n")
    assert value.count("Nomeação e pagamento")==1 and value.endswith(URL+" (abreviado)")
    assert ob["supplemented_column"] and ob["uncertain_punctuation"]==["300 502 502"]
    assert ob["aliases"]==[["https://exemplo.pt/gqJja", URL]]
    assert {"300 502 502","www.seg-social.pt",URL}==set(ob["literals"])


def test_ineligible_sources_and_ambiguous_conditions():
    raw = "inquérito ou durante a investigação não foi"
    assert source._conditional_owner("inquérito se durante a investigação não for",raw)==0
    assert source._conditional_owner("inquérito se durante a investigação não for",raw+"\n"+raw) is None
    assert source._conditional_owner("novo se durante outro processo não for",raw) is None
    with pytest.raises(ValueError, match="requires_review"):
        source._derive("Processo nº 102/21.7ABC", [("case",["Processo no 309/22.5QRS"])])


@pytest.mark.parametrize(("raw","observations"), [
    ("ana.official2@court.org.pt",[("email",["ana.official@court.org.pt","ana.official2@court.org.pt"])]),
    ("Link: https://exemplo.pt/abc2",[("url",["Link: https://exemplo.pt/abc","Link: https://exemplo.pt/abc2"])]),
    (f"Processo nº {BAD}",[("case",[f"Processo no {CASE}",f"Processo no {BAD}"])]),
])
def test_two_corroborated_slots_cannot_reuse_one_raw_field(raw,observations):
    with pytest.raises(ValueError,match="requires_review"):
        source._derive(raw,observations)


def row(txt, box):
    return {"text":txt,"words":[{"text":txt,"box":list(box)}]}


def test_read_line_is_position_bound_and_rejects_overlap():
    original=row("fonte",[20,30,60,8])
    hits=[row("outro",[180,6,120,16]),row("fonte",[40,6,120,16])]
    scan={"dpi":288,"bounds":[0,54,500,100],"lines":hits}
    assert source._read_line(original,scan)=="fonte"
    hits.append(row("borrowed",[42,6,120,16]))
    assert source._read_line(original,scan) is None
    with pytest.raises(ValueError,match="evidence_changed"):
        source._lines([{"text":"borrowed","words":original["words"]}],100,100)


def test_header_multiplicity_position_and_payload():
    raw, groups=projection()
    effective, obligations=source._derive(raw,groups)
    witness={"obligations":obligations}
    input_=pretokenize_arabic_source(source.prepared_source(effective,witness))
    line=f"[[{CASE}]] [\u2066[[{REF}]]\u2069]"
    body=f"[[{LOC}]]\n[[{MAIL}]]\nرقم [[{CASE}]]\nمرجع [[{REF}]]"
    target=line+"\n"+body
    assert source.violation(target,input_,witness) is None
    for bad in (target.replace("[\u2066"," \u2066").replace("\u2069]","\u2069"),
                body+"\n"+line, target.replace("مرجع [[","مرجع [[[") + "]",
                target+"\n[["+MAIL+"]]", target.replace(CASE,BAD,1)):
        assert source.violation(bad,input_,witness)


def test_guidance_only_claims_observed_classes():
    _, obligation=source._derive("Correio postal\nporto. correio@tribunal.gov.pt",[("email",[MAIL])])
    message=source.guidance({"obligations":obligation})
    assert MAIL in message
    assert all(word not in message for word in ("compact header","conditional","sidebar","uncertain fields"))
    assert source.guidance(None)==""


def test_limited_correction_authority_never_exempts_other_primary_tokens():
    a,b="https://exemplo.pt/gqJja",URL
    witness={"obligations":{"aliases":[[a,b]]}}
    before=f"[[11]] [[{a}]] [[22]]"
    correct=f"[[11]] [[{b}]] [[22]]"
    assert source.compliance_baseline(before,correct,witness)==correct
    for changed in (correct.replace("[[11]]","[[99]]"),correct.replace("[[22]]",""),
                    f"[[{b}]] [[11]] [[22]]",correct+f" [[{b}]]"):
        assert source.compliance_baseline(before,changed,witness)==before


def _raster(tmp_path):
    path = tmp_path/"scan.pdf"
    with fitz.open() as doc:
        page=doc.new_page(width=220,height=180)
        page.draw_rect(fitz.Rect(20,20,50,28), width=1)
        other=doc.new_page(width=220,height=180)
        other.insert_text((25,45),"Natural text")
        doc.save(path)
    return path


def test_mixed_pdf_availability_and_prior_behavior(tmp_path,monkeypatch):
    path = _raster(tmp_path)
    mode=lambda x:SimpleNamespace(value=x)
    config=SimpleNamespace(pdf_path=path,image_mode=mode("auto"),ocr_mode=mode("auto"),
                           ocr_engine=mode("local_then_api"),strip_bidi_controls=True)
    assert not source.selection_qualifies(config,[2])
    if source.os.name=="nt":
        assert source.selection_qualifies(config,[2,1])
    monkeypatch.setattr(source,"os",SimpleNamespace(name="posix"))
    assert not source.selection_qualifies(config,[1,2])


def test_unavailable_worker_preserves_bytes_and_saved_reopen_never_calls_engine(tmp_path,monkeypatch):
    from legalpdf_translate import ordinary_windows_ocr_worker as worker
    path=_raster(tmp_path); digest=sha256_of_file(path)
    dir_=tmp_path/"run"; (dir_/"ocr_transport/page_0001").mkdir(parents=True)
    monkeypatch.setattr(worker,"recognize_png",lambda png: ())
    raw="Texto original."
    effective, proof=source.acquire(path,1,raw,digest,dir_)
    assert effective==raw and source.guidance(proof)==""
    assert source.acquire(path,2,raw,digest,dir_)==(raw,None)
    def denied(*args,**kwargs):
        raise AssertionError("reopen launched recognition")
    monkeypatch.setattr(worker,"recognize_png",denied)
    assert source.acquire(path,1,raw,digest,dir_)==(raw,proof)
    assert source.replay(path,1,raw,digest,dir_)==(raw,proof)
    with pytest.raises(ValueError,match="evidence_changed"):
        source.replay(path,1,"Edited raw",digest,dir_)
    file=dir_/"ocr_transport/page_0001/visual_source.json"
    record=source.json.loads(file.read_bytes())
    record["coarse"]["png_sha256"]="0"*64
    file.write_bytes(source._encode(record))
    with pytest.raises(ValueError,match="evidence_changed"):
        source.replay(path,1,raw,digest,dir_)


def test_atomic_publication_can_retry_after_error(tmp_path,monkeypatch):
    file=tmp_path/"proof.json"
    with monkeypatch.context() as ctx:
        def stop(*args):
            raise OSError("interruption")
        ctx.setattr(source.os,"rename" if source.os.name=="nt" else "link",stop)
        with pytest.raises(OSError):
            source._publish(file,b"first")
    assert not file.exists()
    source._publish(file,b"first")
    source._publish(file,b"first")
    with pytest.raises(ValueError,match="evidence_changed"):
        source._publish(file,b"other")
    assert file.read_bytes()==b"first"


def test_partial_worker_failure_does_not_publish(tmp_path,monkeypatch):
    from legalpdf_translate import ordinary_windows_ocr_worker as worker
    path=_raster(tmp_path)
    folder=tmp_path/"run"/"ocr_transport"/"page_0001";folder.mkdir(parents=True)
    def unavailable(png):
        raise TimeoutError("fixture")
    monkeypatch.setattr(worker,"recognize_png",unavailable)
    with pytest.raises(TimeoutError):
        source.acquire(path,1,"texto",sha256_of_file(path),folder.parent.parent)
    assert list(folder.iterdir())==[]



def test_missing_contact_requires_the_adjacent_postal_owner_and_complete_clock_glyphs():
    raw="Cabeçalho\nPalácio de Justiça - Rua do Sol\n1000-123 Porto\nOutro parágrafo."
    lines=[LOC,"1000-123 Porto","Ligue 221234567,","das 09h00 às 13h30.",MAIL]
    text, obligation=source._derive(raw,[("contact",lines)])
    assert text=="\n".join(["Cabeçalho",*lines,"Outro parágrafo."])
    assert obligation["phone_slots"]==[["1000-123 Porto","221234567","09h00"]]
    for damaged in (lines[:3]+["das 09hOO às 13h30.",MAIL], lines[:1]+["1000-123 Lisboa",*lines[2:]]):
        with pytest.raises(ValueError,match="requires_review"):
            source._derive(raw,[("contact",damaged)])


def test_condition_soft_wrap_preserves_every_surrounding_byte():
    context=["Este termo depende da fase de","inquérito se durante a investigação não for",
             "possível reunir factos e provas."]
    old="Este termo depende da fase de inquérito ou durante a investigação após\npossível reunir factos e provas."
    expected=old.replace("inquérito ou durante a investigação após",context[1])
    assert source._derive(old,[("flow_condition",context)])[0]==expected
    for added in (" 12345", " 304/25.3ABCD", " ao arguido"):
        bad=old.replace("após\n","após"+added+"\n")
        assert source._flow_condition(context,bad) is None
        with pytest.raises(ValueError,match="requires_review"):
            source._derive(bad,[("flow_condition",context)])


def test_reporting_that_something_happened_is_not_reporting_a_person():
    line="interrompe se nos informar de que fez o pedido. Não basta pedi-lo."
    wrong=line.replace("de que","de quem")
    raw="Outro período. "+wrong+"\nCom o respetivo aviso."
    assert source._derive(raw,[("inline_condition",[line])])[0]==raw.replace(wrong,line)
    assert source._inline_condition(line,raw+"\n"+wrong) is None
    assert source._inline_condition(line,line) is None


def test_barcode_only_qualifies_printed_tracking_and_mailing_reference():
    raw="Data: 12-10-2025\nOutro campo."
    rows=["Data: 12-10-2025","42-12345678","AB 123456789 PT"]
    for body in (raw,raw+"\n42-12345678"):
        result, ob=source._derive(body,[("mailing",rows)])
        assert result.count("42-12345678")==result.count("AB123456789PT")==1
        assert ob["mailing_labels"]==[["42-12345678","AB123456789PT"]]
    with pytest.raises(ValueError,match="requires_review"):
        source._derive(raw.replace("Data","Valor"),[("mailing",rows)])
    with pytest.raises(ValueError,match="requires_review"):
        source._derive(raw+"\n42-12345678\n42-12345678",[("mailing",rows)])


def test_no_barcode_from_text_or_plain_divider(tmp_path):
    pdf=_raster(tmp_path)
    rows=[row("42-12345678",[24,30,72,6]),row("AB 123456789 PT",[20,65,85,8])]
    with fitz.open(pdf) as doc:
        assert not source._mailing_geometry(doc[0],rows)
        points=[row("Data: 12-10-2025",[24,10,90,8]),*rows]
        assert source._plans(points,"Data: 12-10-2025",440,doc[0])==[]


def test_single_wrong_phone_digit_requires_two_independent_printed_neighbours():
    value="221234567"; old="221234560"
    w={"obligations":{"aliases":[],"phone_slots":[["1000-123 Porto",value,"09h00"]]}}
    before=f"[[1000-123 Porto]] [[{old}]] [[09h00]] [[Outra entidade]]"
    after=before.replace(old,value)
    assert source.compliance_baseline(before,after,w,source=value)==after
    assert source.compliance_baseline(before,after,w,source=value+" "+old)==before
    assert source.compliance_baseline(before,after.replace("09h00","10h00"),w,source=value)==before
    assert source.compliance_baseline(before,after.replace("Outra entidade","Outro"),w,source=value)==after
    assert source.compliance_baseline(before.replace(old,"991234560"),after,w,source=value)!=after


def test_historical_reader_rejects_foreign_witness_before_early_return():
    from legalpdf_translate import workflow_semantic_audit as audit, ocr_text_transport as transport
    with pytest.raises(transport.OcrTextTransportError,match="source_binding"):
        audit._validate_ocr_acquisition(state=None,run_dir=None,page_number=1,recipe={},data={"ocr_visual_source":{}})



@pytest.mark.parametrize("existing",[
    "42-12345678\nAB123456788PT", "42-12345679\nAB123456788PT", "42-12345679\nOutro campo",
    "42-12345678\nAB 12345O788 PT", "42-12345678\nOutro campo\nAB123456789PT",
    "AB123456789PT\n42-12345678",
])
def test_measured_postal_pair_does_not_coexist_with_a_contradictory_carrier(existing):
    group=["Data: 12-10-2025","42-12345678","AB 123456789 PT"]
    with pytest.raises(ValueError,match="requires_review"):
        source._derive("Data: 12-10-2025\n"+existing,[("mailing",group)])


def test_two_separately_attested_mailing_carriers_keep_their_own_fields():
    a=["Data: 12-10-2025","42-12345678","AB 123456789 PT"]
    b=["Data: 13-10-2025","52-12345679","AB 123456788 PT"]
    raw="Data: 12-10-2025\n42-12345678\nData: 13-10-2025\n52-12345679"
    result,ob=source._derive(raw,[("mailing",a),("mailing",b)])
    assert result.splitlines()==[a[0],a[1],"AB123456789PT",b[0],b[1],"AB123456788PT"]
    assert ob["mailing_labels"]==[[a[1],"AB123456789PT"],[b[1],"AB123456788PT"]]




def test_guidance_fresh_order_is_also_the_exact_reopened_order():
    _,groups=projection()
    _,obligation=source._derive(projection()[0],groups)
    fresh=source.guidance({"obligations":obligation})
    old_order={k:v for k,v in obligation.items() if v}
    assert fresh.endswith(source.json.dumps(old_order,ensure_ascii=False))
    restored=source.json.loads(source._encode(obligation))
    assert list(restored)!=list(obligation)
    assert source.guidance({"obligations":restored}).encode()==fresh.encode()


@pytest.mark.parametrize("damage",["none","missing_witness","malformed","foreign","tampered_capture","borrowed_answer",
                                   "missing_intent","missing_answer","unknown_sibling","legacy_reader"])
def test_settled_ocr_transport_reentry_is_zero_dispatch(tmp_path,monkeypatch,damage):
    from legalpdf_translate import ocr_text_transport as transport, ordinary_windows_ocr_worker as worker
    from legalpdf_translate.usage_accounting import accounting_context
    from tests import test_ocr_text_transport as fixture
    path=_raster(tmp_path)
    digest=sha256_of_file(path)
    monkeypatch.setattr(fixture,"PDF",digest)
    engine,accountant,http,_=fixture.native(tmp_path,monkeypatch)
    monkeypatch.setattr(worker,"recognize_png",lambda png: ())
    def run(policy=True):
        options={"visual_source_policy":source.POLICY,"pdf_path":path} if policy else {}
        with accounting_context(accountant,page_number=1),transport.scope(tmp_path,1,digest,**options):
            return engine.ocr_image(b"fictional-image","PT")
    first=run()
    assert first.text==fixture.TEXT and len(http.requests)==1
    effective,proof=source.acquire(path,1,first.text,digest,tmp_path)
    folder=tmp_path/"ocr_transport/page_0001"
    witness=folder/"visual_source.json"
    document=tmp_path/"semantic_source/page_0001.json"
    document.parent.mkdir()
    saved={"pdf_sha256":digest,"page_number":1,"original_source_text":effective,"ocr_visual_source":proof,
           "ocr_text_acquisition":{"reference":first.text_transport_evidence,
                                   "selected_source_sha256":source._sha(effective),"composition":"verified_source_slots_v1"}}
    document.write_bytes(source._encode(saved))
    if damage=="missing_witness": witness.unlink()
    elif damage=="malformed": witness.write_bytes(b"[]")
    elif damage=="foreign":
        bad=source.json.loads(witness.read_bytes());bad["page"]=2;witness.write_bytes(source._encode(bad))
    elif damage=="tampered_capture":
        saved["ocr_visual_source"]={};document.write_bytes(source._encode(saved))
    elif damage=="borrowed_answer":
        saved["ocr_text_acquisition"]["reference"]={};document.write_bytes(source._encode(saved))
    elif damage=="missing_intent": (folder/"intent.json").unlink()
    elif damage=="missing_answer": (folder/"answered.json").unlink()
    elif damage=="unknown_sibling": (folder/"anything.tmp").write_bytes(b"unrelated")
    prior_journal=accountant.journal_path.read_bytes()
    def denied(*args,**kwargs):
        raise AssertionError("resume ran Windows OCR")
    monkeypatch.setattr(worker,"recognize_png",denied)
    if damage=="none":
        assert set(p.name for p in folder.iterdir())=={"intent.json","answered.json","visual_source.json"}
        assert run().text_transport_evidence==first.text_transport_evidence
    else:
        with pytest.raises(ValueError):
            run(damage!="legacy_reader")
    assert len(http.requests)==1 and accountant.journal_path.read_bytes()==prior_journal


def test_acquisition_stages_bytes_outside_the_envelope(tmp_path,monkeypatch):
    from legalpdf_translate import ordinary_windows_ocr_worker as worker
    path=_raster(tmp_path); root=tmp_path/"run";folder=root/"ocr_transport"/"page_0001"
    folder.mkdir(parents=True)
    monkeypatch.setattr(worker,"recognize_png",lambda png: ())
    actual=source.os.rename if source.os.name=="nt" else source.os.link
    def observe(before,after):
        assert Path(before).parent==folder.parent and Path(after).parent==folder
        assert not list(folder.iterdir())
        return actual(before,after)
    monkeypatch.setattr(source.os,"rename" if source.os.name=="nt" else "link",observe)
    source.acquire(path,1,"Texto original.",sha256_of_file(path),root)
    assert [p.name for p in folder.iterdir()]==["visual_source.json"]

