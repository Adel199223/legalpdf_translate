# Review source text and DOCX formatting

Availability: these optional controls are available in builds containing the reviewed-source and DOCX implementation. Check the [current handoff](../HANDOFF.md) for the verified build and acceptance limits.

## Use This Guide When

Use this optional workflow to check the source text before translation, then arrange the saved translation into editable paragraphs, tables, headers and footers. Ordinary **Translate** remains available. Your acceptance records your decisions; it does not certify legal accuracy or guarantee the final Word layout.

## Before you start

Use the normal manual PDF upload. This source-review workflow needs browser-rendered pages, the complete page selection, retained intermediates and an available local OCR baseline. It declines when OCR is off, only an API OCR engine is selected, local evidence is unavailable or only part of the document is selected. It does not purchase an OCR fallback automatically.

Check your saved settings first. If you deliberately change them after acquiring source evidence, start a fresh review context. The review controls do not silently change your saved settings or global model choices.

## Quick Start (No Technical Background)

### 1. Review and accept the source

1. Upload the PDF and choose **Review source before translating**.
2. Compare the whole page image with **Original local OCR text (unchanged)**. Select the relevant OCR blocks and choose an action: retain correct text, replace incorrect text, omit a non-text artifact, or transcribe text missing from the baseline. For a missing passage, select its region on the image. Explain why the action is correct.
3. Choose **Add this explicit action**. This records a local decision; it does not yet save or accept the page. For example, retain a correctly read date; replace an OCR error only after checking the visible source.
4. Check the actions, reading order, page boundary and findings. Enter **Page reviewer**, complete the page-review checks and choose **Save page decisions**. Repeat for every page.
5. Enter **Whole-source reviewer**, explicitly confirm the whole-source review and choose **Accept reviewed source**.
6. Choose **Translate reviewed source**. The translation uses the accepted source and normal translation accounting. Source review itself does not send a translation request.

No hashes, file paths or JSON are required in the browser. Selecting a region or adding an action does not approve it automatically.

## 2. Prepare formatting review

On the completed job, choose **Review DOCX formatting**. This action is available for supported jobs that retain their reviewed source context.

Choose whether to **Create a page-matched derivative**, then select **Prepare formatting review**. That derivative starts each source page on a new output page while preserving your original saved page-break setting and original output. If page breaks are saved as off, keeping that choice without the derivative is currently unsupported for this reviewed formatting profile. Incompatible bidi-control settings also cause an explicit decline.

This panel arranges saved translation text; it does not edit that text or buy another translation.

## 3. Map the page text and layout

1. Compare the source image, source text and translation. Use **Show full-resolution page image** when needed.
2. Select the source passage and choose **Use selected source text**. Independently select its translation and choose **Use selected translation text**. Translations can have different lengths and word order; matching character positions are not assumed.
3. Select the source rectangle and choose the role, alignment and emphasis. Choose **Add this explicit fragment**.
4. Assign each fragment once to a body paragraph, table cell, header, footer or local folio. Account for all source and translated text. If a selection cuts a character sequence or protected literal, use the validation message to select the complete passage; do not remove text to bypass the check.
5. Check the whole page and its source-to-translation mappings, enter the reviewer details and choose **Save page formatting**. Repeat for every page. Finish or cancel an unfinished fragment edit before reordering fragments.

### Tables, groups and spacing

Use **Add empty table** to define columns, rows and cell ownership. Put each selected fragment in its correct cell and check row order. Optional column gaps must be supported by the visible source; they are not guessed automatically.

Document groups describe joined documents and must cover every page once, in order. Review local page numbering and headers/footers for each group.

Review **Text separators inside reviewed table cells** separately from **Vertical spacing between source regions**. Both vertical-spacing choices preserve complete text; they change the amount of vertical space, not what is retained.

Enter **Document formatting reviewer** and an explanation. Check **I reviewed every page, its text mappings and the document groups**, then choose **Save document review**. A subsequent page change clears document completion, including a change saved in another browser view.

## 4. Accept, build and download

Enter the final reviewer and explicit acceptance, then choose **Accept formatting revision**. Use **Check this exact revision**, followed by **Build DOCX from this revision** and **Download this reviewed DOCX**.

The reviewed DOCX is a distinct output. Keep the original output and review the final Word file before delivery, especially pagination, tables, headers/footers, Arabic/Latin direction and existing translation findings. Editing retained target text invalidates its reviewed mapping; edits made directly in Word are not imported into this review.

Saving formatting decisions does not change the original DOCX. If review stops before acceptance and a successful build, the original translation file remains the original output; it has not acquired the unfinished formatting edits.

## Recovering a lost response

The rejected-submission and reopened-draft improvements below are currently in the isolated test build. Check [the current handoff](../HANDOFF.md) before expecting them in the daily-use app.

| What happened | What to do |
| --- | --- |
| A page-save response was lost | Read the current review. If offered, retry that exact save. Resolve a conflicting saved generation explicitly. |
| Source or formatting acceptance was interrupted | Keep the original submission details and use **Retry this exact source submission** or **Retry this exact formatting submission**. |
| Formatting submission was rejected before acceptance | Choose **Read current review / recover response**. If the server confirms the same unsubmitted draft, **Discard the unsubmitted request and continue editing** lets you correct it. This button is unavailable when submission remains uncertain or an accepted revision was observed. |
| Translation start was interrupted | Use **Recover this exact translation start**. Do not start another translation to recover the first one. |
| DOCX build was interrupted | Use **Recover this exact DOCX build**. A pending or unknown result is not permission to repeat the build. |
| You reloaded the browser | Read the current review. A confirmed unsubmitted draft can be completed, explicitly accepted and built in the reopened session. Recovery of an existing revision still works only for its exact associated operation; an unknown stored operation can remain read-only. |
| The server restarted | This UI cannot restore its previous review handle. Browser drafts and operation associations are not guaranteed to survive a server restart. |
| Source, settings or saved target text changed | Expect a stale-review or conflict notice. Obtain a fresh valid context or review; do not repair checkpoints or hashes manually. |

After a confirmed translation start, the upload widget may clear normally. That cleanup does not mean your settings changed.

## Advanced local use

The separate `python -m legalpdf_translate.formatting_review_cli` command provides `draft`, `submit`, `inspect` and `rebuild` operations with an explicit run, profile and revision. It requires retained evidence files and is an advanced path. The browser generates these bindings through the review controls; existing ordinary CLI commands do not automatically select a reviewed revision.

## Terms in Plain English

- **Fragment:** source text, its translated passage and the region you selected on the source page.
- **Revision:** the exact accepted set of review decisions.
- **Derivative:** a separately built DOCX that keeps the original output intact.

## Do Not Use This Guide For

Use the [PDF translation guide](PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md) for ordinary translation or Gmail intake. This optional review does not edit translated text, restore unknown operations or certify legal accuracy.

## For Agents: Support Interaction Contract

Use the visible labels and explain the next review action in plain language. Check the actual build, saved settings and current notice before suggesting a recovery action; never ask the operator to manufacture hashes, review acceptance or checkpoint state.

## Canonical Deference Rule

This is a user guide. Defer to [APP_KNOWLEDGE.md](../../../APP_KNOWLEDGE.md) for architecture and current status; source code is final truth when documentation conflicts.
