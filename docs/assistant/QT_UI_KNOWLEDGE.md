# Qt UI Knowledge Pack

## A. Entry Points and File Map

| File | Key Classes / Functions |
|------|----------------------|
| `src/legalpdf_translate/qt_app.py` | `run()` creates `QApplication`, applies stylesheet, shows `QtMainWindow`; real GUI module entrypoint |
| `src/legalpdf_translate/qt_main.py` | compatibility shim that delegates to `qt_app.run()` |
| `src/legalpdf_translate/qt_gui/window_controller.py` | `WorkspaceWindowController` (workspace registry, numbering, last-active tracking, Gmail intake routing, duplicate-target reservation map) |
| `src/legalpdf_translate/qt_gui/app_window.py` | `_FuturisticCanvas` (background/frame paint), `QtMainWindow` (`_build_ui`, `_apply_responsive_layout`, `_update_card_max_width`, `_refresh_lang_badge`, `_configure_footer_layout`, `_install_overflow_menu`) |
| `src/legalpdf_translate/qt_gui/styles.py` | `build_stylesheet()` (dashboard QSS), `PALETTE`, `apply_soft_shadow()`, `apply_primary_glow()` |
| `src/legalpdf_translate/qt_gui/dialogs.py` | `QtSettingsDialog`, `QtJobLogWindow`, `QtReviewQueueDialog`, `QtSaveToJobLogDialog` |
| `src/legalpdf_translate/qt_gui/tools_dialogs.py` | `QtGlossaryBuilderDialog`, `QtCalibrationAuditDialog` |

### Runtime launch contract
- Supported desktop launch: `python -m legalpdf_translate.qt_app`
- Detached Windows launch: `Start-Process .\.venv311\Scripts\pythonw.exe -ArgumentList '-m','legalpdf_translate.qt_app'`
- `python -m legalpdf_translate.qt_main` remains a compatibility shim, not the canonical command.

## B. objectName Conventions

| objectName | Widget Type | Purpose |
|-----------|-------------|---------|
| `RootWidget` | `_FuturisticCanvas` | painted dashboard scene/background |
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
| `PrimaryButton` | QPushButton | `Start Translate` CTA |
| `DangerButton` | QPushButton | `Cancel` CTA |
| `OverflowMenuButton` | QToolButton | `...` overflow menu trigger |
| `ActionRail` | QFrame | bottom action rail |
| `FooterMetaLabel` | QLabel | `Project v3.0 | LegalPDF` |

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
        └── QScrollArea [_scroll_area]
            └── QWidget [scroll_content]
                └── QVBoxLayout [scroll_layout]
                    └── QHBoxLayout [content_row_layout]
                        └── QWidget [content_card]
                            └── QVBoxLayout [card_shell_layout]
                                ├── QGridLayout [hero row]
                                │   ├── QLabel#HeroTitleLabel
                                │   └── QLabel#HeroStatusLabel
                                ├── QFrame#DashboardFrame
                                │   └── QVBoxLayout [dashboard_layout]
                                │       └── QFrame [main_card]
                                │           └── QVBoxLayout
                                │               ├── QBoxLayout [body_layout]
                                │               │   ├── QFrame#ShellPanel [setup_panel]
                                │               │   │   ├── setup_grid
                                │               │   │   ├── QToolButton#SectionToggleButton
                                │               │   │   ├── adv_frame
                                │               │   │   └── advisor_frame
                                │               │   └── QFrame#ShellPanel [progress_panel]
                                │               │       ├── QLabel#PanelHeading ("Conversion Output")
                                │               │       ├── summary row
                                │               │       ├── QProgressBar
                                │               │       ├── current-task row
                                │               │       ├── QFrame#MetricGridFrame
                                │               │       └── output format label
                                │               └── QFrame#ActionRail [footer_card]
                                │                   ├── Start Translate
                                │                   ├── Cancel
                                │                   └── ...
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

