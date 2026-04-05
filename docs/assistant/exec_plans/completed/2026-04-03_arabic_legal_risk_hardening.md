# Arabic Legal-Term Injection and Risk Hardening

## 1. Title
Narrow hardening for Arabic legal-term injection and Arabic citation-heavy risk scoring.

## 2. Goal and non-goals
Goal:
- Improve Arabic legal-term injection and Arabic run risk visibility without widening healthy prompt behavior.

Non-goals:
- No browser/Gmail/manual Word review behavior changes.
- No global glossary tier expansion.
- No blind post-generation rewriting.
- No pan-Arab glossary rewrite.

## 3. Scope (in/out)
In scope:
- Stage 1: priority injection for `O Juiz de Direito` and narrow Portuguese legal-citation aliases for `p. e p. pelos artigos`, `alínea`, and `n.º`
- Stage 2: `registo criminal` harmonization and Arabic risk-scoring hardening
- Stage 3: targeted regression bundle and sample-class acceptance check

Out of scope:
- Non-Arabic prompt behavior changes beyond the same narrow priority entries
- Browser UI, Gmail UI, or manual Word save flow changes
- Docs sync in this implementation pass

## 4. Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `feat/arabic-legal-risk-hardening`
- Base branch: `main`
- Base SHA: `7c5923578bb8f109fdf7327d5bad71d6e1fcf7a1`
- Target integration branch: `main`
- Canonical build status: canonical main-derived feature branch; no noncanonical runtime override intended

## 5. Interfaces/types/contracts affected
- Internal prompt-priority injection logic in `TranslationWorkflow._append_glossary_prompt`
- Internal glossary diagnostics matching logic in `GlossaryDiagnosticsAccumulator.record_page_cg_matches`
- Internal additive page metadata fields for validation counters in Stage 2
- Internal quality-risk reasons/weights for Arabic runs in Stage 2
- No public API/schema changes intended

## 6. File-by-file implementation steps
- `src/legalpdf_translate/legal_header_glossary.py`
  - Add narrow priority matcher for `O Juiz de Direito` under default tiers.
- `src/legalpdf_translate/pt_legal_glossary_aliases.py`
  - Add narrow PT legal-citation alias logic shared by prompt-priority injection and diagnostics.
- `src/legalpdf_translate/workflow.py`
  - Stage 1: add alias-derived priority glossary entries before generic capped prompt rows.
  - Stage 2: persist validation-summary counters into successful page metadata.
- `src/legalpdf_translate/glossary_diagnostics.py`
  - Stage 1: use shared alias-aware match logic for CG diagnostics.
- `src/legalpdf_translate/glossary.py`
  - Stage 2: add targeted `registo criminal` terminology rows.
- `src/legalpdf_translate/workflow_components/quality_risk.py`
  - Stage 2: score Arabic pages using validation counters and add clearer reasons.
- `tests/test_workflow_glossary.py`
  - Stage 1 prompt-injection coverage.
- `tests/test_glossary_diagnostics.py`
  - Stage 1 alias-aware diagnostics coverage.
- `tests/test_quality_risk_scoring.py`
  - Stage 2 Arabic risk-scoring coverage.

## 7. Tests and acceptance criteria
Stage 1:
- `O Juiz de Direito` reaches the prompt under default tiers.
- Abbreviated legal citation forms trigger canonical glossary concepts without enabling tiers 4/6 globally.
- Non-legal text does not spuriously trigger the narrow citation aliases.

Stage 2:
- `registo criminal` terminology converges on `السجل العدلي`.
- Arabic citation-heavy pages produce higher risk and queue entries when materially noisy.
- EN/FR scoring behavior remains green.

Stage 3:
- Focused regression bundle passes.
- Sample-class acceptance confirms:
  - `قاضي القانون` no longer appears for `O Juiz de Direito`
  - citation scaffolding uses configured concepts more reliably
  - Arabic citation-heavy runs no longer stay artificially green

## 8. Rollout and fallback
- Execute strictly by stage.
- If Stage 1 causes prompt noise or false positives, revert the alias scope to only the matched legal-citation lines.
- Do not proceed to Stage 2 until Stage 1 validations pass.

## 9. Risks and mitigations
- Risk: alias matching could overmatch ordinary prose.
  - Mitigation: keep alias set tiny and legal-context-sensitive; add explicit negative test.
- Risk: priority injection could duplicate generic rows.
  - Mitigation: preserve source/translation dedupe before prompt capping.
- Risk: risk-scoring changes could flood review queues.
  - Mitigation: apply Arabic-only conservative thresholds and preserve EN/FR behavior.

## 10. Assumptions/defaults
- Default glossary tiers remain `[1, 2]`.
- `السجل العدلي` is the preferred harmonized term family for this pass.
- The safest implementation order is Stage 1 -> Stage 2 -> Stage 3 with exact continuation tokens.
