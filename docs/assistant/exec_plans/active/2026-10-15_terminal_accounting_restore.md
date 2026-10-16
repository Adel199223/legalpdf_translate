# Restore pinned terminal translation accounting

## Goal and provenance
Repair the observed normal Recover failure after terminal-capsule import. New worktree `C:/Users/FA507/.codex/worktrees/terminal-accounting-restore-20261015/legalpdf_translate`, branch `feat/terminal-accounting-restore-20261015`, exact base `2f8f8c523ccb1bc680ce93b4cc5d3920b2ea8cfa`. Earlier accepted address/footer worktrees remain untouched. Parent owns canonical/UI/runtime.

## Cause and scope
Fresh completion retains its real workflow accountant. Terminal import reconstructs the job and layout identity but leaves `_completed_accountant=None`, so layout accounting rejects the restored job before authorization. The original five-call translation ledger and three paid layout responses remain unchanged; the failed recovery wrote only its direct-revalidation intent.

## Implementation
1. Add a strictly read-only, existing-journal pinned restore mode to the real DispatchAccounting class. Never create a missing ledger or lock, adopt current pricing/limits, append calls, or ignore a changed pinned journal.
2. Restore terminal accounting only from the exact checkpoint reference and capsule-pinned journal; validate source/context/language/selection/start/protocol identity and saved requested model. Preserve cumulative journal cost independently from an older failed job seed. Keep unsupported hard-budget/BLOCK restoration unavailable rather than downgrading it.
3. Prove actual terminal export/import into a fresh manager/app, immediate verified budget availability, and normal three-response retained Recover with zero SDK calls, original charge once, unchanged ledger and response bytes. Cover missing/mismatched/tampered/unknown/in-flight and hard-budget fail-closed cases.
4. Run focused validation and independent review before freezing a complete parent patch. No live API, provider, Gmail, native, runtime or publication actions here.

## Acceptance and limitations
Capsule import remains read-only and atomic. Only the new layout operation can write its own authorized recovery records; it cannot mutate translation history. A restored hard budget remains unavailable until its exact durable budget can be safely restored. Parent owns integrated Standard/Full and actual normal UI recovery, native content review and final Gmail acceptance.

## Results
Implementation restores the real `DispatchAccounting` object from the capsule-pinned journal in read-only mode. It restores saved pricing and limits, validates the checkpoint/run/model identity and retained event consistency, and forbids begin/finish/save operations or creation of missing accounting files/locks. Unsupported hard budgets and absent pricing catalogs remain unavailable; legitimate unknown spend and in-flight calls cannot authorize layout.

The offline actual-capsule probe restored three jobs and two sessions with a retry-capable accountant for the completed order, original translation cost USD0.44442860, layout cap USD3.8884286 and remaining USD3.217690. All 81 pinned input hashes and the capsule hash remained exact. This probe performed no Recover, output assembly, provider, Gmail or native operation. The first probe encountered a concurrent read-only capsule validator's retained layout lock and failed without changing input bytes; its serialized retry passed.

Focused final validation and the frozen patch receipt belong to private `order_rerun_20261015_01/terminal_accounting_restore_01`. The final focused result is recorded there rather than inferred from the initial exploratory run. Parent owns independent review, application, Standard/Full validation and actual app acceptance; none is claimed by this implementation worktree.
