"""Local, versioned source fractions; no source or translated text is rewritten."""
from copy import deepcopy
import hashlib
import json
import math
import re

VERSION = "ordinary_source_folio_span_proof_v1"
KEY = "local_source_folio_proof"
RECIPE_KEY = "local_source_folio_proof_version"
_HASH = re.compile(r"[a-f0-9]{64}\Z")
_SOURCE = re.compile(r"([1-9][0-9]{0,3})\s*/\s*([1-9][0-9]{0,3})")
_NUM = r"[0-9\u0660-\u0669\u06f0-\u06f9]{1,4}"
_TARGET = re.compile(r"(?<![\w/\u060d])(" + _NUM + r")\s*[/\u060d]\s*(" + _NUM + r")(?![\w/\u060d])")
_MARKS = frozenset("\u200e\u200f\u2066\u2067\u2069")
# Provider boxes are coarse; v1 admits at most 2% horizontal frame uncertainty.
# Vertical containment stays exact, and the independently extracted value is exact.
_HORIZONTAL_MARGIN = .02
# Only a complete email followed by separate whitespace can own this contact-row
# fallback. A numeral inside the address, an identifier or a citation is not a folio.
_EMAIL_BEFORE_FOLIO = re.compile(
    r"(?<!\S)[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}[ \t]+\Z")


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _fail():
    raise ValueError("ordinary_source_folio_proof_changed")


def _frames(pages, selected):
    if (type(selected) not in {tuple, list} or not selected
            or any(type(n) is not int or n < 1 for n in selected)
            or list(selected) != sorted(set(selected)) or type(pages) is not list):
        _fail()
    result = []
    for number in selected:
        rows = [p for p in pages if type(p) is dict and p.get("page_number") == number]
        if len(rows) != 1:
            _fail()
        row = rows[0]
        if (any(type(row.get(k)) is not int or row[k] <= 0 for k in ("width_px", "height_px"))
                or type(row.get("image_sha256")) is not str or not _HASH.fullmatch(row["image_sha256"])):
            _fail()
        result.append({k: row[k] for k in ("page_number", "width_px", "height_px", "image_sha256")})
    return result


def derive_proof(source_pdf, pages, selected, source_sha256):
    """Extract one unique standalone lower-page fraction, or retain no evidence."""
    if (type(source_pdf) is not bytes or not source_pdf or len(source_pdf) > 64 * 1024 * 1024
            or hashlib.sha256(source_pdf).hexdigest() != source_sha256):
        _fail()
    frames = _frames(pages, selected)
    result = {"version": VERSION, "source_pdf_sha256": source_sha256,
        "selected_pages": list(selected), "frames": frames,
        "folios": [{"page_number": n, "fraction": None} for n in selected]}
    import fitz
    try:
        with fitz.open(stream=source_pdf, filetype="pdf") as document:
            if document.needs_pass or len(document) > 10000:
                return result
            for row in result["folios"]:
                number = row["page_number"]
                if number > len(document):
                    continue
                page = document[number - 1]
                if page.rotation != 0:
                    continue
                width, height = float(page.rect.width), float(page.rect.height)
                candidates = []
                data = page.get_text("dict", flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES)
                lines = [line for block in data["blocks"] for line in block.get("lines", [])]
                if len(lines) > 20000:
                    continue
                for line in lines:
                    text = "".join(s["text"] for s in line.get("spans", []))
                    match = _SOURCE.fullmatch(text.strip()) if len(text) <= 80 else None
                    if match:
                        candidates.append((line, text, int(match[1]), int(match[2])))
                if len(candidates) != 1:
                    continue
                line, text, numerator, denominator = candidates[0]
                box = list(line["bbox"])
                if (not 1 <= numerator <= denominator <= 9999 or len(box) != 4
                        or not all(math.isfinite(v) for v in [width, height, *box])
                        or not (0 <= box[0] < box[2] <= width and .85 * height <= box[1] < box[3] <= height)
                        or box[2] - box[0] > .25 * width or box[3] - box[1] > min(24, .05 * height)
                        or tuple(line.get("dir", ())) != (1.0, 0.0)):
                    continue
                row["fraction"] = {"numerator": numerator, "denominator": denominator,
                    "bbox": [box[0]/width, box[1]/height, box[2]/width, box[3]/height],
                    "text_sha256": hashlib.sha256(text.encode()).hexdigest()}
    except (RuntimeError, ValueError, KeyError, TypeError, OverflowError):
        # An unreadable/unsupported PDF cannot justify removing output furniture.
        for row in result["folios"]:
            row["fraction"] = None
    return result


