# API_PROMPTS

## A. Where prompts live (paths + key functions/classes)
- Primary page prompt template: `src/legalpdf_translate/prompt_builder.py::build_page_prompt`.
- Formatting-only retry prompt template: `src/legalpdf_translate/prompt_builder.py::build_retry_prompt`.
- Prompt invocation per page and retry flow: `src/legalpdf_translate/workflow.py::TranslationWorkflow._process_page`.
- Optional glossary block append: `src/legalpdf_translate/workflow.py::TranslationWorkflow._append_glossary_prompt` and `src/legalpdf_translate/glossary.py::format_glossary_for_prompt`.
- Optional addendum append: `src/legalpdf_translate/workflow.py::TranslationWorkflow._append_prompt_addendum`.
- API payload shape: `src/legalpdf_translate/openai_client.py::OpenAIResponsesClient.create_page_response`.
- Calibration verifier prompts: `src/legalpdf_translate/calibration_audit.py::_verifier_prompt`, `_verifier_retry_prompt`, `_call_verifier_with_retries`.
- System instructions loader: `src/legalpdf_translate/resources_loader.py::load_system_instructions`.
- System instruction files:
  - `resources/system_instructions_en.txt`
  - `resources/system_instructions_fr.txt`
  - `resources/system_instructions_ar.txt`
- Compliance parser/validators used after model output:
  - `src/legalpdf_translate/validators.py::parse_code_block_output`
  - `src/legalpdf_translate/validators.py::validate_enfr`
- `src/legalpdf_translate/validators.py::validate_ar`
- `src/legalpdf_translate/output_normalize.py::normalize_output_text`
- `src/legalpdf_translate/arabic_pre_tokenize.py::pretokenize_arabic_source`
- `src/legalpdf_translate/arabic_pre_tokenize.py::extract_locked_tokens`
- `src/legalpdf_translate/arabic_pre_tokenize.py::is_portuguese_month_date_token`

How to inspect in repo:
```powershell
rg -n "build_page_prompt|build_retry_prompt|create_page_response|_append_glossary_prompt|_append_prompt_addendum|_process_page|_verifier_prompt|_verifier_retry_prompt|load_system_instructions" src/legalpdf_translate
Get-Content src/legalpdf_translate/prompt_builder.py
Get-Content src/legalpdf_translate/openai_client.py
Get-Content src/legalpdf_translate/workflow.py
Get-Content resources/system_instructions_en.txt
Get-Content resources/system_instructions_fr.txt
Get-Content resources/system_instructions_ar.txt
```

System instructions safe summary:
- `resources/system_instructions_en.txt`: legal-English-only instruction set + strict single code-block output + layout/ordering constraints.
- `resources/system_instructions_fr.txt`: legal-French-only instruction set + strict single code-block output + layout/ordering constraints.
- `resources/system_instructions_ar.txt`: legal Arabic role + strict token wrapping/RTL constraints + single code-block output.
- `resources/system_instructions_ar.txt` naming policy: translate full institution/court/prosecution names when a stable Arabic equivalent exists; keep Portuguese original only when uncertain/no stable equivalent; dual first mention is for acronyms only.
- Very short excerpt (`resources/system_instructions_en.txt`): `Return ONLY the English translation inside ONE plain-text code block.`
- Very short excerpt (`resources/system_instructions_fr.txt`): `Retourner UNIQUEMENT la traduction francaise dans UN seul bloc de code texte brut.`
- Very short excerpt (`resources/system_instructions_ar.txt`): `Return ONLY the Arabic translation inside ONE plain-text code block.`

## B. Primary request template (per language: EN, FR, AR)
Source of truth: `src/legalpdf_translate/prompt_builder.py::build_page_prompt`.

Template behavior:
- For `EN` target (`TargetLang.EN`), first line is `EN`.
- For `FR` target (`TargetLang.FR`), first line is `FR`.
- For `AR` target (`TargetLang.AR`), no language prefix line is added.
- Then page marker line is always added:
  - `<<<PAGE {PAGE_NUM} OF {TOTAL_PAGES}>>>`
- Context block is optional (only if context text exists).
- Source block is always present:
  - `<<<BEGIN SOURCE>>>`
  - `{SOURCE_TEXT}`
  - `<<<END SOURCE>>>`

Call path:
- Built in `build_page_prompt(...)`, then used in `src/legalpdf_translate/workflow.py::TranslationWorkflow._process_page`.
- Final page request ordering in workflow is:
  1. base prompt from `build_page_prompt(...)`
  2. optional glossary append (`_append_glossary_prompt`)
  3. optional addendum append (`_append_prompt_addendum`)

