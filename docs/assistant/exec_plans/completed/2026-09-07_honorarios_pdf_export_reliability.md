# Reliable Word PDF export for requerimentos de honorarios

## Goal and non-goals

Make the existing honorarios DOCX-to-PDF operation succeed unattended on the user's Windows host, with bounded failures and safe recovery. Keep the editable honorarios DOCX and verify the new PDF before reporting success. Translation deliverables remain DOCX only.

Do not change translation layout, models, prompts, legal wording, monetary calculations, routes, submitted values, Gmail/native-host contracts, or database schemas. No translation/OCR calls, live Gmail access, draft creation, sending, Office repair/install, Trust Center changes, or publication are authorized by this repair request. Do not merge the unrelated quality research branch wholesale.

## Scope

In: Word PDF worker, launch/readiness checks, process/document ownership, bounded concurrency/retries, fresh-PDF verification, shared browser/Qt honorarios recovery, synthetic local acceptance and relevant documentation.

Out: changing Office security protections; closing/restarting unknown Word processes; replacing Word with another rendering engine without a demonstrated need and a new decision; new translation functionality or PDF translation outputs.

## Worktree provenance

- Worktree: `C:/Users/FA507/.codex/legalpdf_translate_honorarios_pdf`.
- Branch: `feat/honorarios-pdf-export` (repository-required major-work prefix).
- Base/target integration branch: `main`.
- Base SHA: `9afe1d05577f271a8618969e8f0be31eb8641a3e`.
- Approved floor: `4e9d20e`; ancestry verified before worktree creation.
- Status: noncanonical diagnostic/implementation checkout. Canonical main is unchanged.
- Preserve the existing merged formatting checkout and local-only research checkpoint `66a7374a2b874f59994215177af4ff48d1d5f100`. Prior blocked local cleanup is not retried by this task.
- If an app is launched here, use isolated shadow state and a non-live port; record exact build identity. No branch switch or restart of canonical live runtime.

## Interfaces and contracts

Preserve public signatures and serialized `WordAutomationResult`, existing readiness payloads (`launch_preflight`, `export_canary`, `finalization_ready`), Qt signals, routes and manual retry/select-existing-PDF/open-folder behavior. Improve diagnostics within existing fields where possible. Keep Gmail readiness fail-closed; passing a launch probe alone is not export acceptance. Tests must continue to stub Gmail external writes.

## Stage gates and current status

This is risk-triggered complex work: shared browser/Qt/Word behavior and potential interference with open user documents. Follow `STAGED_EXECUTION_WORKFLOW.md`.

- Stage 1: read-only diagnosis, baseline tests, implementation plan. Complete; `NEXT_STAGE_2` received.
- Stage 2: implementation and automated validation complete. Bounded native startup diagnostics found two new-helper defects, now corrected; the replacement launch design still needs native acceptance. `NEXT_STAGE_3` received.
- Stage 3: complete. Native export, visual, coexistence, bounded recovery and full validation passed. The pre-existing native Qt layout-test diagnostic remains recorded separately. The user subsequently approved touched-scope documentation sync, integration into main and GitHub publication; the reviewed PR lifecycle is authorized.

Earlier continuation tokens belonged to the translation-quality project; they do not authorize stages of this new repair.

## Stage 1 evidence and diagnosis

1. Canonical main and local `origin/main` were clean and identical at the base SHA. Created the new worktree from that baseline; no production code changes.
2. Word and Windows PowerShell resolve locally (`Office16/WINWORD.EXE` and Windows PowerShell v1.0). The host is Windows and matches the app runtime. No Gmail/listener operation was needed. Installation exists; real export readiness remains unverified this pass.
3. Two existing Word processes were observed, started on the preceding day, with no main-window handle. Their ownership/document state is unknown. They were not hidden, activated, closed, killed, or otherwise altered. Their existence does not prove the cause of the stall.
4. Proven code hazards in `word_automation.py`: PDF export and launch preflight attach to active Word and then set `Visible = false` without restoring visibility. Export also activates the target and closes the returned document without proving it was not already user-open. These hazards make the current probe inappropriate as a supposedly harmless diagnostic against unknown user Word state.
5. Proven diagnostic defect: Windows Python 3.11 can raise `TimeoutExpired` without stdout/stderr. `_run_command` derives the last phase before draining helper output and never recalculates it afterward. A fully mocked local reproduction returned failure code `timeout` and an empty phase although trailing output contained `open_document`. No real subprocess was launched by that reproduction.
6. Proven verification gap: actual export checks only destination existence; the canary checks only the PDF header. Neither is sufficient proof of a complete, newly produced PDF corresponding to this request. Export currently writes directly to the final destination.
7. Current cleanup targets the PowerShell helper tree; that is not proof of Word COM-server cleanup. No verified Word PID/creation identity is recorded. Cleanup wording also confuses attempted with succeeded.
8. Browser honorarios export performs preflight/export and automatically retries after timeout; Qt already uses an asynchronous worker and offers manual recovery. Readiness cache is not a shared export lock. Ambiguous cleanup can allow competing attempts.
9. Historical March 30/April 19 records show exports succeeded after `/automation` bootstrap. September research records show hidden COM still stalled after other safety fixes, while manual Word UI export worked. Neither history proves the present root cause. Preserve bootstrap as a hypothesis to test rather than blindly removing or retaining it.
10. Existing research has some useful safeguards/tests, but still reuses active Word, acknowledges an ownership race, and changes unrelated Arabic alignment. Review individual changes; do not copy that module wholesale or describe it as a proven cure.

