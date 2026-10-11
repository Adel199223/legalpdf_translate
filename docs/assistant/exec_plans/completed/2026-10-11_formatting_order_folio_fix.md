# Focused automatic formatting and source-folio repair

## Goal and non-goals
Fix the October 11 generated column-order rejection and duplicate generated page number, then repeat one normal Arabic Gmail workflow. Accept minor wording/spacing differences. No model changes, broad redesign, cosmetic repair loop, unrelated code, or email sending.

## Scope
Generated layout normalization may conservatively recover an otherwise complete metadata band while retaining exact paragraph order and text. Fresh primary output must avoid redundant generated numbering when source folios cover the selected pages. Historical artifacts and strict manual validation remain supported.

## Worktree provenance
- Worktree: `C:/Users/FA507/.codex/worktrees/formatting-order-folio-fix/legalpdf_translate`
- Branch: `feat/formatting-order-folio-fix-20261011`
- Base/target: canonical `main`, base `6bb590a8cb18901ae6fb67bd521a1ef4ff8f50a1`
- Implementation is noncanonical; live Gmail acceptance occurs only after canonical application.

## Interfaces and implementation
No route, payload, extension, native-host, saved-provider setting or database contract changes.
1. `ordinary_layout_contracts.py` and relevant generated-policy/recovery code: narrowly recover the retained malformed metadata grouping without weakening coverage or manual decisions.
2. `docx_writer.py` and checkpoint compatibility if required: preserve source folios and suppress only redundant generated PAGE furniture in new ordinary files.
3. Focused tests: retained failure shape, negative coverage/schema/order cases, footer evidence coverage and historical compatibility.

## Tests and acceptance
Reproduce the retained failed reply without new provider calls. Run meaningful focused tests and required development validation once on frozen code; hosted checks may run concurrently. Independently review the patch. After normal publication/application, perform one fresh exact-message Arabic workflow through source review, translation/layout, Word review, normal download, saved count/fee and an unsent draft. No manual page-number correction should be required. Preserve existing 78 records, six drafts, inputs and settings.

## Rollout and fallback
Existing user authorization covers publication, merge after checks and application. Stop only the identified idle canonical LegalPDF runtime for application. Keep original paid replies and output files unchanged. A new failure is recorded and diagnosed within this scope; do not buy repeated speculative layout retries or expand into unrelated polish.

## Risks and mitigations
Recovering bad grouping can accidentally reorder content: exact coverage, source order, metadata roles and strict manual validation remain mandatory. Suppressing PAGE can remove useful numbering: require source-folio coverage and leave meaningful footer text and historical recipes intact. Source-derived private content stays outside Git.

## Assumptions and status
The earlier paid run and manual fallback are complete historical evidence. This work is a new authorized repair and fresh test. Implementation starts from the unchanged installed build. Detailed execution results will be retained privately under `formatting_order_folio_fix_20261011_01`; useful touched-scope documentation is updated with the repair.

## Implementation closeout — October 11

Implementation and detached validation are complete; canonical installation and the one fresh Arabic end-to-end acceptance remain pending. Read private `formatting_order_folio_fix_20261011_01/Test_Report.md` and `publication_01/publication_receipt.json` for terminal status before continuing or replaying any operation.

The bounded generated V3 metadata downgrade preserves all paragraph choices and other bands, with policy/hash-bound review provenance. Fresh policy-gated legacy-TXT folio suppression preserves literal labels; historical checkpoints and structured furniture keep their old recipe. New-manager offline rebuild uses the retained policy. Focused checks passed 27 cases; the affected contracts passed 70. The exact retained 34-paragraph proposal produced an independently verified detached candidate without dispatch. Native/canonical fresh acceptance and required Full/hosted publication gates are separate pending lifecycle evidence.
