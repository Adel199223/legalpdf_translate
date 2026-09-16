# Closed numeric-slash direction in Arabic DOCX

## Completed scope, 2026-09-16

Status: completed locally and moved under PLANS rules 8 and 9; this does not imply publication or canonical-main promotion.

All 203 numeric-slash cases passed in F3. Actual corrected Arabic rendering preserves both 2/98 citations; clock handling and ambiguous-token guards retain their separate scope.

Current full validation: repository F3 passed 6,477 tests with zero failures/errors/skips (result `0cceeb4c`, JUnit `ed5c1d79`); separate Standard Full SF2 passed (`adfcafe8`). Both retained the same 481-file source/test/script snapshot `bec79f29`. These results validate this bounded integrated scope; real French native/visual acceptance and final parent/docs closeout remain separate and pending.

The original implementation/authoring plan follows as historical scope and is superseded by this executed outcome where its status says pending. Exact pre-closeout bytes are retained privately in `application_docs_modernization_20260916_01/final_scoped_closeout_beforeimages_01`.


## Goal and scope

Keep the complete ASCII numeric reference `2/98` in one LTR run when saved tokens protect each number separately. A real Arabic Word render showed `98/2` despite unchanged underlying character order. Change run direction only; do not alter saved source/target text, whitespace, controls, font, layout, clock handling, or non-RTL behavior. Do not generalize to dates, identifiers or other separators.

## Worktree provenance

- Authoring worktree: `C:/Users/FA507/.codex/legalpdf_translate_reviewed_regions`.
- Branch: `codex/reviewed-regions`; Git HEAD: `4780a2e16c32adf7af7479656f0b5fafdff83224`.
- Explicit parent-directed noncanonical authoring snapshot: current R `legalpdf_translate_structured_activation`; integration is parent-owned in R before any later canonical promotion.
- Writer and clock test initially exactly match R. Beforeimages and full hashes are retained in `numeric_slash_authoring_20260916_01/beforeimages.json`.

## Interfaces and implementation

1. Add a private closed `digits/digits` matcher and a separate slash-direction helper in `docx_writer.py`.
2. Match a control-free view while mapping the slash back to its original character position. Reject identifier/combining-mark adjacency, longer slash chains, whitespace and line breaks. Respect complete retained bidi scopes and preserve balanced LRI/PDI wrappers.
3. Apply after existing line segmentation so enclosing retained controls across lines remain visible to the scope check. Preserve explicit line barriers when merging adjacent runs. Existing clock functions remain unchanged.
4. Update only the clock test's obsolete RTL-slash expectation, preserving its whitespace/clock assertions.
5. Add synthetic segmentation and actual saved DOCX OOXML tests, with no private case fixture.

## Validation and acceptance

Parent runs focused writer/clock/numeric-slash tests and broader required checks after harvest. This authoring task runs no imports, tests, application/helper modes, paid requests or native Word. Acceptance requires exact text preservation, one `w:rtl=0` reference run, Arabic still RTL, unchanged fonts, exact input hashes, and meaningful rejection cases. A later fresh Word export is required for actual render acceptance; old exports are consumed and cannot be replayed.

## Rollout, risks and assumptions

The fix is a narrow run-direction derivative. Keep previous artifacts and beforeimages intact. If review or tests fail, revise authoring before integration; never mutate historical paid text or replay consumed formatting/native modes. ASCII `n/n` is the deliberately supported shape; other numeral systems, multi-slash values and ambiguous punctuation remain outside this inference.

## Status

Authoring complete. Stdlib AST parsing and beforeimage comparisons confirm that the only existing function changed is `_segment_rtl_placeholder_aware_runs`; the original clock helper is text-identical. No application imports or tests were executed. Runtime validation and real-render verification remain parent-owned and pending.
