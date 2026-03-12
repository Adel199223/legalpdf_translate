# Qt UI Knowledge Pack

## A. Entry Points and File Map

| File | Key Classes / Functions |
|------|----------------------|
| `src/legalpdf_translate/qt_app.py` | `run()` creates `QApplication`, applies stylesheet, shows `QtMainWindow`; real GUI module entrypoint |
| `src/legalpdf_translate/qt_main.py` | compatibility shim that delegates to `qt_app.run()` |
| `src/legalpdf_translate/qt_gui/window_controller.py` | `WorkspaceWindowController` (workspace registry, numbering, last-active tracking, Gmail intake routing, duplicate-target reservation map) |
| `src/legalpdf_translate/qt_gui/app_window.py` | `_FuturisticCanvas` (background/frame paint), `QtMainWindow` (`_build_ui`, `_apply_responsive_layout`, `_update_card_max_width`, `_refresh_lang_badge`, `_refresh_pdf_field_chrome`, `_configure_footer_layout`, `_install_overflow_menu`, `_apply_theme_effects`) |
| `src/legalpdf_translate/qt_gui/window_adaptive.py` | `WINDOW_SIZING_PRESETS`, `ResponsiveWindowController`, `CollapsibleSection` |
| `src/legalpdf_translate/qt_gui/styles.py` | `build_stylesheet(theme=...)`, `normalize_ui_theme()`, `theme_palette()`, `theme_effect_colors()`, `apply_app_appearance()`, `apply_soft_shadow()`, `apply_primary_glow()` |
| `src/legalpdf_translate/qt_gui/guarded_inputs.py` | `NoWheelComboBox`, `GuardedDateEdit`, local hover/popup ownership helpers for guarded shell selectors |
| `src/legalpdf_translate/qt_gui/dialogs.py` | `QtSettingsDialog` (appearance/glossary/study/diagnostics tabs), `QtGlossaryEditorDialog`, `QtJobLogWindow`, `QtReviewQueueDialog`, `QtSaveToJobLogDialog` |
| `src/legalpdf_translate/qt_gui/tools_dialogs.py` | `QtGlossaryBuilderDialog`, `QtCalibrationAuditDialog` |

### Runtime launch contract
- Supported desktop launch: `python -m legalpdf_translate.qt_app`
- Detached Windows launch: `Start-Process .\.venv311\Scripts\pythonw.exe -ArgumentList '-m','legalpdf_translate.qt_app'`
- `python -m legalpdf_translate.qt_main` remains a compatibility shim, not the canonical command.

## B. objectName Conventions

| objectName | Widget Type | Purpose |
|-----------|-------------|---------|
| `RootWidget` | `_FuturisticCanvas` | painted dashboard scene/background |
| `ShellScrollArea` | QScrollArea | main-shell scroll viewport with transparent chrome |
| `ShellScrollContent` | QWidget | transparent main-shell scroll content root |
| `ContentCard` | QWidget | centered dashboard content column |
| `SidebarPanel` | QFrame | left navigation rail |
| `SidebarNavButton` | QToolButton | sidebar nav item (`Dashboard`, `New Job`, `Recent Jobs`, `Settings`, `Profile`) |
| `HeroTitleLabel` | QLabel | centered `LegalPDF Translate` title |
| `HeroStatusLabel` | QLabel | right-aligned top status text |
| `DashboardFrame` | QFrame | outer shell around setup/output/action regions |
| `ShellPanel` | QFrame | interior setup/progress/details/advisor panels |
| `PanelHeading` | QLabel | `Job Setup`, `Conversion Output` headings |
| `FieldChrome` | QFrame | embedded dashboard field container |
| `FieldBrowseButton` | QToolButton | right-edge browse/action affordance inside dashboard fields |
| `LangCaretButton` | QToolButton | explicit dropdown caret in target-language field |
| `SectionToggleButton` | QToolButton | `Advanced Settings` collapsible bar |
| `MetricGridFrame` | QFrame | output metrics grid container |
| `PrimaryButton` | QPushButton | shared primary commit/run/apply action across shell/dialog/tool surfaces |
| `DangerButton` | QPushButton | shared destructive or reset action across shell/dialog/tool surfaces |
| `OverflowMenuButton` | QToolButton | `...` overflow menu trigger |
| `ActionRail` | QFrame | bottom action rail |
| `FooterMetaLabel` | QLabel | `Project v3.0 | LegalPDF` |
| `DialogScrollArea` | QScrollArea | scrollable dialog body viewport |
| `DialogScrollContent` | QWidget | transparent dialog scroll body |
| `DialogActionBar` | QWidget | fixed bottom action row inside tall dialogs |
| `GlossaryTableCombo` | QComboBox | plain in-table glossary editor combo with local size/padding polish; intentionally not converted to `NoWheelComboBox` |

