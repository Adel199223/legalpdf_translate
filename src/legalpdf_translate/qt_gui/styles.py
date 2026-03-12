"""Styling helpers for the Qt GUI."""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsBlurEffect, QGraphicsDropShadowEffect, QWidget

_BASE_PALETTE = {
    "text": "#EFFCFF",
    "text_soft": "#DFF4FB",
    "muted": "#A7C9D7",
    "muted_soft": "#86AEBD",
    "accent": "#70F1FF",
    "accent_strong": "#47DCF4",
    "accent_soft": "#9EFBFF",
    "accent_hot": "#D9FFFF",
    "danger": "#F1A1A7",
    "danger_strong": "#F7B0B6",
    "line": "rgba(142, 239, 255, 166)",
    "card": "rgba(8, 30, 60, 168)",
    "surface_alt": "rgba(10, 35, 66, 182)",
    "surface_panel": "rgba(10, 33, 60, 148)",
    "field": "rgba(5, 20, 42, 220)",
    "field_focus": "rgba(14, 48, 82, 238)",
    "sidebar": "rgba(6, 20, 38, 188)",
    "dialog_bg": "rgba(5, 15, 31, 234)",
    "dialog_border": "rgba(136, 238, 255, 118)",
    "field_border": "rgba(118, 220, 242, 156)",
    "field_focus_border": "#8CFBFF",
    "scroll_track": "rgba(4, 14, 29, 200)",
    "scroll_handle": "rgba(138, 214, 235, 138)",
    "scroll_handle_hover": "rgba(155, 228, 245, 194)",
    "button_bg": "rgba(9, 40, 72, 220)",
    "button_hover": "rgba(18, 64, 101, 232)",
    "button_pressed": "rgba(12, 51, 86, 236)",
    "button_border": "rgba(133, 228, 244, 164)",
    "group_title": "#9EFBFF",
    "table_header_bg": "rgba(16, 48, 78, 214)",
    "table_header_border": "rgba(128, 225, 245, 126)",
    "selection": "rgba(55, 173, 210, 220)",
    "menubar_bg": "rgba(66, 48, 34, 154)",
    "menubar_hover": "rgba(106, 79, 54, 196)",
    "menu_bg": "rgba(7, 22, 42, 244)",
    "menu_hover": "rgba(24, 98, 126, 214)",
    "menu_separator": "rgba(141, 234, 248, 112)",
    "shell_border": "rgba(138, 245, 255, 188)",
    "panel_border": "rgba(124, 234, 255, 136)",
    "field_shell_border": "rgba(124, 234, 255, 148)",
    "metric_border": "rgba(121, 228, 250, 128)",
    "action_rail_border": "rgba(137, 244, 255, 172)",
    "primary_fill": "rgba(130, 240, 255, 238)",
    "primary_fill_hover": "rgba(160, 245, 255, 244)",
    "primary_fill_pressed": "rgba(114, 228, 244, 236)",
    "primary_text": "#08212B",
    "primary_border": "rgba(214, 252, 255, 248)",
    "danger_fill": "rgba(236, 154, 160, 238)",
    "danger_fill_hover": "rgba(244, 175, 180, 244)",
    "danger_fill_disabled": "rgba(92, 50, 56, 124)",
    "danger_border": "rgba(255, 210, 214, 188)",
}

