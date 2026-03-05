# APP User Guide

## Use This Guide When
- You need a plain-language explanation of what the app does.
- You are helping a non-coder run a translation safely.
- You need support steps for common run/setup questions.

## Do Not Use This Guide For
- Low-level architecture decisions.
- Source-code debugging details.
- CI/governance policy enforcement.

## For Agents: Support Interaction Contract
Use this sequence:
1. Plain explanation in everyday language.
2. Numbered action steps.
3. Canonical check against technical docs.
4. Uncertainty note if evidence is incomplete.

## Canonical Deference Rule
This guide is explanatory only. For architecture/status truth, defer to `APP_KNOWLEDGE.md`. If docs conflict with code, source code is final truth.

## Quick Start (No Technical Background)
1. Open the app.
2. Choose your PDF file.
3. Pick output language (`EN`, `FR`, or `AR`).
4. Start translation.
5. Wait for completion and open the generated DOCX file.

## Terms in Plain English
- PDF: The document you want translated.
- DOCX: The Word file created by the app.
- Run folder: A folder containing translation progress and diagnostics files.
- Resume: Continue from where a previous run stopped.
- Glossary: A preferred term list that keeps wording consistent.
- Budget cap: A spend limit you can set for a CLI run.
- Budget decision: What the app does when estimated cost is above cap (`warn` continues, `block` stops early).
- Review Queue: A short list of pages the app thinks deserve a human check.
- OCR Advisor: A recommendation shown after Analyze that suggests safer OCR or image settings.
- Queue Manifest: A small file that tells the app to run several PDFs one after another.
- Job Log: The place where you save finished work details like run ID, tokens, and estimated API cost.

## Common Tasks
1. Analyze first when a PDF looks messy or scanned, then decide whether to apply the OCR Advisor suggestion for the next run.
2. After a run finishes, open the Review Queue if pages were flagged for manual checking.
3. Save the finished run to the Job Log so the case and cost details are stored together.
4. Use a queue manifest when you want the app to process several PDFs in sequence without starting each one manually.

## Common Help Paths
- Translation behavior basics: `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`
- Technical canonical check: `APP_KNOWLEDGE.md`

Queue mode and budget caps also exist in the CLI, but this guide stays focused on the desktop app in plain language.

## If Setup Fails (Beginner Recovery)
If `pip` or `pytest` shows errors about `html.entities` or `idna`, your Python install is broken on the machine, not in your project.

Use this fix:
1. Run: `powershell -ExecutionPolicy Bypass -File scripts/setup_python311_env.ps1 -Recreate`
2. Activate: `. .\.venv311\Scripts\Activate.ps1`
3. Retry your command.