## C. Layout Tree

```
QtMainWindow
└── _FuturisticCanvas [centralWidget, objectName="RootWidget"]
    └── QHBoxLayout [outer]
        ├── QFrame#SidebarPanel [sidebar_frame]
        │   └── QVBoxLayout
        │       ├── Sidebar logo
        │       ├── Dashboard nav
        │       ├── New Job nav
        │       ├── Recent Jobs nav
        │       ├── Settings nav
        │       └── Profile nav
        └── QScrollArea#ShellScrollArea [_scroll_area]
            └── QWidget#ShellScrollContent [scroll_content]
                └── QVBoxLayout [scroll_layout]
                    └── QHBoxLayout [content_row_layout]
                        └── QWidget#ContentCard [content_card]
                            └── QVBoxLayout [card_shell_layout]
                                ├── QGridLayout [hero row]
                                │   ├── QLabel#HeroTitleLabel
                                │   └── QLabel#HeroStatusLabel
                                ├── QHBoxLayout [dashboard_row_layout]
                                │   └── QFrame#DashboardFrame
                                │       └── QVBoxLayout [dashboard_layout]
                                │           └── QFrame [main_card]
                                │               └── QVBoxLayout
                                │                   ├── QBoxLayout [body_layout]
                                │                   │   ├── QFrame#ShellPanel [setup_panel]
                                │                   │   │   ├── setup_grid
                                │                   │   │   ├── QToolButton#SectionToggleButton
                                │                   │   │   ├── adv_frame
                                │                   │   │   └── advisor_frame
                                │                   │   └── QFrame#ShellPanel [progress_panel]
                                │                   │       ├── QLabel#PanelHeading ("Conversion Output")
                                │                   │       ├── summary row
                                │                   │       ├── QProgressBar
                                │                   │       ├── current-task row
                                │                   │       ├── QFrame#MetricGridFrame
                                │                   │       └── output format label
                                │                   └── QFrame#ActionRail [footer_card]
                                │                       ├── Start Translate
                                │                       ├── Cancel
                                │                       └── ...
                                ├── footer meta row
                                ├── details_card
                                └── utility_panel (hidden compatibility controls)
```

## D. UI Invariants

### 1. Launch command invariant
- **What:** The real GUI entrypoint is `legalpdf_translate.qt_app`.
- **Why:** `qt_app.py` owns `QApplication`, stylesheet setup, icon setup, and `QtMainWindow.show()`.
- **Verify:** `python -m legalpdf_translate.qt_app`
- **Breaks if:** docs or scripts keep pointing to `legalpdf_translate.qt_gui`.

### 1b. Runtime theme contract
- **What:** `ui_theme` is a real runtime setting, not dead persisted state.
- **Where:** `qt_app.run()` loads GUI settings and calls `apply_app_appearance()`. Live changes propagate through `WorkspaceWindowController.apply_shared_settings()`.
- **Choices:**
  - `dark_futuristic` = Gemini-locked elevated default with a warm smoked menu band, brighter cyan-glass shell borders, stronger aqua title/sidebar accents, and richer cyan/salmon action fills
  - `dark_simple` = lower-noise darker variant built from the same shared selectors with softer effect tokens
- **Mechanics:** shell effect colors are derived from `theme_effect_colors()` and reapplied through `QtMainWindow._apply_theme_effects()` after UI construction and on shared-theme reload, so title/dashboard/footer/button glow does not go stale when the theme changes live.
- **Verify:** changing `Settings > Appearance > Theme` immediately restyles the open app windows and dialogs without restarting, and switching between `dark_futuristic` and `dark_simple` visibly changes the title/footer glow colors.