_THEME_OVERRIDES = {
    "dark_simple": {
        "text_soft": "#E0EDF3",
        "muted": "#A7BBC6",
        "muted_soft": "#869CA9",
        "accent": "#6CD8F0",
        "accent_strong": "#54C8E2",
        "accent_soft": "#B4E9F5",
        "accent_hot": "#E7F7FC",
        "line": "rgba(134, 176, 192, 112)",
        "card": "rgba(11, 16, 24, 212)",
        "surface_alt": "rgba(12, 18, 27, 220)",
        "surface_panel": "rgba(12, 18, 27, 196)",
        "field": "rgba(7, 11, 17, 236)",
        "field_focus": "rgba(14, 24, 35, 244)",
        "sidebar": "rgba(11, 15, 22, 224)",
        "dialog_bg": "rgba(10, 15, 24, 242)",
        "dialog_border": "rgba(142, 176, 194, 92)",
        "field_border": "rgba(108, 148, 164, 132)",
        "field_focus_border": "#C3E9F5",
        "scroll_track": "rgba(10, 15, 23, 212)",
        "scroll_handle": "rgba(114, 150, 166, 132)",
        "scroll_handle_hover": "rgba(145, 186, 201, 182)",
        "button_bg": "rgba(18, 30, 42, 232)",
        "button_hover": "rgba(26, 40, 55, 238)",
        "button_pressed": "rgba(20, 31, 43, 242)",
        "button_border": "rgba(108, 145, 162, 142)",
        "group_title": "#D4EEF7",
        "table_header_bg": "rgba(20, 29, 40, 220)",
        "table_header_border": "rgba(114, 146, 161, 100)",
        "selection": "rgba(88, 146, 169, 194)",
        "menubar_bg": "rgba(35, 34, 35, 170)",
        "menubar_hover": "rgba(54, 57, 60, 208)",
        "menu_bg": "rgba(10, 15, 24, 242)",
        "menu_hover": "rgba(38, 67, 86, 214)",
        "menu_separator": "rgba(132, 170, 186, 94)",
        "shell_border": "rgba(148, 188, 204, 132)",
        "panel_border": "rgba(126, 167, 184, 108)",
        "field_shell_border": "rgba(120, 161, 178, 118)",
        "metric_border": "rgba(120, 160, 178, 104)",
        "action_rail_border": "rgba(130, 172, 188, 128)",
        "primary_fill": "rgba(170, 219, 230, 218)",
        "primary_fill_hover": "rgba(188, 231, 240, 226)",
        "primary_fill_pressed": "rgba(153, 205, 218, 220)",
        "primary_text": "#10222B",
        "primary_border": "rgba(221, 241, 247, 220)",
        "danger_fill": "rgba(196, 136, 142, 218)",
        "danger_fill_hover": "rgba(206, 150, 155, 224)",
        "danger_fill_disabled": "rgba(82, 54, 58, 118)",
        "danger_border": "rgba(222, 189, 194, 160)",
    },
}

_BASE_EFFECT_TOKENS: dict[str, tuple[int, int, int, int]] = {
    "title_glow": (120, 246, 255, 214),
    "dashboard_shadow": (18, 98, 134, 186),
    "panel_shadow": (7, 48, 80, 176),
    "advisor_shadow": (10, 58, 92, 166),
    "details_shadow": (8, 42, 70, 160),
    "footer_glow": (112, 236, 255, 196),
    "primary_glow": (132, 242, 255, 216),
}

_THEME_EFFECT_OVERRIDES: dict[str, Mapping[str, tuple[int, int, int, int]]] = {
    "dark_simple": {
        "title_glow": (164, 218, 228, 124),
        "dashboard_shadow": (24, 42, 56, 168),
        "panel_shadow": (18, 32, 44, 156),
        "advisor_shadow": (20, 34, 46, 148),
        "details_shadow": (18, 30, 42, 146),
        "footer_glow": (120, 168, 182, 142),
        "primary_glow": (164, 214, 226, 154),
    },
}

_BODY_FONT_STACK = '"Segoe UI Variable", "Segoe UI", "Corbel", "Calibri", "DejaVu Sans", "Arial"'
_HEADING_FONT_STACK = '"Candara", "Segoe UI Variable", "Segoe UI Semibold", "Corbel", "Segoe UI", "DejaVu Sans", "Arial"'
_SECTION_HEADING_FONT_STACK = '"Segoe UI Variable", "Candara", "Segoe UI Semibold", "Corbel", "Segoe UI", "DejaVu Sans", "Arial"'


def normalize_ui_theme(theme: str | None) -> str:
    value = str(theme or "").strip().lower()
    return value if value in {"dark_futuristic", "dark_simple"} else "dark_futuristic"


def theme_palette(theme: str | None) -> dict[str, str]:
    normalized = normalize_ui_theme(theme)
    palette = dict(_BASE_PALETTE)
    palette.update(_THEME_OVERRIDES.get(normalized, {}))
    return palette


def _rgba_to_qcolor(value: tuple[int, int, int, int]) -> QColor:
    red, green, blue, alpha = value
    return QColor(int(red), int(green), int(blue), int(alpha))


def theme_effect_colors(theme: str | None) -> dict[str, QColor]:
    normalized = normalize_ui_theme(theme)
    tokens = dict(_BASE_EFFECT_TOKENS)
    tokens.update(_THEME_EFFECT_OVERRIDES.get(normalized, {}))
    return {key: _rgba_to_qcolor(value) for key, value in tokens.items()}


