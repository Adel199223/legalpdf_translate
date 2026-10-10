# Gmail layout and delivery follow-up

Completed implementation and qualified acceptance on October 10. The earlier staged notes below are dated history; authorized publication/application state is owned by the terminal receipt named in the final outcome.

## Goal and non-goals

Resolve the remaining issues demonstrated by the October 10 Arabic Gmail test: source block placement, duplicated page numbers, misleading fee filename wording, generic selected translation filenames, and disabled-extension handoff. Preserve legal text, exact identifiers, existing rows/settings and the unsent draft. Do not retranscribe or repurchase the successful translation, change saved app models, or send email.

## Scope

In: narrow generalizable layout/delivery fixes, meaningful regression tests, retained-source native Word validation, shadow UI checks and extension readiness after user enablement. Out: unrelated architecture, new Decisions API integration, DB/schema changes, browser security workarounds, fresh unrelated provider campaigns.

The user explicitly requested this goal and authorized ongoing app development/testing. Routine implementation and validation remain within that scope; no old NEXT_STAGE token is reinstated. Publication/canonical rollout remain a separate final approval boundary under AGENTS.md. The user enabled the existing Edge extension manually after browser policy blocked automated settings access. The subsequent genuine handoff passed.

## Worktree provenance

- Integration/layout worktree: C:/Users/FA507/.codex/worktrees/gmail-structure-followup/legalpdf_translate
- Branch: feat/gmail-structure-followup-20261010
- Delivery stream: C:/Users/FA507/.codex/worktrees/gmail-delivery-names/legalpdf_translate
- Delivery branch: feat/gmail-delivery-names-20261010
- Base branch and target: main
- Base SHA for both: fc9b3d560f874459f02274e64977a382bd714f4a
- Approved floor 4e9d20e is an ancestor.
- Canonical live main at C:/Users/FA507/.codex/legalpdf_translate remains running on 8877/8765 and is not edited or switched.
- All feature UI checks use isolated shadow state and explicit worktree/build identity.

## Interfaces and contracts

Keep existing routes, browser IDs, payload shapes, extension/native-host contracts and submitted values. Change presentation labels and trusted server-derived display/attachment names without changing immutable candidate paths/hashes. Layout changes must preserve exact text/multiplicity and recorded source ownership. Any necessary layout contract/version change must be identified by design review before implementation; never silently accept stale provenance.

## File-by-file implementation

1. Astra analysis: inspect ordinary_layout_contracts.py, ordinary_layout_service.py, ordinary_layout_integration.py, reviewed_region_writer.py, reviewed_formatting_writer.py and docx_writer.py against the retained source/response/candidate. Identify why source geometry loses to provider paragraph order and why a source-owned page label coexists with an automatic PAGE field. Lock narrow source-evidence-based behavior before coding.
2. Layout implementation in the integration worktree: ordinary_presentation.py owns a versioned source-evidence plan and independent actual-order/footer-delta checks; saved_docx_layout_writer.py applies V6 only with trusted ordinary context; ordinary_auto_layout_artifacts.py supplies retained page ownership and preserves historical verification; ordinary_auto_layout.py fingerprints the new writer identity. Permit only complete whole-metadata-group source vertical inversion repair with known nonoverlapping geometry, preserving within-group IDs and all substantive body/list/signature order. Record the actual visual-order plan honestly in the source map; keep historical/manual decision validation unchanged. Suppress only a positively recognized app-generated PAGE-only footer when retained source_folio ownership covers all selected source pages. Preserve all source folio text and meaningful reply-footer wording. Add causal and adversarial order/footer regressions using fictional source shapes, not private case text.
3. Delivery stream: correct selected output download naming in shadow_web/app.py and Gmail attachment staging in gmail_batch.py/gmail_browser_service.py using a shared trusted naming rule and existing filename sanitation. Retain exact selected bytes. Correct fee filename labels/hints in translation_completion_presentation.js/templates where actually used. Keep API field names and IDs.
4. Integrate the reviewed delivery patch without overwriting unrelated work; no commits/push yet.
5. Update only touched-scope architecture, handoff, validation and user-guide guidance after behavior is verified. Preserve current guidance beforeimages in private evidence.

