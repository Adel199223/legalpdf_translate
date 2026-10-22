"""Pure, opt-in caller-unit references for the three-stage semantic review.

References select immutable caller-supplied units; they never repair provider
quotes or offsets. Existing strict review validators judge hydrated evidence.
"""
from copy import deepcopy
import json
from . import ordinary_semantic_review as review

POLICY = "caller_unit_refs_v1"
PROTOCOL = "source_inventory_correct_verify_unit_refs_v1"
VERSIONS = ("ordinary_source_inventory_unit_refs_v1", "ordinary_source_correction_unit_refs_v1",
            "ordinary_source_verification_unit_refs_v1")
# Conservative application budgets: each enum <=250 short values; all enum
# definitions <=900 values and 7,500 characters; complete schema <=60,000 chars.
# Shared $defs avoid repeating dynamic enums. Overflow fails before dispatch.
MAX_UNITS = review.MAX_UNITS
MAX_CLAIMS = review.MAX_CLAIMS
ENUM_THRESHOLD = 250
MAX_ENUM_VALUES = 900
MAX_ENUM_CHARS = 7500
MAX_SCHEMA_CHARS = 60000

_ATOMIC = """
This saved protocol uses caller_unit_refs_v1. Cite ONLY the supplied short unit IDs;
never calculate/copy hashes, Unicode offsets or quotes, and never invent an ID.
The caller resolves each reference into exact original unit text and computes
inverse coverage. References are citations, not proof that a proposition is true.
Keep each original legal phrase and its surrounding context authoritative.
Every assertion must be atomic: one subject/action-or-state/recipient relation,
one polarity/modality, one temporal state and one participant-number assertion.
Split distinct predicates, actors, recipients, temporal states or modalities into
separate claims even when their source units overlap. One predication may span
lines/pages; one line may support several assertions. Do not use catchall claims
such as identity and other data. Do not assign a witness's role to another actor.
Challenge any contradiction between proposition/paraphrase and its semantic axes
against the exact original phrase and images. Do not silently resolve ambiguity.
"""
_INVENTORY = """
Return owned source_unit_ids, separate context_unit_ids and source_image_evidence.
Every nonempty source unit must have substantive ownership, not merely context.
Express every material fact WITHIN each owned unit across the atomic propositions;
citing a unit does not express its facts. If one unit contains multiple material
assertions, use multiple atomic claims with shared unit citations as needed.
Do not hide unexpressed facts inside a summary or a broad unit-reference list.
Context refs supply background without transferring page ownership. A text-backed
claim needs owned units; an image-only claim needs actual image bbox evidence.
Do not return quotes, offsets or inverse coverage. The source inventory sees no
primary translation or user preferences. Unresolved source meaning must stop.
"""
_VERIFY = """
Independently challenge the inventory AND final candidate against full originals,
not just each other. Reject missing/wrong propositions, mixed predications and
axis/proposition contradictions via inventory_errors. Check fact-level completeness
WITHIN otherwise correctly cited source units, not only unit/claim-set coverage;
report material source facts missing from the inventory even when their unit is
already cited by another claim. Never force the candidate
to fit a bad inventory. For each claim return target_unit_ids for actual candidate
evidence, with the exact substantive source owner-page set. Cover every candidate
unit; context refs never enlarge ownership. Return no offsets/quotes/inverse
coverage. Inventory errors and unsupported additions remain failures. No primary,
prior correction verdict/reasons, context preferences or repair pass is available.
"""


def check_policy(policy):
    if policy != POLICY:
        review._fail("review_reference_policy")


def unit_map(units, prefix):
    if len(units) > MAX_UNITS or len({u["unit_id"] for u in units}) != len(units):
        review._fail("review_reference_bound")
    return {f"{prefix}{n:03d}": unit for n, unit in enumerate(units, 1)}


def _refs(value, mapping, *, empty=True):
    review._list(value, 64)
    if ((not value and not empty) or any(type(k) is not str or k not in mapping for k in value)
            or len(set(value)) != len(value)):
        review._fail("review_reference_evidence")
    return [mapping[key] for key in value]


def _text_span(unit):
    return {"kind": "text", "page": unit["page"], "start": unit["start"],
            "end": unit["end"], "quote": unit["text"]}


def _target_span(unit):
    return {key: value for key, value in _text_span(unit).items() if key != "kind"}


def _check_schema(schema):
    values, chars = 0, 0
    def visit(node):
        nonlocal values, chars
        if isinstance(node, dict):
            if "enum" in node:
                enum = node["enum"]
                if not enum or len(enum) > ENUM_THRESHOLD:
                    review._fail("review_reference_schema_bound")
                values += len(enum)
                chars += sum(len(str(v)) for v in enum)
            for value in node.values(): visit(value)
        elif isinstance(node, list):
            for value in node: visit(value)
    visit(schema)
    if values > MAX_ENUM_VALUES or chars > MAX_ENUM_CHARS or len(review.audit._json(schema)) > MAX_SCHEMA_CHARS:
        review._fail("review_reference_schema_bound")


