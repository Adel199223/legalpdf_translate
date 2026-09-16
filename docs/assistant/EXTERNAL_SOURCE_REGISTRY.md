# External Source Registry

Purpose: record official primary sources used for material external behavior/capability decisions.

## Current ordinary FR proposal reference — 2026-09-16

The parent task rechecked the official pages below on 2026-09-16. These public facts inform a provisional, test-instrumented two-call proposal; they do not prove account access, authorize dispatch or promote a default. Earlier dated records remain historical evidence.

| source_url | contract_or_workflow | fact_summary | verification_date |
|---|---|---|---|
| https://developers.openai.com/api/docs/models/gpt-5.6-terra | Ordinary FR proposal; explicit model/effort | Terra supports high and xhigh reasoning. Published short-context standard USD/million: input 2, cached input 0.20, output 12. The proposed run explicitly selects high; assistant model choice is separate. | 2026-09-16 |
| https://developers.openai.com/api/docs/pricing | Ordinary FR proposal; conservative per-call reservation | Short-context cache-write input is 2.50 USD/million. Long-context input/cached/cache-write/output rates are 4/0.40/5/18. For the selected short-context default-tier bound, 50,000 input at 2.50 plus 24,000 inclusive output at 12 gives 0.413 USD per call and 0.826 USD for two calls; this is a reservation bound, not a measured bill. | 2026-09-16 |
| https://developers.openai.com/api/docs/guides/reasoning | Ordinary FR proposal; inclusive output and settlement | The output budget includes reasoning and visible output. Incomplete responses can still incur output charges; missing visible text does not imply zero cost. | 2026-09-16 |

## Paid AR4 approval-time public recheck — 2026-09-11 UTC

Official GPT-5.2 model and Python Responses-create pages were opened again before
the exact approved AR4 launch. USD/million1.75 input/0.175 cached/14 output and
standard default-tier facts still matched the frozen proposal. No account/key
probe or private query was used; model/defaults were unchanged. The subsequent
local BootstrapDenied stop is not provider availability or pricing evidence.
See the private paid_execution_ar4_20260911_01/public_facts_recheck.json record.

## Fields
- `source_url`: official source link
- `contract_or_workflow`: policy/workflow impacted
- `fact_summary`: concise verified fact used for decisions
- `verification_date`: date the source was checked (`YYYY-MM-DD`)

## Entries
| source_url | contract_or_workflow | fact_summary | verification_date |
|---|---|---|---|
| https://developers.openai.com/api/docs/guides/structured-outputs | `TRANSLATION_WORKFLOW.md`, structured-new-translations ExecPlan | Responses `text.format` supports JSON-schema output; refusal and incomplete responses require separate handling. Schema conformity does not establish source-block coverage or legal equivalence. No model/account or live-call acceptance is inferred. | 2026-09-09 |
| https://developers.openai.com/api/reference/resources/responses/methods/create | `openai_docs_citation_freshness_policy`, `OPENAI_DOCS_CITATION_WORKFLOW.md` | Responses API `POST /responses` is the canonical create-response endpoint and supports model response creation with tools and structured outputs. | 2026-03-05 |
| https://developers.openai.com/api/docs/guides/batch | `cloud_heavy_scoring_default_policy`, `CLOUD_MACHINE_EVALUATION_WORKFLOW.md` | Batch API supports asynchronous grouped requests and is positioned for non-immediate workloads with separate batch limits/pool behavior. | 2026-03-05 |
| https://playwright.dev/docs/chrome-extensions | `browser_automation_reliability_policy`, `BROWSER_AUTOMATION_ENV_PROVENANCE_WORKFLOW.md` | Chrome extension testing requires Chromium with persistent context; side-load flags are not available in Chrome/Edge as described. | 2026-03-05 |
| https://playwright.dev/docs/browsers | `browser_binary_strategy_policy`, `chromium_for_testing_conditional_install_policy` | Playwright versions depend on matching browser binaries and `npx playwright install` is the canonical install path. | 2026-03-05 |
| https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts | `restricted_browser_page_policy`, `machine_operator_split_validation_policy` | Content scripts run in page context with isolated worlds and extension/page boundary constraints. | 2026-03-05 |
| https://developer.chrome.com/blog/chrome-for-testing/ | `browser_binary_strategy_policy`, `automation_binary_provenance_packet_policy` | Chrome for Testing exists as a test-focused, versioned automation flavor to improve reproducibility versus auto-updating regular Chrome. | 2026-03-05 |
| https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch | `cloud_scoring_preflight_gate_policy`, `CLOUD_MACHINE_EVALUATION_WORKFLOW.md` | `workflow_dispatch` enables manual workflow triggers and input passing via API/CLI/UI on default-branch-resident workflow definitions. | 2026-03-05 |
| https://learn.microsoft.com/en-us/windows/wsl/tutorials/wsl-vscode | `workspace_provenance_lock_policy`, `BROWSER_AUTOMATION_ENV_PROVENANCE_WORKFLOW.md` | VS Code + WSL uses a split client/server model and supports opening WSL projects via `code .`, relevant to host/provenance controls. | 2026-03-05 |
| https://platform.openai.com/docs/guides/images-vision | `ocr_api_fallback_cost_policy`, `OPENAI_DOCS_CITATION_WORKFLOW.md` | Vision requests expose image-detail tradeoffs relevant to OCR fallback cost/latency planning for required-only paid fallback paths. | 2026-03-05 |

