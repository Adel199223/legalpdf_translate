# Source-backed folio spans for automatic page-counter suppression

## Goal and non-goals
Suppress only the app-generated PAGE footer when every selected source page has a locally verified printed fraction and an unchanged matching terminal target span. Preserve all source/translated text, including mixed contact paragraphs. No paid calls, native/UI actions, current delivery changes, broad parser relaxation or historical-policy reinterpretation.

## Scope and provenance
- Worktree: `C:/Users/FA507/.codex/worktrees/source-folio-span-proof-20261016/legalpdf_translate`.
- Branch: `feat/source-folio-span-proof-20261016`.
- Base and integration branch: canonical `main`; exact locked base `d27230c02f71fa177034eb0d88f86fd988a4d9e6`.
- Approved floor `4e9d20e` is an ancestor. This checkout is noncanonical and will not serve an app.
- The parent owns integration, Standard/Full and native acceptance. A separate child owns corrected-Word PAGE removal; its files are excluded here.

## Contracts
New versioned private source-PDF proof and frozen automatic policy identity. No routes, public payload shapes, submitted values or provider protocol changes. Prior recipes retain exact behavior. Pure artifact verification must bind the proof to retained source bytes and page frames before it can affect the writer.

## Implementation
1. Add a bounded local proof helper: exact source hash, unique standalone bottom-page numeric fraction, selected-page/frame identity, text hash and geometry. Unknown/ambiguous extraction yields no suppression.
2. Match one terminal numeric target span per source page only in an owned, unpartitioned source_folio paragraph with plain text/control-safe tokens and matching bottom geometry. Compare numeric values; permit U+060D only inside the closed target numeric expression; preserve the literal bytes.
3. Pin new proof/version under a new automatic policy. Derive and verify at the retained-source service boundary and in pure artifact verification. Save the proof in private evidence and presentation context.
4. Extend presentation derivation and independent footer checking only when a complete verified proof exists. Continue matching the frozen exact generated footer signature; never alter custom furniture.
5. Add fictional positive/negative and historical-replay coverage; read-only actual-source proof may build in memory to confirm recognition and text preservation, without persisting or adopting an actual delivery.

## Validation and acceptance
Run the new focused module and affected ordinary presentation/artifact/policy modules with the locked Python environment and isolated test app data. Require all selected pages, exact text/control preservation, no source fraction deletion, rejection of ambiguous/stale/mismatched evidence and unchanged historical recipes. Root runs integrated Standard/Full once after both patches freeze.

## Rollout, fallback and risks
Freeze an exact patch plus file/test receipts for independent review. No local runtime rollout in this child. Missing selectable source text, invalid PDF, uncertain geometry, multiple fractions, invalid numeric pairs, custom footer or incomplete page coverage retain the generated counter. Avoid interpreting arbitrary prose substrings. Record extraction version in the proof and compare re-derived proof on replay; never silently upgrade old evidence.

## Assumptions and status
The current source PDF has three selectable standalone printed fractions. Its retained target paragraphs merge two fractions with contact text and use U+060D on the third. Current frozen rules decline them conservatively. Implementation authorized by the parent; no additional live or publication scope is inferred. Initial plan recorded before source edits.

Actual-source probing found the second page's coarse provider region missed the exact source fraction center horizontally by 18.28 pixels (1.535% of frame width). The parent approved a v1 horizontal margin of 2% of frame width, with exact vertical containment and all other guards unchanged. Fictional tests cover both horizontal boundaries, just-outside refusal and vertical refusal. The fraction values match source numbering; source excerpts need not number pages by physical PDF index or total PDF length.

## Results and handoff
- Final focused module: 37 passed in 30.82 seconds. The exact-boundary regression exposed binary coordinate roundoff; the only numerical epsilon is 1e-9 pixel around the horizontal limit. Just-outside and vertical refusals pass.
- Read-only retained-source proof: all three pages/target spans recognized; all 45 body paragraphs' text and controls match the prior V7 output; the historical candidate independently verifies with its original evidence and no new proof. All 11 retained input hashes remain unchanged. The new in-memory output was not persisted or adopted.
- Six-module compatibility run started before the horizontal-tolerance adjustment and remains separately recorded; the final focused module covers the changed helper. Parent integration owns definitive combined validation and Standard/Full.
- Private evidence and frozen handoff: `source_folio_span_proof_01` under the parent's retained benchmark evidence root. No runtime, provider, browser or native actions were performed.
