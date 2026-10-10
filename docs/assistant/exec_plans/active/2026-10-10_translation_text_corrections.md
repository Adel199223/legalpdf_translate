# Explicit translation text correction

## Goal and authority
Implement the root-assigned ordinary browser text correction flow in an isolated worktree. User-authorized scope includes source comparison, natural-text replace/add/delete, explicit before/after approval, safe Word text import, current selected delivery/count/review integration and meaningful offline tests. No live Gmail/provider/native actions or publication in this implementation task.

## Provenance
Worktree: C:/Users/FA507/.codex/worktrees/translation-text-corrections/legalpdf_translate
Branch: feat/translation-text-corrections-20261010
Base: b30bdf8b649b43e4ee232f9c5ec3796e841a3c6c
Root integration plan: 2026-10-10_translation_review_completion.md in the separate integration checkout. Root owns touched-scope documentation and validation selectors. Other worker owns diagnostics, proposal V3 manager/contracts, presentation/writer V7. This plan owns only additive correction modules/routes/UI and necessary delivery/Arabic review hooks.

## Invariants
Corrections derive from the exact current selected artifact, never replace provider bytes or raw baseline. Identity includes mode/workspace/source/run/job/language/pages/parent digest and delivery generation. Approval and cancellation are immutable, nonce-bound, under the existing service lock. Stale/frozen selection refuses mutation. No dispatch/accounting calls are added. Selected word count derives from actual DOCX; original translation/layout spend adds once. Normal Save freezes the reviewed selection.

Browser edits preserve exact unchanged XML/story/control content and paragraph ownership. Insertions require explicit source page and region; replace inherits only qualified coarse association. Natural text is not internal [[token]] protocol. Mixed character emphasis reset is disclosed. All changed paragraphs show before/after and require explicit approval; output review is separate. Word import preserves the owned file and accepts only safe story/control/section topology with every content delta exposed. Formatting-only adoption subsequently compares with the corrected parent and follows one stable owned working-copy lineage.

Source coverage findings are proposals, never completeness certificates or automatic insertions. Explicit dispositions bind selected SHA; new selections reset them. Historical raw diagnostics remain unchanged and are labelled separately from the current selected revision review.

## Implementation and validation
- [x] Pure package/editor guards, natural-text direction/font segmentation, stable IDs and section/story protection.
- [x] Immutable correction drafts/approval/cancel/selected delivery and bound delivery-copy/map verification.
- [x] Additive API, source image reference, browser editor and safe before/after rendering.
- [x] Corrected Arabic review target and repeated formatting-only working-copy lineage.
- [x] Offline real API download/Save/Gmail confirmation and initial DOM/pure service regressions.
- [ ] Complete source-finding disposition and selected warning presentation tests.
- [ ] Freeze coherent commit for independent review/integration; no push.
- [ ] Root integration Standard/Full and isolated browser/native acceptance before canonical promotion.

## Evidence and open qualifications
Initial combined correction/existing layout/edited guards: 61 PASS. Subsequent correction service/API/browser: 14 PASS. Actual retained Word serialization plus a synthetic text-only delta passed read-only pure import qualification after resolving rsid/relationship numbering and system-note serialization. Genuine Word UI import/formatting acceptance remains a parent-owned later gate. V7 footer ownership integration awaits the other worker's frozen map interface.
