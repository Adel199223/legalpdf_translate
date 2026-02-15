# Qt UI Playbook

## A. Rules of Engagement

1. **Prefer size policies and layout constraints over fixed pixel sizes.** Use `setMinimumSize`, `setMaximumWidth`, and `QSizePolicy` rather than hard-coded `resize()` or `setFixedSize()`.
2. **Never change paint geometry without updating `_FRAME_INSETS`.** The decorative frame in `_FuturisticCanvas.paintEvent` and the outer layout margins both read from this single constant. Changing one without the other silently breaks card centering.
3. **Keep UI changes isolated to `qt_gui/`** unless the change absolutely requires touching other modules (e.g., adding a new `RunConfig` field that the UI exposes).
4. **Test layout changes visually** — automated tests catch imports and smoke, but layout regressions (clipping, overflow, misalignment) require a manual resize/maximize/restore check.
5. **Preserve LTR direction overrides.** The window and footer card force `LeftToRight` so that RTL target languages don't flip UI chrome. Do not remove these.
6. **Do not add a horizontal scrollbar.** `ScrollBarAlwaysOff` is intentional — if content clips, fix the content width, don't enable horizontal scroll.

## B. Search Recipes

### Find frame/paint geometry code
```bash
rg -n "_FuturisticCanvas|paintEvent|frame_rect|_FRAME_INSETS" src/legalpdf_translate/qt_gui/
```

### Find layout margin and centering code
```bash
rg -n "setContentsMargins|content_card|setMaximumWidth|AlignHCenter|ScrollBarAlwaysOff" src/legalpdf_translate/qt_gui/
```

### Find button styling and glow
```bash
rg -n "PrimaryButton|DangerButton|apply_primary_glow|QPushButton" src/legalpdf_translate/qt_gui/
```

### Find footer button layout
```bash
rg -n "footer_card|QGridLayout|btn_grid|setToolTip" src/legalpdf_translate/qt_gui/
```

### Find stylesheet selectors and palette
```bash
rg -n "objectName|PALETTE|build_stylesheet" src/legalpdf_translate/qt_gui/styles.py
```

### Find scroll area setup
```bash
rg -n "QScrollArea|setWidgetResizable|setFrameShape|ScrollBarPolicy" src/legalpdf_translate/qt_gui/
```

## C. Change Checklists

### Before making a Qt UI change

- [ ] Read `docs/assistant/QT_UI_KNOWLEDGE.md` — especially the invariants (section C)
- [ ] Identify which invariant(s) the change might affect
- [ ] Search for related code using the recipes above

### During the change

- [ ] If touching paint geometry → update `_FRAME_INSETS` (not the raw numbers)
- [ ] If adding/removing footer buttons → update both `row0`/`row1` lists and keep `setColumnStretch` after the last column
- [ ] If changing card width → update both `setMaximumWidth()` and the `min(1180, ...)` in `_update_card_max_width()`
- [ ] If adding a new widget → set appropriate `objectName` for QSS targeting
- [ ] If adding a new panel → use `objectName="SurfacePanel"` for consistent styling

### After the change

- [ ] Run `python -m pytest -q`
- [ ] Run `python -m compileall src tests`
- [ ] Launch app: `python -m legalpdf_translate.qt_gui`
- [ ] Resize window to various sizes — card stays inside painted frame
- [ ] Maximize — card centered, no horizontal scrollbar
- [ ] Restore to normal size — card adapts
- [ ] Check all footer button labels are fully readable
- [ ] Toggle Show Advanced — card grows, vertical scrollbar appears if needed
- [ ] Update `docs/assistant/QT_UI_KNOWLEDGE.md` if any invariant changed
