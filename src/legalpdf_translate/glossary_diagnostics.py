"""Glossary diagnostics: PKG Pareto + CG match analysis + ambiguity heuristics."""

from __future__ import annotations

import math
import re
import threading
from dataclasses import dataclass
from typing import Any

from .glossary import GlossaryEntry
from .glossary_builder import create_builder_stats, update_builder_stats_from_page
from .study_glossary import tokenize_pt

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class PageCoverageRecord:
    page_index: int
    total_pages: int
    source_route: str
    char_count: int
    segment_count: int
    pkg_token_count: int
    cg_entries_active: int
    cg_matches_count: int
    cg_matched_keys: list[str]


@dataclass(slots=True, frozen=True)
class AmbiguousCandidate:
    source_text: str
    frequency: int
    df_pages: int
    heuristic_tags: list[str]
    cg_covered: bool


@dataclass(slots=True, frozen=True)
class DriftCandidate:
    source_text: str
    translations_seen: list[str]
    page_indices: list[int]


# ---------------------------------------------------------------------------
# Ambiguity heuristics
# ---------------------------------------------------------------------------

_LEGAL_CITATION_RE = re.compile(
    r"(?:\bArt\.?\s*\d|\bn\.?[ºo]\s*\d|\balínea\s+[a-z]|\bLei\s+n|"
    r"\bDecreto|Código\s|\bRegulamento\b|\bp\.\s*e\s*p\.?\s*pelo)",
    re.IGNORECASE,
)

_ABBREVIATION_RE = re.compile(r"\b[A-Z]{2,}\b")

_MIXED_SCRIPT_RE = re.compile(
    r"(?:[\u0600-\u06FF].*[A-Za-z]|[A-Za-z].*[\u0600-\u06FF])",
)


def classify_ambiguity_heuristics(
    term: str,
    *,
    cg_source_texts: set[str],
    target_renderings: list[str] | None = None,
) -> list[str]:
    """Return heuristic tags explaining why *term* is considered ambiguous.

    Heuristics enabled:
    - A: ``cg_entry`` — term is already in the Consistency Glossary.
    - B: ``legal_citation``, ``abbreviation``, ``mixed_script`` — token-shape.
    - C: ``varied_translation`` — multiple distinct target renderings observed.
    """
    tags: list[str] = []
    normalized = term.strip().casefold()
    if normalized in {t.casefold() for t in cg_source_texts}:
        tags.append("cg_entry")
    if _LEGAL_CITATION_RE.search(term):
        tags.append("legal_citation")
    if _ABBREVIATION_RE.search(term):
        tags.append("abbreviation")
    if _MIXED_SCRIPT_RE.search(term):
        tags.append("mixed_script")
    if target_renderings is not None:
        unique = {r.strip().casefold() for r in target_renderings if r.strip()}
        if len(unique) > 1:
            tags.append("varied_translation")
    return tags


# ---------------------------------------------------------------------------
# Accumulator
# ---------------------------------------------------------------------------


