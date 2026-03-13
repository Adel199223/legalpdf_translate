# Stage 1 ExecPlan: Beginner-First Declutter Primitives

## 1. Title
Shared compact controls, inline help affordances, and dialog-friendly collapsible sections.

## 2. Goal and non-goals
- Goal:
  - add reusable shared Qt primitives for compact add actions, hover/focus help, and collapsible dialog sections
  - wire styling hooks for those primitives into the shared theme system
  - validate the primitives in isolation before applying them to real user-facing flows
- Non-goals:
  - no actual decluttering of the Save/Edit Job Log dialog yet
  - no main-shell, Gmail-review, or honorarios-surface changes yet
  - no persistence, workflow, or document-generation changes

## 3. Scope (in/out)
- In:
  - shared helper module for declutter primitives
  - shared stylesheet selectors for the new primitives
  - isolated deterministic render sample for the new primitives
  - helper-level Qt tests
- Out:
  - real dialog/shell integration
  - wording/copy changes in production surfaces
  - docs sync outside roadmap/resume governance files

## 4. Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_beginner_first_ux`
- Branch name: `codex/beginner-first-primary-flow-ux`
- Base branch: `main`
- Base SHA: `506dee686801d698c548ba34292ab28df4a3da02`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; approved-base floor satisfied from `main`

## 5. Interfaces/types/contracts affected
- New shared UI helpers:
  - `build_compact_add_button(...)`
  - `build_inline_info_button(...)`
  - `DeclutterSection`
- Shared stylesheet contract:
  - `CompactAddButton`
  - `InlineInfoButton`
  - `DeclutterSectionHeader`
  - `DeclutterSectionToggle`
  - `DeclutterSectionSummary`
  - `DeclutterSectionContent`
- Render-review tooling:
  - `render_declutter_primitives_sample(...)`

## 6. File-by-file implementation steps
- `src/legalpdf_translate/qt_gui/declutter.py`
  - add the new shared declutter helpers
- `src/legalpdf_translate/qt_gui/styles.py`
  - style the new controls and shared tooltip chrome
- `tooling/qt_render_review.py`
  - add an isolated deterministic sample dialog for the new primitives
- `tests/test_qt_tools_dialogs_ui.py`
  - add helper-level assertions for accessibility/focus/object-name contracts
- `tests/test_qt_render_review.py`
  - add isolated render-sample assertions

## 7. Tests and acceptance criteria
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m pytest -q tests/test_qt_tools_dialogs_ui.py tests/test_qt_render_review.py`
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' tooling/qt_render_review.py --outdir tmp/stage1_declutter_primitives --themes dark_futuristic dark_simple`
- Acceptance:
  - compact add and info controls are keyboard-focusable and tooltip-backed
  - the collapsible section supports summary text and trailing header actions
  - isolated render output is deterministic in both themes
  - no production primary-flow surfaces change in this stage

## 8. Rollout and fallback
- Stop after the shared primitives validate.
- If a primitive proves awkward or visually noisy, revise it here before any real-surface adoption in Stage 2.

## 9. Risks and mitigations
- Risk: the helper API is too narrow for Stage 2 integration.
  - Mitigation: include summary text, trailing actions, and attention-state support now.
- Risk: new shared QSS selectors leak unintended visual changes.
  - Mitigation: use new object names instead of repurposing existing selectors.
- Risk: tooltips remain visually inconsistent with the existing chrome.
  - Mitigation: add global tooltip styling through the shared stylesheet.

## 10. Assumptions/defaults
- Stage 2 will reuse these helpers directly rather than inventing per-dialog variants.
- The compact add affordance is the ASCII `+` glyph, not a new icon asset.
- Inline info help uses tooltip/keyboard-focus disclosure instead of persistent text.

## 11. Current status
- Completed.
- Stage completion packet is ready for publication.
- The next step is blocked on the exact user continuation token `NEXT_STAGE_2`.

## 12. Executed validations and outcomes
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m pytest -q tests/test_qt_tools_dialogs_ui.py tests/test_qt_render_review.py`
  - PASS (`16 passed`)
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' tooling/qt_render_review.py --outdir tmp/stage1_declutter_primitives --themes dark_futuristic dark_simple`
  - PASS
  - Isolated render artifacts written under `tmp/stage1_declutter_primitives/`
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m compileall src tests tooling/qt_render_review.py`
  - PASS
- `dart run tooling/validate_agent_docs.dart`
  - PASS
