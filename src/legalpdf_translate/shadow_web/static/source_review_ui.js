import { createSourceReviewController, newSourceReviewId, pageReviewComplete, sourceDecisionsEqual, sourceReviewMessage } from "./source_review.js";

const clone = (value) => JSON.parse(JSON.stringify(value));
const KINDS = [["retain", "Retain the source text"], ["replace", "Correct the source text"],
  ["omit_nontext", "Omit a non-text OCR artifact"], ["transcribe", "Transcribe missing text"]];
const CATEGORIES = ["identifier", "citation", "omission", "invention", "reading_order", "boundary", "other"];

export function blankSourcePageDecision() {
  return { actions: [], reading_order: [], full_page_review_completed: false,
    reading_order_reviewed: false, boundary_decision: "unresolved", boundary_rationale: "", findings: [], reviewer: "" };
}

export function imagePoint(clientX, clientY, rect, size) {
  if (!(rect.width > 0 && rect.height > 0)) return null;
  return [Math.max(0, Math.min(size[0], (clientX - rect.left) * size[0] / rect.width)),
    Math.max(0, Math.min(size[1], (clientY - rect.top) * size[1] / rect.height))];
}

export function selectedWordRegion(page, selectedIds) {
  const selected = new Set(selectedIds);
  let region = null;
  for (const word of page.word_evidence?.words || []) {
    if (!selected.has(word.block_id)) continue;
    const box = word.bbox_px;
    region = region ? [Math.min(region[0], box[0]), Math.min(region[1], box[1]),
      Math.max(region[2], box[2]), Math.max(region[3], box[3])] : [...box];
  }
  return region;
}

function validRegion(region, size) {
  return Array.isArray(region) && region.length === 4 && region.every(Number.isFinite)
    && 0 <= region[0] && region[0] < region[2] && region[2] <= size[0]
    && 0 <= region[1] && region[1] < region[3] && region[3] <= size[1];
}

/** This builds typed operator input, not a hash, acceptance or source envelope. */
export function sourceActionFromInput(page, input) {
  const selected = new Set(input.baseline_block_ids || []);
  const blocks = page.baseline_blocks.filter((block) => selected.has(block.id));
  if (!KINDS.some(([kind]) => kind === input.kind) || blocks.length !== selected.size
      || (input.kind === "transcribe" ? selected.size !== 0 : selected.size === 0)
      || !validRegion(input.region_px, page.image_size_px) || !String(input.rationale || "").trim()) {
    throw new Error("Select an action, its source blocks and region, and explain your decision.");
  }
  const before = blocks.map((block) => block.text).join("\n");
  const after = input.kind === "retain" ? before : input.kind === "omit_nontext" ? "" : input.after_text;
  if (typeof after !== "string" || (input.kind !== "omit_nontext" && !after.trim())
      || (input.kind === "replace" && after === before)) throw new Error("Enter the exact corrected or missing source text.");
  const words = page.word_evidence?.words || [];
  if (words.some((word) => selected.has(word.block_id) &&
      (word.bbox_px[0] < input.region_px[0] || word.bbox_px[1] < input.region_px[1]
        || word.bbox_px[2] > input.region_px[2] || word.bbox_px[3] > input.region_px[3]))) {
    throw new Error("The selected region must include all word evidence for the selected blocks.");
  }
  return { id: input.id || newSourceReviewId(), kind: input.kind,
    baseline_block_ids: blocks.map((block) => block.id), after_text: after,
    region_px: [...input.region_px], rationale: input.rationale };
}

