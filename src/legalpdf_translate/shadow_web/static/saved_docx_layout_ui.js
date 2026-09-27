import { createSavedDocxLayoutController } from "./saved_docx_layout.js";

const copy = (value) => JSON.parse(JSON.stringify(value));
const ROLES = ["institution", "reference", "recipient", "heading", "body", "list", "signature", "source_folio"];

export function savedLayoutMessage(code) {
  if (/unsafe_emphasis|invalid_emphasis/.test(code)) return "That phrase selection splits a protected literal, direction scope or character boundary. Remove the range and select a complete safe phrase; the wording is unchanged.";
  if (/page_break_requires_flow/.test(code)) return "Keep each paragraph containing a page boundary in plain flow, outside columns and notice panels.";
  if (/unsupported/.test(code)) return "This Word file contains a feature outside the supported paragraph-only import. Its original is preserved; use a supported saved copy or retain the current document.";
  if (/busy/.test(code)) return "This review has another operation in progress. Read its current state before retrying the same operation.";
  if (/incomplete/.test(code)) return "The review or build is incomplete. Check page associations and review flags; read a pending build before explicitly starting a new attempt.";
  if (/conflict/.test(code)) return "The saved generation or operation input changed. Read the current review and resolve the local edits before continuing.";
  if (/choose_files/.test(code)) return "Choose the source PDF, saved Word document and output language.";
  if (/file_too_large/.test(code)) return "The source PDF must be at most 64 MiB and the saved Word file at most 32 MiB.";
  if (/recover_save/.test(code)) return "Read the current review to recover the saved response. If that save is unavailable, explicitly discard the local request and review the last saved decisions.";
  return "Formatting review needs attention. Read the current review to recover an uncertain operation. Originals remain preserved.";
}

export function selectedCodepointRange(text, start, end) {
  if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end <= start || end > text.length) throw new Error("Select a phrase first.");
  const insideSurrogate = (at) => at > 0 && at < text.length && /[\uD800-\uDBFF]/.test(text[at - 1]) && /[\uDC00-\uDFFF]/.test(text[at]);
  if (insideSurrogate(start) || insideSurrogate(end)) throw new Error("The selection splits a Unicode character.");
  return [Array.from(text.slice(0, start)).length, Array.from(text.slice(0, end)).length];
}

export function rectangleFromPointer(start, end, bounds, page) {
  if (!(bounds.width > 0 && bounds.height > 0)) throw new Error("Wait for the source image to load.");
  const x = (v) => Math.max(0, Math.min(page.width_px, (v - bounds.left) * page.width_px / bounds.width));
  const y = (v) => Math.max(0, Math.min(page.height_px, (v - bounds.top) * page.height_px / bounds.height));
  const box = [Math.min(x(start.x), x(end.x)), Math.min(y(start.y), y(end.y)), Math.max(x(start.x), x(end.x)), Math.max(y(start.y), y(end.y))].map(Math.round);
  if (!box.every(Number.isFinite) || box[2] <= box[0] || box[3] <= box[1]) throw new Error("Draw a nonempty region on the source image.");
  return box;
}

export function flattenedParagraphIds(bands) {
  return bands.flatMap((band) => (band.kind === "columns" ? band.cells.flatMap((cell) => cell.groups) : band.groups)
    .flatMap((group) => group.paragraph_ids));
}