### Baseline validations

- Canonical `.venv311/Scripts/python.exe -m pytest -q tests/test_word_automation.py tests/test_honorarios_docx.py`: **78 passed in 4.94 seconds**, exit 0.
- Fully mocked Windows-timeout reproduction: defect observed as described above; cleanup and subprocess creation mocked.
- Independent read-only audit confirmed ownership/visibility, trailing timeout output, fresh-PDF verification, caller/retry and cleanup gaps.
- New-worktree agent-docs validation passed using the documented direct-Dart executable. `git diff --check` passed; only this new plan is pending.
- No native Word export attempt this stage because the existing path can alter unknown user Word instances. No generated documents, paid calls, credential changes, private document edits or Gmail operations.

## File-by-file implementation steps

1. `src/legalpdf_translate/word_automation.py` and focused tests:
   - Make unattended export and readiness independent of user-owned Word documents. Prefer a dedicated app-owned Word instance; prove process identity/creation and that it was not pre-existing before altering state or closing anything. Do not equate `New-Object` with ownership. Fail safely when ownership cannot be established.
   - Use a unique staged source copy and staged PDF where needed to avoid collisions with a user-open target, without changing the source DOCX or existing valid destination. Validate source/destination type and reject path collisions.
   - Explicit read-only, hidden/no-activation/no-MRU open; avoid global persistent Word changes. Do not enable macros, remove security labels, dismiss security prompts automatically, or weaken Trust Center settings. Preserve document content and print layout.
   - Bound startup/open/export/cleanup and lock acquisition. Serialize app export/canary operations across relevant worker processes, not just per cache key. Track only owned helper/Word identities; never kill by image name or a before/after PID difference alone.
   - Retain primary failing phase/HRESULT separately from cleanup phases. Fix empty Windows timeout output handling, sanitize diagnostics, and distinguish helper cleanup from confirmed Word cleanup.
   - Reopen staged PDF with the existing PDF library, require readable pages and expected canary text, then promote only a verified fresh output. On any failure retain original DOCX and previous good PDF; do not return a stale PDF as this operation's success.
   - Keep readiness on the same export path. Do not let cached canary success override an actual export failure. Preserve existing cache invalidation behavior.
2. `src/legalpdf_translate/interpretation_service.py`, `src/legalpdf_translate/qt_gui/worker.py`, and only necessary recovery code in `qt_gui/dialogs.py`:
   - Remove unsafe automatic re-probe/re-export after ambiguous timeout. At most one justified bounded retry after confirmed cleanup; otherwise use the existing manual recovery flow.
   - Preserve asynchronous Qt behavior and existing serialized responses. Avoid unnecessary extra launch/open/quit cycles and overlapping readiness/export operations.
3. `tests/test_word_automation.py`, `tests/test_honorarios_docx.py`, and relevant interpretation/runtime/Gmail service tests:
   - Cover visibility/focus preservation, existing user-open target, ownership ambiguity, PID reuse, startup failure, timeout before identity capture, stale/empty/malformed PDF, valid-output promotion, locked paths, accented/spaced/apostrophe paths, concurrency and clean subsequent retry.
   - Cover empty `TimeoutExpired` plus trailing markers, primary failure surviving cleanup errors, accurate cleanup reporting, and no sensitive script/document dump in normal messages.
   - Preserve Gmail mock gating, Qt signals, DOCX retention and translation-only DOCX output. Never launch Word implicitly in the normal test suite.
