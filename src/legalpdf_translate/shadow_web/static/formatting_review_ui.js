import { createFormattingReviewController, formattingPageComplete, formattingReviewMessage, formattingValuesEqual } from "./formatting_review.js";

const clone = (value) => JSON.parse(JSON.stringify(value));
let controlSequence = 0;
const roles = ["header", "body", "signature", "footer", "folio"];
const alignments = ["left", "right", "center", "justify"];
export function blankFormattingPage() {
  return {fragments: [], header: [], body: [], footer: [], folio_fragment_number: null,
    full_page_review_completed: false, source_target_mapping_reviewed: false, reviewer: "", review_note: ""};
}
export function blankFormattingDocument() {
  return {groups: [], all_pages_reviewed: false, allow_pipe_cell_boundaries: false,
    preserve_source_gaps: false, reviewer: "", review_note: ""};
}
/** DOM text selections count UTF-16 units; the reviewed mapping counts codepoints. */
export function selectedCodepointRange(text, start, end) {
  if (typeof text !== "string" || !Number.isInteger(start) || !Number.isInteger(end)
      || start < 0 || end > text.length || start >= end) throw new Error("Select the intended text first.");
  const splitsPair = (at) => at > 0 && at < text.length && /[\uD800-\uDBFF]/.test(text[at - 1]) && /[\uDC00-\uDFFF]/.test(text[at]);
  if (splitsPair(start) || splitsPair(end)) throw new Error("Select complete characters, including the whole symbol.");
  return [Array.from(text.slice(0, start)).length, Array.from(text.slice(0, end)).length];
}
export const codepointSlice = (text, range) => Array.from(text).slice(range[0], range[1]).join("");
function mapReferences(decision, convert) {
  const list = (values) => values.map(convert).filter((n) => n !== null);
  decision.header = list(decision.header); decision.footer = list(decision.footer);
  decision.body = decision.body.flatMap((block) => {
    if (Object.hasOwn(block, "fragment_number")) { const n = convert(block.fragment_number); return n === null ? [] : [{fragment_number: n}]; }
    return [{...block, rows: block.rows.map((row) => row.map(list))}];
  });
  if (decision.folio_fragment_number !== null) decision.folio_fragment_number = convert(decision.folio_fragment_number);
}
export function removeFormattingFragment(decision, number) {
  const result = clone(decision); result.fragments.splice(number - 1, 1);
  mapReferences(result, (n) => n === number ? null : n > number ? n - 1 : n);
  result.full_page_review_completed = false; result.source_target_mapping_reviewed = false;
  return result;
}
export function moveFormattingFragment(decision, number, direction) {
  const other = number + direction;
  if (![-1, 1].includes(direction) || other < 1 || other > decision.fragments.length) return clone(decision);
  const result = clone(decision);
  [result.fragments[number - 1], result.fragments[other - 1]] = [result.fragments[other - 1], result.fragments[number - 1]];
  mapReferences(result, (n) => n === number ? other : n === other ? number : n);
  result.full_page_review_completed = false; result.source_target_mapping_reviewed = false;
  return result;
}
export function formattingPageProblem(page, decision) {
  if (!decision.fragments.length) return "Add the reviewed source and target fragments before saving.";
  if (!decision.reviewer.trim() || !decision.review_note.trim()) return "Enter the page reviewer and explain the review.";
  const owned = [...decision.header, ...decision.footer];
  for (const block of decision.body) {
    if (Object.hasOwn(block, "fragment_number")) { owned.push(block.fragment_number); continue; }
    if (!block.column_widths.length || block.column_widths.length > 4 || block.column_widths.some((n) => !Number.isInteger(n) || n < 1)
        || block.column_widths.reduce((a, b) => a + b, 0) !== 100) return "Enter whole-number column widths totalling 100%.";
    if (!block.rows.length || block.rows.some((row) => row.length !== block.column_widths.length || row.every((cell) => !cell.length))) {
      return "Each table needs reviewed rows, with at least one fragment in every row.";
    }
    if (block.column_gaps_px && (block.column_gaps_px.length !== block.column_widths.length - 1
        || block.column_gaps_px.some((n) => !Number.isFinite(n) || n < 0))) return "Enter each reviewed space between columns in source-image pixels.";
    owned.push(...block.rows.flat(2));
  }
  if (decision.body.some((block) => block.column_gaps_px)
      && decision.body.some((block) => Object.hasOwn(block, "rows") && !block.column_gaps_px)) {
    return "When using measured column spacing, review and enter it for every table on this page.";
  }
  if (owned.length !== decision.fragments.length || new Set(owned).size !== owned.length
      || owned.some((n) => !Number.isInteger(n) || n < 1 || n > decision.fragments.length)) return "Assign every fragment exactly once to a header, body paragraph, table cell or footer.";
  if (decision.folio_fragment_number !== null && (!decision.footer.includes(decision.folio_fragment_number)
      || decision.fragments[decision.folio_fragment_number - 1]?.role !== "folio")) return "Select the page-local number from a folio fragment assigned to the footer.";
  return "";
}
function element(doc, tag, text = "", className = "") {
  const node = doc.createElement(tag); if (text) node.textContent = text; if (className) node.className = className; return node;
}
function button(doc, label, fn, disabled = false) {
  const node = element(doc, "button", label); node.type = "button"; node.disabled = disabled; node.addEventListener("click", fn); return node;
}
function field(doc, label, control) {
  const node = element(doc, "label", "", "formatting-review-field");
  control.id = `formatting-review-control-${++controlSequence}`; node.htmlFor = control.id;
  control.setAttribute("aria-label", label);
  node.append(element(doc, "span", label), control); return node;
}
function input(doc, value, change, {disabled = false, number = false, readOnly = false, textarea = false} = {}) {
  const node = element(doc, textarea ? "textarea" : "input"); node.value = value ?? ""; node.disabled = disabled;
  node.readOnly = readOnly; node.dir = "auto"; if (!textarea) node.type = number ? "number" : "text";
  if (!readOnly) node.addEventListener("input", () => change(node.value)); return node;
}
function select(doc, values, value, change, disabled = false) {
  const node = element(doc, "select"); node.disabled = disabled;
  for (const [key, label] of values) { const option = element(doc, "option", label); option.value = String(key); node.append(option); }
  node.value = String(value); node.addEventListener("change", () => change(node.value)); return node;
}
function checkbox(doc, label, checked, change, disabled = false) {
  const node = element(doc, "label", "", "formatting-review-check"), control = element(doc, "input");
  control.type = "checkbox"; control.checked = checked; control.disabled = disabled;
  control.id = `formatting-review-control-${++controlSequence}`; node.htmlFor = control.id; control.setAttribute("aria-label", label);
  control.addEventListener("change", () => change(control.checked)); node.append(control, element(doc, "span", label)); return node;
}
const emptyFragment = () => ({parent_number: null, source_range: null, target_range: null, bbox_px: [null, null, null, null],
  role: "", alignment: "", bold: false, italic: false, review_note: ""});