## C. Optional context template (how it is injected, delimiters/markers)
Source of truth: `src/legalpdf_translate/prompt_builder.py::build_page_prompt`.

Injection rule:
- Context is included only when `context_text` is truthy in `build_page_prompt(...)`.
- Delimiters are exact:
  - `<<<BEGIN CONTEXT>>>`
  - `{CONTEXT_TEXT}`
  - `<<<END CONTEXT>>>`

Ordering:
- Page marker appears before context block.
- Context block appears before source block.

## D. Image attachment template (when included, how referenced, what remains in text)
Image decision and rendering:
- Decision logic: `src/legalpdf_translate/workflow.py::_process_page` with `src/legalpdf_translate/image_io.py::should_include_image`.
- Image rendering to data URL: `src/legalpdf_translate/image_io.py::render_page_image_data_url`.

API payload shape:
- Built in `src/legalpdf_translate/openai_client.py::OpenAIResponsesClient.create_page_response`.
- `content` list ordering is exact:
  1. `{"type": "input_text", "text": prompt_text}`
  2. Optional `{"type": "input_image", "image_url": image_data_url, "detail": image_detail}` (only when `image_data_url` exists)
- `input` payload sent as:
  - `[{"role": "user", "content": content}]`

What remains in text:
- Prompt text still contains the same delimiters/template from `build_page_prompt(...)`.
- Image is attached as a separate `input_image` content item, not embedded in prompt text.

## E. Compliance/format contract (code block rules, blank lines rules, token rules if any)
Parser contract:
- `src/legalpdf_translate/validators.py::parse_code_block_output` requires exactly one code block.
- Non-whitespace text outside the single code block is considered non-compliant.

EN/FR validator contract:
- `src/legalpdf_translate/validators.py::validate_enfr` requires:
  - Non-empty output.
  - No blank lines.
  - When called with `lang=EN|FR`, rejects remaining Portuguese month-name date leaks after normalization.
  - Date-leak check is context-aware and skips likely address lines (e.g., `Rua 1.º de Dezembro ...`).

AR validator contract:
- `src/legalpdf_translate/validators.py::validate_ar` requires:
  - Non-empty output.
  - No unwrapped `[[` / `]]` tokens.
  - No Latin letters or digits outside wrapped tokens.
  - If `expected_tokens` are provided, every locked token must be preserved with matching multiplicity (missing/altered token mismatch fails validation).

Normalization contract:
- `src/legalpdf_translate/output_normalize.py::normalize_output_text`:
  - normalizes line endings,
  - strips trailing spaces,
  - removes blank lines,
  - for EN/FR, deterministically converts Portuguese month-name dates to target-language month names while preserving day-month-year order:
    - with year: `10 de fevereiro de 2026` -> `10 February 2026` / `10 février 2026`,
    - without year: `20 de Março às 11:30` -> `20 March às 11:30` / `20 mars às 11:30`,
  - for EN/FR, slash numeric dates remain unchanged (e.g., `09/02/2026`),
  - for AR, deterministically normalizes Portuguese month-name dates to Arabic month + tokenized day/year (`[[DD]] <ArabicMonth> [[YYYY]]`) via `normalize_ar_portuguese_month_dates(...)`,
  - for AR month-name date parsing uncertainty, falls back to one protected token (`[[...]]`) to preserve LTR stability,
  - for AR, applies deterministic expected-token auto-fix (when expected token list is provided),
  - then wraps existing `[[...]]` tokens with LRI/PDI via `wrap_existing_tokens_with_isolates(...)`.

AR source-token lock contract:
- `src/legalpdf_translate/workflow.py::_process_page` pretokenizes Arabic source text via `pretokenize_arabic_source(...)`.
- Locked source tokens are extracted with `extract_locked_tokens(...)`.
- Portuguese month-name date tokens are classified by `is_portuguese_month_date_token(...)` and excluded from strict expected-token matching.
- The filtered expected token list is enforced in both initial and retry output evaluation.

## F. Retry template(s) (formatting-only retry, including “prior output” wrapper)
Template source (translation compliance retry): `src/legalpdf_translate/prompt_builder.py::build_retry_prompt`.

Retry prompt structure:
- Header line (formatting fix only):
  - EN: `COMPLIANCE FIX ONLY: Re-emit the SAME content, fix formatting only, as ONE plain-text code block and NOTHING ELSE. Keep the output strictly in English.`
  - FR: `COMPLIANCE FIX ONLY: Re-emit the SAME content, fix formatting only, as ONE plain-text code block and NOTHING ELSE. Keep the output strictly in French.`
  - AR: `COMPLIANCE FIX ONLY: Re-emit the SAME content, fix formatting only, as ONE plain-text code block and NOTHING ELSE.`