### 3. Sidebar geometry comes from `_apply_responsive_layout()`
- **What:** Sidebar width, nav widths, nav heights, icon sizes, and logo size must stay tied to the active size class.
- **Where:** `sidebar_width`, `nav_width`, `nav_height`, `icon_size`, `logo_size` values inside `_apply_responsive_layout()`.
- **Verify:** desktop exact shows readable `Dashboard`/`Recent Jobs`; stacked compact shrinks to icon-heavy chrome without overlap.

### 4. Content-card width is computed, then centered
- **What:** `content_card` uses a computed fixed width based on viewport space, then is centered with `content_row_layout`.
- **Where:** `_update_card_max_width()` sets `target_width = max(360, min(1760, available))` and `content_card.setFixedWidth(target_width)`.
- **Verify:** large windows use most of the available width without horizontal scroll; shell remains centered.

### 5. Paint layer must read live geometry
- **What:** `_FuturisticCanvas.paintEvent()` must derive sidebar separator placement from the actual sidebar width, not stale constants.
- **Where:** `sidebar = getattr(window, "sidebar_frame", None)` then `sidebar_line_x = sidebar.width()`.
- **Verify:** painted sidebar divider stays aligned while resizing across layout modes.

### 6. Desktop metrics grid contract
- **What:** Desktop grid shows `Pages`, `Images`, `Errors`, and a `Retries` heading only.
- **Where:** `_build_ui()` metric grid; `metric_retry_header_label` remains, row-level retry cells are not added to the layout.
- **Verify:** no per-row retry counts are visible in the desktop grid, even though retry tracking still exists internally.

### 7. Target-language badge contract
- **What:** Show one language code and one matching flag only.
- **Where:** `_LANG_FLAG_ICON_BY_CODE` and `_refresh_lang_badge()`.
- **Behavior:** if a flag asset is missing, hide the flag widget instead of duplicating text.
- **Verify:** switching `EN`, `FR`, `AR` shows one code, one flag, and no repeated fallback text.

### 8. Small-window layout is intentionally different
- **What:** `stacked_compact` is not a broken desktop shell; it is a deliberate mobile-like adaptation.
- **Where:** `_apply_responsive_layout()` changes `body_layout` direction to `TopToBottom` and calls `_configure_footer_layout(compact=True)`.
- **Verify:** setup panel above output panel; `Start Translate` on row 1; `Cancel` and `...` on row 2.

### 9. Run-critical selectors use no-wheel guards
- **What:** Translation-critical combo boxes ignore mouse-wheel changes when closed, and the workers spin box ignores wheel changes entirely.
- **Where:** `qt_gui/guarded_inputs.py`, `QtMainWindow` run controls, and matching settings-dialog controls.
- **Verify:** scrolling over a closed target-language, effort, OCR, image, or workers control does not silently change the value; opening the combo popup still allows intentional list scrolling.

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

### Change output actions
- Edit `_install_overflow_menu()` for `...` menu items.
- Review Queue and Save to Job Log remain top-menu actions in `_install_menu()`.

### Change field icons or language flags
- Update assets under `resources/icons/dashboard/`.
- Update `_LANG_FLAG_ICON_BY_CODE` when adding a new supported UI flag.

### Change progress-grid presentation
- Edit the metric-grid section in `_build_ui()` and the data population logic in `_apply_dashboard_snapshot()` / `_refresh_dashboard_counters()`.
- Keep the heading-only retries presentation unless the visual contract changes intentionally.

## F. How to Verify

### Automated

```bash
python -m pytest -q
python -m compileall src tests
```

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
9. Scroll over the closed run-critical selectors and confirm they do not change by accident
10. Trigger the EN/FR xhigh warning and confirm `Switch to fixed high` changes the current effort policy
11. Trigger the OCR-heavy warning and confirm `Apply safe OCR profile` changes the current run only
12. Open `File > New Window` or press `Ctrl+Shift+N` and confirm a second top-level window appears with the next `Workspace N` title
13. Start a run in one workspace and confirm another workspace stays usable while it is busy
14. Configure the same source file, target language, and output folder in two workspaces and confirm the second start is blocked as duplicate run-folder reuse
15. If Gmail intake is enabled, confirm intake reuses an idle blank workspace first and opens a new workspace when the last active one is busy or already has job context