/** Replace a contiguous range without changing the order or ownership of any other paragraph. */
export function replaceLayoutRange(decisions, paragraphs, first, last, replacement) {
  if (!Number.isInteger(first) || !Number.isInteger(last) || first < 0 || last < first || last >= paragraphs.length) throw new Error("Choose a valid paragraph range.");
  const all = paragraphs.map((p) => p.id), selected = all.slice(first, last + 1);
  if (JSON.stringify(flattenedParagraphIds(replacement)) !== JSON.stringify(selected)) throw new Error("The layout must keep every selected paragraph in its original order.");
  const safeBreaks = new Set(paragraphs.filter((p) => p.has_page_break).map((p) => p.id));
  for (const band of replacement) for (const group of band.kind === "columns" ? band.cells.flatMap((cell) => cell.groups) : band.groups) {
    if ((band.kind === "columns" || group.panel) && group.paragraph_ids.some((id) => safeBreaks.has(id))) throw new Error("A paragraph containing a page boundary must stay in plain flow.");
  }
  const before = [], after = [];
  for (const band of decisions.bands) {
    const ids = flattenedParagraphIds([band]), begin = all.indexOf(ids[0]), end = begin + ids.length - 1;
    if (end < first) { before.push(copy(band)); continue; }
    if (begin > last) { after.push(copy(band)); continue; }
    if (band.kind === "columns" && (begin < first || end > last)) throw new Error("Select the entire existing column band before replacing it.");
    if (band.kind === "flow") {
      const left = [], right = [];
      for (const group of band.groups) {
        const split = (predicate) => group.paragraph_ids.filter((id) => predicate(all.indexOf(id)));
        const a = split((i) => i < first), b = split((i) => i > last);
        if (a.length) left.push({ ...copy(group), paragraph_ids: a });
        if (b.length) right.push({ ...copy(group), paragraph_ids: b });
      }
      if (left.length) before.push({ kind: "flow", groups: left });
      if (right.length) after.push({ kind: "flow", groups: right });
    }
  }
  const result = copy(decisions); result.bands = [...before, ...copy(replacement), ...after];
  if (JSON.stringify(flattenedParagraphIds(result.bands)) !== JSON.stringify(all)) throw new Error("Paragraph ownership is incomplete.");
  return result;
}

export function savedLayoutProblems(view, decisions) {
  if (!view || !decisions) return ["Import or reopen a saved document first."];
  const problems = [];
  const missing = decisions.paragraphs.filter((p) => !p.regions.length && !p.unmapped_reason.trim());
  if (missing.length) problems.push(`${missing.length} paragraph(s) need a source region or a retained-unmapped reason.`);
  if (JSON.stringify(flattenedParagraphIds(decisions.bands)) !== JSON.stringify(view.paragraphs.map((p) => p.id))) problems.push("Layout ownership must preserve every paragraph once and in order.");
  if (!view.pages.every((p) => decisions.review.pages_reviewed.includes(p.page_number))) problems.push("Review each complete source page.");
  if (!decisions.review.reviewer.trim() || !decisions.review.note.trim()) problems.push("Enter the reviewer and document review note.");
  if (!decisions.review.document_reviewed) problems.push("Confirm the complete document review.");
  return problems;
}

export function setNoticePanelRange(decisions, paragraphs, first, last) {
  const ids = paragraphs.slice(first, last + 1).map((p) => p.id);
  if (paragraphs.slice(first, last + 1).some((p) => p.has_page_break)) throw new Error("Page-boundary paragraphs cannot be inside panels.");
  const result = copy(decisions);
  for (const band of result.bands.filter((b) => b.kind === "columns")) {
    for (const cell of band.cells) {
      const cellIds = cell.groups.flatMap((g) => g.paragraph_ids);
      if (!ids.every((id) => cellIds.includes(id))) continue;
      const left = [], right = [];
      for (const group of cell.groups) {
        const before = group.paragraph_ids.filter((id) => paragraphs.findIndex((p) => p.id === id) < first);
        const after = group.paragraph_ids.filter((id) => paragraphs.findIndex((p) => p.id === id) > last);
        if (before.length) left.push({ ...group, paragraph_ids: before });
        if (after.length) right.push({ ...group, paragraph_ids: after });
      }
      cell.groups = [...left, { paragraph_ids: ids, panel: true }, ...right]; return result;
    }
  }
  return replaceLayoutRange(decisions, paragraphs, first, last, [{ kind: "flow", groups: [{ paragraph_ids: ids, panel: true }] }]);
}