export function sourceDecisionProblem(page, decision) {
  if (!decision.actions.length) return "Make an explicit decision for every baseline block.";
  const covered = decision.actions.flatMap((a) => a.baseline_block_ids);
  if (new Set(covered).size !== covered.length || covered.length !== page.baseline_blocks.length
      || page.baseline_blocks.some((b) => !covered.includes(b.id))) return "Each baseline block must belong to exactly one action.";
  for (let i = 0; i < decision.actions.length; i += 1) {
    const a = decision.actions[i].region_px;
    if (!validRegion(a, page.image_size_px)) return "Every action needs a valid image region.";
    for (const other of decision.actions.slice(i + 1)) {
      const b = other.region_px;
      if (Math.max(a[0], b[0]) < Math.min(a[2], b[2]) && Math.max(a[1], b[1]) < Math.min(a[3], b[3])) {
        return "Action regions overlap. Group related blocks in one action or adjust the regions.";
      }
    }
  }
  const expected = decision.actions.filter((a) => a.kind !== "omit_nontext").map((a) => a.id);
  if (decision.reading_order.length !== expected.length || new Set(decision.reading_order).size !== expected.length
      || expected.some((id) => !decision.reading_order.includes(id))) return "Order every retained, corrected and transcribed action.";
  if (!decision.reviewer.trim() || !decision.boundary_rationale.trim()) return "Enter your reviewer name and explain the page boundary.";
  if (page.page_number === 1 && decision.boundary_decision === "continuation") return "The first page cannot continue a preceding page.";
  if (decision.findings.some((f) => !f.rationale.trim() || (f.status === "resolved" && !f.action_ids.length))) {
    return "Explain each finding and link resolved findings to the actions that address them.";
  }
  return "";
}

