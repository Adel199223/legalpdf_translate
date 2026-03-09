# Decision-Complete Specs: Top-5 Upgrades

Verification date: 2026-03-05

## Global Contract Rules
1. Preserve `TranslationWorkflow.run/analyze/rebuild_docx` signatures.
2. Additive schema only; existing artifacts remain parseable.
3. No breaking CLI flag changes; only additive flags.
4. Any unavailable dependency must return explicit `unavailable` semantics, not silent fallback.

## 1) Cost Guardrails

### Scope
- Add deterministic pre-run cost estimate and budget-cap outcome policy.

### Interface additions
- CLI:
  - `--budget-cap-usd <float>` (optional)
  - `--cost-profile-id <string>` (optional; default `default_local`)
- `run_summary.json` additive keys:
  - `cost_estimation_status`: `available|unavailable|failed`
  - `cost_profile_id`: string
  - `budget_cap_usd`: number or null
  - `budget_decision`: `allow|warn|block|n/a`
  - `budget_decision_reason`: string

### Behavior
1. Pre-run estimate uses expected page count and configured token heuristics.
2. If estimate unavailable: continue run, set `cost_estimation_status=unavailable`, `budget_decision=n/a`.
3. If estimate available and `budget_cap_usd` missing: `budget_decision=allow`.
4. If estimate available and exceeds cap:
   - CLI default: `warn` and continue.
   - GUI profile `Strict Legal`: `block` and require explicit user override action.
5. Post-run write actual estimate fields (if available) and variance against pre-run estimate.

### Rollback
- Remove additive keys and ignore unknown keys in readers (already required).

### Acceptance tests
1. Budget cap absent -> `allow` with non-error status.
2. Estimate unavailable -> status `unavailable`, no crash.
3. Estimate above cap + strict profile -> blocked before page processing.
4. Old summary without new keys still renders in run report.

## 2) Review Queue + Quality Risk Scoring

### Scope
- Deterministically flag pages that need manual review.

### Interface additions
- `run_summary.json` additive keys:
  - `quality_risk_score` (0-100)
  - `review_queue_count` (int)
  - `review_queue` (array of page records)
- Page record fields:
  - `page_number`, `risk_score`, `reasons[]`, `recommended_action`
- CLI:
  - `--review-export <path>` optional export destination.

### Behavior
1. Score each page from deterministic signals:
   - validation anomaly severity
   - retry usage
   - high reasoning-token outlier
   - extraction quality warning
   - OCR unavailable when helpful/required
2. Aggregate run score = weighted average of page scores with cap on one-page domination.
3. Queue threshold defaults:
   - page score >= 70 enters review queue.
4. Export, if requested, writes CSV + markdown summary.

### GUI UX
- New panel: `Review Queue` with sortable columns (`page`, `score`, `reason`, `open page text`).
- One-click copy/export of queue.

### Rollback
- If disabled, fields omitted; legacy reports remain unchanged.

### Acceptance tests
1. Deterministic replay of same input yields identical page risk scores.
2. Queue count equals number of pages above threshold.
3. Export path failure returns explicit warning and non-fatal run status.

## 3) Queue/Batch Runner (Desktop-Local)

### Scope
- Execute multiple run configs from local manifest with checkpoint-aware sequencing.

### Interface additions
- CLI:
  - `--queue-manifest <path>`: JSONL/JSON array of run jobs.
  - `--rerun-failed-only true|false` (queue mode only).
- New artifact:
  - `queue_summary.json` in selected output root.

### Behavior
1. Queue runner validates every job config before execution.
2. Execution modes:
   - default sequential (reliability-first).
   - optional bounded parallel per document (future flag, default off).
3. Crash-safe checkpoint:
   - queue state persisted after each job completion.
4. `rerun-failed-only=true` reruns only jobs/pages marked failed in prior queue summary.

### GUI UX
- Minimal first slice: import queue manifest and show status list (`pending|running|done|failed|skipped`).

### Rollback
- Queue mode isolated from single-run path; disable by omitting queue flags.

### Acceptance tests
1. Interrupt mid-queue then resume -> completed jobs are skipped deterministically.
2. Failed-only rerun executes only failed jobs/pages.
3. Queue summary remains valid JSON after abnormal termination.

## 4) Auto Job-Log Sync

### Scope
- Populate business job-log cost/token quality fields from run outputs.

### Schema additions (`job_runs`)
- `run_id` TEXT
- `target_lang` TEXT
- `total_tokens` INTEGER
- `estimated_api_cost` REAL
- `quality_risk_score` REAL

### Behavior
1. On successful translation run completion, seed Save-to-Job-Log dialog with run metrics.
2. User retains edit authority before final save.
3. If metric unavailable, store null and include reason note in UI.
4. Backfill not required in this phase.

### Rollback
- Additive columns; existing reads continue by column-presence checks.

### Acceptance tests
1. New columns added idempotently by migration path.
2. Save dialog pre-populates metrics from latest run summary.
3. Existing DB without migration still opens; migration applies automatically.

## 5) Guided OCR/Image Advisor

### Scope
- Recommend `ocr_mode` and `image_mode` before run based on extraction signals.

### Interface additions
- New analyze/preflight artifact key in `analyze_report.json`:
  - `recommended_ocr_mode`, `recommended_image_mode`, `recommendation_reasons[]`, `confidence`

### Behavior
1. Analyze sample pages before run start (bounded sample size).
2. Heuristics:
   - extraction char density
   - layout complexity markers
   - observed OCR-required/helpful rates
3. Recommendation policy:
   - return recommendation only; never force override.
4. User action captured in run metadata:
   - `advisor_recommendation_applied` boolean.

### GUI UX
- Pre-run banner: `Advisor suggests OCR=auto, Images=auto (confidence 0.82)` with Apply/Ignore actions.

### Rollback
- Advisor can be disabled globally; runtime falls back to current manual settings path.

### Acceptance tests
1. Advisor output exists for analyze-supported files and includes reasons.
2. Applying recommendation updates run config deterministically.
3. Ignoring recommendation leaves current settings unchanged.

## Cross-Feature Compatibility Tests
1. Legacy run artifacts parse without new keys.
2. New keys do not break `tests/test_run_report.py` rendering path.
3. Queue mode and single-run mode share same page-level validation/retry behavior.
4. Job-log sync tolerates null cost estimates.

## Gate
`NEXT_STAGE_5`