def verify_proof(proof, source_pdf, pages, selected, source_sha256):
    expected = derive_proof(source_pdf, pages, selected, source_sha256)
    if _encoded(proof) != _encoded(expected):
        _fail()
    return deepcopy(expected)


def target_spans(snapshot, pages, decisions, context):
    """Recognize complete selected-page coverage using source-bound terminal spans."""
    return _target_spans(snapshot, pages, decisions, context, require_all_pages=True)


def direction_target_spans(snapshot, pages, decisions, context, *, accepted_footers=(), group_overlap=False):
    """Qualify pages independently for direction; never authorize PAGE suppression."""
    return _target_spans(snapshot, pages, decisions, context, require_all_pages=False,
                         accepted_footers=accepted_footers, group_overlap=group_overlap)


def _unique_footer(footers, number, owners):
    if not isinstance(footers, (tuple, list)) or any(type(f) is not dict for f in footers):
        _fail()
    groups = [f for f in footers if f.get("kind") == "source_footer" and f.get("source_page_number") == number]
    if len(groups) != 1:
        return None
    group = groups[0]
    ids, box = group.get("paragraph_ids"), group.get("bbox")
    if (type(group["source_page_number"]) is not int
            or type(ids) is not list or not ids or any(type(i) is not str or owners.get(i) != number for i in ids)
            or len(set(ids)) != len(ids) or type(box) is not list or len(box) != 4
            or any(type(v) not in {int, float} or not math.isfinite(v) for v in box)
            or not 0 <= box[0] < box[2] <= 1 or not .85 <= box[1] < box[3] <= 1):
        _fail()
    return group


def _other_terminal_fraction(rows, ids, identifier, fraction):
    expected = (fraction["numerator"], fraction["denominator"])
    for sibling in ids:
        if sibling == identifier:
            continue
        text = "".join(c for c in rows[sibling]["text"] if c not in _MARKS).rstrip()
        if any(m.end() == len(text) and tuple(map(int, m.groups())) == expected for m in _TARGET.finditer(text)):
            return True
    return False