### 1a. Multi-window workspace contract
- **What:** The app now uses independent top-level workspaces under one `QApplication`, not tabs or an MDI shell.
- **Where:** `qt_app.run()` creates a `WorkspaceWindowController`, which owns top-level windows, workspace numbering, last-active tracking, and duplicate-target reservations.
- **Behavior:** `File > New Window`, `Ctrl+Shift+N`, and the overflow blank-window action must stay available even while another workspace is busy.
- **Verify:** a new window opens with an incremented `Workspace N` title; starting a second job is allowed only when it resolves to a different run folder.

### 2. Three responsive layout modes
- **What:** Layout is controlled by explicit size classes, not ad-hoc widget drift.
- **Where:** `_LAYOUT_DESKTOP_EXACT`, `_LAYOUT_DESKTOP_COMPACT`, `_LAYOUT_STACKED_COMPACT` plus `_layout_mode_for_budget()`.
- **Breakpoints:**
  - `desktop_exact`: content budget `>= 1500`
  - `desktop_compact`: `1180..1499`
  - `stacked_compact`: `< 1180`
- **Verify:** wide window = two-column shell; narrow window = stacked shell.

### 2a. Shared top-level window sizing contract
- **What:** Top-level windows and major dialogs must use the shared adaptive sizing helper instead of hardcoded open-time geometry.
- **Where:** `qt_gui/window_adaptive.py` via `ResponsiveWindowController` and role presets in `WINDOW_SIZING_PRESETS`.
- **Roles:** `shell`, `form`, `table`, `preview`.
- **Behavior:** initial size is derived from the current screen, clamped to available geometry, and kept user-resizable; dialogs should not open larger than the current display.
- **Verify:** `QtMainWindow`, `QtSaveToJobLogDialog`, `QtJobLogWindow`, `QtGmailAttachmentPreviewDialog`, `QtSettingsDialog`, `QtReviewQueueDialog`, and glossary/calibration tools all open within small-screen bounds without fixed-size clipping.

### 3. Sidebar geometry comes from `_apply_responsive_layout()`
- **What:** Sidebar width, nav widths, nav heights, icon sizes, and logo size must stay tied to the active size class.
- **Where:** `sidebar_width`, `nav_width`, `nav_height`, `icon_size`, `logo_size` values inside `_apply_responsive_layout()`.
- **Verify:** desktop exact shows readable `Dashboard`/`Recent Jobs`; stacked compact shrinks to icon-heavy chrome without overlap.

### 4. Content-card width is computed, then centered
- **What:** `content_card` uses a computed fixed width based on viewport space, then is centered with `content_row_layout`.
- **Where:** `_update_card_max_width()` sets `target_width = max(360, min(1760, available))` and `content_card.setFixedWidth(target_width)`.
- **Verify:** large windows use most of the available width without horizontal scroll; shell remains centered.

### 4d. Dashboard footprint is independently centered inside the content card
- **What:** the outer `DashboardFrame` no longer always consumes the full `content_card` width. Desktop modes clamp it to a narrower centered shell; stacked compact expands it back to full width.
- **Where:** `dashboard_row_layout` plus the dashboard-width path inside `_apply_responsive_layout()`.
- **Contract:**
  - `desktop_exact`: `DashboardFrame` width `1200`
  - `desktop_compact`: `DashboardFrame` width `1100` unless available width is smaller
  - `stacked_compact`: full-width dashboard shell
- **Verify:** deterministic render-review metadata reports centered desktop `dashboard_frame_x`, narrower desktop `dashboard_frame_width`, and full-width stacked compact `dashboard_frame_x == 0`.

### 4a. Main-shell resize stability contract
- **What:** The main shell should resize smoothly without clipped hero-status text or jittery full-layout recomputation on every tick.
- **Where:** `QtMainWindow` uses `ResponsiveWindowController(..., role="shell", resize_callback=...)` plus the hero-status width reservation path (`hero_status_spacer` and `_sync_hero_status_width()`).
- **Behavior:** the dashboard shell keeps `ScrollBarAlwaysOff`, reserves width for the status text, and coalesces live resize updates rather than thrashing the layout continuously.
- **Verify:** narrow and wide resizing keeps `Idle`-style status text readable, avoids visible trembling, and never adds a horizontal scrollbar to the main shell.

