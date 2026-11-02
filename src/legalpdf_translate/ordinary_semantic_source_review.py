"""Optional, request-bound source commitment and visual review instructions.

This changes no response schema, evidence map or validator. Absence is handled
by the caller without importing or serializing any policy descriptor.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata

POLICY = "source_commitment_visual_v1"
POLICY_V2 = "source_commitment_visual_v2"
POLICY_V3 = "source_commitment_visual_v3"
POLICY_V4 = "source_commitment_visual_v4"
POLICY_V5 = "source_commitment_visual_v5"
POLICY_V6 = "source_commitment_visual_v6"
POLICY_V7 = "source_commitment_visual_v7"
POLICY_V8 = "source_commitment_visual_v8"
POLICY_V9 = "source_commitment_visual_v9"

_SHARED = """
SOURCE COMMITMENT AND VISUAL REVIEW POLICY:
Preserve the source's linguistic commitments, speaker and attribution without
deciding whether a reported event happened in the world. Keep chronology/aspect
separate from epistemic status: an unproved allegation or denial can clearly
concern a past event. Preserve alleged, reported, conditional, intended and denied
status in the proposition and polarity/modality axis. Determine represented time
from the WHOLE construction and discourse, not isolated verb labels. Conditional
or perfect constructions can represent reported/hypothetical/conjectural past rather than
prospectivity. Distinguish prospective action, current/resultative documentary
state and completed action. Neither a documentary formula, a visible signature
nor a blank area alone authorizes inferring physical execution/nonexecution or
rewriting the clause's time, aspect or modality.
In the existing structured axes/representations, use unspecified when the source
supplies no value; do not add missing-information statements to the translation.
Preserve generic/passive roles
without inventing a personal identity from proximity; an unspecified actor does
not make clear represented timing uncertain. Distinguish an unexpressed actor,
uncertain personal identity and uncertain occurrence; preserve translatable
ambiguity without forcing a unique person. Identify ONLY source-supported roles:
actor, reporter, communication addressee, provider/payer and recipient/beneficiary.
Keep every material quantifier, possessive, legal capacity, conjunction, condition,
negation, modality and participant-number qualifier within its actual scope.
Resolve cross-page anaphora without expanding a limited referent to everyone named
or present. Shared unit citations do not replace expression of facts within them.
Genuine ambiguity preventing a faithful source reading remains uncertain/unresolved
and MUST block; do not change an uncertainty merely to obtain approval.
"""

INVENTORY = _SHARED + """
Survey EVERY supplied original page image first: body, headers, footers, margins,
labels, annotations and stamps. Account for ALL readable textual content, including
short/single-character labels and numerals regardless of apparent importance.
Compare the visual survey with extracted caller units. A larger identifier, nearby
description or semantic interpretation does not cover separately printed text.
For readable content absent from text units, use an image-only claim with
source_unit_ids=[], original source_image_evidence page/bbox, and exact visible
transcription plus enough context to identify its role. Clearly interpretable
selection, cancellation or association marks may instead have a precise visual
description and supported association when no transcription exists. Never infer
such an association from decoration or illegibility. Never invent unit IDs or
duplicate content already faithfully represented by text units. Do not invent
meaning for decoration or an undecipherable mark; genuinely unreadable relevant
text must be unresolved. A visual observation certifies neither authenticity,
legal effect nor physical execution.
Then complete the atomic inventory of extracted units. Split distinct assertions
and denials into atomic claims as needed, while retaining each attribution,
condition, qualifier and negation within the proposition it scopes; share citations
when necessary. Do not replace their material facts with a broad catchall. Reviewed visual coverage
is an assertion of survey, not proof of completeness. Image Off must remain
text_only with no visual inspection claim or invented image-only evidence.
"""

CORRECTION = _SHARED + """
Compare each atomic assertion and its qualification scope against the originals,
not merely against an inventory paraphrase. Correct material defects while retaining
already adequate equivalent Arabic. Independently inspect supplied source images
for ALL readable content missing from the inventory or primary, including short
labels and image-only claims. Restore source-supported visible-only
literals character-for-character using the existing protected-literal/bidi
protocol, preserving every existing protected occurrence and visible residual.
Never invent unreadable content, normalize a literal's glyphs or drop content to
fit a schema. The same ordinary correction validators remain mandatory. If source
meaning or a material visual reading is genuinely unresolved, stop unapproved.
Image Off remains text only and cannot establish visual completeness.
"""

VERIFICATION = _SHARED + """
Begin an independent source-image/text comparison with the final candidate, not
the inventory checklist. Challenge inventory and candidate against whole original
constructions/discourse. Citation coverage and visual-coverage flags are not proof
of fact-level completeness. Check ALL readable source content, including short
labels, annotations and marks, and every material qualifier within each cited unit.
If omitted from the inventory, report inventory_errors (source_unit_ids=[] for an
image-only omission, with a reason locating page/region and missing content), even
when every extracted unit was cited. If a claimed item is absent or contradicted in
the candidate, use the existing missing/contradiction results. Challenge inaccurate
inventory propositions and proposition/axis contradictions rather than forcing the
candidate to follow them. Genuine unresolved material readings must fail approval.
Verify exact visible literals through actual candidate evidence and existing
owner/coverage rules; never invent text units or waive literal/bidi guards.
Image Off cannot support a visual completeness claim. Do not repair or iterate.
"""

SUFFIXES = dict(zip(("source_inventory", "correction", "verification"),
                    (INVENTORY, CORRECTION, VERIFICATION)))

_INVENTORY_OLD_AMBIGUITY = (
    "Unspecified is not uncertain: use uncertain/unresolved when original meaning cannot be resolved."
)
_INVENTORY_NEW_AMBIGUITY = (
    "Unexpressed source values are unspecified. Preserve a readable intrinsic ambiguity when its "
    "linguistic commitment can be represented faithfully without choosing an unsupported reading. "
    "Use uncertain/unresolved when unreadability, conflicting evidence or an indeterminate reading "
    "prevents a faithful representation of a material source commitment; do not change an uncertainty "
    "merely to obtain approval."
)
_SHARED_OLD_AMBIGUITY = (
    "Genuine ambiguity preventing a faithful source reading remains uncertain/unresolved\n"
    "and MUST block; do not change an uncertainty merely to obtain approval.\n"
)
_SHARED_NEW_AMBIGUITY = (
    "Faithful representation preserves what the source asserts, denies, reports, questions and leaves open.\n"
    "Describe an open attachment or scope in the inventory without selecting an unsupported actor or\n"
    "interpretation. The Arabic must preserve the supported ambiguity through an equivalent construction,\n"
    "without adding alternative explanations or missing-information commentary absent from the source.\n"
    "If the material distinction or ambiguity cannot be preserved faithfully, retain unresolved and stop\n"
    "unapproved.\n"
)


# Fresh-only additions; prior suffix constants remain immutable.
V3_ADDITIONS = {
    "source_inventory": """Before splitting a coordinated or elliptical source construction into atomic claims, determine which extent, quantifier, negation, temporal, modal, conditional and attribution modifiers govern each predicate. Carry every shared material modifier into EACH independently assessed claim whose predicate it governs, including that claim's proposition and applicable axes. A modifier recorded only in a neighboring claim, shared citation, or broad group description does not qualify another claim. Conversely, do not distribute a modifier beyond its source-supported scope. Recheck the resulting claims together against the whole source construction so that splitting neither loses a shared commitment nor adds one. Preserve genuinely open scope through a faithful representation; if a material distinction cannot be represented faithfully, retain unresolved and stop unapproved.