class GlossaryDiagnosticsAccumulator:
    """Thread-safe collector for per-page PKG and CG diagnostics."""

    def __init__(self, total_pages: int) -> None:
        self._lock = threading.Lock()
        self._total_pages = int(total_pages)
        self._page_coverage: dict[int, PageCoverageRecord] = {}
        self._pkg_stats: dict[str, Any] = create_builder_stats()
        self._pkg_token_counts: dict[int, int] = {}  # page_index -> raw token count
        self._cg_entries: list[GlossaryEntry] = []
        self._cg_page_matches: dict[int, dict[str, int]] = {}  # page -> {source_text: count}
        self._cg_page_active_counts: dict[int, int] = {}
        self._lemma_mapping: dict[str, str] | None = None

    # -- setup ---------------------------------------------------------------

    def set_cg_entries(self, entries: list[GlossaryEntry]) -> None:
        with self._lock:
            self._cg_entries = list(entries)

    def set_lemma_mapping(self, mapping: dict[str, str]) -> None:
        with self._lock:
            self._lemma_mapping = dict(mapping)

    # -- per-page recording --------------------------------------------------

    def record_page_pkg_stats(
        self,
        *,
        page_index: int,
        source_text: str,
        doc_id: str,
    ) -> int:
        """Tokenize *source_text* and accumulate PKG frequency stats.

        Returns the raw token count for the page.
        """
        tokens = tokenize_pt(source_text)
        token_count = len(tokens)
        with self._lock:
            self._pkg_token_counts[page_index] = token_count
            update_builder_stats_from_page(
                doc_id=doc_id,
                page_number=page_index,
                text=source_text,
                stats=self._pkg_stats,
                mode="full_text",
            )
        return token_count

    def record_page_cg_matches(
        self,
        *,
        page_index: int,
        active_entries: list[GlossaryEntry],
        source_text: str,
    ) -> int:
        """Count CG entries whose source_text appears in *source_text*.

        Returns total match count for the page.
        """
        lowered = source_text.casefold()
        matches: dict[str, int] = {}
        for entry in active_entries:
            needle = entry.source_text.casefold()
            if needle and needle in lowered:
                matches[entry.source_text] = matches.get(entry.source_text, 0) + 1
        total = sum(matches.values())
        with self._lock:
            self._cg_page_matches[page_index] = matches
            self._cg_page_active_counts[page_index] = len(active_entries)
        return total

    def record_page_coverage(self, record: PageCoverageRecord) -> None:
        with self._lock:
            self._page_coverage[record.page_index] = record

    # -- finalizers ----------------------------------------------------------

    def finalize_coverage_proof(self) -> dict[str, Any]:
        with self._lock:
            processed = len(self._page_coverage)
            per_page = []
            for idx in sorted(self._page_coverage):
                rec = self._page_coverage[idx]
                per_page.append({
                    "page_index": rec.page_index,
                    "total_pages": rec.total_pages,
                    "source_route": rec.source_route,
                    "char_count": rec.char_count,
                    "segment_count": rec.segment_count,
                    "pkg_token_count": rec.pkg_token_count,
                    "cg_entries_active": rec.cg_entries_active,
                    "cg_matches_count": rec.cg_matches_count,
                    "cg_matched_keys": rec.cg_matched_keys[:10],
                })
        return {
            "processed_pages": processed,
            "total_pages": self._total_pages,
            "assertion": f"Processed pages: {processed}/{self._total_pages}",
            "per_page": per_page,
        }

    def finalize_pkg_pareto(self) -> dict[str, Any]:
        with self._lock:
            term_tf: dict[str, int] = dict(self._pkg_stats.get("term_tf", {}))
            term_pages: dict[str, set[str]] = {
                k: set(v) for k, v in self._pkg_stats.get("term_pages", {}).items()
            }
            total_raw_tokens = sum(self._pkg_token_counts.values())
            lemma_map = dict(self._lemma_mapping) if self._lemma_mapping is not None else None

        lemma_mode = lemma_map is not None and len(lemma_map) > 0

        if not term_tf:
            return {
                "total_tokens": total_raw_tokens,
                "unique_terms": 0,
                "top_20_pct_coverage": 0.0,
                "core80_count": 0,
                "core80_terms": [],
                "suggested_pkg_candidates": [],
                "lemma_mode": lemma_mode,
            }

        # If lemma mode, group surface forms by lemma
        if lemma_mode:
            assert lemma_map is not None
            lemma_tf: dict[str, int] = {}
            lemma_surface_forms: dict[str, list[str]] = {}
            lemma_pages: dict[str, set[str]] = {}
            for surface, tf in term_tf.items():
                lemma = lemma_map.get(surface.casefold(), surface.casefold())
                lemma_tf[lemma] = lemma_tf.get(lemma, 0) + tf
                lemma_surface_forms.setdefault(lemma, []).append(surface)
                lemma_pages.setdefault(lemma, set()).update(term_pages.get(surface, set()))
            effective_tf = lemma_tf
            effective_pages = lemma_pages
        else:
            effective_tf = term_tf
            effective_pages = term_pages
            lemma_surface_forms = {}

        ranked = sorted(
            effective_tf.items(),
            key=lambda kv: (-kv[1], kv[0]),
        )
        unique_terms = len(ranked)
        total_term_occurrences = sum(tf for _, tf in ranked)

        # Pareto: smallest set covering ~80%
        cumulative = 0
        core80: list[dict[str, Any]] = []
        for term, tf in ranked:
            cumulative += tf
            entry: dict[str, Any] = {
                "term": term,
                "tf": tf,
                "df_pages": len(effective_pages.get(term, set())),
            }
            if lemma_mode and term in lemma_surface_forms:
                forms = sorted(set(lemma_surface_forms[term]))
                if len(forms) > 1 or (len(forms) == 1 and forms[0] != term):
                    entry["surface_forms"] = forms
            core80.append(entry)
            if cumulative / max(1, total_term_occurrences) >= 0.80:
                break

        # Top 20% of unique terms
        top_20_count = max(1, math.ceil(unique_terms * 0.20))
        top_20_terms = ranked[:top_20_count]
        top_20_tf = sum(tf for _, tf in top_20_terms)
        top_20_pct_coverage = top_20_tf / max(1, total_term_occurrences)

        # Suggested candidates (top 50, no threshold)
        suggested = []
        for term, tf in ranked[:50]:
            dp = len(effective_pages.get(term, set()))
            entry_s: dict[str, Any] = {
                "term": term,
                "tf": tf,
                "df_pages": dp,
            }
            if lemma_mode and term in lemma_surface_forms:
                forms = sorted(set(lemma_surface_forms[term]))
                if len(forms) > 1 or (len(forms) == 1 and forms[0] != term):
                    entry_s["surface_forms"] = forms
            suggested.append(entry_s)

        result: dict[str, Any] = {
            "total_tokens": total_raw_tokens,
            "unique_terms": unique_terms,
            "total_term_occurrences": total_term_occurrences,
            "top_20_pct_coverage": round(top_20_pct_coverage, 4),
            "core80_count": len(core80),
            "core80_terms": core80,
            "suggested_pkg_candidates": suggested,
            "lemma_mode": lemma_mode,
        }
        if lemma_mode:
            result["lemma_grouped_unique_terms"] = unique_terms
            result["surface_unique_terms"] = len(term_tf)
        return result

    def finalize_cg_summary(self) -> dict[str, Any]:
        with self._lock:
            entries_loaded = len(self._cg_entries)
            cg_source_texts = {e.source_text for e in self._cg_entries}
            cg_source_texts_lower = {t.casefold() for t in cg_source_texts}

            # Per-page matches
            per_page: list[dict[str, Any]] = []
            all_matched_keys: set[str] = set()
            total_match_count = 0
            for page_idx in sorted(self._cg_page_matches):
                page_matches = self._cg_page_matches[page_idx]
                page_total = sum(page_matches.values())
                matched_keys = sorted(page_matches.keys())
                all_matched_keys.update(matched_keys)
                total_match_count += page_total
                per_page.append({
                    "page_index": page_idx,
                    "match_count": page_total,
                    "matched_entries": matched_keys[:10],
                    "entries_active": self._cg_page_active_counts.get(page_idx, 0),
                })

            never_matched = sorted(cg_source_texts - all_matched_keys)

            # Aggregate term frequencies across pages for ambiguous analysis
            term_page_freq: dict[str, int] = {}
            term_pages_seen: dict[str, set[int]] = {}
            for page_idx, page_matches in self._cg_page_matches.items():
                for source_text, count in page_matches.items():
                    term_page_freq[source_text] = term_page_freq.get(source_text, 0) + count
                    term_pages_seen.setdefault(source_text, set()).add(page_idx)

            # Also include high-frequency PKG terms for ambiguity check
            pkg_tf: dict[str, int] = dict(self._pkg_stats.get("term_tf", {}))
            pkg_pages: dict[str, set[str]] = {
                k: set(v) for k, v in self._pkg_stats.get("term_pages", {}).items()
            }

        # Build ambiguous candidates
        ambiguous: list[AmbiguousCandidate] = []
        seen_terms: set[str] = set()

        # Check CG-matched terms first
        for term, freq in sorted(term_page_freq.items(), key=lambda kv: -kv[1]):
            tags = classify_ambiguity_heuristics(
                term,
                cg_source_texts=cg_source_texts,
            )
            if tags:
                ambiguous.append(AmbiguousCandidate(
                    source_text=term,
                    frequency=freq,
                    df_pages=len(term_pages_seen.get(term, set())),
                    heuristic_tags=tags,
                    cg_covered=term.casefold() in cg_source_texts_lower,
                ))
                seen_terms.add(term.casefold())

        # Check PKG high-frequency terms for token-shape ambiguity
        for term, tf in sorted(pkg_tf.items(), key=lambda kv: -kv[1])[:200]:
            if term.casefold() in seen_terms:
                continue
            tags = classify_ambiguity_heuristics(
                term,
                cg_source_texts=cg_source_texts,
            )
            if tags:
                ambiguous.append(AmbiguousCandidate(
                    source_text=term,
                    frequency=tf,
                    df_pages=len(pkg_pages.get(term, set())),
                    heuristic_tags=tags,
                    cg_covered=term.casefold() in cg_source_texts_lower,
                ))
                seen_terms.add(term.casefold())

        # Sort ambiguous by frequency desc
        ambiguous.sort(key=lambda c: (-c.frequency, c.source_text.casefold()))

        # Ambiguous Pareto: smallest set covering ~80% of ambiguous frequency
        ambig_total = sum(c.frequency for c in ambiguous)
        ambig_core80: list[dict[str, Any]] = []
        cumulative = 0
        for cand in ambiguous:
            cumulative += cand.frequency
            ambig_core80.append({
                "source_text": cand.source_text,
                "frequency": cand.frequency,
                "df_pages": cand.df_pages,
                "heuristic_tags": cand.heuristic_tags,
                "cg_covered": cand.cg_covered,
            })
            if ambig_total > 0 and cumulative / ambig_total >= 0.80:
                break

        max_active = max(self._cg_page_active_counts.values()) if self._cg_page_active_counts else 0

        return {
            "entries_loaded": entries_loaded,
            "entries_active_max": max_active,
            "per_page_matches": per_page,
            "total_match_count": total_match_count,
            "unique_matched_entries": len(all_matched_keys),
            "never_matched_entries": never_matched,
            "ambiguous_candidates": [
                {
                    "source_text": c.source_text,
                    "frequency": c.frequency,
                    "df_pages": c.df_pages,
                    "heuristic_tags": c.heuristic_tags,
                    "cg_covered": c.cg_covered,
                }
                for c in ambiguous
            ],
            "ambiguous_pareto_core80": ambig_core80,
            "ambiguous_total_frequency": ambig_total,
            "drift_candidates": [],  # populated by detect_drift below
        }


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------


