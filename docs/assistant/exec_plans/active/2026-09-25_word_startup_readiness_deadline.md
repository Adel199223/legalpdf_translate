# Bounded Word startup readiness deadline

## Goal and non-goals

Conditionally fix the demonstrated inconsistency between ordinary browser Word readiness callers and the shared startup deadline. A genuine Gmail Confirm saved its case successfully, then automatic finalization preflight stopped its owned helper after an eight-second deadline before Word ownership was established. Preserve that failed operation and determine whether a fresh, supported 45-second canonical preflight succeeds with confirmed cleanup before changing product code.

This is a narrow follow-up to the [Gmail and formatting readiness plan](2026-09-24_gmail_formatting_readiness.md). It does not repeat translation, re-save the confirmed case, create or send a Gmail draft, change formatting behavior, alter provider settings, promote saved defaults, or reopen the shelved historical French investigation. Existing user authorization governs the overall task; this plan does not independently grant new runtime, paid, native or publication authority.

## Scope

In scope, only after the evidence gate below: one shared, finite startup/preflight deadline, removal of the three conflicting browser overrides, meaningful no-provider regressions, independent review, fresh required validation, and integration through the normal reviewed publication flow when authorized.

Out of scope: Word process ownership algorithms, orphan adoption or termination, native journal/reset behavior, locking, cache scope or TTL changes, route/payload contracts, provider request bounds, ledger edits, Gmail permission changes, and unrelated cleanup. The separately prepared private shadow06 helpers remain unarmed and untouched by this code task.

## Worktree provenance

- Worktree: `C:/Users/FA507/.codex/worktrees/word-startup-readiness/legalpdf_translate`.
- Branch: `codex/word-startup-readiness-20260925`.
- Base branch and target integration branch: canonical `main`.
- Base SHA: `ca395d601efe4e00aad3458526b7d961d3cf5f0c`.
- Approved-base floor: `4e9d20e`, present in the base ancestry and declared by `docs/assistant/runtime/CANONICAL_BUILD.json`.
- This is a noncanonical authoring checkout. Canonical live Gmail remains `C:/Users/FA507/.codex/legalpdf_translate` on `main`; do not edit/switch that checkout or replace its running server during implementation.
- The older formatting authoring worktree remains at its separately recorded source/runtime identity. Its validation and unconsumed preparations do not validate this new change.

## Interfaces, evidence and contracts

At the base snapshot, `gmail_browser_service.py:2418` and `power_tools_service.py:581,813` explicitly supply `launch_timeout_seconds=8.0`. Shared `assess_word_pdf_export_readiness` and `probe_word_pdf_export_support` default to 12 seconds in `word_automation.py`. Canary and actual PDF export have separate 45-second deadlines. There is no constructor-level deadline to update.

The proposed shared launch deadline is 45 seconds. Readiness can therefore require a launch/preflight stage of up to 45 seconds followed by a separate canary/export stage of up to 45 seconds. This is **45 + 45 seconds of stage deadlines**, not a single 45-second or guaranteed 90/95-second wall-clock limit: lock/recovery checks, owned-helper shutdown grace, artifact preparation and reporting can add overhead. Do not add an outer timeout that interrupts cleanup or change the separate canary deadline.

Private evidence root: `C:/Users/FA507/.codex/legalpdf_translate_private_benchmarks/gmail_formatting_readiness_20260924_01/`. Bounded starting evidence:

- `gmail_finalize_native_diagnosis_01/diagnosis_receipt_01.json`, SHA256 `a93de72f4a3092cf0a9aa59fdd2331603aaf6a114256f97db79f29513aab76c7`: actual automatic eight-second preflight, stopped owned helper, unknown Word ownership and unconfirmed cleanup. It does not establish the underlying Windows delay's cause.
- `cases/gmail_live_03/after_confirm_01/persisted_gmail_session_after_confirm.json`, SHA256 `45b769c4fe7ab8593c7b309711edfb11a62d27ebe03c4461da74651d8ea00517`: genuine saved-session result; fresh preflight rather than a cached failure. Do not print private content.
- Root-verified `owned_word_orphan_cleanup_01/result.json`, SHA256 `1875de5e8036c13ef02034b1bfbff28329a3b582d6cfa69b2fc0e59cc101abb1`: one separately authorized exact-process stop, 5.144 seconds Word-free, four protected files unchanged, prior journal retained unchanged. This historical receipt is not permission to repeat cleanup.
- The fresh supported canonical 45-second preflight result is **pending at plan creation**. Pin its actual terminal result and cleanup evidence before deciding implementation. A success supports bounded startup tolerance; it does not prove why the previous operation was slow or guarantee every later startup succeeds.

Keep the prior native failure, successful private exports, cleanup operation and fresh probe distinct. Private 45-second exports used a different profile/environment and are not proof that the canonical eight-second preflight was sufficient.

