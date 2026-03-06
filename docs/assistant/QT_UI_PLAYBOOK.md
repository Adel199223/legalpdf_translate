# Qt UI Playbook

## A. Rules of Engagement

1. **Use `REFERENCE_LOCKED_QT_UI_WORKFLOW.md` when a visual reference is the acceptance target.** Desktop exactness is a binary contract, not a “close enough” discussion.
2. **Prefer the responsive size-class path over one-off geometry tweaks.** Desktop behavior is driven by `_layout_mode_for_budget()` and `_apply_responsive_layout()`. Change that first.
3. **Never change paint geometry in isolation.** `_FuturisticCanvas.paintEvent()` must stay aligned with live widget geometry, especially `sidebar_frame.width()` and the computed `content_card` width.
4. **Keep UI changes isolated to `qt_gui/`** unless the change absolutely requires touching other modules (e.g., adding a new `RunConfig` field that the UI exposes).
5. **Test layout changes visually with deterministic renders first.** Run `tooling/qt_render_review.py` before relying on ad hoc desktop screenshots.
6. **Preserve LTR direction overrides.** The window and footer card force `LeftToRight` so that RTL target languages don't flip UI chrome. Do not remove these.
7. **Do not add a horizontal scrollbar.** `ScrollBarAlwaysOff` is intentional — if content clips, fix the content width, don't enable horizontal scroll.

## B. Search Recipes

### Find frame/paint geometry code
```bash
rg -n "_FuturisticCanvas|paintEvent|sidebar_line_x|content_card|_FRAME_INSETS" src/legalpdf_translate/qt_gui/
```

### Find layout mode and centering code
```bash
rg -n "_LAYOUT_DESKTOP|_apply_responsive_layout|_update_card_max_width|content_card|ScrollBarAlwaysOff" src/legalpdf_translate/qt_gui/
```

### Find button styling and glow
```bash
rg -n "PrimaryButton|DangerButton|apply_primary_glow|QPushButton" src/legalpdf_translate/qt_gui/
```

### Find footer button layout
```bash
rg -n "ActionRail|_configure_footer_layout|OverflowMenuButton|PrimaryButton|DangerButton" src/legalpdf_translate/qt_gui/
```

### Find stylesheet selectors and palette
```bash
rg -n "objectName|PALETTE|build_stylesheet" src/legalpdf_translate/qt_gui/styles.py
```

### Find language badge and field chrome
```bash
rg -n "_refresh_lang_badge|_LANG_FLAG_ICON_BY_CODE|FieldChrome|LangCaretButton|FieldBrowseButton" src/legalpdf_translate/qt_gui/
```

## C. Change Checklists

### Reference-locked review contract

- [ ] Freeze one desktop validation size and keep it constant through the pass
- [ ] Review these regions independently: sidebar, hero row, setup card, output card, footer rail, overflow menu, background scene
- [ ] Mark each region pass/fail; do not advance on vague “closer” language
- [ ] Treat desktop exact as authoritative; medium/narrow are stability checks only
- [ ] Generate deterministic wide/medium/narrow renders with `tooling/qt_render_review.py`

### Before making a Qt UI change

- [ ] Read `docs/assistant/QT_UI_KNOWLEDGE.md` — especially the invariants (section C)
- [ ] Identify which invariant(s) the change might affect
- [ ] Search for related code using the recipes above

### During the change

- [ ] If touching layout behavior → update `_layout_mode_for_budget()` / `_apply_responsive_layout()` before adding local widget hacks
- [ ] If touching paint geometry → confirm paint logic still derives from live sidebar/card geometry
- [ ] If changing card width behavior → update `_update_card_max_width()` and verify the centered `content_row_layout` still works
- [ ] If adding a new widget → set appropriate `objectName` for QSS targeting
- [ ] If adding a new shell panel → use `objectName="ShellPanel"` for consistent styling

### After the change

- [ ] Run `python -m pytest -q`
- [ ] Run `python -m compileall src tests`
- [ ] Launch app: `python -m legalpdf_translate.qt_app`
- [ ] Generate deterministic review renders: `python tooling/qt_render_review.py --outdir tmp_ui_review --preview reference_sample`
- [ ] Desktop exact: readable sidebar labels, `Conversion Output`, two-column shell
- [ ] Desktop compact: still two-column, no clipped field chrome
- [ ] Stacked compact: setup/output stack cleanly, footer reflows to two rows
- [ ] Verify `...` menu actions and `Tools` menu routes still match the dashboard shell contract
- [ ] Update `docs/assistant/QT_UI_KNOWLEDGE.md` if any invariant changed
