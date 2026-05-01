# Google Photos Interpretation Runbook

## Use This Guide When
- You are helping with Google Photos import for an Interpretation request.
- You need the OAuth/Picker setup checklist.
- You need to diagnose Google Photos config, sign-in, Picker session, or import completion.
- You need the metadata provenance and artifact hygiene rules for this feature.

## Do Not Use This Guide For
- PDF-to-DOCX Translation runs.
- Gmail intake/draft sending.
- OpenAI model or prompt decisions.
- Final honorarios generation without normal manual review.
- Any workflow that would require printing secrets, raw OAuth/Picker URLs, tokens, account identifiers, media IDs/base URLs, private photos, or private document text.

## For Agents: Support Interaction Contract
Use this order:
1. Confirm the task is Interpretation-only.
2. Run the safe config/status gate before live OAuth or Picker work.
3. Use shadow mode first for diagnostics.
4. Record method/path-only routes with query strings removed.
5. Stop at the narrow failing layer: config, OAuth, callback, Picker session, media import, or Review Case Details.
6. Keep user-facing answers to safe booleans, source labels, whitelisted categories, and presence/absence metadata.

## Canonical Deference Rule
This runbook is the feature support guide. For app-wide architecture/status, defer to `APP_KNOWLEDGE.md`. For exact route behavior and payload contracts, source code is final truth. For validation commands, defer to `docs/assistant/VALIDATION.md` when it is stricter.

## Quick Start (No Technical Background)
1. Open the browser app.
2. Go to `New Job`.
3. Switch to `Interpretation`.
4. Connect Google Photos if needed.
5. Choose one non-private Google Photos test image.
6. Wait for `Review Case Details`.
7. Check and correct the service date, service city, case city, and distance before saving or generating honorarios output.

## Terms in Plain English
- Google Photos Picker: Google's screen where the user chooses which photos to share with the app.
- OAuth: the Google sign-in permission step.
- Picker session: a temporary Google Photos selection session created by the app.
- `mediaItemsSet`: the safe status flag that means the user finished selecting media.
- Provenance: supporting context about where a date or file came from, not a final legal value by itself.
- Shadow mode: an isolated browser-app workspace for tests and diagnostics.
- Live mode: the real app workspace that uses real settings, profiles, job log, and outputs.

## Purpose
Use this runbook for the Google Photos import path inside the Interpretation workflow.
It is intentionally not a Translation workflow. Translation target-language controls,
Translation routes, Gmail sending, and final honorarios export are out of scope until
the user has reviewed the imported Interpretation case details.

Primary workflow:
1. Open `New Job`.
2. Switch to `Interpretation`.
3. Choose `Choose from Google Photos`.
4. Select exactly one non-private test photo first.
5. Import the selected image and metadata into the existing photo/OCR autofill path.
6. Review the existing `Review Case Details` drawer.
7. Continue through the normal deterministic interpretation honorarios review/export path only after manual confirmation.

