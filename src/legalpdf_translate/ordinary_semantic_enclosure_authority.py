"""Fresh occurrence-owned source enclosures, layered over unchanged literal v1.

The visual assertions are fallible. Exact sequence and unique neighborhood
binding establish their scope, never their truth. Raw/OCR source is immutable.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, replace
import unicodedata

from . import ordinary_semantic_literal_authority as literal
from . import ordinary_semantic_review as review
from .ar_source_fields import _view

POLICY = "source_enclosure_authority_v1"
CERTIFICATE = "source_enclosure_certificate_v1"
CONTEXT = "source_enclosure_validation_context_v1"
RESPONSE = "source_literal_enclosure_resolution_v1"
MAX_LOOKUPS = literal.MAX_LOOKUPS
_PAIRS = {"none": ("", ""), "round": ("(", ")"), "square": ("[", "]"), "curly": ("{", "}")}
_DELIMITERS = "()[]{}"
_SPACE = " \t\u00a0\u202f"
_INSTRUCTIONS = """
INDEPENDENT SOURCE ENCLOSURE OBSERVATIONS v1:
For EACH old_enclosure_lookup, inspect the original full-page source image and
report the immediate matching printed enclosure around that EXACT old protected
literal: none, round (), square [], or curly {}. The bare exact_reading must
equal the supplied OLD value. An enclosure contains only that whole literal,
with optional horizontal spaces; never infer editorial punctuation or combine
prose, several literals, nesting, or a partial field. Observe every requested
same-valued occurrence separately, including occurrences with no enclosure.
Prove that each OLD occurrence owns its own distinct source position from the
old lookup context and original source. Never assign repeats by ordinal,
similarity, OCR absence or an assumed correction. The region must include both
printed delimiters, or enough surrounding space to establish none. If reading
or ownership is ambiguous/unreadable, return unresolved. Enclosure observations
have NO raw_span and never correct OCR or change the bare literal reading.
source_image.bbox is INTEGER ORIGINAL IMAGE PIXEL coordinates
[left, top, right, bottom], right/bottom exclusive, using supplied width/height.
Distinct literal decisions and enclosure observations require nonoverlapping
source regions. No proposed candidate enclosure or expected answer is supplied.
Return the combined schema, with unchanged literal-v1 decisions separately.
"""
FACT_INSTRUCTIONS = literal.FACT_INSTRUCTIONS + """
Separately typed source enclosure assertions describe only the immediate printed
pair or none at an individually owned literal occurrence. Challenge each against
the original full-page images. They do not edit raw source/OCR or source units.
Enclosure absence is an explicit constraint; a matching pair elsewhere gives no
credit. No old primary draft, rejected proposal or resolver verdict is authority.
"""
REPLACEMENT_INSTRUCTIONS = literal.REPLACEMENT_INSTRUCTIONS + """
Apply source_enclosure_observations ONLY at their exact protected occurrence:
preserve the complete protected-value sequence and each unique previous/self/next
literal neighborhood on affected pages. Keep every unrelated occurrence and
source commitment. The derived primary baseline licenses only certified immediate
delimiters, not prose or value changes. no_change still retains the ACTUAL ORIGINAL
primary page, never the projected baseline. The optional effective quality
diagnostic is untrusted and cannot authorize or remove source-printed punctuation.
"""


def _fail(code):
    review._fail("enclosure_authority_" + code)


def descriptor():
    return {"policy": POLICY, "certificate": CERTIFICATE, "validation_context": CONTEXT,
        "response_version": RESPONSE, "max_combined_lookups": MAX_LOOKUPS,
        "schema_sha256": literal._hash(review.audit._json(response_format())),
        "instructions_sha256": literal._hash(_INSTRUCTIONS),
        "fact_instructions_sha256": literal._hash(FACT_INSTRUCTIONS),
        "replacement_instructions_sha256": literal._hash(REPLACEMENT_INSTRUCTIONS),
        "mapping": "complete_projected_sequence_and_unique_neighbor_signature_v1",
        "projection": "exact_original_primary_delimiters_only_v1",
        "enclosure_source_edits": "forbidden_v1"}


# The registry remains byte-exact literal v1, including its bounded unavailable state.
freeze = literal.freeze


def _tokens(text):
    view = _view(text)
    if view is None:
        _fail("wrapper_binding")
    return view[0], view[2]


def _candidate_tokens(text):
    """Preserve supported views; normalize only an isolate-only wrapper gap.

    Printed square brackets adjacent to raw [[...]] need the validator's exact
    isolate placement before tokenization. Raw proposals/receipts and original
    provenance spans stay unchanged; this view cannot license visible edits.
    """
    view = _view(text)
    if view is not None:
        return view[0], view[2]
    if any((unicodedata.category(c) == "Cc" and c not in "\r\n\t")
            or (unicodedata.category(c) == "Cf" and c not in "\u2066\u2069\u200e\u200f\u061c\u200c\u200d") for c in text):
        _fail("wrapper_binding")
    probe = review.audit.evaluate_output("```\n" + text + "\n```", review.audit.TargetLang.AR)
    if not probe.ok or not probe.normalized_text:
        _fail("wrapper_binding")
    # Equality is proof only, never an output transformation: every visible
    # character and protocol bracket must remain exact. Other evaluator
    # changes (whitespace, wording, token regrouping) cannot use this fallback.
    if (probe.normalized_text.replace("\u2066", "").replace("\u2069", "")
            != text.replace("\u2066", "").replace("\u2069", "")):
        _fail("wrapper_binding")
    return _tokens(probe.normalized_text)


def _kind(visible, token):
    """Immediate whole-token enclosure, retaining visible token boundaries."""
    left, right = token[0] - 1, token[1]
    while left >= 0 and visible[left] in _SPACE:
        left -= 1
    while right < len(visible) and visible[right] in _SPACE:
        right += 1
    a = visible[left] if left >= 0 else ""
    b = visible[right] if right < len(visible) else ""
    for kind, pair in _PAIRS.items():
        if kind != "none" and (a, b) == pair:
            return kind
    # A closing delimiter on the left or opening delimiter on the right can
    # belong to a separate adjacent pair. The full stack proves that distinction.
    return "invalid" if (a and a in "([{") or (b and b in ")]}" ) else "none"


def _signatures(values):
    # Typed sentinels cannot collide with any literal string.
    return [(('value', values[i-1]) if i else ('page_start',), ('value', value),
        ('value', values[i+1]) if i+1 < len(values) else ('page_end',))
        for i, value in enumerate(values)]


def _shapes(visible, tokens):
    """Bind the immediate pair to the complete surrounding delimiter stack.

    Delimiters inside any protected value are data, not enclosure syntax. A
    queried token may have exactly its own immediate pair, or no active opener;
    a larger prose pair, nesting or an unmatched surrounding opener cannot give
    an immediate-pair certificate. Work and storage are linear in the page.
    """
    starts = {t[0]: i for i,t in enumerate(tokens)}
    owners, closing, stack = {}, {}, []
    pairs = {"(": ")", "[": "]", "{": "}"}
    position = 0
    while position < len(visible):
        if position in starts:
            index = starts[position]
            owners[index] = (len(stack), stack[-1][1] if stack else None)
            position = tokens[index][1]
            continue
        char = visible[position]
        if char in pairs:
            stack.append((char,position))
        elif char in ")]}":
            if stack and pairs[stack[-1][0]] == char:
                _, opening = stack.pop()
                closing[opening] = position
            # A mismatch leaves its opener unresolved, which cannot establish
            # ownership for a token inside it.
        position += 1
    result = []
    for index,token in enumerate(tokens):
        kind = _kind(visible,token)
        depth, opening = owners[index]
        left, right = token[0]-1, token[1]
        while left >= 0 and visible[left] in _SPACE: left -= 1
        while right < len(visible) and visible[right] in _SPACE: right += 1
        if ((kind == "none" and depth != 0)
                or (kind in {"round","square","curly"}
                    and (depth != 1 or opening != left or closing.get(opening) != right))):
            kind = "invalid"
        result.append(kind)
    return result


def _span_matches(text, token, span, value):
    start, end = span["start"], span["end"]
    return (token[2] == value and 0 <= token[3]-start <= 1 and 0 <= end-token[4] <= 1
        and text[start:token[3]] in {"", "\u2066"} and text[token[4]:end] in {"", "\u2069"}
        and text[start:end] == span["quote"])


def _carry_alignment(page, old_tokens, tokens, lookups):
    """Eligibility only: no positional comparison can authorize a reading."""
    if len(old_tokens) != len(tokens):
        return {}
    old_counts, new_counts = Counter(t[2] for t in old_tokens), Counter(t[2] for t in tokens)
    by_value = {o["value"]: o for o in lookups if o["page"] == page.page_number}
    changed = {}
    for i,(old,new) in enumerate(zip(old_tokens,tokens)):
        if old[2] == new[2]:
            continue
        occurrence = by_value.get(old[2])
        if (old_counts[old[2]] != 1 or new_counts[new[2]] != 1 or old_counts[new[2]]
                or occurrence is None or not _span_matches(page.primary_text,old,occurrence["primary_span"],old[2])):
            return {}
        changed[i] = occurrence
    return changed


def classify(raw, pages, inventory, recipe, registry):
    base = literal.classify(raw, pages, inventory, recipe, registry)
    data = literal.parse_correction(raw, pages, inventory)
    enclosure, proposed, carried = [], [], []
    for page, row, frozen in zip(pages, data["pages"], registry["pages"]):
        text = page.primary_text if row["status"] == "no_change" else row["corrected_text"]
        # literal.classify has checked every page's wrapper/control/language gates.
        visible, tokens = _candidate_tokens(text)
        old_visible, old_tokens = _tokens(page.primary_text)
        proposed.append({"page_number": page.page_number, "text": text})
        old_counts, new_counts = Counter(t[2] for t in old_tokens), Counter(t[2] for t in tokens)
        old_kinds, new_kinds = _shapes(old_visible,old_tokens), _shapes(visible,tokens)
        old_immediate = [_kind(old_visible,t) for t in old_tokens]
        new_immediate = [_kind(visible,t) for t in tokens]
        old_immediate_counts = Counter((t[2],kind) for t,kind in zip(old_tokens,old_immediate))
        new_immediate_counts = Counter((t[2],kind) for t,kind in zip(tokens,new_immediate))
        old_shapes = Counter((t[2], kind) for t,kind in zip(old_tokens,old_kinds))
        new_shapes = Counter((t[2], kind) for t,kind in zip(tokens,new_kinds))
        old_signatures = _signatures([t[2] for t in old_tokens])
        new_signatures = _signatures([t[2] for t in tokens])
        same_sequence = [t[2] for t in old_tokens] == [t[2] for t in tokens]
        old_signature_counts, new_signature_counts = Counter(old_signatures), Counter(new_signatures)
        old_unique = {s: i for i,s in enumerate(old_signatures) if old_signature_counts[s] == 1}
        alignment = _carry_alignment(page,old_tokens,tokens,base["lookups"]) if base else {}
        triggered = set()
        for i,t in enumerate(tokens):
            kind = new_kinds[i]
            signature = new_signatures[i]
            immediate = new_immediate[i]
            # Eligibility/rejection only: an unchanged old nested structure
            # cannot become a new delta because unrelated prose changed. A
            # sequence position can expose a delta here but NEVER authorizes
            # final ownership; project/_check still require both independent
            # complete-sequence and unique-neighborhood proofs.
            changed_immediate = (new_immediate_counts[t[2],immediate] > old_immediate_counts[t[2],immediate]
                or (new_signature_counts[signature] == 1 and signature in old_unique
                    and old_immediate[old_unique[signature]] != immediate)
                or (same_sequence and old_immediate[i] != immediate))
            if (kind == "invalid" and immediate in {"round","square","curly"}
                    and changed_immediate and old_counts[t[2]]):
                _fail("nested_or_larger_enclosure")
            if kind not in {"round", "square", "curly"}:
                continue
            if base and any(o["page"] == page.page_number for o in base["lookups"]) and new_counts[t[2]] > old_counts[t[2]]:
                old = alignment.get(i)
                if old is None or old_kinds[i] != kind or any(c in _DELIMITERS for c in old["value"]):
                    _fail("same_occurrence_value_and_enclosure")
                carried.append({"old_occurrence": {k: deepcopy(old[k])
                    for k in ("occurrence_id","page","value","primary_span")}, "enclosure": kind})
            moved = (new_signature_counts[signature] == 1 and signature in old_unique
                and old_kinds[old_unique[signature]] != kind)
            if (new_counts[t[2]] == old_counts[t[2]] and old_counts[t[2]]
                    and (new_shapes[t[2],kind] > old_shapes[t[2],kind] or moved or changed_immediate)):
                triggered.add(t[2])
        if not triggered:
            continue
        if registry.get("availability") != "complete":
            _fail("registry_unavailable")
        if (recipe.configured_image_mode == "off" or frozen["image"] is None
                or frozen["source_origin"] not in literal.ORIGINS):
            _fail("source_origin_or_image_required")
        for occurrence in frozen["occurrences"]:
            if occurrence["value"] in triggered:
                if any(c in _DELIMITERS for c in occurrence["value"]):
                    _fail("bare_value_required")
                enclosure.append({k: deepcopy(occurrence[k])
                    for k in ("occurrence_id", "page", "value", "primary_span")})
    if not enclosure:
        if base is None:
            return None
        result = {**base, "version": "source_literal_enclosure_eligibility_v1", "enclosure_lookups": []}
        if carried:
            result["carried_original_pairs"] = carried
        return result
    lookups = base["lookups"] if base else []
    if len(lookups) + len(enclosure) > MAX_LOOKUPS:
        _fail("lookup_bound")
    if {o["occurrence_id"] for o in lookups} & {o["occurrence_id"] for o in enclosure}:
        _fail("same_occurrence_value_and_enclosure")
    result = {"version": "source_literal_enclosure_eligibility_v1", "lookups": lookups,
        "enclosure_lookups": enclosure, "registry_sha256": literal._hash(review.audit._json(registry)),
        "rejected_proposal": {"untrusted": True, "pages": proposed}, "canonical": data}
    if carried:
        result["carried_original_pairs"] = carried
    return result


def response_format():
    obj = review._object_schema
    string, integer = {"type": "string"}, {"type": "integer"}
    literal_schema = literal.response_format()["schema"]["properties"]["decisions"]
    image = obj({"page": integer, "image_sha256": string,
        "bbox": {"type": "array", "items": integer, "minItems": 4, "maxItems": 4}})
    observation = obj({"occurrence_id": string, "exact_reading": string,
        "ownership": {"type": "string", "enum": ["owned", "unresolved"]},
        "enclosure": {"type": "string", "enum": ["none", "round", "square", "curly", "unresolved"]},
        "source_image": image})
    return {"type": "json_schema", "name": RESPONSE, "strict": True,
        "schema": obj({"version": string, "literal_decisions": literal_schema,
            "enclosure_observations": {"type": "array", "items": observation, "maxItems": MAX_LOOKUPS}})}


def request(pages, recipe, registry, eligibility):
    result = literal.request(pages, recipe, registry, eligibility)
    payload = review._parse(result["prompt_text"])
    payload.update(protocol=POLICY, old_enclosure_lookups=eligibility["enclosure_lookups"])
    result.update(prompt_text=review._prompt_json(payload), response_format=response_format())
    result["instructions"] += _INSTRUCTIONS
    return result


def _enclosure_rows(pages, registry, lookups, observations, literal_decisions):
    if type(lookups) is not list or len(lookups) + len(literal_decisions) > MAX_LOOKUPS:
        _fail("lookup_bound")
    review._list(observations, MAX_LOOKUPS)
    if len(observations) != len(lookups):
        _fail("observation_coverage")
    old_map = {o["occurrence_id"]: o for p in registry["pages"] for o in p["occurrences"]}
    frozen_map = {p["page"]: p for p in registry["pages"]}
    boxes, seen, result = {}, set(), []
    for row in literal_decisions:
        image = row["source_image"]
        boxes.setdefault(image["page"], []).append(image["bbox"])
        seen.add(row["occurrence_id"])
    for old, row in zip(lookups, observations):
        review._obj(old, {"occurrence_id", "page", "value", "primary_span"})
        identifier = old["occurrence_id"]
        frozen_old = old_map.get(identifier)
        if (frozen_old is None or old != {k: frozen_old[k] for k in old}
                or identifier in seen or any(c in _DELIMITERS for c in old["value"])):
            _fail("occurrence_binding")
        seen.add(identifier)
        review._obj(row, {"occurrence_id", "exact_reading", "ownership", "enclosure", "source_image"})
        if (row["occurrence_id"] != identifier or row["exact_reading"] != old["value"]
                or row["ownership"] != "owned" or type(row["enclosure"]) is not str
                or row["enclosure"] not in _PAIRS):
            _fail("unresolved_or_reading_changed")
        frozen = frozen_map[old["page"]]
        image = row["source_image"]
        review._obj(image, {"page", "image_sha256", "bbox"})
        bbox = image["bbox"]
        if (frozen["image"] is None or frozen["source_origin"] not in literal.ORIGINS
                or type(image["page"]) is not int or image["page"] != old["page"]
                or image["image_sha256"] != frozen["image"]["sha256"]
                or type(bbox) is not list or len(bbox) != 4 or any(type(v) is not int for v in bbox)
                or not 0 <= bbox[0] < bbox[2] <= frozen["image"]["width"]
                or not 0 <= bbox[1] < bbox[3] <= frozen["image"]["height"]
                or any(literal._overlap(bbox, b) for b in boxes.setdefault(old["page"], []))):
            _fail("source_image_ownership")
        boxes[old["page"]].append(bbox)
        result.append({"old_occurrence": old, "enclosure": row["enclosure"], "source_image": image})
    # All original occurrences of each queried same value must be present once.
    queried = {(o["page"], o["value"]) for o in lookups}
    required = {o["occurrence_id"] for o in old_map.values() if (o["page"], o["value"]) in queried}
    if required != {o["occurrence_id"] for o in lookups}:
        _fail("same_value_coverage")
    return result


def _carried_rows(pages, registry, rows, decisions, observations):
    if rows is None:
        return []
    review._list(rows,MAX_LOOKUPS)
    if not rows:
        _fail("carried_pair_binding")
    old_map = {o["occurrence_id"]:o for p in registry["pages"] for o in p["occurrences"]}
    page_map = {p.page_number:p for p in pages}
    allowed = {d["occurrence_id"] for d in decisions}
    seen = {o["occurrence_id"] for o in observations}
    for row in rows:
        review._obj(row,{"old_occurrence","enclosure"})
        old = row["old_occurrence"]
        review._obj(old,{"occurrence_id","page","value","primary_span"})
        if type(old["occurrence_id"]) is not str or type(row["enclosure"]) is not str:
            _fail("carried_pair_binding")
        frozen = old_map.get(old["occurrence_id"])
        if (frozen is None or old != {k:frozen[k] for k in old} or old["occurrence_id"] not in allowed
                or old["occurrence_id"] in seen or row["enclosure"] not in {"round","square","curly"}
                or any(c in _DELIMITERS for c in old["value"])):
            _fail("carried_pair_binding")
        seen.add(old["occurrence_id"])
        page = page_map[old["page"]]
        visible,tokens = _tokens(page.primary_text)
        matches = [i for i,t in enumerate(tokens) if _span_matches(page.primary_text,t,old["primary_span"],old["value"])]
        if (len(matches) != 1 or Counter(t[2] for t in tokens)[old["value"]] != 1
                or _shapes(visible,tokens)[matches[0]] != row["enclosure"]):
            _fail("carried_pair_binding")
    return deepcopy(rows)


def _proposed_carried_pairs(pages, eligibility):
    expected = []
    for page,row in zip(pages,eligibility["canonical"]["pages"]):
        visible,tokens = _candidate_tokens(page.primary_text if row["status"] == "no_change" else row["corrected_text"])
        old_visible,old_tokens = _tokens(page.primary_text)
        old_counts,new_counts = Counter(t[2] for t in old_tokens),Counter(t[2] for t in tokens)
        alignment = _carry_alignment(page,old_tokens,tokens,eligibility["lookups"])
        old_shapes = _shapes(old_visible,old_tokens)
        for i,(token,kind) in enumerate(zip(tokens,_shapes(visible,tokens))):
            if (kind in {"round","square","curly"} and new_counts[token[2]] > old_counts[token[2]]
                    and any(o["page"] == page.page_number for o in eligibility["lookups"])):
                old = alignment.get(i)
                if old is None or old_shapes[i] != kind:
                    _fail("carried_pair_binding")
                expected.append({"old_occurrence":{k:deepcopy(old[k])
                    for k in ("occurrence_id","page","value","primary_span")},"enclosure":kind})
    return expected


def certificate(raw, pages, registry, eligibility):
    data = review._parse(raw)
    review._obj(data, {"version", "literal_decisions", "enclosure_observations"})
    if data["version"] != RESPONSE or eligibility["registry_sha256"] != literal._hash(review.audit._json(registry)):
        _fail("resolution_binding")
    base = None
    if eligibility["lookups"]:
        base = literal.certificate(review.audit._json({"version": "source_literal_resolution_v1",
            "decisions": data["literal_decisions"]}), pages, registry, eligibility)
    elif data["literal_decisions"] != []:
        _fail("unexpected_literal_decisions")
    observations = _enclosure_rows(pages, registry, eligibility["enclosure_lookups"],
        data["enclosure_observations"], data["literal_decisions"])
    if base is None and not observations:
        _fail("empty_resolution")
    expected_carry = _proposed_carried_pairs(pages,eligibility)
    if (eligibility.get("carried_original_pairs",[]) != expected_carry
            or ("carried_original_pairs" in eligibility and not expected_carry)):
        _fail("carried_pair_binding")
    carried = _carried_rows(pages,registry,eligibility.get("carried_original_pairs"),
        data["literal_decisions"],eligibility["enclosure_lookups"])
    result = {"version": CERTIFICATE, "policy": POLICY,
        "registry_sha256": eligibility["registry_sha256"], "resolution_sha256": literal._hash(raw),
        "assertion_status": "fallible_source_reading_and_ownership", "literal_certificate": base,
        "enclosure_lookups": eligibility["enclosure_lookups"], "enclosure_observations": observations}
    if carried:
        result["carried_original_pairs"] = carried
    return result


@dataclass(frozen=True)
class ValidationContext:
    projected_pages: tuple
    evidence: dict
    source_facts: tuple
    enclosure_facts: tuple
    obligations: tuple


def project(pages, registry, cert):
    if (cert.get("version") != CERTIFICATE or cert.get("policy") != POLICY
            or cert.get("registry_sha256") != literal._hash(review.audit._json(registry))
            or cert.get("assertion_status") != "fallible_source_reading_and_ownership"):
        _fail("certificate_binding")
    base_cert = cert["literal_certificate"]
    base = literal.project(pages, registry, base_cert) if base_cert is not None else None
    raw_observations = [{"occurrence_id": o["old_occurrence"]["occurrence_id"],
        "exact_reading": o["old_occurrence"]["value"], "ownership": "owned",
        "enclosure": o["enclosure"], "source_image": o["source_image"]}
        for o in cert["enclosure_observations"]]
    checked = _enclosure_rows(pages, registry, cert["enclosure_lookups"], raw_observations,
        base_cert["decisions"] if base_cert else [])
    if checked != cert["enclosure_observations"] or (not checked and base is None):
        _fail("projection_binding")
    if "carried_original_pairs" in cert and cert["carried_original_pairs"] is None:
        _fail("carried_pair_binding")
    carried = _carried_rows(pages,registry,cert.get("carried_original_pairs"),
        base_cert["decisions"] if base_cert else [],cert["enclosure_lookups"])
    projected, evidence, facts, obligations = [], [], [], []
    for original, effective, frozen in zip(pages, base.projected_pages if base else pages, registry["pages"]):
        if (frozen["page"] != original.page_number or frozen["raw_sha256"] != literal._hash(review._original(original))
                or frozen["source_sha256"] != literal._hash(original.source_text)
                or frozen["primary_sha256"] != literal._hash(original.primary_text)):
            _fail("page_binding")
        visible, tokens = _tokens(effective.primary_text)
        shapes = _shapes(visible,tokens)
        values = [t[2] for t in tokens]
        signatures = _signatures(values)
        counts = Counter(signatures)
        edits, page_obligations = [], []
        for observation in checked:
            old = observation["old_occurrence"]
            if old["page"] != original.page_number:
                continue
            span = old["primary_span"]
            offset = sum(len("\u2066[["+c["exact_reading"]+"]]\u2069") - len(c["old_occurrence"]["primary_span"]["quote"])
                for c in (base_cert["changes"] if base_cert else [])
                if c["old_occurrence"]["page"] == original.page_number
                and c["old_occurrence"]["primary_span"]["end"] <= span["start"])
            start, end = span["start"]+offset, span["end"]+offset
            # _view may omit either exact isolate at the edges of a canonical
            # wrapper adjacent to visible square delimiters. The frozen full
            # wrapper quote remains exact; no value/prose offset is adjustable.
            matches = [i for i,t in enumerate(tokens) if t[2] == old["value"]
                and 0 <= t[3]-start <= 1 and 0 <= end-t[4] <= 1
                and effective.primary_text[start:t[3]] in {"", "\u2066"}
                and effective.primary_text[t[4]:end] in {"", "\u2069"}
                and effective.primary_text[start:end] == span["quote"]]
            if len(matches) != 1 or counts[signatures[matches[0]]] != 1:
                _fail("ambiguous_neighborhood")
            index = matches[0]
            previous = shapes[index]
            kind = observation["enclosure"]
            if previous == "invalid" or (previous != "none" and previous != kind):
                _fail("existing_enclosure_conflict")
            if previous == "none" and kind != "none":
                a, b = _PAIRS[kind]
                edits.append((start,end,span["quote"],a+span["quote"]+b))
            page_obligations.append({"occurrence_id": old["occurrence_id"],
                "signature": signatures[index], "enclosure": kind})
            facts.append({"page": original.page_number, "bare_reading": old["value"],
                "enclosure": kind, "source_image": observation["source_image"],
                "status": "challengeable_source_enclosure_assertion"})
        for carry in carried:
            old = carry["old_occurrence"]
            if old["page"] != original.page_number:
                continue
            span = old["primary_span"]
            changes = base_cert["changes"]
            offset = sum(len("\u2066[["+c["exact_reading"]+"]]\u2069")-len(c["old_occurrence"]["primary_span"]["quote"])
                for c in changes if c["old_occurrence"]["page"] == old["page"]
                and c["old_occurrence"]["primary_span"]["end"] <= span["start"])
            change = next((c for c in changes if c["old_occurrence"]["occurrence_id"] == old["occurrence_id"]),None)
            value = change["exact_reading"] if change else old["value"]
            quote = "\u2066[["+value+"]]\u2069" if change else span["quote"]
            projected_span = {"start":span["start"]+offset,"end":span["start"]+offset+len(quote),"quote":quote}
            matches = [i for i,t in enumerate(tokens) if _span_matches(effective.primary_text,t,projected_span,value)]
            if (len(matches) != 1 or values.count(value) != 1 or counts[signatures[matches[0]]] != 1
                    or shapes[matches[0]] != carry["enclosure"]):
                _fail("carried_pair_projection")
            page_obligations.append({"occurrence_id":old["occurrence_id"],"signature":signatures[matches[0]],
                "enclosure":carry["enclosure"],"basis":"unchanged_original_primary_pair_v1"})
        primary = literal._replace(effective.primary_text, edits)
        projected.append(replace(effective, primary_text=primary))
        if base:
            item = deepcopy(next(p for p in base.evidence["pages"] if p["page"] == original.page_number))
        else:
            item = {"page": original.page_number, "exact_protected_occurrence_counts": {},
                "effective_required_occurrences": list(original.expected_ar_tokens)}
        item.update(original_primary_sha256=literal._hash(original.primary_text),
            projected_primary_sha256=literal._hash(primary))
        evidence.append(item)
        if page_obligations:
            obligations.append({"page": original.page_number, "complete_protected_sequence": values,
                "occurrences": page_obligations})
    return ValidationContext(tuple(projected), {"version": CONTEXT,
        "certificate_sha256": literal._hash(review.audit._json(cert)), "pages": evidence,
        "enclosure_obligations": obligations}, base.source_facts if base else (), tuple(facts), tuple(obligations))


def _check(texts, context):
    for page in context.obligations:
        visible, tokens = _candidate_tokens(texts[page["page"]])
        shapes = _shapes(visible,tokens)
        values = [t[2] for t in tokens]
        if values != page["complete_protected_sequence"]:
            _fail("final_sequence_mismatch")
        signatures = _signatures(values)
        counts = Counter(signatures)
        for old in page["occurrences"]:
            signature = tuple(tuple(v) for v in old["signature"])
            if counts[signature] != 1:
                _fail("final_neighborhood_mismatch")
            index = signatures.index(signature)
            if shapes[index] != old["enclosure"]:
                _fail("final_enclosure_mismatch")


def validate(raw, pages, inventory, recipe, context=None):
    if context is not None:
        data = literal.parse_correction(raw, pages, inventory)
        _check({p.page_number: p.primary_text if r["status"] == "no_change" else r["corrected_text"]
            for p,r in zip(pages,data["pages"])}, context)
    selected, decisions, data = literal.validate(raw, pages, inventory, recipe, context)
    if context is not None:
        _check(selected, context)
    return selected, decisions, data


check_replacement_eligibility = literal.check_replacement_eligibility


def check_initial_sequence_replacement_eligibility(raw, pages, inventory, registry, cert, context):
    """Reject an initial proposal whose only sequence errors are certified slots.

    This proves eligibility for the existing replacement, never source ownership
    or acceptance. Final validation still requires the exact projected sequence.
    """
    if context != project(pages,registry,cert) or cert["literal_certificate"] is None:
        _fail("initial_sequence_replacement_ineligible")
    changes = cert["literal_certificate"]["changes"]
    old_rows = [c["old_occurrence"] for c in changes]
    readings = {c["old_occurrence"]["occurrence_id"]:c["exact_reading"] for c in changes}
    data = literal.parse_correction(raw,pages,inventory)
    mismatches = 0
    for original,effective,row in zip(pages,context.projected_pages,data["pages"]):
        text = original.primary_text if row["status"] == "no_change" else row["corrected_text"]
        _,old_tokens = _tokens(original.primary_text)
        _,initial_tokens = _candidate_tokens(text)
        _,projected_tokens = _tokens(effective.primary_text)
        if not len(old_tokens) == len(initial_tokens) == len(projected_tokens):
            _fail("initial_sequence_replacement_ineligible")
        initial = _carry_alignment(original,old_tokens,initial_tokens,old_rows)
        projected = _carry_alignment(original,old_tokens,projected_tokens,old_rows)
        for index,(proposed,expected) in enumerate(zip(initial_tokens,projected_tokens)):
            if proposed[2] == expected[2]:
                continue
            old = initial.get(index)
            if (old is None or projected.get(index) != old
                    or readings[old["occurrence_id"]] != expected[2]):
                _fail("initial_sequence_replacement_ineligible")
            mismatches += 1
    if not mismatches:
        _fail("initial_sequence_replacement_ineligible")


def effective_diagnostic(raw, pages, inventory, recipe, context):
    """Exact remaining quality diagnostic; actual original no_change is retained."""
    from .ordinary_semantic_repair import correction_validation_diagnostic
    data = literal.parse_correction(raw, pages, inventory)
    for original,row in zip(pages,data["pages"]):
        if row["status"] == "no_change":
            row.update(status="corrected", corrected_text=original.primary_text, reason_codes=["material_meaning"])
    try:
        result = correction_validation_diagnostic(review.audit._json(data), context.projected_pages, inventory, recipe)
    except review.SemanticAuditError as exc:
        if exc.code == "correction_literal_or_language_failure":
            return None
        raise
    return result