## Tests and acceptance

- Causal regressions for source recipient/reference order; sparse or ambiguous source evidence must retain safe order.
- Source page labels remain exact and appear once; generated pagination must not duplicate retained literal source numbering. Exercise single/multiple pages and languages, including Arabic and narrative numerals that are not folios.
- Download and Gmail names are descriptive, safe and derived from the original source/target while selected bytes and candidate identity remain unchanged. Cover existing selected revisions and collisions.
- Render corrected retained Arabic output with native Word; inspect every source/output page. Verify all 14 exact-data checks and meaning, no clipping/overlap, modern compatibility, proper bidi, no graphics.
- Exercise isolated shadow browser UI and filename labels/download.
- Targeted pytest with locked canonical .venv311 and worktree src; process-isolated APPDATA/TEMP and no API keys for automated checks. Standard validate_dev.ps1 and selected Full are required for final code. Record the known Dart wrapper failure/direct fallback accurately.
- User-enabled extension: verify installed identity and one genuine same-message handoff only; no duplicate translation/save/draft or send.
- Existing real row 101 and unsent draft remain unchanged unless a later concrete user-authorized delivery update is required.

## Rollout and fallback

Keep fixes isolated and reviewable until final validation. Ask for the specific publication/application action only when the final changes and checks are concrete, if no further authorization has arrived. Preserve old files/evidence rather than overwrite historical output. A failed new native/provider operation stays recorded and is not silently replayed.

## Risks and mitigations

Geometry-driven ordering can corrupt narrative or mixed columns: use explicit source association and bounded evidence; test unknown/overlapping geometry. Footer suppression can hide legitimate data: preserve source text and distinguish literal folios from prose/identifiers. Naming must not permit path injection or change attachment content: sanitize trusted names and verify byte identity. Browser restrictions must not be bypassed through alternate surfaces.

## Assumptions and current evidence

Reference test evidence: C:/Users/FA507/.codex/legalpdf_translate_private_benchmarks/gmail_arabic_e2e_20261010_01. Qualified prior result had one source/native page, all 14 data checks passing, manual RTL/right alignment, a duplicated page counter, recipient/reference order drift, one saved row and one unsent draft. Its successful paid/native operations are historical and must not be replayed.

## Progress