def build_stylesheet(theme: str = "dark_futuristic") -> str:
    PALETTE = theme_palette(theme)
    return f"""
    QWidget {{
        color: {PALETTE['text']};
        font-family: {_BODY_FONT_STACK};
        font-size: 12pt;
    }}

    QWidget#RootWidget {{
        background: transparent;
    }}

    QWidget#ContentCard,
    QWidget#ShellScrollContent,
    QWidget#DialogScrollContent {{
        background: transparent;
    }}

    QScrollArea#ShellScrollArea,
    QScrollArea#DialogScrollArea {{
        background: transparent;
        border: none;
    }}

    QDialog, QMessageBox {{
        background-color: {PALETTE['dialog_bg']};
        color: {PALETTE['text']};
        border: 1px solid {PALETTE['dialog_border']};
        border-radius: 22px;
    }}

    QMenuBar {{
        background: {PALETTE['menubar_bg']};
        color: {PALETTE['text']};
        padding: 2px 10px;
    }}

    QMenuBar::item {{
        background: transparent;
        padding: 6px 10px;
        border-radius: 6px;
    }}

    QMenuBar::item:selected {{
        background: {PALETTE['menubar_hover']};
    }}

    QMenu {{
        background-color: {PALETTE['menu_bg']};
        color: {PALETTE['text']};
        border: 1px solid {PALETTE['dialog_border']};
        border-radius: 18px;
        padding: 12px;
    }}

    QMenu::item {{
        padding: 12px 20px 12px 40px;
        border-radius: 12px;
        margin: 2px 0;
    }}

    QMenu::item:selected {{
        background: {PALETTE['menu_hover']};
    }}

    QMenu::separator {{
        height: 1px;
        margin: 6px 10px;
        background: {PALETTE['menu_separator']};
    }}

    QFrame#SidebarPanel {{
        background-color: {PALETTE['sidebar']};
        border-right: 1px solid rgba(132, 241, 255, 102);
    }}

    QLabel#SidebarLogoLabel {{
        color: {PALETTE['accent_soft']};
        font-size: 28pt;
        font-weight: 700;
    }}

    QLabel#SidebarCaption {{
        color: {PALETTE['muted_soft']};
        font-size: 9.5pt;
        font-weight: 500;
    }}

    QToolButton#SidebarNavButton {{
        color: rgba(226, 249, 255, 216);
        background: transparent;
        border: 1px solid transparent;
        border-left: 4px solid transparent;
        border-radius: 20px;
        padding: 12px 10px 14px 10px;
        font-size: 10.2pt;
        font-weight: 500;
    }}

    QToolButton#SidebarNavButton:hover {{
        background: rgba(20, 83, 116, 164);
        border-color: rgba(117, 240, 255, 118);
    }}

    QToolButton#SidebarNavButton[navRole=\"active\"] {{
        background: rgba(24, 110, 138, 190);
        border-color: rgba(142, 245, 255, 172);
        border-left: 4px solid {PALETTE['accent']};
        color: {PALETTE['accent_hot']};
    }}

    QToolButton#SidebarNavButton[comingSoon=\"true\"] {{
        color: rgba(184, 213, 229, 154);
    }}

    QLabel#HeroTitleLabel {{
        color: {PALETTE['accent_soft']};
        font-family: {_HEADING_FONT_STACK};
        font-size: 30pt;
        font-weight: 600;
        letter-spacing: 0.82px;
    }}

    QLabel#HeroStatusLabel {{
        color: rgba(182, 239, 255, 228);
        font-family: {_SECTION_HEADING_FONT_STACK};
        font-size: 12.6pt;
        font-weight: 500;
        letter-spacing: 0.24px;
    }}

    QFrame#DashboardFrame {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 rgba(255, 255, 255, 16),
            stop:0.10 {PALETTE['card']},
            stop:0.72 {PALETTE['surface_alt']},
            stop:1 rgba(5, 22, 46, 228)
        );
        border: 1px solid {PALETTE['shell_border']};
        border-radius: 28px;
    }}

    QFrame#ShellPanel {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 rgba(255, 255, 255, 18),
            stop:0.14 {PALETTE['surface_panel']},
            stop:1 rgba(6, 24, 46, 226)
        );
        border: 1px solid {PALETTE['panel_border']};
        border-radius: 20px;
    }}

    QLabel#PanelHeading {{
        color: {PALETTE['accent_soft']};
        font-family: {_SECTION_HEADING_FONT_STACK};
        font-size: 18.9pt;
        font-weight: 600;
        letter-spacing: 0.28px;
    }}

    QLabel#FieldLabel {{
        color: rgba(236, 249, 255, 224);
        font-family: {_SECTION_HEADING_FONT_STACK};
        font-size: 12pt;
        font-weight: 600;
        letter-spacing: 0.16px;
    }}

    QFrame#FieldChrome {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 rgba(255, 255, 255, 18),
            stop:0.16 rgba(10, 29, 51, 192),
            stop:1 rgba(5, 20, 40, 228)
        );
        border: 1px solid {PALETTE['field_shell_border']};
        border-radius: 16px;
    }}

    QFrame#InlineDivider {{
        background: rgba(136, 241, 255, 62);
        border: none;
        min-width: 1px;
        max-width: 1px;
    }}

    QLineEdit[embeddedField=\"true\"],
    QComboBox[embeddedField=\"true\"] {{
        background: transparent;
        border: none;
        padding: 8px 0;
        color: {PALETTE['text']};
        font-family: {_BODY_FONT_STACK};
        font-size: 12.15pt;
        font-weight: 520;
        letter-spacing: 0.08px;
        selection-background-color: rgba(35, 138, 185, 220);
    }}

    QLineEdit[embeddedField=\"true\"]:focus,
    QComboBox[embeddedField=\"true\"]:focus {{
        background: transparent;
        border: none;
    }}

    QComboBox[embeddedField=\"true\"]::drop-down {{
        border: none;
        width: 0px;
    }}

    QComboBox[embeddedField=\"true\"]::down-arrow {{
        width: 0px;
        height: 0px;
    }}

    QComboBox[langField=\"true\"] {{
        padding: 8px 2px;
        min-width: 46px;
        color: rgba(238, 251, 255, 236);
        font-family: {_SECTION_HEADING_FONT_STACK};
        font-size: 11.4pt;
        font-weight: 600;
        letter-spacing: 0.12px;
    }}

    QFrame#FieldChrome[sharedChromeCombo=\"true\"][hovered=\"true\"],
    QFrame#FieldChrome[sharedChromeCombo=\"true\"][focused=\"true\"],
    QFrame#FieldChrome[sharedChromeCombo=\"true\"][popupOpen=\"true\"],
    QFrame#FieldChrome[sharedChromeDate=\"true\"][hovered=\"true\"],
    QFrame#FieldChrome[sharedChromeDate=\"true\"][focused=\"true\"],
    QFrame#FieldChrome[sharedChromeDate=\"true\"][popupOpen=\"true\"] {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 rgba(255, 255, 255, 18),
            stop:0.16 rgba(8, 31, 62, 198),
            stop:1 rgba(4, 16, 31, 238)
        );
        border: 1px solid {PALETTE['field_focus_border']};
    }}

    QLabel#FlagLabel {{
        background: transparent;
        border: none;
    }}

    QLabel#FieldSupportLabel {{
        color: rgba(216, 240, 248, 214);
        font-family: {_BODY_FONT_STACK};
        font-size: 10.7pt;
        font-weight: 520;
        letter-spacing: 0.06px;
    }}

    QLabel#FieldValueLabel {{
        color: rgba(238, 251, 255, 236);
        font-family: {_BODY_FONT_STACK};
        font-size: 11.3pt;
        font-weight: 560;
        letter-spacing: 0.08px;
    }}

    QLabel#FieldValueLabel[accent=\"true\"] {{
        color: {PALETTE['accent_soft']};
    }}

    QToolButton#FieldBrowseButton {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 rgba(255, 255, 255, 22),
            stop:0.22 {PALETTE['button_bg']},
            stop:1 rgba(9, 36, 62, 244)
        );
        border: 1px solid rgba(132, 239, 255, 166);
        border-radius: 12px;
        padding: 8px;
    }}

    QToolButton#FieldBrowseButton:hover {{
        background-color: {PALETTE['button_hover']};
    }}

    QToolButton#LangCaretButton {{
        background: transparent;
        border: none;
        padding: 0 2px;
        min-width: 18px;
    }}

    QToolButton#LangCaretButton:hover {{
        background: transparent;
    }}

    QToolButton#LangCaretButton[hovered=\"true\"],
    QToolButton#LangCaretButton[focused=\"true\"],
    QToolButton#LangCaretButton[popupOpen=\"true\"] {{
        color: {PALETTE['accent_soft']};
    }}

    QToolButton#DatePickerButton {{
        background: transparent;
        border: none;
        min-width: 18px;
        padding: 0 2px;
        color: rgba(226, 249, 255, 218);
    }}

    QToolButton#DatePickerButton:hover {{
        background: transparent;
        color: {PALETTE['accent_soft']};
    }}

    QToolButton#SectionToggleButton {{
        color: rgba(229, 247, 255, 228);
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 rgba(255, 255, 255, 14),
            stop:0.22 {PALETTE['button_bg']},
            stop:1 rgba(6, 24, 43, 238)
        );
        border: 1px solid rgba(116, 231, 255, 128);
        border-radius: 16px;
        padding: 12px 15px;
        font-family: {_SECTION_HEADING_FONT_STACK};
        font-size: 11.8pt;
        font-weight: 600;
        letter-spacing: 0.18px;
    }}

    QToolButton#SectionToggleButton:hover {{
        background-color: {PALETTE['button_hover']};
        border-color: {PALETTE['field_focus_border']};
    }}

    QLabel#ProgressSummaryLabel {{
        color: rgba(238, 251, 255, 230);
        font-family: {_SECTION_HEADING_FONT_STACK};
        font-size: 13.2pt;
        font-weight: 600;
        letter-spacing: 0.18px;
    }}

    QLabel#CurrentTaskLabel {{
        color: rgba(235, 247, 255, 214);
        font-family: {_BODY_FONT_STACK};
        font-size: 10.8pt;
        font-weight: 520;
        letter-spacing: 0.06px;
    }}

    QFrame#MetricGridFrame {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 rgba(255, 255, 255, 12),
            stop:0.14 rgba(9, 26, 46, 164),
            stop:1 rgba(5, 20, 39, 216)
        );
        border: 1px solid {PALETTE['metric_border']};
        border-radius: 18px;
    }}

    QFrame#MetricCell {{
        background: transparent;
        border: none;
    }}

    QLabel#MetricTitle {{
        color: rgba(227, 244, 252, 214);
        font-family: {_SECTION_HEADING_FONT_STACK};
        font-size: 11pt;
        font-weight: 600;
        letter-spacing: 0.14px;
    }}

    QLabel#MetricValue {{
        color: rgba(240, 250, 255, 236);
        font-family: {_BODY_FONT_STACK};
        font-size: 13pt;
        font-weight: 560;
        letter-spacing: 0.06px;
    }}

    QLabel#MetricRetryValue {{
        color: rgba(222, 242, 250, 216);
        font-family: {_BODY_FONT_STACK};
        font-size: 12pt;
        font-weight: 540;
        letter-spacing: 0.05px;
    }}

    QFrame#RetryBadge {{
        background: transparent;
        border: none;
    }}

    QLabel#OutputFormatLabel {{
        color: rgba(219, 241, 251, 218);
        font-family: {_SECTION_HEADING_FONT_STACK};
        font-size: 12pt;
        font-weight: 600;
        letter-spacing: 0.12px;
    }}

    QLabel#FooterMetaLabel {{
        color: rgba(191, 224, 238, 186);
        font-family: {_BODY_FONT_STACK};
        font-size: 10.5pt;
        font-weight: 520;
        letter-spacing: 0.04px;
    }}

    QFrame#ActionRail {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 rgba(255, 255, 255, 14),
            stop:0.15 rgba(9, 30, 52, 162),
            stop:1 rgba(6, 22, 40, 226)
        );
        border: 1px solid {PALETTE['action_rail_border']};
        border-radius: 20px;
    }}

    QWidget#DialogActionBar {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 rgba(255, 255, 255, 10),
            stop:0.18 rgba(8, 24, 42, 176),
            stop:1 rgba(5, 17, 31, 220)
        );
        border: 1px solid rgba(108, 222, 244, 98);
        border-radius: 16px;
    }}

    QToolButton#OverflowMenuButton {{
        background-color: rgba(8, 30, 55, 228);
        color: {PALETTE['text']};
        border: 1px solid rgba(136, 239, 255, 166);
        border-radius: 14px;
        padding: 0 14px 4px 14px;
        font-size: 17pt;
        font-weight: 700;
        min-width: 84px;
    }}

    QToolButton#OverflowMenuButton:hover {{
        background-color: rgba(16, 53, 84, 242);
    }}

    QFrame#HiddenUtilityPanel {{
        background: transparent;
        border: none;
    }}

    QFrame#HeaderStrip {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(8, 36, 66, 198),
            stop:0.5 rgba(11, 52, 88, 228),
            stop:1 rgba(8, 36, 66, 198)
        );
        border: 1px solid rgba(120, 214, 255, 146);
        border-radius: 16px;
    }}

    QLabel#TitleLabel {{
        color: {PALETTE['accent']};
        font-size: 23pt;
        font-weight: 700;
        letter-spacing: 0.6px;
    }}

    QLabel#StatusHeaderLabel {{
        color: #B6EFFF;
        font-size: 11.5pt;
        font-weight: 600;
    }}

    QLabel#SectionTitle {{
        color: {PALETTE['accent']};
        font-size: 10.5pt;
        font-weight: 600;
    }}

    QLabel#MutedLabel {{
        color: {PALETTE['muted']};
    }}

    QLabel#PathLabel {{
        color: {PALETTE['accent']};
        font-size: 10pt;
        font-weight: 600;
    }}

    QFrame#SurfacePanel {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 rgba(255, 255, 255, 10),
            stop:0.16 {PALETTE['surface_panel']},
            stop:1 rgba(4, 15, 28, 220)
        );
        border: 1px solid rgba(114, 193, 227, 108);
        border-radius: 18px;
    }}

    QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox {{
        background-color: {PALETTE['field']};
        color: {PALETTE['text']};
        border: 1px solid {PALETTE['field_border']};
        border-radius: 12px;
        padding: 8px 10px;
        selection-background-color: {PALETTE['selection']};
    }}

    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
        border: 1px solid {PALETTE['field_focus_border']};
        background-color: {PALETTE['field_focus']};
    }}

    QComboBox[sharedChromeCombo=\"true\"][hovered=\"true\"],
    QComboBox[sharedChromeCombo=\"true\"][focused=\"true\"],
    QComboBox[sharedChromeCombo=\"true\"][popupOpen=\"true\"] {{
        border: 1px solid {PALETTE['field_focus_border']};
        background-color: {PALETTE['field_focus']};
    }}

    QComboBox[sharedChromeCombo=\"true\"][embeddedField=\"true\"][hovered=\"true\"],
    QComboBox[sharedChromeCombo=\"true\"][embeddedField=\"true\"][focused=\"true\"],
    QComboBox[sharedChromeCombo=\"true\"][embeddedField=\"true\"][popupOpen=\"true\"] {{
        border: none;
        background: transparent;
    }}

    QFrame#CalendarPopup {{
        background: {PALETTE['dialog_bg']};
        border: 1px solid {PALETTE['dialog_border']};
        border-radius: 16px;
    }}

    QCalendarWidget#CalendarPopupWidget {{
        background: transparent;
        color: {PALETTE['text']};
    }}

    QCalendarWidget#CalendarPopupWidget QWidget#qt_calendar_navigationbar {{
        background: transparent;
        border: none;
    }}

    QCalendarWidget#CalendarPopupWidget QToolButton {{
        background-color: {PALETTE['button_bg']};
        color: {PALETTE['text']};
        border: 1px solid {PALETTE['button_border']};
        border-radius: 10px;
        padding: 4px 10px;
        font-family: {_SECTION_HEADING_FONT_STACK};
        font-weight: 600;
    }}

    QCalendarWidget#CalendarPopupWidget QToolButton:hover {{
        background-color: {PALETTE['button_hover']};
    }}

    QCalendarWidget#CalendarPopupWidget QMenu {{
        background-color: rgba(4, 14, 29, 248);
    }}

    QCalendarWidget#CalendarPopupWidget QSpinBox {{
        min-width: 72px;
    }}

    QCalendarWidget#CalendarPopupWidget QAbstractItemView:enabled {{
        background: {PALETTE['dialog_bg']};
        color: {PALETTE['text']};
        selection-background-color: {PALETTE['selection']};
        selection-color: {PALETTE['accent_hot']};
    }}

    QCalendarWidget#CalendarPopupWidget QWidget {{
        alternate-background-color: transparent;
    }}

    QCalendarWidget#CalendarPopupWidget QTableView {{
        background: transparent;
        border: none;
        outline: none;
    }}

    QCalendarWidget#CalendarPopupWidget QTableView::item {{
        border-radius: 8px;
        padding: 4px;
    }}

    QCalendarWidget#CalendarPopupWidget QTableView::item:hover {{
        background: rgba(20, 83, 121, 212);
        color: {PALETTE['accent_hot']};
    }}

    QCalendarWidget#CalendarPopupWidget QTableView::item:selected {{
        background: {PALETTE['selection']};
        color: {PALETTE['accent_hot']};
    }}

    QComboBox#GlossaryTableCombo {{
        padding: 2px 6px;
        border-radius: 4px;
    }}

    QComboBox#GlossaryTableCombo::drop-down {{
        width: 18px;
    }}

    QComboBox::drop-down {{
        border-left: 1px solid {PALETTE['field_border']};
        width: 26px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {PALETTE['dialog_bg']};
        color: {PALETTE['text']};
        selection-background-color: {PALETTE['selection']};
        border: 1px solid {PALETTE['dialog_border']};
        outline: none;
        border-radius: 12px;
        padding: 6px;
    }}

    QComboBox QAbstractItemView::item {{
        padding: 8px 12px;
        border-radius: 8px;
        margin: 2px;
    }}

    QComboBox QAbstractItemView::item:hover {{
        background: rgba(20, 83, 121, 212);
        color: {PALETTE['accent_hot']};
    }}

    QComboBox QAbstractItemView::item:selected {{
        background: {PALETTE['selection']};
        color: {PALETTE['accent_hot']};
    }}

    QCheckBox {{
        spacing: 8px;
    }}

    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {PALETTE['field_border']};
        border-radius: 4px;
        background: rgba(4, 14, 29, 210);
    }}

    QCheckBox::indicator:checked {{
        background: {PALETTE['accent_strong']};
        border: 1px solid {PALETTE['accent']};
    }}

    QPushButton {{
        background-color: {PALETTE['button_bg']};
        color: {PALETTE['text']};
        border: 1px solid {PALETTE['button_border']};
        border-radius: 12px;
        padding: 0 16px;
        font-family: {_SECTION_HEADING_FONT_STACK};
        font-weight: 600;
        letter-spacing: 0.18px;
    }}

    QPushButton:hover {{
        border-color: {PALETTE['field_focus_border']};
        background-color: {PALETTE['button_hover']};
    }}

    QPushButton:pressed {{
        background-color: {PALETTE['button_pressed']};
    }}

    QPushButton:disabled {{
        color: rgba(151, 182, 206, 120);
        border-color: rgba(72, 104, 128, 110);
    }}

    QPushButton#PrimaryButton {{
        background-color: {PALETTE['primary_fill']};
        color: {PALETTE['primary_text']};
        border: 1px solid {PALETTE['primary_border']};
        font-family: {_SECTION_HEADING_FONT_STACK};
        font-weight: 700;
        border-radius: 14px;
        padding: 0 28px;
        font-size: 12pt;
        letter-spacing: 0.2px;
    }}

    QPushButton#PrimaryButton:default {{
        background-color: {PALETTE['primary_fill']};
        color: {PALETTE['primary_text']};
        border: 1px solid {PALETTE['primary_border']};
        border-radius: 14px;
    }}

    QPushButton#PrimaryButton:hover {{
        background-color: {PALETTE['primary_fill_hover']};
    }}

    QPushButton#PrimaryButton:default:hover {{
        background-color: {PALETTE['primary_fill_hover']};
    }}

    QPushButton#PrimaryButton:default:pressed {{
        background-color: {PALETTE['primary_fill_pressed']};
    }}

    QWidget#DialogActionBar QPushButton {{
        min-height: 34px;
    }}

    QWidget#DialogActionBar QPushButton#PrimaryButton {{
        border-radius: 18px;
        padding: 0 30px;
    }}

    QWidget#DialogActionBar QPushButton#PrimaryButton:default {{
        border-radius: 18px;
    }}

    QPushButton#DangerButton {{
        background-color: {PALETTE['danger_fill']};
        border-color: {PALETTE['danger_border']};
        color: #321115;
        border-radius: 14px;
        padding: 0 24px;
        font-family: {_SECTION_HEADING_FONT_STACK};
        font-size: 11.5pt;
        letter-spacing: 0.16px;
    }}

    QPushButton#PrimaryButton:disabled {{
        background-color: rgba(58, 88, 105, 112);
        border-color: rgba(146, 193, 207, 96);
        color: rgba(225, 242, 248, 146);
    }}

    QPushButton#DangerButton:disabled {{
        background-color: {PALETTE['danger_fill_disabled']};
        border-color: rgba(172, 112, 121, 110);
        color: rgba(228, 199, 205, 150);
    }}

    QPushButton#DangerButton:hover {{
        background-color: {PALETTE['danger_fill_hover']};
    }}

    QToolButton#OverflowMenuButton:disabled {{
        background-color: rgba(25, 37, 51, 168);
        border-color: rgba(106, 145, 162, 96);
        color: rgba(208, 226, 236, 150);
    }}

    QProgressBar {{
        background-color: rgba(7, 24, 44, 220);
        border: 1px solid rgba(134, 240, 255, 136);
        border-radius: 15px;
        min-height: 26px;
        padding: 2px;
        text-align: center;
        color: {PALETTE['text']};
    }}

    QProgressBar::chunk {{
        border-radius: 11px;
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 {PALETTE['accent_soft']},
            stop:1 {PALETTE['accent_strong']}
        );
    }}

    QToolButton#DisclosureButton {{
        color: {PALETTE['accent']};
        background: transparent;
        border: none;
        font-weight: 600;
        padding: 4px;
    }}

    QGroupBox {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 rgba(255, 255, 255, 8),
            stop:0.16 {PALETTE['surface_panel']},
            stop:1 rgba(4, 15, 28, 220)
        );
        border: 1px solid rgba(114, 193, 227, 108);
        border-radius: 18px;
        margin-top: 18px;
        padding: 16px 12px 12px 12px;
        font-weight: 600;
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 14px;
        padding: 0 6px;
        color: {PALETTE['group_title']};
        font-family: {_SECTION_HEADING_FONT_STACK};
        font-size: 12.3pt;
        font-weight: 600;
        letter-spacing: 0.18px;
    }}

    QTabWidget::pane {{
        background: rgba(6, 17, 34, 176);
        border: 1px solid rgba(108, 204, 230, 104);
        border-radius: 18px;
        margin-top: 10px;
    }}

    QTabBar::tab {{
        background: rgba(8, 24, 43, 170);
        border: 1px solid rgba(108, 204, 230, 104);
        border-bottom: none;
        color: {PALETTE['text_soft']};
        padding: 8px 14px;
        margin-right: 6px;
        border-top-left-radius: 12px;
        border-top-right-radius: 12px;
        min-width: 110px;
    }}

    QTabBar::tab:hover {{
        background: rgba(12, 39, 68, 198);
    }}

    QTabBar::tab:selected {{
        background: rgba(18, 83, 118, 212);
        border-color: rgba(126, 236, 255, 152);
        color: {PALETTE['accent_hot']};
    }}

    QTableWidget, QListWidget, QTreeWidget {{
        background: {PALETTE['field']};
        color: {PALETTE['text']};
        border: 1px solid {PALETTE['field_border']};
        border-radius: 12px;
        gridline-color: rgba(130, 182, 199, 52);
        selection-background-color: {PALETTE['selection']};
    }}

    QHeaderView::section {{
        background: {PALETTE['table_header_bg']};
        color: {PALETTE['text_soft']};
        border: 1px solid {PALETTE['table_header_border']};
        padding: 8px;
        font-weight: 600;
    }}

    QScrollBar:vertical {{
        background: {PALETTE['scroll_track']};
        width: 10px;
        border-radius: 5px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {PALETTE['scroll_handle']};
        border-radius: 4px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {PALETTE['scroll_handle_hover']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    QScrollBar:horizontal {{
        background: {PALETTE['scroll_track']};
        height: 10px;
        border-radius: 5px;
        margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: {PALETTE['scroll_handle']};
        border-radius: 4px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {PALETTE['scroll_handle_hover']};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: transparent;
    }}
    """


