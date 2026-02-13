# API_PROMPTS

## A. Where prompts live (paths + key functions/classes)
- Primary page prompt template: `src/legalpdf_translate/prompt_builder.py::build_page_prompt`.
- Formatting-only retry prompt template: `src/legalpdf_translate/prompt_builder.py::build_retry_prompt`.
- Prompt invocation per page and retry flow: `src/legalpdf_translate/workflow.py::TranslationWorkflow._process_page`.
- Optional glossary block append: `src/legalpdf_translate/workflow.py::TranslationWorkflow._append_glossary_prompt` and `src/legalpdf_translate/glossary.py::format_glossary_for_prompt`.
- API payload shape: `src/legalpdf_translate/openai_client.py::OpenAIResponsesClient.create_page_response`.
- System instructions loader: `src/legalpdf_translate/resources_loader.py::load_system_instructions`.
- System instruction files:
  - `resources/system_instructions_enfr.txt`
  - `resources/system_instructions_ar.txt`
- Compliance parser/validators used after model output:
  - `src/legalpdf_translate/validators.py::parse_code_block_output`
  - `src/legalpdf_translate/validators.py::validate_enfr`
  - `src/legalpdf_translate/validators.py::validate_ar`
  - `src/legalpdf_translate/output_normalize.py::normalize_output_text`

How to inspect in repo:
```powershell
rg -n "build_page_prompt|build_retry_prompt|create_page_response|_append_glossary_prompt|_process_page|load_system_instructions" src/legalpdf_translate
Get-Content src/legalpdf_translate/prompt_builder.py
Get-Content src/legalpdf_translate/openai_client.py
Get-Content src/legalpdf_translate/workflow.py
Get-Content resources/system_instructions_enfr.txt
Get-Content resources/system_instructions_ar.txt
```

System instructions safe summary:
- `resources/system_instructions_enfr.txt`: legal translation role + strict single code-block output + layout/ordering constraints.
- `resources/system_instructions_ar.txt`: legal Arabic role + strict token wrapping/RTL constraints + single code-block output.
- Very short excerpt (`resources/system_instructions_enfr.txt`): `Return ONLY the translation inside ONE plain-text code block.`
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

AR validator contract:
- `src/legalpdf_translate/validators.py::validate_ar` requires:
  - Non-empty output.
  - No unwrapped `[[` / `]]` tokens.
  - No Latin letters or digits outside wrapped tokens.

Normalization contract:
- `src/legalpdf_translate/output_normalize.py::normalize_output_text`:
  - normalizes line endings,
  - strips trailing spaces,
  - removes blank lines,
  - for AR, wraps existing `[[...]]` tokens with LRI/PDI via `wrap_existing_tokens_with_isolates(...)`.

## F. Retry template(s) (formatting-only retry, including “prior output” wrapper)
Template source: `src/legalpdf_translate/prompt_builder.py::build_retry_prompt`.

Retry prompt structure:
- Header line (formatting fix only):
  - `COMPLIANCE FIX ONLY: Re-emit the SAME content, fix formatting only, as ONE plain-text code block and NOTHING ELSE.`
- Wrapped prior output:
  - `<<<BEGIN PRIOR OUTPUT>>>`
  - `{PRIOR_OUTPUT}`
  - `<<<END PRIOR OUTPUT>>>`

Retry call behavior (workflow):
- Triggered from `src/legalpdf_translate/workflow.py::_process_page` when initial evaluation fails.
- Retry call uses same `instructions`, retry prompt text, medium/high policy-resolved effort, and **no image** (`image_data_url=None`).

## G. Placeholders dictionary (define every placeholder used, e.g. {PAGE_NUM}, {TOTAL_PAGES}, {SOURCE_TEXT}, {CONTEXT_TEXT}, {PRIOR_OUTPUT})
- `{TARGET_PREFIX}`: `EN` for English, `FR` for French, omitted for Arabic (`build_page_prompt` behavior).
- `{PAGE_NUM}`: current 1-based page number (`build_page_prompt` input).
- `{TOTAL_PAGES}`: total PDF page count (`build_page_prompt` input).
- `{SOURCE_TEXT}`: per-page extracted/selected source text passed to prompt builder.
- `{CONTEXT_TEXT}`: optional context text (file or inline) when provided.
- `{GLOSSARY_BLOCK}`: optional appended block from `format_glossary_for_prompt(...)` via `_append_glossary_prompt`.
- `{PRIOR_OUTPUT}`: first model output passed into `build_retry_prompt(...)`.
- `{SYSTEM_INSTRUCTIONS}`: loaded text from `load_system_instructions(...)`.
- `{EFFORT}`: reasoning effort passed to API call (`high`, `xhigh`, `medium`).
- `{IMAGE_DATA_URL}`: optional rendered image data URL.
- `{IMAGE_DETAIL}`: optional image detail (`low` or `high`) when image is attached.

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

### 6) Retry formatting-only prompt
```text
COMPLIANCE FIX ONLY: Re-emit the SAME content, fix formatting only, as ONE plain-text code block and NOTHING ELSE.
<<<BEGIN PRIOR OUTPUT>>>
{PRIOR_OUTPUT}
<<<END PRIOR OUTPUT>>>
```

### 7) API payload template (with optional image content object)
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
- Payload ordering/content types in `create_page_response(...)` (`input_text` first, optional `input_image` second).
- Compliance assumptions enforced by `parse_code_block_output`, `validate_enfr`, `validate_ar`, and `normalize_output_text`.
- System instruction file selection logic in `load_system_instructions(...)`.

Evaluation checklist for prompt edits:
```powershell
rg -n "build_page_prompt|build_retry_prompt|create_page_response|_append_glossary_prompt|parse_code_block_output|validate_enfr|validate_ar|normalize_output_text" src/legalpdf_translate
python -m pytest -q
python -m compileall src tests
```

Documentation sync rule:
- If prompt templates, system instructions, retry wrapper, or API payload shape changes, update:
  - `docs/assistant/API_PROMPTS.md` (this file),
  - `docs/assistant/APP_KNOWLEDGE.md` pointers,
  - `docs/assistant/CODEX_PROMPT_FACTORY.md` prompt-touch guidance.
