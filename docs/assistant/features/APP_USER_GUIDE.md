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

## Common Help Paths
- Translation behavior basics: `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`
- Technical canonical check: `APP_KNOWLEDGE.md`
