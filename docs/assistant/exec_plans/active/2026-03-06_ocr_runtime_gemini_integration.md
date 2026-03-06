# 2026-03-06 OCR Runtime Gemini Integration

## Summary
Integrate the local Gemini OCR provider work onto the approved OCR-stabilization baseline, while preserving the local Requerimento de Honorarios feature work.

## Source Worktrees
- Base branch/worktree: `feat/ocr-runtime-stabilization-20260306` at `1657079`
- Honorarios source: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Gemini OCR source: `/mnt/c/Users/FA507/.codex/legalpdf_translate_gemini`

## Target Branch
- `feat/ocr-runtime-gemini-integration`

## Implementation Notes
1. Transplant honorarios local WIP first.
2. Apply Gemini OCR provider changes from the older Gemini worktree onto this newer base.
3. Resolve overlaps in `dialogs.py`, `app_window.py`, `workflow.py`, and `user_settings.py` while preserving OCR runtime stabilization behavior.
4. Validate one combined build.
5. Commit in three scopes: honorarios, Gemini OCR, docs sync.
