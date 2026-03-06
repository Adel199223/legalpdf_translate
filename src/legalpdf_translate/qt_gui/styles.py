"""Styling helpers for the Qt GUI."""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsBlurEffect, QGraphicsDropShadowEffect, QWidget

PALETTE = {
    "text": "#EAF9FF",
    "muted": "#9AB9CE",
    "muted_soft": "#7CA4B7",
    "accent": "#59E8FF",
    "accent_strong": "#2DD4F0",
    "accent_soft": "#8CF6FF",
    "danger": "#E98E98",
    "danger_strong": "#F39CA7",
    "line": "rgba(124, 232, 255, 140)",
    "card": "rgba(5, 18, 38, 176)",
    "surface_alt": "rgba(6, 21, 43, 182)",
    "surface_panel": "rgba(6, 19, 36, 142)",
    "field": "rgba(3, 12, 27, 226)",
    "field_focus": "rgba(8, 31, 62, 236)",
    "sidebar": "rgba(4, 12, 24, 202)",
}


def build_stylesheet() -> str:
    return f"""
    QWidget#RootWidget {{
        background: transparent;
        color: {PALETTE['text']};
        font-family: "Segoe UI", "DejaVu Sans", "Arial";
        font-size: 12pt;
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
        border: 1px solid rgba(113, 230, 255, 120);
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
        border-right: 1px solid rgba(112, 235, 255, 64);
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
        background: rgba(10, 42, 66, 126);
        border-color: rgba(89, 232, 255, 82);
    }}

    QToolButton#SidebarNavButton[navRole=\"active\"] {{
        background: rgba(15, 72, 100, 148);
        border-color: rgba(112, 240, 255, 124);
        border-left: 4px solid {PALETTE['accent']};
        color: {PALETTE['accent_soft']};
    }}

    QToolButton#SidebarNavButton[comingSoon=\"true\"] {{
        color: rgba(184, 213, 229, 154);
    }}

    QLabel#HeroTitleLabel {{
        color: {PALETTE['accent_soft']};
        font-family: "Bahnschrift", "Segoe UI", "DejaVu Sans";
        font-size: 30pt;
        font-weight: 700;
        letter-spacing: 0.8px;
    }}

    QLabel#HeroStatusLabel {{
        color: rgba(182, 239, 255, 228);
        font-family: "Bahnschrift", "Segoe UI", "DejaVu Sans";
        font-size: 13pt;
        font-weight: 500;
    }}

    QFrame#DashboardFrame {{
        background-color: rgba(7, 20, 40, 82);
        border: 1px solid rgba(118, 243, 255, 178);
        border-radius: 28px;
    }}

    QFrame#ShellPanel {{
        background-color: rgba(8, 23, 45, 108);
        border: 1px solid rgba(116, 231, 255, 82);
        border-radius: 18px;
    }}

    QLabel#PanelHeading {{
        color: {PALETTE['accent_soft']};
        font-family: "Bahnschrift", "Segoe UI";
        font-size: 19.5pt;
        font-weight: 500;
    }}

    QLabel#FieldLabel {{
        color: rgba(236, 249, 255, 224);
        font-size: 12.2pt;
        font-weight: 500;
    }}

    QFrame#FieldChrome {{
        background-color: rgba(8, 19, 34, 170);
        border: 1px solid rgba(120, 232, 255, 112);
        border-radius: 14px;
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
        padding: 8px 0;
        min-width: 46px;
        color: rgba(238, 251, 255, 236);
        font-size: 11.5pt;
        font-weight: 500;
    }}

    QLabel#FlagLabel {{
        background: transparent;
        border: none;
    }}

    QLabel#FieldSupportLabel {{
        color: rgba(216, 240, 248, 214);
        font-size: 10.7pt;
        font-weight: 500;
    }}

    QLabel#FieldValueLabel {{
        color: rgba(238, 251, 255, 236);
        font-size: 11.3pt;
        font-weight: 500;
    }}

    QLabel#FieldValueLabel[accent=\"true\"] {{
        color: {PALETTE['accent_soft']};
    }}

    QToolButton#FieldBrowseButton {{
        background-color: rgba(9, 29, 54, 228);
        border: 1px solid rgba(116, 231, 255, 128);
        border-radius: 11px;
        padding: 8px;
    }}

    QToolButton#FieldBrowseButton:hover {{
        background-color: rgba(12, 42, 74, 238);
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

    QToolButton#SectionToggleButton {{
        color: rgba(229, 247, 255, 228);
        background-color: rgba(7, 19, 35, 180);
        border: 1px solid rgba(116, 231, 255, 120);
        border-radius: 15px;
        padding: 12px 15px;
        font-size: 12pt;
        font-weight: 500;
    }}

    QToolButton#SectionToggleButton:hover {{
        background-color: rgba(12, 35, 60, 192);
    }}

    QLabel#ProgressSummaryLabel {{
        color: rgba(238, 251, 255, 230);
        font-size: 13.5pt;
        font-weight: 500;
    }}

    QLabel#CurrentTaskLabel {{
        color: rgba(235, 247, 255, 214);
        font-size: 10.8pt;
    }}

    QFrame#MetricGridFrame {{
        background-color: rgba(6, 16, 30, 142);
        border: 1px solid rgba(110, 230, 255, 94);
        border-radius: 16px;
    }}

    QFrame#MetricCell {{
        background: transparent;
        border: none;
    }}

    QLabel#MetricTitle {{
        color: rgba(227, 244, 252, 214);
        font-size: 11.2pt;
        font-weight: 500;
    }}

    QLabel#MetricValue {{
        color: rgba(240, 250, 255, 236);
        font-size: 13.2pt;
        font-weight: 500;
    }}

    QLabel#MetricRetryValue {{
        color: rgba(222, 242, 250, 216);
        font-size: 12pt;
        font-weight: 500;
    }}

    QFrame#RetryBadge {{
        background: transparent;
        border: none;
    }}

    QLabel#OutputFormatLabel {{
        color: rgba(219, 241, 251, 218);
        font-size: 12pt;
        font-weight: 500;
    }}

    QLabel#FooterMetaLabel {{
        color: rgba(191, 224, 238, 186);
        font-size: 10.5pt;
        font-weight: 500;
    }}

    QFrame#ActionRail {{
        background-color: rgba(7, 22, 40, 124);
        border: 1px solid rgba(106, 236, 255, 108);
        border-radius: 18px;
    }}

    QToolButton#OverflowMenuButton {{
        background-color: rgba(7, 26, 46, 224);
        color: {PALETTE['text']};
        border: 1px solid rgba(116, 231, 255, 132);
        border-radius: 14px;
        padding: 0 14px 4px 14px;
        font-size: 17pt;
        font-weight: 700;
        min-width: 84px;
    }}

    QToolButton#OverflowMenuButton:hover {{
        background-color: rgba(11, 41, 68, 240);
    }}

    QFrame#HiddenUtilityPanel {{
        background: transparent;
        border: none;
    }}

    QFrame#HeaderStrip {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(8, 36, 66, 175),
            stop:0.5 rgba(11, 52, 88, 212),
            stop:1 rgba(8, 36, 66, 175)
        );
        border: 1px solid rgba(120, 214, 255, 130);
        border-radius: 15px;
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
        background-color: {PALETTE['surface_panel']};
        border: 1px solid rgba(114, 193, 227, 94);
        border-radius: 16px;
    }}

    QLineEdit, QPlainTextEdit, QComboBox, QSpinBox {{
        background-color: {PALETTE['field']};
        color: {PALETTE['text']};
        border: 1px solid rgba(103, 181, 215, 130);
        border-radius: 10px;
        padding: 8px 10px;
        selection-background-color: rgba(35, 138, 185, 220);
    }}

    QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
        border: 1px solid {PALETTE['accent']};
        background-color: {PALETTE['field_focus']};
    }}

    QComboBox#GlossaryTableCombo {{
        padding: 2px 6px;
        border-radius: 4px;
    }}

    QComboBox#GlossaryTableCombo::drop-down {{
        width: 18px;
    }}

    QComboBox::drop-down {{
        border-left: 1px solid rgba(116, 187, 217, 112);
        width: 26px;
    }}

    QComboBox QAbstractItemView {{
        background-color: rgba(6, 19, 37, 235);
        color: {PALETTE['text']};
        selection-background-color: rgba(24, 106, 148, 230);
        border: 1px solid rgba(82, 164, 198, 122);
        outline: none;
    }}

    QCheckBox {{
        spacing: 8px;
    }}

    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid rgba(112, 182, 214, 104);
        border-radius: 3px;
        background: rgba(4, 14, 29, 210);
    }}

    QCheckBox::indicator:checked {{
        background: {PALETTE['accent_strong']};
        border: 1px solid {PALETTE['accent']};
    }}

    QPushButton {{
        background-color: rgba(8, 31, 57, 228);
        color: {PALETTE['text']};
        border: 1px solid rgba(113, 185, 216, 145);
        border-radius: 11px;
        padding: 0 16px;
        font-weight: 600;
    }}

    QPushButton:hover {{
        border-color: rgba(125, 226, 255, 235);
        background-color: rgba(13, 45, 80, 236);
    }}

    QPushButton:pressed {{
        background-color: rgba(14, 44, 76, 236);
    }}

    QPushButton:disabled {{
        color: rgba(151, 182, 206, 120);
        border-color: rgba(72, 104, 128, 110);
    }}

    QPushButton#PrimaryButton {{
        background-color: rgba(110, 236, 255, 230);
        color: #0A1C27;
        border: 1px solid rgba(199, 249, 255, 250);
        font-weight: 700;
        border-radius: 14px;
        padding: 0 28px;
        font-size: 12.2pt;
    }}

    QPushButton#PrimaryButton:hover {{
        background-color: rgba(140, 242, 255, 236);
    }}

    QPushButton#DangerButton {{
        background-color: rgba(226, 145, 150, 232);
        border-color: rgba(255, 202, 208, 180);
        color: #321115;
        border-radius: 14px;
        padding: 0 24px;
        font-size: 11.7pt;
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
        background-color: rgba(7, 22, 39, 214);
        border: 1px solid rgba(121, 236, 255, 112);
        border-radius: 14px;
        min-height: 26px;
        padding: 2px;
        text-align: center;
        color: {PALETTE['text']};
    }}

    QProgressBar::chunk {{
        border-radius: 10px;
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(94, 230, 255, 255),
            stop:1 rgba(57, 216, 255, 255)
        );
    }}

    QToolButton#DisclosureButton {{
        color: {PALETTE['accent']};
        background: transparent;
        border: none;
        font-weight: 600;
        padding: 4px;
    }}

    QScrollBar:vertical {{
        background: rgba(4, 14, 29, 200);
        width: 10px;
        border-radius: 5px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: rgba(114, 193, 227, 120);
        border-radius: 4px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: rgba(114, 193, 227, 180);
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    QScrollBar:horizontal {{
        background: rgba(4, 14, 29, 200);
        height: 10px;
        border-radius: 5px;
        margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: rgba(114, 193, 227, 120);
        border-radius: 4px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: rgba(114, 193, 227, 180);
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: transparent;
    }}
    """


def make_blur_effect(parent: QWidget, *, radius: int = 24) -> QGraphicsBlurEffect:
    effect = QGraphicsBlurEffect(parent)
    effect.setBlurRadius(float(radius))
    effect.setBlurHints(QGraphicsBlurEffect.QualityHint)
    return effect


def apply_soft_shadow(widget: QWidget, *, blur_radius: int = 48, offset_y: int = 12) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(float(blur_radius))
    effect.setOffset(0.0, float(offset_y))
    effect.setColor(QColor(12, 58, 96, 104))
    widget.setGraphicsEffect(effect)


def apply_primary_glow(widget: QWidget, *, blur_radius: int = 30) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(float(blur_radius))
    effect.setOffset(0.0, 0.0)
    effect.setColor(QColor(57, 216, 255, 126))
    widget.setGraphicsEffect(effect)
