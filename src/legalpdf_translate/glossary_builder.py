"""Consistency glossary builder helpers (frequency-based suggestions)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Literal

from .glossary import GlossaryEntry
from .study_glossary import tokenize_pt

BuilderScope = Literal["personal", "project"]
BuilderMode = Literal["full_text", "headers_only"]

_SPACE_RE = re.compile(r"\s+")
_DATE_LIKE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b")
_IBAN_LIKE_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", re.IGNORECASE)
_CASE_ID_LIKE_RE = re.compile(r"\b\d+[./-][A-Za-z0-9./-]{2,}\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_URL_RE = re.compile(r"\b(?:https?://|www\.)\S+\b", re.IGNORECASE)
_ADDRESS_LIKE_RE = re.compile(
    r"\b(?:rua|avenida|av\.?|travessa|lote|andar|bloco|apt\.?|n[.ºo]|c\.?p\.?)\b",
    re.IGNORECASE,
)
_SECTION_HEADER_RE = re.compile(r"^\s*(?:[IVXLCDM]+|[A-Z])\s*[–\-.:)]", re.IGNORECASE)

_STOPWORDS_PT: set[str] = {
    "a",
    "ao",
    "aos",
    "as",
    "com",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "na",
    "nas",
    "no",
    "nos",
    "o",
    "os",
    "ou",
    "para",
    "por",
    "que",
    "se",
    "sem",
    "um",
    "uma",
    "uns",
    "umas",
}


@dataclass(slots=True, frozen=True)
class GlossaryBuilderSuggestion:
    source_term: str
    target_lang: str
    occurrences_doc: int
    occurrences_corpus: int
    df_pages: int
    df_docs: int
    suggested_translation: str
    confidence: float
    recommended_scope: BuilderScope


def _normalize_text(value: object) -> str:
    return _SPACE_RE.sub(" ", str(value or "").strip())


def _header_like_line(text: str) -> bool:
    cleaned = _normalize_text(text)
    if cleaned == "":
        return False
    if _SECTION_HEADER_RE.search(cleaned):
        return True
    letters = [ch for ch in cleaned if ch.isalpha()]
    if not letters:
        return False
    upper = sum(1 for ch in letters if ch.upper() == ch)
    return len(cleaned) <= 90 and (upper / float(max(1, len(letters)))) >= 0.60


def _is_identifier_like(term: str) -> bool:
    cleaned = term.strip()
    if cleaned == "":
        return True
    lowered = cleaned.casefold()
    if _EMAIL_RE.search(lowered) or _URL_RE.search(lowered):
        return True
    if _IBAN_LIKE_RE.search(cleaned) or _CASE_ID_LIKE_RE.search(cleaned) or _DATE_LIKE_RE.search(cleaned):
        return True
    if _ADDRESS_LIKE_RE.search(cleaned):
        return True
    digit_count = sum(1 for ch in cleaned if ch.isdigit())
    if digit_count > 0 and digit_count / max(1, len(cleaned)) >= 0.25:
        return True
    return False


def _candidate_allowed(tokens: list[str]) -> bool:
    if not tokens:
        return False
    if len(tokens) == 1 and len(tokens[0]) < 3:
        return False
    if all(tok in _STOPWORDS_PT for tok in tokens):
        return False
    phrase = " ".join(tokens)
    if _is_identifier_like(phrase):
        return False
    return True


def _candidate_ngrams(tokens: list[str], n: int) -> list[list[str]]:
    if n <= 0 or len(tokens) < n:
        return []
    return [tokens[idx : idx + n] for idx in range(0, len(tokens) - n + 1)]


def create_builder_stats() -> dict[str, Any]:
    return {
        "term_tf": {},
        "term_pages": {},
        "term_docs": {},
        "term_doc_tf": {},
        "term_header_hits": {},
    }


def update_builder_stats_from_page(
    *,
    doc_id: str,
    page_number: int,
    text: str,
    stats: dict[str, Any] | None = None,
    mode: BuilderMode = "full_text",
) -> dict[str, Any]:
    if stats is None:
        stats = create_builder_stats()
    selected_mode: BuilderMode = mode if mode in {"full_text", "headers_only"} else "full_text"
    if _normalize_text(text) == "":
        return stats

    term_tf: dict[str, int] = stats.setdefault("term_tf", {})
    term_pages: dict[str, set[str]] = stats.setdefault("term_pages", {})
    term_docs: dict[str, set[str]] = stats.setdefault("term_docs", {})
    term_doc_tf: dict[str, dict[str, int]] = stats.setdefault("term_doc_tf", {})
    term_header_hits: dict[str, int] = stats.setdefault("term_header_hits", {})
    page_key = f"{doc_id}#{int(page_number)}"

    for raw_line in str(text or "").splitlines():
        line = _normalize_text(raw_line)
        if line == "":
            continue
        header_like = _header_like_line(line)
        if selected_mode == "headers_only" and not header_like:
            continue
        tokens = tokenize_pt(line)
        if not tokens:
            continue
        for n_size in (1, 2, 3, 4):
            for ngram in _candidate_ngrams(tokens, n_size):
                if not _candidate_allowed(ngram):
                    continue
                term = " ".join(ngram)
                term_tf[term] = term_tf.get(term, 0) + 1
                term_pages.setdefault(term, set()).add(page_key)
                term_docs.setdefault(term, set()).add(doc_id)
                per_doc = term_doc_tf.setdefault(term, {})
                per_doc[doc_id] = per_doc.get(doc_id, 0) + 1
                if header_like:
                    term_header_hits[term] = term_header_hits.get(term, 0) + 1
    return stats


def _confidence(tf: int, df_pages: int, df_docs: int, header_hits: int) -> float:
    raw = (
        (math.log1p(float(tf)) * 0.45)
        + (math.log1p(float(df_pages)) * 0.30)
        + (math.log1p(float(df_docs)) * 0.20)
        + (0.05 if header_hits > 0 else 0.0)
    )
    return round(max(0.0, min(1.0, raw / 3.2)), 3)


def _score(tf: int, df_pages: int, df_docs: int, header_hits: int) -> float:
    header_boost = 1.15 if header_hits > 0 else 1.0
    return float(tf) * (1.0 + math.log1p(float(df_pages)) + (0.5 * math.log1p(float(df_docs)))) * header_boost


def finalize_builder_suggestions(
    stats: dict[str, Any],
    *,
    target_lang: str,
    min_tf_per_doc: int = 5,
    min_tf_corpus: int = 3,
    min_df_docs: int = 2,
) -> list[GlossaryBuilderSuggestion]:
    term_tf: dict[str, int] = stats.get("term_tf", {}) if isinstance(stats.get("term_tf"), dict) else {}
    term_pages: dict[str, set[str]] = stats.get("term_pages", {}) if isinstance(stats.get("term_pages"), dict) else {}
    term_docs: dict[str, set[str]] = stats.get("term_docs", {}) if isinstance(stats.get("term_docs"), dict) else {}
    term_doc_tf: dict[str, dict[str, int]] = (
        stats.get("term_doc_tf", {}) if isinstance(stats.get("term_doc_tf"), dict) else {}
    )
    term_header_hits: dict[str, int] = (
        stats.get("term_header_hits", {}) if isinstance(stats.get("term_header_hits"), dict) else {}
    )

    rows: list[GlossaryBuilderSuggestion] = []
    for term, tf in term_tf.items():
        tf_value = int(tf)
        if tf_value <= 0:
            continue
        df_pages = len(term_pages.get(term, set()))
        df_docs = len(term_docs.get(term, set()))
        per_doc_counts = term_doc_tf.get(term, {})
        doc_max = max(per_doc_counts.values()) if per_doc_counts else tf_value
        meets_threshold = (doc_max >= int(min_tf_per_doc)) or (
            tf_value >= int(min_tf_corpus) and df_docs >= int(min_df_docs)
        )
        if not meets_threshold:
            continue
        header_hits = int(term_header_hits.get(term, 0))
        confidence = _confidence(tf_value, df_pages, df_docs, header_hits)
        recommended_scope: BuilderScope = "project" if df_docs >= int(min_df_docs) else "personal"
        rows.append(
            GlossaryBuilderSuggestion(
                source_term=term,
                target_lang=str(target_lang).strip().upper(),
                occurrences_doc=int(doc_max),
                occurrences_corpus=tf_value,
                df_pages=df_pages,
                df_docs=df_docs,
                suggested_translation="",
                confidence=confidence,
                recommended_scope=recommended_scope,
            )
        )
    rows.sort(
        key=lambda item: (
            -_score(
                item.occurrences_corpus,
                item.df_pages,
                item.df_docs,
                1 if item.recommended_scope == "project" else 0,
            ),
            -item.occurrences_corpus,
            -item.df_docs,
            -item.df_pages,
            item.source_term.casefold(),
        )
    )
    return rows


def mine_glossary_builder_suggestions(
    corpus_pages: list[dict[str, object]],
    *,
    target_lang: str,
    mode: BuilderMode = "full_text",
    min_tf_per_doc: int = 5,
    min_tf_corpus: int = 3,
    min_df_docs: int = 2,
) -> list[GlossaryBuilderSuggestion]:
    stats = create_builder_stats()
    for page in corpus_pages:
        update_builder_stats_from_page(
            doc_id=str(page.get("doc_id", "") or "doc"),
            page_number=int(page.get("page_number", 0) or 0),
            text=str(page.get("text", "") or ""),
            stats=stats,
            mode=mode,
        )
    return finalize_builder_suggestions(
        stats,
        target_lang=target_lang,
        min_tf_per_doc=min_tf_per_doc,
        min_tf_corpus=min_tf_corpus,
        min_df_docs=min_df_docs,
    )


def serialize_glossary_builder_suggestions(rows: list[GlossaryBuilderSuggestion]) -> list[dict[str, object]]:
    return [
        {
            "source_term": row.source_term,
            "target_lang": row.target_lang,
            "occurrences_doc": int(row.occurrences_doc),
            "occurrences_corpus": int(row.occurrences_corpus),
            "df_pages": int(row.df_pages),
            "df_docs": int(row.df_docs),
            "suggested_translation": row.suggested_translation,
            "confidence": float(row.confidence),
            "recommended_scope": row.recommended_scope,
        }
        for row in rows
    ]


def build_glossary_builder_markdown(
    rows: list[GlossaryBuilderSuggestion],
    *,
    generated_at_iso: str,
    corpus_label: str,
    total_sources: int,
    total_pages_scanned: int,
) -> str:
    lines: list[str] = [
        "# Glossary Builder Suggestions",
        "",
        f"Generated: {generated_at_iso}",
        f"Corpus: {corpus_label}",
        f"Sources processed: {max(0, int(total_sources))}",
        f"Pages scanned: {max(0, int(total_pages_scanned))}",
        "",
    ]
    if not rows:
        lines.append("No suggestions.")
        return "\n".join(lines).strip() + "\n"
    lines.append(
        "| Source term | Target | Occurrences (doc) | Occurrences (corpus) | Pages | Docs | Confidence | Recommended scope | Suggested translation |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for row in rows:
        source = row.source_term.replace("|", "\\|")
        suggested = row.suggested_translation.replace("|", "\\|")
        lines.append(
            "| "
            + " | ".join(
                [
                    source,
                    row.target_lang,
                    str(int(row.occurrences_doc)),
                    str(int(row.occurrences_corpus)),
                    str(int(row.df_pages)),
                    str(int(row.df_docs)),
                    f"{float(row.confidence):.3f}",
                    row.recommended_scope,
                    suggested,
                ]
            )
            + " |"
        )
    return "\n".join(lines).strip() + "\n"


def suggestions_to_glossary_entries(
    rows: list[GlossaryBuilderSuggestion],
    *,
    target_lang: str,
    match_mode: Literal["exact", "contains"] = "exact",
    source_lang: str = "PT",
    tier: int = 2,
) -> list[GlossaryEntry]:
    output: list[GlossaryEntry] = []
    for row in rows:
        source_text = _normalize_text(row.source_term)
        preferred = _normalize_text(row.suggested_translation)
        if source_text == "" or preferred == "":
            continue
        output.append(
            GlossaryEntry(
                source_text=source_text,
                preferred_translation=preferred,
                match_mode=match_mode,
                source_lang=source_lang,  # type: ignore[arg-type]
                tier=int(tier),
            )
        )
    return output