def _target_spans(snapshot, pages, decisions, context, *, require_all_pages, accepted_footers=(), group_overlap=False):
    proof = context.get(KEY)
    if proof is None:
        return []
    selected = context["selected_pages"]
    if (type(proof) is not dict or set(proof) != {"version", "source_pdf_sha256", "selected_pages", "frames", "folios"}
            or proof["version"] != VERSION or type(proof["source_pdf_sha256"]) is not str
            or not _HASH.fullmatch(proof["source_pdf_sha256"])
            or _encoded(proof["selected_pages"]) != _encoded(selected)
            or _encoded(proof["frames"]) != _encoded(_frames(pages, selected))
            or type(proof["folios"]) is not list or len(proof["folios"]) != len(selected)):
        _fail()
    rows = {r["id"]: r for r in snapshot["paragraphs"]}
    owners = {i: p for p, ids in context["page_groups"] for i in ids}
    frames = {p["page_number"]: p for p in pages}
    cuts = {p["paragraph_id"] for p in decisions.get("paragraph_partitions", [])}
    flow = {i for b in decisions["bands"] if b["kind"] == "flow" for g in b["groups"] if not g["panel"] for i in g["paragraph_ids"]}
    result = []
    for number, source in zip(selected, proof["folios"]):
        if type(source) is not dict or set(source) != {"page_number", "fraction"} or type(source["page_number"]) is not int or source["page_number"] != number:
            _fail()
        fraction = source["fraction"]
        if fraction is None:
            continue
        if (type(fraction) is not dict or set(fraction) != {"numerator", "denominator", "bbox", "text_sha256"}
                or any(type(fraction[k]) is not int for k in ("numerator", "denominator"))
                or not 1 <= fraction["numerator"] <= fraction["denominator"] <= 9999
                or type(fraction["text_sha256"]) is not str or not _HASH.fullmatch(fraction["text_sha256"])):
            _fail()
        box = fraction["bbox"]
        if (type(box) is not list or len(box) != 4 or any(type(v) not in {int, float} or not math.isfinite(v) for v in box)
                or not 0 <= box[0] < box[2] <= 1 or not .85 <= box[1] < box[3] <= 1):
            _fail()
        frame = frames[number]
        cx, cy = (box[0]+box[2])*frame["width_px"]/2, (box[1]+box[3])*frame["height_px"]/2
        margin = _HORIZONTAL_MARGIN * frame["width_px"]
        matches = []
        fallback = []
        footer = _unique_footer(accepted_footers, number, owners)
        for choice in decisions["paragraphs"]:
            identifier = choice["paragraph_id"]
            if (owners.get(identifier) != number or identifier in cuts or identifier not in flow
                    or choice["role"] != "source_folio" or len(choice["regions"]) != 1):
                continue
            row = rows[identifier]
            tokens = row["tokens"][:-1] if row["tokens"] and row["tokens"][-1]["kind"] == "page_break" else row["tokens"]
            if not tokens or any(t["kind"] != "t" for t in tokens):
                continue
            region = choice["regions"][0]
            x0,y0,x1,y1 = region["bbox_px"]
            horizontal_gap = max(x0-cx, cx-x1, 0)
            within_horizontal = horizontal_gap <= margin or math.isclose(
                horizontal_gap, margin, rel_tol=0, abs_tol=1e-9)  # coordinate arithmetic roundoff only
            member_contains_y = y0 <= cy <= y1
            primary_geometry = member_contains_y and within_horizontal
            if (region["page_number"] != number or y0 < .85*frame["height_px"]
                    or y1-y0 > .12*frame["height_px"] or not member_contains_y and not group_overlap):
                continue
            if not primary_geometry:
                if footer is None or footer["paragraph_ids"].count(identifier) != 1:
                    continue
                group_box = footer["bbox"]
                group_gap = max(group_box[0]*frame["width_px"]-cx, cx-group_box[2]*frame["width_px"], 0)
                if (not .85 <= group_box[1] <= cy/frame["height_px"] <= group_box[3] <= 1
                        or group_gap > margin and not math.isclose(group_gap, margin, rel_tol=0, abs_tol=1e-9)):
                    continue
                if not member_contains_y:
                    # A coarse contact frame can start within the printed fraction
                    # rather than at its center. Its own accepted footer must own
                    # the center, and the member must intersect the physical ink
                    # bounds in both dimensions. No global geometry tolerance grows.
                    w, h = frame["width_px"], frame["height_px"]
                    if (group_gap != 0 or min(x1,box[2]*w) <= max(x0,box[0]*w)
                            or min(y1,box[3]*h) <= max(y0,box[1]*h)):
                        continue
            indexed = [(i,c) for i,c in enumerate(row["text"]) if c not in _MARKS]
            text = "".join(c for _,c in indexed).rstrip()
            candidates = list(_TARGET.finditer(text))
            if len(candidates) != 1 or candidates[0].end() != len(text):
                continue
            match = candidates[0]
            if any(len(v)>1 and int(v[0])==0 for v in match.groups()):
                continue
            if (int(match[1]),int(match[2])) != (fraction["numerator"],fraction["denominator"]):
                continue
            start, end = indexed[match.start()][0], indexed[match.end()-1][0]+1
            span = {"page_number": number, "paragraph_id": identifier, "start": start, "end": end,
                    "literal_sha256": hashlib.sha256(row["text"][start:end].encode()).hexdigest()}
            if primary_geometry:
                matches.append(span)
            elif (_EMAIL_BEFORE_FOLIO.search(text[:match.start()])
                    and not _other_terminal_fraction(rows, footer["paragraph_ids"], identifier, fraction)):
                span["footer_association"] = {k: deepcopy(footer[k]) for k in
                                             ("kind", "paragraph_ids", "bbox", "source_page_number")}
                fallback.append(span)
        # Primary paragraph geometry stays authoritative. An ambiguous result
        # cannot be replaced by a contact candidate elsewhere on the page.
        candidates = matches + fallback if group_overlap else matches or fallback
        if len(candidates) == 1:
            span = candidates[0]
            if group_overlap and _other_terminal_fraction(rows, [i for i,p in owners.items() if p==number],
                                                           span["paragraph_id"], fraction):
                continue
            result.append(span)
    return result if not require_all_pages or len(result) == len(selected) else []


CONTACT_KEY = "source_native_folio_contact_v1"
_EMAIL = re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}(?![A-Za-z0-9._%+-])")