## File-by-file implementation steps

1. Record the fresh canonical probe's actual result and root decision in Progress. If it fails or cleanup remains unknown, retain this plan as conditional and investigate only the demonstrated result; do not implement a deadline increase speculatively.
2. If supported by that result, add one named 45-second startup/preflight constant in `src/legalpdf_translate/word_automation.py`, used by the direct probe and readiness aggregator defaults. Preserve explicit timeout overrides, finite-positive validation, actual-export/canary deadlines, result fields, error classification and all ownership/cleanup gates.
3. Remove the three eight-second launch overrides in `src/legalpdf_translate/gmail_browser_service.py` and `src/legalpdf_translate/power_tools_service.py`, letting the supported shared default govern ordinary Gmail finalization, provider-state readiness and the explicit Word test. Preserve cache scopes, force-refresh behavior and independent export arguments.
4. Add focused regressions to `tests/test_word_automation.py`, `tests/test_gmail_browser_service.py` and `tests/test_shadow_runtime_service.py` only as needed. Use fake subprocess/native results and virtual elapsed/deadline behavior. Do not sleep for the real deadline, launch Word, query live credentials, or use real Gmail/native-host diagnostics.
5. Independently review the exact patch. After source freeze, perform targeted validation, required Full and scoped docs validation. Preserve exact commands, terminal output, JUnit/counts where available, source pins, and original failed test results privately.
6. Update this plan and only useful touched-scope handoff/validation/user guidance, preserving beforeimages when replacing current guidance. Keep old eight-second evidence historical and distinguish product regression from fresh actual native acceptance.

## Tests and acceptance criteria

- Before the fix, a synthetic startup requiring 20 virtual seconds must fail meaningfully through the old ordinary eight-second caller and old 12-second default. After the fix, the real readiness aggregator receives the shared 45-second budget and reaches ready only after synthetic launch success with confirmed cleanup and successful canary.
- Cover all three actual browser/service entry points, not only a constant-value assertion. For provider-state tests, stub credentials, Gmail prerequisites, OCR availability and native-host diagnostics before any settings/bootstrap call. Existing readiness mocks accepting arbitrary keyword arguments do not establish correct timeout forwarding.
- The direct probe passes its default bounded deadline to a fake owned subprocess; a supplied smaller caller override remains supported. Retain failure coverage proving a timed-out helper never kills a Word/process tree and unresolved cleanup blocks a subsequent attempt without another launch (`test_word_automation.py`, existing timeout/recovery regression).
- Failed or cleanup-unconfirmed launch skips the canary; canary failure still blocks readiness. Cached results, force refresh and cross-scope invalidation retain existing behavior. No automatic retry is introduced.
- Run targeted modules with the canonical `C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe`, explicitly importing this worktree's source and using isolated child APPDATA/TEMP, disabled dotenv, null keyring and reviewed no-provider/native guards. No bare/global Python and no actual live app data.
- Then run a fresh owned `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full` for the frozen new source snapshot. The targeted Word/Gmail/power-tools modules remain required even if Full's selected groups omit them. Do not reuse old Full_04 results for changed code. Preserve known Dart AOT-launch failures and accept only the wrapper's successful direct fallback; run scoped docs/hygiene checks separately if its clean-tree path skips docs.
- Before integration, exact publication-head CI must pass the current `test (3.11)` Windows workflow and `docs_tooling_contracts` Linux workflow, together with current repository rules and independent review. Windows CI includes full pytest, targeted core tests, compile and docs/tooling checks. Recheck actual requirements at publication time; no pending run is a pass.
- Actual canonical recovery/acceptance is a separate root-owned operation after safe integration/runtime transition. A no-provider regression or larger timeout alone does not close the Gmail finalization goal.

## Rollout and fallback

Follow the current commit/publish workflow within the already authorized publication scope, with exact-head checks and a normal reviewed merge. Stop the current owned runtime before applying a new canonical build; use a fresh operation with verified ownership. Do not patch a running process or claim a helper cache warms a different server process.

If evidence does not support the candidate, leave code unchanged and record the cause as unresolved. If the implemented change fails review or validation, retain the failing receipt and correct only the demonstrated regression. Any later rollback must be a scoped reviewed change, not a reset of settings, journals, evidence, ledgers or unrelated commits.

## Risks and mitigations

- Slower readiness response: document the two independent stage budgets and retain normal busy UI/error behavior. No arbitrary 95-second promise or additional client cancellation is included.
- Native overlap or orphan risk: preserve the existing OS lock, exact identity checks, prior-operation recovery and cleanup confirmation. A longer deadline never authorizes adopting or terminating an unknown Word process.
- Misstated causality: the prior eight-second deadline expired before ownership; the underlying Windows delay remains unknown. Record observed probe timing rather than attributing it to load, security software or process introspection without evidence.
- Live-data contamination: tests use temporary state and mocked boundaries. Never import production launch helpers merely to test a default. Python audit guards do not imply an OS sandbox or automatic child-process protection.
- Historical evidence or default drift: all old operations and legitimate current settings remain preserved. The normal Gmail Confirm addition of `court_emails_by_city` is separately reviewed metadata; all saved translation/OCR defaults remain equal and must not be restored over the user's new metadata.