export function mountFormattingReview({root, prepareButton, getScope, getJob, request, storage, createNonce} = {}) {
  if (!root || !prepareButton) return null;
  const doc = root.ownerDocument || document, editors = new Map();
  let controller, pageNumber = 1, seen = "", seenOwner = "", seenGeneration = null, choice = "", localMessage = "", accept = false, reviewer = "", opened = false;
  let documentEditor = {decision: blankFormattingDocument(), dirty: false, cellChoice: "", gapChoice: ""};
  let submitButton = null, acceptBox = null, buildButton = null;
  function pageEditor(page) {
    if (!editors.has(page.page_number)) editors.set(page.page_number, {decision: page.decision ? clone(page.decision) : blankFormattingPage(),
      dirty: false, fragment: emptyFragment(), editNumber: null, fragmentTouched: false, fullSize: false, tableColumns: ""});
    return editors.get(page.page_number);
  }
  function update() {
    if (!controller) return;
    const s = controller.snapshot(), done = s.view?.pages?.length && s.view.pages.every(formattingPageComplete)
      && s.view.document_decision?.all_pages_reviewed === true && !s.dirty;
    if (submitButton) submitButton.disabled = s.busy || !s.verified || !done || !accept || !reviewer.trim() || Boolean(s.operationNonce || s.revisionId)
      || Boolean(s.pendingKind && s.pendingKind !== "submit") || s.view?.status === "submission_pending" && s.pendingKind !== "submit";
    if (acceptBox) acceptBox.querySelector("input").checked = accept;
    if (buildButton) buildButton.disabled = s.busy || !s.verified || !s.revisionId || s.dirty || Boolean(s.pendingKind)
      || s.restored && !s.associated;
  }
  function changed(page, editor, resetChecks = true) {
    editor.dirty = true; accept = false; controller.markDirty(page.page_number);
    if (resetChecks) { editor.decision.full_page_review_completed = false; editor.decision.source_target_mapping_reviewed = false; }
    documentEditor.decision.all_pages_reviewed = false; documentEditor.dirty = true; controller.markDirty();
    if (editor.checks) { editor.checks[0].checked = editor.decision.full_page_review_completed; editor.checks[1].checked = editor.decision.source_target_mapping_reviewed; }
    if (documentEditor.check) documentEditor.check.checked = false;
    update();
  }
  function documentChanged(resetCheck = true) {
    documentEditor.dirty = true; controller.markDirty(); accept = false;
    if (resetCheck) documentEditor.decision.all_pages_reviewed = false;
    if (documentEditor.check) documentEditor.check.checked = documentEditor.decision.all_pages_reviewed;
    update();
  }
  const safely = (fn) => async () => { try { await fn(); } catch (error) { localMessage = error.message; render(); } };
  function render(s = controller.snapshot()) {
    const ownerKey = JSON.stringify(s.owner);
    if (ownerKey !== seenOwner) { seenOwner = ownerKey; choice = ""; opened = false; }
    const identity = JSON.stringify([s.owner, s.reviewId]);
    if (identity !== seen) { seen = identity; seenGeneration = null; editors.clear(); pageNumber = 1; accept = false; reviewer = ""; localMessage = "";
      documentEditor = {decision: blankFormattingDocument(), dirty: false, cellChoice: "", gapChoice: ""}; }
    if (Number.isInteger(s.view?.generation) && s.view.generation !== seenGeneration) {
      if (s.view.document_decision === null) {
        documentEditor.decision.all_pages_reviewed = false; accept = false;
      }
      seenGeneration = s.view.generation;
    }
    for (const page of s.view?.pages || []) {
      const e = editors.get(page.page_number);
      if (e && page.decision && (!e.dirty || formattingValuesEqual(e.decision, page.decision))) { e.decision = clone(page.decision); e.dirty = false; }
    }
    if (s.view?.document_decision && (!documentEditor.dirty || formattingValuesEqual(documentEditor.decision, s.view.document_decision))) {
      documentEditor = {...documentEditor, decision: clone(s.view.document_decision), dirty: false,
        cellChoice: s.view.document_decision.allow_pipe_cell_boundaries ? "yes" : "no", gapChoice: s.view.document_decision.preserve_source_gaps ? "yes" : "no"};
    }
    prepareButton.disabled = !s.owner || getJob()?.status !== "completed" || !getJob()?.actions?.formatting_review || s.busy;
    root.replaceChildren(); root.hidden = !s.owner || !opened;
    if (root.hidden) return;
    root.append(element(doc, "h2", "Review DOCX formatting"));
    root.append(element(doc, "p", s.busy ? "Working on this review…" : s.errorCode ? formattingReviewMessage(s.errorCode) : localMessage
      || "Compare the source image with the complete source and translation. Choose every mapping and layout explicitly.", "formatting-review-status"));
    root.append(element(doc, "p", "These decisions do not verify the geometry or the rendered DOCX. Open and visually review the exported file before using it.", "formatting-review-note"));
    if (!s.reviewId) {
      root.append(field(doc, "Page layout for this review", select(doc, [["", "Choose explicitly…"], ["saved", "Use this run’s saved page breaks"],
        ["matched", "Create a page-matched derivative"]], choice, (value) => { choice = value; }, s.busy)));
      root.append(element(doc, "p", "A page-matched derivative starts each source page on a new output page. Your saved settings and ordinary output choice stay unchanged."));
      root.append(button(doc, "Prepare formatting review", () => controller.prepare(choice === "" ? null : choice === "matched"), s.busy || getJob()?.status !== "completed"));
    } else {
      root.append(button(doc, "Read current formatting review", () => controller.read(), s.busy));
      root.append(element(doc, "p", "This review handle needs the current server session. A server restart cannot restore it here."));
      if (s.restored && !s.verified) root.append(element(doc, "p", "Read the saved review before editing or recovering an operation."));
      if (s.view?.page_matched_derivative) root.append(element(doc, "p", "Selected: page-matched derivative. Original saved page-break settings are preserved."));
    }
    for (const code of s.view?.notice_codes || []) root.append(element(doc, "p", formattingReviewMessage(code)));
    if (s.conflict) root.append(button(doc, "Discard the conflicting local decision and load the saved one", () => {
      const discarded = controller.discardConflict();
      if (discarded?.kind === "page") editors.delete(discarded.pageNumber);
      if (discarded?.kind === "document") documentEditor.dirty = false;
      accept = false; render();
    }, s.busy));
    const pages = s.view?.pages || [];
    if (pages.length && s.verified && !s.operationNonce) {
      if (!pages.some((p) => p.page_number === pageNumber)) pageNumber = pages[0].page_number;
      root.append(field(doc, "Source page", select(doc, pages.map((p) => [p.page_number, `Page ${p.page_number}${formattingPageComplete(p) ? " — reviewed" : ""}`]),
        pageNumber, (value) => { pageNumber = Number(value); render(); }, s.busy)));
      const page = pages.find((p) => p.page_number === pageNumber);
      renderPage(page, pageEditor(page), s); renderDocument(pages, s);
    }
    const footer = element(doc, "div", "", "formatting-review-submit");
    if (!s.revisionId && pages.length) {
      footer.append(field(doc, "Formatting acceptance reviewer", input(doc, reviewer, (value) => { reviewer = value; accept = false; update(); }, {disabled: s.busy})));
      acceptBox = checkbox(doc, "I accept these complete formatting decisions for this exact translation", accept, (value) => { accept = value; update(); }, s.busy);
      footer.append(acceptBox);
      submitButton = button(doc, s.pendingKind === "submit" ? "Retry this exact formatting submission" : "Accept formatting revision", () => controller.submit(reviewer, accept));
      footer.append(submitButton);
    } else { submitButton = null; acceptBox = null; }
    if (s.view?.status === "submission_pending" && s.pendingKind !== "submit") footer.append(element(doc, "p", "A submission was started earlier. Read can recover its completed revision. The original submission request is unavailable in this page session."));
    if (s.revisionId) {
      footer.append(element(doc, "p", "The formatting revision is selected explicitly for this review."));
      footer.append(button(doc, "Check this exact revision", () => controller.inspect(), s.busy || !s.verified));
      buildButton = button(doc, s.operationNonce ? "Recover this exact DOCX build" : "Build DOCX from this revision", () => controller.rebuild()); footer.append(buildButton);
      if (s.restored && !s.associated) footer.append(element(doc, "p", "Recovery after reload requires an existing server-recorded build for this exact revision. No new build will start from stored identifiers alone."));
      const href = controller.artifactUrl();
      if (href) { const link = element(doc, "a", "Download this reviewed DOCX"); link.href = href; link.className = "button-link"; footer.append(link); }
    } else buildButton = null;
    root.append(footer); update();
  }
  function renderPage(page, editor, s) {
    const locked = s.busy || Boolean(s.revisionId || s.pendingKind) || s.view.status === "submission_pending";
    const grid = element(doc, "div", "", "formatting-review-grid"), imageColumn = element(doc, "div"), controls = element(doc, "div");
    const viewport = element(doc, "div", "", "formatting-review-image-viewport"), image = element(doc, "img"), frame = element(doc, "div", "", "formatting-review-image-frame");
    image.src = controller.imageUrl(page.page_number); image.alt = `Original source page ${page.page_number}`;
    frame.style.width = editor.fullSize ? `${page.image_size_px[0]}px` : "100%"; image.draggable = false;
    const point = (event) => { const box = image.getBoundingClientRect(); return [
      Math.max(0, Math.min(page.image_size_px[0], (event.clientX - box.left) * page.image_size_px[0] / box.width)),
      Math.max(0, Math.min(page.image_size_px[1], (event.clientY - box.top) * page.image_size_px[1] / box.height))]; };
    let anchor = null;
    image.addEventListener("pointerdown", (event) => { if (!locked && event.button === 0) { anchor = point(event); event.preventDefault(); } });
    image.addEventListener("pointerup", (event) => { if (!anchor || locked) return; const end = point(event);
      editor.fragment.bbox_px = [Math.min(anchor[0], end[0]), Math.min(anchor[1], end[1]), Math.max(anchor[0], end[0]), Math.max(anchor[1], end[1])];
      anchor = null; editor.fragmentTouched = true; changed(page, editor); render(); });
    frame.append(image);
    for (const [index, box] of [...editor.decision.fragments.map((fragment) => fragment.bbox_px), editor.fragment.bbox_px].entries()) {
      if (box.some((n) => !Number.isFinite(n))) continue;
      const overlay = element(doc, "div", index < editor.decision.fragments.length ? String(index + 1) : "Selection", "formatting-review-region");
      overlay.style.left = `${100 * box[0] / page.image_size_px[0]}%`; overlay.style.top = `${100 * box[1] / page.image_size_px[1]}%`;
      overlay.style.width = `${100 * (box[2] - box[0]) / page.image_size_px[0]}%`; overlay.style.height = `${100 * (box[3] - box[1]) / page.image_size_px[1]}%`;
      frame.append(overlay);
    }
    viewport.append(frame); imageColumn.append(button(doc, editor.fullSize ? "Fit page image" : "Show full-resolution page image", () => { editor.fullSize = !editor.fullSize; render(); }), viewport);
    imageColumn.append(element(doc, "p", `Source provenance: ${String(page.source_provenance)}. Source uncertainty: ${page.source_uncertain ? "present" : "not reported"}.`));
    const f = editor.fragment, parent = page.parents.find((p) => p.parent_number === f.parent_number);
    controls.append(field(doc, "Source / target block", select(doc, [["", "Choose a block…"], ...page.parents.map((p) => [p.parent_number, `Block ${p.parent_number}`])],
      f.parent_number ?? "", (value) => { editor.fragment = {...emptyFragment(), parent_number: value ? Number(value) : null}; editor.fragmentTouched = true; changed(page, editor); render(); }, locked)));
    if (parent) {
      for (const [side, label] of [["source", "Source text"], ["target", "Translation text"]]) {
        const text = parent[`${side}_text`], area = input(doc, text, () => {}, {readOnly: true, textarea: true});
        controls.append(field(doc, label, area));
        controls.append(button(doc, `Use selected ${side === "source" ? "source" : "translation"} text`, safely(() => {
          f[`${side}_range`] = selectedCodepointRange(text, area.selectionStart, area.selectionEnd);
          editor.fragmentTouched = true; changed(page, editor); render();
        }), locked));
        if (f[`${side}_range`]) controls.append(element(doc, "pre", codepointSlice(text, f[`${side}_range`]), "formatting-review-selection"));
      }
    }
    controls.append(element(doc, "p", "Select source and translation independently. Include complete characters and legal references. Every meaningful part of each block must be mapped; the server checks coverage."));
    for (const [index, label] of ["Region left (px)", "Region top (px)", "Region right (px)", "Region bottom (px)"].entries()) controls.append(field(doc, label,
      input(doc, f.bbox_px[index], (value) => { f.bbox_px[index] = value === "" ? null : Number(value); editor.fragmentTouched = true; changed(page, editor); }, {number: true, disabled: locked})));
    controls.append(field(doc, "Fragment role", select(doc, [["", "Choose a role…"], ...roles.map((r) => [r, r === "folio" ? "Page-local number" : r])], f.role,
      (value) => { f.role = value; editor.fragmentTouched = true; changed(page, editor); }, locked)));
    controls.append(field(doc, "Text alignment", select(doc, [["", "Choose alignment…"], ...alignments.map((a) => [a, a])], f.alignment,
      (value) => { f.alignment = value; editor.fragmentTouched = true; changed(page, editor); }, locked)));
    for (const key of ["bold", "italic"]) controls.append(checkbox(doc, key === "bold" ? "Bold text" : "Italic text", f[key], (value) => { f[key] = value; editor.fragmentTouched = true; changed(page, editor); }, locked));
    controls.append(field(doc, "Fragment review explanation", input(doc, f.review_note, (value) => { f.review_note = value; editor.fragmentTouched = true; changed(page, editor); }, {disabled: locked})));
    controls.append(button(doc, editor.editNumber ? "Save this fragment edit" : "Add this explicit fragment", safely(() => {
      if (!parent || !f.source_range || !f.target_range || !roles.includes(f.role) || !alignments.includes(f.alignment) || !f.review_note.trim()
          || f.bbox_px.some((n) => !Number.isFinite(n)) || f.bbox_px[0] < 0 || f.bbox_px[1] < 0
          || f.bbox_px[2] > page.image_size_px[0] || f.bbox_px[3] > page.image_size_px[1]
          || f.bbox_px[0] >= f.bbox_px[2] || f.bbox_px[1] >= f.bbox_px[3]) throw new Error("Select both text spans, a valid source-image region, role, alignment and review explanation.");
      if (editor.editNumber) editor.decision.fragments[editor.editNumber - 1] = clone(f); else editor.decision.fragments.push(clone(f));
      editor.fragment = emptyFragment(); editor.editNumber = null; editor.fragmentTouched = false; changed(page, editor); localMessage = ""; render();
    }), locked));
    if (editor.fragmentTouched || editor.editNumber) controls.append(button(doc, "Cancel unfinished fragment", () => { editor.fragment = emptyFragment(); editor.editNumber = null; editor.fragmentTouched = false; render(); }, locked));
    renderFragments(controls, page, editor, locked); renderOwnership(controls, page, editor, locked);
    controls.append(field(doc, "Page formatting reviewer", input(doc, editor.decision.reviewer, (value) => { editor.decision.reviewer = value; changed(page, editor); }, {disabled: locked})));
    controls.append(field(doc, "Page review explanation", input(doc, editor.decision.review_note, (value) => { editor.decision.review_note = value; changed(page, editor); }, {disabled: locked})));
    const pageCheck = checkbox(doc, "I reviewed the complete page image and its formatting", editor.decision.full_page_review_completed,
      (value) => { editor.decision.full_page_review_completed = value; changed(page, editor, false); }, locked);
    const mapCheck = checkbox(doc, "I checked every source-to-translation text selection", editor.decision.source_target_mapping_reviewed,
      (value) => { editor.decision.source_target_mapping_reviewed = value; changed(page, editor, false); }, locked);
    editor.checks = [pageCheck.querySelector("input"), mapCheck.querySelector("input")]; controls.append(pageCheck, mapCheck);
    controls.append(button(doc, s.pendingKind === "page" ? "Retry this exact page formatting save" : "Save page formatting", safely(async () => {
      if (editor.fragmentTouched || editor.editNumber) throw new Error("Finish or cancel the unfinished fragment before saving the page.");
      const problem = formattingPageProblem(page, editor.decision); if (problem) throw new Error(problem);
      await controller.savePage(page.page_number, editor.decision);
    }), s.busy || locked && s.pendingKind !== "page"));
    grid.append(imageColumn, controls); root.append(grid);
  }
  function renderFragments(container, page, editor, locked) {
    container.append(element(doc, "h3", "Reviewed fragments in source order"));
    editor.decision.fragments.forEach((fragment, index) => {
      const box = element(doc, "div", "", "formatting-review-fragment"), parent = page.parents.find((p) => p.parent_number === fragment.parent_number);
      box.append(element(doc, "strong", `Fragment ${index + 1} · ${fragment.role}`));
      box.append(element(doc, "pre", parent ? codepointSlice(parent.source_text, fragment.source_range) : ""));
      box.append(element(doc, "pre", parent ? codepointSlice(parent.target_text, fragment.target_range) : ""));
      box.append(button(doc, "Edit fragment", () => { editor.fragment = clone(fragment); editor.editNumber = index + 1; editor.fragmentTouched = true; changed(page, editor); render(); }, locked));
      box.append(button(doc, "Remove fragment", () => { editor.decision = removeFormattingFragment(editor.decision, index + 1); editor.fragment = emptyFragment(); editor.editNumber = null; editor.fragmentTouched = false; changed(page, editor); render(); }, locked));
      for (const [delta, label] of [[-1, "Move fragment earlier"], [1, "Move fragment later"]]) box.append(button(doc, label,
        () => { editor.decision = moveFormattingFragment(editor.decision, index + 1, delta); changed(page, editor); render(); }, locked || editor.fragmentTouched || Boolean(editor.editNumber)
          || index + delta < 0 || index + delta >= editor.decision.fragments.length));
      container.append(box);
    });
  }
  function ownerList(container, label, values, page, editor, locked) {
    const group = element(doc, "div", "", "formatting-review-owner"); group.append(element(doc, "strong", label));
    values.forEach((number, index) => {
      const row = element(doc, "div"); row.append(element(doc, "span", `Fragment ${number}`));
      for (const [delta, name] of [[-1, "Earlier"], [1, "Later"]]) row.append(button(doc, name, () => {
        [values[index], values[index + delta]] = [values[index + delta], values[index]]; changed(page, editor); render();
      }, locked || index + delta < 0 || index + delta >= values.length));
      row.append(button(doc, "Remove ownership", () => { values.splice(index, 1); changed(page, editor); render(); }, locked)); group.append(row);
    });
    let selected = "";
    group.append(field(doc, `Choose fragment for ${label}`, select(doc, [["", "Choose a fragment…"],
      ...editor.decision.fragments.map((f, i) => [i + 1, `Fragment ${i + 1} · ${f.role}`])], "", (value) => { selected = value; }, locked)));
    group.append(button(doc, "Assign selected fragment here", safely(() => {
      if (!selected) throw new Error("Choose the fragment to assign.");
      const n = Number(selected), d = editor.decision;
      const all = [...d.header, ...d.footer, ...d.body.flatMap((b) => Object.hasOwn(b, "fragment_number") ? [b.fragment_number] : b.rows.flat(2))];
      if (all.includes(n)) throw new Error("This fragment already has an owner. Remove its previous ownership explicitly first.");
      values.push(n); changed(page, editor); render();
    }), locked)); container.append(group);
  }
  function renderOwnership(container, page, editor, locked) {
    const d = editor.decision;
    container.append(element(doc, "h3", "Paragraph and table ownership"));
    ownerList(container, "Header", d.header, page, editor, locked);
    d.body.forEach((block, index) => {
      const region = element(doc, "div", "", "formatting-review-body-block");
      region.append(element(doc, "h4", `Body item ${index + 1} · ${Object.hasOwn(block, "fragment_number") ? "paragraph" : "table"}`));
      if (Object.hasOwn(block, "fragment_number")) region.append(element(doc, "p", `Fragment ${block.fragment_number}`));
      else {
        block.column_widths.forEach((width, col) => region.append(field(doc, `Column ${col + 1} width (%)`, input(doc, width,
          (value) => { block.column_widths[col] = value === "" ? null : Number(value); changed(page, editor); }, {number: true, disabled: locked}))));
        region.append(checkbox(doc, "I want to preserve measured spaces between these columns", Boolean(block.column_gaps_px), (checked) => {
          if (checked) block.column_gaps_px = Array(block.column_widths.length - 1).fill(null); else delete block.column_gaps_px;
          changed(page, editor); render();
        }, locked));
        block.column_gaps_px?.forEach((gap, col) => region.append(field(doc, `Reviewed space after column ${col + 1} (px)`, input(doc, gap,
          (value) => { block.column_gaps_px[col] = value === "" ? null : Number(value); changed(page, editor); }, {number: true, disabled: locked}))));
        block.rows.forEach((row, rowIndex) => {
          const cells = element(doc, "div", "", "formatting-review-table-row");
          row.forEach((cell, col) => ownerList(cells, `Row ${rowIndex + 1}, column ${col + 1}`, cell, page, editor, locked));
          for (const [delta, name] of [[-1, "Move row earlier"], [1, "Move row later"]]) cells.append(button(doc, name, () => {
            [block.rows[rowIndex], block.rows[rowIndex + delta]] = [block.rows[rowIndex + delta], block.rows[rowIndex]]; changed(page, editor); render();
          }, locked || rowIndex + delta < 0 || rowIndex + delta >= block.rows.length));
          cells.append(button(doc, "Remove table row and its ownership", () => { block.rows.splice(rowIndex, 1); changed(page, editor); render(); }, locked)); region.append(cells);
        });
        region.append(button(doc, "Add empty table row", () => { block.rows.push(block.column_widths.map(() => [])); changed(page, editor); render(); }, locked || block.rows.length >= 100));
      }
      for (const [delta, name] of [[-1, "Move body item earlier"], [1, "Move body item later"]]) region.append(button(doc, name, () => {
        [d.body[index], d.body[index + delta]] = [d.body[index + delta], d.body[index]]; changed(page, editor); render();
      }, locked || index + delta < 0 || index + delta >= d.body.length));
      region.append(button(doc, "Remove body item and its ownership", () => { d.body.splice(index, 1); changed(page, editor); render(); }, locked)); container.append(region);
    });
    let paragraph = "";
    container.append(field(doc, "New body paragraph", select(doc, [["", "Choose an unowned body/signature fragment…"],
      ...d.fragments.flatMap((f, i) => ["body", "signature"].includes(f.role) ? [[i + 1, `Fragment ${i + 1}`]] : [])], "", (value) => { paragraph = value; }, locked)));
    container.append(button(doc, "Add selected body paragraph", safely(() => {
      const all = [...d.header, ...d.footer, ...d.body.flatMap((b) => Object.hasOwn(b, "fragment_number") ? [b.fragment_number] : b.rows.flat(2))];
      if (!paragraph || all.includes(Number(paragraph))) throw new Error("Choose a fragment with no current owner.");
      d.body.push({fragment_number: Number(paragraph)}); changed(page, editor); render();
    }), locked));
    container.append(field(doc, "New table columns", select(doc, [["", "Choose a column count…"], ...[1, 2, 3, 4].map((n) => [n, `${n} column${n === 1 ? "" : "s"}`])],
      editor.tableColumns, (value) => { editor.tableColumns = value; }, locked)));
    container.append(button(doc, "Add empty table", safely(() => {
      if (!editor.tableColumns) throw new Error("Choose how many columns this table has.");
      const count = Number(editor.tableColumns); d.body.push({column_widths: Array(count).fill(null), rows: [Array.from({length: count}, () => [])]});
      editor.tableColumns = ""; changed(page, editor); render();
    }), locked));
    ownerList(container, "Footer, including page-local number", d.footer, page, editor, locked);
    container.append(field(doc, "Page-local number", select(doc, [["", "No page-local number selected"],
      ...d.fragments.flatMap((f, i) => f.role === "folio" ? [[i + 1, `Folio fragment ${i + 1}`]] : [])], d.folio_fragment_number ?? "",
      (value) => { d.folio_fragment_number = value ? Number(value) : null; changed(page, editor); }, locked)));
  }
  function renderDocument(pages, s) {
    const d = documentEditor.decision, locked = s.busy || Boolean(s.revisionId || s.pendingKind) || s.view.status === "submission_pending";
    const section = element(doc, "section", "", "formatting-review-document"); section.append(element(doc, "h3", "Review the complete document"));
    section.append(element(doc, "p", "Group consecutive source pages that belong to the same document. Every source page must belong to exactly one group, in order."));
    d.groups.forEach((group, index) => {
      const row = element(doc, "div"); row.append(field(doc, `Group ${index + 1} first page`, input(doc, group.start_page,
        (value) => { group.start_page = value === "" ? null : Number(value); documentChanged(); }, {number: true, disabled: locked})));
      row.append(field(doc, `Group ${index + 1} last page`, input(doc, group.end_page,
        (value) => { group.end_page = value === "" ? null : Number(value); documentChanged(); }, {number: true, disabled: locked})));
      row.append(button(doc, "Remove document group", () => { d.groups.splice(index, 1); documentChanged(); render(); }, locked)); section.append(row);
    });
    section.append(button(doc, "Add document group", () => { d.groups.push({start_page: null, end_page: null}); documentChanged(); render(); }, locked || d.groups.length >= pages.length));
    section.append(field(doc, "Text separators inside reviewed table cells", select(doc, [["", "Choose after reviewing…"],
      ["no", "Keep strict original text boundaries"], ["yes", "Allow reviewed table-cell separators"]], documentEditor.cellChoice,
      (value) => { documentEditor.cellChoice = value; d.allow_pipe_cell_boundaries = value === "yes"; documentChanged(); }, locked)));
    section.append(field(doc, "Vertical spacing between source regions", select(doc, [["", "Choose after reviewing…"],
      ["no", "Use capped source spacing"], ["yes", "Preserve full measured vertical source gaps"]], documentEditor.gapChoice,
      (value) => { documentEditor.gapChoice = value; d.preserve_source_gaps = value === "yes"; documentChanged(); }, locked)));
    section.append(element(doc, "p", "Both vertical-spacing choices require complete source and translation text coverage. They change spacing, not which text is retained."));
    section.append(field(doc, "Document formatting reviewer", input(doc, d.reviewer, (value) => { d.reviewer = value; documentChanged(); }, {disabled: locked})));
    section.append(field(doc, "Document review explanation", input(doc, d.review_note, (value) => { d.review_note = value; documentChanged(); }, {disabled: locked})));
    const check = checkbox(doc, "I reviewed every page, its text mappings and the document groups", d.all_pages_reviewed,
      (value) => { d.all_pages_reviewed = value; documentChanged(false); }, locked);
    documentEditor.check = check.querySelector("input"); section.append(check);
    section.append(button(doc, s.pendingKind === "document" ? "Retry this exact document review save" : "Save document review", safely(async () => {
      let expected = 1;
      for (const group of d.groups) {
        if (!Number.isInteger(group.start_page) || !Number.isInteger(group.end_page) || group.start_page !== expected || group.end_page < expected || group.end_page > pages.length) {
          throw new Error("Document groups must cover every page once, in consecutive order.");
        }
        expected = group.end_page + 1;
      }
      if (expected !== pages.length + 1 || !d.reviewer.trim() || !d.review_note.trim() || !documentEditor.cellChoice || !documentEditor.gapChoice) {
        throw new Error("Complete the page groups, text-spacing choices, reviewer and explanation.");
      }
      await controller.saveDocument(d);
    }), s.busy || locked && s.pendingKind !== "document")); root.append(section);
  }
  let sessionStorage = storage;
  if (sessionStorage === undefined) { try { sessionStorage = globalThis.sessionStorage; } catch { sessionStorage = null; } }
  controller = createFormattingReviewController({getScope, getJob, request, storage: sessionStorage, createNonce, onChange: render});
  prepareButton.addEventListener("click", () => { opened = true; render(); root.scrollIntoView?.({block: "start"}); });
  render(); return {controller, sync: () => { controller.sync(); prepareButton.disabled = !controller.snapshot().owner
    || getJob()?.status !== "completed" || !getJob()?.actions?.formatting_review || controller.snapshot().busy; update(); }};
}