def _native_ink(page, trace, box):
    """Prove the encoded glyphs actually paint the observed dark-on-white pixels."""
    import fitz
    import zlib
    from .ordinary_source_postal_band import _font_program
    if (trace["type"]!=0 or trace["opacity"]!=1 or trace["dir"]!=(1.,0.)
            or trace["color"] not in {(0.,0.,0.),(0.,),0.} or not 4<=trace["size"]<=64
            or not page.rect.contains(box) or box.is_empty or box.width*box.height*16>300000
            or len(trace["chars"])>400 or page.rotation or page.cropbox_position!=fitz.Point(0,0)):
        return False
    name=trace["font"]
    fonts=[f for f in page.get_fonts() if f[3]==name or re.sub(r"^[A-Z]{6}\+","",f[3])==name]
    if len(fonts)!=1:
        return False
    f=fonts[0]
    if f[1]=="n/a" and f[2]=="Type1" and name in fitz.Base14_fontnames:
        program=None
        font=fitz.Font(fontname=name)
    elif f[1:3]==("ttf","Type0") and f[5]=="Identity-H":
        try:
            program=_font_program(page,name)
        except (ValueError,zlib.error):
            program=None
        if not program:
            # Some PDFs encode the CID descendant inline rather than by xref.
            doc=page.parent
            kind,desc=doc.xref_get_key(f[0],"DescendantFonts")
            streams=re.findall(r"/FontFile2\s+(\d+)\s+0\s+R\b",desc) if len(desc)<=16000 else []
            if kind!="array" or not desc.startswith("[<<") or not desc.endswith(">>]") or len(streams)!=1:
                return False
            ref=int(streams[0])
            length=doc.xref_get_key(ref,"Length");original=doc.xref_get_key(ref,"Length1")
            if any(k!="int" or not v.isdecimal() or not 1<=int(v)<=524288 for k,v in (length,original)):
                return False
            program=doc.xref_stream_raw(ref)
            if len(program)!=int(length[1]) or doc.xref_get_key(ref,"DecodeParms")[0]!="null":
                return False
            kind,value=doc.xref_get_key(ref,"Filter")
            if (kind,value)==("name","/FlateDecode"):
                decoder=zlib.decompressobj()
                try:
                    program=decoder.decompress(program,524289)
                except zlib.error:
                    return False
                if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                    return False
            elif kind!="null":
                return False
            if len(program)!=int(original[1]):
                return False
        font=fitz.Font(fontbuffer=program)
    else:
        return False
    if any(font.has_glyph(code)!=glyph for code,glyph,_,_ in trace["chars"]):
        return False
    with fitz.open() as doc:
        other=doc.new_page(width=page.rect.width,height=page.rect.height)
        alias=name
        if program:
            alias="ContactProof"
            other.insert_font(fontname=alias,fontbuffer=program)
        for code,_,origin,_ in trace["chars"]:
            other.insert_text(origin,chr(code),fontname=alias,fontsize=trace["size"],color=(0,0,0))
        options=dict(matrix=fitz.Matrix(4,4),clip=box,colorspace=fitz.csGRAY,alpha=False)
        actual=page.get_pixmap(**options).samples
        return bool(actual) and min(actual)<96 and actual==other.get_pixmap(**options).samples


def _visible_native_field(page, paints, trace, box):
    import fitz
    return (trace["type"]==0 and trace["opacity"]==1 and trace["dir"]==(1.,0.)
            and page.rect.contains(box) and not box.is_empty
            and not any(kind!="ignore-text" and box.intersects(fitz.Rect(bounds))
                        for kind,bounds in paints[trace["seqno"]+1:])
            and _native_ink(page,trace,box))


