# Fix Gmail PDF Preview/Prepare Failure Without Repeating the Same Blind Loop

## Goal and non-goals

Goal:
- Restore Gmail PDF `Preview` and `Prepare selected` in the browser app.
- Preserve exact browser PDF worker/module failures in diagnostics and failure reports.
- Warn operators when live Gmail is being run from a noncanonical worktree so the runtime under test is explicit.

Non-goals:
- Do not change the unrelated LichtFeld WSL setup work.
- Do not redesign Gmail intake, translation startup, or finalization flows beyond the targeted failure handling.
- Do not introduce a second static asset versioning scheme.

## Scope (in/out)

In:
- Browser PDF worker/module diagnostics and preflight.
- Gmail browser failure reporting and state preservation.
- Additive runtime/build-identity exposure for the browser bootstrap.
- Gmail live-mode warning/continue UX for noncanonical runtimes.
- Targeted tests and local validation for the repaired worker path.

Out:
- Packaging or deployment changes.
- Translation pipeline behavior unrelated to Gmail PDF preview/prepare.
- Changes to the WSL setup branch or its active ExecPlan.

## Worktree provenance

- worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_pdf_worker_fix`
- branch name: `codex/gmail-pdf-worker-fix`
- base branch: `main`
- base SHA: `ab70a47`
- target integration branch: `main`
- canonical build status: noncanonical worktree for isolated implementation; canonical runtime under test remains `main` per `docs/assistant/runtime/CANONICAL_BUILD.json`

## Interfaces/types/contracts affected

- Browser bootstrap/runtime payload gains additive build-identity fields for the browser client.
- Browser PDF diagnostics gain additive worker/module metadata fields.
- Gmail browser failure report remains `report_kind=browser_failure_report` with additive provenance/diagnostic fields only.

## File-by-file implementation steps

1. Extend runtime/build-identity payloads in the browser app bootstrap so the client can see canonicality and reasons directly.
2. Add Gmail review warning/continue UX for live noncanonical runtimes without hard-blocking the workspace.
3. Repair browser PDF worker/module preflight and preserve raw browser errors/response metadata in `browser_pdf.js`.
4. Keep Gmail selection/start-page state stable on preview/prepare failure and make repeated failure-report generation idempotent for the current captured context.
5. Add server/client regressions for versioned `.mjs` asset headers, browser failure report metadata, and noncanonical live Gmail warning behavior.
6. Run targeted validation plus a local live acceptance pass on canonical `main`.

## Tests and acceptance criteria

- Versioned `pdf.mjs` and `pdf.worker.mjs` return `200` with JavaScript MIME on the live asset path.
- Browser failure report includes raw browser PDF diagnostics and runtime build-identity metadata.
- Duplicate failure-report generation for the same captured Gmail failure remains stable and updates the existing context.
- Gmail preview/prepare failure preserves selected attachments and chosen start page.
- Noncanonical live Gmail shows a warning/continue surface before preview/prepare.
- Canonical live Gmail cold-start path can load the exact message, preview `sentença 305.pdf`, and prepare the selected attachment successfully.

## Rollout and fallback

- Preferred path: land the isolated fix on `main` and test from the canonical runtime.
- Fallback: if the exact worker bootstrap failure is still environment-specific after the targeted fix, preserve the new raw diagnostics and stop with a reproducible failure packet instead of broad speculative changes.

## Risks and mitigations

- Risk: browser PDF diagnostics changes could destabilize the existing bundle path.
  - Mitigation: keep the asset path scheme unchanged and add focused regressions around current versioned routes.
- Risk: noncanonical runtime warning could become noisy for legitimate operator workflows.
  - Mitigation: make it dismissible/continue-able per workspace instead of a hard block.
- Risk: fixing the worker path without exposing the raw browser error could hide the next failure.
  - Mitigation: record raw browser error text and fetch/content-type metadata in both UI diagnostics and report artifacts.

## Assumptions/defaults

- The pasted browser failure report reflects the real Gmail PDF preview/prepare failure.
- The correct implementation workspace is an isolated branch from canonical `main`.
- The live Gmail noncanonical guard should warn and guide, not fully block.

