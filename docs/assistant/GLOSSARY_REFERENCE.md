# GLOSSARY_REFERENCE

## Purpose
Quick reference for glossary systems in this repo and where they are used.

## AI Glossary (translation consistency)
- Source:
  - `src/legalpdf_translate/user_settings.py` (`glossaries_by_lang`, `enabled_glossary_tiers_by_target_lang`)
  - `src/legalpdf_translate/glossary.py` (`GlossaryEntry`, `format_glossary_for_prompt`, filter/sort/cap helpers)
- Injection point:
  - `src/legalpdf_translate/workflow.py::TranslationWorkflow._append_glossary_prompt`
- Behavior:
  - Injected into translation prompt only when rows exist for target language and active tiers match.
  - Tier-aware and token-capped (`max 50` entries, `max 6000` chars).

## Study Glossary (learning-only)
- Source:
  - `src/legalpdf_translate/user_settings.py` (`study_glossary_entries` and related study keys)
  - `src/legalpdf_translate/study_glossary.py` (mining/scoring/coverage/merge/review helpers)
  - `src/legalpdf_translate/qt_gui/dialogs.py::_build_tab_study` (Qt UI)
- Behavior:
  - Used for study/review and term learning.
  - Not injected into translation prompts.
  - Prompt path remains AI glossary only (`_append_glossary_prompt`).

## Verification Commands
```powershell
rg -n "_append_glossary_prompt|glossaries_by_lang|study_glossary_entries|_build_tab_study" src/legalpdf_translate
python -m pytest -q tests/test_workflow_glossary.py tests/test_study_glossary_prompt_isolation.py
```