## Source-Backed Architecture
Google Photos import uses the Google Photos Picker API, not broad Library API access.
Official references:
- [Get started with the Picker API](https://developers.google.com/photos/picker/guides/get-started-picker)
- [Configure your app](https://developers.google.com/photos/overview/configure-your-app)
- [Create and manage sessions](https://developers.google.com/photos/picker/guides/sessions)

Important architecture rules:
- Use the minimal scope:
  `https://www.googleapis.com/auth/photospicker.mediaitems.readonly`
- Do not use broad Library API scopes such as `photoslibrary.readonly`, `photoslibrary`, or `photoslibrary.sharing` for this feature.
- Google Photos APIs require signed-in user OAuth; service accounts are not supported for user-library access.
- Picker flow:
  1. Check Google Photos OAuth status.
  2. Create a Picker session.
  3. Open the returned Picker URL in the browser, with the visible `Open Google Photos Picker` fallback when needed.
  4. Poll the session until `mediaItemsSet=true`.
  5. List the selected media items.
  6. Download the selected image bytes for the existing Interpretation photo/OCR autofill pipeline.
  7. Clean up the Picker session.
- For web flows, appending `/autoclose` to the browser-opened Picker URL is allowed. Do this only for browser navigation, not for diagnostics or artifacts.

## Metadata Policy
Treat Google Photos metadata as provenance, not as final legal facts.

- Google Photos `createTime` maps to safe photo-taken provenance only.
- Downloaded EXIF date, when present, is also safe photo-date provenance only.
- OCR/legal text is the first source for `service_date`; when OCR does not recover a legal date, the app may prefill `service_date` from safe photo-date provenance as an editable fallback.
- `service_city` and `case_city` must come from OCR/document text or explicit user confirmation.
- Do not blindly set `service_city` from a Google Photos place label.
- Google Photos place/location fields are unavailable from the official Picker selected-media payload used by this app, even when the Google Photos UI itself shows a place label.
- Downloaded EXIF GPS was absent or unproven in current validation.
- User confirmation remains required before generating the honorarios document.

## OAuth Setup Runbook
1. Create or select a Google Cloud project.
2. Enable **Google Photos Picker API**. Do not confuse it with the separate Google Picker API.
3. Configure Google Auth Platform / OAuth consent.
4. Add the Picker scope:
   `https://www.googleapis.com/auth/photospicker.mediaitems.readonly`
5. Add the local operator account as a test user while the app is in testing mode.
6. Create a **Web application** OAuth client.
7. Configure authorized JavaScript origins:
   - `http://127.0.0.1:8890`
   - `http://127.0.0.1:8877`
8. Configure authorized redirect URIs exactly, with no trailing slash:
   - `http://127.0.0.1:8890/api/interpretation/google-photos/oauth/callback`
   - `http://127.0.0.1:8877/api/interpretation/google-photos/oauth/callback`
9. Set local environment variables:
   - `LEGALPDF_GOOGLE_PHOTOS_CLIENT_ID`
   - `LEGALPDF_GOOGLE_PHOTOS_CLIENT_SECRET`
10. The client secret must be the full secret from the same OAuth client as the client ID. Do not paste a masked value, last characters only, placeholder text, or the client ID as the secret.
11. Restart the terminal/app process after changing environment variables, or rely on the Windows User environment fallback when the process did not inherit new User-scope values.
12. If a credential is exposed during testing, delete or rotate that OAuth client before production-like use and rerun the config gate with a fresh unexposed credential.

## Configuration Gate
Run the safe status/config gate before live OAuth:
- `configured=true`
- `client_id_source=process_env` or `windows_user_env` unless settings explicitly provides the non-secret client ID
- `client_secret_source=process_env` or `windows_user_env`
- scope exactly `https://www.googleapis.com/auth/photospicker.mediaitems.readonly`
- shadow redirect exactly `http://127.0.0.1:8890/api/interpretation/google-photos/oauth/callback`
- live redirect exactly `http://127.0.0.1:8877/api/interpretation/google-photos/oauth/callback`

Never print credential values, OAuth codes, state values, tokens, raw OAuth URLs, or query strings.

## Troubleshooting Matrix
| Symptom | Safe likely cause | Safe fix |
| --- | --- | --- |
| `client_id_configured=false` | Environment variable not visible to the app process | Check process env and Windows User env fallback; restart app process if needed |
| PowerShell sees env vars but app reports empty | Process inheritance gap | Use the Windows User env fallback and rerun the config gate |
| `client_secret_env_configured=false` | Missing, placeholder, masked, too-short, or client-ID-shaped secret | Rerun the strict reset/checklist and paste the full matching secret |
| `token_exchange_invalid_client` | Mismatched Client ID/Secret, stale secret, wrong client, masked secret, or old invalid secret | Create a fresh Web application OAuth client, copy both values from that same client, reset env vars, restart, and rerun OAuth diagnostic |
| `redirect_uri_mismatch` | Redirect URI differs by port/path/trailing slash | Add the exact local callback URI in Google Cloud |
| `user_not_test_user` or access blocked | OAuth consent app is still in testing and account is not listed | Add the Google account as a test user |
| API not enabled | Google Photos Picker API is disabled or wrong API was enabled | Enable Google Photos Picker API |
| Connect visible but no `/connect` POST | Disabled secondary button blocked the primary action | Fixed by guarding only the Connect button for the Connect action |
| `/connect` works but no Google tab opens | Popup/noopener/browser behavior | Use visible `Open Google sign-in`; do not print or persist the URL |
| Callback route reached but status stays disconnected | State/code/token-exchange/token-save/token-path problem | Inspect safe callback diagnostics only |
| Callback not observed | Consent not completed, popup issue, Google error, or redirect problem | Run OAuth consent watch with method/path-only route logging |
| Picker session created but no visible Picker | Popup/noopener/browser behavior | Use visible `Open Google Photos Picker`; do not print or persist the Picker URL |
| Picker polling stays `mediaItemsSet=false` | User did not finish selection, wrong account, picker behind another window, or timeout | Ask the user to finish one non-private selection and wait for the Done screen |
| User sees Google Photos `Done! Continue in the other app or device` | Selection completed | Return to LegalPDF and continue polling; expect media-items list and import routes |
| Successful Picker completion | Expected route sequence | session create -> poll -> `mediaItemsSet=true` -> media-items list -> import -> Review Case Details -> cleanup |

## Live Validation Checklist
Use shadow mode first, normally with port `8890`.

Acceptance evidence:
- Config gate passes.
- OAuth `connected=true`.
- Token store is present.
- `Choose from Google Photos` is enabled.
- Picker session is created.
- User selects exactly one non-private photo.
- Google Photos completion screen appears or the tab closes after selection.
- `mediaItemsSet=true` is observed.
- Selected media items are listed.
- Import route is called.
- Selected image imports.
- Existing `Review Case Details` drawer opens.
- Translation controls are avoided.
- `createTime` and downloaded EXIF date remain photo-date provenance only, with OCR/legal date preferred.
- `service_city` and `case_city` remain OCR/document- or user-confirmed.
- Review Details does not silently copy case city or case-city distance into an unproven service city.
- Distinct case/service evidence remains distinct and KM uses the effective service city profile distance.
- Court email options follow the case city.
- Picker session cleanup succeeds.
- Focused tests and `scripts/validate_dev.ps1` pass.

Stop before Picker/photo import when debugging OAuth. Proceed to Picker only after `connected=true`.

## Artifact Hygiene
Sanitized route logs may include only:
- timestamp
- HTTP method
- path without query string

Normalize session IDs in logs, for example:
- `/api/interpretation/google-photos/session/{session}`
- `/api/interpretation/google-photos/session/{session}/media-items`

Artifacts must never include:
- Client ID values or Client Secret values
- OAuth code, state, access token, refresh token, or ID token
- raw OAuth URLs, Picker URLs, Picker URL values, or URL query strings
- `.env` files, token files, or private settings
- raw media IDs or media base URLs
- Google account identifiers
- Gmail data
- raw photos
- private document text
- generated private DOCX/PDF outputs

Safe words such as `mediaItemsSet`, `pickerUri`, `baseUrl`, or `auth_url` may appear only as concept names in docs or code comments, not as real value-bearing artifacts.

Review patches for this feature must include untracked Google Photos source, test, and docs files as well as tracked modifications. Do not rely on ordinary `git diff` alone when untracked feature files still exist.

## Validated State
On `2026-04-29`, the feature branch validation proved:
- config gate passed
- OAuth reached `connected=true`
- token store existed
- Picker session create/poll/list/import path worked
- the Google Photos completion screen counted as completed selection
- selected image import reached `Review Case Details`
- Translation controls were avoided
- `createTime` and downloaded EXIF date stayed photo-date provenance only, with OCR/legal date preferred
- service city stayed OCR/document- or user-confirmed; Google Photos place/location remained unavailable from Picker API
- the accepted live Review Details result kept Beja case metadata, Beja court email, `Serviço de Turno | Moura`, service date `2026-04-25`, KM `26`, and `service_same=false`
- no final DOCX/PDF was generated during the Google Photos validation
- focused tests passed
- sanitized artifact scan passed

If any testing OAuth credential is exposed during troubleshooting, delete or rotate it before production-like use.
