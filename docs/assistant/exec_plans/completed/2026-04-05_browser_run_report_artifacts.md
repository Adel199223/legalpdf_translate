# Browser Run Report Artifacts

## Goal
- Make browser translation run reports first-class completion artifacts.
- Keep the detailed Markdown report content unchanged.
- Preserve existing generic power-tools report behavior for non-translation flows.

## Execution
1. Add a translation-job run-report generator that writes `run_report.md` into the run directory and stores the path on the job.
2. Expose the report through the translation artifact route and action flags.
3. Update the completion drawer to show/download the generated report and trigger a one-time download on generation.
4. Run focused browser/report regression tests.

## Guardrails
- Do not change Arabic review gating or Gmail confirmation behavior.
- Do not add a generic absolute-path download surface.
- Do not weaken the current report detail level.
