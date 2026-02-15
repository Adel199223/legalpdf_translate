# Glossary Builder Knowledge Pack

## A. Entry Points and Key Functions

### `src/legalpdf_translate/glossary_builder.py`

| Function | Line | Purpose |
|----------|------|---------|
| `create_builder_stats()` | 138 | Initialize empty stats accumulator (dict with `term_tf`, `term_pages`, `term_docs`, `term_doc_tf`, `term_header_hits`) |
| `update_builder_stats_from_page()` | 208 | Extract 1-4 word n-grams from page text, accumulate TF/DF stats |
| `build_lemma_grouped_stats()` | 148 | Group surface forms by lemma, promote highest-TF representative |
| `finalize_builder_suggestions()` | 269 | Filter candidates by thresholds, rank by score, return sorted suggestions |
| `compute_selection_delta()` | 334 | Compare surface vs lemma suggestion sets (set diff) |
| `compute_selection_metadata()` | 354 | Return filtering pipeline diagnostics dict |
| `mine_glossary_builder_suggestions()` | 413 | Single-call convenience: create stats + update from pages + finalize |
| `serialize_glossary_builder_suggestions()` | 440 | Convert suggestions to dict list for JSON |
| `build_glossary_builder_markdown()` | 457 | Format suggestions as markdown table |
| `suggestions_to_glossary_entries()` | 504 | Convert suggestions to `GlossaryEntry` objects for glossary import |

### Dataclasses

- **`GlossaryBuilderSuggestion`** (line 61): `source_term`, `target_lang`, `occurrences_doc` (max TF in any single doc), `occurrences_corpus` (total TF), `df_pages`, `df_docs`, `suggested_translation`, `confidence` (0.0-1.0), `recommended_scope` ("personal" or "project").
- **`SelectionDelta`** (line 74): `surface_only_terms`, `lemma_only_terms`, `unchanged_count`, `surface_count`, `lemma_count`, `affected` (bool).

## B. How Suggestions Are Computed

### 1. N-gram extraction (`update_builder_stats_from_page`)

For each page, text is tokenized into words. All 1-gram through 4-gram combinations are generated. Each n-gram passes through `_candidate_allowed()`:

- Single tokens < 3 chars are rejected (line 122)
- All-stopword phrases are rejected (line 124, `_STOPWORDS_PT` = 29 Portuguese words)
- Identifier-like terms are rejected via `_is_identifier_like()` (line 127):
  - Emails, URLs, IBANs, case IDs, dates, addresses
  - Terms with > 25% digits

### 2. TF/DF accumulation

For each passing n-gram the function increments:
- `term_tf[term]` — total term frequency
- `term_pages[term]` — set of `"{doc_id}#{page_number}"` keys
- `term_docs[term]` — set of doc_ids
- `term_doc_tf[term][doc_id]` — per-document frequency
- `term_header_hits[term]` — count if the line is header-like (> 60% uppercase and <= 90 chars)

### 3. Threshold filtering (`finalize_builder_suggestions`)

A candidate passes if **either**:
- `doc_max >= min_tf_per_doc` (default 5) — high frequency in a single document, **OR**
- `tf >= min_tf_corpus` (default 3) **AND** `df_docs >= min_df_docs` (default 2) — moderate frequency across multiple documents

### 4. Confidence scoring (`_confidence`, line 254)

```
raw = log1p(tf) * 0.45 + log1p(df_pages) * 0.30 + log1p(df_docs) * 0.20 + (0.05 if header_hits else 0.0)
confidence = clamp(raw / 3.2, 0.0, 1.0)
```

### 5. Ranking score (`_score`, line 264)

```
header_boost = 1.15 if header_hits > 0 else 1.0
score = tf * (1.0 + log1p(df_pages) + 0.5 * log1p(df_docs)) * header_boost
```

### 6. Sort order (line 317)

Descending score, then descending TF, then descending df_docs, then descending df_pages, then ascending casefold(term).

**Note:** The sort key uses `1 if item.recommended_scope == "project" else 0` as a proxy for header_hits in the _score call (line 323). This means "project"-scoped terms get a 1.15x header boost in sort ranking regardless of actual header hits.

### 7. Scope assignment (line 303)

- "project" if `df_docs >= min_df_docs` (appears in multiple documents)
- "personal" otherwise

## C. Lemma Grouping

### What it does

`build_lemma_grouped_stats()` takes surface-form stats and a `lemma_mapping` dict (`surface.casefold() -> lemma`), then:

1. Groups all surface forms that share the same lemma
2. Accumulates TF, pages, docs, and per-doc counts per lemma group
3. Promotes the highest-TF surface form as the representative for each group
4. Returns a new stats dict keyed by representative surface forms

### Where it's wired