""",
    "correction": """Produce professionally usable legal Arabic as well as complete source-faithful content. Use established Arabic terms for the function and procedural capacity actually described in the source. Resolve false friends by context; do not use a superficially similar word for a different legal or ordinary function. Keep repeated role references consistent when their referent and function are the same, while preserving distinct capacities or changes of capacity stated in the source. Apply terminology and contextual guidance only where compatible with the source; they are not evidence of additional facts.

Read the corrected Arabic continuously and repair nonstandard role terminology, unnatural verb complements or collocations, and grammatical agreement that impair professional readability. Make the smallest source-faithful repair. Preserve who did what to whom, reported speech, uncertainty, negation, causality, and all required literals. Do not add legal status, intent, hostility, legal conclusions or jurisdiction-specific powers to make a phrase sound more formal. Use gender agreement supported by the source; do not infer personal gender from a name, or turn a valid generic form label into an unsupported individual assertion. Equally natural, accurate wording is acceptable; do not rewrite solely to prefer a synonym or a more ornate style.
""",
    "verification": """Ground each claim result in the actual source commitment and the exact candidate wording within the supplied target units. Check the material components separately: predicate, functional role, referent, chronology/aspect, epistemic status and scoped qualifiers. Read complete constructions and discourse; an equivalent paraphrase need not repeat inventory wording. Conjectural or reported language can preserve a completed past event without asserting certainty.