### 4b. Dense data tables may scroll horizontally on purpose
- **What:** The no-horizontal-scroll rule applies to the main dashboard shell, not to dense data tables.
- **Where:** `QtJobLogWindow` in `qt_gui/dialogs.py` intentionally uses interactive header widths, header auto-fit, persisted manual widths, and `ScrollBarAsNeeded`.
- **Verify:** Job Log headers stay readable by default, columns can be resized manually, and a horizontal scrollbar appears when the table becomes wider than the window.

### 4c. Dense secondary windows stay screen-bounded
- **What:** Table-heavy and preview-heavy secondary windows may scroll internally, but the outer window itself should still open within the current screen bounds and remain stable while resizing.
- **Where:** `ResponsiveWindowController` role presets `table` and `preview`, applied in `QtJobLogWindow`, `QtReviewQueueDialog`, `QtGmailBatchReviewDialog`, and `QtGmailAttachmentPreviewDialog`.
- **Verify:** dense dialogs stay on-screen on smaller displays, while their table/preview content handles overflow inside the window instead of forcing off-screen geometry.

### 5. Paint layer must read live geometry
- **What:** `_FuturisticCanvas.paintEvent()` must derive sidebar separator placement from the actual sidebar width, not stale constants.
- **Where:** `sidebar = getattr(window, "sidebar_frame", None)` then `sidebar_line_x = sidebar.width()`.
- **Verify:** painted sidebar divider stays aligned while resizing across layout modes.

### 5a. Main-shell atmosphere is geometry-aware and probe-locked
- **What:** the futuristic shell lighting is not just stylesheet chrome; `_FuturisticCanvas.paintEvent()` paints a warm top smoke band, a large left teal dome glow, brighter circuit/divider lines, and geometry-aware cyan backlights behind the live `DashboardFrame` and `ActionRail`.
- **Where:** `_FuturisticCanvas.paintEvent()` plus `QtMainWindow._apply_theme_effects()` and the `theme_effect_colors()` tokens in `qt_gui/styles.py`.
- **Verify:** deterministic render-review output shows a warm menu probe, brighter dashboard border than dashboard fill, and a brighter footer halo than footer fill. The live shell should read as one continuous glass/neon scene rather than separate flat cards.

### 6. Desktop metrics grid contract
- **What:** Desktop grid shows `Pages`, `Images`, `Errors`, and a `Retries` heading only.
- **Where:** `_build_ui()` metric grid; `metric_retry_header_label` remains, row-level retry cells are not added to the layout.
- **Verify:** no per-row retry counts are visible in the desktop grid, even though retry tracking still exists internally.

### 7. Target-language badge contract
- **What:** Show one language code and one matching flag only.
- **Where:** `_LANG_FLAG_ICON_BY_CODE` and `_refresh_lang_badge()`.
- **Behavior:** if a flag asset is missing, hide the flag widget instead of duplicating text.
- **Verify:** switching `EN`, `FR`, `AR` shows one code, one flag, and no repeated fallback text.

### 7a. Target-language popup contract
- **What:** Keep the closed target-language field compact, but make the popup readable.
- **Where:** `NoWheelComboBox` popup-label support in `qt_gui/guarded_inputs.py` and the embedded target-language field wiring in `qt_gui/app_window.py`.
- **Behavior:** the closed field shows `EN`, `FR`, or `AR`; the popup shows `English`, `French`, and `Arabic`; popup width must fit those labels without `...`.
- **Verify:** opening the target-language popup shows full names, and hovering/opening one dashboard combo does not visually activate a neighboring combo.

### 7b. Source-file support cluster is state-driven
- **What:** the source-file field should not reserve the page-count cluster when no source is selected.
- **Where:** the source-file `FieldChrome` wiring and `_refresh_pdf_field_chrome()` in `qt_gui/app_window.py`.
- **Behavior:** empty or invalid source state hides the page-count icon/divider cluster; a real source restores it. Placeholder copy also shortens in compact layouts to avoid overlap.
- **Verify:** the empty desktop field shows only the placeholder plus browse button, while a selected source shows `Pages: <n>` without text collisions.

### 8. Small-window layout is intentionally different
- **What:** `stacked_compact` is not a broken desktop shell; it is a deliberate mobile-like adaptation.
- **Where:** `_apply_responsive_layout()` changes `body_layout` direction to `TopToBottom` and calls `_configure_footer_layout(compact=True)`.
- **Verify:** setup panel above output panel; `Start Translate` on row 1; `Cancel` and `...` on row 2.

