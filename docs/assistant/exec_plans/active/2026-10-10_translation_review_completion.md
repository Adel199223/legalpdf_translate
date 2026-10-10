# Translation review completion and fresh end-to-end acceptance

## Goal and non-goals
Fix every finding retained by the fresh Arabic Gmail retest: readable text beside graphics omitted from output, misleading citation/bidi warnings, missing ordinary text-correction approval, wrapped separator and source-footer placement. Then exercise the whole normal same-email Arabic workflow again. Minor source spacing may differ; content cannot be silently omitted. No mail sending, model-default changes, schema migration, history rewrite or unrelated cleanup.

## Scope and authority
The current user explicitly requests fixes plus another full test. Existing full development/publication/application authorization is retained; current normal Gmail/API/Word scope authorizes one fresh acceptance run and one unsent draft after code/fixture acceptance. The previous test and its calls are complete, not reusable operations. Technical stage checks are internal verification boundaries; current explicit end-to-end authorization supersedes historical continuation-token stops. Use stored response evidence for deterministic regressions before new paid work.

## Worktree provenance
- Integration worktree: C:/Users/FA507/.codex/worktrees/translation-review-completion/legalpdf_translate
- Branch: feat/translation-review-completion-20261010
- Base and target: main
- Base SHA: b30bdf8b649b43e4ee232f9c5ec3796e841a3c6c
- Approved floor: 4e9d20e, ancestry checked
- Canonical app remains main in C:/Users/FA507/.codex/legalpdf_translate; this feature worktree is noncanonical and may use only isolated shadow UI before promotion.
- Prior evidence: private gmail_arabic_retest_20261010_02/final_report_01.md and terminal_receipt_01.json.

## Interfaces and invariants
Introduce only necessary additive text-review routes/contracts. Preserve existing route IDs, request shapes, select values, Gmail/native-host/extension contracts and safe text insertion. Explicit text changes create owned immutable revisions with server-validated source/run/language association, base identity, before/after review and recalculated actual word counts. Formatting-only adoption stays strict. Source, original output, existing selected revisions, historical records/drafts and every-call accounting remain immutable/preserved. No arbitrary client paths or hashes become authority.

## File-by-file implementation
1. Inspect source-completeness/literal and prompt plumbing; preserve readable words and standalone identifiers beside graphics without case-specific insertion or inferring barcode payloads. Add a source-grounded visible review when completeness is unverified.
2. translation_diagnostics.py and quality-risk/presentation surfaces: compare user-visible target text after protocol decoding, retain real missing citations and unsafe/replacement/control issues, explain actionable findings.
3. ordinary layout/revision service, routes and browser review: explicit text correction editor/approval with source reference and change preview; owned immutable correction revision, recovery, delivery selection and formatting workflow. Allow additions/removals required for actual corrections; preserve safeguards rather than silently waiving text equality.
4. Automatic layout/writer: source-supported rule treatment and source/footer placement using native Word structure, while preserving meaningful underscores and exact legal text. Keep historical writer verification compatible.
5. Focused regression and DOM/API integration tests: normal paths, stale bases, wrong source/job, invalid document content, cancelled correction, no paid dispatch and source/accounting preservation.
6. Touched user guide, canonical architecture/handoff/validation and this plan: synchronize with exact final behavior. Preserve prior guidance/history as required.

## Tests and acceptance
- Retained failing specimen drives bounded regression; fictional EN/FR/AR examples prove changes are not hardcoded to the postal R or one language.
- Genuine browser correction shows before/after, refuses stale ownership, creates an immutable current revision, recalculates counts and survives reload/download/save/Gmail confirmation.
- An unchanged formatting-only Word edit remains adoptable; an unapproved text edit remains visibly pending instead of lost or silently adopted.
- Review every affected native Word page, including one longer/footer example and mixed-script identifiers; no graphics, clipping, overlapping footers or duplicated page numbers.
- Targeted suites, standard validation and selected Full in isolated environment; exact final-head hosted checks before merge/application.
- Canonical fresh same-email intake through Arabic translation, explicit content correction if needed, native Word/manual RTL finishing, normal download, one saved record, correct fees and one unsent draft. Verify actual attachment bytes, old row/file/draft preservation and owned cleanup.
- Completion requires all five findings addressed and whole normal process verified; fixture-only success is insufficient.

## Rollout and fallback
Use isolated worker branches from the same base. Review/cherry-pick bounded commits into integration. Preserve live baseline before installation, stop only owned LegalPDF server when necessary, apply accepted main after hosted checks and restart canonical runtime. Retain previous outputs/drafts. Do not reset data, bypass uncertainty, replay consumed calls, or weaken safeguards to force a green result.

## Risks and mitigations
Text correction can invalidate source maps and charges: keep revision lineage and maps explicit and costs unchanged. Footer changes can relocate legal content: require source ownership and multi-page checks. Completeness from images is uncertain: honest review evidence, no invented text. Intermediate protocol controls can mislead diagnostics: decode established protocol only and test true controls separately.

## Assumptions and current status
Arabic remains the test target; assistant Astra/GPT-6.1 Sol routing is separate from app models. Existing manual RTL/right alignment remains acceptable. No new feature implementation at plan creation. Astra is analyzing design; workers will own disjoint isolated scopes. No provider/native/Gmail operation has begun for this new goal.
