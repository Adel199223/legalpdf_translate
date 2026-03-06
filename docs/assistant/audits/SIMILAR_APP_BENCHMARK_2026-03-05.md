# Similar-App Benchmark (Official Sources Only)

Verification date: 2026-03-05

## Method
- Target app profile for similarity scoring:
  - Windows desktop-first, single-operator legal translation workflow.
  - One-page-per-request processing with deterministic artifacts/checkpointing.
  - Strong terminology and reliability emphasis, weak current cost observability.
- Scoring weights (fixed):
  - Document fidelity `25%`
  - Legal terminology control `20%`
  - QA/review workflow `20%`
  - Reliability/ops controls `20%`
  - Cost governance `15%`
- Scale: each dimension `0..5`; weighted score converted to `0..100`.

## Ranked Similarity Matrix
| Rank | Product Family | Fidelity (25) | Terminology (20) | QA/Review (20) | Reliability/Ops (20) | Cost Gov (15) | Weighted Score |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | Google Cloud Translation | 4.0 | 4.0 | 2.5 | 4.5 | 4.0 | 76.0 |
| 2 | Azure Document Translation | 4.0 | 3.5 | 2.5 | 4.5 | 4.0 | 74.0 |
| 3 | memoQ | 3.5 | 4.5 | 4.0 | 3.5 | 2.0 | 71.5 |
| 4 | DeepL API | 4.5 | 4.5 | 2.0 | 3.0 | 2.5 | 68.0 |
| 5 | Smartcat | 3.0 | 4.0 | 4.5 | 3.0 | 2.0 | 67.0 |
| 6 | Phrase | 3.0 | 4.0 | 3.5 | 3.0 | 2.5 | 64.5 |

## Evidence Registry (Fact-Level)
### DeepL
- Document API supports asynchronous document translation lifecycle (`upload`, `status`, `download`).
  - Source: <https://developers.deepl.com/api-reference/document>
- Glossary APIs support glossary creation/management and multilingual dictionary entries.
  - Source: <https://developers.deepl.com/api-reference/multilingual-glossaries>

### Google Cloud Translation
- Advanced docs include document translation and batch document translation routes.
  - Sources:
    - <https://cloud.google.com/translate/docs/advanced/translate-documents>
    - <https://cloud.google.com/translate/docs/advanced/batch-translation>
- Advanced docs include glossary usage and glossary stopwords controls.
  - Source: <https://cloud.google.com/translate/docs/advanced/glossary>
- Adaptive translation is provided as a first-party capability.
  - Source: <https://cloud.google.com/translate/docs/advanced/adaptive-translation>

### Azure AI Translator
- Document translation is asynchronous and operation-based.
  - Source: <https://learn.microsoft.com/en-us/azure/ai-services/translator/document-translation/overview>
- Glossary support is documented for document translation pipelines.
  - Source: <https://learn.microsoft.com/en-us/azure/ai-services/translator/document-translation/how-to-guides/create-use-glossaries>

### Smartcat
- AI Glossary capability exists for terminology control.
  - Source: <https://help.smartcat.com/ai-glossary/>
- Linguistic Quality Assurance checks are first-class workflow controls.
  - Source: <https://help.smartcat.com/linguistic-quality-assurance/>

### memoQ
- Translation memory is central to segment reuse.
  - Source: <https://docs.memoq.com/current/en/Workspace/translation-memories.html>
- Term base guidance supports terminology governance workflows.
  - Source: <https://docs.memoq.com/current/en/Workspace/term-bases.html>

### Phrase
- Term base capability is documented as core terminology governance.
  - Source: <https://support.phrase.com/hc/en-us/articles/5709620703388-Term-Base-Overview>
- Phrase Language AI documents AI translation/post-editing workflow primitives.
  - Source: <https://support.phrase.com/hc/en-us/articles/5784113626140-Language-AI>

## Why These Scores Map To LegalPDF Translate
1. Google/Azure score highest because they align with document pipelines, batch/ops controls, and explicit governance surfaces.
2. memoQ scores high on terminology and QA depth, but lower on API-style cost/ops governance fit for your current architecture.
3. DeepL is strong in document+glossary quality but lighter on review/ops transparency compared with cloud enterprise stacks.
4. Smartcat/Phrase contribute strong QA/terminology patterns useful for your roadmap, but are less similar to your current deterministic desktop runtime architecture.