### 9. Guarded selector coverage contract
- **What:** No-wheel guards are used where accidental scroll changes can silently alter active run or fixed-vocabulary admin state: the main shell run controls, Gmail batch review workflow/target-language selectors, settings provider/default plus glossary/study/diagnostics selectors, glossary-builder/calibration top-level selectors, Save/Edit Job Log fixed-vocabulary combos, and Job Log inline combo editors. Guarded spin boxes ignore wheel changes entirely.
- **Where:** `qt_gui/guarded_inputs.py`, `QtMainWindow` in `qt_gui/app_window.py`, Gmail review plus Settings/Job Log helpers in `qt_gui/dialogs.py`, and admin/tool wiring in `qt_gui/tools_dialogs.py`.
- **Exception:** dense table-cell editors keep their local combo contract; `GlossaryTableCombo` and glossary/calibration suggestion scope selectors remain plain `QComboBox`.
- **Verify:** scrolling over a closed guarded selector does not silently change the value, while dense table editors still keep normal Qt combo behavior and guarded combo popups still allow intentional list scrolling.

### 10. Warning dialog contract
- **What:** There are two important runtime warning actions:
  - `Switch to fixed high` for EN/FR `fixed_xhigh`
  - `Apply safe OCR profile` for OCR-heavy API-only runs
- **Behavior:** `Apply safe OCR profile` changes the current form only and does not persist new defaults.
- **Verify:** after applying the safe OCR profile, the form shows `always/api/off/1/fixed_high/resume-off/keep-intermediates-on` for the current run, but reopening the app restores the saved defaults.

### 11. Bounded cancel-wait contract
- **What:** `Cancel and wait` remains cooperative, but it is bounded by the active request deadline and updates the status text while waiting.
- **Where:** `QtMainWindow._resolve_busy_close_choice()`, `_begin_cancel_wait()`, and cancel-wait status refresh logic.
- **Verify:** cancelling an OCR-heavy run shows wait-state progress and resolves within the request budget instead of appearing indefinitely frozen.

### 12. Tall-form dialog contract
- **What:** `QtSaveToJobLogDialog` must stay usable on smaller screens without pushing critical actions off-screen.
- **Where:** `QtSaveToJobLogDialog` now uses `DialogScrollArea` for the body, keeps a fixed `DialogActionBar` outside the scrolling form body, and applies `ResponsiveWindowController(..., role="form")`.
- **Behavior:** the main editable case/service fields remain immediately visible; the body scrolls vertically when needed; `Save`, `Cancel`, `Open translated DOCX`, and the honorários action stay accessible.
- **Verify:** on a smaller display, the dialog fits within the screen bounds, the body scrolls internally, and the action row remains visible.

### 12a. Shared date-picker contract
- **What:** editable app dates use one shared guarded date field instead of plain line edits.
- **Where:** `GuardedDateEdit` in `qt_gui/guarded_inputs.py`, used by Save/Edit Job Log, Job Log inline date editing, and interpretation honorários export.
- **Behavior:** manual `YYYY-MM-DD` typing remains valid, the popup calendar starts on Monday, and the popup styling stays inside the shared translucent chrome instead of falling back to a clashing native widget.
- **Verify:** date fields accept typed ISO text, open the themed calendar popup, and the popup week header starts on Monday in every current usage site.

### 12b. Translation Job Log form contract
- **What:** translation editing should not waste space on interpretation-only service controls.
- **Where:** `QtSaveToJobLogDialog` in `qt_gui/dialogs.py`.
- **Behavior:** translation rows hide the `SERVICE (provided to)` section, keep fixed-vocabulary fields as selection-only combos, and retain a rounded primary action button even when Enter/Return submits the dialog.
- **Verify:** switching `Job type` between translation and interpretation toggles the service section live, `Lang` remains selection-only, and the bottom-right action keeps the shared rounded primary-button styling.

