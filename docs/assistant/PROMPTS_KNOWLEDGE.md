# Prompts Knowledge Pack

## A. Where Prompts Are Constructed

### `src/legalpdf_translate/prompt_builder.py`

| Function | Line | Purpose |
|----------|------|---------|
| `build_page_prompt()` | 8 | Assemble initial page translation prompt |
| `build_retry_prompt()` | 32 | Compliance-fix-only retry prompt |
| `build_language_retry_prompt()` | 54 | Language-correction-only retry prompt (PT leak removal) |

### Page prompt structure (`build_page_prompt`)

Sections are appended in this order:

1. **Language marker** (EN/FR only, not AR) — line 16
2. **Page marker** — `<<<PAGE {n} OF {total}>>>` — line 21
3. **Context block** (optional) — `<<<BEGIN CONTEXT>>>` / `<<<END CONTEXT>>>` — lines 22-25
4. **Source block** — `<<<BEGIN SOURCE>>>` / `<<<END SOURCE>>>` — lines 26-28

### Retry prompts

- `build_retry_prompt()` — header: `"COMPLIANCE FIX ONLY: Re-emit the SAME content, fix formatting only, as ONE plain-text code block and NOTHING ELSE."` + language hint (EN/FR) + `<<<BEGIN PRIOR OUTPUT>>>` wrapper
- `build_language_retry_prompt()` — header: `"LANGUAGE CORRECTION ONLY: Re-emit the SAME content, fix language compliance only, as ONE plain-text code block and NOTHING ELSE."` + language-specific correction instructions + same wrapper

### Markers / delimiters

| Marker | Used In |
|--------|---------|
| `EN` / `FR` | First line of page prompt (EN/FR only) |
| `<<<PAGE n OF total>>>` | Page prompt |
| `<<<BEGIN CONTEXT>>>` / `<<<END CONTEXT>>>` | Page prompt (optional) |
| `<<<BEGIN SOURCE>>>` / `<<<END SOURCE>>>` | Page prompt |
| `<<<BEGIN PRIOR OUTPUT>>>` / `<<<END PRIOR OUTPUT>>>` | Retry prompts |
| `<<<BEGIN GLOSSARY>>>` / `<<<END GLOSSARY>>>` | Appended by workflow (glossary block) |
| `<<<BEGIN ADDENDUM>>>` / `<<<END ADDENDUM>>>` | Appended by workflow (per-language addendum) |

## B. Where Prompts Are Called

### `src/legalpdf_translate/workflow.py`

In `_process_page()` (line ~1400):

1. `build_page_prompt()` — build base prompt from source text + optional context
2. `_append_glossary_prompt()` — append filtered/sorted/capped glossary entries
3. `_append_prompt_addendum()` — append per-language addendum text

Then the composed prompt is sent to the API alongside system instructions.

### Retry flow (line ~1602)

- If initial attempt fails with `"pt_language_leak"` reason → `build_language_retry_prompt()`
- Otherwise → `build_retry_prompt()` (formatting focused)

## C. System Instructions

### `src/legalpdf_translate/resources_loader.py`

`load_system_instructions(target_lang)` (line 28) loads a text file from `resources/`:

| Target Lang | File |
|-------------|------|
| EN | `resources/system_instructions_en.txt` |
| FR | `resources/system_instructions_fr.txt` |
| AR | `resources/system_instructions_ar.txt` |

Also available: `system_instructions_enfr.txt` (shared EN/FR base).

### Key instruction sections

**EN/FR**: ROLE, LANGUAGE LOCK, TASK, PDF ORDER FIX, WORD-COMPACT LAYOUT, LEGAL FIDELITY, ACRONYMS, TRANSLATE GENERIC LABELS, KEEP VERBATIM, DATES, ANTI-CALQUE, FINAL CHECK.

**AR**: ROLE, TASK, OUTPUT, PRIORITY RULES, BIDI/RTL STABILITY, TOKEN-LOCK (`⁦[[...]]⁩` wrapping), LIST ITEMS, CLAUSE ORDER, PDF ORDER FIX, WORD-COMPACT LAYOUT, WHAT MUST BE TRANSLATED vs KEPT VERBATIM, LEGAL QUALITY.

System instructions are loaded in `workflow.py` at line ~396 and stored in `self._system_instructions_text`.

## D. Glossary Injection

### Flow

`workflow._append_glossary_prompt()` (line 1740):

1. Get entries for target language from `self._prompt_glossaries_by_lang`
2. Detect source language in source text (`detect_source_lang_for_glossary()`)
3. Filter by source lang and enabled tiers (`filter_entries_for_prompt()`)
4. Sort entries (`sort_entries_for_prompt()`)
5. Cap: max 50 entries, max 6000 chars (`cap_entries_for_prompt()`)
6. Record diagnostics if accumulator present
7. Format via `format_glossary_for_prompt()` from `glossary.py` (line 758)