4. Add a narrowly scoped opt-in diagnostic/acceptance helper under `tooling/` if required:
   - Use synthetic honorarios data, record source/output hashes, elapsed times, phases and owned process identities. No live settings dumps, credentials or real document text.
   - Refuse implicit real Gmail use and unknown-process cleanup. Keep generated evidence in a task-local ignored/private directory.
5. Synchronize only relevant `APP_KNOWLEDGE.md`, `HANDOFF.md`, `VALIDATION.md`, user-guide and repeated-issue notes after implementation. Follow the repository Docs Sync approval rule when applicable. Keep this plan current.

## Tests and acceptance criteria

Stage 2: regress each defect before fixing it; run targeted Word/honorarios/interpretation/browser-runtime/Gmail-contract suites, full pytest, and `scripts/validate_dev.ps1 -Full`. Use `.venv311/Scripts/python.exe` with imports proven to point at this worktree. Record the known Dart AOT wrapper failure only with a successful direct-Dart fallback. Rerun affected native Qt checks serially if the COM diagnostic recurs; do not suppress it or call offscreen success native export acceptance.

Stage 3: run canary and actual translation-kind/interpretation-kind honorarios export through the same shared caller paths, using synthetic data. Require consecutive clean warm runs and cold runs only when a genuinely safe cold condition exists; never close unknown user Word processes just to obtain that condition. Exercise coexistence with a deliberately created unsaved synthetic Word document and already-open target recovery. Confirm unchanged source bytes and unsaved synthetic content/window state, readable complete PDFs, bounded timeout behavior, no leaked owned helpers, and a healthy next export. Validate an isolated browser export and Qt worker path without any email action.

Render the actual Word-produced PDFs to page images and inspect every page for missing text, spacing, clipping, signature/closing placement and accented Portuguese text. Use bundled Poppler resolved from workspace dependencies. Packaged LibreOffice was not present in the runtime inventory; do not substitute user-installed LibreOffice as proof of Word export reliability. If packaged DOCX renderer cannot run, record that limitation; real Word PDF plus complete PNG inspection is the relevant native acceptance evidence. Do not change the established honorarios design to make the test pass.

## Rollout and fallback

Keep canonical main stable until accepted. GitHub integration is a separate approved lifecycle after validation, not part of this stage. Preserve local Word-only recovery and user-selected-PDF handling while export is unavailable. If a bounded native test still stalls after safety/diagnostic repair, report the precise phase and ownership evidence and request only the necessary host action; do not claim a safety patch fixes export.

## Risks and mitigations

- User data loss: never close unknown documents/instances or retry ambiguous ownership; stage output before publication.
- Office state or installation fault: distinguish installed from COM-ready/export-ready; no account, installation or security modifications without new authorization.
- Duplicate/background Word instances: explicit ownership plus bounded lock and teardown; existing process age/window visibility alone is not ownership evidence.
- False positive from tests or manual export: mocked tests prove contracts, not host success; manual UI export proves rendering, not unattended readiness.
- Scope creep: reuse only relevant safeguards from research; keep translation, honorarios content, Gmail and model policy unchanged.

## Assumptions and decision locks

Word remains the intended PDF renderer. The user wants honorarios PDFs, not PDF translations. Synthetic local exports are normal implementation testing; no private financial/case data is needed. Unknown Word processes remain untouched. Do not silently increase retries/timeouts to mask the hang. The choice of safe launch/bootstrap mechanism is evidence-dependent and must be recorded after native diagnosis; no mechanism is promoted merely because it constructs a COM object.

## Primary API references checked 2026-09-07