- **Qt dialog**: `QtGlossaryBuilderDialog` has a "Enable lemma grouping" checkbox (line 498 in `tools_dialogs.py`) and an effort dropdown ("high"/"xhigh")
- **Worker**: `_GlossaryBuilderWorker.run()` calls `batch_normalize_lemmas()` (OpenAI API) if lemma is enabled, then calls `build_lemma_grouped_stats()` + `finalize_builder_suggestions()` on grouped stats, and `compute_selection_delta()` to compare surface vs lemma sets

### How it changes suggestions

- Inflections of the same word are merged (e.g., "acusação" + "acusações" -> one entry)
- The merged entry uses the highest-TF surface form as the representative
- Merged TF/DF may cause previously below-threshold terms to pass filters
- Previously passing terms may be replaced by their lemma group representative

## D. Diagnostics

### `src/legalpdf_translate/glossary_diagnostics.py`

`GlossaryDiagnosticsAccumulator` collects per-page data during a glossary builder run.

| Method | Purpose |
|--------|---------|
| `set_cg_entries()` | Store Consistency Glossary entries for matching |
| `set_lemma_mapping()` | Store lemma normalization mapping |
| `record_page_pkg_stats()` | Tokenize page and accumulate PKG frequency stats |
| `record_page_cg_matches()` | Count CG entries whose source_text appears in page |
| `record_page_coverage()` | Store per-page coverage record |
| `finalize_coverage_proof()` | Summarize pages processed / total |
| `finalize_pkg_pareto()` | 80/20 Pareto on PKG n-grams (supports lemma grouping) |
| `finalize_token_pareto()` | Pareto on unigram content tokens (stopword-filtered) |
| `finalize_cg_summary()` | CG coverage, ambiguity heuristics, never-matched entries |

### Events emitted (via `emit_diagnostics_events`)

1. `page_coverage_summary` — overall coverage proof
2. `pkg_token_stats_page` — per-page token counts (one per page)
3. `pkg_pareto_summary` — PKG n-gram Pareto analysis
4. `token_pareto_summary` — content token Pareto
5. `cg_load_summary` — CG entry count
6. `cg_apply_page` — per-page CG match records
7. `cg_ambiguous_pareto_summary` — ambiguity analysis
8. `cg_drift_candidates` — drift candidates (placeholder, currently empty)

These events are rendered in the run report by `src/legalpdf_translate/run_report.py::_render_glossary_diagnostics_markdown`.

## E. How to Change X

### Ranking formula

Edit `_score()` at line 264 in `glossary_builder.py`. The current formula weights TF most heavily. To give more weight to document frequency, increase the `0.5` multiplier on `log1p(df_docs)`.

### Threshold defaults

Edit the defaults in `finalize_builder_suggestions()` signature (line 269): `min_tf_per_doc=5`, `min_tf_corpus=3`, `min_df_docs=2`. These are also exposed in the Qt dialog and can be changed per-run.

### Deduplication / tie-breaking

The sort key at line 317 controls ordering. To add a new tie-breaker, append a field to the sort tuple. The alphabetical fallback (`item.source_term.casefold()`) ensures determinism.

### Lemma grouping representative

In `build_lemma_grouped_stats()` (line 148), the representative is chosen by highest TF. To change to longest surface form or most frequent in docs, edit the comparison at the `if counts > best_counts` block (line 181).

### N-gram size

The extraction loop at line 232 uses `range(1, 5)` for 1-4 word n-grams. Change the upper bound to include longer phrases.

### Confidence weights

Edit the weight constants in `_confidence()` at line 254: TF (0.45), df_pages (0.30), df_docs (0.20), header_boost (0.05). The normalizer divisor is 3.2.

## F. How to Test X

### Run existing tests

```bash
python -m pytest tests/test_glossary_builder.py tests/test_glossary_builder_lemma_selection.py tests/test_glossary_diagnostics.py tests/test_qt_glossary_builder_diagnostics.py -q
```

### Test suggestion ordering

`tests/test_glossary_builder.py::test_builder_thresholds_require_repetition_and_are_deterministic` verifies determinism. `tests/test_glossary_builder_ordering.py` (new) tests exact sort order by score, TF, df, and alphabetical tie-break.

### Test lemma grouping

`tests/test_glossary_builder_lemma_selection.py` has 10 tests covering: merge logic, unmatched preservation, per-doc TF merge, selection delta detection, metadata keys, and end-to-end flow.

### Test diagnostics

`tests/test_glossary_diagnostics.py` covers PKG Pareto, CG matching, ambiguity heuristics, token Pareto, and event emission.

### Add a new ordering test

Create a stats dict with known TF/DF values, finalize, and assert `[s.source_term for s in suggestions]` matches the expected order.
