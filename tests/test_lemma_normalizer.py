"""Tests for lemma_normalizer module and PKG Pareto lemma grouping."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# LemmaCache
# ---------------------------------------------------------------------------


def test_cache_put_get() -> None:
    from legalpdf_translate.lemma_normalizer import LemmaCache

    cache = LemmaCache()
    cache.put("arguidos", "arguido")
    assert cache.get("arguidos") == "arguido"


def test_cache_case_insensitive() -> None:
    from legalpdf_translate.lemma_normalizer import LemmaCache

    cache = LemmaCache()
    cache.put("Arguidos", "arguido")
    assert cache.get("arguidos") == "arguido"
    assert cache.get("ARGUIDOS") == "arguido"


def test_cache_persistence(tmp_path: Path) -> None:
    from legalpdf_translate.lemma_normalizer import LemmaCache

    path = tmp_path / "lemma_cache.json"
    cache1 = LemmaCache(cache_path=path)
    cache1.put("sentenças", "sentença")
    cache1.save()
    assert path.exists()

    # Reload
    cache2 = LemmaCache(cache_path=path)
    assert cache2.get("sentenças") == "sentença"


def test_cache_empty_on_missing_file(tmp_path: Path) -> None:
    from legalpdf_translate.lemma_normalizer import LemmaCache

    path = tmp_path / "nonexistent.json"
    cache = LemmaCache(cache_path=path)
    assert cache.get("anything") is None
    assert cache.stats()["size"] == 0


def test_cache_corrupted_file(tmp_path: Path) -> None:
    from legalpdf_translate.lemma_normalizer import LemmaCache

    path = tmp_path / "bad.json"
    path.write_text("not json!", encoding="utf-8")
    cache = LemmaCache(cache_path=path)
    assert cache.stats()["size"] == 0


def test_cache_no_save_when_clean() -> None:
    """Cache with no changes should not write to disk."""
    from legalpdf_translate.lemma_normalizer import LemmaCache

    cache = LemmaCache()
    cache.save()  # Should not raise even without path


def test_cache_put_ignores_empty() -> None:
    from legalpdf_translate.lemma_normalizer import LemmaCache

    cache = LemmaCache()
    cache.put("", "lemma")
    cache.put("term", "")
    assert cache.stats()["size"] == 0


# ---------------------------------------------------------------------------
# batch_normalize_lemmas (mocked client)
# ---------------------------------------------------------------------------


def _mock_client(response_text: str, usage: dict | None = None) -> MagicMock:
    """Create a mock OpenAI client returning the given response text."""
    mock = MagicMock()
    result = MagicMock()
    result.raw_output = response_text
    result.usage = usage or {"input_tokens": 10, "output_tokens": 5}
    mock.create_page_response.return_value = result
    return mock


def test_batch_all_cached(tmp_path: Path) -> None:
    from legalpdf_translate.lemma_normalizer import LemmaCache, batch_normalize_lemmas

    cache = LemmaCache(cache_path=tmp_path / "c.json")
    cache.put("arguidos", "arguido")
    cache.put("sentenças", "sentença")

    client = _mock_client("")
    result = batch_normalize_lemmas(
        ["arguidos", "sentenças"],
        client=client,
        cache=cache,
    )
    assert result.cache_hits == 2
    assert result.api_calls == 0
    assert result.mapping["arguidos"] == "arguido"
    assert result.mapping["sentenças"] == "sentença"


def test_batch_api_call(tmp_path: Path) -> None:
    from legalpdf_translate.lemma_normalizer import LemmaCache, batch_normalize_lemmas

    cache = LemmaCache(cache_path=tmp_path / "c.json")
    client = _mock_client("arguido\nsentença")

    result = batch_normalize_lemmas(
        ["arguidos", "sentenças"],
        client=client,
        cache=cache,
    )
    assert result.api_calls == 1
    assert result.cache_misses == 2
    assert result.mapping["arguidos"] == "arguido"
    assert result.mapping["sentenças"] == "sentença"
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    # Verify cache was updated
    assert cache.get("arguidos") == "arguido"


def test_batch_partial_failure(tmp_path: Path) -> None:
    """One batch fails, others succeed — failed terms fallback to surface."""
    from legalpdf_translate.lemma_normalizer import LemmaCache, batch_normalize_lemmas

    cache = LemmaCache(cache_path=tmp_path / "c.json")

    call_count = 0

    def side_effect(**kwargs: Any) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First batch succeeds
            r = MagicMock()
            r.raw_output = "arguido\nsentença"
            r.usage = {"input_tokens": 8, "output_tokens": 4}
            return r
        else:
            # Second batch fails
            raise RuntimeError("API error")

    client = MagicMock()
    client.create_page_response.side_effect = side_effect

    terms = ["arguidos", "sentenças", "tribunal", "réu"]
    result = batch_normalize_lemmas(
        terms,
        client=client,
        cache=cache,
        batch_size=2,
    )
    assert result.api_calls == 1  # Only first batch counted
    assert result.failures == 2  # Second batch terms
    assert not result.fallback_to_surface  # Not all failed
    assert result.mapping["arguidos"] == "arguido"
    assert result.mapping["sentenças"] == "sentença"
    # Failed terms fall back to surface
    assert result.mapping["tribunal"] == "tribunal"
    assert result.mapping["réu"] == "réu"


def test_batch_total_failure(tmp_path: Path) -> None:
    from legalpdf_translate.lemma_normalizer import LemmaCache, batch_normalize_lemmas

    cache = LemmaCache(cache_path=tmp_path / "c.json")
    client = MagicMock()
    client.create_page_response.side_effect = RuntimeError("API error")

    result = batch_normalize_lemmas(
        ["arguidos", "sentenças"],
        client=client,
        cache=cache,
    )
    assert result.fallback_to_surface is True
    assert result.failures == 2
    assert result.api_calls == 0
    # Surface fallback
    assert result.mapping["arguidos"] == "arguidos"


def test_batch_size_splitting(tmp_path: Path) -> None:
    """150 terms with batch_size=100 should produce 2 batches."""
    from legalpdf_translate.lemma_normalizer import LemmaCache, batch_normalize_lemmas

    cache = LemmaCache(cache_path=tmp_path / "c.json")

    call_count = 0

    def side_effect(**kwargs: Any) -> MagicMock:
        nonlocal call_count
        call_count += 1
        prompt = kwargs.get("prompt_text", "")
        n = len([l for l in prompt.strip().splitlines() if l.strip()])
        r = MagicMock()
        # Return the input back as lemmas (identity mapping)
        r.raw_output = prompt
        r.usage = {"input_tokens": n, "output_tokens": n}
        return r

    client = MagicMock()
    client.create_page_response.side_effect = side_effect

    terms = [f"term{i}" for i in range(150)]
    result = batch_normalize_lemmas(
        terms,
        client=client,
        cache=cache,
        batch_size=100,
    )
    assert result.api_calls == 2
    assert len(result.mapping) == 150


def test_batch_deduplicates(tmp_path: Path) -> None:
    from legalpdf_translate.lemma_normalizer import LemmaCache, batch_normalize_lemmas

    cache = LemmaCache(cache_path=tmp_path / "c.json")
    client = _mock_client("arguido")

    result = batch_normalize_lemmas(
        ["arguidos", "Arguidos", "ARGUIDOS"],
        client=client,
        cache=cache,
    )
    # Only 1 unique term after casefolding
    assert result.cache_misses == 1
    assert result.api_calls == 1
    assert result.mapping["arguidos"] == "arguido"


def test_batch_response_mismatch(tmp_path: Path) -> None:
    """If response has wrong number of lines, batch fails gracefully."""
    from legalpdf_translate.lemma_normalizer import LemmaCache, batch_normalize_lemmas

    cache = LemmaCache(cache_path=tmp_path / "c.json")
    client = _mock_client("only_one_line")  # 2 terms but 1 response line

    result = batch_normalize_lemmas(
        ["arguidos", "sentenças"],
        client=client,
        cache=cache,
    )
    assert result.failures == 2
    assert result.fallback_to_surface is True


def test_batch_progress_callback(tmp_path: Path) -> None:
    from legalpdf_translate.lemma_normalizer import LemmaCache, batch_normalize_lemmas

    cache = LemmaCache(cache_path=tmp_path / "c.json")
    client = _mock_client("arguido")

    progress_calls: list[tuple[int, str]] = []

    def on_progress(pct: int, msg: str) -> None:
        progress_calls.append((pct, msg))

    batch_normalize_lemmas(
        ["arguidos"],
        client=client,
        cache=cache,
        progress_callback=on_progress,
    )
    # Should have at least a progress call and the final 100% call
    assert any(pct == 100 for pct, _ in progress_calls)


# ---------------------------------------------------------------------------
# PKG Pareto with lemma grouping
# ---------------------------------------------------------------------------


def _make_accumulator() -> Any:
    """Create a GlossaryDiagnosticsAccumulator with sample PKG data."""
    from legalpdf_translate.glossary_diagnostics import GlossaryDiagnosticsAccumulator

    acc = GlossaryDiagnosticsAccumulator(total_pages=4)
    # Simulate PKG stats: inflected forms of "arguido"
    with acc._lock:
        acc._pkg_stats["term_tf"] = {
            "arguido": 10,
            "arguidos": 5,
            "arguida": 3,
            "sentença": 8,
            "sentenças": 4,
            "tribunal": 20,
        }
        acc._pkg_stats["term_pages"] = {
            "arguido": {"0", "1", "2"},
            "arguidos": {"0", "1"},
            "arguida": {"2"},
            "sentença": {"0", "1"},
            "sentenças": {"1", "2"},
            "tribunal": {"0", "1", "2", "3"},
        }
        acc._pkg_token_counts = {0: 100, 1: 100, 2: 100, 3: 100}
    return acc


def test_pareto_lemma_groups_inflections() -> None:
    acc = _make_accumulator()
    mapping = {
        "arguido": "arguido",
        "arguidos": "arguido",
        "arguida": "arguido",
        "sentença": "sentença",
        "sentenças": "sentença",
        "tribunal": "tribunal",
    }
    acc.set_lemma_mapping(mapping)
    result = acc.finalize_pkg_pareto()

    assert result["lemma_mode"] is True
    # "arguido" should have TF = 10+5+3 = 18
    # "sentença" should have TF = 8+4 = 12
    # "tribunal" should have TF = 20
    # So unique grouped terms = 3
    assert result["lemma_grouped_unique_terms"] == 3
    assert result["surface_unique_terms"] == 6

    # Check the top candidate has correct aggregated TF
    candidates = result["suggested_pkg_candidates"]
    tf_by_term = {c["term"]: c["tf"] for c in candidates}
    assert tf_by_term["tribunal"] == 20
    assert tf_by_term["arguido"] == 18
    assert tf_by_term["sentença"] == 12

    # "arguido" should have surface forms listed
    arguido_entry = next(c for c in candidates if c["term"] == "arguido")
    assert "surface_forms" in arguido_entry
    assert set(arguido_entry["surface_forms"]) == {"arguido", "arguidos", "arguida"}


def test_pareto_lemma_mode_flag() -> None:
    acc = _make_accumulator()
    acc.set_lemma_mapping({"arguido": "arguido", "tribunal": "tribunal"})
    result = acc.finalize_pkg_pareto()
    assert result["lemma_mode"] is True


def test_pareto_no_lemma_unchanged() -> None:
    acc = _make_accumulator()
    result = acc.finalize_pkg_pareto()
    assert result["lemma_mode"] is False
    assert "lemma_grouped_unique_terms" not in result
    assert "surface_unique_terms" not in result
    # All 6 surface forms present
    assert result["unique_terms"] == 6


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def test_report_renders_lemma_section() -> None:
    """_render_glossary_diagnostics_markdown includes Lemma Normalization section."""
    from legalpdf_translate.run_report import _render_glossary_diagnostics_markdown

    gd: dict[str, Any] = {
        "lemma_summary": {
            "terms_total": 50,
            "cache_hits": 10,
            "api_calls": 1,
            "input_tokens": 200,
            "output_tokens": 100,
            "failures": 0,
            "fallback_to_surface": False,
            "wall_seconds": 1.5,
        }
    }
    lines: list[str] = []
    _render_glossary_diagnostics_markdown(lines, gd)
    text = "\n".join(lines)
    assert "### Lemma Normalization" in text
    assert "Terms processed: **50**" in text
    assert "Cache hits: **10**" in text
    assert "API calls: **1**" in text
    assert "Tokens: **200** in / **100** out" in text
    assert "Wall time: **1.5s**" in text
    assert "Warning" not in text  # No fallback warning


def test_report_lemma_fallback_warning() -> None:
    from legalpdf_translate.run_report import _render_glossary_diagnostics_markdown

    gd: dict[str, Any] = {
        "lemma_summary": {
            "terms_total": 10,
            "cache_hits": 0,
            "api_calls": 0,
            "failures": 10,
            "fallback_to_surface": True,
            "wall_seconds": 0.3,
        }
    }
    lines: list[str] = []
    _render_glossary_diagnostics_markdown(lines, gd)
    text = "\n".join(lines)
    assert "Warning" in text
    assert "surface forms only" in text


def test_report_pareto_shows_surface_forms() -> None:
    """PKG Pareto table in lemma mode includes Surface Forms column."""
    from legalpdf_translate.run_report import _render_glossary_diagnostics_markdown

    gd: dict[str, Any] = {
        "pkg_pareto": {
            "total_tokens": 400,
            "unique_terms": 3,
            "total_term_occurrences": 50,
            "top_20_pct_coverage": 0.5,
            "core80_terms": [],
            "suggested_pkg_candidates": [
                {"term": "arguido", "tf": 18, "df_pages": 3, "surface_forms": ["arguida", "arguido", "arguidos"]},
                {"term": "tribunal", "tf": 20, "df_pages": 4},
            ],
            "lemma_mode": True,
            "lemma_grouped_unique_terms": 3,
            "surface_unique_terms": 6,
        },
    }
    lines: list[str] = []
    _render_glossary_diagnostics_markdown(lines, gd)
    text = "\n".join(lines)
    assert "(Lemma-grouped)" in text
    assert "Surface Forms" in text
    assert "arguida, arguido, arguidos" in text
    assert "Surface unique terms: **6**" in text
    assert "Lemma-grouped unique terms: **3**" in text


def test_report_pareto_no_lemma_mode() -> None:
    """PKG Pareto table without lemma mode uses standard columns."""
    from legalpdf_translate.run_report import _render_glossary_diagnostics_markdown

    gd: dict[str, Any] = {
        "pkg_pareto": {
            "total_tokens": 400,
            "unique_terms": 6,
            "total_term_occurrences": 50,
            "top_20_pct_coverage": 0.5,
            "core80_terms": [],
            "suggested_pkg_candidates": [
                {"term": "tribunal", "tf": 20, "df_pages": 4},
            ],
            "lemma_mode": False,
        },
    }
    lines: list[str] = []
    _render_glossary_diagnostics_markdown(lines, gd)
    text = "\n".join(lines)
    assert "(Lemma-grouped)" not in text
    assert "Surface Forms" not in text
    assert "Unique terms (n-grams): **6**" in text
