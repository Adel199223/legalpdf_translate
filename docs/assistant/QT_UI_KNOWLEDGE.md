# Qt UI Knowledge Pack

## A. Entry Points and File Map

| File | Key Classes / Functions |
|------|----------------------|
| `src/legalpdf_translate/qt_gui/app_window.py` | `_FuturisticCanvas` (paintEvent — decorative frame), `QtMainWindow` (_build_ui, resizeEvent, showEvent, _update_card_max_width, `_start`, `_start_analyze`, `_start_queue`, `_refresh_advisor_banner`, `_open_review_queue_dialog`) |
| `src/legalpdf_translate/qt_gui/styles.py` | `build_stylesheet()` (full QSS), `PALETTE` dict, `apply_soft_shadow()`, `apply_primary_glow()` |
| `src/legalpdf_translate/qt_gui/dialogs.py` | `QtSettingsDialog` (launched via `QtMainWindow._open_settings_dialog`) |
| `src/legalpdf_translate/qt_gui/tools_dialogs.py` | `QtGlossaryBuilderDialog`, `QtCalibrationAuditDialog` (launched via main window toolbar buttons) |

### objectName conventions

| objectName | Widget Type | Styled By |
|-----------|-------------|-----------|
| `RootWidget` | `_FuturisticCanvas` (QWidget) | `QWidget#RootWidget` — transparent background, font family |
| `GlassCard` | QFrame (content_card) | `QFrame#GlassCard` — dark card background, rounded border |
| `HeaderStrip` | QFrame | `QFrame#HeaderStrip` — gradient header bar |
| `SurfacePanel` | QFrame (main_card, adv_frame, details_card, footer_card) | `QFrame#SurfacePanel` — darker panel background |
| `PrimaryButton` | QPushButton (Translate) | `QPushButton#PrimaryButton` — cyan fill, dark text |
| `DangerButton` | QPushButton (Cancel) | `QPushButton#DangerButton` — red border |
| `TitleLabel` | QLabel | `QLabel#TitleLabel` — large accent-colored title |
| `MutedLabel` | QLabel | `QLabel#MutedLabel` — subdued text |
| `PathLabel` | QLabel | `QLabel#PathLabel` — accent status text |
| `DisclosureButton` | QToolButton (Show details) | `QToolButton#DisclosureButton` — transparent, accent text |
| `GlossaryTableCombo` | QComboBox (Match / Source lang / Tier in glossary table) | `QComboBox#GlossaryTableCombo` — compact padding (`2px 4px`), smaller border-radius (`4px`) for in-table fit |

## B. Layout Tree

```
QtMainWindow
└── _FuturisticCanvas  [centralWidget, objectName="RootWidget"]
    │   paintEvent draws: gradient background, top bar, decorative frame,
    │   corner accents, sweep line
    │
    └── QVBoxLayout [outer]  margins=_FRAME_INSETS  spacing=0
        └── QScrollArea [_scroll_area]
            │   NoFrame, widgetResizable=True, transparent
            │   horizontalScrollBarPolicy = AlwaysOff
            │
            └── QWidget [scroll_content]  transparent
                └── QVBoxLayout [scroll_layout]  margins=(18,14,18,6)  spacing=0
                    ├── stretch(1)
                    ├── QFrame#GlassCard [content_card]
                    │   maxWidth=1180, sizePolicy=(Expanding, Preferred)
                    │   AlignHCenter, soft shadow (blur=66, offset_y=16)
                    │   │
                    │   └── QVBoxLayout [card_shell]  margins=(18,16,18,16) spacing=10
                    │       ├── QFrame#HeaderStrip  [header_strip]
                    │       │   └── QHBoxLayout: TitleLabel + StatusHeaderLabel
                    │       │
                    │       ├── QFrame#SurfacePanel [main_card]
                    │       │   └── QVBoxLayout → QGridLayout (PDF/lang/outdir rows + tools)
                    │       │
                    │       ├── QFrame#SurfacePanel [adv_frame]  (hidden by default)
                    │       │   └── QFormLayout (effort/images/OCR/pages/workers/context/analyze/queue controls)
                    │       │       Includes: Analyze button, queue manifest picker,
                    │       │       rerun-failed-only checkbox, Run Queue button, Queue status label
                    │       │
                    │       ├── QFrame#SurfacePanel [advisor_frame]
                    │       │   └── QHBoxLayout: Advisor label + Apply + Ignore
                    │       │
                    │       ├── QFrame#SurfacePanel [details_card]
                    │       │   └── QVBoxLayout: DisclosureButton + log QPlainTextEdit
                    │       │
                    │       └── QFrame#SurfacePanel [footer_card]  LTR forced
                    │           └── QVBoxLayout: Final DOCX row, progress bar,
                    │               status labels, QGridLayout [btn_grid]:
                    │               Row 0: Translate | Cancel | New Run | Export partial DOCX | Rebuild DOCX
                    │               Row 1: Open output folder | Export Run Report | Review Queue | Save to Job Log | Job Log
                    │
                    └── stretch(1)
```

## C. UI Invariants

### 1. Painted Frame ↔ Layout Margins (CRITICAL)

