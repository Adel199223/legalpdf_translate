# ExecPlan: Arabic DOCX Run Ordering for Manual Word Review

## 1. Title
Arabic DOCX Run Ordering for Manual Word Review

## 2. Goal and non-goals
- Goal: fix shared Arabic DOCX mixed-script run ordering so manual right-alignment in Word preserves commas, bars, numbering markers, and mixed Arabic/Latin token placement.
- Non-goal: change browser/manual Arabic review gating, Gmail confirmation flow, Save-to-Job-Log gating, or automatic Word mutation behavior.
- Non-goal: change Arabic retry/compliance behavior in this pass beyond preserving current diagnostics.

## 3. Scope (in/out)
- In scope:
  - shared Arabic DOCX assembly in `src/legalpdf_translate/docx_writer.py`
  - focused regression coverage for exact broken run shapes
  - visual validation with rendered scratch DOCX fixtures
- Out of scope:
  - browser Arabic review workflow changes
  - Qt review-dialog behavior changes
  - page-5 Arabic compliance recovery changes

## 4. Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_pdf_worker_fix`
- Branch name: `codex/gmail-pdf-worker-fix`
- Base branch: `main`
- Base SHA: `ab70a4796e29281f09be5bcdb962ba56bd0473b3`
- Target integration branch: `main`
- Canonical build status: intended noncanonical fix worktree used for isolated browser/manual Arabic validation

## 5. Interfaces/types/contracts affected
- No public API changes.
- No browser/Gmail review contract changes.
- Shared Arabic DOCX writer behavior changes for mixed-script run segmentation only.

## 6. File-by-file implementation steps
1. Update `src/legalpdf_translate/docx_writer.py` to keep placeholder-derived token spans explicit during Arabic DOCX assembly instead of unwrapping them before run segmentation.
2. Add token-aware Arabic run segmentation so:
   - protected token cores stay atomic verbatim runs
   - Arabic-side punctuation outside token cores stays with RTL context
   - separator-only edges like `|` do not remain attached to LTR runs
   - list/index/article markers such as `I-`, `1.1-`, `153.º`, and `a)` remain atomic LTR runs
3. Extend `tests/test_docx_writer_rtl.py` with exact regression fixtures for the real failure shapes seen in the saved Arabic DOCX.
4. Update any adjacent DOCX writer tests only as needed to reflect the refined run-level contract.

## 7. Tests and acceptance criteria
- Focused automated coverage:
  - XML/run-level assertions for header, list opener, mixed name/date/address paragraph, and statute line
  - existing RTL paragraph flags remain present
  - token cores remain verbatim
  - Arabic commas and separator bars are no longer attached to LTR runs unless they are truly internal to the protected token core
- Focused validation:
  - `py_compile` for the touched writer module
  - targeted pytest slice for DOCX writer tests
  - render representative scratch Arabic DOCX fixtures with `tooling/render_docx.py`
- Acceptance:
  - manual Word right-alignment no longer produces leading commas/bars or visibly scrambled mixed-script ordering on the affected lines

## 8. Rollout and fallback
- Roll out only in the isolated fix worktree first.
- If token-aware segmentation alone is insufficient after visual validation, follow up with a narrow writer-only pass that preserves placeholder-derived isolate intent during DOCX assembly without broadening bidi-control preservation elsewhere.

## 9. Risks and mitigations
- Risk: overcorrecting token edges could break legitimate marker tokens.
  - Mitigation: lock exact marker shapes with targeted regression tests before broader rendering validation.
- Risk: changing Arabic run segmentation could regress previously stable mixed-script lines.
  - Mitigation: keep the change limited to placeholder-aware Arabic assembly and preserve existing non-RTL behavior.

## 10. Assumptions/defaults
- The saved Arabic DOCX already demonstrates the defect on completed pages, so the first fix belongs in shared DOCX assembly rather than the browser review flow.
- Manual Word review remains operator-owned and must stay manual-only.
- The safest order is writer fix first, visual validation second, and only then any narrower bidi-control follow-up if still needed.
