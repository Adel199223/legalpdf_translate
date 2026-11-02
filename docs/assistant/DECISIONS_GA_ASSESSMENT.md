# Decisions API GA assessment — 2026-10-30

**Recommendation: do not integrate Decisions into production routing or acceptance on this evidence.** It is inexpensive and can recognize a detached signing group, but it missed a known material footer-order failure. General availability did not demonstrate a significant improvement over the app's existing checks.

## What changed at OpenAI

The official [changelog](https://developers.openai.com/api/docs/changelog) dates general availability to **2026-10-22**, following public beta on October 6. The [Decisions guide](https://developers.openai.com/api/docs/guides/decisions), verified 2026-10-30, still identifies `gpt-6-luna` as the supported model. The release adds shared-input caching, question-local images, structured JSON input and up to 400 questions per request. It does not announce a new reasoning model for this endpoint.

Decisions returns predicates, fixed choices and scores. It does not generate the app's arbitrary repair structures, execute repairs or prove the resulting Word layout. The guide directs arbitrary structured output and tool execution to other API mechanisms. Treat advertised speed as a vendor claim; this evaluation did not run a matched Responses comparison.

## Fixed experiment and measured results

Five primary requests were registered before dispatch: four complete retained native artifacts and an incomplete-document control. Filenames, historical verdicts and pair labels were excluded from the provider input. Whole-page PNGs were supplied in order. Gold labels came from pinned prior independent content/native reviews. The advisory rule required a supported defect choice and predicate at least 0.80 to request visual review; complete `no_issue` evidence at or below 0.20 meant low alarm only. Missing evidence or conflicting answers meant abstention. No model answer could approve legal content or override an existing hard stop.

| Retained case | Expected | Observed route | Visible-defect probability | Result |
|---|---|---|---:|---|
| Trial04 detached signing group | Review closing split | `closing_split` | 0.91 | Detected |
| Trial03 repaired footer flow | No specified defect | `no_issue` | 0.00 | Correct low alarm |
| Trial03 footer before continued body | Review footer order | `no_issue` | 0.02 | **Missed material defect** |
| Trial04 repaired whole closing group | No specified defect | `no_issue` | 0.00 | Correct low alarm |
| First page only, three pages absent | Insufficient evidence | `insufficient_evidence` | 0.00 | Correct abstention |

The predefined screen **failed**: three of four actual artifacts were classified correctly, but only one of two known defects was flagged. Both repaired controls avoided alarms. These counts concern one original and two correlated repair pairs; they are not a general accuracy estimate. The missed case's separate choice confidence was 0.41; its 0.02 predicate is what incorrectly produced low alarm under the frozen rule. Neither field is calibrated assurance.

Two additional requests moved the bad/fixed closing-group images into question instructions. Both returned the expected route. They demonstrate the new interface working, not independent quality samples or improved reasoning. No post-hoc threshold fitting, prompt tuning or purchase of fresh translations followed.

## Cost, latency and caching

All **nine** planned HTTP calls returned 200. They used **48,026 input tokens**, with estimated total cost **USD0.00450672**, less than one cent. Summed HTTP duration was 12.113 seconds; median 1.078 seconds. These are per-response usage calculations at the verified public prices, not invoice reconciliation or proof of a particular remaining account balance.

The cache pair wrote 4,552 tokens on the first call and read the same 4,552 on the second, with 4,901 total input tokens per request. Including the first write, the pair cost USD0.00068432 versus USD0.0009802 for the same reported input counts at uncached prices: **30.2% lower for this deliberately repeated pair**. This is not a forecast of whole-app savings. The [pricing page](https://developers.openai.com/api/docs/pricing) and [caching guide](https://developers.openai.com/api/docs/guides/prompt-caching), verified 2026-10-30, support the separate read/write accounting. Decisions output is uncharged under its guide.

The first cache response included `cache_write_tokens_details`. The private runner rejected that additional field and stopped before the next dispatch. A separately versioned offline fix validated its 30-minute/12-hour counters, exact sum and zero 12-hour writes, then reconciled the retained response without buying it again. The original failed-parser receipt remains intact. Only the final planned cache-read request followed. The main app already supports this bounded optional usage shape; no production repair was required.

## Consequences for this project

- Keep deterministic source ownership, protected-text, coverage, terminal-footer ordering, repair allowance and settled-cost gates authoritative. These decisions do not benefit from another probabilistic vote.
- Keep semantic review and native layout verification. A low Decisions score must not remove `automatic_unreviewed` or permit release without the existing checks.
- Do not restructure the app or project harness around this API. The current main already repairs the two historical layout patterns tested here; recognizing one does not demonstrate incremental production value.
- A possible future use is advisory prioritization after native rendering, with abstention and a safe existing repair route. That requires an unseen representative corpus and evidence of improvement over current code. This experiment does not justify enabling it now.
- Keep the October 9 pilot separate: its 25/30 role agreement and poor bad/good omission separation remain historical evidence, not pooled validation for this screen.

## Validation and preservation

Current targeted product tests passed: 168 semantic/repair/footer/closing cases and 47 installed cache-compatibility cases. Private runner versions passed 55 and 78 tests respectively; those versions overlap and are not summed. All 802 protected production/test/script files still match the prior accepted Full03 freeze. All retained page pins and frozen request hashes remain unchanged. No production code, models, settings, jobs, translations, Gmail state or dependencies were changed. This is not a new app startup test.

Standard project validation also passed: 267 browser regression tests, compilation, documentation and workspace hygiene. The known Dart AOT wrapper issue required the successful direct-Dart fallback. Full03 remains the unchanged product's prior broad validation; no new Full run is claimed.

Fresh unattended acceptance remains **0/3**. The previously installed provisional update is unchanged. This evaluation did not restart that campaign or establish a new accepted original.

Evidence is private under `C:\Users\FA507\.codex\legalpdf_translate_private_benchmarks\decisions_ga_20261030_01`: frozen `protocol.json`, original and versioned runner/tests, all nine raw request/response pairs, `C01_reconciliation_v2.json`, independent assessment and `terminal_receipt.json`. Protocol SHA-256: `732f4dbed7ad865d0b0871139bc4d4e12b0df30f07f7193a291c58822f1d03ab`. The [completed plan](exec_plans/completed/2026-10-30_decisions_ga_evaluation.md) records scope and validation. No further API calls are part of this completed protocol.
