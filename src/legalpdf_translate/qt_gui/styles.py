"""Styling helpers for the Qt GUI."""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsBlurEffect, QGraphicsDropShadowEffect, QWidget

PALETTE = {
    "text": "#EAF7FF",
    "muted": "#93B6D2",
    "accent": "#39D8FF",
    "accent_strong": "#11BCE8",
    "danger": "#D56A7A",
    "line": "rgba(132, 220, 255, 118)",
    "surface": "rgba(8, 24, 45, 148)",
    "surface_alt": "rgba(10, 30, 56, 132)",
    "field": "rgba(5, 15, 31, 194)",
    "field_focus": "rgba(8, 26, 51, 220)",
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
        background: transparent;
        border: 1px solid transparent;
        border-radius: 28px;
    }}

    QWidget#CardTint {{
        background-color: {PALETTE['surface']};
        border: 1px solid {PALETTE['line']};
        border-radius: 28px;
    }}

    QLabel#TitleLabel {{
        color: {PALETTE['accent']};
        font-size: 24pt;
        font-weight: 700;
        letter-spacing: 0.4px;
    }}

    QLabel#StatusHeaderLabel {{
        color: {PALETTE['muted']};
        font-size: 11pt;
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
    }}

    QFrame#SurfacePanel {{
        background-color: {PALETTE['surface_alt']};
        border: 1px solid rgba(111, 184, 216, 86);
        border-radius: 16px;
    }}

    QLineEdit, QPlainTextEdit, QComboBox, QSpinBox {{
        background-color: {PALETTE['field']};
        color: {PALETTE['text']};
        border: 1px solid rgba(108, 184, 216, 116);
        border-radius: 10px;
        padding: 8px 10px;
        selection-background-color: rgba(35, 138, 185, 220);
    }}

    QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
        border: 1px solid {PALETTE['accent']};
        background-color: {PALETTE['field_focus']};
    }}

    QComboBox::drop-down {{
        border-left: 1px solid rgba(116, 187, 217, 96);
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
        background-color: rgba(8, 29, 53, 224);
        color: {PALETTE['text']};
        border: 1px solid rgba(105, 173, 204, 126);
        border-radius: 11px;
        padding: 9px 14px;
        font-weight: 600;
    }}

    QPushButton:hover {{
        border-color: {PALETTE['accent']};
    }}

    QPushButton:pressed {{
        background-color: rgba(14, 44, 76, 236);
    }}

    QPushButton:disabled {{
        color: rgba(151, 182, 206, 120);
        border-color: rgba(72, 104, 128, 110);
    }}

    QPushButton#PrimaryButton {{
        background-color: rgba(17, 188, 232, 228);
        color: #001724;
        border: 1px solid rgba(130, 237, 255, 232);
        font-weight: 700;
    }}

    QPushButton#PrimaryButton:hover {{
        background-color: rgba(51, 212, 246, 235);
    }}

    QPushButton#DangerButton {{
        border-color: {PALETTE['danger']};
        color: #FFD9DF;
    }}

    QProgressBar {{
        background-color: rgba(4, 16, 31, 196);
        border: 1px solid rgba(110, 181, 212, 98);
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