- [Microsoft Documents.Open](https://learn.microsoft.com/en-us/office/vba/api/word.documents.open): explicit ReadOnly, AddToRecentFiles, Visible and open-document behavior.
- [Microsoft AutomationSecurity](https://learn.microsoft.com/en-us/office/vba/api/word.application.automationsecurity): macro security is separate from ordinary alert suppression; preserve user security settings.
- [Microsoft ExportAsFixedFormat](https://learn.microsoft.com/en-us/office/vba/api/word.document.exportasfixedformat): full-document PDF export and protection/label retention.

## Stage 2 implementation evidence and decisions

### Changes implemented

- Shared export lock and content-free durable phase journal; conservative quarantine after uncertain cleanup. Only the retained PowerShell helper handle may be terminated on timeout, never unknown Word processes or a process-name tree.
- Fresh staged DOCX/PDF handling, original/prior-PDF snapshots, PDF parsing and canary text checks before atomic promotion. Reject unsafe source aliases, origin-marked files, macros and external-content references; preserve permitted hyperlinks and protection behavior.
- Browser and Qt callers make one bounded export attempt. Remove automatic timeout re-probe/re-export; preserve asynchronous Qt and explicit manual recovery. A stale worker-finished signal cannot discard the current retry worker.
- Windows trailing phase recovery fixed. Raw subprocess stderr, private scripts and document text are not returned as diagnostics. Helper setup, primary COM and cleanup failures remain distinct.
- Independent review found two additional runner defects: pipe errors could leave the helper running, and a timeout before initial journaling could make quarantine unrecoverable. Red regressions reproduced both; bounded retained-handle cleanup and parent-confirmed helper-exit evidence now cover them. Corrupt journals still fail closed.

### Native diagnostic evidence (not export acceptance)

1. Startup-only probe, no DOCX opened: helper stopped before Word launch because PowerShell converted a null File.Replace backup argument to an invalid empty string. Fixed using `[NullString]::Value`; regression executes state replacement in real PowerShell without launching Word. No new Word process in this attempt.
2. Second startup-only probe: failed after 2,931 ms at `capture_word_identity`, HRESULT `0x80004002`. Initial implementation used unsupported `Word.Application.Hwnd`; Word documents `Window.Hwnd`, not that Application property. This is a helper defect, not evidence of Office installation corruption.
3. Helper PID 31412 exited; newly observed Word PID 42944 (local start 2026-09-07 16:35:18) could not be bound to the COM object and was deliberately retained. Earlier unknown Word PIDs 7156 and 32096 were untouched. The diagnostic journal under ignored `tmp/stage2_word_probe_fixed` remains quarantined. Do not bypass it by changing APPDATA for another native attempt, guess ownership from PID differences, or force-close any of these processes.
4. No honorarios/reference document was opened or exported. These diagnostics do not prove unattended export works. Real repeated exports and visual acceptance remain Stage 3.

### Evidence-based startup amendment

Replace COM-first launch with process-first launch: start the resolved WINWORD executable with the **single documented `/w` switch**, hidden startup intent, and retain the returned process identity/handle. Bind only that process's `_WwG` child through documented `AccessibleObjectFromWindow(OBJID_NATIVEOM, IID_IDispatch)` to `Word.Window`; verify its HWND maps to the same live process before obtaining Application and making mutations. Never create a second COM instance or attach via GetActiveObject. Null/exited/redirection or ambiguous binding must fail closed rather than chase another process.

The `/w` bootstrap is a deliberately new blank document, not a user file. Keep its exact object as the anchor and reject custom/nonblank content, extra documents or protected-view windows. Recheck content and ownership before closing only that bootstrap and the exact staged target. Do not set Saved=true to erase a dirty state or change Normal templates/add-ins/security. Startup loads the existing trusted Word environment; native coexistence is still an acceptance requirement, not guaranteed by mocks. Windows PowerShell 5.1 requires shell execution for ProcessStartInfo Hidden intent; do not assume .NET 8 behavior.

This replaces the unsupported HWND assumption without changing the task's renderer, document content, user settings, or process-safety constraints. Stage 3 must validate it on the actual host after safe recovery of the retained diagnostic session.

Primary references checked 2026-09-07:

- [Microsoft Office command-line switches](https://support.microsoft.com/en-us/office/lifecycle/command-line-switches-for-microsoft-office-products): Word `/w` creates a new instance with a blank document; multiple startup switches are unsupported.
- [AccessibleObjectFromWindow](https://learn.microsoft.com/en-us/windows/win32/api/oleacc/nf-oleacc-accessibleobjectfromwindow): Word `_WwG` exposes the native Window object.
- [Word Window.Hwnd](https://learn.microsoft.com/en-us/office/vba/api/word.window.hwnd): supported window handle source.
- [ProcessStartInfo.WindowStyle compatibility](https://learn.microsoft.com/en-us/dotnet/core/compatibility/core-libraries/8.0/processstartinfo-windowstyle): pre-.NET 8 behavior differs with UseShellExecute=false.

### Validation progress

- Artifact layer: 68 tests passed after new security regressions.
- Honorarios/runtime/Gmail caller suites: 123 passed; later focused Qt lifecycle regression passed.
- Migrated Word/launch-isolation suites: 29 passed before startup amendment; rerun required afterward.
- Runner/control regressions: 19 passed in 0.39 seconds, including the two independent-review failures fixed above, safe process-first recovery and accurate post-publication lock-error reporting.
- Final Word helper script suite: 35 passed in 19.63 seconds. This includes actual production C# compilation under Windows PowerShell 5.1, story-only XML validation (style numbering is not substantive content), generated-helper parsing, and complete helper execution with all process/native/Word calls replaced by fakes. Fake executables are nonexistent task-local paths; no native Word launch occurs in the suite.
- Final combined Word runner/control/legacy/launch-isolation suites: 48 passed in 1.05 seconds. Artifact/runner/caller integration group: 191 passed in 20.69 seconds before the final process-first recovery test was added.
- `scripts/validate_dev.ps1 -Full`: passed, exit 0. Browser group 233 passed in 186.10 seconds; Gmail groups 2 passed and 5 passed/9 deselected; compileall passed. Known Dart AOT launcher failures occurred for docs and hygiene, followed by successful direct-Dart fallbacks for both validators. Log: ignored `tmp/stage2_validate_dev_full.log`.
- Full pytest: **2,173 passed in 312.22 seconds**, exit 0, run serially after the wrapper. Log: ignored `tmp/stage2_pytest_full.log`.
- The previously affected small-screen honorarios dialog test was rerun separately with `QT_QPA_PLATFORM=windows`: **1 passed in 1.26 seconds**, exit 0; the `0x8001010d` COM diagnostic did not recur. This proves the dialog check only, not Word export readiness.
- Assistant Docs Sync was requested asynchronously this turn; no response yet. Defer product-doc synchronization unless approved; this implementation record is kept current independently.

## Stage 2 handoff packet

- Changed files: shared runner `src/legalpdf_translate/word_automation.py`; new isolated helper, lock/recovery and staged-artifact modules `word_pdf_script.py`, `word_pdf_control.py`, `word_pdf_artifacts.py`; single-attempt callers in `interpretation_service.py`, `qt_gui/worker.py`, `qt_gui/dialogs.py`; corresponding Word/helper/artifact/control/runtime/honorarios/launch-isolation tests; and this plan. No routes, payload shapes, legal content, model policy, Gmail contracts or database changes.
- Validations: 2,173 full tests, full validation wrapper, 35 dedicated generated-helper tests including actual C# compilation, and the separate native Windows Qt regression, all passing. Mocked helper tests and XML checks are not real Word PDF acceptance.
- Risks: the corrected process-first exporter has not yet exported a real PDF on this host. The earlier failed COM-first diagnostic left one unbound Word session; it and pre-existing Word sessions remain untouched. Preserve the quarantine and resolve the session safely before new native attempts; do not erase the record or use another app-data root to evade it.
- Decision locks: Word remains the renderer; translations remain DOCX; honorarios originals/prior PDFs remain protected; use one explicit process-first `/w` launch with exact identity; no GetActiveObject, extra COM activation, process-name termination, automatic timeout retry, security weakening, paid calls or Gmail actions.
- Repository status: all repair edits remain uncommitted in the isolated feature worktree. Canonical main is clean and unchanged at the recorded base. No GitHub publication or integration occurred.
- Prepared Stage 3 prompt: On `NEXT_STAGE_3`, read this current packet, check the retained diagnostic state and arrange safe user-assisted recovery if Word ownership remains unknown. Do not bypass quarantine. Then run repeated synthetic canary and both honorarios caller paths with real Word, inspect every output PDF page, verify coexistence/source preservation/cleanup/retry, and document actual success or a precise blocker. No unknown-session termination or host repair without necessary authority. Stop before publication.
- Prepared post-acceptance integration prompt: Only after successful Stage 3 acceptance and separate publication authorization, follow `COMMIT_PUBLISH_WORKFLOW.md`, synchronize approved touched-scope docs, rerun required checks against the integration base, and carry out the normal reviewed branch lifecycle. Do not treat earlier translation-project GitHub approval as approval for this repair.

## Stage 3 recovery check

`NEXT_STAGE_3` was received. Read-only process inventory still shows exactly the retained Word PIDs 7156, 32096 and 42944, with the same creation times and no main-window handles. Their document/unsaved-work state remains unknown; none was attached to, hidden, closed or force-terminated.

The original diagnostic journal remains intact. The shared recovery check confirms the helper has exited, but Word is not absent and safe re-entry is false. No new Word startup, canary, DOCX/PDF generation, export or visual-acceptance run occurred. No quarantine reset, alternate-app-data bypass, host repair, Gmail action or publication occurred.

Next required user action: save open work and restart Windows to clear the unknown hidden Word sessions safely through the normal operating-system flow. Respect any save/cancel prompts. On return, recheck process identities and the existing journal; if safe re-entry succeeds, continue Stage 3 under its existing authorization. Another stage token is not required merely to resume after this recovery step.

### Agent-operated recovery request

The user subsequently requested direct computer control. The Computer Use plugin's supported `node_repl` / `@oai/sky` interface is available and initialized successfully (separate from the CUA browser tool). Desktop window inventory shows no targetable Word windows; Word's installed-app entry also has no windows. Do not claim desktop control is generally unavailable.

Opened the existing Windows Task Manager for inspection, without ending any task. Its state reports: "Accessibility is limited because the target window has higher Windows integrity than the Computer Use helper." No usable process controls were returned. No attempt was made to elevate the helper, bypass the integrity boundary, automate security prompts, launch another Word instance, or close any Word process.

The remaining choices are normal user-assisted save/restart recovery, or explicit informed approval to end exactly the three retained background Word processes despite the risk of losing any unsaved Word content. Broad "whatever it takes" direction is not treated as approval to discard unknown unsaved documents. Stage 3 exports remain unattempted and the original quarantine remains intact.

### Approved cleanup and resumed native testing

The user explicitly approved terminating exactly those three processes after the unsaved-work risk was explained. Before termination, retained process handles were acquired and WINWORD name, installed executable path and exact UTC start ticks were checked for every target: 7156/639243262804128146, 32096/639243262796598553 and 42944/639243921181526283. Only these three approved processes were terminated; each exit was confirmed. No files were deleted, other applications were not terminated, and Windows was not restarted. Unsaved changes are not guaranteed recoverable. This authorization is not blanket permission to terminate future or unrelated Word sessions.

The unchanged journal's recovery checks then returned `helper_exited=true`, `word_free=true`, `safe_to_retry=true`. Archived that failed Stage 2 journal as `stage2_failed_journal.json` in the same private state directory before its normal replacement by a new operation. No quarantine bypass or alternate app-data root was used.

The first Stage 3 startup-only preflight proved the new process-first mechanism: Word PID 3328, exact start ticks 639243946895690912, native Window binding and ownership all verified. It reached bootstrap close but rejected the subsequent document count (`remaining_documents_count`, `cleanup_ambiguous`, HRESULT 0x80131509). Word then exited and cleanup was confirmed; total 27,915 ms. No export or user document open occurred. The unexpected count is being investigated as an application/helper defect, especially PowerShell collection wrapping; no host/Office fault is inferred and the count safety check is not weakened.

### Confirmed last-document teardown defect

A second serial startup-only probe in the same APPDATA completed in 4,896 ms with confirmed Word cleanup. Content-free type diagnostics showed a genuine `System.__ComObject` collection, initially `System.Int32` Count 1, but a null Count after closing the final bootstrap. No Word process remained. An in-memory Scripting.Dictionary regression using the identical PowerShell collection-return mechanism tracked 1 to 0 correctly, so generic COM array wrapping was not reproduced.

The native evidence justifies retaining the exact sole, unchanged, identity-verified blank document/window anchor through scoped `Quit(0)`, after closing the exact staged target and verifying zero Protected View windows. The safe quit guard continues requiring exactly that bootstrap, matching content/saved state and process identity; it never permits arbitrary remaining documents. This replaces the close-last-document-then-count sequence, which disconnects native Word's automation surface. No user document or export artifact was involved in either probe.

The amended real preflight passed in 5,483 ms with confirmed cleanup. Its dedicated fake/PowerShell suite passed 36 tests. Updated the wrapper's obsolete close-bootstrap assertion and made the timeout/quarantine test independent of whether real Word happens to be running; all 22 wrapper tests passed.

The first actual canary then failed safely at `open_document` (`0x80070057`, 6,165 ms); source/output verification was not reached and Word cleanup was confirmed. Microsoft documents conflicting optional positional tails for [VBA Documents.Open](https://learn.microsoft.com/en-us/office/vba/api/word.documents.open) and [Interop Documents.Open](https://learn.microsoft.com/en-us/dotnet/api/microsoft.office.interop.word.documents.open?view=word-pia): the latter has XMLTransform at position 16 where the VBA signature lists NoEncodingDialog. The previously explicit 16-argument VBA-derived call can therefore pass false as a transform. Restrict the call to the common first 12 arguments ending in Visible=false, retaining ReadOnly=true, AddToRecentFiles=false, no reversion and omitted password/encoding values; request no repair or XML transformation. Real canary acceptance is still pending this correction.

The 12-argument native call successfully opened and verified the staged canary. The next operation failed at `export_pdf` with `0x80070057` after 5,811 ms, again with confirmed cleanup and no remaining Word process. Omit the unnecessary final optional FixedFormatExtClassPtr argument from [ExportAsFixedFormat](https://learn.microsoft.com/en-us/dotnet/api/microsoft.office.interop.word._document.exportasfixedformat?view=word-pia), preserving all fourteen explicit export settings, including KeepIRM=true. This avoids passing a missing-value sentinel where an optional alternate-renderer pointer is expected. It is a separate marshaling hypothesis pending native verification, not proof of an Office installation problem.

### Stage 3 actual export acceptance

The fourteen-argument export passed the native canary in 7,255 ms. The final success-path reporting fix also preserves the underlying cleanup flags/details instead of defaulting them to false. Both signatures and the anchored shutdown are now validated on this host, not only by mocks.

All application acceptance used the required `.venv311` interpreter, imports from this worktree's `src`, the same original `tmp/stage2_word_probe_fixed` APPDATA and one bounded call at a time. Synthetic names/addresses/payment placeholders only; no private financial data, Gmail, API calls or live server were involved. Artifacts and observer harnesses remain ignored under `tmp/stage3_acceptance` and `tmp/stage3_*.py`.

| Real operation | Native export time | Result |
| --- | --- | --- |
| Initial full canary | 7,255 ms | Readable PDF and expected canary text; clean shutdown |
| Translation-kind honorarios | 7,992 ms | One page, all 12 substantive paragraphs, DOCX hash unchanged |
| Interpretation shared caller | 6,262 ms | One page, all 12 substantive paragraphs, DOCX hash unchanged |
| Browser interpretation route | 6,444 ms | HTTP 200/status ok; one real export; shadow/live_data=false |
| Real Qt worker/QThread | 6,055 ms | One result signal; 55 main-loop heartbeats; correct result paths |
| Export beside unsaved Word document | 6,759 ms | Complete PDF; existing window/process/content unchanged |
| Export of already-open source DOCX | 6,623 ms | Complete PDF; original file hash/window preserved |
| Post-timeout recovery canary | 6,671 ms | Readable expected-text PDF, confirmed cleanup and healthy retry |

The browser case exercised actual `POST /api/interpretation/export-honorarios`, service, generator and exporter using FastAPI TestClient. Harness-only path injection and a transparent exporter observer isolate data/count dispatches; no export return value was mocked. It is route acceptance, not a claim of a browser-button click. Build metadata reports base `9afe1d05`; the tested distinguishing feature is this uncommitted worktree repair.

Rendered every page of all six retained Word-produced honorarios PDFs using bundled Poppler and inspected every PNG. Each is a clean one-page document with readable Portuguese accents, intact paragraph spacing, recipient positioning and closing/signature placement, no clipping or missing text. Unchanged honorarios layout/content, not a redesign. Updated each private evidence record to `passed_all_pages_poppler_png`. Disposable canaries perform full content parsing; their files are removed by the app's normal canary lifecycle and were not retained for visual delivery. No bundled LibreOffice was available or substituted; Word-native PDF rendering is the acceptance evidence.

### Native coexistence and bounded recovery

Using the Computer Use skill, launched Word normally and created `Document1` containing one synthetic unsaved sentence. The same Word PID 43840/start ticks 639243958655377737 and window 2953938 remained before/after a separate real export; screenshots showed the text and caret unchanged. Opened the synthetic honorarios source in that Word instance, exported through a private staged copy, and verified its source hash and visible saved state remained unchanged. Closed only the unchanged source normally. The unsaved safety sentence was then saved to a new task-local DOCX and compared exactly with the original typed text before closing Word normally; no discard or force termination was used for these tests.

A deliberately short 0.2-second export allowance exercised real helper startup timeout: 238 ms wall time, timeout reported, retained helper stopped, original DOCX and previous good PDF hashes unchanged, safe re-entry true. No COM-stage timeout was deliberately induced and no unknown Word process was killed. The subsequent full native canary passed. Final read-only identity checks returned `status=succeeded`, `cleanup=confirmed`, `helper_exited=true`, `word_exited=true`, `word_free=true`.

### Final automated validation

- Dedicated script suite: 37 passed, including red regressions for last-document disconnection and both optional-argument incompatibilities.
- Runner/control/artifact/legacy isolation set: 116 passed in 5.13 s before the additional successful-canary metadata regression; wrapper suite then 23 passed in 0.71 s.
- Full pytest: **2,176 passed in 357.78 s**; log `tmp/stage3_pytest_full.log`.
- Final `validate_dev.ps1 -Full`: **passed**, exit 0. Browser suite 233 passed in 204.26 s; Gmail mocks 2 passed and 5 passed/9 deselected; compileall passed. Known `dart run` AOT launcher failure (255) occurred, and the documented direct-Dart fallback passed both docs and workspace hygiene. Log `tmp/stage3_validate_dev_full.log`.
- Explicit native small-screen Qt test: assertions passed (1 in 1.99 s), but the known `0x8001010d` diagnostic recurred at its `app.processEvents()` call. A separate serial native rerun after full validation also passed (1 in 1.44 s) with the same diagnostic; log `tmp/stage3_native_qt_serial.log`. Windows SDK identifies it as RPC_E_CANTCALLOUT_ININPUTSYNCCALL. Independent review confirmed this pre-existing March test only constructs/shows a dialog; export is never invoked and native Word calls are fixture-blocked. The repaired real asynchronous export case passed. No diagnostic suppression or unrelated Qt/event-system repair; retain this as a separate known limitation.
- Canonical main remains clean and unchanged. No commit/push/merge, Office repair or host-security modification. Relevant product-doc sync remains deferred pending the already-asked Docs Sync approval; this ExecPlan records current evidence.

### Stage 3 handoff

The honorarios export repair is accepted by actual same-host synthetic execution, complete-page visual review and the regression suites above. No ordinary translation PDF workflow was added. No production model, legal wording, rates, API contracts or user documents changed. Private evidence stays out of Git.

The user approved documentation sync, integration and GitHub publication after this acceptance packet. The implementation plan is closed before merge as required by the commit/publish workflow. Publish only the repair plus touched-scope documentation from the approved-base lineage; require green checks on the exact PR head, then merge and synchronize canonical main. The known native Qt layout warning is not represented as fixed. Preserve the unrelated quality checkpoint and prior formatting worktree.

### Approved integration closeout

- Rechecked origin/main at `9afe1d05577f271a8618969e8f0be31eb8641a3e`; this worktree contains both the latest base and approved floor `4e9d20e`.
- Docs Sync approved and applied only to honorarios behavior/recovery, validation, handoff/resume and the existing repeated-issue record. No new translation/model policy or workflow contract.
- The system GitHub CLI credential is invalid; use the connected GitHub service for PR/check/merge operations and existing Git credential handling for transport. Do not replace credentials or require browser authentication solely for publication.
- No LegalPDF listeners or server processes were active at integration preflight. Canonical main stays stable until the PR is merged; no live Gmail interaction is authorized or required.
- Keep synthetic acceptance artifacts/logs privately outside Git under `C:/Users/FA507/.codex/legalpdf_translate_private_benchmarks/honorarios_pdf_export_2026_09_07` during cleanup. Published source/tests contain no generated documents, private settings, credentials or browser captures.
- Record actual push, checks and merge outcomes in the PR and final handoff rather than inventing the future merge SHA in this pre-merge commit. Rerun focused validation from canonical main after integration. Retain manual PDF recovery and the known Qt diagnostic.

## Stage 1 handoff packet

- Changed files: this ExecPlan only, in the new worktree. No application implementation yet.
- Validations: 78 baseline tests; mocked timeout reproduction; same-host installation/process inventory; independent code audit; base-floor ancestry.
- Risks: current exporter can interfere with user Word; actual stall location remains unproven; two unknown pre-existing processes are deliberately retained.
- Locked decisions: honorarios-only PDF scope, preserve translations/Word originals, safe ownership before native tests, no Gmail/security/paid operations, no unreviewed research merge.
- Prepared Stage 2 prompt: On `NEXT_STAGE_2`, implement the scoped ownership, diagnostic, staged-output and bounded-retry repair above; begin with red regressions and use only safe bounded native diagnostics after safeguards. Complete targeted/full validation and stop with evidence for Stage 3.
- Prepared Stage 3 prompt: On `NEXT_STAGE_3`, perform repeated same-host synthetic real-path exports and every-page PDF visual inspection, including coexistence/recovery. Report genuine unattended success or a precise remaining host blocker. Preserve main and seek the normal publication approval after acceptance.
