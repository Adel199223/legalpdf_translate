---
name: legalpdf-word-review
description: >-
  Review LegalPDF DOCX outputs visually and structurally via tooling/render_docx.py
  or live Microsoft Word using windows-desktop-control MCP. Use when inspecting
  translation fidelity, layout, Arabic RTL alignment, or Word visual appearance.
---

# LegalPDF Word & Translation Quality Review

Defer to `agent.md`, `docs/assistant/VALIDATION.md`, `docs/assistant/workflows/TRANSLATION_WORKFLOW.md`, and `docs/assistant/workflows/HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md`.

## Evaluation Principles

- Keep three dimensions strictly separate in every report:
  1. **Legal content & source relationships** (meaning, intact literals, headings, fields, rows, paragraphs, signatures, folios).
  2. **Word visual appearance** (pagination, indentation, footer flow, alignment, typography).
  3. **Installed build status** (canonical `main` runtime vs offline/branch candidate), plus evidence type (`synthetic test`, `retained-response replay`, `fresh run`, or `installed check`).
- Defect triage order: name the visible failure -> locate the first broken representation -> reproduce with the smallest ordinary-path offline replay -> check an unaffected control. Never trigger paid OpenAI API calls or native helpers without explicit user authorization.

## Visual Inspection Paths

### Option A: Headless Render (Safe & Non-Interactive)
1. Render pages to PDF/PNG using LibreOffice + Poppler + `.venv311` `pdf2image`:
   ```powershell
   .\.venv311\Scripts\python.exe tooling/render_docx.py <path/to/output.docx> --outdir tmp/docs/render_docx/<run-name>
   ```
2. Open the generated PNG page images directly with `read_file` and inspect every relevant page individually.

### Option B: Live Windows Microsoft Word (`windows-desktop-control` MCP)
- WSL-only checks are insufficient for Windows Word COM export canaries and the Arabic `Align Right + Save` gate.
- Use `windows-desktop-control` `Screenshot` first for visual page inspection; use `Snapshot` only when UI Automation element coordinates/clicks are needed.
- **Always release desktop control** (`ControlStatus` with `release=true`) when finished or before waiting on the user, and stop immediately if the user reclaims control.
- Never kill unrelated open or AutoRecovered Word documents, and never delete Word quarantine state.

## Verification

- State exact reviewed DOCX path/hash, evidence type, page-by-page visual findings (including any RTL/header/footer caveats), and `ControlStatus` release if `windows-desktop-control` was used.