- Goal opened; canonical tree verified clean apart from preserved user attachments.
- Fresh isolated branches created on the exact installed base.
- User-only extension enablement requested; code work proceeds independently.
- Astra identified deliberate provider-order normalization and unconditional legacy PAGE furniture as the two layout causes. The bounded new automatic-writer approach above is approved; detailed guards remain subject to independent review.
- GPT-6.1 Sol filename/fee-label implementation passed focused tests and was integrated with all nine file hashes matching its frozen packet. Independent Astra review accepted selected-byte preservation, route boundaries, names and labels; the supplementary-Unicode filename-length correction was completed before final freeze.
- User enabled the extension and reported that Edge Developer mode was required. Microsoft documentation confirms that requirement for the current unpacked local installation. One genuine intake-only handoff passed and loaded the exact email and supported PDF without manual Load/Prepare. Canonical main remains fc9b3d560f874459f02274e64977a382bd714f4a; worker 25300 serves both 8877/8765, asset 0c27123ea444. Private extension_01/runtime_binding_01.json binds the UI evidence to that build. No translation/save/draft was repeated.
- V6 will receive trusted RawOrdinarySnapshot selected_pages/page_groups at automatic build and verification through ordinary_auto_layout_artifacts.py. Missing context keeps V5 behavior. It will record original and rendered IDs with a policy identity, independently validate eligible changed pairs, and verify the exact recognized footer delta. Historical V1–V5 and manual decisions remain strict.
- Exact beforeimages of touched current docs and validate_dev.ps1 are retained in private docs_beforeimages_01. Validation reuses the existing locked canonical Python through an ignored worktree junction; no environment recreation or package upgrade occurs.
- Final implementation freeze: private layout_01/review_packet_final_01.json (SHA-256 c09422a0f373e14d365e9b2f9a8eff8ea5ee70c35e5c777b79eedc9690934250) pins seven layout/naming source/test files. Independent review verified those pins and retained candidate/map/proof. Final 30 affected tests passed, including the Arabic edited-delivery fake-SDK workflow; the earlier 171-test pass predates the last small verifier/import cleanup and retains that qualification. Eight additional independent probes passed. No blocking review finding remains.
- The new detached actual candidate preserves all 34 IDs, performs two source-evidenced metadata swaps and suppresses only footer1's generated PAGE field. Exact historical V5 verification still passes. The candidate was reverified against final frozen sources without another provider call.
- Fresh native review used a copy, visible Word RTL/right alignment and one Save/close. The new export succeeded in 6.691 seconds, left the working DOCX unchanged and cleaned up its owned Word instance. Native visual/content/edited-copy qualification subsequently passed as recorded below; prior native helpers were not replayed.
- Shadow UI attempt 01 hydrated the new asset and downloaded identical synthetic bytes as Fictional_Notice_EN.docx. This proves the normal artifact route in a browser, but not a completion-button click or visible fee field: the completed fake job was not selected and the Gmail labels remained hidden. That qualification is preserved; the fresh complete synthetic UI fixture subsequently passed visible controls without submitting a mutation, as recorded below.
- Complete native acceptance now passes with the user's close-fidelity qualification: one source/output page, all 14 exact-data values and multiplicities in DOCX/PDF, all 34 paragraph texts retained, recipient before reference/date and one visible source folio. Actual Word-save adoption passes; compatibility is 15, graphics/media/PAGE fields and prohibited bidi controls are zero. Thirty existing LRMs remain unchanged. Source-page-bottom anchoring, wrapping and spacing are not pixel-identical; the user explicitly accepts close fidelity. Root and Astra reviewed every page. Private native_qa_01/native_qa_01.json (SHA-256 ae4a8ad01b44ff674fc20c0f172d7e6ca53996fc9e7f199d0480a1e0cfc31e28) owns the detailed result.
- Fresh shadow_ui_02 passes visible normal Recent Work → Open run → Download and normal Continue Gmail step → visible Honorários DOCX filename. Download bytes match the synthetic completed output. All mutations were blocked, including the automatic preflight POST; no live Gmail/native/provider operation was claimed. Both isolated runtimes/tabs are retired and port 18877 is free. Private outcome_01.json pins screenshots, bytes and guard logs.
- Standard01 completed with 249 passing tests and one obsolete label expectation at test_shadow_web_api.py:524. Its failure and all 1,149 unchanged pins remain preserved. The test-only update now asserts the intentional new Honorários label and passed its focused case; no product or accepted native artifact changed. Standard02 passed all 250 tests in 51.875 seconds with all 1,149 pins unchanged.
- Final selected Full01 passed 1,847 executions, including all 191 formatting cases and nine expected intake deselections, exit 0 in 2,455.579 seconds with all 1,149 file pins unchanged. Both Dart wrapper AOT failures remain recorded alongside successful direct-Dart fallback results. All 19 formatting evidence files were preserved and hash-verified. Private validation_full_01/terminal_count_receipt.json owns the exact counts and qualifications; no hosted-CI pass is claimed.
- Post-validation read-only comparison confirms all 75 live records, schema and settings unchanged. The original reply draft remains unsent; its attachment reference IDs/history ID differ from the initial response, while the compared body/headers/attachment metadata match. No new attachment-byte fetch or draft mutation was performed. The reviewed editable copy is indexed by private final_local_receipt_02.json.
- Implementation, independent review, local regression, actual native Arabic acceptance and visible shadow UI acceptance are complete. Final docs-only verification belongs to private docs_closeout_02/receipt.json. The user subsequently authorized publication, merge after hosted checks and application to the normal app. Implementation and acceptance are complete; the authorized terminal rollout is delegated to `C:/Users/FA507/.codex/legalpdf_translate_private_benchmarks/gmail_structure_followup_20261010_01/publication_01/publication_receipt.json`. That receipt owns exact CI/merge/installed/cleanup state; absent or incomplete means finish only the remaining lifecycle, while terminal means no replay.
