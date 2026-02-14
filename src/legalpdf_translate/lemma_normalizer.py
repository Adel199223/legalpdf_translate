"""Portuguese lemma normalization via OpenAI API (analytics-only, batch mode).

This module provides batch lemmatization of Portuguese surface forms for use
in glossary diagnostics (PKG Pareto grouping).  It does NOT affect glossary
matching, translation prompts, or any production pipeline behaviour.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .openai_client import OpenAIResponsesClient

_BATCH_INSTRUCTIONS = (
    "You are a Portuguese morphological normalizer. "
    "For each word or phrase below, return ONLY its dictionary lemma form "
    "(masculine singular for nouns/adjectives, infinitive for verbs). "
    "Return exactly one lemma per line, in the same order as the input. "
    "No numbering, no explanations, no extra text."
)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


class LemmaCache:
    """Thread-safe persistent lemma cache (surface form → lemma, casefolded)."""

    def __init__(self, cache_path: Path | None = None) -> None:
        self._lock = threading.Lock()
        self._cache: dict[str, str] = {}
        self._path = cache_path
        self._dirty = False
        if cache_path is not None and cache_path.exists():
            self._load()

    # -- public API ----------------------------------------------------------

    def get(self, term: str) -> str | None:
        key = term.strip().casefold()
        with self._lock:
            return self._cache.get(key)

    def put(self, term: str, lemma: str) -> None:
        key = term.strip().casefold()
        value = lemma.strip().casefold()
        if not key or not value:
            return
        with self._lock:
            self._cache[key] = value
            self._dirty = True

    def save(self) -> None:
        with self._lock:
            if not self._dirty or self._path is None:
                return
            snapshot = dict(self._cache)
            self._dirty = False
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._path.with_suffix(".tmp")
        temp.write_text(json.dumps(snapshot, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        temp.replace(self._path)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {"size": len(self._cache), "path": str(self._path or "")}

    # -- internal ------------------------------------------------------------

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(k, str) and isinstance(v, str):
                    self._cache[k.casefold()] = v.casefold()


# ---------------------------------------------------------------------------
# Batch result
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class LemmaBatchResult:
    mapping: dict[str, str] = field(default_factory=dict)
    api_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    failures: int = 0
    fallback_to_surface: bool = False
    wall_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Batch normalization
# ---------------------------------------------------------------------------


def _normalize_batch(
    terms: list[str],
    *,
    client: OpenAIResponsesClient,
    effort: str,
) -> tuple[list[str], dict[str, int]]:
    """Send a single batch of terms to the API and return lemmas + usage.

    Returns ``(lemmas, usage_dict)``.  Raises on API or parse failure.
    """
    prompt_text = "\n".join(terms)
    result = client.create_page_response(
        instructions=_BATCH_INSTRUCTIONS,
        prompt_text=prompt_text,
        effort=effort,
        image_data_url=None,
    )
    response_lines = [
        line.strip() for line in result.raw_output.strip().splitlines() if line.strip()
    ]
    if len(response_lines) != len(terms):
        raise ValueError(
            f"Lemma batch response mismatch: expected {len(terms)} lines, got {len(response_lines)}"
        )
    usage = result.usage or {}
    return response_lines, {
        "input_tokens": int(usage.get("input_tokens", 0) or 0),
        "output_tokens": int(usage.get("output_tokens", 0) or 0),
    }


def batch_normalize_lemmas(
    terms: list[str],
    *,
    client: OpenAIResponsesClient,
    effort: str = "medium",
    cache: LemmaCache,
    batch_size: int = 100,
    progress_callback: Callable[[int, str], None] | None = None,
) -> LemmaBatchResult:
    """Normalize Portuguese surface forms to lemmas using batch API calls.

    Always returns a result — never raises.  On failure, individual terms
    fall back to their surface form (casefolded).
    """
    t0 = time.monotonic()

    # Deduplicate + casefold
    seen: set[str] = set()
    unique: list[str] = []
    for raw in terms:
        key = raw.strip().casefold()
        if key and key not in seen:
            seen.add(key)
            unique.append(key)

    mapping: dict[str, str] = {}
    cache_hits = 0
    uncached: list[str] = []

    for term in unique:
        cached = cache.get(term)
        if cached is not None:
            mapping[term] = cached
            cache_hits += 1
        else:
            uncached.append(term)

    result = LemmaBatchResult(
        mapping=mapping,
        cache_hits=cache_hits,
        cache_misses=len(uncached),
    )

    if not uncached:
        result.wall_seconds = time.monotonic() - t0
        return result

    # Batch API calls
    batches = [uncached[i : i + batch_size] for i in range(0, len(uncached), batch_size)]
    total_batches = len(batches)
    failed_batches = 0

    for batch_idx, batch in enumerate(batches):
        if progress_callback is not None:
            pct = int(((batch_idx) / max(1, total_batches)) * 100)
            progress_callback(pct, f"Lemmatizing batch {batch_idx + 1}/{total_batches}...")
        try:
            lemmas, usage = _normalize_batch(batch, client=client, effort=effort)
            result.api_calls += 1
            result.input_tokens += usage.get("input_tokens", 0)
            result.output_tokens += usage.get("output_tokens", 0)
            for term, lemma in zip(batch, lemmas):
                normalized_lemma = lemma.strip().casefold()
                if normalized_lemma:
                    mapping[term] = normalized_lemma
                    cache.put(term, normalized_lemma)
                else:
                    mapping[term] = term  # surface fallback
        except Exception:  # noqa: BLE001
            failed_batches += 1
            result.failures += len(batch)
            for term in batch:
                mapping[term] = term  # surface fallback

    if failed_batches == total_batches and total_batches > 0:
        result.fallback_to_surface = True

    try:
        cache.save()
    except Exception:  # noqa: BLE001
        pass

    if progress_callback is not None:
        progress_callback(100, "Lemmatization complete.")

    result.mapping = mapping
    result.wall_seconds = time.monotonic() - t0
    return result