def response_format(stage, source, *, inventory=None, target=None):
    index = review.STAGES.index(stage)
    result = deepcopy(review._format(stage))
    result["name"] = VERSIONS[index]
    schema = result["schema"]
    schema["properties"]["version"] = review._string(enum=[VERSIONS[index]])
    definitions = {}
    def refs(name, keys):
        if not keys:
            return {"type": "array", "items": {"type": "string"}, "maxItems": 0}
        definitions[name] = review._string(enum=keys) if len(keys) <= ENUM_THRESHOLD else review._string()
        return review._array({"$ref": "#/$defs/" + name})
    source_refs = refs("source_id", list(source))
    if index == 0:
        props = schema["properties"]["claims"]["items"]["properties"]
        props["source_unit_ids"] = source_refs
        props["context_unit_ids"] = deepcopy(source_refs)
        evidence = props.pop("source_evidence")["items"]["anyOf"][1]
        props["source_image_evidence"] = review._array(evidence)
        schema["properties"]["claims"]["items"]["required"] = list(props)
        del schema["properties"]["unit_coverage"]
    else:
        claim_ids = [c["claim_id"] for c in inventory["claims"]]
        if not claim_ids or len(claim_ids) > MAX_CLAIMS:
            review._fail("review_reference_bound")
        refs("claim_id", claim_ids)
        claim_ref = {"$ref": "#/$defs/claim_id"}
        if index == 1:
            schema["properties"]["claim_coverage"]["items"]["properties"]["claim_id"] = claim_ref
        else:
            target_refs = refs("target_id", list(target))
            props = schema["properties"]["claim_results"]["items"]["properties"]
            props["claim_id"] = claim_ref
            del props["target_spans"]
            props["target_unit_ids"] = target_refs
            schema["properties"]["claim_results"]["items"]["required"] = list(props)
            del schema["properties"]["target_unit_coverage"]
            schema["properties"]["inventory_errors"]["items"]["properties"]["source_unit_ids"] = source_refs
            extra = schema["properties"]["unsupported_additions"]["items"]
            del extra["properties"]["target_spans"]
            extra["properties"]["target_unit_ids"] = deepcopy(target_refs)
            extra["required"] = list(extra["properties"])
    schema["required"] = list(schema["properties"])
    if definitions: schema["$defs"] = definitions
    # A valid long claim ID must not make a settled inventory unusable merely
    # because a duplicated enum exhausts a schema budget. Fall back only for
    # dynamic definitions; the exact same application membership guards remain.
    while True:
        enums = []
        def collect(node):
            if isinstance(node, dict):
                if "enum" in node: enums.append(node["enum"])
                for value in node.values(): collect(value)
            elif isinstance(node, list):
                for value in node: collect(value)
        collect(schema)
        over = (sum(len(v) for v in enums) > MAX_ENUM_VALUES
            or sum(len(str(x)) for values in enums for x in values) > MAX_ENUM_CHARS
            or len(review.audit._json(schema)) > MAX_SCHEMA_CHARS)
        dynamic = [value for value in definitions.values() if "enum" in value]
        if not over or not dynamic: break
        del max(dynamic, key=lambda value: sum(len(str(x)) for x in value["enum"]))["enum"]
    _check_schema(schema)
    return result


def descriptor(units):
    source = unit_map(units, "S")
    return {"semantic_unit_reference_policy": POLICY, "protocol": PROTOCOL,
            "source_unit_map_sha256": review.audit._sha(review.audit._json(source)),
            "adapter_instructions_sha256": review.audit._sha(_ATOMIC + _INVENTORY + _VERIFY),
            "inventory_format_sha256": review.audit._sha(review.audit._json(response_format(review.STAGES[0], source))),
            "limits": [MAX_UNITS, MAX_CLAIMS, ENUM_THRESHOLD, MAX_ENUM_VALUES, MAX_ENUM_CHARS, MAX_SCHEMA_CHARS]}


def adapt_request(request, stage, units):
    request = deepcopy(request)
    payload = json.loads(request["prompt_text"])
    source = unit_map(units, "S")
    target = unit_map(payload.get("target_units", []), "T")
    payload["protocol"] = PROTOCOL
    payload["semantic_unit_reference_policy"] = POLICY
    payload["source_units"] = [{**unit, "unit_id": key} for key, unit in source.items()]
    if "target_units" in payload:
        payload["target_units"] = [{**unit, "unit_id": key} for key, unit in target.items()]
    # The accepted inventory remains exact original evidence, with short IDs in
    # the request. No new paraphrase or correction verdict is introduced here.
    inventory = payload.get("source_inventory")
    if inventory is not None:
        reverse = {u["unit_id"]: key for key, u in source.items()}
        for claim in inventory["claims"]:
            claim["source_unit_ids"] = [reverse[key] for key in claim["source_unit_ids"]]
        for row in inventory["unit_coverage"]: row["unit_id"] = reverse[row["unit_id"]]
    request["instructions"] += _ATOMIC + (_INVENTORY if stage == review.STAGES[0] else _VERIFY if stage == review.STAGES[2] else "")
    request["prompt_text"] = review._prompt_json(payload)
    request["response_format"] = response_format(stage, source, inventory=inventory, target=target)
    return request


