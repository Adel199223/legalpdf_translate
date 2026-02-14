"""Study glossary mining and learning helpers (learning-only, prompt-isolated)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any, Iterable, Literal

from .openai_client import OpenAIResponsesClient
from .output_normalize import normalize_output_text
from .prompt_builder import build_page_prompt
from .resources_loader import load_system_instructions
from .types import TargetLang
from .validators import parse_code_block_output, validate_ar, validate_enfr

StudyCategory = Literal["headers", "roles", "procedure", "evidence", "reasoning", "decision_costs", "other"]
StudyStatus = Literal["new", "learning", "known", "hard"]
CoverageTier = Literal["core80", "next15", "long_tail"]
StudyMode = Literal["full_text", "headers_only"]

_VALID_CATEGORIES: tuple[StudyCategory, ...] = (
    "headers",
    "roles",
    "procedure",
    "evidence",
    "reasoning",
    "decision_costs",
    "other",
)
_VALID_STATUSES: tuple[StudyStatus, ...] = ("new", "learning", "known", "hard")
_VALID_TIERS: tuple[CoverageTier, ...] = ("core80", "next15", "long_tail")
_VALID_MODES: tuple[StudyMode, ...] = ("full_text", "headers_only")

_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")
_IS_NUMERIC_LIKE_RE = re.compile(r"\d")
_DATE_LIKE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b")
_IBAN_LIKE_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", re.IGNORECASE)
_CASE_ID_LIKE_RE = re.compile(r"\b\d+[./-][A-Za-z0-9./-]{2,}\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_URL_RE = re.compile(r"\b(?:https?://|www\.)\S+\b", re.IGNORECASE)
_SECTION_HEADER_RE = re.compile(r"^\s*(?:[IVXLCDM]+|[A-Z])\s*[–\-.:)]", re.IGNORECASE)
_UPPER_LETTER_RE = re.compile(r"[A-ZÀ-ÖØ-Þ]")

_STOPWORDS_PT: set[str] = {
    "a",
    "ao",
    "aos",
    "as",
    "até",
    "com",
    "como",
    "da",
    "das",
    "de",
    "delas",
    "deles",
    "do",
    "dos",
    "e",
    "em",
    "entre",
    "era",
    "essa",
    "esse",
    "esta",
    "este",
    "foi",
    "foram",
    "há",
    "já",
    "lhe",
    "lhes",
    "mais",
    "mas",
    "na",
    "nas",
    "no",
    "nos",
    "o",
    "os",
    "ou",
    "para",
    "pela",
    "pelas",
    "pelo",
    "pelos",
    "por",
    "que",
    "se",
    "sem",
    "ser",
    "seu",
    "seus",
    "sua",
    "suas",
    "também",
    "tem",
    "tendo",
    "uma",
    "umas",
    "um",
    "uns",
}


@dataclass(slots=True, frozen=True)
class StudyGlossaryEntry:
    term_pt: str
    translations_by_lang: dict[str, str]
    tf: int
    df_pages: int
    sample_snippets: list[str]
    category: StudyCategory
    status: StudyStatus
    next_review_date: str | None
    coverage_tier: CoverageTier = "long_tail"
    confidence: float = 0.0
    df_docs: int = 0


@dataclass(slots=True, frozen=True)
class StudyCandidate:
    term_pt: str
    tf: int
    df_pages: int
    score: float
    confidence: float
    sample_snippets: list[str]
    category: StudyCategory
    df_docs: int = 0
    coverage_tier: CoverageTier = "long_tail"
    cumulative_coverage: float = 0.0


def supported_learning_langs() -> list[str]:
    return [lang.value for lang in TargetLang]


def expand_translations_by_lang(
    translations_by_lang: object,
    supported_langs: list[str],
) -> dict[str, str]:
    raw = translations_by_lang if isinstance(translations_by_lang, dict) else {}
    output: dict[str, str] = {}
    for lang in supported_langs:
        value = raw.get(lang, "")
        output[lang] = str(value or "").strip()
    return output


def _coerce_category(value: object) -> StudyCategory:
    raw = str(value or "").strip().lower()
    if raw in _VALID_CATEGORIES:
        return raw  # type: ignore[return-value]
    return "other"


def _coerce_status(value: object) -> StudyStatus:
    raw = str(value or "").strip().lower()
    if raw in _VALID_STATUSES:
        return raw  # type: ignore[return-value]
    return "new"


def _coerce_coverage_tier(value: object) -> CoverageTier:
    raw = str(value or "").strip().lower()
    if raw in _VALID_TIERS:
        return raw  # type: ignore[return-value]
    return "long_tail"


def _normalize_term(value: object) -> str:
    cleaned = _SPACE_RE.sub(" ", str(value or "").strip())
    return cleaned


def _entry_key(term_pt: str) -> str:
    return _normalize_term(term_pt).casefold()


def normalize_study_entries(
    raw_entries: object,
    supported_langs: list[str],
) -> list[StudyGlossaryEntry]:
    if not isinstance(raw_entries, list):
        return []
    output: list[StudyGlossaryEntry] = []
    seen: set[str] = set()
    for raw in raw_entries:
        if not isinstance(raw, dict):
            continue
        term_pt = _normalize_term(raw.get("term_pt", ""))
        if term_pt == "":
            continue
        key = _entry_key(term_pt)
        if key in seen:
            continue
        seen.add(key)
        snippets_raw = raw.get("sample_snippets", [])
        snippets: list[str] = []
        if isinstance(snippets_raw, list):
            for item in snippets_raw:
                text = _normalize_term(item)
                if text:
                    snippets.append(text)
                if len(snippets) >= 3:
                    break
        next_review_raw = str(raw.get("next_review_date", "") or "").strip()
        next_review = next_review_raw if next_review_raw else None
        try:
            tf = max(0, int(raw.get("tf", 0) or 0))
        except (TypeError, ValueError):
            tf = 0
        try:
            df_pages = max(0, int(raw.get("df_pages", 0) or 0))
        except (TypeError, ValueError):
            df_pages = 0
        try:
            df_docs = max(0, int(raw.get("df_docs", 0) or 0))
        except (TypeError, ValueError):
            df_docs = 0
        try:
            confidence = float(raw.get("confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < 0.0:
            confidence = 0.0
        if confidence > 1.0:
            confidence = 1.0
        output.append(
            StudyGlossaryEntry(
                term_pt=term_pt,
                translations_by_lang=expand_translations_by_lang(raw.get("translations_by_lang"), supported_langs),
                tf=tf,
                df_pages=df_pages,
                sample_snippets=snippets,
                category=_coerce_category(raw.get("category")),
                status=_coerce_status(raw.get("status")),
                next_review_date=next_review,
                coverage_tier=_coerce_coverage_tier(raw.get("coverage_tier")),
                confidence=round(confidence, 3),
                df_docs=df_docs,
            )
        )
    return output


def serialize_study_entries(entries: list[StudyGlossaryEntry], supported_langs: list[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for entry in normalize_study_entries(
        [
            {
                "term_pt": item.term_pt,
                "translations_by_lang": item.translations_by_lang,
                "tf": item.tf,
                "df_pages": item.df_pages,
                "df_docs": item.df_docs,
                "sample_snippets": item.sample_snippets,
                "category": item.category,
                "status": item.status,
                "next_review_date": item.next_review_date,
                "coverage_tier": item.coverage_tier,
                "confidence": item.confidence,
            }
            for item in entries
        ],
        supported_langs,
    ):
        rows.append(
            {
                "term_pt": entry.term_pt,
                "translations_by_lang": expand_translations_by_lang(entry.translations_by_lang, supported_langs),
                "tf": int(entry.tf),
                "df_pages": int(entry.df_pages),
                "df_docs": int(entry.df_docs),
                "sample_snippets": list(entry.sample_snippets[:3]),
                "category": entry.category,
                "status": entry.status,
                "next_review_date": entry.next_review_date,
                "coverage_tier": entry.coverage_tier,
                "confidence": round(float(entry.confidence), 3),
            }
        )
    return rows


def is_identifier_like(text: str) -> bool:
    term = text.strip()
    if term == "":
        return True
    lowered = term.casefold()
    if _EMAIL_RE.search(lowered) or _URL_RE.search(lowered):
        return True
    if _IBAN_LIKE_RE.search(term) or _CASE_ID_LIKE_RE.search(term) or _DATE_LIKE_RE.search(term):
        return True
    digit_count = sum(1 for ch in term if ch.isdigit())
    if digit_count > 0 and digit_count / max(1, len(term)) >= 0.25:
        return True
    return False


def _header_like_line(line: str) -> bool:
    cleaned = line.strip()
    if cleaned == "":
        return False
    if _SECTION_HEADER_RE.search(cleaned):
        return True
    letters = [ch for ch in cleaned if ch.isalpha()]
    if not letters:
        return False
    upper_count = sum(1 for ch in letters if bool(_UPPER_LETTER_RE.match(ch)))
    if len(cleaned) <= 90 and upper_count / len(letters) >= 0.65:
        return True
    return False


def tokenize_pt(line: str) -> list[str]:
    tokens = [match.group(0).casefold() for match in _WORD_RE.finditer(line)]
    return [tok for tok in tokens if len(tok) >= 2]


def tokenize_page_for_mode(text: str, mode: StudyMode = "full_text") -> list[str]:
    selected_mode: StudyMode = mode if mode in _VALID_MODES else "full_text"
    output: list[str] = []
    for raw_line in str(text or "").splitlines():
        line_clean = _normalize_term(raw_line)
        if line_clean == "":
            continue
        header_like = _header_like_line(line_clean)
        if selected_mode == "headers_only" and not header_like:
            continue
        output.extend(tokenize_pt(line_clean))
    return output


def _candidate_ngram_tokens(tokens: list[str], n: int) -> Iterable[list[str]]:
    if n <= 0 or len(tokens) < n:
        return []
    return (tokens[index : index + n] for index in range(0, len(tokens) - n + 1))


def _join_tokens(tokens: list[str]) -> str:
    return " ".join(tokens)


def _candidate_allowed(tokens: list[str]) -> bool:
    if not tokens:
        return False
    if all(token in _STOPWORDS_PT for token in tokens):
        return False
    phrase = _join_tokens(tokens)
    if phrase in _STOPWORDS_PT:
        return False
    if is_identifier_like(phrase):
        return False
    return True


def categorize_term(term_pt: str) -> StudyCategory:
    text = term_pt.casefold()
    if any(
        marker in text
        for marker in ("sentença", "relatório", "fundamentação", "dispositivo", "custas", "de facto", "de direito")
    ):
        return "headers"
    if any(marker in text for marker in ("ministério público", "arguido", "arguida", "juiz", "tribunal")):
        return "roles"
    if any(marker in text for marker in ("audiência", "contestação", "autos", "prazo", "notifique")):
        return "procedure"
    if any(marker in text for marker in ("prova", "factos provados", "factos não provados", "documento")):
        return "evidence"
    if any(marker in text for marker in ("presunção", "in dubio", "fundamentação", "doravante")):
        return "reasoning"
    if any(marker in text for marker in ("custas", "absolvição", "dispositivo", "depósito da sentença")):
        return "decision_costs"
    return "other"


def _confidence(tf: int, df_pages: int, header_hits: int) -> float:
    value = (math.log1p(tf) * 0.55) + (math.log1p(df_pages) * 0.35) + (0.10 if header_hits > 0 else 0.0)
    bounded = max(0.0, min(1.0, value / 3.0))
    return round(bounded, 3)


def _score(tf: int, df_pages: int, header_hits: int) -> float:
    header_boost = 1.25 if header_hits > 0 else 1.0
    return float(tf) * (1.0 + math.log1p(float(df_pages))) * header_boost


def sort_candidates_for_selection(candidates: list[StudyCandidate]) -> list[StudyCandidate]:
    return sorted(candidates, key=lambda item: (-item.score, -item.tf, -item.df_pages, item.term_pt.casefold()))


def _candidate_term_key(term_pt: str) -> str:
    return _entry_key(term_pt)


def _candidate_term_tokens(term_pt: str) -> tuple[str, ...]:
    tokens = tokenize_pt(_normalize_term(term_pt))
    if 1 <= len(tokens) <= 3:
        return tuple(tokens)
    return ()


def build_ngram_index(
    candidates: list[StudyCandidate],
    *,
    ranked_term_keys: list[str] | None = None,
) -> dict[tuple[str, ...], str]:
    rank_map = {key: index for index, key in enumerate(ranked_term_keys or [])}
    output: dict[tuple[str, ...], str] = {}
    for candidate in candidates:
        term_key = _candidate_term_key(candidate.term_pt)
        tokens = _candidate_term_tokens(candidate.term_pt)
        if not tokens:
            continue
        prior = output.get(tokens)
        if prior is None:
            output[tokens] = term_key
            continue
        prior_rank = rank_map.get(prior, 10_000_000)
        current_rank = rank_map.get(term_key, 10_000_000)
        if current_rank < prior_rank or (current_rank == prior_rank and term_key < prior):
            output[tokens] = term_key
    return output


def count_non_overlapping_matches(
    pages_tokens: list[list[str]],
    allowed_terms_set: set[str],
    ngram_index: dict[tuple[str, ...], str],
) -> tuple[dict[str, int], int]:
    if not pages_tokens or not allowed_terms_set or not ngram_index:
        return ({}, 0)

    counts: dict[str, int] = {}
    total = 0
    for page_tokens in pages_tokens:
        if not page_tokens:
            continue
        index = 0
        limit = len(page_tokens)
        while index < limit:
            matched_key: str | None = None
            matched_len = 0
            for n_size in (3, 2, 1):
                end = index + n_size
                if end > limit:
                    continue
                gram = tuple(page_tokens[index:end])
                term_key = ngram_index.get(gram)
                if term_key is None or term_key not in allowed_terms_set:
                    continue
                matched_key = term_key
                matched_len = n_size
                break
            if matched_key is None:
                index += 1
                continue
            counts[matched_key] = counts.get(matched_key, 0) + 1
            total += 1
            index += matched_len
    return (counts, total)


def compute_non_overlapping_tier_assignment(
    candidates: list[StudyCandidate],
    pages_tokens: list[list[str]],
    *,
    coverage_target: float = 0.80,
    next_target: float = 0.95,
) -> list[StudyCandidate]:
    ordered = sort_candidates_for_selection(candidates)
    if not ordered:
        return []

    rank_keys = [_candidate_term_key(item.term_pt) for item in ordered]
    ngram_index = build_ngram_index(ordered, ranked_term_keys=rank_keys)
    all_allowed = set(rank_keys)
    _all_counts, total_occurrences = count_non_overlapping_matches(
        pages_tokens,
        all_allowed,
        ngram_index,
    )
    if total_occurrences <= 0:
        return [replace(item, coverage_tier="long_tail", cumulative_coverage=0.0) for item in ordered]

    target = max(0.0, min(1.0, float(coverage_target)))
    next_cutoff_target = max(target, min(1.0, float(next_target)))

    core_cutoff = len(ordered)
    next_cutoff = len(ordered)
    prefix_coverage: list[float] = [0.0] * len(ordered)
    last_coverage = 0.0
    reached_next = False
    for idx in range(len(ordered)):
        allowed = set(rank_keys[: idx + 1])
        _prefix_counts, covered_total = count_non_overlapping_matches(
            pages_tokens,
            allowed,
            ngram_index,
        )
        coverage = covered_total / float(total_occurrences)
        prefix_coverage[idx] = coverage
        last_coverage = coverage
        if core_cutoff == len(ordered) and coverage >= target:
            core_cutoff = idx + 1
        if next_cutoff == len(ordered) and coverage >= next_cutoff_target:
            next_cutoff = idx + 1
            reached_next = True
            break
    if reached_next:
        for idx in range(next_cutoff, len(ordered)):
            prefix_coverage[idx] = last_coverage
    if next_cutoff == len(ordered) and core_cutoff < len(ordered):
        # Keep deterministic split even if 95% was not reached before end.
        next_cutoff = len(ordered)

    assigned: list[StudyCandidate] = []
    for idx, item in enumerate(ordered):
        if idx < core_cutoff:
            tier: CoverageTier = "core80"
        elif idx < next_cutoff:
            tier = "next15"
        else:
            tier = "long_tail"
        assigned.append(replace(item, coverage_tier=tier, cumulative_coverage=round(prefix_coverage[idx], 6)))
    return assigned


def _contains_token_subsequence(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    if not needle or len(needle) > len(haystack):
        return False
    for index in range(0, len(haystack) - len(needle) + 1):
        if haystack[index : index + len(needle)] == needle:
            return True
    return False


def apply_subsumption_suppression(
    candidates: list[StudyCandidate],
    pages_tokens: list[list[str]],
    *,
    threshold: float = 0.80,
) -> list[StudyCandidate]:
    if not candidates or not pages_tokens:
        return list(candidates)
    ranked = list(candidates)
    ranked_keys = [_candidate_term_key(item.term_pt) for item in ranked]
    ngram_index = build_ngram_index(ranked, ranked_term_keys=ranked_keys)
    token_map = {_candidate_term_key(item.term_pt): _candidate_term_tokens(item.term_pt) for item in ranked}
    anchor_keys = {
        _candidate_term_key(item.term_pt)
        for item in ranked
        if item.coverage_tier in {"core80", "next15"}
    }
    safe_threshold = max(0.0, min(1.0, float(threshold)))

    output: list[StudyCandidate] = []
    for candidate in ranked:
        key = _candidate_term_key(candidate.term_pt)
        term_tokens = token_map.get(key, ())
        if candidate.coverage_tier == "long_tail" or len(term_tokens) >= 3:
            output.append(candidate)
            continue
        longer_anchor_keys = [
            other_key
            for other_key in anchor_keys
            if other_key != key
            and len(token_map.get(other_key, ())) > len(term_tokens)
            and _contains_token_subsequence(token_map.get(other_key, ()), term_tokens)
        ]
        if not longer_anchor_keys:
            output.append(candidate)
            continue
        base_counts, _base_total = count_non_overlapping_matches(
            pages_tokens,
            {key},
            ngram_index,
        )
        base_count = int(base_counts.get(key, 0))
        if base_count <= 0:
            output.append(candidate)
            continue
        residual_counts, _residual_total = count_non_overlapping_matches(
            pages_tokens,
            {key, *longer_anchor_keys},
            ngram_index,
        )
        residual_count = int(residual_counts.get(key, 0))
        subsumed_ratio = 1.0 - (float(residual_count) / float(base_count))
        if subsumed_ratio >= safe_threshold:
            output.append(replace(candidate, coverage_tier="long_tail"))
            continue
        output.append(candidate)
    return output


def assign_coverage_tiers(sorted_candidates: list[StudyCandidate]) -> list[StudyCandidate]:
    total_tf = sum(max(0, int(item.tf)) for item in sorted_candidates)
    if total_tf <= 0:
        return [replace(item, coverage_tier="long_tail", cumulative_coverage=0.0) for item in sorted_candidates]
    assigned: list[StudyCandidate] = []
    cumulative = 0
    for item in sorted_candidates:
        before = cumulative / float(total_tf)
        cumulative += max(0, int(item.tf))
        after = cumulative / float(total_tf)
        if before < 0.80:
            tier: CoverageTier = "core80"
        elif before < 0.95:
            tier = "next15"
        else:
            tier = "long_tail"
        assigned.append(replace(item, coverage_tier=tier, cumulative_coverage=round(after, 6)))
    return assigned


def select_min_cover_set(
    candidates: list[StudyCandidate],
    coverage_target: float = 0.80,
    *,
    pages_tokens: list[list[str]] | None = None,
) -> list[StudyCandidate]:
    if pages_tokens:
        assigned = compute_non_overlapping_tier_assignment(
            candidates,
            pages_tokens,
            coverage_target=coverage_target,
            next_target=0.95,
        )
        return [item for item in assigned if item.coverage_tier == "core80"]
    target = max(0.0, min(1.0, float(coverage_target)))
    if target <= 0.0:
        return []
    ordered = sort_candidates_for_selection(candidates)
    total_tf = sum(max(0, int(item.tf)) for item in ordered)
    if total_tf <= 0:
        return []
    selected: list[StudyCandidate] = []
    cumulative = 0
    for item in ordered:
        selected.append(item)
        cumulative += max(0, int(item.tf))
        if (cumulative / float(total_tf)) >= target:
            break
    return selected


def mine_study_candidates(
    corpus_pages: list[dict[str, object]],
    mode: StudyMode = "full_text",
    *,
    include_snippets: bool = False,
    snippet_max_chars: int = 120,
) -> list[StudyCandidate]:
    stats = create_candidate_stats()
    for page in corpus_pages:
        update_candidate_stats_from_page(
            doc_id=str(page.get("doc_id", "") or "doc"),
            page_number=int(page.get("page_number", 0) or 0),
            text=str(page.get("text", "") or ""),
            mode=mode,
            include_snippets=include_snippets,
            snippet_max_chars=snippet_max_chars,
            stats=stats,
        )
    return finalize_study_candidates(stats)


def filter_candidates_by_thresholds(
    candidates: list[StudyCandidate],
    *,
    min_tf_per_doc: int = 5,
    min_tf_cross_doc: int = 3,
    min_df_docs: int = 2,
) -> list[StudyCandidate]:
    output: list[StudyCandidate] = []
    for item in candidates:
        if item.tf >= min_tf_per_doc:
            output.append(item)
            continue
        if item.tf >= min_tf_cross_doc and item.df_docs >= min_df_docs:
            output.append(item)
    return output


def compute_next_review_date(status: StudyStatus, *, today: date | None = None) -> str:
    now = today or date.today()
    if status == "known":
        delta = timedelta(days=14)
    elif status == "learning":
        delta = timedelta(days=3)
    else:
        delta = timedelta(days=1)
    return (now + delta).isoformat()


def build_entry_from_candidate(
    candidate: StudyCandidate,
    *,
    supported_langs: list[str],
    default_status: StudyStatus = "new",
) -> StudyGlossaryEntry:
    return StudyGlossaryEntry(
        term_pt=_normalize_term(candidate.term_pt),
        translations_by_lang=expand_translations_by_lang({}, supported_langs),
        tf=int(candidate.tf),
        df_pages=int(candidate.df_pages),
        df_docs=int(candidate.df_docs),
        sample_snippets=list(candidate.sample_snippets[:3]),
        category=candidate.category,
        status=default_status,
        next_review_date=compute_next_review_date(default_status),
        coverage_tier=candidate.coverage_tier,
        confidence=round(float(candidate.confidence), 3),
    )


def merge_study_entries(
    existing_entries: list[StudyGlossaryEntry],
    incoming_entries: list[StudyGlossaryEntry],
    *,
    supported_langs: list[str],
) -> list[StudyGlossaryEntry]:
    normalized_existing = normalize_study_entries(serialize_study_entries(existing_entries, supported_langs), supported_langs)
    by_key: dict[str, StudyGlossaryEntry] = {_entry_key(item.term_pt): item for item in normalized_existing}

    for incoming in normalize_study_entries(serialize_study_entries(incoming_entries, supported_langs), supported_langs):
        key = _entry_key(incoming.term_pt)
        prior = by_key.get(key)
        if prior is None:
            by_key[key] = incoming
            continue
        merged_translations = expand_translations_by_lang(prior.translations_by_lang, supported_langs)
        incoming_translations = expand_translations_by_lang(incoming.translations_by_lang, supported_langs)
        for lang in supported_langs:
            if merged_translations.get(lang, "").strip() == "" and incoming_translations.get(lang, "").strip() != "":
                merged_translations[lang] = incoming_translations[lang].strip()
        by_key[key] = StudyGlossaryEntry(
            term_pt=prior.term_pt,
            translations_by_lang=merged_translations,
            tf=max(int(prior.tf), int(incoming.tf)),
            df_pages=max(int(prior.df_pages), int(incoming.df_pages)),
            df_docs=max(int(prior.df_docs), int(incoming.df_docs)),
            sample_snippets=list(prior.sample_snippets[:3]) or list(incoming.sample_snippets[:3]),
            category=prior.category if prior.category != "other" else incoming.category,
            status=prior.status,
            next_review_date=prior.next_review_date,
            coverage_tier=incoming.coverage_tier,
            confidence=max(float(prior.confidence), float(incoming.confidence)),
        )

    merged = list(by_key.values())
    merged.sort(key=lambda item: item.term_pt.casefold())
    return normalize_study_entries(serialize_study_entries(merged, supported_langs), supported_langs)


def create_candidate_stats() -> dict[str, Any]:
    return {
        "term_tf": {},
        "term_pages": {},
        "term_docs": {},
        "term_header_hits": {},
        "term_snippets": {},
    }


def update_candidate_stats_from_page(
    *,
    doc_id: str,
    page_number: int,
    text: str,
    mode: StudyMode = "full_text",
    include_snippets: bool = False,
    snippet_max_chars: int = 120,
    stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if stats is None:
        stats = create_candidate_stats()
    selected_mode: StudyMode = mode if mode in _VALID_MODES else "full_text"
    max_chars = max(40, min(300, int(snippet_max_chars)))
    if str(text or "").strip() == "":
        return stats

    term_tf: dict[str, int] = stats.setdefault("term_tf", {})
    term_pages: dict[str, set[str]] = stats.setdefault("term_pages", {})
    term_docs: dict[str, set[str]] = stats.setdefault("term_docs", {})
    term_header_hits: dict[str, int] = stats.setdefault("term_header_hits", {})
    term_snippets: dict[str, list[str]] = stats.setdefault("term_snippets", {})

    page_key = f"{doc_id}#{int(page_number)}"
    for raw_line in str(text).splitlines():
        line_clean = _normalize_term(raw_line)
        if line_clean == "":
            continue
        header_like = _header_like_line(line_clean)
        if selected_mode == "headers_only" and not header_like:
            continue
        tokens = tokenize_pt(line_clean)
        if not tokens:
            continue
        for n in (1, 2, 3):
            for ngram_tokens in _candidate_ngram_tokens(tokens, n):
                if not _candidate_allowed(ngram_tokens):
                    continue
                phrase = _join_tokens(ngram_tokens)
                term_tf[phrase] = term_tf.get(phrase, 0) + 1
                term_pages.setdefault(phrase, set()).add(page_key)
                term_docs.setdefault(phrase, set()).add(str(doc_id))
                if header_like:
                    term_header_hits[phrase] = term_header_hits.get(phrase, 0) + 1
                if include_snippets:
                    snippets = term_snippets.setdefault(phrase, [])
                    if len(snippets) < 3:
                        snippets.append(line_clean[:max_chars])
    return stats


def finalize_study_candidates(stats: dict[str, Any]) -> list[StudyCandidate]:
    term_tf: dict[str, int] = stats.get("term_tf", {}) if isinstance(stats.get("term_tf"), dict) else {}
    term_pages: dict[str, set[str]] = stats.get("term_pages", {}) if isinstance(stats.get("term_pages"), dict) else {}
    term_docs: dict[str, set[str]] = stats.get("term_docs", {}) if isinstance(stats.get("term_docs"), dict) else {}
    term_header_hits: dict[str, int] = (
        stats.get("term_header_hits", {}) if isinstance(stats.get("term_header_hits"), dict) else {}
    )
    term_snippets: dict[str, list[str]] = stats.get("term_snippets", {}) if isinstance(stats.get("term_snippets"), dict) else {}
    candidates: list[StudyCandidate] = []
    for term, tf in term_tf.items():
        if int(tf) <= 0:
            continue
        df_pages = len(term_pages.get(term, set()))
        if df_pages <= 0:
            continue
        df_docs = len(term_docs.get(term, set()))
        header_hits = int(term_header_hits.get(term, 0))
        candidates.append(
            StudyCandidate(
                term_pt=term,
                tf=int(tf),
                df_pages=df_pages,
                score=round(_score(tf=int(tf), df_pages=df_pages, header_hits=header_hits), 6),
                confidence=_confidence(tf=int(tf), df_pages=df_pages, header_hits=header_hits),
                sample_snippets=list(term_snippets.get(term, []))[:3],
                category=categorize_term(term),
                df_docs=df_docs,
            )
        )
    return assign_coverage_tiers(sort_candidates_for_selection(candidates))


def _coverage_tier_label(value: CoverageTier) -> str:
    if value == "core80":
        return "Core80"
    if value == "next15":
        return "Next15"
    return "LongTail"


def _escape_markdown_cell(value: object) -> str:
    text = str(value or "").replace("|", "\\|").replace("\n", " ").strip()
    return text


def _ordered_language_columns(supported_langs: list[str]) -> list[str]:
    preferred = ["AR", "FR", "EN"]
    upper = [str(lang or "").strip().upper() for lang in supported_langs if str(lang or "").strip()]
    ordered = [lang for lang in preferred if lang in upper]
    extras = sorted({lang for lang in upper if lang not in set(preferred)})
    return ordered + extras


def build_study_glossary_markdown(
    entries: list[StudyGlossaryEntry],
    *,
    generated_at_iso: str,
    run_folders_count: int,
    total_pages_scanned: int,
    include_snippets: bool,
    snippet_max_chars: int,
    scope_label: str,
    supported_langs: list[str],
) -> str:
    normalized = normalize_study_entries(
        serialize_study_entries(entries, supported_langs),
        supported_langs,
    )
    rows_by_tier: dict[CoverageTier, list[StudyGlossaryEntry]] = {"core80": [], "next15": [], "long_tail": []}
    for entry in sorted(
        normalized,
        key=lambda item: (
            {"core80": 0, "next15": 1, "long_tail": 2}.get(item.coverage_tier, 3),
            item.term_pt.casefold(),
        ),
    ):
        rows_by_tier.setdefault(entry.coverage_tier, []).append(entry)

    lang_columns = _ordered_language_columns(supported_langs)
    table_headers = ["PT"] + lang_columns + ["TF", "Pages", "Docs", "Tier", "Category", "Status"]
    markdown_lines: list[str] = [
        "# Study Glossary",
        "",
        f"Generated: {generated_at_iso}",
        f"Scope: {scope_label}",
        f"Run folders processed: {max(0, int(run_folders_count))}",
        f"Total pages scanned: {max(0, int(total_pages_scanned))}",
    ]
    if not normalized:
        markdown_lines.extend(["", "No entries available."])
        return "\n".join(markdown_lines).strip() + "\n"

    max_chars = max(40, min(300, int(snippet_max_chars)))
    for tier in ("core80", "next15", "long_tail"):
        rows = rows_by_tier.get(tier, [])
        if not rows:
            continue
        markdown_lines.extend(["", f"## {_coverage_tier_label(tier)}", ""])
        markdown_lines.append("| " + " | ".join(table_headers) + " |")
        markdown_lines.append("| " + " | ".join(["---"] * len(table_headers)) + " |")
        for entry in rows:
            cells = [_escape_markdown_cell(entry.term_pt)]
            for lang in lang_columns:
                cells.append(_escape_markdown_cell(entry.translations_by_lang.get(lang, "")))
            cells.extend(
                [
                    str(int(entry.tf)),
                    str(int(entry.df_pages)),
                    str(int(entry.df_docs)),
                    _coverage_tier_label(entry.coverage_tier),
                    _escape_markdown_cell(entry.category),
                    _escape_markdown_cell(entry.status),
                ]
            )
            markdown_lines.append("| " + " | ".join(cells) + " |")

        if include_snippets:
            snippet_rows: list[str] = []
            for entry in rows:
                snippets = [snippet[:max_chars] for snippet in entry.sample_snippets[:3] if str(snippet or "").strip()]
                if not snippets:
                    continue
                snippet_rows.append(
                    f"- {_escape_markdown_cell(entry.term_pt)}: " + " | ".join(_escape_markdown_cell(s) for s in snippets)
                )
            if snippet_rows:
                markdown_lines.extend(["", "Snippets:"])
                markdown_lines.extend(snippet_rows)

    return "\n".join(markdown_lines).strip() + "\n"


def _coerce_target_lang(value: str | TargetLang) -> TargetLang:
    if isinstance(value, TargetLang):
        return value
    return TargetLang(str(value).strip().upper())


def _evaluate_term_output(raw_output: str, *, lang: TargetLang) -> str:
    parsed = parse_code_block_output(raw_output)
    if parsed.block_count != 1 or parsed.inner_content is None or parsed.outside_has_non_whitespace:
        raise ValueError("Non-compliant translation output for glossary term.")
    normalized = normalize_output_text(parsed.inner_content, lang=lang)
    validation = validate_ar(normalized) if lang == TargetLang.AR else validate_enfr(normalized, lang=lang)
    if not validation.ok:
        raise ValueError(validation.reason or "Glossary term validation failed.")
    return normalized


def translate_term_for_lang(
    term_pt: str,
    target_lang: TargetLang | str,
    *,
    client: OpenAIResponsesClient | None = None,
    timeout_seconds: float = 45.0,
    effort: str = "medium",
) -> str:
    lang = _coerce_target_lang(target_lang)
    phrase = _normalize_term(term_pt)
    if phrase == "":
        return ""
    local_client = client or OpenAIResponsesClient(request_timeout_seconds=max(5.0, timeout_seconds))
    instructions = load_system_instructions(lang)
    prompt_text = build_page_prompt(
        lang=lang,
        page_number=1,
        total_pages=1,
        source_text=phrase,
        context_text=None,
    )
    result = local_client.create_page_response(
        instructions=instructions,
        prompt_text=prompt_text,
        effort=effort,
        image_data_url=None,
        timeout_seconds=max(5.0, timeout_seconds),
    )
    return _evaluate_term_output(result.raw_output, lang=lang)


def fill_translations_for_entry(
    entry: StudyGlossaryEntry,
    *,
    supported_langs: list[str],
    client: OpenAIResponsesClient | None = None,
    timeout_seconds: float = 45.0,
    fill_only_missing: bool = True,
    effort: str = "medium",
) -> StudyGlossaryEntry:
    translations = expand_translations_by_lang(entry.translations_by_lang, supported_langs)
    local_client = client or OpenAIResponsesClient(request_timeout_seconds=max(5.0, timeout_seconds))
    for lang in supported_langs:
        current = translations.get(lang, "").strip()
        if fill_only_missing and current != "":
            continue
        try:
            translated = translate_term_for_lang(
                entry.term_pt,
                lang,
                client=local_client,
                timeout_seconds=timeout_seconds,
                effort=effort,
            )
        except Exception:
            continue
        translations[lang] = translated.strip()
    return replace(entry, translations_by_lang=translations)