### 13. Save-to-Job-Log collapse defaults
- **What:** Lower-detail Job Log sections are collapsed by default on every open.
- **Where:** `QtSaveToJobLogDialog` uses `CollapsibleSection` for `metrics_section` and `finance_section`.
- **Behavior:** `Run Metrics (auto-filled)` and `Amounts (EUR)` start collapsed in both create mode and historical edit mode; the user can expand them on demand.
- **Verify:** a newly opened Save/Edit Job Log dialog shows those sections collapsed while the main case/service fields stay visible.

### 13b. Court-email confirmation contract
- **What:** `Court Email` stays editable, but Save/Edit Job Log must show its provenance and stop Gmail draft actions when the address was inferred or unresolved.
- **Where:** `QtSaveToJobLogDialog` in `qt_gui/dialogs.py`, shared resolver state from `src/legalpdf_translate/court_email.py`, and Gmail draft guards in `qt_gui/app_window.py`.
- **Behavior:** the hint label under `Court Email` reflects whether the address came from the document, broader document text, manual confirmation, or saved-suggestion inference. User edits or explicit combo selection promote the current address to manual confirmation. Inferred or ambiguous saved-suggestion states block Gmail draft creation with a warning until the user confirms or corrects the field.
- **Verify:** a row with a document-found email shows a non-warning hint and allows Gmail draft creation, while a row populated only from conflicting saved suggestions shows the inferred warning and the draft is not created until `Court Email` is manually confirmed.

### 13a. Shared core-dialog chrome contract
- **What:** `Settings`, `Glossary Editor`, `Glossary Builder`, `Calibration Audit`, Gmail preview/review, Save/Edit Job Log, and honorários export should inherit the same elevated translucent styling language as the dashboard instead of relying on dialog-local one-off styles.
- **Where:** centralized selectors in `qt_gui/styles.py`, especially `QDialog`, `QGroupBox`, `QTabWidget`, `DialogScrollArea`, and `DialogActionBar`.
- **Verify:** those dialogs visibly inherit the same layered panel/field/button treatment while remaining screen-bounded and responsive.

### 14. Preview resize coalescing contract
- **What:** Attachment preview scaling must be coalesced so drag-resizing does not trigger full rescale/reflow work on every viewport tick.
- **Where:** `QtGmailAttachmentPreviewDialog` uses `_scaled_preview_timer`, viewport event filtering, and a deferred `_refresh_scaled_preview()` path.
- **Behavior:** preview refresh is scheduled after resize bursts settle, which reduces visible shake in PDF/image preview while preserving lazy page refresh behavior.
- **Verify:** a burst of resize events results in one deferred scaled refresh instead of repeated immediate rescale churn.

## E. How to Change X

### Change sidebar width or nav rhythm
- Edit the size-class values in `_apply_responsive_layout()`:
  - `sidebar_width`
  - `nav_width`
  - `nav_height`
  - `icon_size`
  - `logo_size`

### Change desktop shell balance
- Edit `progress_stretch` inside `_apply_responsive_layout()`.
- `body_layout.addWidget(self.setup_panel, 7)` and `body_layout.addWidget(self.progress_panel, 6)` are the base stretch weights.

### Change centered dashboard footprint
- Edit the dashboard-width path inside `_apply_responsive_layout()`.
- Keep `content_card` width logic in `_update_card_max_width()` separate from the narrower desktop `DashboardFrame` clamp.
- Preserve `dashboard_row_layout` centering for desktop modes and full-width expansion for `stacked_compact`.

### Change shell palette or glow
- Edit palette tokens in `qt_gui/styles.py` first, especially `theme_palette()` and `theme_effect_colors()`.
- Reapply shell graphics effects through `_apply_theme_effects()` instead of adding one-off widget glow calls in `_build_ui()`.
- Use `_FuturisticCanvas.paintEvent()` for scene-level haze, dome glow, dividers, and geometry-aware backlights behind `DashboardFrame` / `ActionRail`.

### Change output actions
- Edit `_install_overflow_menu()` for `...` menu items.
- Review Queue and Save to Job Log remain top-menu actions in `_install_menu()`.

### Change top-level window sizing behavior
- Start in `qt_gui/window_adaptive.py`.
- Adjust `WINDOW_SIZING_PRESETS` or `ResponsiveWindowController` before adding per-dialog `resize(...)` calls.
- Keep `shell` horizontally adaptive without a shell-level horizontal scrollbar; let dense table/preview content handle overflow inside the window instead.

