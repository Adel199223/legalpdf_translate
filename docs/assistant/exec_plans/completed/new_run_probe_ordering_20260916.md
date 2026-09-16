# Preserve new-run output preflight ordering with run ownership

## Completed scope, 2026-09-16

Status: completed locally and moved under PLANS rules 8 and 9; this does not imply publication or canonical-main promotion.

All 16 preflight and 8 ordering cases passed in F3. Only genuinely absent roots are probed before lock creation; retained roots and rival evidence keep locked validation.

Current full validation: repository F3 passed 6,477 tests with zero failures/errors/skips (result `0cceeb4c`, JUnit `ed5c1d79`); separate Standard Full SF2 passed (`adfcafe8`). Both retained the same 481-file source/test/script snapshot `bec79f29`. These results validate this bounded integrated scope; real French native/visual acceptance and final parent/docs closeout remain separate and pending.

The original implementation/authoring plan follows as historical scope and is superseded by this executed outcome where its status says pending. Exact pre-closeout bytes are retained privately in `application_docs_modernization_20260916_01/final_scoped_closeout_beforeimages_01`.


## Goal, scope and provenance

The full-regression candidates were authoritatively reproduced by root: both
fresh protocol paths create a run directory and permanent lock before a denied
output probe. Preserve the original unchanged-output contract and the stable OS
lock. Do not weaken existing tests or change legacy defaults, source-review
ownership, provider behavior, public routes or saved settings.

W is the approved concurrent worktree
`C:/Users/FA507/.codex/legalpdf_translate_reviewed_regions`, branch
`codex/reviewed-regions`, HEAD `4780a2e16c32adf7af7479656f0b5fafdff83224`.
Root owns integration into R and eventual canonical `main`. This W-only scope
does not alter R while its full regression snapshot remains frozen. Exact R and
W workflow baselines are preserved in
`new_run_probe_ordering_beforeimages_20260916_01`.

## Approved ordering

After the existing read-only configuration and reviewed-source prerequisites,
compute the same deterministic run path including Gmail batch scope. Only an
explicit `resume=False` with an absent run path gets the existing owned output
probe before lock-directory creation. Then take the unchanged run lock. Require
the locked root to contain only its stable lock and no retained checkpoint;
otherwise stop before the body, preserving the competing owner's files.

Pass a private one-call `output_preprobed=True` argument only for that pristine
new-run path, suppressing its second probe. Existing directories, browser source
review claims and all resumes keep the original single-argument locked body and
evidence-before-probe behavior. No persistent flag, lock deletion or rollback is
introduced. Only `run` and `_run_locked` change in production.

## Files and validation

- `workflow.py`: implement the above narrow ordering and local keyword.
- `test_new_run_probe_ordering.py`: six deterministic competing-publication
  negatives for valid checkpoint, malformed checkpoint and source-review
  evidence across both protocols; two genuine precreated-pristine workflow
  positives verify single probing under exclusion and stable lock inode.
- Keep every existing `test_new_run_preflight.py` assertion unchanged. Root also
  runs run-lock/reviewed-workflow tests and the existing genuine source-service
  acceptance-to-Workflow test to cover an already claimed review root.

Root performs all runtime tests after independent review and full-run completion.
No helper/application imports or tests are executed by this author. All private
`_run_locked` references were read before changing its signature: existing mocks
on retained run roots still receive the original single argument.

## Risks, rollout and fallback

An early successful probe cannot authorize writing over a competing new run.
The post-probe check therefore runs under the same unchanged OS lock and checks
both checkpoint presence and exact root inventory. An already-existing run never
uses this new path. Rejection preserves all rival bytes and the stable lock.
Root must retain fresh single-probe, denied-probe/no-artifacts, resume validation,
same-run exclusion and unrelated-run independence regressions. If validation
fails, inspect the preserved baseline; do not remove safety assertions or delete
stable lock files as a workaround. No publication or deployment is included.

## Status

W authoring frozen for independent review: two new test functions define eight
cases. Existing tests, lock implementation and all R files remain unchanged.
Runtime validation and root integration remain pending.
