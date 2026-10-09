# Last five sent translations structural fidelity audit

## Goal and non-goals

Audit the five latest sent translation threads, bind exact sent DOCX to their source PDFs, inspect Microsoft Word rendering, reproduce the current writer with retained wording, and prepare a bounded repair. The user accepts close structural fidelity; exact fonts, pagination and pixel equality are not acceptance requirements. No sending, draft writing, paid translation, publication, schema change, saved-setting change or live-service operation belongs to Stage 1 or Stage 2.

## Scope and worktree provenance

- Authoring worktree: C:/Users/FA507/.codex/worktrees/sent-structure-audit/legalpdf_translate
- Branch: feat/sent-structure-audit-20261003
- Base/target: canonical main; base SHA e70e1912b20de57901bec93372cf4e122568967a
- Canonical checkout: C:/Users/FA507/.codex/legalpdf_translate, main; no listeners on 8877/8765 at audit start.
- Status: unpublished, noncanonical docs/review work. No product/test/default or canonical runtime edits.
- Private evidence: C:/Users/FA507/.codex/legalpdf_translate_private_benchmarks/sent_structure_audit_20261003_01
- Native ownership: root alone operates Word. Existing user-owned/recovered documents remain untouched.

Stage 1 is complete subject to the terminal validation receipt. The complex pipeline repair requires the project staged-execution gate. Historical continuation tokens are consumed evidence and do not authorize new paid/native operations. This plan remains active while implementation is pending.

## Interfaces and decision locks

Preserve backend paths, browser routes, payload shapes, submitted select values, Gmail/native-host/extension contracts, safe rendering, accounting and delivery selection. No public protocol extension is planned. Reuse existing ID/text structured transport. Determine a whole-run policy before dispatch, with exact source/checkpoint identity; never promote a legacy resume in place or switch transport halfway through a run. Source acquisition cannot trigger another paid OCR/translation/layout call. Keep existing defaults until a separate acceptance/activation decision.

Do not infer source geometry from target wording or fabricate source IDs/review evidence. Preserve every target fragment once and in logical order. Whole-block emphasis can inherit source evidence; mixed source emphasis cannot map its offsets directly onto translated text. Unsupported or ambiguous source evidence must produce an honest review/qualified state. Natural target reflow is allowed; no shrinking, truncation or artificial source-page-count parity. Manual Arabic RTL/right-alignment finishing in Word is explicitly accepted by the user. Preserve protected names/identifiers/clocks/numbers in their established internal run order; no new automatic alignment or save feature is necessary.

## Stage 1 executed evidence

Five latest sent threads (October 1 and September 27) contain seven DOCX and ten candidate source PDFs. All 17 exact attachment hashes are preserved. Bindings exclude cover/instruction/correspondence pages:

| Reference | Language | Bound source physical pages | Word output pages |
| --- | --- | --- | --- |
| D01 sent 1 | Arabic | D01 source 1, p1 | 1 |
| D02 sent 1 | English | D02 source 1, pp3–7 | 5 |
| D03 sent 1 | French | D03 source 3, pp1–2 | 2 |
| D03 sent 2 | French | D03 source 4, pp1–2 | 2 |
| D04 sent 1 | English | D04 source 1, pp2–4 | 3 |
| D05 sent 1 | English | D05 source 2, p1 | 1 |
| D05 sent 2 | English | D05 source 1, pp1–7 | 7 |

Native Word screenshots are retained for each document; native exports and individual source/output page inspection cover all 21 output pages. Close structural fidelity is good, with no clipping, overlap or accidental extra pages found. One minor defect is confirmed: D05 long-document page 5 has a stretched justified final body line before an in-paragraph hard page break. Its historical app provenance is unproven. Initial citation/header/footer warnings were review errors; corrected authoritative reports retract them and preserve the originals/beforeimages. No comprehensive legal or linguistic certification is claimed. The user subsequently reports ChatGPT 6 Pro as the reference generator and manual Arabic RTL/right-alignment finishing; exact conversation/export history remains unverified.

