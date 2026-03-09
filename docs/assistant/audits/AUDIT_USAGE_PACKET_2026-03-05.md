# AUDIT_USAGE_PACKET_2026-03-05

Verification date: 2026-03-05

## Scope
- Sources scanned:
  - `C:\Users\FA507\Downloads\*_run\run_summary.json`
  - `C:\Users\FA507\.codex\legalpdf_translate\*_run\run_summary.json`
  - `C:\Users\FA507\AppData\Roaming\LegalPDFTranslate\settings.json`
  - `C:\Users\FA507\AppData\Roaming\LegalPDFTranslate\job_log.sqlite3`
- Normalization rule: exclude non-translation `run_id` values prefixed with `glossary_builder_` from throughput/latency distributions.

## Repro Command
```powershell
& .\.venv311\Scripts\python.exe tooling/build_usage_audit_packet.py `
  --scan-root "C:\Users\FA507\Downloads" `
  --scan-root "C:\Users\FA507\.codex\legalpdf_translate" `
  --output-json "docs/assistant/audits/AUDIT_USAGE_PACKET_2026-03-05.json"
```

Output JSON artifact:
- `docs/assistant/audits/AUDIT_USAGE_PACKET_2026-03-05.json`

## Normalized Metrics (Translation Runs)
| Metric | Value |
|---|---|
| Translation run count | 4 |
| Language mix | `FR:2`, `AR:1`, `EN:1` |
| Pages/run | avg `6.0`, min `1`, max `16` |
| Total tokens | sum `124,218`, avg `31,054.5`, max `79,322` |
| Reasoning tokens | sum `31,359`, avg `7,839.75` |
| Wall time | sum `761.834s`, avg `190.459s`, max `527.455s` |
| Slowest-page concentration (top3/total wall) | avg `0.7648`, max `1.0` |
| Retry frequency | `0` pages retried |
| Failure frequency | `0` pages failed |
| OCR usage | `0` runs requested OCR; `0` pages used OCR |
| Image attachment usage | `6` pages (single `image_mode=always` run) |
| Cost estimate coverage | `0/4` runs had non-null cost estimate |

## Per-Run Rows (Translation-Only)
| Run Dir | Lang | Pages | Tokens | Reasoning Tokens | Wall Seconds | Retries | Failed | Images | OCR Used Pages | Cost Estimate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `6a330e92-744d-4579-847b-6bace4fa38d2_temp_FR_run` | FR | 16 | 79,322 | 20,449 | 527.455 | 0 | 0 | 0 | 0 | null |
| `f939154e-2b13-4ca3-a498-0004ebe09f6c_temp_FR_run` | FR | 6 | 36,748 | 8,461 | 183.138 | 0 | 0 | 6 | 0 | null |
| `Req. Hono.._AR_run` | AR | 1 | 5,226 | 1,919 | 38.903 | 0 | 0 | 0 | 0 | null |
| `Req. Hono.._EN_run` | EN | 1 | 2,922 | 530 | 12.338 | 0 | 0 | 0 | 0 | null |

## Settings Snapshot (Current Machine)
| Key | Value |
|---|---|
| `default_effort` | `high` |
| `default_effort_policy` | `fixed_high` |
| `default_images_mode` | `auto` |
| `default_workers` | `1` |
| `default_resume` | `false` |
| `ocr_mode_default` | `off` |
| `ocr_engine_default` | `local` |
| `workers` | `3` |
| `effort_policy` | `fixed_high` |
| `image_mode` | `off` |
| `resume` | `false` |
| `diagnostics_show_cost_summary` | `true` |
| `study_glossary_corpus_source` | `select_pdfs` |
| `study_glossary_default_coverage_percent` | `80` |

## Job-Log Snapshot
- `job_runs` rows: `6`
- language distribution: `AR:4`, `FR:2`
- `api_cost` aggregate: min `0.0`, max `0.0`, avg `0.0`, sum `0.0`

## Immediate Reliability/Quality Signals
1. Quality/reliability is currently stable on sampled runs: no retries and no failed pages.
2. Time concentration is high on a small page subset (top-3 pages dominate wall time in multiple runs).
3. OCR route is not used in observed runs; OCR policy and preflight are currently low-impact for normal traffic.
4. Cost visibility is the largest observability gap: summary/job-log cost fields are effectively empty in observed production usage.