- Wrapped prior output:
  - `<<<BEGIN PRIOR OUTPUT>>>`
  - `{PRIOR_OUTPUT}`
  - `<<<END PRIOR OUTPUT>>>`

Retry call behavior (workflow):
- Triggered from `src/legalpdf_translate/workflow.py::_process_page` when initial evaluation fails.
- Retry call uses same `instructions`, retry prompt text, medium/high policy-resolved effort, and **no image** (`image_data_url=None`).

Calibration verifier JSON retry:
- Source: `src/legalpdf_translate/calibration_audit.py::_verifier_retry_prompt`.
- Trigger path: `src/legalpdf_translate/calibration_audit.py::_call_verifier_with_retries`.
- Header line is:
  - `FORMAT FIX ONLY: Re-emit as valid JSON only matching the required schema. No markdown.`
- Wrapped prior output markers are exact:
  - `<<<BEGIN PRIOR OUTPUT>>>`
  - `{PRIOR_OUTPUT}`
  - `<<<END PRIOR OUTPUT>>>`
- Retry limit: up to 2 retries after the first verifier attempt (3 total attempts).

## G. Placeholders dictionary (define every placeholder used, e.g. {PAGE_NUM}, {TOTAL_PAGES}, {SOURCE_TEXT}, {CONTEXT_TEXT}, {PRIOR_OUTPUT})
- `{TARGET_PREFIX}`: `EN` for English, `FR` for French, omitted for Arabic (`build_page_prompt` behavior).
- `{PAGE_NUM}`: current 1-based page number (`build_page_prompt` input).
- `{TOTAL_PAGES}`: total PDF page count (`build_page_prompt` input).
- `{SOURCE_TEXT}`: per-page extracted/selected source text passed to prompt builder.
- `{CONTEXT_TEXT}`: optional context text (file or inline) when provided.
- `{GLOSSARY_BLOCK}`: optional appended block from `format_glossary_for_prompt(...)` via `_append_glossary_prompt`.
- `{ADDENDUM_TEXT}`: optional per-language addendum from settings key `prompt_addendum_by_lang` appended by `_append_prompt_addendum`.
- `{PRIOR_OUTPUT}`: first model output passed into `build_retry_prompt(...)`.
- `{LANGUAGE_HINT_OPTIONAL}`: EN adds ` Keep the output strictly in English.`; FR adds ` Keep the output strictly in French.`; AR adds empty suffix.
- `{SYSTEM_INSTRUCTIONS}`: loaded text from `load_system_instructions(...)`.
- `{EFFORT}`: reasoning effort passed to API call (`high`, `xhigh`, `medium`).
- `{IMAGE_DATA_URL}`: optional rendered image data URL.
- `{IMAGE_DETAIL}`: optional image detail (`low` or `high`) when image is attached.
- `{EXTRACTED_SOURCE}`: extracted page text passed to calibration verifier prompt.
- `{FORCED_OCR_SOURCE}`: forced-OCR page text passed to calibration verifier prompt.
- `{TRANSLATED_OUTPUT}`: evaluated translation text passed to calibration verifier prompt.
- `{ADDENDUM_CONTEXT}`: addendum text included in verifier context block.

## H. Copy/paste prompt blocks (one block per scenario) — TEMPLATE ONLY, with placeholders

### 1) Primary EN (text-only)
```text
EN
<<<PAGE {PAGE_NUM} OF {TOTAL_PAGES}>>>
<<<BEGIN SOURCE>>>
{SOURCE_TEXT}
<<<END SOURCE>>>
```

### 2) Primary FR (text-only)
```text
FR
<<<PAGE {PAGE_NUM} OF {TOTAL_PAGES}>>>
<<<BEGIN SOURCE>>>
{SOURCE_TEXT}
<<<END SOURCE>>>
```

### 3) Primary AR (text-only)
```text
<<<PAGE {PAGE_NUM} OF {TOTAL_PAGES}>>>
<<<BEGIN SOURCE>>>
{SOURCE_TEXT}
<<<END SOURCE>>>
```

### 4) Primary with optional context
```text
{TARGET_PREFIX_OPTIONAL}
<<<PAGE {PAGE_NUM} OF {TOTAL_PAGES}>>>
<<<BEGIN CONTEXT>>>
{CONTEXT_TEXT}
<<<END CONTEXT>>>
<<<BEGIN SOURCE>>>
{SOURCE_TEXT}
<<<END SOURCE>>>
```