All seven sent files exactly match direct Downloads copies, but none matches 37 extant job-log output paths or retained run joins examined. Two D03 files also match older August copies. Missing LegalPDF styles narrowly rules out direct current ordinary writer output and its style-preserving layout derivative without intervening recreation; it does not verify the exact conversation/export chain or exclude every other writer. The user-reported generator is ChatGPT 6 Pro.

Seven offline baselines use the current legacy writer and exact nonempty sent body wording/order, including nested table paragraphs. Each has one explicitly synthetic input page, zero tables and one section. Six Latin-script text-node streams are exact; Arabic adds existing presentation direction controls. Reference headers/footers and true source-page boundaries are outside the body-only projection, not provider omission findings. The complete two-page native French diagnostic confirms collapsed sidebar/columns, lost heading emphasis and wrapped-bullet indentation. Equal page counts conceal this failure. The other six baselines have package checks, not native acceptance.

Evidence index: private AUDIT_REPORT.md, stage1_receipt.json, attachment_manifest.json, originals_preservation_after_native.json, corrected page review receipts, reproductions/provenance_lookup_01.json and reproductions/legacy_writer_01/structural_comparison_01.json. Raw legal content/filenames are not copied into tracked docs.

## Proposed file-by-file Stage 2 implementation

Independent review narrowed the initial ten-module proposal. Start with one fresh digital-PDF vertical slice under explicit internal policy; expand only when a real fictional extraction fixture demonstrates a missing behavior.

1. Add ordinary_source_layout.py as a pure pre-dispatch source plan if existing helpers do not already provide a reusable whole-run decision. Bind exact source hash, physical selected pages, winning text, real block/span geometry, policy version and complete ordered-token coverage. Return supported, review-required or unavailable with content-free reasons.
2. Update workflow.py at source-winner/pre-dispatch identity boundaries to prepare every selected page before the first translation call and retain the plan through cache/commit/assembly. Reuse existing digital/same-pass OCR evidence; do not create a second extraction winner. Unsupported mixed/merged/OCR-off cases cannot silently acquire source fidelity.
3. Update translation_policy.py only as necessary for an explicit internal fresh-run policy, preserving DEFAULT_TRANSLATION_PROTOCOL, saved model/effort and legacy checkpoint behavior. No new public select value or default activation.
4. Update new_translation_blocks.py/document_structure.py only for a demonstrated binding gap; current v2 already captures digital structure, requests same-pass OCR evidence and checks ordered tokens. Existing pdf_text_order.py all-span emphasis logic is not a proven defect and should not be rewritten speculatively.
5. Reuse document_layout.py, layout_integration.py and docx_writer.py for a fictional court-letterhead plus recipient/reference-column fixture. Change these modules only if the full vertical slice exposes an actual unsupported association or rendering defect. Defer new panel, furniture, OCR and spacing algorithms until separate evidence proves necessity. The private D05 break-spacing defect is a qualified candidate, not an established app regression.
6. Add meaningful fictional/no-provider regressions at the existing workflow/structured-block/layout test seams. Fake translations must be distinct per source ID and traverse real extraction, workflow dispatch boundary, committed sidecars and actual DOCX assembly. Do not use private legal documents as automatic test fixtures.
7. Update only touched-scope architecture, handoff, validation and relevant guides after final implementation behavior is known. Exact beforeimages are retained. Stage 1 harvested the recurrent flattening limitation into ISSUE_MEMORY; no bootstrap/template work is implied.

The broader private stage2_design_01.md is design research. This bounded plan and independent reviewer assessment supersede its speculative ten-module first slice. In particular, no majority-bold extraction defect was demonstrated.

## Tests and acceptance

Stage 1: seven wording/order assertions, 17 original preservation checks, full native reference coverage, separate two-page native diagnostic review, doc/issue-schema and workspace checks, standard development validation. No new reversible docs tests are added. Terminal results belong to stage1_receipt.json; do not infer Full or product acceptance.

Stage 2: focused pytest with the existing canonical .venv311 interpreter and isolated worktree source precedence, standard validation, then required selected Full on the frozen final product/test tree. Keep package versions unchanged; no unlocked install or environment recreation.