## Honorarios Native Export

Honorarios native-export sources checked during the 2026-09-07 repair:

| source_url | contract_or_workflow | fact_summary | verification_date |
|---|---|---|---|
| https://learn.microsoft.com/en-us/office/vba/api/word.documents.open | `HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md` | VBA documents read-only, no-MRU and hidden-open arguments; its optional tail differs from the PIA signature. | 2026-09-07 |
| https://learn.microsoft.com/en-us/dotnet/api/microsoft.office.interop.word.documents.open?view=word-pia | `HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md` | PIA Open has XMLTransform at position 16; use the common first twelve arguments for this PowerShell COM path. | 2026-09-07 |
| https://learn.microsoft.com/en-us/dotnet/api/microsoft.office.interop.word._document.exportasfixedformat?view=word-pia | `HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md` | FixedFormatExtClassPtr is optional and selects an alternate renderer; native export omits it while keeping explicit protection/export settings. | 2026-09-07 |

## Structured Ordinary-Use Readiness — 2026-09-10

Read-only official web fallback was used because the OpenAI docs connector was
unavailable. No connector/configuration change or provider call was made. These
are public reference facts, not account-tier verification or paid authority.

| source_url | contract_or_workflow | fact_summary | verification_date |
|---|---|---|---|
| https://developers.openai.com/api/docs/models/gpt-5.2 | Active structured ordinary-use ExecPlan; pricing provenance | Published standard USD/million: input 1.75, cached input 0.175, output 14; context 400,000 and max output 128,000. GPT-5.2 alias and 2025-12-11 snapshot are explicitly bound by the local policy. Actual tier, public API scope and USD must match; these model capacities are conservative ordinary bounds, not a small campaign allowance or permission to send. Local 30-day freshness expiry is our policy, not a provider promise; no model-default promotion. | 2026-09-10 |
| https://developers.openai.com/api/reference/cli/resources/responses/methods/create | Dispatch accounting and hard reservations | Omitted service tier uses auto/project policy; the response reports actual processing tier, which may differ from requested tier. Provider/model-only pricing cannot establish complete tier-sensitive cost. | 2026-09-10 |
| https://developers.openai.com/api/docs/guides/fast-mode | Tier-aware pricing and reservation readiness | Project policy can apply premium processing to omitted-tier requests; downgrade can return default and standard billing. Bound allowed tiers before hard-budget dispatch or block. | 2026-09-10 |
| https://developers.openai.com/api/docs/guides/reasoning | Inclusive usage and conservative output caps | Reasoning is billed as output; max_output_tokens includes visible and nonvisible generation. Incomplete responses can incur charges without visible output. | 2026-09-10 |
| https://developers.openai.com/api/docs/guides/images-vision | Future image/OCR request-bound evidence | GPT-5.2 image bounds use documented resolution/patch rules and token multipliers. No case-specific image-token bound, paid OCR route or permission is established by this reference alone. | 2026-09-10 |