### 5) Primary with glossary block appended
```text
{PRIMARY_PROMPT_TEMPLATE_FROM_ABOVE}
<<<BEGIN GLOSSARY>>>
{GLOSSARY_LINES}
<<<END GLOSSARY>>>
```

### 6) Primary with glossary + addendum appended
```text
{PRIMARY_PROMPT_TEMPLATE_FROM_ABOVE}
<<<BEGIN GLOSSARY>>>
{GLOSSARY_LINES}
<<<END GLOSSARY>>>
<<<BEGIN ADDENDUM>>>
{ADDENDUM_TEXT}
<<<END ADDENDUM>>>
```

### 7) Retry formatting-only prompt
```text
COMPLIANCE FIX ONLY: Re-emit the SAME content, fix formatting only, as ONE plain-text code block and NOTHING ELSE.{LANGUAGE_HINT_OPTIONAL}
<<<BEGIN PRIOR OUTPUT>>>
{PRIOR_OUTPUT}
<<<END PRIOR OUTPUT>>>
```

### 8) Calibration verifier prompt (JSON-only contract)
```text
You are a legal translation verifier.
Return JSON only. No markdown, no prose outside JSON.
{VERIFIER_SCHEMA_TEXT}
Page: {PAGE_NUM}
Target language: {TARGET_LANG}
<<<BEGIN EXTRACTED SOURCE>>>
{EXTRACTED_SOURCE}
<<<END EXTRACTED SOURCE>>>
<<<BEGIN FORCED OCR SOURCE>>>
{FORCED_OCR_SOURCE}
<<<END FORCED OCR SOURCE>>>
<<<BEGIN TRANSLATED OUTPUT>>>
{TRANSLATED_OUTPUT}
<<<END TRANSLATED OUTPUT>>>
<<<BEGIN GLOSSARY CONTEXT>>>
{GLOSSARY_BLOCK_OR_NONE}
<<<END GLOSSARY CONTEXT>>>
<<<BEGIN ADDENDUM CONTEXT>>>
{ADDENDUM_CONTEXT}
<<<END ADDENDUM CONTEXT>>>
```

### 9) Calibration verifier retry prompt
```text
FORMAT FIX ONLY: Re-emit as valid JSON only matching the required schema. No markdown.
<<<BEGIN PRIOR OUTPUT>>>
{PRIOR_OUTPUT}
<<<END PRIOR OUTPUT>>>
```

### 10) API payload template (with optional image content object)
```text
responses.create(
  model={OPENAI_MODEL},
  instructions={SYSTEM_INSTRUCTIONS},
  input=[
    {
      "role": "user",
      "content": [
        {"type": "input_text", "text": {PROMPT_TEXT}},
        {"type": "input_image", "image_url": {IMAGE_DATA_URL}, "detail": {IMAGE_DETAIL}}  # optional
      ]
    }
  ],
  reasoning={"effort": {EFFORT}},
  store={OPENAI_STORE},
  timeout={TIMEOUT_SECONDS}
)
```

## I. Prompt-change safety rules (what must not change; how to evaluate changes)
Do not change without coordinated code + docs updates:
- Prompt delimiters and ordering in `build_page_prompt(...)` (`<<<PAGE...>>>`, context markers, source markers).
- Retry wrapper markers/header in `build_retry_prompt(...)`.
- Addendum markers/order in `_append_prompt_addendum` (`<<<BEGIN ADDENDUM>>> ... <<<END ADDENDUM>>>`).
- Calibration verifier JSON prompt/retry wrappers in `_verifier_prompt` / `_verifier_retry_prompt`.
- Payload ordering/content types in `create_page_response(...)` (`input_text` first, optional `input_image` second).
- Compliance assumptions enforced by `parse_code_block_output`, `validate_enfr`, `validate_ar`, and `normalize_output_text`.
- System instruction file selection logic in `load_system_instructions(...)`.

Evaluation checklist for prompt edits:
```powershell
rg -n "build_page_prompt|build_retry_prompt|create_page_response|_append_glossary_prompt|_append_prompt_addendum|_verifier_prompt|_verifier_retry_prompt|parse_code_block_output|validate_enfr|validate_ar|normalize_output_text" src/legalpdf_translate
python -m pytest -q
python -m compileall src tests
```

Documentation sync rule:
- If prompt templates, system instructions, retry wrapper, or API payload shape changes, update:
  - `docs/assistant/API_PROMPTS.md` (this file),
  - `docs/assistant/APP_KNOWLEDGE.md` pointers,
  - `docs/assistant/CODEX_PROMPT_FACTORY.md` prompt-touch guidance.
