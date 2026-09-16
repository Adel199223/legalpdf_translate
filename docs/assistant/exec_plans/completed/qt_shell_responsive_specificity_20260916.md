# Restore existing Qt shell responsive rules

## Completed scope, 2026-09-16

Status: completed locally and moved under PLANS rules 8 and 9; this does not imply publication or canonical-main promotion.

Actual browser receipt 07e6b55e verifies the served asset and 494px/1366px layouts without overflow or browser errors, followed by owned cleanup. Gmail-focus behavior was checked statically only; no live Gmail acceptance is claimed.

Current full validation: repository F3 passed 6,477 tests with zero failures/errors/skips (result `0cceeb4c`, JUnit `ed5c1d79`); separate Standard Full SF2 passed (`adfcafe8`). Both retained the same 481-file source/test/script snapshot `bec79f29`. These results validate this bounded integrated scope; real French native/visual acceptance and final parent/docs closeout remain separate and pending.

The original implementation/authoring plan follows as historical scope and is superseded by this executed outcome where its status says pending. Exact pre-closeout bytes are retained privately in `application_docs_modernization_20260916_01/final_scoped_closeout_beforeimages_01`.


## Root validation checkpoint, 2026-09-16

Root verified the fresh actual asset version a3cd055c90e2 and HTTP stylesheet SHA f18f847b403b21e13762a1720451b017616c98a204c0a71ace0722124a54f0f1. At494px the shell has one474.4px column; at1366px it retains220px and1088.4px columns. Both screenshots were visually reviewed, no horizontal overflow or browser errors were observed, and the temporary viewport was reset. Private actual-browser receipt07e6b55e retains the measurements. Gmail-focus was statically checked only; no Gmail UI operation occurred. The responsive fixture made zero local/SDK calls; owned PID39632 was verified and stopped, and the sole tab reset to about:blank.

## Goal and scope

Let the existing 1180px and 900px shell media rules override the Qt desktop shell selector. Root observed a 220px sidebar beside a 216px main column and 606px document width in a 494px browser viewport. The Qt desktop selector has greater specificity than the existing media rules, so the intended one-column layout never applies.

Only add `body[data-ui-variant="qt"] .app-shell` to the selector lists of those two existing media rules. Preserve their declarations, breakpoints, desktop layout and later more-specific Gmail-focus override. No redesign, JavaScript, API, content or test changes.

## Provenance

Authoring W: `C:/Users/FA507/.codex/legalpdf_translate_reviewed_regions`, branch `codex/reviewed-regions`, HEAD `4780a2e16c32adf7af7479656f0b5fafdff83224`, noncanonical authoring only. Target runtime R is `C:/Users/FA507/.codex/legalpdf_translate_structured_activation`, branch `feat/structured-translation-activation`.

W and current R CSS both matched SHA256 `fb745962009988a42e2e511ce97579946c547458a46aa8bec11d4480a1ae1d33`. The exact baseline is retained in `qt_shell_responsive_beforeimages_20260916_01/style.css`. No R edits or wholesale sync.

## Validation and rollout

Static review confirms the added Qt selectors tie the desktop specificity and win by later source order at the two breakpoints. The final Gmail-focus selector still has greater specificity and remains later. Root will harvest and verify the actual narrow viewport, a desktop viewport and Gmail-focus layout in the browser. This reversible CSS-only correction adds no new tests and performs no local browser/test execution.

Rollback is the exact retained CSS baseline. No settings or route contract changes. Authoring frozen; browser verification pending root.
