# Acceptance runtime continuation: official references

Fresh-task recheck2026-09-15 for the remaining eight Arabic pages: opened the official [Terra model page](https://developers.openai.com/api/docs/models/gpt-5.6-terra) and [Responses creation reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create). Terra high/xhigh and structured outputs remain documented; ordinary-context USD2/M input, USD0.20/M cached input and USD12/M output, with cache writes1.25x input and long-context multipliers only above272K input. The existing50000input/24000inclusiveoutput bound yields a conservative USD0.413maximum per request and USD3.304for eight (arithmetic, not expected cost). Responses output caps include reasoning; requested default tier uses standard pricing, while the returned tier must still be checked. No account/probe/API operation occurred for this recheck, and original ledger/defaults are unchanged.

Verified 2026-09-14 through official OpenAI documentation. The documentation lookup itself made no provider request or account-access test. Subsequent six-call Terra API evidence is recorded separately in [the pilot summary](TERRA_EFFORT_PILOT.md); it does not prove Sol access or ordinary-use readiness.

- [GPT-5.2 model](https://developers.openai.com/api/docs/models/gpt-5.2): standard text rates shown are USD1.75/M input, USD0.175/M cached input and USD14/M output; high reasoning and structured outputs are supported. Existing gpt-5.2/high selection remains unchanged. These public rates do not prove this account's access, invoice, endpoint or actual served tier.
- [Responses creation reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create): maximum output includes visible and reasoning tokens; explicit default tier selects standard processing, but the returned tier must be checked. Store is explicitly false in the acceptance contract. Cached tokens are a detail of input usage, not additional input to double-charge.

Use these only in a separately scoped future cost manifest with original-ledger reconciliation, actual request/model/endpoint/tier validation, conservative reservation and observed usage. No prices in an existing journal are rewritten. No savings or real-document acceptance is inferred.

## Explicit Terra and Sol acceptance candidates

Verified2026-09-14 against the fetched official pages:

- [GPT-5.6 Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra): explicit model ID gpt-5.6-terra, Responses/structured outputs and high/xhigh reasoning supported. Standard ordinary-context input/cached-input/output rates are USD2/0.20/12 per million tokens. Prompts over272K input tokens have different multipliers; a future reservation must respect that threshold instead of applying ordinary-context rates to an unbounded request.
- [GPT-5.6 Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol): explicit model ID gpt-5.6-sol, Responses/structured outputs and high/xhigh reasoning supported. Standard ordinary-context input/cached-input/output rates USD4/0.40/20 per million tokens are promotional through at least2026-11-21. The broader gpt-5.6 alias routes to Sol; this application uses exact named IDs rather than aliases.

The user intends Terra as the application engine and permits evaluating xhigh, including as a possible base choice; Codex model selection stays AstraUltra. Current code adds explicit per-client candidate selection and exact model/effort identity binding, not ordinary default promotion. No endpoint, SDK, prompt-content, credential or auth/OCR routing change is required by these documented capabilities. Model availability for this account and current real-document quality/efficiency remain unverified. Historical6Sept experiments support a Terra/high successor candidate but not universal superiority, automatic Sol escalation or xhigh benefit. Retain those results and test only justified current-workflow gaps under the original lifetimeUSD10 cap.

Subsequent14Sept checkpoint: six bounded Terra requests completed on the actual account with exact Terra model/effort and default tier; Sol access remains untested. Three one-page high/xhigh pairs cost USD0.118219 total, with xhigh47.07% higher and no demonstrated material quality advantage after independent blinded raw-text reviews. Existing deterministic French month normalization already repairs the observed raw month leakage. These are limited initial-response results, not full-document, layout or complete-workflow acceptance. No silent default promotion follows. Current official reasoning guidance recommends xhigh only where evaluation demonstrates a benefit sufficient to justify additional cost/latency; verification used the opened [reasoning guide](https://developers.openai.com/api/docs/guides/reasoning), not model-name inference.

Verified again2026-09-14: the same Terra page specifies cache writes at1.25 times uncached input, hence USD2.5/M. The proposed50k input/24k inclusive output cap stays below the272k long-context threshold. Reserving every input token at the maximum applicable input/cache-write rate yields USD0.413 per call, not USD0.388. The six-call high/xhigh pilot ceiling is USD2.478; this is a conservative reservation, not observed spend. [Reasoning documentation](https://developers.openai.com/api/docs/guides/reasoning) confirms that reasoning tokens are billed as output and included in max_output_tokens. High/xhigh therefore require measured total tokens/cost/latency rather than assuming a fixed effort surcharge.

## AR5 legal terminology review

Verified2026-09-14 for source-versus-translation review, not advice about the private case. Queries contained no private text or identifiers.

- [DGRSP: Suspensão Provisória do Processo](https://dgrsp.justica.gov.pt/Justi%C3%A7a-de-adultos/Penas-e-medidas-na-comunidade/Medidas-na-Comunidade/Suspens%C3%A3o-Provis%C3%B3ria-do-Processo): pre-judgment suspension of proceedings, imposed obligations/conduct rules and absence of high culpability. Page states last content update2023-12-11; not a complete current statutory verification.
- [Évora Court of Appeal decision2025-06-03, official publication](https://diariodarepublica.pt/dr/detalhe/acordao/212-2025-930244975): corroborates the institution's prevention/culpability considerations. Used to assess terminology, not to substitute a judicial decision for the source document.

The paid response was independently reviewed by two AI reviewers with no observed material content error on this one page. This is not human certification or full-document/layout acceptance. Private review details remain outside Git.

## AR3 administrative date reference

Verified2026-09-14 against [official Setubal court usage](https://comarcas.tribunais.org.pt/comarcas/juris2/setubal/pdf/6912-20.8T8STB%20-%20Hipoteca.pdf), final page: the signature-place notation d.s. is paired with a statement that the document was signed on the date above. This supports the contextual Arabic rendering التاريخ أعلاه without inventing an actual date. Used for a bounded AI-reviewed translation correction, not advice about the private case. Private source values were not sent to public search. Generic judge-title gender is an editorial/context issue, not a changed legal disposition.

## Acceptance SDK metadata

Verified 2026-09-14: [official Python library reference](https://developers.openai.com/api/reference/python) documents explicit custom HTTP clients and disabling retries with max_retries=0. Current web documentation describes HTTPX2; this project has an inspected HTTPX-based SDK, which is tested without upgrading. The acceptance-only platform_headers override is a source-inspected compatibility seam, not a promised public SDK API. It returns honest Unknown OS/architecture metadata without platform probes; ordinary clients and defaults remain unchanged. Re-run actual-SDK MockTransport tests after dependency updates.

## AR4 and AR6 legal-language review

Verified2026-09-14 using public generic terms only. Direct consolidated Diário da República pages required JavaScript in the reader; readable official prosecutorial publications below supplied the terminology evidence instead.

- [PGDLisboa criminal-procedure provisions including Article243](https://www.pgdlisboa.pt/leis/lei_mostra_articulado.php?artigo_id=199A0242&ficha=1&nid=199&nversao=&pagina=1&so_miolo=S&tabela=leis): an auto de notícia records an observed offence and its particulars. This supports distinguishing an offence-report record from an ordinary notification record.
- [PGDLisboa Penal Code provisions including Article20](https://pgdlisboa.pt/leis/lei_mostra_articulado.php?artigo_id=109A0023&ficha=1&nid=109&nversao=&pagina=1&so_miolo=&tabela=leis): the capacity to direct one's conduct in accordance with an assessment is distinct from merely identifying or determining something. Used only to check the source's normative-capacity language, not to assess culpability in the private case.
- [Procuradoria-Geral da República opinion22/2019](https://www.ministeriopublico.pt/pareceres-pgr/9324): explains driving entitlement and reproduces statutory preconditions for provisional suspension. This supports rendering licensing and statutory prerequisites distinctly from general legal capacity or assumptions. This historical publication is terminology evidence, not a claim that all reproduced statutory wording is current.

Exact Arabic replacements are contextual AI-review decisions based on the supplied source, not official Arabic statutory translations. All case text, edit offsets and private identities remain outside Git. Saved preferences are unchanged. These reviews do not establish layout acceptance or human certification.

## AR7 procedural-party terminology

Verified2026-09-14: [Supreme Court judgment12/2016 in the official Diário da República](https://diariodarepublica.pt/dr/detalhe/acordao-supremo-tribunal-justica/12-2016-75462709) distinguishes a formally constituted assistente from an ordinary complainant or injured party, and reproduces Article69's assisting role in relation to the prosecution. The contextual Arabic description identifies this procedural party, without attributing formal status merely to a complainant. The historical judgment is used for terminology only, not current procedural deadlines or advice about the private case. Exact review changes remain private and saved preferences unchanged.

## Blinded Terra pilot terminology references

Used by the independent AI reviewers on2026-09-14 for contextual wording checks; no private text or identifiers were sent to search. These support terminology discussion, not a finding about the private matter or complete current statutory verification.

- Arabic driving entitlement and suspension terminology: [official driving regulation](https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2012-114321099), [official driving-offence legislation](https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1998-34445675), [DGRSP suspension explanation](https://dgrsp.justica.gov.pt/Justi%C3%A7a-de-adultos/Penas-e-medidas-na-comunidade/Suspens%C3%A3o-Provis%C3%B3ria-do-Processo-artigos-281%C2%BA-e-282%C2%BA-do-C%C3%B3digo-do-Processo-Penal). Preserve the distinction between driving entitlement and general legal capacity; do not invent suspension prerequisites in a translation.
- French TIR terminology: [official legal lexicon](https://diariodarepublica.pt/dr/lexionario/termo/termo-identidade-residencia-processo-penal). TIR is a Portuguese procedural measure; a translation must not substitute a French procedure.
- English advance-period wording: [official usage example](https://diariodarepublica.pt/dr/detalhe/acordao/18922-2024-929916075). Minimum-lead-time readings can be contextual, but this reference does not resolve the pilot source's incomplete final instruction. Flag an added express minimum for full-document review instead of declaring an unsupported consequential error.

AI text reviews remain distinct from local deterministic normalization, committed-output coverage and rendered-layout acceptance. No human certification is implied.

## English legacy reuse review, 2026-09-15

Root and the independent AI reviewer opened these public primary sources for bounded terminology checks, without submitting private case text or identifiers:

- [Porto Court of Appeal decision 0742984](https://www.dgsi.pt/jtrp.nsf/-/3849006EE866F7878025731B003440A5): expressly expands the administrative abbreviation d.s. as data supra. The contextual English rendering date as above preserves the reference without supplying a presumed date. This is historical usage evidence, not advice on current law.
- [DGAJ: Criminal record certificate](https://dgaj.justica.gov.pt/Registo-criminal/Criminal-record-certificate): supports the existing English term criminal record certificate. The current court-division header wording comes from the user's saved/generated glossary and consistency with the reviewed first page, not a claimed official English statutory translation.

The proposed second-page derivative has two explicit, single-line AI-review edits; all other legacy target strings, the ordered French-translation duty and interpreter appointment remain unchanged. Historical EN2 did not receive today's glossary suffix. Current preference compatibility, AI test review, technical validation and rendered-layout acceptance stay separate.

Also reverified on 2026-09-15: [Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra) and [Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol) retain the previously recorded ordinary-context rates and high/xhigh support; [reasoning guidance](https://developers.openai.com/api/docs/guides/reasoning) bills reasoning within output tokens. The answer-only model assessment made no paid calls or configuration changes. The September14 three-pair pilot remains limited evidence, not a definitive xhigh rejection or a Sol comparison.

## Reviewed region writer: compatibility XML ordering, 2026-09-15

The [Microsoft Open XML SDK WordprocessingML schema](https://raw.githubusercontent.com/dotnet/Open-XML-SDK/main/data/schemas/schemas_openxmlformats_org_wordprocessingml_2006_main.json) defines CT_Compat as an ordered sequence: doNotExpandShiftReturn precedes useFELayout and compatSetting. Independent static review found that the initial v2 writer appended it after those children; synthetic regression109 reproduced that order, and root changed insertion under the explicit known-template contract. This is schema evidence, not an observed native Word failure or a rendered-layout pass. V1 output behavior is unchanged.
