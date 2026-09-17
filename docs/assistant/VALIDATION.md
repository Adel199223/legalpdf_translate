# Validation guide

Use the smallest meaningful check first. Do not claim a test passed until its process and terminal result are known. [HANDOFF.md](HANDOFF.md) and the [completed Arabic acceptance plan](exec_plans/completed/2026-09-17_arabic_normal_browser_acceptance.md) identify the current build and latest outcomes; the [ordinary integration plan](exec_plans/completed/2026-09-16_ordinary_browser_integration.md) retains earlier qualified results. This page defines the validation tiers.

## Interpreter and isolation

Project tests use `C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe`, available as `.\.venv311\Scripts\python.exe` in a configured worktree. Do not use bare/global Python for pytest. Run from the intended worktree and record its path, branch and HEAD.

Use fresh temporary settings/output roots and existing synthetic fixtures. Never point tests at live Gmail, credentials, the user's app data or private outputs by default. Browser `shadow` mode alone does not disable provider, auth or native operations. A named isolated acceptance runner can have a stricter socket boundary than the ordinary browser/API test harness; do not weaken that boundary to make a different test fit it.

## 1. Targeted tests

```powershell
.\.venv311\Scripts\python.exe -m pytest -q tests/test_source_review_browser_state.py tests/test_formatting_review_browser_state.py
.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_source_review_api.py tests/test_shadow_web_formatting_review_api.py
```

Choose affected modules and real regression cases rather than repeating broad suites without a new change or unresolved concern. Source/accounting changes need guard, resume and failure-path coverage. Formatting changes need content/mapping/package checks, including Arabic where relevant. A synthetic SDK/Word test is not a real-provider/native acceptance result.

## 2. Complete repository pytest

```powershell
.\.venv311\Scripts\python.exe -m pytest -q -ra tests
```

Use the complete collection before merge and after integrated code/test/workflow changes when required. Retain the full terminal count, failures, skips, duration and JUnit when available. For a long run, use a bounded owned launcher, capture logs and freeze its named source/test snapshot. Do not duplicate collection or start another full run merely because the active run is quiet.

## 3. Standard validation wrapper

```powershell
powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1
powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full
```

The wrapper runs focused browser tests, compileall, relevant docs validation and workspace hygiene. `-Full` adds Gmail unit coverage and separate groups of seven source-review and six formatting-review test files. **Full is not the complete repository pytest collection.** Preserve its existing Gmail filters and interpreter selection; it does not authorize live Gmail or native Word operations.

## 4. Documentation and policy checks

After docs/manifest/policy-validator changes, run the direct Dart tools on this machine (or the same current runtime resolved by the wrapper):

```powershell
& 'C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe' test/tooling/validate_agent_docs_test.dart
& 'C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe' tooling/validate_agent_docs.dart
& 'C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe' tooling/validate_workspace_hygiene.dart
```

The known `Unable to find AOT snapshot for dartdev` wrapper error is distinct from the direct-Dart fallback. Record the wrapper failure and an actual successful fallback; do not infer success if the fallback did not finish. Standing Docs Sync authorization does not waive docs/manifest consistency checks.

## 5. Browser and rendered-document evidence

For browser checks, record the actual build/asset version and owned isolated workspace, use fictional inputs where possible, and test the real UI path. Source review, exact operation recovery and artifact download should use the public APIs rather than injected accepted commits. A new CSS file on disk does not change an old server's immutable static snapshot; verify the served asset.

For a perceptual DOCX change, retain exact source/output identities and inspect the actual relevant pages. Programmatic package/text checks and visual/native acceptance answer different questions. Translation DOCX creation does not require automatic Word export. Any necessary native or paid operation must follow its current explicit scope, retained ownership and one-shot recovery rules; failed/consumed helpers are not reusable.

When a visual review appears to lose repeated headers or footers, inspect the relevant image individually and corroborate the actual file content before removing source text or diagnosing a renderer defect. Preserve and explicitly supersede incorrect review aids. For Arabic literal failures, reproduce with the exact accepted source, saved glossary contract and unchanged provider response; a probe without the actual contract is not proof of a product defect. Offline validation of retained paid bytes remains distinct from a completed ordinary run.

Successful source preparation proves valid supported input, not complete entity attribution. After a demonstrated attribution gap, inspect the remaining document’s source-proven names and reference fields before another paid run. Distinguish a missing source span from a genuine provider omission or untranslated ordinary word; keep strict validation for the latter. Literal compliance alone does not establish legal fidelity. Bilingual review must check tense, mood, conditional gates and legal effect, including whether an instruction has become a claim that the action already happened. Saved glossary/addendum influence must be checked under the exact run contract before changing prompts or preferences.