- **What:** The decorative outer frame drawn in `_FuturisticCanvas.paintEvent` and the outer layout margins that position the scroll area MUST use the same inset values.
- **Where:**
  - `_FRAME_INSETS = (16, 96, 16, 18)` — module-level constant in `app_window.py`
  - `paintEvent`: `frame_rect = rect.adjusted(_l, _t, -_r, -_b)` (unpacks `_FRAME_INSETS`)
  - `_build_ui`: `outer.setContentsMargins(*_FRAME_INSETS)`
- **How to verify:** Launch app → the content card should sit visually inside the painted rounded frame with uniform padding.
- **What breaks it:** Changing any value in paintEvent without updating the margins (or vice versa). Using `_FRAME_INSETS` prevents this.

### 2. Card Centering

- **What:** The content card is horizontally centered and vertically padded within the scroll area.
- **Where:**
  - `scroll_layout.addWidget(content_card, 0, Qt.AlignmentFlag.AlignHCenter)` — horizontal centering
  - `scroll_layout.addStretch(1)` above and below — vertical centering
  - `content_card.setMaximumWidth(1180)` + `_update_card_max_width()` — responsive width
- **How to verify:** Resize window → card stays centered. Maximize → card doesn't stretch beyond 1180px.
- **What breaks it:** Removing AlignHCenter, removing either stretch, or setting a fixed width instead of max.

### 3. Responsiveness

- **What:** Window adapts to any display size without hard-coded dimensions.
- **Where:**
  - `setMinimumSize(720, 540)` in `__init__`
  - `showEvent`: sizes to 92% of available screen area on first show
  - `_update_card_max_width()` in `resizeEvent`: `max(600, min(1180, viewport - margins))`
- **How to verify:** Launch on different display sizes → window fits screen, card adapts.
- **What breaks it:** Adding a hard-coded `resize()` call, or setting a fixed card width.

### 4. No Horizontal Overflow

- **What:** Users must never be able to scroll horizontally (which would clip button labels).
- **Where:**
  - `_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)`
  - `_update_card_max_width()` caps card width to viewport
- **How to verify:** Launch app → no horizontal scrollbar at any window size.
- **What breaks it:** Removing the scroll bar policy, or letting content exceed viewport width.

### 5. Footer Button Labels

- **What:** All 10 footer buttons must show complete labels (no truncation).
- **Where:** `_build_ui` creates a QGridLayout with 2 rows:
  - Row 0 (5 buttons): Translate, Cancel, New Run, Export partial DOCX, Rebuild DOCX
  - Row 1 (5 buttons): Open output folder, Export Run Report, Review Queue, Save to Job Log, Job Log
  - `btn_grid.setColumnStretch(len(row0), 1)` pushes content left
  - `btn.setToolTip(btn.text())` on each button
- **How to verify:** All labels fully readable at default window width.
- **What breaks it:** Adding buttons without adjusting the row split, or using a single row for many buttons.

### 6. Layout Direction (LTR)

- **What:** UI chrome always renders left-to-right regardless of target translation language.
- **Where:**
  - `self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)` in `__init__`
  - `self.footer_card.setLayoutDirection(Qt.LayoutDirection.LeftToRight)` in `_build_ui`
- **How to verify:** Select AR target language → buttons still appear in expected LTR order.
- **What breaks it:** Removing the direction overrides, or setting a global RTL policy.

## D. How to Change X

### Change decorative frame thickness/margins

Edit the `_FRAME_INSETS` tuple in `app_window.py`. Both paintEvent and outer layout margins read from it, so they stay in sync.

### Change content card max width

Edit the `1180` value in both:
1. `self.content_card.setMaximumWidth(1180)` in `_build_ui`
2. `min(1180, available)` in `_update_card_max_width()`

### Change footer buttons

Edit the `row0` and `row1` lists in `_build_ui`. Keep the QGridLayout pattern with `setColumnStretch` on the column after the last button. Remember to add `setToolTip(btn.text())` on any new button.

### Change advisor or queue controls

Edit `_build_ui` in `app_window.py`:
1. Queue controls live in `adv_frame`.
2. The advisor banner lives in `advisor_frame`.
3. Queue behavior wiring lives in `_start_queue()`, `_on_queue_status()`, and `_on_queue_finished()`.

### Improve primary button contrast

1. Edit `QPushButton#PrimaryButton` section in `build_stylesheet()` in `styles.py` (border width, color, background)
2. Edit `apply_primary_glow()` in `styles.py` (glow color and blur radius)

### Change scroll layout inner margins

Edit `scroll_layout.setContentsMargins(18, 14, 18, 6)` in `_build_ui`. Left/right affect the effective card width floor (subtracted in `_update_card_max_width`). Top/bottom affect card vertical breathing room.

## E. How to Verify

### Automated

```bash
python -m pytest -q
python -m compileall src tests
```

### Manual smoke check

1. `python -m legalpdf_translate.qt_gui` — app launches without error
2. Resize window to various sizes → content card stays inside painted frame
3. Maximize → card centered, no horizontal scrollbar
4. Restore to normal size → card adapts
5. Check all footer button labels are fully readable
6. Toggle Show Advanced → card grows, vertical scrollbar appears if needed
7. Run Analyze on a difficult PDF → advisor banner appears when recommendation data exists
8. Finish a run with flagged pages → `Review Queue` button enables
9. Load a queue manifest in Advanced settings → `Run Queue` starts and status text updates
