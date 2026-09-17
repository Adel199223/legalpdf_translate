"""Opt-in block association at the existing source-winner/translation boundary.

No model selection, OCR policy, source recovery or Word automation lives here.
Coverage is structural evidence, not a certification of legal equivalence.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import re
import threading
import time
import unicodedata
from types import SimpleNamespace

from .config import OPENAI_MODEL
from .document_structure import (PageStructure, SOURCE_STRUCTURE_VERSION, STRUCTURE_VERSION, classify_document_boundaries,
    apply_reviewed_document_boundary,
    rebind_page_structure, structure_from_ordered, structure_from_text)
from .formatting_support import digest_text, fingerprint, flatten_blocks, confirmed_source_continuation
from .openai_client import ApiCallError, is_openai_auth_failure
from .output_normalize import normalize_output_text_with_stats
from .pdf_text_order import NATIVE_EXTRACTION_VERSION
from .source_document import source_page_dimensions, source_page_identity
from .source_readiness import (SOURCE_READINESS_VERSION, source_readiness_diagnostics,
    verify_source_review, verify_reviewed_page, SourceReadinessError)
from .reviewed_source import REVIEWED_SOURCE_VERSION
from .document_structure import validate_page_structure
from .structured_arabic_literals import (StructuredArabicLiteralError,
    prepare_structured_arabic_source, normalize_structured_arabic_translation,
    source_person_name_for_field, STRUCTURED_ARABIC_LITERALS_VERSION)
from .structured_glossary import (build_structured_glossary, StructuredGlossaryError,
    STRUCTURED_GLOSSARY_VERSION)
from .structured_artifacts import publish_structured_page, StructuredArtifactError
from .translation_structure import (PROTOCOL_VERSION, RETRY_POLICY_VERSION, BlockCoverageError,
    build_structured_page_prompt, build_structured_retry_prompt, parse_structured_translation,
    structured_response_format, structured_system_instructions, translation_fingerprint,
    request_fingerprint)
from .types import OcrMode, PageStatus, TargetLang
from .validators import validate_ar, validate_enfr

INTEGRATION_VERSION = "new_runs_v1"
CONTEXT_POLICY_VERSION = "direct_winner_neighbors_v1"
CITATION_POLICY_VERSION = "article_heads_v4_arabic_punctuation"
MAX_OUTPUT_TOKENS = 24000
MAX_SOURCE_CHARS = 120000
_NUMBER = re.compile(r"\d[\d.,]*\d|\d")
_ARTICLE = re.compile(r"(?:\bart(?:igo|icle)?s?\.?\s*|(?:المادة|المادتان|المادتين|المواد)\s*)(\d+(?:[º°.]|\s*[-–]\s*[A-Z])?)", re.I)
# Continue only a closed citation grammar. Horizontal whitespace is deliberate:
# a new source/target line or sentence never borrows the previous article head.
_CITATION_JOIN = re.compile(r"[ \t]*(?:(?:[,،][ \t]*)?(?:\b(?:e|et|and)\b[ \t]*|و[ \t]*)|[,،][ \t]*)", re.I)
_CITATION_SUBDIVISION = re.compile(
    r"[ \t]*,[ \t]*(?:(?P<number>n(?:\.[º°]|[º°]|\.)s?|nos?\.?|paragraphs?|paragraphes?|§{1,2})"
    r"|(?P<letter>al[íi]n[ée]as?|subparagraphs?|points?))[ \t]+", re.I)
_CITATION_SUBNUMBER = re.compile(r"\d+(?![\wº°]|[./][\wº°]|,[\d]|[-–][A-Z0-9])", re.I)
_CITATION_SUBLETTER = re.compile(r"[a-z]\)?(?!\w)", re.I)
_CITATION_ELIDED_NUMBER = re.compile(
    r"\d+(?:(?:\.[º°]|[º°])|[ \t]*[-–][ \t]*[A-Z])?"
    r"(?![\wº°]|[./][\wº°]|,[\d]|[-–][A-Z0-9])", re.I)
_CITATION_LEGAL_TAIL = re.compile(
    r"[ \t]*(?:(?:do|da|dos|das|du|des|de|of(?:[ \t]+the)?)"
    r"[ \t]+(?:c[oó]digo|code|lei|loi|law|act)\b|من[ \t]+(?:القانون|قانون)\b)", re.I)
_MAX_CITATION_TAIL_CHARS = 512
_MAX_CITATION_TAIL_STEPS = 64
_DATE = re.compile(r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{4})(?!\d)")
_EVENTS = {"hearing": r"audiência(?:\s+de\s+julgamento)?|hearing|audience|جلسة",
           "questioning": r"interrogatório|questioning|interrogatoire|استجواب",
           "payment": r"pagamento|payment|paiement|الدفع|السداد"}
_NAME = re.compile(r"(?i:nome|name|arguido|testemunha|signatário)\s*[:,\-]?\s*([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+(?:\s+(?:(?:da|de|do|dos|das)\s+)?[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+){1,5})")


def _digits(text):
    return "".join(str(unicodedata.digit(c)) if c.isdecimal() else c for c in text)


def _citation_heads(text):
    """Count explicit heads and conservative, contiguous coordinated articles.

    Repeating an article noun in translation must not create a false extra head.
    Marked subdivisions consume their own lists first. After a subdivision an
    elided article requires an ordinal/suffix, so bare paragraph numbers cannot
    be promoted to articles. Unrecognized prose, dates, identifiers, line breaks
    and sentence-ending periods stop the chain. This is not a general legal
    citation parser; unsupported grammar keeps the existing conservative check.
    """
    normalize = lambda value: re.sub(r"[º°. ]", "", value)
    result = Counter()
    for head in _ARTICLE.finditer(text):
        result[normalize(head.group(1))] += 1
        cursor = head.end()
        # The existing explicit-head expression consumes the dot in 24.º.
        # A bare consumed dot instead terminates the sentence; never cross it.
        if head.group(1).endswith("."):
            if text[cursor:cursor + 1] in {"º", "°"}:
                cursor += 1
            else:
                continue
        end = min(len(text), cursor + _MAX_CITATION_TAIL_CHARS)
        has_subdivision = False
        steps = 0
        while cursor < end and steps < _MAX_CITATION_TAIL_STEPS:
            steps += 1
            subdivision = _CITATION_SUBDIVISION.match(text, cursor, end)
            if subdivision is not None:
                value_pattern = _CITATION_SUBNUMBER if subdivision.group("number") else _CITATION_SUBLETTER
                value = value_pattern.match(text, subdivision.end(), end)
                if value is None:
                    break
                cursor = value.end()
                has_subdivision = True
                while steps < _MAX_CITATION_TAIL_STEPS:
                    join = _CITATION_JOIN.match(text, cursor, end)
                    value = value_pattern.match(text, join.end(), end) if join is not None else None
                    if value is None:
                        break
                    steps += 1
                    cursor = value.end()
                continue
            join = _CITATION_JOIN.match(text, cursor, end)
            value = _CITATION_ELIDED_NUMBER.match(text, join.end(), end) if join is not None else None
            if value is None:
                break
            raw = value.group()
            if has_subdivision and not re.search(r"[º°]|[-–]", raw):
                break
            tail = value.end()
            while tail < end and text[tail] in " \t":
                tail += 1
            # A cap is not a document end, and a number before a word such as
            # 'days' or 'May' is not accepted merely because it follows 'and'.
            # Arabic comma joins the same bounded lists as ASCII comma;
            # either semicolon closes a head but never continues its list.
            closed = (tail == len(text) or tail < end and text[tail] in ".,،;؛:)]"
                      or _CITATION_JOIN.match(text, value.end(), end) is not None
                      or _CITATION_LEGAL_TAIL.match(text, value.end(), end) is not None)
            if not closed:
                break
            result[normalize(raw)] += 1
            cursor = value.end()
            has_subdivision = False
    return result


def _events(text):
    result = {}
    for name, expression in _EVENTS.items():
        dates = []
        for event in re.finditer(expression, _digits(text), re.I):
            tail = _digits(text)[event.end():event.end() + 160]
            following = re.search("|".join(_EVENTS.values()), tail, re.I)
            if following:
                tail = tail[:following.start()]
            date = _DATE.search(tail)
            if date:
                dates.append(tuple(int(part) for part in date.groups()))
        if dates:
            result[name] = Counter(dates)
    return result


def validate_block(source, translated, lang, contract, review_codes):
    if not source["text"].strip() and not translated.strip():
        return ""
    if lang == TargetLang.AR:
        try:
            normalized = normalize_structured_arabic_translation(source["text"], translated,
                                                                  glossary_contract=contract)
        except StructuredArabicLiteralError as exc:
            raise BlockCoverageError("block_language_or_token_defect", block_id=source["id"],
                                     detail_code=exc.code) from None
        verdict = validate_ar(normalized)
    else:
        normalized, _ = normalize_output_text_with_stats(translated, lang=lang)
        verdict = validate_enfr(normalized, lang=lang)
    if not verdict.ok:
        raise BlockCoverageError("block_language_or_token_defect", block_id=source["id"])
    left = re.sub(r"[\[\]\u2066\u2069]", "", _digits(source["text"]))
    right = re.sub(r"[\[\]\u2066\u2069]", "", _digits(normalized))
    if Counter(_NUMBER.findall(left)) != Counter(_NUMBER.findall(right)):
        raise BlockCoverageError("block_numeric_association_defect", block_id=source["id"])
    source_citations = _citation_heads(left)
    if source_citations and source_citations != _citation_heads(right):
        raise BlockCoverageError("block_citation_association_defect", block_id=source["id"])
    source_events, target_events = _events(left), _events(right)
    for event, dates in source_events.items():
        if event not in target_events:
            # A missing/unrecognized event cannot silently count as a passed check.
            review_codes.add("event_association_not_evaluated")
        elif dates != target_events[event]:
            raise BlockCoverageError("block_event_date_defect", block_id=source["id"])
    for name in _NAME.findall(source["text"]):
        if source["text"].count(name) != normalized.count(name):
            raise BlockCoverageError("block_name_defect", block_id=source["id"])
    return normalized


def _source_table_person_names(source: PageStructure) -> dict[str, str]:
    """Person cells need a unique first-row field in the same source table/column.

    Do not infer a name from a generic table role, an adjacent cell or another
    page. This supplements block-local person attribution without altering any
    source text, source geometry or target-provided evidence.
    """
    headers = {}
    for block in source.blocks:
        if (block.role == 'table_cell' and block.table_id and block.row == 0
                and type(block.col) is int and block.col >= 0):
            headers.setdefault((block.table_id, block.col), []).append(block.text)
    names = {}
    for block in source.blocks:
        if (block.role != 'table_cell' or not block.table_id or type(block.row) is not int
                or block.row <= 0 or type(block.col) is not int or block.col < 0):
            continue
        fields = headers.get((block.table_id, block.col), ())
        if len(fields) == 1:
            name = source_person_name_for_field(fields[0], block.text)
            if name is not None:
                names[block.id] = name
    return names


class NewTranslationBlocks:
    def __init__(self, workflow, config, selected_pages, *, source_hash, context_hash):
        self.model = getattr(workflow, "_translation_model", OPENAI_MODEL)
        self.workflow, self.config = workflow, config
        self.acceptance = getattr(workflow, "_acceptance_continuation", None)
        self.ordinary_review = getattr(workflow, "_reviewed_source_context", None)
        if self.acceptance is not None:
            self.acceptance.validate_selection(selected_pages)
            if config.workers != 1:
                raise StructuredArtifactError("acceptance_requires_serial_dispatch")
            if not config.keep_intermediates:
                raise StructuredArtifactError("acceptance_requires_private_evidence_retention")
        self.selected_pages = frozenset(selected_pages)
        self.source_hash = source_hash
        self.instructions = structured_system_instructions(config.target_lang)
        self.entries = deepcopy(workflow._prompt_glossaries_by_lang.get(config.target_lang.value, []))
        self.tiers = tuple(workflow._enabled_glossary_tiers_by_lang.get(config.target_lang.value, [1, 2]))
        self.addendum = workflow._prompt_addendum_by_lang.get(config.target_lang.value, "")
        self.page_identities = {n: source_page_identity(config.pdf_path, n) for n in selected_pages}
        self.reviewed_evidence = (self.ordinary_review.evidence if self.ordinary_review is not None
                                 else getattr(self.acceptance, "reviewed_source_evidence", None))
        self.reviewed_page_sizes = ({n: source_page_dimensions(config.pdf_path, n) for n in selected_pages}
                                   if self.reviewed_evidence is not None else None)
        self.reviewed_sources = {}
        if self.ordinary_review is not None:
            self.reviewed_sources = self.ordinary_review.verify(source_hash=self.source_hash,
                page_identities=self.page_identities, page_sizes=self.reviewed_page_sizes)
        if self.acceptance is not None:
            if self.reviewed_evidence is not None:
                self.acceptance.source_review_guard()
            self.reviewed_sources = verify_source_review(self.acceptance.source_review_json,
                page_identities=self.page_identities, source_hash=self.source_hash,
                reviewed_evidence=self.reviewed_evidence, page_sizes=self.reviewed_page_sizes)
        self.identity = {"protocol": PROTOCOL_VERSION, "fingerprint": translation_fingerprint(
            model=self.model, instructions=self.instructions, config=config, glossary=self.entries,
            tiers=self.tiers, addendum=self.addendum, context_hash=context_hash,
            extraction_identity={"integration": INTEGRATION_VERSION, "source_pages": self.page_identities,
                "structure_schema": STRUCTURE_VERSION, "source_structure": SOURCE_STRUCTURE_VERSION,
                "native_extraction": NATIVE_EXTRACTION_VERSION, "context_policy": CONTEXT_POLICY_VERSION,
                **({"acceptance_campaign": self.acceptance.campaign_identity,
                    "source_readiness_version": SOURCE_READINESS_VERSION,
                    "source_review_sha256": digest_text(self.acceptance.source_review_json),
                    "acceptance_full_case_pages": list(self.acceptance.full_case_pages)} if self.acceptance else {}),
                **({"ordinary_source_review": self.ordinary_review.identity}
                   if self.ordinary_review is not None else {})},
            evaluation_identity={"integration": INTEGRATION_VERSION, "retry": RETRY_POLICY_VERSION,
                "citations": CITATION_POLICY_VERSION,
                "arabic": STRUCTURED_ARABIC_LITERALS_VERSION, "glossary": STRUCTURED_GLOSSARY_VERSION,
                "max_output_tokens": MAX_OUTPUT_TOKENS})}
        self.ordered_pages = {}
        self.native_sources = {}
        self.lock = threading.RLock()
        if self.ordinary_review is not None:
            self.check_source()

    def _ordinary_dispatch_cancel_check(self):
        # The real transport calls this through its deadline callback after
        # jitter/backoff and again after accounting.begin, before each SDK send.
        # Keep private acceptance on its existing authorization/recheck path.
        if self.workflow._cancel_event.is_set():
            return True
        self.check_source()
        return False

    def check_source(self):
        if self.ordinary_review is not None:
            identities = {n: source_page_identity(self.config.pdf_path, n) for n in self.selected_pages}
            sizes = {n: source_page_dimensions(self.config.pdf_path, n) for n in self.selected_pages}
            sources = self.ordinary_review.verify(source_hash=self.source_hash,
                page_identities=identities, page_sizes=sizes)
            if sources != self.reviewed_sources:
                raise SourceReadinessError("ordinary_source_review_source_changed")
        elif self.reviewed_evidence is not None:
            self.acceptance.source_review_guard()
        for number, identity in self.page_identities.items():
            if source_page_identity(self.config.pdf_path, number) != identity:
                raise StructuredArtifactError("source_changed_during_run")

    def prepare_native_evidence(self):
        # Read available native evidence once; never OCR a neighbor for context.
        from .workflow import (extract_ordered_page_text, classify_extracted_text_quality,
                               _assess_extraction_integrity)
        self.native_sources.clear()
        if self.reviewed_evidence is not None:
            self.check_source()
            return  # No extraction/OCR or raw-neighbor context in the reviewed lane.
        for number in sorted(self.selected_pages):
            if self.workflow._cancel_event.is_set():
                return
            ordered = extract_ordered_page_text(self.config.pdf_path, number - 1, preserve_structure=True)
            self.ordered_pages[number] = ordered
            quality = classify_extracted_text_quality(ordered.text)
            # This is the same source-routing evidence used by _process_page.
            # Any potential OCR replacement makes the precomputed native text
            # unsuitable as authoritative neighbor context, even if OCR later fails.
            if (ordered.extraction_failed or quality.get("ocr_required")
                    or not self.workflow._is_usable_source_text(ordered.text)
                    or self.config.ocr_mode == OcrMode.ALWAYS
                    or (self.config.ocr_mode == OcrMode.AUTO and quality.get("ocr_helpful"))):
                continue
            try:
                integrity = _assess_extraction_integrity(pdf_path=self.config.pdf_path,
                    page_number=number, target_lang=self.config.target_lang, ordered=ordered)
            except (OSError, ValueError, TypeError):
                # Missing local evidence cannot certify context; normal source
                # processing still owns its existing failure/recovery behavior.
                continue
            if integrity.suspect:
                continue
            source = structure_from_ordered(ordered, page_number=number, source_file_sha256=self.source_hash)
            if source.provenance == "digital_pdf" and not source.uncertain:
                self.native_sources[number] = self._bind_source(source, number=number, text=ordered.text)

    def make_source(self, *, number, ordered, text, ocr_result, ocr_used, merged, suspect):
        if self.reviewed_evidence is not None:
            raise SourceReadinessError("reviewed_source_route_required")
        size = source_page_dimensions(self.config.pdf_path, number)
        source = None
        if not merged and ocr_used and getattr(ocr_result, "structure", None):
            try:
                candidate = rebind_page_structure(ocr_result.structure, page_number=number,
                    source_file_sha256=self.source_hash, page_size=size)
                if candidate.text.split() == text.split():
                    source = candidate
            except (ValueError, TypeError, KeyError):
                pass
        elif not ocr_used and not merged and not suspect:
            candidate = structure_from_ordered(ordered, page_number=number, source_file_sha256=self.source_hash)
            if candidate.text.split() == text.split():
                source = candidate
        if source is None:
            source = structure_from_text(text, page_number=number, source_file_sha256=self.source_hash,
                                         page_size=size)
        if source.text.split() != text.split():
            raise StructuredArtifactError("source_content_binding_failed")
        return self._bind_source(source, number=number, text=text)

    def _bind_source(self, source, *, number, text):
        # Neighbor context and actual dispatch must see the same reviewed
        # boundaries; otherwise a missing-title next document can leak context.
        source.metadata["selected_text_sha256"] = digest_text(text)
        source.metadata["source_page_identity"] = self.page_identities[number]
        source.metadata["source_coverage_status"] = "recognized_words_only"
        source = classify_document_boundaries(source)
        reviewed = self.reviewed_sources.get(number, {}).get("source_structure", {})
        boundary_review = reviewed.get("metadata", {}).get("document_boundary_review")
        if boundary_review is not None:
            source = apply_reviewed_document_boundary(source, boundary_review)
        source.metadata["source_readiness"] = source_readiness_diagnostics(source)
        return source

    def contexts(self, source):
        if self.reviewed_evidence is not None:
            return "", ""  # A page boundary is not a paragraph-continuation decision.
        previous, following = "", ""
        left = self.native_sources.get(source.page_number - 1)
        right = self.native_sources.get(source.page_number + 1)
        if left and confirmed_source_continuation(left, source):
            previous = left.text[-600:]
        if right and confirmed_source_continuation(source, right):
            following = right.text[:600]
        return previous, following

    def translate_reviewed(self, *, client, paths, page_number, total_pages, context_text, started):
        """Explicit reviewed source input; share the normal structured transport."""
        if self.reviewed_evidence is None or (self.acceptance is None and self.ordinary_review is None):
            raise SourceReadinessError("reviewed_source_not_enabled")
        self.check_source()
        source = validate_page_structure(self.reviewed_sources[page_number]["source_structure"])
        metadata = dict(started_at_iso=self.workflow._utc_now(), api_calls_count=0,
            transport_retries_count=0, extract_seconds=0.0, ocr_seconds=0.0,
            source_route="reviewed_image_transcription", source_route_reason=("explicit_ordinary_source_review"
                if self.ordinary_review is not None else "explicit_acceptance_review"),
            ocr_requested=False, ocr_used=False, ocr_attempts_count=0, ocr_engine_used="none",
            image_mode=self.config.image_mode.value, image_bytes=0,
            image_decision_reason="reviewed_source_no_visual_recovery")
        effort = self.workflow._resolve_attempt1_effort(config=self.config,
            image_used=False, ordered_text_chars=len(source.text)).value
        return self.translate(client=client, source=source, paths=paths,
            page_number=page_number, total_pages=total_pages, context_text=context_text,
            image_data_url=None, image_detail="low", effort=effort,
            metadata=metadata, started=started)

    def _verify_reviewed_page(self, source):
        if self.ordinary_review is not None:
            self.check_source()
            if validate_page_structure(source).to_dict() != self.reviewed_sources.get(source.page_number, {}).get("source_structure"):
                raise SourceReadinessError("ordinary_source_review_page_changed")
            return
        verify_reviewed_page(self.acceptance.source_review_json,
            page_identities=self.page_identities, source_hash=self.source_hash, source=source,
            reviewed_evidence=self.reviewed_evidence, page_sizes=self.reviewed_page_sizes)

    def translate(self, *, client, source, paths, page_number, total_pages, context_text,
                  image_data_url, image_detail, effort, metadata, started, source_unusable=False):
        from .workflow import _PageOutcome
        metadata.update(protocol=PROTOCOL_VERSION, model=self.model, effort=effort,
            fidelity_review_required=True, fidelity_review_status="not_evaluated",
            source_review_required=True, source_coverage_status=("reviewed_image_transcription"
                if source.provenance == REVIEWED_SOURCE_VERSION else "recognized_words_only"),
            layout_review_required=source.uncertain or not any(b.bbox for b in source.blocks),
            cost_measurement_status="not_evaluated_all_calls", estimated_cost=None)
        usage = {"ocr": {"engine": metadata.get("ocr_engine_used", "none"),
                         "measurement_status": "not_evaluated_provider_usage"}}
        prior = self.workflow._last_state.pages.get(str(page_number), {})
        if prior.get("usage"):
            usage["prior_attempts"] = [deepcopy(prior["usage"])]
            for key in ("input_tokens", "output_tokens", "reasoning_tokens", "total_tokens", "api_calls_count"):
                metadata[key] = int(prior.get(key, 0) or 0)
        retry = False
        commit = None
        review_codes = {"legal_fidelity_not_evaluated"}

        def outcome(status, error=None):
            metadata.update(ended_at_iso=self.workflow._utc_now(), wall_seconds=round(time.perf_counter()-started, 3),
                            fidelity_review_codes=sorted(review_codes))
            return _PageOutcome(status=status, image_used=image_data_url is not None, retry_used=retry,
                usage=usage, error=error, page_metadata=metadata, structured_commit=commit)

        try:
            if self.acceptance is not None or self.ordinary_review is not None:
                self._verify_reviewed_page(source)
                metadata.update(source_review_required=False, source_review_status="explicit_review_accepted")
                if self.ordinary_review is not None:
                    metadata.update(ordinary_source_review=self.ordinary_review.identity,
                                    source_review_kind=self.ordinary_review.reviewer_kind)
            if source_unusable or not source.blocks or not source.text.strip() or len(source.text) > MAX_SOURCE_CHARS:
                metadata["validator_defect_reason"] = "adequate_assigned_source_unavailable"
                return outcome(PageStatus.FAILED, "source_failure")
            glossary = build_structured_glossary(source.to_dict()["blocks"], self.entries,
                        target_lang=self.config.target_lang.value, enabled_tiers=self.tiers)
            rows = []
            table_names = _source_table_person_names(source) if self.config.target_lang == TargetLang.AR else {}
            for block in source.blocks:
                text = block.text
                if self.config.target_lang == TargetLang.AR:
                    names = [*_NAME.findall(text)]
                    if block.id in table_names:
                        names.append(table_names[block.id])
                    text = prepare_structured_arabic_source(text, role=block.role,
                        protected_names=names, glossary_contract=glossary.for_block(block.id))
                rows.append({"id": block.id, "text": text})
            previous, following = self.contexts(source)
            prompt = build_structured_page_prompt(source_blocks=rows, page_number=page_number,
                total_pages=total_pages, previous_context=previous, next_context=following, context_text=context_text)
            if glossary.prompt_text:
                prompt += "\n" + glossary.prompt_text
            if self.addendum:
                prompt += "\n" + self.addendum
            metadata.update(structured_glossary_entries=len(glossary.entries),
                            structured_glossary_fingerprint=glossary.fingerprint)
            original = prompt
            page_fingerprint = request_fingerprint(source_blocks=rows, prompt_text=prompt,
                translation_identity=fingerprint({"run": self.identity, "model": self.model, "effort": effort}))
            journal = None
            if self.acceptance is not None:
                from .acceptance_continuation import AcceptancePageJournal
                journal = AcceptancePageJournal(paths.run_dir, policy=self.acceptance,
                    protocol_identity=self.identity, page_number=page_number, page_fingerprint=page_fingerprint)
                journal.require_prior_attempt_evidence(int(prior.get("api_calls_count", 0) or 0),
                                                      prior.get("pending_correction_sha256"))
            deadline = time.perf_counter() + self.workflow._translation_request_timeout_seconds(image_used=image_data_url is not None)
            for attempt in (1, 2):
                if self.workflow._cancel_event.is_set():
                    return outcome(PageStatus.FAILED, "cancelled")
                self.check_source()
                if self.acceptance is not None or self.ordinary_review is not None:
                    self._verify_reviewed_page(source)
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    return outcome(PageStatus.FAILED, "runtime_failure")
                request = dict(instructions=self.instructions, prompt_text=prompt, effort=effort,
                    image_data_url=image_data_url, image_detail=image_detail,
                    response_format=structured_response_format(), max_output_tokens=MAX_OUTPUT_TOKENS)
                saved = journal.response(attempt, request) if journal else None
                if saved is not None:
                    # Re-validate the already-paid bytes, never buy the primary again.
                    result = SimpleNamespace(**saved["response"])
                    usage.clear()
                    usage.update(deepcopy(saved["usage"]))
                    metadata.update(deepcopy(saved["metadata"]))
                else:
                    if journal is not None:
                        pending_digest = journal.pending_correction(request) if attempt == 2 else None
                        descriptor = {"page_number": page_number, "attempt": attempt,
                            "purpose": "translation" if attempt == 1 else "correction", "model": self.model,
                            "request": request, "pending_correction_sha256": pending_digest}
                        approval = self.acceptance.authorize(descriptor, primary_approval=journal.primary_approval())
                        if approval is None:
                            metadata["acceptance_approval_required"] = True
                            metadata["pending_correction_sha256"] = pending_digest
                            return outcome(PageStatus.FAILED, "acceptance_approval_required")
                        journal.begin(attempt, request, approval)
                    metadata["api_calls_count"] += 1
                    metadata[f"attempt{attempt}_effort"] = effort
                    began = time.perf_counter()
                    from .usage_accounting import accounting_context
                    with accounting_context(self.workflow._dispatch_accounting,
                            purpose="translation" if attempt == 1 else "correction", page_number=page_number):
                        result = client.create_page_response(**request, timeout_seconds=remaining,
                            cancel_check=(self._ordinary_dispatch_cancel_check if self.ordinary_review is not None
                                          else self.workflow._cancel_event.is_set))
                    metadata[f"attempt{attempt}_seconds"] = round(time.perf_counter()-began, 3)
                    usage[f"attempt_{attempt}"] = result.usage
                    self.workflow._accumulate_usage_totals(metadata, result.usage)
                    metadata["transport_retries_count"] += result.transport_retries_count
                    metadata.setdefault("dispatches", []).append({"model": getattr(result, "model", "") or self.model,
                        "effort": getattr(result, "effort", "") or effort, "protocol": PROTOCOL_VERSION,
                        "response_id": result.response_id, "status": getattr(result, "response_status", "unknown"),
                        "attempt_usage": getattr(result, "attempt_usage", [])})
                    if journal is not None:
                        # This durable boundary precedes cancellation, validation,
                        # correction approval and commit-last page publication.
                        journal.save_response(attempt, result=result, usage=usage, metadata=metadata)
                if self.workflow._cancel_event.is_set():
                    return outcome(PageStatus.FAILED, "cancelled")
                if getattr(result, "refused", False) or getattr(result, "response_status", "unknown") != "completed":
                    metadata["validator_defect_reason"] = "response_not_completed"
                    return outcome(PageStatus.FAILED, "runtime_failure")
                try:
                    translated = parse_structured_translation(result.raw_output, rows, page_number=page_number,
                        response_status=result.response_status, refused=result.refused)
                    normalized = [{"id": left["id"], "text": validate_block(left, right["text"],
                        self.config.target_lang, glossary.for_block(left["id"]), review_codes)}
                        for left, right in zip(rows, translated)]
                except BlockCoverageError as exc:
                    metadata.update(validator_failed=True, validator_defect_reason=str(exc),
                                    validator_block_id=exc.block_id or "", retry_reason="structured_block_defect")
                    if attempt == 2:
                        return outcome(PageStatus.FAILED, "compliance_failure")
                    retry = True
                    diagnostics = [{"block_id": exc.block_id, "code": exc.detail_code or str(exc)}] if exc.block_id else []
                    prompt = build_structured_retry_prompt(original_prompt=original,
                        defect_reason=str(exc), block_diagnostics=diagnostics)
                    continue
                text = flatten_blocks(normalized)
                target = source.to_dict()
                target["blocks"] = [{**block, "text": row["text"]}
                                      for block, row in zip(target["blocks"], normalized)]
                target["translation_sha256"] = digest_text(text)
                target["metadata"].update(translation_fingerprint=page_fingerprint, protocol=PROTOCOL_VERSION,
                    review={"fidelity_status": "not_evaluated", "human_review_required": True})
                if self.ordinary_review is not None:
                    target["metadata"]["ordinary_source_review"] = self.ordinary_review.identity
                self.check_source()
                metadata.update(ended_at_iso=self.workflow._utc_now(), wall_seconds=round(time.perf_counter()-started, 3),
                    translate_seconds=sum(float(metadata.get(f"attempt{i}_seconds", 0)) for i in (1, 2)),
                    fidelity_review_codes=sorted(review_codes), source_block_count=len(rows))
                commit = publish_structured_page(paths.pages_dir, source_structure=source,
                    translated_structure=target, translated_text=text, protocol_identity=self.identity,
                    page_fingerprint=page_fingerprint, cancelled=self.workflow._cancel_event.is_set,
                    evidence_guard=self.check_source, page_result={"usage": usage, "image_used": image_data_url is not None,
                        "retry_used": retry, "metadata": deepcopy(metadata)})
                return outcome(PageStatus.DONE)
        except ApiCallError as exc:
            charged = getattr(exc, "usage", None) or {}
            usage["failed_attempt"] = charged
            self.workflow._accumulate_usage_totals(metadata, charged)
            metadata.update(exception_class=exc.exception_class, status_code=exc.status_code,
                response_status=getattr(exc, "response_status", "unknown"),
                cancel_requested_before_failure=self.workflow._cancel_event.is_set())
            metadata.setdefault("dispatches", []).append({"model": getattr(exc, "model", "") or self.model,
                "effort": getattr(exc, "effort", "") or effort, "protocol": PROTOCOL_VERSION,
                "response_id": getattr(exc, "response_id", None), "status": getattr(exc, "response_status", "unknown"),
                "attempt_usage": getattr(exc, "attempt_usage", [])})
            error = "authentication_failure" if is_openai_auth_failure(exception_class=exc.exception_class,
                            status_code=exc.status_code) else "runtime_failure"
            return outcome(PageStatus.FAILED, "cancelled" if self.workflow._cancel_event.is_set() else error)
        except SourceReadinessError as exc:
            metadata.update(validator_defect_reason=str(exc), source_review_required=True,
                            source_review_status="review_required")
            return outcome(PageStatus.FAILED, "source_failure")
        except (StructuredArtifactError, StructuredGlossaryError, StructuredArabicLiteralError, BlockCoverageError):
            metadata["validator_defect_reason"] = "structured_evidence_invalid"
            return outcome(PageStatus.FAILED, "cancelled" if self.workflow._cancel_event.is_set() else "compliance_failure")
        except (OSError, ValueError, TypeError):
            metadata["validator_defect_reason"] = "structured_publication_failed"
            return outcome(PageStatus.FAILED, "runtime_failure")