## Assumptions and defaults

The original USD 10 limit, 226 historical ledger rows, USD 0.119 hold/block and partial output remain untouched. The separate USD 3/16-reservation phase currently has 14 finalized rows costing USD 0.21838600, no new hold and two slots; this code task makes no paid request and allocates no new capacity. Reassess the actual ledger before any separately authorized future translation rather than treating this snapshot as immutable current state.

Sending email, Gmail scope expansion, public hosting and global default promotion remain excluded. Root owns native probing, cleanup, runtime transitions and final execution decisions. Current user authorization overrides obsolete historical stage-token stops, but no unproved technical prerequisite is waived.

## Progress and decisions

- 2026-09-25: Created this plan before product edits in the fresh isolated worktree; verified branch/base and read current runbooks. Source-only diagnosis identified three eight-second overrides and two shared 12-second defaults. No source/test edit, test run, native/provider action or shadow06 helper change occurred in this preparation.
- Evidence gate satisfied: root executed one fresh supported canonical preflight with a 45-second deadline. `native_startup_recovery_01/operations/native_preflight_recovery_01/result.json` (SHA256 `10a8c00e8f233e451e748277777c1265afbea119e63ac70e4a1913cb6472d735`) records success, proven ownership, confirmed cleanup, Word-free state and unchanged protected files. Total native-operation time was 10.309 seconds including the five-second prior-operation recovery observation; the actual helper took 5.268 seconds. This is not a claim that this successful helper itself exceeded eight seconds. The prior 8.434-second failure plus the fresh bounded pass supports the approved tolerance change without establishing the Windows delay's cause.
- Root authorized implementation and targeted red-to-green validation after this plan was written. Fresh Full waits for independent review and source freeze. No publication, native operation or provider dispatch is delegated to the implementation agent.
- Implementation, targeted regressions, independent review, fresh Full, scoped docs checks, CI/integration and canonical application of the product change remain unexecuted at this checkpoint. The successful probe is a distinct consumed operation, not a replayable test helper.
- Targeted pre-fix run `word_startup_fix_01/red_03` reproduced six failures and one passing explicit-timeout case with no external-action attempts. Earlier runner/JUnit-hostname and missing ancillary-mock observations are preserved separately. The first full three-module run then exposed an existing test-isolation gap: setup/bootstrap paths attempted installed Gmail-helper and native-host diagnostics before per-test mocks. All attempts were blocked by the private audit hook. Root approved a bounded test-only extension of deterministic ancillary-diagnostic fixtures in the two touched service test modules; explicit test overrides remain effective. Private-child diagnostic stubbing produced a provisional 91-pass result, but final acceptance must rerun with those private product monkeypatches removed and the isolation expressed in the repository tests.
- Implemented one `WORD_PDF_STARTUP_TIMEOUT_SECONDS = 45.0` constant for direct probe/readiness defaults and removed the three eight-second service overrides. No canary/export deadline, cache, ownership, lock, recovery, route, payload or saved setting changed. Seven regression cases exercise the slow-startup/default/explicit-override boundary and three real service entry points.
- Final targeted run `word_startup_fix_01/green_04` passed all 91 tests across `test_word_automation.py`, `test_gmail_browser_service.py` and `test_shadow_runtime_service.py` in 3.81 seconds, with no skips/warnings, unchanged six-file source/test pins and zero denied external-action events. Its fresh private runner uses isolated data, null keyring, disabled dotenv/plugins and fail-closed socket/subprocess/registry/native guards; it has no product-function monkeypatches. Hostname/Windows platform metadata are fixed only to avoid test-report/dependency platform-version subprocess discovery. Repository fixtures now isolate unrelated Gmail/native-host diagnostics before setup while each test may install its specific mocks.
- Retained earlier attempts: `red_01` test-report metadata guard failure; `red_02` meaningful failures plus an ancillary Gmail attempt blocked by the audit guard; `red_03` clean pre-fix reproduction; `green_01` 83 passed/eight ambient-diagnostic isolation failures; `green_02` 85 passed/six native-host isolation failures; provisional privately isolated `green_03` 91 passed. None of these blocked attempts dispatched a native/helper/provider action. Final acceptance uses `green_04`, not a relabeled earlier run.
- Six product/test files are frozen for independent review and root-owned commit/Full validation. Scoped whitespace validation passed. No Full, publication, canonical product update or further native/provider action has been executed by this implementation agent; those gates remain pending.