Use equivalent only when the candidate entails all material components with the source's qualifications; mere occurrence of relevant words or a matching topic is insufficient. Use missing for a material component genuinely absent from the candidate, not merely for an awkward expression or a different adequate paraphrase. Partial preservation is not approval: distinguish the preserved components from the defective component when selecting the existing non-equivalent result. Use contradiction when candidate wording commits to an incompatible component, including a materially wrong functional role. Use unresolved when the material candidate reading cannot be determined faithfully. Do not convert a term or collocation concern into absence of unrelated facts in the same claim or in a neighboring claim.
Cite the existing target_unit_ids containing the actual evidence, and use only the response schema's supported fields and statuses. Where a supported reason field applies, identify the precise source component and relevant quoted wording; do not invent a per-claim explanation field or misuse inventory_errors or unsupported_additions to house a target-only prose concern. Independently retain every genuine inventory error, even when the candidate happens to supply the omitted commitment. No lexical match, contextual guess or stylistic preference overrides source-faithfulness, literal/bidi guards, unresolved gates or the unchanged validator. Do not repair, iterate or pre-approve a result.
""",
}


_CORRECTION_LITERAL_OLD = 'Preserve every protected literal occurrence and the LRI [[literal]] PDI protocol.'
_CORRECTION_LITERAL_NEW = 'Preserve every protected literal occurrence with visible ASCII [[literal]] delimiters; the application supplies the directional isolates.'
V4_CORRECTION_ADDITION = """In corrected_text, serialize every protected literal using the visible ASCII delimiters [[ and ]] around its exact literal content. ASCII describes the delimiters, not the literal content: preserve accented and non-Latin characters, punctuation, whitespace and every required occurrence exactly. Do not add invisible directional controls or NUL characters as protocol markers, or substitute control-code numbers or names for the delimiters. The application supplies canonical directional isolates after JSON parsing using its existing normalizer. Do not decode or reinterpret genuine backslash-u text within a source literal; preserve that text exactly. Normal JSON escaping still applies to literal content. This output representation does not relax literal fidelity or validation requirements; all source-faithful semantic correction requirements remain in force.
Preserve the precise relation expressed by the source. Distinguish possession, temporary custody, source, recipient and ownership; do not replace one relation with another or infer ownership from possession or proximity. Keep quantified denials and affirmations scoped to the relation and participants actually stated, without narrowing or broadening that scope.
"""
# Fresh-only precision additions; inherited stage text stays immutable.
V5_ADDITIONS = {
    "correction": """Preserve explicit object types, subtypes and meaning-bearing qualifiers through accurate Arabic terms or unambiguous target references. A broader category is inadequate when the distinction is lost; everyday plausibility does not restore an omitted distinction. Compare the actual source and candidate in context; an inventory label or paraphrase cannot authorize generalization or a stronger relationship. Do not strengthen use, handling, access, association or proximity into ownership or another unsupported relationship. Retain idiomatic, source-equivalent wording, including grammatical possessives that add no unsupported commitment. Correct material losses, without rewriting an adequate equivalent for word matching or synonym preference.
""",
    "source_inventory": """Preserve explicit object types, subtypes and meaning-bearing qualifiers in each inventory proposition through accurate terms or unambiguous references. A broader category is inadequate when it loses an explicit distinction; everyday plausibility does not supply that distinction. Inventory propositions state source commitments, so labels or metalinguistic shorthand must not silently generalize them. Use neutral wording when an unnecessary possessive or relationship expression could add a stronger or unsupported commitment about possession, custody or ownership. Use, handling, access, association and proximity do not by themselves establish ownership. Grammatical possessives remain acceptable when source-equivalent in context, including inalienable or discourse-supported references. Accurate equivalent paraphrases require neither word-for-word matching nor a preferred synonym.