def native_contacts(pdf, proof, *, visible_folios=None):
    """Independently identify the visible email beside a proven printed folio."""
    import fitz
    rows = {}
    pending = []
    confirmed = {}
    if not pdf or len(proof["folios"])>64 or len(pdf) > 64_000_000 or hashlib.sha256(pdf).hexdigest() != proof["source_pdf_sha256"]:
        return rows
    try:
        with fitz.open(stream=pdf, filetype="pdf") as doc:
            for page in proof["folios"]:
                f = page["fraction"]
                if f is None:
                    continue
                number = page["page_number"]
                source = doc[number-1]
                width,height=source.rect.width,source.rect.height
                rect=fitz.Rect(*(c*(width if i%2==0 else height) for i,c in enumerate(f["bbox"])))
                trace=source.get_texttrace()
                paints=source.get_bboxlog()
                if len(trace)>20000 or len(paints)>50000 or sum(len(t["chars"]) for t in trace)>250000:
                    continue
                emails=[]
                all_emails=[]
                folios=[]
                for t in trace:
                    chars=t["chars"]
                    text="".join(chr(c[0]) for c in chars)
                    m=_SOURCE.fullmatch(text.strip())
                    if m and tuple(map(int,m.groups()))==(f["numerator"],f["denominator"]):
                        folios.append((t,fitz.Rect(t["bbox"])))
                    for m in _EMAIL.finditer(text):
                        all_emails.append(m[0].casefold())
                        box=fitz.Rect()
                        for c in chars[m.start():m.end()]:
                            box |= fitz.Rect(c[3])
                        if max(rect.y0,box.y0) < min(rect.y1,box.y1) and box.y0>=.85*height:
                            emails.append((m[0],box,t))
                # Resolve all candidate identities and cheap geometry first.
                # Only one fraction and one email may materialize pixel proofs.
                if len(folios)!=1:
                    continue
                ft,fb=folios[0]
                if not rect.intersects(fb):
                    continue
                stamp={"source_page":number,"source_pdf_sha256":proof["source_pdf_sha256"],
                       "source_line_sha256":f["text_sha256"],"fraction_bbox":list(f["bbox"])}
                unambiguous=len(emails)==1 and all_emails.count(emails[0][0].casefold())==1
                if unambiguous:
                    # The same printed address can use several adjacent font
                    # spans in a second location. Check full visual lines too.
                    data=source.get_text("dict",flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES)
                    lines=[line for block in data["blocks"] for line in block.get("lines",[])]
                    if len(lines)>20000:
                        continue
                    same=0
                    near=[]
                    for line in lines:
                        values=_EMAIL.findall("".join(span["text"] for span in line["spans"]))
                        same+=sum(v.casefold()==emails[0][0].casefold() for v in values)
                        if max(rect.y0,line["bbox"][1])<min(rect.y1,line["bbox"][3]):
                            near.extend(values)
                    unambiguous=(same==1 and near==[emails[0][0]])
                if not unambiguous:
                    # A pure peer's fraction can be proven without an email.
                    # Defer this work unless another page actually qualifies.
                    if visible_folios is not None:
                        pending.append((number,ft,fb,stamp))
                    continue
                email,box,et=emails[0]
                if not _visible_native_field(source,paints,ft,fb):
                    continue
                confirmed[str(number)]=stamp
                if not _visible_native_field(source,paints,et,box):
                    continue
                rows[str(number)]={"source_page":number,"email_sha256":hashlib.sha256(email.encode()).hexdigest(),
                    "email_bbox":[box.x0/width,box.y0/height,box.x1/width,box.y1/height],
                    "source_pdf_sha256":proof["source_pdf_sha256"],"source_line_sha256":f["text_sha256"]}
            if rows and visible_folios is not None:
                for number,ft,fb,stamp in pending:
                    page=doc[number-1]
                    if _visible_native_field(page,page.get_bboxlog(),ft,fb):
                        confirmed[str(number)]=stamp
                visible_folios.update(confirmed)
    except (RuntimeError,ValueError,KeyError,IndexError,TypeError,OverflowError):
        return {}
    return rows


def native_contact_scope(pdf, proof):
    visible = {}
    contacts = native_contacts(pdf,proof,visible_folios=visible)
    return {"contacts":contacts, "visible_folios":visible}


