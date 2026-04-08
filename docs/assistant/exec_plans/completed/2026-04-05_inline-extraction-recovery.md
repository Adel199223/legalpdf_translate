# Inline Extraction Recovery for EN/FR Amount Loss

## Goal and non-goals
- Goal: detect inline EN/FR extraction defects where a visually present amount/value span is missing from extracted text, recover it through a low-cost visual path, and surface accurate risk/reporting when recovery is weak or unavailable.
- Non-goal: redesign the whole OCR advisor, replace the text-first pipeline for normal EN/FR pages, or introduce breaking output-schema changes.

## Scope (in/out)
- In:
  - EN/FR extraction-integrity detection in the translation workflow
  - targeted cropped visual recovery and merge path
  - forced image-grounded fallback for suspect pages
  - additive diagnostics, run-summary/run-report fields, and review-queue scoring
  - regression coverage for detector, routing, recovery fallback, and reporting
- Out:
  - broad Arabic workflow changes
  - full-page OCR replacement for all EN/FR pages
  - UI redesign work outside additive reporting surfacing

## Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- branch name: `feat/inline-extraction-recovery`
- base branch: `main`
- base SHA: `0683f529b9adf65b7ed44051376fa21f1d6fd0b4`
- target integration branch: `main`
- canonical build status: noncanonical feature branch on canonical worktree; approved-base floor satisfied (`4e9d20e`)

## Interfaces/types/contracts affected
- Additive page metadata only:
  - `extraction_integrity_suspect`
  - `extraction_integrity_reasons`
  - `vector_gap_count`
  - `visual_recovery_required`
  - `visual_recovery_strategy`
  - `visual_recovery_used`
  - `visual_recovery_failed`
- Additive run summary/report and event payload keys only; no breaking contract changes.

## File-by-file implementation steps
1. `src/legalpdf_translate/pdf_text_order.py`
   - extend ordered extraction metadata with block geometry needed to localize suspicious gaps without changing existing text output behavior.
2. `src/legalpdf_translate/ocr_helpers.py`
   - add a cropped page-render helper and OCR entrypoint for a rectangular suspect band.
3. `src/legalpdf_translate/workflow.py`
   - add EN/FR extraction-integrity detection after ordered extraction
   - route suspect pages into visual recovery
   - merge cropped OCR text when usable
   - force image-grounded translation fallback when cropped recovery is weak/unavailable
   - persist additive integrity/recovery metadata on the page payload
4. `src/legalpdf_translate/image_io.py`
   - allow suspect EN/FR pages to force image attachment while preserving normal text-first auto behavior for clean pages.
5. `src/legalpdf_translate/translation_diagnostics.py`
   - emit integrity-related diagnostic counters/flags alongside existing numeric/citation/structure checks.
6. `src/legalpdf_translate/workflow_components/quality_risk.py`
   - score EN/FR integrity suspicion and escalate suspect pages into the review queue.
7. `src/legalpdf_translate/workflow_components/ocr_advisor.py`
   - treat integrity-suspect pages as evidence that `ocr=off/image=off` is not stable.
8. `src/legalpdf_translate/run_report.py`
   - render integrity recovery/flagging in markdown and payload output.
9. `tests/*`
   - add focused regression coverage for detector behavior, workflow routing, recovery fallback, risk scoring, and run-report rendering.

## Tests and acceptance criteria
- Targeted tests:
  - workflow/routing tests for suspect EN/FR pages
  - translation diagnostics tests for integrity fields
  - quality-risk scoring tests for EN/FR suspect pages
  - run-report rendering tests for new integrity fields
- Acceptance:
  - a page matching `ascende a ... e três cêntimos)` with vector-gap evidence must not remain plain `direct_text_usable`
  - suspect page must use cropped recovery or image-grounded fallback
  - unresolved suspect page must appear in review/risk outputs
  - this PDF class must preserve the amount in the resulting French translation

## Rollout and fallback
- Keep the detector narrow and pattern-driven to avoid broad EN/FR cost regressions.
- If cropped recovery is weak, prefer multimodal grounding before accepting text-only translation.
- If both recovery paths fail, allow completion but with explicit risk/review surfacing instead of silent clean success.

## Risks and mitigations
- Risk: false positives increase OCR/image usage.
  - Mitigation: require both textual integrity cues and localized vector-gap evidence where possible.
- Risk: cropped OCR merge inserts noisy text.
  - Mitigation: apply acceptance checks before merge and fall back to image-grounded translation when merge confidence is weak.
- Risk: reporting schema drift.
  - Mitigation: additive keys only and compatibility tests for legacy report payloads.

## Assumptions/defaults
- Existing multimodal translation support remains the fallback grounding path.
- Cost/speed should stay unchanged for clean EN/FR pages.
- Immediate assistant-doc sync is deferred unless implementation finishes with touched-scope docs needing same-pass sync.