## Freshness Rule

### V3 post-header-fix preparation refresh — 2026-09-11

Official web fallback was used after connector discovery found no usable OpenAI
docs tool. Both pages were opened and read; no private query data, account test,
credential resolution or provider request was used. No model/default promotion.

| source_url | contract_or_workflow | fact_summary | verification_date |
|---|---|---|---|
| https://developers.openai.com/api/docs/models/gpt-5.2 | V3 offline preparation and separate AR4 proposal | Reconfirmed GPT-5.2 standard USD/million: 1.75 input, 0.175 cached input, 14 output; context400000, model output128000, high effort and dated2025-12-11 alias. Keep existing24000 output cap; capacity arithmetic1.036/call,4.144/AR4,13.468/all13 is our conservative calculation, not measured cost or account availability. | 2026-09-11 |
| https://developers.openai.com/api/reference/python/resources/responses/methods/create | Frozen request tier/storage/output controls | Explicit default requests standard processing/pricing; actual returned tier may differ. Output-token ceiling includes reasoning and visible tokens. Existing prepared requests retain explicit store=False and default; no ordinary-model or tier-default change. | 2026-09-11 |

### Request preparation refresh — 2026-09-11

Official public web pages only; no private document information, key/account test
or provider request. Dates are Lisbon local (retrieval UTC date 2026-09-10).

| source_url | contract_or_workflow | fact_summary | verification_date |
|---|---|---|---|
| https://developers.openai.com/api/docs/models/gpt-5.2 | Structured acceptance request preparation | Rechecked GPT-5.2 rates: USD/million 1.75 input, 0.175 cached input, 14 output; 400000 context and 128000 model max output. Proposed reservation uses full input capacity plus existing 24000 output cap, with no cache discount assumption. No account/model availability or paid authority is established. | 2026-09-11 |
| https://developers.openai.com/api/reference/cli/resources/responses/methods/create | Exact request bounds and tier | Explicit default requests standard processing/pricing; actual returned tier can differ. max_output_tokens includes reasoning and visible output. Ordinary auto and store=false remain unchanged; only a separately approved acceptance policy may pin default. | 2026-09-11 |
| https://developers.openai.com/cookbook/examples/how_to_count_tokens_with_tiktoken | Conservative input reservation | Cookbook message counters are estimates and model/framing-dependent; this is not proof that local serialized bytes plus64 bounds complete GPT-5.2 Responses schema/framing. Use documented capacity fallback for the proposed pilot. | 2026-09-11 |
| https://developers.openai.com/api/reference/cli/resources/responses/subresources/input_tokens/methods/count | Unused future count alternative | Official reference exposes POST /responses/input_tokens. Existence alone establishes neither free billing nor request/count parity. Not invoked; no new auth/provider authority is inferred. | 2026-09-11 |

- If a decision depends on unstable facts (pricing, limits, schedules, product behavior), re-check sources and update `verification_date` before implementation or release decisions.

### Frozen-caller preparation refresh — 2026-09-11 UTC

Official model and Python Responses reference pages were fetched again for the
new offline caller/preparation packet. No private query, account check or paid
request; the existing key/model/effort/defaults are unchanged.

| source_url | contract_or_workflow | fact_summary | verification_date |
|---|---|---|---|
| https://developers.openai.com/api/docs/models/gpt-5.2 | Private frozen-caller capacity proposal | Reconfirmed USD/million 1.75 input, 0.175 cached input, 14 output, 400000 context, 128000 maximum output and high effort. Full-capacity input plus unchanged 24000 inclusive output reserves USD1.036 per call without cache discount; this is a conditional bound, not actual cost or account availability. | 2026-09-11 |
| https://developers.openai.com/api/reference/python/resources/responses/methods/create | Private exact-request and tier guards | Explicit default requests standard pricing; actual returned tier may differ and must be accounted. Output cap includes visible and reasoning tokens. Private requests retain store=false; no ordinary model/tier/default change. | 2026-09-11 |