Check exact target text once across all OOXML stories and nested tables, stable source/target ID mapping, physical column order and Arabic direction. EN/FR/AR longer target wording must retain grouping without shrink/truncation. Changed source, stale plan/checkpoint, reordered duplicate tokens, incomplete geometry, mismatched OCR winner and unsupported page mixtures must not claim fidelity or dispatch an unannounced extra call. Check default policy, settings, contracts and legacy resumes remain unchanged. Package success is separate from all-page native visual acceptance.

## Rollout, fallback, risks and assumptions

Source-bound implementation stays behind explicit policy pending Stage 3. Unsupported inputs retain existing qualified legacy/review behavior, with complete original text and visible limitation; no false geometry or silent paid fallback. Image-only/OCR-off inputs currently rely on image translation and cannot simply select v2, whose source-readiness gate rejects unusable text. Existing complex OCR eligibility must not be broadened just to fit these references.

Private historical files have uncertain generation lineage and often complex table/multi-section packages outside the saved-layout v1 import profile. Body-only writer probes are diagnostic, not faithful target candidates. Repeated furniture needs individual full-page corroboration; withdrawn review warnings cannot become product fixes. Word initial status page counts may be stale; native PDF physical pages are authoritative. Bundled LibreOffice is absent on Windows; native Microsoft Word exports are the review authority.

Publication, production/default activation and new real paid acceptance remain separately gated. No consumed operation/helper is replayed. Original attachments and documentation beforeimages remain immutable; the canonical checkout stays stable.

## Stage 1 packet and continuation

Changed tracked files: APP_KNOWLEDGE.md, docs/assistant/APP_KNOWLEDGE.md, HANDOFF.md, VALIDATION.md, ISSUE_MEMORY.md, ISSUE_MEMORY.json and this new active plan. Product/test/configuration files are unchanged. Private artifacts include original hashes, native screenshots/PDFs, complete page coverage, corrected reviews, provenance joins, seven offline baselines and a user-readable audit.

Validation outcome: standard development validation passed 249 tests in 56.03 seconds, compilation and docs/hygiene. Known dartdev AOT wrapper exit 255 events were preserved; direct Dart fallbacks passed. User-clarification docs-only edits receive final direct docs/hygiene checks; exact terminal results belong to stage1_receipt.json. Decision locks and risks are above. Gate source: docs/assistant/workflows/STAGED_EXECUTION_WORKFLOW.md, multi-surface medium-risk source/translation/Word pipeline implementation. Require exact NEXT_STAGE_2 for product implementation; this is a current stage boundary, not reuse of a historical token.

### Prepared Stage 2 prompt pack

Continue this plan at Stage 2 in the attached isolated worktree. Re-read the terminal Stage 1 receipt and reviewer-narrowed scope. Implement the smallest source-bound fresh digital-PDF vertical slice under explicit internal policy, preserving existing public contracts/defaults/resumes and no-provider limits. Run real fictional extraction through distinct fake translations, sidecar commit and existing DOCX region assembly. Change further layout modules only for demonstrated fixture gaps. Complete targeted and frozen selected Full validation, independent review and scoped docs. Stop with a concrete implementation packet before the next stage; no paid, Gmail, publication or default promotion.

### Prepared Stage 3 prompt pack

After accepted Stage 2 packet and exact NEXT_STAGE_3, perform root-owned full-page Microsoft Word review of the new fictional EN/FR/AR artifacts, comparing actual source layout with natural translated reflow. Assess columns, emphasis, groups, literal ordering, page furniture and break behavior only within the implemented supported lane. Arabic may include the user-accepted manual RTL/right-alignment finishing step on a separate derivative; record that qualification and verify literal ordering afterward. Use private retained wording solely as separately qualified, no-provider diagnostics where actual source bindings exist; do not retrofit synthetic baselines into structured commits. Preserve all previous evidence and fix demonstrated issues within this stage's supported scope. Report unsupported scan/panel/multi-document gaps explicitly. Real paid translations and production/default activation require a separate bounded proposal with build, inputs, settings, cost and current approval; do not invent authorization from this prompt pack.
