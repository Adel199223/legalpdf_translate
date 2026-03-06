# Qt UI Playbook

## A. Rules of Engagement

1. **Prefer the responsive size-class path over one-off geometry tweaks.** Desktop behavior is driven by `_layout_mode_for_budget()` and `_apply_responsive_layout()`. Change that first.
2. **Never change paint geometry in isolation.** `_FuturisticCanvas.paintEvent()` must stay aligned with live widget geometry, especially `sidebar_frame.width()` and the computed `content_card` width.
3. **Keep UI changes isolated to `qt_gui/`** unless the change absolutely requires touching other modules (e.g., adding a new `RunConfig` field that the UI exposes).
4. **Test layout changes visually** — automated tests catch imports and smoke, but layout regressions (clipping, overflow, misalignment) require a manual resize/maximize/restore check.
5. **Preserve LTR direction overrides.** The window and footer card force `LeftToRight` so that RTL target languages don't flip UI chrome. Do not remove these.
6. **Do not add a horizontal scrollbar.** `ScrollBarAlwaysOff` is intentional — if content clips, fix the content width, don't enable horizontal scroll.

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
- [ ] Desktop exact: readable sidebar labels, `Conversion Output`, two-column shell
- [ ] Desktop compact: still two-column, no clipped field chrome
- [ ] Stacked compact: setup/output stack cleanly, footer reflows to two rows
- [ ] Verify `...` menu actions and `Tools` menu routes still match the dashboard shell contract
- [ ] Update `docs/assistant/QT_UI_KNOWLEDGE.md` if any invariant changed