def apply_app_appearance(app: object, *, theme: str) -> str:
    normalized_theme = normalize_ui_theme(theme)
    stylesheet = build_stylesheet(normalized_theme)
    set_property = getattr(app, "setProperty", None)
    if callable(set_property):
        set_property("uiTheme", normalized_theme)
    set_stylesheet = getattr(app, "setStyleSheet", None)
    if callable(set_stylesheet):
        set_stylesheet(stylesheet)
    return stylesheet


def make_blur_effect(parent: QWidget, *, radius: int = 24) -> QGraphicsBlurEffect:
    effect = QGraphicsBlurEffect(parent)
    effect.setBlurRadius(float(radius))
    effect.setBlurHints(QGraphicsBlurEffect.QualityHint)
    return effect


def _coerce_effect_color(color: QColor | tuple[int, int, int, int] | None, *, fallback: tuple[int, int, int, int]) -> QColor:
    if isinstance(color, QColor):
        return QColor(color)
    if isinstance(color, tuple):
        return _rgba_to_qcolor(color)
    return _rgba_to_qcolor(fallback)


def apply_soft_shadow(
    widget: QWidget,
    *,
    blur_radius: int = 48,
    offset_y: int = 12,
    color: QColor | tuple[int, int, int, int] | None = None,
) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(float(blur_radius))
    effect.setOffset(0.0, float(offset_y))
    effect.setColor(_coerce_effect_color(color, fallback=(7, 26, 54, 146)))
    widget.setGraphicsEffect(effect)


def apply_primary_glow(
    widget: QWidget,
    *,
    blur_radius: int = 30,
    color: QColor | tuple[int, int, int, int] | None = None,
) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(float(blur_radius))
    effect.setOffset(0.0, 0.0)
    effect.setColor(_coerce_effect_color(color, fallback=(89, 232, 255, 146)))
    widget.setGraphicsEffect(effect)