""",
}

# One fresh-only boundary, identical in inventory, correction and verification.
V6_VISUAL_SCOPE = """Apply the same visual-content boundary to inventory, correction and verification. Account for ALL readable text wherever it appears, including within a logo, crest, stamp or seal, and repeated headers/footers on each original page. Preserve source-supported document-specific meaning conveyed by stamps, signatures, selection, cancellation or association marks; where no transcription exists, use the existing precise visual-description and association evidence, without inferring authenticity, legal effect, identity or physical execution. Generic nontext institutional artwork alone is not a source proposition requiring invented prose or a neutral label in the translation, and its pictorial presence alone is not an inventory omission. This exception does not cover readable text or a document-specific meaning-bearing mark. Judge each page and region from its own supplied original evidence; recurrence on another page is not evidence here. If the distinction or a relevant material reading is unresolved, retain unresolved and stop unapproved. Do not suppress a real inventory error, target defect or unsupported addition; all existing response schemas, evidence, literal/bidi and approval rules remain mandatory.
"""

_LITERAL_PROJECTION_SEMANTICS = """correction_visible_literal_wrappers_v1: On decoded correction-request strings only, remove the outer U+2066 and U+2069 of an exact, nonempty, well-formed, nonnested U+2066[[literal]]U+2069 protocol token. Preserve every character inside [[literal]], both ASCII delimiters, order, whitespace, punctuation and multiplicity. HT, LF and CR (including CRLF sequences) are permitted inside a proven wrapper and remain byte-for-byte unchanged. Act only on primary_pages[].text and literal_protocol[].source_text. Bare [[literal]] tokens stay unchanged. If a syntactically unambiguous canonical token contains other Cc/Cf characters, retain its ENTIRE original wrapper and contents unchanged rather than project, reject or sanitize it. Fail closed only for ambiguous nested/malformed/overlapping protocol-wrapper candidates; never expose and strip an inner match. This is not a generic raw-bracket/content validator. Unrelated directional runs/characters outside protocol-owned wrappers stay exact. A proven whole protocol token encountered inside an ambient directional isolate is retained with its entire wrapper and the surrounding run unchanged. Ambient isolation alone is not nested protocol ownership; unrelated directional runs are not validated or repaired by this projection. Requests are not universally control-free: originals, unrelated runs and abstained wrappers remain exact. Never unicode_escape, globally strip controls, normalize glyphs, change originals/source units/images/context/expected tokens, transform provider responses or project any inventory/verification field. Enforce existing bounded request text limits and linear work. The unchanged evaluator/normalizer canonicalizes an accepted corrected candidate before verification.
"""


def project_visible_literal_wrappers(text):
    """Project only unambiguous app protocol wrappers; never sanitize contents."""
    if not isinstance(text, str) or len(text) > 300_000:
        raise ValueError("Invalid visible literal request projection.")
    lri, pdi = "\u2066", "\u2069"
    openers = {"\u2066", "\u2067", "\u2068"}
    chunks, cursor, index, isolate_depth, bracket_depth = [], 0, 0, 0, 0
    while index < len(text):
        if text.startswith(lri + "[[", index):
            end = text.find("]]" + pdi, index + 3)
            if (bracket_depth or end < 0
                    or text.find("[[", index + 3, end) >= 0
                    or text.find("]]", index + 3, end) >= 0
                    or text[end + 2:end + 3] != pdi):
                raise ValueError("Ambiguous visible literal request projection.")
            literal = text[index + 3:end]
            if any(char in openers or char == pdi for char in literal):
                raise ValueError("Ambiguous visible literal request projection.")
            whole = text[index:end + 3]
            abstain = isolate_depth or not literal or any(
                unicodedata.category(char) in {"Cc", "Cf"} and char not in "\t\r\n"
                for char in literal)
            chunks.extend((text[cursor:index], whole if abstain else "[[" + literal + "]]"))
            cursor = index = end + 3
            continue
        char = text[index]
        if char in openers:
            isolate_depth += 1
        elif char == pdi and isolate_depth:
            isolate_depth -= 1
        if text.startswith("[[", index):
            bracket_depth += 1
            index += 2
        elif text.startswith("]]", index):
            bracket_depth = max(0, bracket_depth - 1)
            index += 2
        else:
            index += 1
    chunks.append(text[cursor:])
    return "".join(chunks)


def _project_correction_payload(payload):
    for collection, field in (("primary_pages", "text"), ("literal_protocol", "source_text")):
        rows = payload.get(collection)
        if not isinstance(rows, list):
            raise ValueError("Invalid visible literal request projection.")
        for row in rows:
            if not isinstance(row, dict) or field not in row:
                raise ValueError("Invalid visible literal request projection.")
            row[field] = project_visible_literal_wrappers(row[field])
    return payload


V7_INVENTORY_SCOPE = """Inventory propositions state commitments communicated by the original document, not commentary generated by extraction or review. Do not add an assertion about how an extractor, OCR system, barcode font or encoding represents the evidence unless the original document itself communicates that assertion. Do not combine such process commentary with a source commitment or split it into another purported source claim. Distinguish the document's readable content from a technical representation of that content using the supplied original evidence, while preserving the original raw source units, their IDs and evidence without rewriting, stripping or normalizing them. Use only the existing evidence fields as defined. A difference between extracted and visible text does not itself authorize changing a protected literal; every such change remains subject to the existing literal and source-authority rules.
Preserve all genuinely printed readable symbols, including percent signs and asterisks, and preserve source-authored statements about extraction, OCR, fonts or encoding when they are part of the document's substantive content. Neither a keyword, font name, apparent technical format nor a desired approval establishes that content is an extraction artifact. If the material reading or the distinction cannot be established from the available original evidence, retain uncertain/unresolved and stop unapproved; Image Off cannot supply visual proof. Do not suppress a real inventory omission, false proposition, candidate defect or unsupported addition. All existing atomicity, evidence, schema, literal/bidi and approval requirements remain mandatory.
"""


V8_CORRECTION_ADDITION = """VISIBLE SOURCE REPRESENTATION:
Distinguish readable characters communicated by the original document from technical characters present only in extraction, OCR or font-encoding representations. Use the bound original evidence for that page and region. A raw source unit or verbatim evidence quote may preserve a technical representation; its inclusion does not establish that every character is displayed as readable source text. An inventory proposition is derived evidence, not authority over the original. Compare the complete readable candidate expression, including symbols adjacent to a protected literal, rather than accepting a matching identifier substring alone. Interpret protocol delimiters and directional isolates under the existing literal protocol; they are not additional source text.
Preserving visible residuals means preserving source-supported content. It does not require retaining output-only technical characters outside protected owners when the supplied original image clearly establishes that they are not displayed as readable source characters. Correct such a supported discrepancy through the ordinary correction contract. Preserve every protected literal occurrence, converted-group obligation and all existing validation requirements. Changing a protected value or owned enclosure still requires its existing authority path; this instruction grants no exemption.
Preserve genuinely readable source symbols, including percent signs, asterisks, footnote marks and enclosures, and preserve source-authored statements about extraction, OCR, fonts or encoding. A font name, keyword, apparent code format, inventory wording or desired approval is not proof of an artifact. Do not strip punctuation by pattern, normalize source glyphs, rewrite raw source units/evidence or infer missing content. If the distinction cannot be established from the supplied original evidence, retain unresolved and stop unapproved. Image Off cannot supply visual proof. All existing schemas, evidence ownership, literal/bidi, source-authority and approval rules remain mandatory.
"""

V8_VERIFICATION_ADDITION = """VISIBLE SOURCE REPRESENTATION:
Independently compare the complete readable candidate expression with the bound original evidence for that page and region, including symbols adjacent to a protected literal. A matching identifier substring, claim topic or literal count does not establish that the whole expression is faithful. Interpret protocol delimiters and directional isolates under the existing literal protocol; they are not additional source text. Distinguish readable characters communicated by the original from technical characters present only in extraction, OCR or font-encoding representations. A raw source unit or verbatim evidence quote may preserve that technical representation without establishing that every character is displayed as readable source text. Challenge the inventory as well as the candidate; inventory wording is not authority over the original.
Unsupported readable symbols in the candidate remain a source-fidelity defect even when the protected value itself matches. Report the actual defect under the existing claim-result or unsupported-addition contract, using exact owned target evidence as appropriate. Do not approve merely because a clean identifier occurs inside a longer expression. Do not force a finding category to obtain repair eligibility, suppress another error, invent a field or prescribe a correction. Existing protected-value, enclosure and converted-group obligations remain in force; this instruction grants no exemption.
Preserve genuinely readable source symbols, including percent signs, asterisks, footnote marks and enclosures, and preserve source-authored statements about extraction, OCR, fonts or encoding. A font name, keyword, apparent code format or desired approval is not proof of an artifact. Do not strip punctuation by pattern, normalize source glyphs, rewrite raw source units/evidence or infer missing content. If the distinction cannot be established from the supplied original evidence, retain unresolved and stop unapproved. Image Off cannot supply visual proof. Remain blind to prior correction verdicts and reasons; do not repair, iterate or pre-approve a result. All existing schemas, evidence ownership, literal/bidi, source-authority and approval rules remain mandatory.
"""


V9_CORRECTION_ADDITION = '\nPARTICIPANT DIRECTION IN DEMANDS, PAYMENTS AND DELIVERIES: Read the complete source relation and distinguish the requester or claimant, the communication addressee, the person performing or providing the requested action, and the payer, recipient or beneficiary, only where the source supports each role. The person wanting or requesting an action is not necessarily its performer. Preserve source-established direction in the actual Arabic clause and its target context. A delivery or payment noun governed by desire or demand can leave the performer or recipient unclear; correct that material ambiguity when the source establishes the relation. Preserve an adequate active, passive, nominal or idiomatic anaphoric rendering when its target context makes the same relation unambiguous. Do not infer a payer or performer that the source leaves unspecified, strengthen an intrinsically uncertain source relation, require repeated names, or rewrite a faithful equivalent for stylistic preference. All existing literal, enclosure, converted-group, source-authority and schema requirements remain mandatory.\n'
V9_VERIFICATION_ADDITION = "\nPARTICIPANT DIRECTION IN DEMANDS, PAYMENTS AND DELIVERIES: Independently compare the source-established participant relation with what the actual Arabic clause and its relevant target context communicate. Distinguish the requester or claimant and communication addressee from the performer, provider or payer and the recipient or beneficiary. A correct inventory role or a source-supported interpretation does not by itself establish that the candidate expresses that direction. Do not silently fill a material target-role gap from the source, from the expected claim, or from the fact that one reading would be faithful. In particular, a delivery or payment noun under desire or demand may permit the requester-as-performer reading; assess whether the candidate's own grammar and context unambiguously preserve the source-established relation. Accept adequate active, passive, nominal and idiomatic anaphoric equivalents; do not require repeated names or invent a source-unspecified payer or performer. Preserve genuine source uncertainty. Report any material loss, reversal or unresolved target direction through only the existing supported result fields and statuses; do not force a finding to obtain repair eligibility or invent a field. Remain blind to prior verdicts and reasons, and do not repair or pre-approve. All existing literal, enclosure, converted-group, source-authority and approval requirements remain mandatory.\n"


def _suffixes(policy):
    if type(policy) is not str or policy not in (POLICY, POLICY_V2, POLICY_V3, POLICY_V4, POLICY_V5, POLICY_V6, POLICY_V7, POLICY_V8, POLICY_V9):
        raise ValueError("Invalid source review policy.")
    if policy == POLICY:
        return SUFFIXES
    if any(text.count(_SHARED_OLD_AMBIGUITY) != 1 for text in SUFFIXES.values()):
        raise ValueError("Unexpected legacy source ambiguity instruction.")
    suffixes = {stage: text.replace(_SHARED_OLD_AMBIGUITY, _SHARED_NEW_AMBIGUITY)
                for stage, text in SUFFIXES.items()}
    if policy in (POLICY_V3, POLICY_V4, POLICY_V5, POLICY_V6, POLICY_V7, POLICY_V8, POLICY_V9):
        suffixes = {stage: text + V3_ADDITIONS[stage] for stage, text in suffixes.items()}
        if policy in (POLICY_V4, POLICY_V5, POLICY_V6, POLICY_V7, POLICY_V8, POLICY_V9):
            suffixes["correction"] += V4_CORRECTION_ADDITION
    if policy in (POLICY_V5, POLICY_V6, POLICY_V7, POLICY_V8, POLICY_V9):
        for stage, addition in V5_ADDITIONS.items():
            suffixes[stage] += addition
    if policy in (POLICY_V6, POLICY_V7, POLICY_V8, POLICY_V9):
        suffixes = {stage: text + V6_VISUAL_SCOPE for stage, text in suffixes.items()}
    if policy in (POLICY_V7, POLICY_V8, POLICY_V9):
        suffixes["source_inventory"] += V7_INVENTORY_SCOPE
    if policy in (POLICY_V8, POLICY_V9):
        suffixes["correction"] += V8_CORRECTION_ADDITION
        suffixes["verification"] += V8_VERIFICATION_ADDITION
    if policy == POLICY_V9:
        suffixes["correction"] += V9_CORRECTION_ADDITION
        suffixes["verification"] += V9_VERIFICATION_ADDITION
    return suffixes


def descriptor(policy=POLICY):
    result = {"policy": policy, "stage_instruction_sha256": {
        stage: hashlib.sha256(text.encode("utf-8")).hexdigest()
        for stage, text in _suffixes(policy).items()}}
    if policy in (POLICY_V2, POLICY_V3, POLICY_V4, POLICY_V5, POLICY_V6, POLICY_V7, POLICY_V8, POLICY_V9):
        result["inventory_ambiguity_instruction"] = {
            "replaced_sha256": hashlib.sha256(_INVENTORY_OLD_AMBIGUITY.encode()).hexdigest(),
            "replacement_sha256": hashlib.sha256(_INVENTORY_NEW_AMBIGUITY.encode()).hexdigest(),
        }
    if policy in (POLICY_V4, POLICY_V5, POLICY_V6, POLICY_V7, POLICY_V8, POLICY_V9):
        result["correction_literal_instruction"] = {
            "replaced_sha256": hashlib.sha256(_CORRECTION_LITERAL_OLD.encode()).hexdigest(),
            "replacement_sha256": hashlib.sha256(_CORRECTION_LITERAL_NEW.encode()).hexdigest(),
        }
        result["correction_request_projection"] = {
            "version": "correction_visible_literal_wrappers_v1",
            "fields": ["primary_pages[].text", "literal_protocol[].source_text"],
            "semantics_sha256": hashlib.sha256(_LITERAL_PROJECTION_SEMANTICS.encode()).hexdigest(),
        }
    return result


def check_policy(policy, unit_reference_policy):
    if (type(policy) is not str or policy not in (POLICY, POLICY_V2, POLICY_V3, POLICY_V4, POLICY_V5, POLICY_V6, POLICY_V7, POLICY_V8, POLICY_V9)
            or unit_reference_policy != "caller_unit_refs_v1"):
        raise ValueError("Invalid source review policy.")


def adapt_request(request, stage, *, encode_payload, policy=POLICY):
    """Bind the exact suffix descriptor after immutable compact adaptation."""
    suffixes = _suffixes(policy)
    payload = json.loads(request["prompt_text"])
    if (stage not in suffixes or payload.get("stage") != stage
            or payload.get("semantic_unit_reference_policy") != "caller_unit_refs_v1"
            or "semantic_source_review_policy" in payload):
        raise ValueError("Invalid source review policy request.")
    instructions = request["instructions"]
    if policy in (POLICY_V2, POLICY_V3, POLICY_V4, POLICY_V5, POLICY_V6, POLICY_V7, POLICY_V8, POLICY_V9) and stage == "source_inventory":
        if instructions.count(_INVENTORY_OLD_AMBIGUITY) != 1:
            raise ValueError("Unexpected inherited source ambiguity instruction.")
        instructions = instructions.replace(_INVENTORY_OLD_AMBIGUITY, _INVENTORY_NEW_AMBIGUITY)
    if policy in (POLICY_V4, POLICY_V5, POLICY_V6, POLICY_V7, POLICY_V8, POLICY_V9) and stage == "correction":
        if instructions.count(_CORRECTION_LITERAL_OLD) != 1:
            raise ValueError("Unexpected inherited correction literal instruction.")
        instructions = instructions.replace(_CORRECTION_LITERAL_OLD, _CORRECTION_LITERAL_NEW)
        payload = _project_correction_payload(payload)
    payload["semantic_source_review_policy"] = descriptor(policy)
    return {**request, "instructions": instructions + suffixes[stage],
            "prompt_text": encode_payload(payload)}
