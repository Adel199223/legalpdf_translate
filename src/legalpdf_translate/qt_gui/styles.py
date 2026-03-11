"""Styling helpers for the Qt GUI."""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsBlurEffect, QGraphicsDropShadowEffect, QWidget

_BASE_PALETTE = {
    "text": "#EAF9FF",
    "text_soft": "#D6EEF8",
    "muted": "#9AB9CE",
    "muted_soft": "#7CA4B7",
    "accent": "#59E8FF",
    "accent_strong": "#2DD4F0",
    "accent_soft": "#8CF6FF",
    "accent_hot": "#C7FBFF",
    "danger": "#E98E98",
    "danger_strong": "#F39CA7",
    "line": "rgba(124, 232, 255, 140)",
    "card": "rgba(5, 18, 38, 176)",
    "surface_alt": "rgba(6, 21, 43, 182)",
    "surface_panel": "rgba(6, 19, 36, 142)",
    "field": "rgba(3, 12, 27, 226)",
    "field_focus": "rgba(8, 31, 62, 236)",
    "sidebar": "rgba(4, 12, 24, 202)",
    "dialog_bg": "rgba(5, 15, 31, 234)",
    "dialog_border": "rgba(121, 232, 255, 104)",
    "field_border": "rgba(103, 181, 215, 130)",
    "field_focus_border": "#59E8FF",
    "scroll_track": "rgba(4, 14, 29, 200)",
    "scroll_handle": "rgba(114, 193, 227, 120)",
    "scroll_handle_hover": "rgba(114, 193, 227, 180)",
    "button_bg": "rgba(8, 31, 57, 228)",
    "button_hover": "rgba(13, 45, 80, 236)",
    "button_pressed": "rgba(14, 44, 76, 236)",
    "button_border": "rgba(113, 185, 216, 145)",
    "group_title": "#8CF6FF",
    "table_header_bg": "rgba(13, 39, 66, 214)",
    "table_header_border": "rgba(110, 214, 240, 112)",
    "selection": "rgba(35, 138, 185, 220)",
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
        background: rgba(4, 10, 20, 148);
        color: {PALETTE['text']};
        padding: 2px 10px;
    }}

    QMenuBar::item {{
        background: transparent;
        padding: 6px 10px;
        border-radius: 6px;
    }}

    QMenuBar::item:selected {{
        background: rgba(18, 61, 90, 180);
    }}

    QMenu {{
        background-color: rgba(4, 14, 29, 248);
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
        background: rgba(20, 83, 121, 212);
    }}

    QMenu::separator {{
        height: 1px;
        margin: 6px 10px;
        background: rgba(116, 211, 237, 90);
    }}

    QFrame#SidebarPanel {{
        background-color: {PALETTE['sidebar']};
        border-right: 1px solid rgba(112, 235, 255, 72);
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
        background: rgba(14, 56, 83, 158);
        border-color: rgba(89, 232, 255, 92);
    }}

    QToolButton#SidebarNavButton[navRole=\"active\"] {{
        background: rgba(17, 89, 121, 172);
        border-color: rgba(112, 240, 255, 138);
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
            stop:0 rgba(255, 255, 255, 10),
            stop:0.10 {PALETTE['card']},
            stop:0.68 {PALETTE['surface_alt']},
            stop:1 rgba(2, 12, 28, 230)
        );
        border: 1px solid rgba(118, 243, 255, 188);
        border-radius: 28px;
    }}

    QFrame#ShellPanel {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 rgba(255, 255, 255, 14),
            stop:0.14 {PALETTE['surface_panel']},
            stop:1 rgba(3, 16, 31, 226)
        );
        border: 1px solid rgba(116, 231, 255, 110);
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
            stop:0 rgba(255, 255, 255, 14),
            stop:0.16 rgba(8, 19, 34, 188),
            stop:1 rgba(3, 12, 24, 232)
        );
        border: 1px solid rgba(120, 232, 255, 128);
        border-radius: 16px;
    }}

    QFrame#InlineDivider {{
        background: rgba(120, 232, 255, 52);
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
            stop:0 rgba(255, 255, 255, 18),
            stop:0.22 {PALETTE['button_bg']},
            stop:1 rgba(6, 26, 46, 244)
        );
        border: 1px solid rgba(116, 231, 255, 142);
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
            stop:0 rgba(255, 255, 255, 10),
            stop:0.14 rgba(6, 16, 30, 160),
            stop:1 rgba(4, 14, 27, 214)
        );
        border: 1px solid rgba(110, 230, 255, 112);
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
            stop:0 rgba(255, 255, 255, 12),
            stop:0.15 rgba(7, 22, 40, 156),
            stop:1 rgba(4, 15, 29, 224)
        );
        border: 1px solid rgba(106, 236, 255, 132);
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
        background-color: rgba(7, 26, 46, 232);
        color: {PALETTE['text']};
        border: 1px solid rgba(116, 231, 255, 146);
        border-radius: 14px;
        padding: 0 14px 4px 14px;
        font-size: 17pt;
        font-weight: 700;
        min-width: 84px;
    }}

    QToolButton#OverflowMenuButton:hover {{
        background-color: rgba(11, 41, 68, 242);
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
        background-color: rgba(110, 236, 255, 230);
        color: #0A1C27;
        border: 1px solid rgba(199, 249, 255, 250);
        font-family: {_SECTION_HEADING_FONT_STACK};
        font-weight: 700;
        border-radius: 14px;
        padding: 0 28px;
        font-size: 12pt;
        letter-spacing: 0.2px;
    }}

    QPushButton#PrimaryButton:default {{
        background-color: rgba(110, 236, 255, 230);
        color: #0A1C27;
        border: 1px solid rgba(199, 249, 255, 250);
        border-radius: 14px;
    }}

    QPushButton#PrimaryButton:hover {{
        background-color: rgba(140, 242, 255, 236);
    }}

    QPushButton#PrimaryButton:default:hover {{
        background-color: rgba(140, 242, 255, 236);
    }}

    QPushButton#PrimaryButton:default:pressed {{
        background-color: rgba(102, 220, 240, 232);
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
        background-color: rgba(226, 145, 150, 232);
        border-color: rgba(255, 202, 208, 180);
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
        background-color: rgba(88, 46, 52, 122);
        border-color: rgba(172, 112, 121, 110);
        color: rgba(228, 199, 205, 150);
    }}

    QToolButton#OverflowMenuButton:disabled {{
        background-color: rgba(25, 37, 51, 168);
        border-color: rgba(106, 145, 162, 96);
        color: rgba(208, 226, 236, 150);
    }}

    QProgressBar {{
        background-color: rgba(7, 22, 39, 220);
        border: 1px solid rgba(121, 236, 255, 126);
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


def apply_soft_shadow(widget: QWidget, *, blur_radius: int = 48, offset_y: int = 12) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(float(blur_radius))
    effect.setOffset(0.0, float(offset_y))
    effect.setColor(QColor(7, 26, 54, 146))
    widget.setGraphicsEffect(effect)


def apply_primary_glow(widget: QWidget, *, blur_radius: int = 30) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(float(blur_radius))
    effect.setOffset(0.0, 0.0)
    effect.setColor(QColor(89, 232, 255, 146))
    widget.setGraphicsEffect(effect)