def hydrate(raw, stage, request, units):
    """Resolve only the exact map serialized into this immutable stage request."""
    data = review._parse(raw)
    index = review.STAGES.index(stage)
    if type(data) is not dict:
        review._fail("review_response_shape")
    if data.get("version") != VERSIONS[index]:
        review._fail("review_response_version")
    payload = json.loads(request["prompt_text"])
    if (payload.get("semantic_unit_reference_policy") != POLICY or payload.get("protocol") != PROTOCOL
            or payload.get("stage") != stage):
        review._fail("review_reference_binding")
    source = unit_map(units, "S")
    if payload["source_units"] != [{**unit, "unit_id": key} for key, unit in source.items()]:
        review._fail("review_reference_binding")
    target_units = payload.get("target_units", [])
    target = {u["unit_id"]: u for u in target_units}
    if len(target) != len(target_units) or list(target) != list(unit_map(target_units, "T")):
        review._fail("review_reference_binding")
    result = deepcopy(data)
    span_chars = 0
    def span(unit, *, source_span):
        nonlocal span_chars
        value = _text_span(unit) if source_span else _target_span(unit)
        span_chars += len(review.audit._json(value))
        # These span objects alone are part of the final canonical JSON. Stop
        # repeated large-reference expansion before allocating/serializing it.
        if span_chars > review.audit.MAX_RESPONSE_CHARS:
            review._fail("review_response_bound")
        return value
    result["version"] = (review.INVENTORY_VERSION, review.CORRECTION_VERSION, review.VERIFICATION_VERSION)[index]
    if index == 0:
        review._obj(data, {"version", "claims", "boundaries", "page_visual_coverage"})
        review._list(data["claims"], MAX_CLAIMS)
        inverse = {u["unit_id"]: [] for u in units}
        for claim in result["claims"]:
            review._obj(claim, {"claim_id", "source_unit_ids", "context_unit_ids", "source_image_evidence", "proposition", "axes", "unresolved"})
            owned = _refs(claim["source_unit_ids"], source)
            context = _refs(claim["context_unit_ids"], source)
            if set(claim["source_unit_ids"]) & set(claim["context_unit_ids"]):
                review._fail("review_reference_evidence")
            review._list(claim["source_image_evidence"], 64)
            for image in claim["source_image_evidence"]:
                review._obj(image, {"kind", "page", "bbox"})
                if image["kind"] != "image":
                    review._fail("review_reference_evidence")
            claim["source_unit_ids"] = [u["unit_id"] for u in owned]
            claim["source_evidence"] = [span(u, source_span=True) for u in owned + context] + claim.pop("source_image_evidence")
            del claim["context_unit_ids"]
            for unit in owned: inverse[unit["unit_id"]].append(claim["claim_id"])
        result["unit_coverage"] = [{"unit_id": key, "claim_ids": values} for key, values in inverse.items()]
    elif index == 2:
        review._obj(data, {"version", "claim_results", "boundary_results", "inventory_errors", "unsupported_additions"})
        inverse = {key: [] for key in target}
        review._list(result["claim_results"], MAX_CLAIMS)
        for row in result["claim_results"]:
            review._obj(row, {"claim_id", "status", "target_unit_ids"})
            selected = _refs(row.pop("target_unit_ids"), target, empty=False)
            row["target_spans"] = [span(u, source_span=False) for u in selected]
            for unit in selected: inverse[unit["unit_id"]].append(row["claim_id"])
        result["target_unit_coverage"] = [{"unit_id": key, "claim_ids": values} for key, values in inverse.items()]
        # Legacy verifier uses target IDs derived from exact candidate text.
        # Request short IDs are replaced by that exact caller coordinate key.
        for row, original in zip(result["target_unit_coverage"], target_units):
            row["unit_id"] = f"tp{original['page']}_{original['start']}_{original['sha256'][:16]}"
        review._list(result["inventory_errors"], review.MAX_UNITS)
        for row in result["inventory_errors"]:
            review._obj(row, {"source_unit_ids", "reason"})
            row["source_unit_ids"] = [u["unit_id"] for u in _refs(row["source_unit_ids"], source)]
        review._list(result["unsupported_additions"], review.MAX_UNITS)
        for row in result["unsupported_additions"]:
            review._obj(row, {"target_unit_ids", "reason"})
            row["target_spans"] = [span(u, source_span=False) for u in _refs(row.pop("target_unit_ids"), target, empty=False)]
    if len(review.audit._json(result)) > review.audit.MAX_RESPONSE_CHARS:
        review._fail("review_response_bound")
    return result, {"policy": POLICY, "policy_sha256": review.audit._sha(review.audit._json(descriptor(units))), "request_sha256": review.audit._sha(review.audit._json(request)),
        "unit_map_sha256": review.audit._sha(review.audit._json({"source": source, "target": target})),
        "raw_output_sha256": review.audit._sha(raw), "canonical_response": result}
