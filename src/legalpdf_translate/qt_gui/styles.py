"""Styling helpers for the Qt GUI."""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget

PALETTE = {
    "bg": "#050F21",
    "card": "#0A1A33",
    "card_alt": "#0E2345",
    "text": "#EAF5FF",
    "muted": "#97AECB",
    "accent": "#31C7FF",
    "accent_soft": "#1B8FBC",
    "danger": "#D86A6A",
    "border": "#1E395F",
}


def build_stylesheet() -> str:
    return f"""
    QWidget#RootWidget {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 {PALETTE['bg']},
            stop:1 #071633
        );
        color: {PALETTE['text']};
    }}

    QFrame#HeaderCard, QFrame#MainCard, QFrame#FooterCard, QFrame#DetailsCard {{
        background-color: rgba(10, 26, 51, 225);
        border: 1px solid {PALETTE['border']};
        border-radius: 12px;
    }}

    QLabel#TitleLabel {{
        color: {PALETTE['accent']};
        font-size: 20px;
        font-weight: 600;
    }}

    QLabel#StatusHeaderLabel {{
        color: {PALETTE['muted']};
        font-size: 12px;
        font-weight: 500;
    }}

    QLabel#MutedLabel {{
        color: {PALETTE['muted']};
    }}

    QLabel#PathLabel {{
        color: {PALETTE['accent']};
        font-size: 12px;
    }}

    QLineEdit, QPlainTextEdit, QComboBox, QSpinBox {{
        background-color: rgba(7, 18, 36, 240);
        color: {PALETTE['text']};
        border: 1px solid {PALETTE['border']};
        border-radius: 8px;
        padding: 8px;
        selection-background-color: {PALETTE['accent_soft']};
    }}

    QComboBox::drop-down {{
        border-left: 1px solid {PALETTE['border']};
        width: 26px;
    }}

    QComboBox QAbstractItemView {{
        background-color: #0A1D3B;
        color: {PALETTE['text']};
        selection-background-color: {PALETTE['accent_soft']};
        border: 1px solid {PALETTE['border']};
        outline: 0px;
    }}

    QCheckBox {{
        spacing: 8px;
    }}

    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {PALETTE['border']};
        border-radius: 3px;
        background-color: rgba(7, 18, 36, 240);
    }}

    QCheckBox::indicator:checked {{
        background-color: {PALETTE['accent']};
        border: 1px solid {PALETTE['accent']};
    }}

    QPushButton {{
        background-color: rgba(10, 31, 60, 235);
        color: {PALETTE['text']};
        border: 1px solid {PALETTE['border']};
        border-radius: 10px;
        padding: 9px 14px;
        font-weight: 500;
    }}

    QPushButton:hover {{
        border-color: {PALETTE['accent']};
    }}

    QPushButton:pressed {{
        background-color: rgba(17, 50, 90, 240);
    }}

    QPushButton:disabled {{
        color: #5D7594;
        border-color: #21354D;
    }}

    QPushButton#PrimaryButton {{
        background-color: rgba(27, 143, 188, 235);
        border-color: {PALETTE['accent']};
        color: #021522;
        font-weight: 700;
    }}

    QPushButton#PrimaryButton:hover {{
        background-color: rgba(48, 188, 236, 240);
    }}

    QPushButton#DangerButton {{
        border-color: {PALETTE['danger']};
        color: #FFCECE;
    }}

    QProgressBar {{
        background-color: rgba(7, 18, 36, 240);
        border: 1px solid {PALETTE['border']};
        border-radius: 9px;
        min-height: 18px;
        text-align: center;
        color: {PALETTE['text']};
    }}

    QProgressBar::chunk {{
        border-radius: 8px;
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


def apply_card_shadow(widget: QWidget, *, blur_radius: int = 30, offset_y: int = 8) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(float(blur_radius))
    effect.setOffset(0.0, float(offset_y))
    effect.setColor(QColor(49, 199, 255, 58))
    widget.setGraphicsEffect(effect)