For citation failures, compare actual source and target citation occurrences with parser results, including valid target-language punctuation. A closed coordinated citation followed by Arabic comma U+060C must not be mistaken for missing coverage merely because the parser recognizes only ASCII closing punctuation. Keep true missing, extra or reassociated citations rejected. Pure probes or retained-response revalidation do not create an accepted run, authorize another dispatch or repair a separate linguistic defect.

## Readiness and historical results

PR #298 publication (2026-09-17): exact head `b3480e092530ab65d569842ba488a3d7c1e6f102` completed required Windows and Linux CI successfully. All four PR/push Windows and Linux jobs succeeded. Both complete pytest runs passed 6,607 tests with two dependency-deprecation warnings each (PR 2,314.94 seconds; push 2,201.84 seconds); each targeted core run passed 34 tests. Original failed runs remain preserved. Canonical `main` was updated to merge `751185fca959ab074c328050adf0184f5db76d2c`. Fresh owned isolated verification result was recorded at 2026-09-17T19:44:52.8118593Z and checked runtime identity, asset version `3a37cb2d78df` and every one of 93 served static assets against disk, with recorded process ownership and cleanup. During this isolated verification, no provider, OCR, Word readiness/native, Gmail, OAuth or external network operation was performed; saved settings, lifetime ledger and Word journal hashes were unchanged. This is HTTP/runtime/static evidence, not browser JavaScript execution or another document acceptance. The HTTP verification applies to that implementation revision. Later documentation-only revisions do not change its evidence scope or establish a new HTTP-tested HEAD. The [publication closeout](exec_plans/completed/2026-09-17_arabic_acceptance_publication.md) pins CI and the retained HTTP receipt.

Arabic closeout (2026-09-17): E (`_05`) completed nine genuine ordinary pages with12 settled calls and qualified bilingual review of147 immutable mappings. Its frozen runtime snapshot passed627 selected Full tests. Actual submitted formatting, same-nonce build recovery and browser download bind a60342-byte DOCX; complete package checks passed147 fragments,460 runs and five editable tables. One real native Word export produced nine PDF pages, all individually visually reviewed, with confirmed cleanup. Strict extraction remains nonexact because of five extra shadda in the PDF font Unicode map; a separate font trace reconciles that copy/search-text qualification, while the original report remains unchanged. No missing characters were found; character counts alone do not prove reading order or visual quality. Later formatting UI fixes passed24 focused tests, Chromium geometry checks with fictional service responses, and the final Full wrapper:629 selected passes,9 deselected, compilation and direct-Dart docs/hygiene fallbacks after the known AOT255 failures. This is not a complete-repository pytest run or evidence that E used the later UI fixes. Retain the initial build decline/recovery, original terminology concern with qualified disposition, all paid/zero-dispatch failures and the two consumed pre-native failures. Current spend and the unchanged original USD10 budget are recorded in [HANDOFF.md](HANDOFF.md).

A passing targeted suite, Full wrapper, full pytest run, real browser check and real-document acceptance are separate evidence. Report unexecuted or unavailable checks plainly. Before publication, use [COMMIT_PUBLISH_WORKFLOW.md](workflows/COMMIT_PUBLISH_WORKFLOW.md), exact-head required CI and the user’s current scope.

Detailed historical validation, Google Photos/native cases and old PR-specific coverage are retained in the [dated public guide](history/2026-09-16_front_doors/VALIDATION.md), which discloses one fictional personal-name substitution. The exact original remains privately preserved. Its old budgets, pending instructions and stage tokens are historical, not active execution authority.

For reviewed-source startup failures, distinguish a zero-dispatch job from translation failure. Public fixed diagnostics may intentionally omit the originating exception. Preserve actual job/accounting and browser timing, then reproduce suspected concurrency using disposable fictional evidence; overlapping requests alone do not prove the hidden exception. Keep normal same-review read serialization separate from rejection of an unrelated operation holding the run workspace.

When an Arabic PDF extraction differs from the reviewed DOCX, preserve the strict report and inspect the actual font mapping and affected glyphs before classifying the difference. Font-to-Unicode expansion can affect copy/search text while visible glyphs remain correct. Retain exact bytes, independently inspect every affected page, and label a reconciled extraction limitation explicitly; never strip arbitrary Arabic letters or diacritics to manufacture an exact pass.
