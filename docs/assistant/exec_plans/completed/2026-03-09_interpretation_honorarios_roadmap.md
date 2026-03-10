# Interpretation Honorarios Roadmap

## 1. Title
Interpretation honorarios roadmap for in-person interpreting services.

## 2. Goal and non-goals
- Goal:
  - add a second deterministic requerimento de honorarios workflow for interpretation services
  - keep translation honorarios intact while introducing interpretation-specific document logic, travel handling, and source-driven prefilling
  - make the workflow resumable across sessions through `SESSION_RESUME.md`, one active roadmap tracker, and one active wave ExecPlan
- Non-goals:
  - no WebEx/remote interpretation support in v1
  - no Google Photos or Samsung Gallery API integration in v1
  - no interpretation Gmail draft flow in v1

## 3. Scope (in/out)
- In:
  - interpretation-specific honorarios draft/model/template branch
  - Job Log schema and normalization updates required for interpretation rows
  - interpretation-aware `Edit Job Log Entry` and `QtHonorariosExportDialog`
  - profile-backed travel origin and city-distance storage
  - new Job Log add entrypoints for blank interpretation and later import-driven flows
  - roadmap/governance artifacts for this feature
- Out:
  - remote/WebEx template branch
  - Google Photos Picker integration
  - Samsung Gallery integration
  - EXIF GPS or geocoding
  - interpretation Gmail draft flow

## 4. Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `feat/interpretation-honorarios`
- Base branch: `main`
- Base SHA: `abf608f16fac69e477849b9e8b3e040502856999`
- Target integration branch: `main`
- Canonical build status: noncanonical feature branch on the canonical worktree path; approved-base floor satisfied from `main`

## 5. Interfaces/types/contracts affected
- Honorarios generation:
  - add explicit interpretation-vs-translation branching through a kind-aware draft contract
- Job Log persistence:
  - additive interpretation columns for travel km and explicit service-location usage
- Profile settings:
  - additive interpretation travel origin and per-city one-way distance mapping
- Qt UI:
  - Job Log gains a real `Add...` interpretation entrypoint
  - `Edit Job Log Entry` becomes job-type-aware for translation vs interpretation requirements
  - `QtHonorariosExportDialog` becomes kind-aware and supports recipient auto-suggest plus manual override for interpretation

## 6. File-by-file implementation steps
- Wave 1:
  - extend profile/settings persistence for interpretation travel identity
  - extend Job Log schema and normalization for interpretation fields
  - refactor honorarios draft/docx generation to support translation and interpretation kinds
  - add interpretation-specific export UI and Job Log add entrypoint
  - add tests for migrations, template branching, and Qt flow
- Wave 2:
  - add notification PDF extraction for interpretation cases
- Wave 3:
  - add photo/screenshot fallback and saved distance prompting
- Wave 4:
  - later remote/WebEx and external photo-source integrations

## 7. Tests and acceptance criteria
- Wave 1:
  - translation honorarios regressions stay green
  - interpretation draft renders the new Portuguese wording correctly
  - GNR/PSP explicit-location text uses the explicit service-location phrase
  - Job Log accepts interpretation rows without translation-only required values
  - per-profile distance defaults persist and reload safely
- Roadmap acceptance:
  - `SESSION_RESUME.md` points to this roadmap and the active wave plan
  - a fresh session can resume from the anchor without chat history

## 8. Rollout and fallback
- Implement in waves on this feature branch.
- Wave 1 should be independently testable and mergeable even before source-import waves land.
- If later extraction waves slip, the manual interpretation workflow must still remain usable.

## 9. Risks and mitigations
- Risk: translation assumptions are currently baked into Job Log normalization and honorarios generation.
  - Mitigation: make contracts explicitly kind-aware and preserve translation behavior with regression tests.
- Risk: interpretation km logic becomes inconsistent if tied only to ad hoc document fields.
  - Mitigation: store one-way city distances per profile and derive default ida/volta values from that map.
- Risk: GNR/PSP wording becomes over-automatic.
  - Mitigation: require explicit service-location confirmation before inserting the extra phrase.

## 10. Assumptions/defaults
- `job_type == "Interpretation"` is the only trigger for the interpretation honorarios branch.
- Remote/WebEx cases are deferred.
- Recipient handling is auto-suggest plus manual override.
- V1 source import is local file based only.
- Distances are scoped to the selected profile because secondary profiles may have different home addresses.

## 11. Current status
- Roadmap activated.
- Wave 1 manual interpretation core is implemented in the current worktree and remains the accepted floor for this roadmap.
- Wave 2 notification-first import is implemented and closed through Stage 3 validation on this branch.
- Wave 3 photo/screenshot fallback and saved-distance prompting are implemented and closed through Stage 4 validation on this branch.
- Wave 4 is closed as an explicit deferral packet because remote/WebEx and external photo-source integrations are outside the v1 roadmap non-goals.
- The interpretation honorarios roadmap is complete on this branch.
- `SESSION_RESUME.md` should point to this roadmap and the active wave plan while this branch is live.
