# Localization Glossary

This file is the single source-of-truth for localized terminology policy.

## Scope
- Target languages: EN, FR, AR.
- Canonical reference for terminology consistency rules and defaults.
- Other docs should reference this file instead of duplicating glossary policy tables.

## Core Terms
| Concept | EN | FR | AR | Notes |
|---|---|---|---|---|
| Source text | Source text | Texte source | النص المصدر | Input extracted from PDF page. |
| Preferred translation | Preferred translation | Traduction preferee | الترجمة المفضلة | Canonical target wording. |
| Exact match | exact | exact | exact | Match mode value used by app schema. |
| Tier 1 | Tier 1 | Niveau 1 | المستوى 1 | Highest priority glossary tier. |
| Tier 2 | Tier 2 | Niveau 2 | المستوى 2 | Default enabled tier with Tier 1. |
| Run summary | Run summary | Resume d'execution | ملخص التشغيل | Post-run JSON/markdown diagnostics context. |

## Policies
1. Keep localized term governance centralized here.
2. Use this glossary when editing localization docs/workflows.
3. If a term changes, update this file first, then dependent docs.
4. Do not duplicate full term tables in workflow docs.

## Validation Hooks
- `dart run tooling/validate_agent_docs.dart --scope localization`
- `dart run tooling/validate_agent_docs.dart`