function element(doc, tag, text = "", className = "") {
  const node = doc.createElement(tag);
  if (text) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function button(doc, text, action, disabled = false) {
  const node = element(doc, "button", text);
  node.type = "button";
  node.disabled = disabled;
  node.addEventListener("click", action);
  return node;
}
function field(doc, labelText, control) {
  const wrapper = element(doc, "label", "", "source-review-field");
  control.setAttribute("aria-label", labelText);
  wrapper.append(element(doc, "span", labelText), control);
  return wrapper;
}
function input(doc, value, change, { textarea = false, disabled = false } = {}) {
  const node = element(doc, textarea ? "textarea" : "input");
  if (!textarea) node.type = "text";
  node.value = value;
  node.dir = "auto";
  node.disabled = disabled;
  node.maxLength = textarea ? 100000 : 1000;
  node.addEventListener("input", () => change(node.value));
  return node;
}
function select(doc, choices, value, change, disabled = false) {
  const node = element(doc, "select");
  choices.forEach(([key, label]) => {
    const option = element(doc, "option", label);
    option.value = key;
    node.append(option);
  });
  node.value = value;
  node.disabled = disabled;
  node.addEventListener("change", () => change(node.value));
  return node;
}
function checkbox(doc, labelText, checked, change, disabled = false) {
  const control = element(doc, "input");
  control.type = "checkbox";
  control.checked = checked;
  control.disabled = disabled;
  control.addEventListener("change", () => change(control.checked));
  const wrapper = element(doc, "label", "", "source-review-check");
  wrapper.append(control, element(doc, "span", labelText));
  return wrapper;
}

export function mountSourceReview({ root, prepareButton, getScope, getSetup, manualReady, beforePrepare,
  onJob, request, storage, createNonce } = {}) {
  if (!root || !prepareButton) return null;
  const doc = root.ownerDocument || document;
  let controller;
  let selectedPage = 1;
  let seenReview = "";
  let reviewer = "";
  let acceptSource = false;
  let localMessage = "";
  const editors = new Map();

  function editorFor(page) {
    let editor = editors.get(page.page_number);
    if (!editor) {
      const saved = page.decision ? clone(page.decision) : blankSourcePageDecision();
      delete saved.reviewer_kind;
      editor = { decision: saved, dirty: false, selected: new Set(), kind: "", text: "", rationale: "",
        region: null, regionInput: ["", "", "", ""], editId: "", showWords: false, fullSize: false,
        findingCategory: "", findingStatus: "", findingActions: new Set(), findingRationale: "" };
      editors.set(page.page_number, editor);
    }
    return editor;
  }
  function changed(page, editor, resetChecks = true) {
    editor.dirty = true;
    if (resetChecks) {
      editor.decision.full_page_review_completed = false;
      editor.decision.reading_order_reviewed = false;
    }
    if (editor.completionInputs) {
      editor.completionInputs[0].checked = editor.decision.full_page_review_completed;
      editor.completionInputs[1].checked = editor.decision.reading_order_reviewed;
    }
    acceptSource = false;
    controller.markDirty(page.page_number);
    updateSubmitControls();
  }
  let submitButton, acceptBox, startButton;
  function updateSubmitControls() {
    if (!controller) return;
    const snapshot = controller.snapshot();
    const pages = snapshot.view?.pages || [];
    const complete = pages.length > 0 && pages.every(pageReviewComplete) && !snapshot.dirty;
    if (submitButton) submitButton.disabled = snapshot.busy || !acceptSource || !reviewer.trim()
      || snapshot.operationNonce !== "" || (!snapshot.view?.submission
        && (!complete || snapshot.invalidated || snapshot.recoveryOnly));
    if (acceptBox) acceptBox.querySelector("input").checked = acceptSource;
    if (startButton) startButton.disabled = snapshot.busy || !snapshot.revisionId || snapshot.dirty
      || !snapshot.reviewVerified || Boolean(snapshot.pendingKind)
      || ((snapshot.recoveryOnly || snapshot.invalidated) && !snapshot.operationAssociated);
  }
  function render(next = controller.snapshot()) {
    prepareButton.disabled = next.busy || Boolean(next.reviewId) || !manualReady();
    if (next.reviewId !== seenReview) {
      seenReview = next.reviewId;
      editors.clear();
      selectedPage = 1;
      acceptSource = false;
      reviewer = "";
      localMessage = "";
    }
    for (const page of next.view?.pages || []) {
      const prior = editors.get(page.page_number);
      if (prior && page.decision) {
        const saved = clone(page.decision);
        delete saved.reviewer_kind;
        if (!prior.dirty || sourceDecisionsEqual(prior.decision, saved)) {
          prior.decision = saved;
          prior.dirty = false;
        }
      }
    }
    root.replaceChildren();
    root.hidden = !next.reviewId && !next.view && !next.errorCode && !next.busy;
    if (root.hidden) return;
    root.append(element(doc, "h2", "Review the source before translation"));
    const status = element(doc, "p", "", "source-review-status");
    status.setAttribute("role", "status");
    status.textContent = next.busy ? "Working on this review…" : next.errorCode
      ? sourceReviewMessage(next.errorCode) : next.operationNonce
        ? "Source review is accepted. Follow the translation job, or recover this exact start if its response was lost."
        : localMessage || "Compare the complete page image with the text and make each decision explicitly.";
    root.append(status);
    if (next.recoveryOnly) root.append(element(doc, "p", sourceReviewMessage("source_review_recovery_only"), "source-review-warning"));
    if (next.invalidated) root.append(element(doc, "p", sourceReviewMessage("source_review_setup_changed"), "source-review-warning"));
    if (next.view?.status === "declined") {
      for (const code of next.view.notice_codes || []) root.append(element(doc, "p", sourceReviewMessage(code)));
    }
    const toolbar = element(doc, "div", "", "source-review-toolbar");
    if (next.reviewId) toolbar.append(button(doc, "Read current review / recover response", () => controller.read(), next.busy));
    if (next.pendingPageConflict) toolbar.append(button(doc, "Discard local page changes and use the current saved page", () => {
      const pageNumber = controller.discardConflictedPage();
      if (pageNumber !== null) { editors.delete(pageNumber); acceptSource = false; localMessage = "Current saved page loaded. Review its decisions before accepting the source."; render(); }
    }, next.busy));
    if (!next.operationNonce) toolbar.append(button(doc, "Close this local review", () => {
      if (controller.discardLocalReview()) { editors.clear(); localMessage = ""; }
    }, next.busy || Boolean(next.pendingKind)));
    root.append(toolbar);
    root.append(element(doc, "p", "Review handles are available only while this server session retains them. Browser reload offers recovery only; a server restart cannot restore the review here.", "source-review-note"));
    const pages = next.view?.pages || [];
    if (pages.length && !next.operationNonce) {
      if (!pages.some((p) => p.page_number === selectedPage)) selectedPage = pages[0].page_number;
      toolbar.append(select(doc, pages.map((p) => [String(p.page_number), `Page ${p.page_number}${pageReviewComplete(p) ? " — saved and reviewed" : " — needs review"}`]),
        String(selectedPage), (value) => { selectedPage = Number(value); render(); }, next.busy));
      const page = pages.find((p) => p.page_number === selectedPage);
      renderPage(page, editorFor(page), next);
    }
    const footer = element(doc, "div", "", "source-review-submit");
    if (next.view?.submission) {
      reviewer = next.view.submission.reviewer;
      footer.append(element(doc, "p", next.view.submission.status === "pending"
        ? "This exact source submission is pending. Reconfirm it to complete only the pinned publication."
        : "This source submission is complete. An explicit repeat can recover its exact browser association."));
    }
    if (pages.length && !next.operationNonce) {
      footer.append(field(doc, "Whole-source reviewer", input(doc, reviewer, (value) => {
        reviewer = value; acceptSource = false; updateSubmitControls();
      }, { disabled: next.busy || Boolean(next.view?.submission) })));
      acceptBox = checkbox(doc, "I accept the complete reviewed source for this translation", acceptSource,
        (value) => { acceptSource = value; updateSubmitControls(); }, next.busy);
      footer.append(acceptBox);
      submitButton = button(doc, next.pendingKind === "submit" || next.view?.submission ? "Retry this exact source submission" : "Accept reviewed source",
        async () => { await controller.submit(reviewer, acceptSource); acceptSource = false; updateSubmitControls(); });
      footer.append(submitButton);
    } else { submitButton = null; acceptBox = null; }
    if (next.revisionId) {
      footer.append(element(doc, "p", next.reviewVerified
        ? "The accepted source revision is selected explicitly. Source review does not confirm the translation or its formatting."
        : "Saved review identifiers need a current server read before this exact operation can be recovered."));
      startButton = button(doc, next.operationNonce ? "Recover this exact translation start" : "Translate reviewed source",
        () => controller.translate());
      footer.append(startButton);
      if (next.operationUnknown) footer.append(element(doc, "p", sourceReviewMessage("browser_source_review_operation_outcome_unknown")));
      if (next.jobId) footer.append(element(doc, "p", `Translation job ${next.jobId}. The same start request will recover this job.`));
    } else startButton = null;
    root.append(footer);
    updateSubmitControls();
  }

  function renderPage(page, editor, snapshot) {
    const decision = editor.decision;
    const locked = snapshot.busy || snapshot.invalidated || snapshot.recoveryOnly
      || Boolean(snapshot.revisionId || snapshot.view?.submission || snapshot.pendingKind);
    const grid = element(doc, "div", "", "source-review-grid");
    const imageColumn = element(doc, "div", "", "source-review-image-column");
    const viewport = element(doc, "div", "", "source-review-image-viewport");
    const frame = element(doc, "div", "", "source-review-image-frame");
    frame.style.width = editor.fullSize ? `${page.image_size_px[0]}px` : "100%";
    const image = element(doc, "img");
    image.alt = `Complete source page ${page.page_number}`;
    image.draggable = false;
    const query = new URLSearchParams({ mode: snapshot.scope.runtimeMode, workspace: snapshot.scope.workspaceId });
    image.src = `/api/translation/source-reviews/${snapshot.reviewId}/pages/${page.page_number}/image?${query}`;
    frame.append(image);
    function drawRegion(region, className) {
      if (!validRegion(region, page.image_size_px)) return;
      const box = element(doc, "div", "", className);
      box.style.left = `${100 * region[0] / page.image_size_px[0]}%`;
      box.style.top = `${100 * region[1] / page.image_size_px[1]}%`;
      box.style.width = `${100 * (region[2] - region[0]) / page.image_size_px[0]}%`;
      box.style.height = `${100 * (region[3] - region[1]) / page.image_size_px[1]}%`;
      frame.append(box);
    }
    decision.actions.forEach((action) => drawRegion(action.region_px, "source-review-region saved"));
    if (editor.showWords) for (const word of page.word_evidence?.words || []) {
      if (editor.selected.has(word.block_id)) drawRegion(word.bbox_px, "source-review-region evidence");
    }
    drawRegion(editor.region, "source-review-region selected");
    let origin = null;
    frame.addEventListener("pointerdown", (event) => {
      if (locked || event.button !== 0 || !image.complete) return;
      origin = imagePoint(event.clientX, event.clientY, image.getBoundingClientRect(), page.image_size_px);
      frame.setPointerCapture?.(event.pointerId);
      event.preventDefault();
    });
    frame.addEventListener("pointerup", (event) => {
      if (!origin) return;
      const end = imagePoint(event.clientX, event.clientY, image.getBoundingClientRect(), page.image_size_px);
      if (end) editor.region = [Math.min(origin[0], end[0]), Math.min(origin[1], end[1]),
        Math.max(origin[0], end[0]), Math.max(origin[1], end[1])];
      origin = null;
      changed(page, editor);
      render();
    });
    frame.addEventListener("pointercancel", () => { origin = null; });
    viewport.append(frame);
    imageColumn.append(button(doc, editor.fullSize ? "Fit page to panel" : "Show image at full resolution", () => {
      editor.fullSize = !editor.fullSize; render();
    }), viewport, element(doc, "p", "Drag on the page to select an action region. Selection alone does not accept anything.", "source-review-note"));
    const baseline = element(doc, "textarea");
    baseline.value = page.baseline_text;
    baseline.readOnly = true;
    baseline.dir = "auto";
    baseline.rows = 10;
    imageColumn.append(field(doc, "Original local OCR text (unchanged)", baseline));
    const controls = element(doc, "div", "", "source-review-page-controls");
    controls.append(element(doc, "h3", `Page ${page.page_number}: explicit source actions`));
    controls.append(element(doc, "p", "Select the OCR blocks for one action. Word bounds are retained evidence, not a certified layout. Select a missing-text region with no blocks to transcribe it."));
    const blockList = element(doc, "div", "", "source-review-block-list");
    const owned = new Set(decision.actions.filter((a) => a.id !== editor.editId).flatMap((a) => a.baseline_block_ids));
    page.baseline_blocks.forEach((block, index) => {
      const row = checkbox(doc, `${index + 1}. ${block.text}`, editor.selected.has(block.id), (checked) => {
        checked ? editor.selected.add(block.id) : editor.selected.delete(block.id);
        editor.region = null;
        changed(page, editor);
        render();
      }, locked || owned.has(block.id) || editor.kind === "transcribe");
      row.dir = "auto";
      blockList.append(row);
    });
    controls.append(blockList);
    controls.append(checkbox(doc, "Show retained OCR word boxes for the selected blocks", editor.showWords,
      (value) => { editor.showWords = value; render(); }));
    controls.append(field(doc, "Action", select(doc, [["", "Choose an action…"], ...KINDS], editor.kind, (value) => {
      editor.kind = value;
      if (value === "transcribe") editor.selected.clear();
      changed(page, editor);
      render();
    }, locked)));
    controls.append(button(doc, "Use selected word bounds as this action region", () => {
      editor.region = selectedWordRegion(page, [...editor.selected]); changed(page, editor); render();
    }, locked || !editor.selected.size));
    controls.append(element(doc, "p", editor.region ? `Selected image region: ${editor.region.map((n) => Number(n.toFixed(2))).join(", ")}` : "No region selected."));
    const coordinates = element(doc, "details");
    coordinates.append(element(doc, "summary", "Enter an image rectangle with the keyboard"));
    ["Left", "Top", "Right", "Bottom"].forEach((label, index) => {
      const coordinate = input(doc, editor.regionInput[index], (value) => {
        editor.regionInput[index] = value; editor.region = null; changed(page, editor);
      }, { disabled: locked });
      coordinate.type = "number"; coordinate.min = "0"; coordinate.step = "any";
      coordinate.max = String(page.image_size_px[index % 2]);
      coordinates.append(field(doc, `${label} (original image pixels)`, coordinate));
    });
    coordinates.append(button(doc, "Use this typed rectangle", () => {
      const region = editor.regionInput.map((value) => value.trim() ? Number(value) : NaN);
      if (!validRegion(region, page.image_size_px)) { localMessage = "Enter four ordered coordinates inside the original image."; render(); return; }
      editor.region = region; changed(page, editor); render();
    }, locked));
    controls.append(coordinates);
    const before = page.baseline_blocks.filter((b) => editor.selected.has(b.id)).map((b) => b.text).join("\n");
    const text = input(doc, editor.kind === "retain" ? before : editor.kind === "omit_nontext" ? "" : editor.text,
      (value) => { editor.text = value; changed(page, editor); }, { textarea: true, disabled: locked || ["retain", "omit_nontext"].includes(editor.kind) });
    text.rows = 5;
    controls.append(field(doc, "Source text after this action", text));
    controls.append(field(doc, "Why is this action correct?", input(doc, editor.rationale, (value) => { editor.rationale = value; changed(page, editor); }, { disabled: locked })));
    controls.append(button(doc, editor.editId ? "Save action changes" : "Add this explicit action", () => {
      try {
        const action = sourceActionFromInput(page, { id: editor.editId, kind: editor.kind,
          baseline_block_ids: [...editor.selected], after_text: editor.text, region_px: editor.region, rationale: editor.rationale });
        const index = decision.actions.findIndex((a) => a.id === editor.editId);
        if (index >= 0) decision.actions[index] = action; else decision.actions.push(action);
        decision.reading_order = decision.reading_order.filter((id) => id !== action.id || action.kind !== "omit_nontext");
        if (action.kind !== "omit_nontext" && !decision.reading_order.includes(action.id)) decision.reading_order.push(action.id);
        editor.editId = ""; editor.kind = ""; editor.text = ""; editor.rationale = ""; editor.region = null; editor.regionInput = ["", "", "", ""]; editor.selected.clear();
        localMessage = "Action recorded locally. Review the order and save the page.";
        changed(page, editor); render();
      } catch (error) { localMessage = error.message; render(); }
    }, locked));
    controls.append(button(doc, "Cancel unfinished action", () => {
      editor.editId = ""; editor.kind = ""; editor.text = ""; editor.rationale = ""; editor.region = null; editor.regionInput = ["", "", "", ""]; editor.selected.clear();
      changed(page, editor); render();
    }, locked));
    renderActions(controls, page, editor, locked);
    renderFindings(controls, page, editor, locked);
    controls.append(field(doc, "Page reviewer", input(doc, decision.reviewer, (value) => {
      decision.reviewer = value; changed(page, editor);
    }, { disabled: locked })));
    controls.append(field(doc, "Page boundary", select(doc,
      [["unresolved", "Choose after reviewing…"], ["start", "Starts a document/section"], ["continuation", "Continues the previous page"]],
      decision.boundary_decision, (value) => { decision.boundary_decision = value; changed(page, editor); render(); }, locked)));
    controls.append(field(doc, "Boundary explanation", input(doc, decision.boundary_rationale, (value) => {
      decision.boundary_rationale = value; changed(page, editor);
    }, { disabled: locked })));
    const fullCheck = checkbox(doc, "I reviewed the complete page image for missing or invented text", decision.full_page_review_completed,
      (value) => { decision.full_page_review_completed = value; changed(page, editor, false); }, locked);
    const orderCheck = checkbox(doc, "I checked the reading order shown above", decision.reading_order_reviewed,
      (value) => { decision.reading_order_reviewed = value; changed(page, editor, false); }, locked);
    editor.completionInputs = [fullCheck.querySelector("input"), orderCheck.querySelector("input")];
    controls.append(fullCheck, orderCheck);
    controls.append(button(doc, snapshot.pendingKind === "save" ? "Retry this exact page save" : "Save page decisions", async () => {
      const unfinished = editor.kind || editor.editId || editor.selected.size || editor.region || editor.regionInput.some((value) => value !== "")
        || editor.findingCategory || editor.findingStatus || editor.findingRationale || editor.findingActions.size;
      const problem = unfinished ? "Finish or cancel the unfinished action/finding before saving the page."
        : sourceDecisionProblem(page, decision);
      if (problem) { localMessage = problem; render(); return; }
      localMessage = "";
      await controller.savePage(page.page_number, decision);
    }, snapshot.busy || (locked && snapshot.pendingKind !== "save")));
    grid.append(imageColumn, controls);
    root.append(grid);
  }

  function renderActions(parent, page, editor, locked) {
    const decision = editor.decision;
    parent.append(element(doc, "h4", "Reading order and omitted artifacts"));
    const order = [...decision.reading_order, ...decision.actions.filter((a) => a.kind === "omit_nontext").map((a) => a.id)];
    order.forEach((id) => {
      const action = decision.actions.find((a) => a.id === id);
      if (!action) return;
      const row = element(doc, "div", "", "source-review-action");
      const label = element(doc, "p", `${KINDS.find(([kind]) => kind === action.kind)?.[1]}: ${action.after_text || "[non-text artifact omitted]"}`);
      label.dir = "auto";
      row.append(label);
      const position = decision.reading_order.indexOf(id);
      [-1, 1].forEach((step) => row.append(button(doc, step < 0 ? "Move up" : "Move down", () => {
        [decision.reading_order[position], decision.reading_order[position + step]] =
          [decision.reading_order[position + step], decision.reading_order[position]];
        changed(page, editor); render();
      }, locked || position < 0 || position + step < 0 || position + step >= decision.reading_order.length)));
      row.append(button(doc, "Edit action", () => {
        editor.editId = id; editor.kind = action.kind; editor.selected = new Set(action.baseline_block_ids);
        editor.text = action.after_text; editor.region = [...action.region_px]; editor.rationale = action.rationale;
        changed(page, editor); render();
      }, locked));
      row.append(button(doc, "Remove action", () => {
        decision.actions = decision.actions.filter((a) => a.id !== id);
        decision.reading_order = decision.reading_order.filter((n) => n !== id);
        decision.findings.forEach((f) => { if (f.action_ids.includes(id)) { f.action_ids = f.action_ids.filter((n) => n !== id); f.status = "unresolved"; } });
        changed(page, editor); render();
      }, locked));
      parent.append(row);
    });
  }

  function renderFindings(parent, page, editor, locked) {
    const details = element(doc, "details", "", "source-review-findings");
    details.append(element(doc, "summary", "Record a review finding (optional)"));
    details.append(field(doc, "Category", select(doc, [["", "Choose a category…"], ...CATEGORIES.map((c) => [c, c.replaceAll("_", " ")])],
      editor.findingCategory, (value) => { editor.findingCategory = value; changed(page, editor); }, locked)));
    details.append(field(doc, "Resolution", select(doc, [["", "Choose a status…"], ["unresolved", "Unresolved"], ["resolved", "Resolved by linked actions"]],
      editor.findingStatus, (value) => { editor.findingStatus = value; changed(page, editor); }, locked)));
    editor.decision.actions.forEach((a, index) => details.append(checkbox(doc, `Link action ${index + 1}`, editor.findingActions.has(a.id),
      (value) => { value ? editor.findingActions.add(a.id) : editor.findingActions.delete(a.id); changed(page, editor); }, locked)));
    details.append(field(doc, "Finding explanation", input(doc, editor.findingRationale, (value) => { editor.findingRationale = value; changed(page, editor); }, { disabled: locked })));
    details.append(button(doc, "Add finding", () => {
      if (!CATEGORIES.includes(editor.findingCategory) || !["resolved", "unresolved"].includes(editor.findingStatus)
          || !editor.findingRationale.trim() || (editor.findingStatus === "resolved" && !editor.findingActions.size)) {
        localMessage = "Choose a finding category/status, explain it and link any resolution actions."; render(); return;
      }
      editor.decision.findings.push({ id: newSourceReviewId(), category: editor.findingCategory, status: editor.findingStatus,
        action_ids: [...editor.findingActions], rationale: editor.findingRationale });
      editor.findingCategory = ""; editor.findingStatus = ""; editor.findingRationale = ""; editor.findingActions.clear();
      changed(page, editor); render();
    }, locked));
    details.append(button(doc, "Cancel unfinished finding", () => {
      editor.findingCategory = ""; editor.findingStatus = ""; editor.findingRationale = ""; editor.findingActions.clear();
      changed(page, editor); render();
    }, locked));
    editor.decision.findings.forEach((finding) => {
      const row = element(doc, "div", "", "source-review-action");
      row.append(element(doc, "p", `${finding.category}: ${finding.status}. ${finding.rationale}`));
      row.append(button(doc, "Remove finding to revise it", () => {
        editor.decision.findings = editor.decision.findings.filter((f) => f.id !== finding.id);
        changed(page, editor); render();
      }, locked));
      details.append(row);
    });
    parent.append(details);
  }

  let sessionStorage = storage;
  if (sessionStorage === undefined) {
    try { sessionStorage = globalThis.sessionStorage; } catch { sessionStorage = null; }
  }
  controller = createSourceReviewController({ getScope, getSetup, manualReady, onChange: render,
    onJob, request, storage: sessionStorage, createNonce });
  prepareButton.addEventListener("click", async () => {
    try {
      await beforePrepare?.();
      await controller.prepare();
    } catch {
      localMessage = "Wait for the manual PDF to finish staging, then prepare the source review.";
      render();
    }
  });
  render(controller.snapshot());
  let ready = manualReady();
  return { controller, sync: () => {
    controller.sync();
    const nextReady = manualReady();
    if (ready !== nextReady) { ready = nextReady; render(controller.snapshot()); }
  } };
}