def contact_overlap_spans(snapshot, pages, decisions, context, associations):
    """Qualify only source-matched terminal email/folio carriers in an accepted group."""
    if not associations or not context.get(CONTACT_KEY):
        return []
    groups = [{**record["accepted_footer"], "source_page_number":record["source_page_number"]}
              for record in associations]
    candidates=direction_target_spans(snapshot,pages,decisions,context,accepted_footers=groups,group_overlap=True)
    result=[]
    frames={p["page_number"]:p for p in pages}
    rows={r["id"]:r for r in snapshot["paragraphs"]}
    choices={r["paragraph_id"]:r for r in decisions["paragraphs"]}
    fractions={r["page_number"]:r["fraction"] for r in context[KEY]["folios"]}
    for span in candidates:
        n,ident=span["page_number"],span["paragraph_id"]
        contacts=context[CONTACT_KEY]["contacts"].get(str(n))
        before="".join(c for c in rows[ident]["text"][:span["start"]] if c not in _MARKS)
        match=_EMAIL_BEFORE_FOLIO.search(before)
        selected=[group for group in groups if group["source_page_number"]==n and ident in group["paragraph_ids"]]
        if not (contacts and match and len(selected)==1 and len(_EMAIL.findall(before))==1
                and contacts.get("source_page")==n and contacts.get("source_pdf_sha256")==context[KEY]["source_pdf_sha256"]
                and contacts.get("source_line_sha256")==fractions[n]["text_sha256"]
                and hashlib.sha256(match[0].strip().encode()).hexdigest()==contacts["email_sha256"]):
            continue
        group=selected[0]; box=fractions[n]["bbox"]
        gx,gy,gx1,gy1=group["bbox"]
        cx,cy=(box[0]+box[2])/2,(box[1]+box[3])/2
        region=choices[ident]["regions"][0]["bbox_px"];f=frames[n]
        x,y,x1,y1=[v/(f["width_px"] if j%2==0 else f["height_px"]) for j,v in enumerate(region)]
        mail=contacts["email_bbox"]
        overlaps_fraction=min(x1,box[2])>max(x,box[0]) and min(y1,box[3])>max(y,box[1])
        # Existing contact-row ownership can instead use the same vertical
        # center together with positive intersection of the physical email.
        overlaps_email=(y<=cy<=y1 and min(x1,mail[2])>max(x,mail[0])
                        and min(y1,mail[3])>max(y,mail[1]))
        if not (gx<=cx<=gx1 and gy<=cy<=gy1 and (overlaps_fraction or overlaps_email)
                and gx<=mail[0]<=mail[2]<=gx1 and gy<=mail[1]<=mail[3]<=gy1):
            continue
        record=next(a for a in associations if a["source_page_number"]==n)
        result.append({**span,"footer_association":deepcopy(group),"email_sha256":contacts["email_sha256"],
            "email_bbox":mail,"member_bbox":[x,y,x1,y1],
            "member_basis":"printed_fraction_overlap" if overlaps_fraction else "same_row_email_overlap",
            "canonical_proposal_sha256":record["canonical_proposal_sha256"],"response_sha256":record["response_sha256"]})
    return result


def complete_mixed_coverage(snapshot,pages,decisions,context,contacts):
    """Every selected physical page must have exactly one matching visible carrier."""
    if not contacts:
        return []
    rows={r["id"]:r for r in snapshot["paragraphs"]}
    choices={r["paragraph_id"]:r for r in decisions["paragraphs"]}
    owners=dict(context["page_groups"]);frames={p["page_number"]:p for p in pages}
    cuts={r["paragraph_id"] for r in decisions.get("paragraph_partitions",[])}
    result=[]
    for item in context[KEY]["folios"]:
        n,f=item["page_number"],item["fraction"]
        if f is None:
            return []
        visible=context[CONTACT_KEY]["visible_folios"].get(str(n))
        if visible!={"source_page":n, "source_pdf_sha256":context[KEY]["source_pdf_sha256"],
                     "source_line_sha256":f["text_sha256"], "fraction_bbox":f["bbox"]}:
            return []
        found=[]
        for ident in owners[n]:
            text="".join(c for c in rows[ident]["text"] if c not in _MARKS).strip()
            m=next((m for m in _TARGET.finditer(text) if m.end()==len(text)),None)
            if m is None:
                continue
            pair=tuple(map(int,m.groups()))
            if pair!=(f["numerator"],f["denominator"]):
                if choices[ident]["role"]=="source_folio":
                    return []
                continue
            found.append((ident,m,text))
        if len(found)!=1:
            return []
        ident,match,text=found[0]
        mixed=[s for s in contacts if s["page_number"]==n and s["paragraph_id"]==ident]
        if len(mixed)==1:
            kind="contact"
        else:
            choice=choices[ident];frame=frames[n];tokens=rows[ident]["tokens"]
            if tokens and tokens[-1]["kind"]=="page_break":
                tokens=tokens[:-1]
            if (match.start()!=0 or any(len(s)>1 and int(s[0])==0 for s in match.groups())
                    or choice["role"]!="source_folio" or len(choice["regions"])!=1 or ident in cuts
                    or rows[ident].get("has_field") or rows[ident].get("has_numbering")
                    or not tokens or any(t["kind"]!="t" for t in tokens)):
                return []
            region=choice["regions"][0];_,y,_,y1=region["bbox_px"]
            if region["page_number"]!=n or y<.85*frame["height_px"] or y1-y>.12*frame["height_px"]:
                return []
            kind="standalone"
        result.append({"page_number":n,"paragraph_id":ident,"kind":kind,"source_fraction":deepcopy(f),
            "visible_source_folio":deepcopy(visible),
            "target_sha256":hashlib.sha256(rows[ident]["text"].encode()).hexdigest(),
            **({"source_contact":deepcopy(mixed[0])} if kind=="contact" else {})})
    return result