### Glossary block format (`glossary.py::format_glossary_for_prompt`)

```
<<<BEGIN GLOSSARY>>>
Target language: EN
Detected source language: PT
Use preferred translations exactly when source phrase matches.
Do not rewrite IDs, IBANs, case numbers, addresses, dates, or names.
Preserve capitalization style of the source phrase when applying glossary entries.
1. [T2][PT][exact] 'Tribunal' => 'court'
1a. [T2][PT][exact] 'Tribunal' => 'Court' (capitalized variant)
2. [T1][ANY][contains] 'another phrase' => 'another translation'
<<<END GLOSSARY>>>
```

> The `Preserve capitalization style …` instruction and `{N}a.` variant lines are
> emitted only for case-sensitive target languages (EN, FR). AR is caseless and
> skips them. A variant is added when the source starts uppercase but the target
> starts lowercase.

### Addendum

`workflow._append_prompt_addendum()` (line 1780) reads `self._prompt_addendum_by_lang` and appends:

```
<<<BEGIN ADDENDUM>>>
{user-configured text}
<<<END ADDENDUM>>>
```

## E. Output Validation

### `src/legalpdf_translate/validators.py`

| Function | Line | Validates |
|----------|------|-----------|
| `parse_code_block_output()` | 60 | Exactly 1 markdown code block; extracts inner content |
| `validate_enfr()` | 119 | EN/FR: not empty, no blank lines, no PT month/legal/institution leaks |
| `validate_ar()` | 154 | AR: not empty, all `[[...]]` wrapped with LRI/PDI, no Latin/digits outside tokens, expected token match |

### Validation pipeline (`workflow._evaluate_output`, line ~1793)

1. Parse code block → must be exactly 1
2. Normalize output (`output_normalize.normalize_output_text_with_stats()`)
3. Language-specific validation (EN/FR or AR)
4. Check for non-whitespace text outside code block

### `src/legalpdf_translate/output_normalize.py`

Normalization applied after code block extraction:

- Newline normalization (`\r\n` / `\r` → `\n`)
- Strip trailing spaces, remove blank lines
- **AR**: normalize PT month dates to Arabic, autofix bare expected tokens, wrap `[[...]]` with LRI/PDI isolates
- **EN/FR**: normalize PT month dates to English/French month names

### Retry reason classification (`workflow._retry_reason_from_evaluation`)

| Reason | Trigger |
|--------|---------|
| `"no_code_block"` | 0 code blocks |
| `"multi_code_block"` | > 1 code blocks |
| `"outside_text"` | Non-whitespace outside block |
| `"blank_lines"` | Blank lines in output |
| `"pt_language_leak"` | Portuguese terms leaked |
| `"ar_token_violation"` | Latin/digit/token wrapping issue |
| `"other"` | Anything else |

## F. How to Change X

### Page prompt structure

Edit `build_page_prompt()` in `prompt_builder.py` (line 8). Add new sections by appending to the `lines` list. Keep the marker convention (`<<<BEGIN X>>>` / `<<<END X>>>`).

### Retry prompt wording

Edit `build_retry_prompt()` (line 32) or `build_language_retry_prompt()` (line 54). The header string is the instruction to the model; the prior output block is always wrapped in markers.

### Glossary format in prompt

Edit `format_glossary_for_prompt()` in `glossary.py` (line 758). The entry format string is at line 779: `f"{index}. [T{tier}][{source_lang}][{match_mode}] '{source}' => '{target}'"`.

### Glossary caps

Edit the defaults in `_append_glossary_prompt()` (workflow.py, line 1756): `max_entries=50`, `max_chars=6000`.

### System instructions

Edit the text files under `resources/` directly. Changes take effect on next run.

### Add a new validator check

Add a check in `validate_enfr()` or `validate_ar()` in `validators.py`. Return `ValidationResult(ok=False, reason="description")` on failure.

## G. How to Test X

### Run existing tests

```bash
python -m pytest tests/test_prompt_builder.py tests/test_validators_enfr.py tests/test_validators_ar.py tests/test_codeblock_parser.py tests/test_output_normalize.py -q
```

### Prompt regression test

`tests/test_prompt_builder.py` has 7 tests verifying markers, language hints, and structure for EN/FR/AR. `tests/test_prompt_structure.py` (new) adds section ordering and glossary-conditional assertions.

### Validator tests

- `tests/test_validators_enfr.py` — empty output, blank lines, PT month/legal/institution leaks, address exemption
- `tests/test_validators_ar.py` — unwrapped tokens, Latin/digits, expected token counts
- `tests/test_codeblock_parser.py` — single/zero/multi block detection

### Add a new prompt test

Build a prompt with `build_page_prompt()`, split into lines, and assert section ordering (language marker before page marker before source block). Assert glossary block appears only when glossary entries are provided.
