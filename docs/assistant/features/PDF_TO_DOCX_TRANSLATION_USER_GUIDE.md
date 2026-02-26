# PDF to DOCX Translation User Guide

## Use This Guide When
- You need help with the app's main workflow: translating a PDF into DOCX.
- You are supporting users who are unfamiliar with technical tooling.
- You want plain-language troubleshooting for failed or partial runs.

## Do Not Use This Guide For
- Deep implementation details for OCR/model internals.
- Database schema migration procedures.
- CI pipeline maintenance.

## For Agents: Support Interaction Contract
Response shape:
1. Plain explanation.
2. Numbered steps.
3. Canonical check against `APP_KNOWLEDGE.md`.
4. Uncertainty note when needed.

Define unavoidable technical terms in one sentence.

## Canonical Deference Rule
This user guide is not canonical architecture truth. Defer to `APP_KNOWLEDGE.md`, and treat source code as final truth on conflict.

## Quick Start (No Technical Background)
1. Open LegalPDF Translate.
2. Select your PDF.
3. Choose target language.
4. Choose output folder.
5. Start translation.
6. Open output DOCX when run completes.

## Terms in Plain English
- Target language: The language you want the final document in.
- Analyze-only: A mode that inspects extraction quality without translating.
- Retry: The app making another attempt after a failed page response.
- OCR: Reading text from page images when normal extraction is poor.
- Run summary: A final report about what happened in the run.

## Troubleshooting
1. If setup commands fail with `html.entities` or `idna` import errors, run `powershell -ExecutionPolicy Bypass -File scripts/setup_python311_env.ps1 -Recreate`, then activate `. .\.venv311\Scripts\Activate.ps1`.
2. If output is missing pages, check if run stopped early and use resume.
3. If run is slow, lower worker count and retry.
4. If text quality is poor, test analyze-only and inspect OCR routing.
5. If terminology is inconsistent, review glossary settings and rerun affected pages.

## Canonical Checkpoints for Agents
- Runtime behavior: `APP_KNOWLEDGE.md`
- Workflow specifics: `docs/assistant/workflows/TRANSLATION_WORKFLOW.md`
- Data/persistence behavior: `docs/assistant/workflows/PERSISTENCE_DATA_WORKFLOW.md`
