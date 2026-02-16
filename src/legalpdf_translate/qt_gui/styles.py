"""Styling helpers for the Qt GUI."""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsBlurEffect, QGraphicsDropShadowEffect, QWidget

PALETTE = {
    "text": "#EAF9FF",
    "muted": "#9AB9CE",
    "accent": "#38DCFF",
    "accent_strong": "#14C9F2",
    "danger": "#DC7B8C",
    "line": "rgba(124, 216, 255, 130)",
    "card": "rgba(5, 18, 38, 175)",
    "surface_alt": "rgba(8, 24, 47, 170)",
    "field": "rgba(3, 12, 27, 212)",
    "field_focus": "rgba(8, 31, 62, 228)",
}


def build_stylesheet() -> str:
    return f"""
    QWidget#RootWidget {{
        background: transparent;
        color: {PALETTE['text']};
        font-family: "Segoe UI";
        font-size: 12pt;
    }}

    QFrame#GlassCard {{
        background-color: {PALETTE['card']};
        border: 1px solid {PALETTE['line']};
        border-radius: 28px;
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
        background-color: {PALETTE['surface_alt']};
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
        padding: 9px 14px;
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
        background-color: rgba(23, 201, 242, 232);
        color: #001724;
        border: 1px solid rgba(166, 244, 255, 246);
        font-weight: 700;
    }}

    QPushButton#PrimaryButton:hover {{
        background-color: rgba(61, 220, 247, 238);
    }}

    QPushButton#DangerButton {{
        border-color: {PALETTE['danger']};
        color: #FFD9DF;
    }}

    QProgressBar {{
        background-color: rgba(4, 16, 31, 196);
        border: 1px solid rgba(107, 182, 214, 114);
        border-radius: 10px;
        min-height: 20px;
        text-align: center;
        color: {PALETTE['text']};
    }}

    QProgressBar::chunk {{
        border-radius: 9px;
        background-color: {PALETTE['accent']};
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
    effect.setColor(QColor(14, 68, 107, 138))
    widget.setGraphicsEffect(effect)


def apply_primary_glow(widget: QWidget, *, blur_radius: int = 30) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(float(blur_radius))
    effect.setOffset(0.0, 0.0)
    effect.setColor(QColor(57, 216, 255, 146))
    widget.setGraphicsEffect(effect)