def emit_diagnostics_events(
    accumulator: GlossaryDiagnosticsAccumulator,
    collector: object,
) -> None:
    """Emit all glossary diagnostics events into *collector*.

    *collector* must have an ``add_event`` method matching
    ``RunEventCollector.add_event``.
    """
    if collector is None or not hasattr(collector, "add_event"):
        return

    stage = "glossary_diagnostics"

    # 1) Page coverage proof
    proof = accumulator.finalize_coverage_proof()
    collector.add_event(
        event_type="page_coverage_summary",
        stage=stage,
        details=proof,
    )

    # 2) PKG per-page token stats
    with accumulator._lock:
        pkg_counts = dict(accumulator._pkg_token_counts)
    for page_idx in sorted(pkg_counts):
        collector.add_event(
            event_type="pkg_token_stats_page",
            stage=stage,
            page_index=page_idx,
            counters={"token_count": pkg_counts[page_idx]},
        )

    # 3) PKG Pareto summary
    pkg_pareto = accumulator.finalize_pkg_pareto()
    collector.add_event(
        event_type="pkg_pareto_summary",
        stage=stage,
        details=pkg_pareto,
    )

    # 4) CG load summary
    with accumulator._lock:
        entries_loaded = len(accumulator._cg_entries)
    collector.add_event(
        event_type="cg_load_summary",
        stage=stage,
        counters={"entries_loaded": entries_loaded},
    )

    # 5) CG per-page matches
    with accumulator._lock:
        page_matches_copy = dict(accumulator._cg_page_matches)
        page_active_copy = dict(accumulator._cg_page_active_counts)
    for page_idx in sorted(page_matches_copy):
        matches = page_matches_copy[page_idx]
        collector.add_event(
            event_type="cg_apply_page",
            stage=stage,
            page_index=page_idx,
            counters={
                "match_count": sum(matches.values()),
                "entries_active": page_active_copy.get(page_idx, 0),
                "matched_keys": sorted(matches.keys())[:10],
            },
        )

    # 6) CG ambiguous Pareto summary
    cg_summary = accumulator.finalize_cg_summary()
    collector.add_event(
        event_type="cg_ambiguous_pareto_summary",
        stage=stage,
        details={
            "ambiguous_candidates": cg_summary["ambiguous_candidates"],
            "ambiguous_pareto_core80": cg_summary["ambiguous_pareto_core80"],
            "ambiguous_total_frequency": cg_summary["ambiguous_total_frequency"],
            "entries_loaded": cg_summary["entries_loaded"],
            "total_match_count": cg_summary["total_match_count"],
            "unique_matched_entries": cg_summary["unique_matched_entries"],
            "never_matched_entries": cg_summary["never_matched_entries"],
        },
    )

    # 7) CG drift candidates
    collector.add_event(
        event_type="cg_drift_candidates",
        stage=stage,
        details={"drift_candidates": cg_summary["drift_candidates"]},
    )