export function mountSavedDocxLayout({ root, ...options }) {
  if (!root) return null;
  const doc = root.ownerDocument || document;
  let controller, sourceFile = null, wordFile = null, language = "EN", first = 0, last = 0, pageNumber = 1;
  let active = 0, region = null, dragging = null, localMessage = "", seenReview = "", seenOwner = "", initialized = false;
  const el = (tag, text, className) => { const node = doc.createElement(tag); if (text != null) node.textContent = String(text); if (className) node.className = className; return node; };
  const button = (text, action, disabled = false) => { const node = el("button", text); node.type = "button"; node.disabled = disabled;
    node.addEventListener("click", async () => { try { localMessage = ""; await action(); } catch (error) { localMessage = error.message; } render(); }); return node; };
  const field = (parent, label, node) => { const wrap = el("label", null, "saved-layout-field"); wrap.append(el("span", label), node); parent.append(wrap); return node; };
  const input = (type, value) => { const node = el("input"); node.type = type; node.value = value ?? ""; return node; };
  const select = (values, value) => { const node = el("select"); for (const choice of values) { const option = el("option", Array.isArray(choice) ? choice[1] : choice); option.value = Array.isArray(choice) ? choice[0] : choice; node.append(option); } node.value = String(value); return node; };
  const check = (parent, label, value, action, disabled = false) => { const node = input("checkbox", ""); node.checked = Boolean(value); node.disabled = disabled; field(parent, label, node);
    node.addEventListener("change", () => { try { action(node.checked); } catch (error) { localMessage = error.message; render(); } }); return node; };
  const update = (mutate, reviewOnly = false) => { const decisions = copy(controller.snapshot().decisions); mutate(decisions); controller.edit(decisions, { reviewOnly }); };
  const selectedIds = (view) => view.paragraphs.slice(first, last + 1).map((p) => p.id);
  const mutateSelected = (mutate) => update((d) => { const ids = new Set(selectedIds(controller.snapshot().view)); d.paragraphs.filter((p) => ids.has(p.paragraph_id)).forEach(mutate); });
  const settingsNumber = (parent, label, value, min, max, action, disabled, blank = true) => {
    const node = input("number", value); node.min = String(min); node.max = String(max); node.step = "0.5"; node.disabled = disabled;
    field(parent, label, node); node.addEventListener("change", () => { const next = node.value === "" && blank ? null : Number(node.value);
      if (next !== null && (!Number.isFinite(next) || next < min || next > max)) { localMessage = `${label} must be between ${min} and ${max}.`; render(); return; } action(next); }); return node;
  };
  function renderImport(state) {
    const form = el("div", null, "saved-layout-import");
    const pdf = input("file", ""); pdf.accept = ".pdf,application/pdf"; pdf.disabled = state.busy;
    pdf.addEventListener("change", () => { sourceFile = pdf.files?.[0] || null; }); field(form, "Original source PDF (up to 64 MiB)", pdf);
    const word = input("file", ""); word.accept = ".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"; word.disabled = state.busy;
    word.addEventListener("change", () => { wordFile = word.files?.[0] || null; }); field(form, "Current saved Word document (up to 32 MiB)", word);
    const lang = select([["EN", "English"], ["FR", "French"], ["AR", "Arabic"]], language); lang.disabled = state.busy;
    lang.addEventListener("change", () => { language = lang.value; }); field(form, "Word document language", lang);
    form.append(button(state.pending?.kind === "import" ? "Retry the same import" : "Import for formatting", () => controller.importFiles(sourceFile, wordFile, language), state.busy || state.dirty || state.capabilities?.available === false));
    if (state.capabilities?.available === false) form.append(el("p", "The local source renderer is unavailable. Saved reviews remain available; importing needs the supported local renderer."));
    if (sourceFile || wordFile) form.append(el("p", `Selected: ${sourceFile?.name || "PDF needed"}; ${wordFile?.name || "Word document needed"}.`));
    if (state.pending?.kind === "import") form.append(button("Start a different import and retain the earlier attempt", () => controller.startNewImport(), state.busy));
    root.append(form);
    const saved = el("div", null, "saved-layout-toolbar"); saved.append(button("Refresh saved formatting reviews", () => controller.initialize(), state.busy));
    if (state.reviewId) saved.append(button("Read current saved review", () => controller.read(), state.busy));
    root.append(saved);
    const list = el("div", null, "saved-layout-reviews");
    for (const item of state.reviews) list.append(button(`${item.target_lang} · ${item.page_count ?? "?"} source pages · ${item.status} · ${item.review_id.slice(0, 8)}`,
      () => controller.open(item.review_id), state.busy || state.dirty || Boolean(state.pending)));
    if (state.reviews.length) root.append(el("h3", "Saved formatting reviews"), list);
  }
  function renderSource(state, parent, locked) {
    const pages = state.view.pages, page = pages.find((p) => p.page_number === pageNumber) || pages[0]; if (!page) return;
    pageNumber = page.page_number;
    const picker = select(pages.map((p) => [String(p.page_number), `Source page ${p.page_number}`]), pageNumber);
    picker.addEventListener("change", () => { pageNumber = Number(picker.value); region = null; render(); }); field(parent, "Source page", picker);
    parent.append(el("p", "Draw a rectangle around a visible source region, then associate it with the selected Word paragraphs."));
    const frame = el("div", null, "saved-layout-image-frame"), image = el("img"); image.src = controller.imageUrl(pageNumber); image.alt = `Original source page ${pageNumber}`; image.draggable = false;
    const overlay = el("div", null, "saved-layout-rectangle"); overlay.hidden = !region;
    function draw(box) {
      overlay.hidden = !box; if (!box) return;
      overlay.style.left = `${box[0] / page.width_px * 100}%`; overlay.style.top = `${box[1] / page.height_px * 100}%`;
      overlay.style.width = `${(box[2] - box[0]) / page.width_px * 100}%`; overlay.style.height = `${(box[3] - box[1]) / page.height_px * 100}%`;
    }
    draw(region);
    image.addEventListener("pointerdown", (event) => { if (locked) return; event.preventDefault(); dragging = { x: event.clientX, y: event.clientY }; image.setPointerCapture?.(event.pointerId); });
    image.addEventListener("pointermove", (event) => { if (!dragging) return; try { draw(rectangleFromPointer(dragging, { x: event.clientX, y: event.clientY }, image.getBoundingClientRect(), page)); } catch { /* Zero-sized drag. */ } });
    image.addEventListener("pointerup", (event) => { if (!dragging) return; try { region = rectangleFromPointer(dragging, { x: event.clientX, y: event.clientY }, image.getBoundingClientRect(), page); localMessage = "Source region selected."; } catch (error) { localMessage = error.message; } dragging = null; render(); });
    image.addEventListener("pointercancel", () => { dragging = null; draw(region); });
    frame.append(image, overlay); parent.append(frame);
    parent.append(button("Associate selected region", () => { if (!region) throw new Error("Select a source region first.");
      mutateSelected((p) => { p.regions.push({ page_number: pageNumber, bbox_px: [...region] }); p.unmapped_reason = ""; }); }, locked || !region));
    // Numeric bounds are an accessible alternative to dragging; they remain image coordinates, never hashes or paths.
    const boxFields = el("details"); boxFields.append(el("summary", "Select region with coordinates")); const values = region ? [...region] : [0, 0, page.width_px, page.height_px];
    ["Left", "Top", "Right", "Bottom"].forEach((label, i) => settingsNumber(boxFields, label, values[i], 0, i % 2 ? page.height_px : page.width_px, (value) => { values[i] = value; }, locked, false));
    boxFields.append(button("Use these bounds", () => { if (values[2] <= values[0] || values[3] <= values[1]) throw new Error("Region bounds must enclose visible content."); region = [...values]; }, locked)); parent.append(boxFields);
    check(parent, "I reviewed every visible group on this source page", state.decisions.review.pages_reviewed.includes(pageNumber), (value) => update((d) => {
      d.review.pages_reviewed = d.review.pages_reviewed.filter((n) => n !== pageNumber); if (value) d.review.pages_reviewed.push(pageNumber); d.review.document_reviewed = false;
    }, true), locked);
  }
  function renderParagraphs(state, parent, locked) {
    const { paragraphs } = state.view; active = Math.min(active, paragraphs.length - 1); first = Math.min(first, paragraphs.length - 1); last = Math.max(first, Math.min(last, paragraphs.length - 1));
    parent.append(el("h3", "Current Word wording"), el("p", "Wording and paragraph order are fixed. Formatting creates a separate copy."));
    const selection = el("div", null, "saved-layout-toolbar");
    settingsNumber(selection, "Range starts at paragraph", first + 1, 1, paragraphs.length, (n) => { first = Math.floor(n) - 1; if (last < first) last = first; active = first; render(); }, locked, false).step = "1";
    settingsNumber(selection, "Range ends at paragraph", last + 1, first + 1, paragraphs.length, (n) => { last = Math.floor(n) - 1; render(); }, locked, false).step = "1";
    parent.append(selection);
    const windowStart = Math.floor(active / 40) * 40, windowEnd = Math.min(paragraphs.length, windowStart + 40);
    if (paragraphs.length > 40) parent.append(el("p", `Showing paragraphs ${windowStart + 1}–${windowEnd} of ${paragraphs.length}. The selected range may span several groups of paragraphs.`),
      button("Previous paragraphs", () => { active = Math.max(0, windowStart - 40); }, windowStart === 0),
      button("Next paragraphs", () => { active = windowEnd; }, windowEnd === paragraphs.length));
    const decisionsById = new Map(state.decisions.paragraphs.map((d) => [d.paragraph_id, d]));
    const list = el("div", null, "saved-layout-paragraph-list");
    paragraphs.slice(windowStart, windowEnd).forEach((p, offset) => {
      const index = windowStart + offset, decision = decisionsById.get(p.id);
      const card = el("article", null, `saved-layout-paragraph${index >= first && index <= last ? " selected" : ""}`);
      card.append(button(`Paragraph ${index + 1}${p.has_page_break ? " · page boundary" : ""}`, () => { active = first = last = index; region = null; }, locked));
      const text = el("pre", p.text || "(Empty paragraph)"); text.dir = state.view.target_lang === "AR" ? "rtl" : "auto"; card.append(text);
      card.append(el("small", `${decision.role} · ${decision.regions.length ? `${decision.regions.length} source region(s)` : decision.unmapped_reason ? "Retained unmapped: " + decision.unmapped_reason : "Needs source association"}`));
      decision.regions.forEach((r, regionIndex) => card.append(button(`View paragraph ${index + 1} source region ${regionIndex + 1}`, () => { pageNumber = r.page_number; region = [...r.bbox_px]; active = first = last = index; })));
      if (decision.regions.length) card.append(button(`Clear paragraph ${index + 1} regions`, () => update((d) => { d.paragraphs.find((v) => v.paragraph_id === p.id).regions = []; }), locked));
      list.append(card);
    }); parent.append(list);
    const unmapped = el("textarea"); unmapped.rows = 2; unmapped.disabled = locked;
    field(parent, "Reason to retain selected paragraphs without a source match", unmapped);
    parent.append(button("Record retained-unmapped reason", () => { if (!unmapped.value.trim()) throw new Error("Explain why this wording must remain unmatched.");
      mutateSelected((p) => { p.unmapped_reason = unmapped.value.trim(); p.regions = []; }); }, locked));
    const styling = el("details"); styling.open = true; styling.append(el("summary", `Style paragraphs ${first + 1}–${last + 1}`));
    const current = state.decisions.paragraphs[first];
    for (const [label, key, choices] of [["Role", "role", ROLES], ["Alignment", "alignment", ["inherit", "left", "center", "right", "justify"]]]) {
      const node = select(choices, current[key]); node.disabled = locked; field(styling, label, node); node.addEventListener("change", () => mutateSelected((p) => { p[key] = node.value;
        if (key === "role") { p.heading_level = node.value === "heading" ? 1 : 0; if (node.value !== "heading") p.heading_size_pt = null; } }));
    }
    settingsNumber(styling, "Space before (pt; blank inherits)", current.space_before_pt, 0, 36, (v) => mutateSelected((p) => { p.space_before_pt = v; }), locked);
    settingsNumber(styling, "Space after (pt; blank inherits)", current.space_after_pt, 0, 36, (v) => mutateSelected((p) => { p.space_after_pt = v; }), locked);
    if (current.role === "heading") {
      const level = select([1, 2, 3], current.heading_level); level.disabled = locked; field(styling, "Heading level", level);
      level.addEventListener("change", () => mutateSelected((p) => { if (p.role === "heading") p.heading_level = Number(level.value); }));
      settingsNumber(styling, "Heading size (pt; blank preserves original)", current.heading_size_pt, 1, 24, (v) => mutateSelected((p) => { if (p.role === "heading") p.heading_size_pt = v; }), locked);
    }
    for (const key of ["bold", "italic", "underline"]) check(styling, `Add ${key} to selected paragraphs`, current[key], (v) => mutateSelected((p) => { p[key] = v; }), locked);
    styling.append(el("p", "Existing emphasis, fonts and text direction are retained. Heading sizes cannot shrink the original text.")); parent.append(styling);
    const phrase = el("details"); phrase.append(el("summary", `Phrase emphasis in paragraph ${active + 1}`));
    const phraseText = el("textarea"); phraseText.readOnly = true; phraseText.value = paragraphs[active].text; phraseText.rows = 4; phraseText.dir = state.view.target_lang === "AR" ? "rtl" : "auto"; field(phrase, "Select exact phrase in immutable text", phraseText);
    phrase.append(el("p", "Select a complete phrase. Protected literals, direction controls and line/page boundaries cannot be split. Unsafe selections are declined when saved."));
    for (const style of ["bold", "italic", "underline"]) phrase.append(button(`Add phrase ${style}`, () => {
      if (phraseText.value !== paragraphs[active].text) throw new Error("This browser normalizes line endings in this paragraph. Phrase emphasis is unavailable; paragraph styling remains available and the original wording is preserved.");
      const [start, end] = selectedCodepointRange(phraseText.value, phraseText.selectionStart, phraseText.selectionEnd);
      update((d) => { const p = d.paragraphs[active], exact = p.emphasis.find((span) => start === span.start && end === span.end);
        if (exact) { exact[style] = true; return; }
        if (p.emphasis.some((span) => start < span.end && end > span.start)) throw new Error("Phrase ranges cannot partially overlap. Remove the earlier range first.");
        p.emphasis.push({ start, end, bold: style === "bold", italic: style === "italic", underline: style === "underline" }); p.emphasis.sort((a, b) => a.start - b.start); });
    }, locked));
    for (const [index, span] of state.decisions.paragraphs[active].emphasis.entries()) {
      const text = Array.from(paragraphs[active].text).slice(span.start, span.end).join("");
      phrase.append(el("p", `${text} · ${["bold", "italic", "underline"].filter((key) => span[key]).join(", ")}`), button(`Remove phrase range ${index + 1}`, () => update((d) => { d.paragraphs[active].emphasis.splice(index, 1); }), locked));
    } parent.append(phrase);
  }
  function renderLayout(state, parent, locked) {
    const panel = el("details"); panel.open = true; panel.append(el("summary", "Paragraph groups, columns and notice panels"));
    panel.append(el("p", "Select consecutive paragraphs above. Left-to-right physical column order stays fixed for all languages; Arabic text direction is preserved inside each column."));
    const selected = selectedIds(state.view), replace = (bands) => controller.edit(replaceLayoutRange(state.decisions, state.view.paragraphs, first, last, bands));
    panel.append(button("Use plain flow", () => replace([{ kind: "flow", groups: [{ paragraph_ids: selected, panel: false }] }]), locked),
      button("Use a shaded notice panel", () => controller.edit(setNoticePanelRange(state.decisions, state.view.paragraphs, first, last)), locked));
    let split = Math.max(1, Math.floor(selected.length / 2)), width = 40, gutter = 12, leftPanel = false, rightPanel = false;
    if (selected.length > 1) {
      settingsNumber(panel, "Paragraphs in left column", split, 1, selected.length - 1, (v) => { split = Math.floor(v); }, locked, false).step = "1";
      settingsNumber(panel, "Left column width (%)", width, 20, 80, (v) => { width = v; }, locked, false);
      settingsNumber(panel, "Column gutter (pt)", gutter, 0, 36, (v) => { gutter = v; }, locked, false);
      check(panel, "Shade left column group", leftPanel, (v) => { leftPanel = v; }, locked); check(panel, "Shade right column group", rightPanel, (v) => { rightPanel = v; }, locked);
      panel.append(button("Create two physical columns", () => replace([{ kind: "columns", widths_pct: [width, 100 - width], gutter_pt: gutter,
        cells: [{ groups: [{ paragraph_ids: selected.slice(0, split), panel: leftPanel }] }, { groups: [{ paragraph_ids: selected.slice(split), panel: rightPanel }] }] }]), locked));
    }
    panel.append(el("h4", "Schematic layout — Word rendering still needs review"));
    state.decisions.bands.forEach((band, bandIndex) => {
      const preview = el("div", null, `saved-layout-band ${band.kind}`);
      const cells = band.kind === "columns" ? band.cells : [{ groups: band.groups }];
      if (band.kind === "columns") preview.style.gridTemplateColumns = band.widths_pct.map((v) => `${v}fr`).join(" ");
      cells.forEach((cell, cellIndex) => {
        const column = el("div", null, "saved-layout-cell");
        cell.groups.forEach((group, groupIndex) => {
          const positions = group.paragraph_ids.map((id) => state.view.paragraphs.findIndex((p) => p.id === id) + 1);
          const block = el("div", `Paragraphs ${positions[0]}–${positions.at(-1)}`, group.panel ? "saved-layout-panel-preview" : "saved-layout-group-preview");
          check(block, "Notice shading", group.panel, (value) => update((d) => {
            const g = d.bands[bandIndex].kind === "columns" ? d.bands[bandIndex].cells[cellIndex].groups[groupIndex] : d.bands[bandIndex].groups[groupIndex];
            if (value && state.view.paragraphs.some((p) => p.has_page_break && g.paragraph_ids.includes(p.id))) throw new Error("Page-boundary paragraphs cannot be inside panels."); g.panel = value;
          }), locked); column.append(block);
        }); preview.append(column);
      }); panel.append(preview);
    }); parent.append(panel);
  }
  function renderReview(state, parent, locked) {
    const section = el("div", null, "saved-layout-review"); section.append(el("h3", "Complete the formatting review"));
    const kind = select([["operator_review", "Operator source-image review"], ["assistant_source_image_review", "Assistant source-image review"]], state.decisions.review.reviewer_kind);
    kind.disabled = locked; field(section, "Review provenance", kind); kind.addEventListener("change", () => update((d) => { d.review.reviewer_kind = kind.value; }, true));
    const reviewer = input("text", state.decisions.review.reviewer); reviewer.disabled = locked; field(section, "Reviewer", reviewer);
    reviewer.addEventListener("change", () => update((d) => { d.review.reviewer = reviewer.value; }, true));
    const note = el("textarea"); note.value = state.decisions.review.note; note.rows = 3; note.disabled = locked; field(section, "Review note and retained source differences", note);
    note.addEventListener("change", () => update((d) => { d.review.note = note.value; }, true));
    check(section, "I reviewed all wording, source associations, layout ownership and retained differences", state.decisions.review.document_reviewed,
      (value) => update((d) => { d.review.document_reviewed = value; }, true), locked);
    const problems = savedLayoutProblems(state.view, state.decisions); const list = el("ul"); problems.forEach((p) => list.append(el("li", p))); section.append(list);
    const unmapped = state.decisions.paragraphs.filter((p) => p.unmapped_reason);
    if (unmapped.length) { section.append(el("strong", `${unmapped.length} retained-unmapped paragraph(s): source completeness is qualified.`));
      for (const p of unmapped) section.append(el("p", `${p.paragraph_id}: ${p.unmapped_reason}`)); }
    for (const qualification of state.view.qualifications || []) section.append(el("p", typeof qualification === "string" ? qualification : qualification.message || qualification.code || "Retained source qualification"));
    section.append(el("p", "Saving and building verify preservation of the Word wording. Compare every page of the separate output before accepting its rendered layout."));
    if (state.pending?.kind === "save" && !state.pendingSavePayloadAvailable) section.append(el("p", "The interrupted local save payload is unavailable after this reload. The last saved decisions are displayed. Read the current review to recover its receipt, or explicitly discard the unavailable local request."));
    section.append(button(state.pending?.kind === "save" ? "Retry the exact save" : "Save formatting review", () => controller.save(), state.busy || !state.verified || state.conflict || Boolean(state.pending && state.pending.kind !== "save") || Boolean(state.pending?.kind === "save" && !state.pendingSavePayloadAvailable)));
    section.append(button(state.pending?.kind === "build" ? "Recover the same build" : "Build separate Word copy", () => controller.build(), state.busy || state.dirty || problems.length > 0 || state.conflict || Boolean(state.pending && state.pending.kind !== "build")));
    const attempt = state.pending?.kind === "build" && state.view.builds?.find((b) => b.operation_nonce === state.pending.nonce);
    if (attempt?.status === "incomplete") section.append(button("Start a new build attempt after the incomplete attempt", () => controller.build({ newAttempt: true }), state.busy));
    if (state.dirty || state.conflict || state.pending?.kind === "save") section.append(button("Discard local edits and use the last read saved review", () => controller.discardChanges(), state.busy || !state.verified || Boolean(state.pending?.kind === "build" && !state.canAbandonBuild)));
    if (state.pending?.kind === "build" && state.canAbandonBuild) section.append(button("Use latest saved review and retain previous build records", () => controller.discardChanges(), state.busy || !state.verified));
    for (const artifact of state.view.artifacts || []) {
      const url = controller.artifactUrl(artifact); if (!url) continue;
      const link = el("a", `Download separate Word copy · review generation ${artifact.generation}`); link.href = url; link.download = ""; link.className = "saved-layout-download"; section.append(link);
      for (const [kind, label] of [["source_map", "Download source association record"], ["receipt", "Download preservation receipt"]]) {
        const recordUrl = controller.artifactUrl(artifact, kind); if (!recordUrl || !artifact.kinds?.includes(kind)) continue;
        const record = el("a", `${label} · generation ${artifact.generation}`); record.href = recordUrl; record.download = ""; record.className = "saved-layout-download"; section.append(record);
      }
    } parent.append(section);
  }
  function render() {
    if (!controller) return;
    const state = controller.snapshot(), owner = `${state.owner.runtimeMode}:${state.owner.workspaceId}`;
    if (owner !== seenOwner) { seenOwner = owner; sourceFile = wordFile = null; region = null; initialized = false; localMessage = ""; }
    if (state.reviewId !== seenReview) { seenReview = state.reviewId; first = last = active = 0; pageNumber = 1; region = null; }
    root.replaceChildren(); root.append(el("p", "Restore recognizable source headers, headings, emphasis, columns and notices in a separate saved Word copy. This local workflow preserves current wording and does not translate it."));
    if (state.busy) root.append(el("p", "Working locally…", "saved-layout-status"));
    if (state.errorCode || localMessage) { const message = el("p", localMessage || `${savedLayoutMessage(state.errorCode)} (${state.errorCode})`, "saved-layout-error"); message.setAttribute("role", "alert"); root.append(message); }
    if (state.conflict) root.append(el("p", "Another save or changed input conflicts with this operation. Read the current review, then explicitly discard local edits before continuing."));
    renderImport(state);
    if (!state.view || !state.decisions) return;
    root.append(el("h3", `${state.view.target_lang} saved Word review · generation ${state.view.generation} · ${state.view.status}${state.dirty ? " · unsaved changes" : ""}`));
    const locked = state.busy || !state.verified || Boolean(state.pending) || state.conflict;
    const comparison = el("div", null, "saved-layout-comparison"), source = el("section", null, "saved-layout-source"), words = el("section", null, "saved-layout-words");
    renderSource(state, source, locked); renderParagraphs(state, words, locked); comparison.append(source, words); root.append(comparison);
    renderLayout(state, root, locked); renderReview(state, root, locked);
  }
  // Input change can fire while focus moves to Save. Let that click complete before
  // replacing controls, so a blur-triggered change never consumes the user's click.
  controller = createSavedDocxLayoutController({ ...options, onChange: (state) => {
    if (doc.defaultView && state.dirty && !state.busy && !state.pending) doc.defaultView.setTimeout(render, 0);
    else render();
  } }); render();
  const disclosure = root.closest?.("details");
  const initialize = () => { if (!initialized) { initialized = true; return controller.initialize(); } return null; };
  disclosure?.addEventListener("toggle", () => { if (disclosure.open) initialize(); });
  const scopeChanged = () => { if (controller.sync() && disclosure?.open) initialize(); };
  globalThis.window?.addEventListener?.("legalpdf:route-state-changed", scopeChanged);
  return { controller, render, initialize, dispose: () => globalThis.window?.removeEventListener?.("legalpdf:route-state-changed", scopeChanged) };
}
