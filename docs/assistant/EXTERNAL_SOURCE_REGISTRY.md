# External Source Registry

Purpose: record official primary sources used for material external behavior/capability decisions.

## Fields
- `source_url`: official source link
- `contract_or_workflow`: policy/workflow impacted
- `fact_summary`: concise verified fact used for decisions
- `verification_date`: date the source was checked (`YYYY-MM-DD`)

## Entries
| source_url | contract_or_workflow | fact_summary | verification_date |
|---|---|---|---|
| https://developers.openai.com/api/reference/resources/responses/methods/create | `openai_docs_citation_freshness_policy`, `OPENAI_DOCS_CITATION_WORKFLOW.md` | Responses API `POST /responses` is the canonical create-response endpoint and supports model response creation with tools and structured outputs. | 2026-03-05 |
| https://developers.openai.com/api/docs/guides/batch | `cloud_heavy_scoring_default_policy`, `CLOUD_MACHINE_EVALUATION_WORKFLOW.md` | Batch API supports asynchronous grouped requests and is positioned for non-immediate workloads with separate batch limits/pool behavior. | 2026-03-05 |
| https://playwright.dev/docs/chrome-extensions | `browser_automation_reliability_policy`, `BROWSER_AUTOMATION_ENV_PROVENANCE_WORKFLOW.md` | Chrome extension testing requires Chromium with persistent context; side-load flags are not available in Chrome/Edge as described. | 2026-03-05 |
| https://playwright.dev/docs/browsers | `browser_binary_strategy_policy`, `chromium_for_testing_conditional_install_policy` | Playwright versions depend on matching browser binaries and `npx playwright install` is the canonical install path. | 2026-03-05 |
| https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts | `restricted_browser_page_policy`, `machine_operator_split_validation_policy` | Content scripts run in page context with isolated worlds and extension/page boundary constraints. | 2026-03-05 |
| https://developer.chrome.com/blog/chrome-for-testing/ | `browser_binary_strategy_policy`, `automation_binary_provenance_packet_policy` | Chrome for Testing exists as a test-focused, versioned automation flavor to improve reproducibility versus auto-updating regular Chrome. | 2026-03-05 |
| https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch | `cloud_scoring_preflight_gate_policy`, `CLOUD_MACHINE_EVALUATION_WORKFLOW.md` | `workflow_dispatch` enables manual workflow triggers and input passing via API/CLI/UI on default-branch-resident workflow definitions. | 2026-03-05 |
| https://learn.microsoft.com/en-us/windows/wsl/tutorials/wsl-vscode | `workspace_provenance_lock_policy`, `BROWSER_AUTOMATION_ENV_PROVENANCE_WORKFLOW.md` | VS Code + WSL uses a split client/server model and supports opening WSL projects via `code .`, relevant to host/provenance controls. | 2026-03-05 |
| https://platform.openai.com/docs/guides/images-vision | `ocr_api_fallback_cost_policy`, `OPENAI_DOCS_CITATION_WORKFLOW.md` | Vision requests expose image-detail tradeoffs relevant to OCR fallback cost/latency planning for required-only paid fallback paths. | 2026-03-05 |

## Freshness Rule
- If a decision depends on unstable facts (pricing, limits, schedules, product behavior), re-check sources and update `verification_date` before implementation or release decisions.
