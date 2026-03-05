# Gap Analysis and Opportunity Map

Verification date: 2026-03-05

## Capability Mapping (`already-have` | `partial` | `missing`)
| Capability Pattern (from benchmark apps) | Current LegalPDF Translate State |
|---|---|
| Deterministic per-document processing artifacts | `already-have` |
| Checkpoint/resume workflow safety | `already-have` |
| Per-page validation and retry reason diagnostics | `already-have` |
| Terminology glossary controls | `already-have` |
| Structured run diagnostics and stage timings | `already-have` |
| Cost estimation consistently populated in run outputs | `partial` |
| Cost accounting synced into business job log | `missing` |
| Pre-run budget cap with hard/soft guardrails | `missing` |
| Review queue for risk-prone pages | `missing` |
| Deterministic quality risk scoring | `missing` |
| Multi-document queue/batch runner (desktop local) | `missing` |
| Failed-page-only rerun route | `missing` |
| OCR/image recommendation assistant before run | `missing` |
| Run profile presets for different risk/speed postures | `missing` |
| One-click review export for legal QA handoff | `missing` |

## Prioritized Top-12 Opportunities
Priority order follows: quality -> reliability -> cost efficiency -> throughput.

1. Cost Guardrails with run budget cap and policy outcomes (`block|warn|allow`).
2. Auto Job-Log Sync from `run_summary`/`run_state` into `job_log.sqlite3` cost/token fields.
3. Quality Risk Scoring per page with deterministic, explainable rules.
4. Review Queue panel to triage pages flagged by risk score.
5. Failed-page-only rerun flow for targeted correction.
6. Multi-document desktop queue runner with checkpoint-aware execution.
7. Guided OCR/Image Advisor preflight (recommend `ocr_mode`/`image_mode` per file).
8. Profile presets: `Strict Legal`, `Balanced`, `Fast Safe`.
9. Review export package (`CSV + markdown` summary + page list).
10. High-latency page prediction from prior runs (early warning).
11. Cost profile IDs to preserve reproducible pricing assumptions.
12. Policy-level run acceptance gate (`quality_risk_score <= threshold` before business save).

## Selected Top-5 Implementation Candidates
Locked candidate set for specification stage:
1. Cost Guardrails
2. Review Queue + Quality Risk Scoring
3. Queue/Batch Runner (desktop-local)
4. Auto Job-Log Sync
5. Guided OCR/Image Advisor

## Gate
`NEXT_STAGE_4`