### Change Save-to-Job-Log layout
- Edit `QtSaveToJobLogDialog` in `qt_gui/dialogs.py`.
- Preserve the `form_scroll_area` body and the fixed action row unless the interaction model is intentionally being redesigned.
- Keep `metrics_section` and `finance_section` collapsed by default unless product requirements change.

### Change preview resizing behavior
- Edit `QtGmailAttachmentPreviewDialog` in `qt_gui/dialogs.py`.
- Preserve deferred/coalesced preview refresh; do not reintroduce per-resize-tick scaling work unless there is a strong reason and new verification coverage.

### Change field icons or language flags
- Update assets under `resources/icons/dashboard/`.
- Update `_LANG_FLAG_ICON_BY_CODE` when adding a new supported UI flag.

### Change progress-grid presentation
- Edit the metric-grid section in `_build_ui()` and the data population logic in `_apply_dashboard_snapshot()` / `_refresh_dashboard_counters()`.
- Keep the heading-only retries presentation unless the visual contract changes intentionally.

## F. How to Verify

### Automated

```bash
python -m pytest -q tests/test_qt_main_smoke.py tests/test_qt_app_state.py tests/test_qt_render_review.py
python tooling/qt_render_review.py --outdir tmp/qt_ui_review --preview reference_sample --profiles wide medium narrow
python -m pytest -q
python -m compileall src tests
```

- `tooling/qt_render_review.py` now emits shell color probes for `menu_bar_mid_rgb`, `left_glow_rgb`, `dashboard_border_rgb`, `footer_halo_rgb`, `primary_button_rgb`, `danger_button_rgb`, and sidebar active/inactive comparison so visual regressions can be asserted relationally instead of by brittle screenshot hashes.

### Manual smoke check

1. Launch app: `python -m legalpdf_translate.qt_app`
2. Optional detached launch on Windows: `Start-Process .\.venv311\Scripts\pythonw.exe -ArgumentList '-m','legalpdf_translate.qt_app'`
3. Desktop exact: sidebar labels readable, `Conversion Output` visible, two-column shell intact
4. Desktop compact: still two-column, no clipped fields or drifting action rail
5. Stacked compact: setup/output stack cleanly; footer reflows to two rows
6. Switch language between `EN`, `FR`, `AR` and confirm one code + one flag only
7. Open `...` and confirm only:
   - `Open Output Folder`
   - `Export Partial DOCX`
   - `Rebuild DOCX`
   - `Generate Run Report`
   - `View Job Log`
8. Open `Tools` and confirm `Review Queue...` and `Save to Job Log...` remain reachable
9. Resize the main window across wide and narrow states and confirm the hero status text still fits cleanly without trembling or a shell-level horizontal scrollbar
10. Open `Tools > Save to Job Log...` and confirm the dialog fits on-screen, scrolls internally on smaller sizes, and starts with `Run Metrics` and `Amounts` collapsed
11. Open `Tools > View Job Log` and confirm the table uses icon row actions, resizable headers, and horizontal scrolling only when the table is wider than the window
12. Open Gmail attachment preview and confirm drag-resizing does not visibly shake from repeated rescale/reflow work
13. In `Save to Job Log`, check the hint under `Court Email`: document-found addresses should read as safe, while inferred/ambiguous addresses should warn and block Gmail draft creation until you confirm the field manually
14. Scroll over the closed run-critical selectors and confirm they do not change by accident
15. Trigger the EN/FR xhigh warning and confirm `Switch to fixed high` changes the current effort policy
16. Trigger the OCR-heavy warning and confirm `Apply safe OCR profile` changes the current run only
17. Open `File > New Window` or press `Ctrl+Shift+N` and confirm a second top-level window appears with the next `Workspace N` title
18. Start a run in one workspace and confirm another workspace stays usable while it is busy
19. Configure the same source file, target language, and output folder in two workspaces and confirm the second start is blocked as duplicate run-folder reuse
20. If Gmail intake is enabled, confirm intake reuses an idle blank workspace first and opens a new workspace when the last active one is busy or already has job context
21. In `dark_futuristic`, confirm the top menu bar reads as a warm smoky band, the left background glow is visibly stronger than the nearby cold field chrome, the dashboard/footer shells carry cyan bloom, the primary button reads cyan, and the cancel button reads salmon rather than disabled maroon
