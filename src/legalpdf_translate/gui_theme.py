"""Dark ttk theme for the GUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

PALETTE = {
    "bg": "#0F111A",
    "surface": "#161A24",
    "text": "#E6E6E6",
    "secondary": "#A0A0A0",
    "accent": "#3A7BFF",
    "danger": "#D14B4B",
}


def apply_theme(root: tk.Tk) -> None:
    style = ttk.Style(root)
    style.theme_use("clam")

    root.configure(bg=PALETTE["bg"])

    style.configure(
        ".",
        background=PALETTE["bg"],
        foreground=PALETTE["text"],
        fieldbackground=PALETTE["surface"],
    )
    style.configure("TFrame", background=PALETTE["bg"])
    style.configure("TLabel", background=PALETTE["bg"], foreground=PALETTE["text"])
    style.configure(
        "TLabelframe",
        background=PALETTE["bg"],
        foreground=PALETTE["text"],
        bordercolor=PALETTE["surface"],
    )
    style.configure("TLabelframe.Label", background=PALETTE["bg"], foreground=PALETTE["text"])

    style.configure(
        "TButton",
        background=PALETTE["surface"],
        foreground=PALETTE["text"],
        bordercolor=PALETTE["surface"],
        focuscolor=PALETTE["accent"],
        padding=(10, 6),
    )
    style.map(
        "TButton",
        background=[("active", PALETTE["accent"]), ("disabled", PALETTE["surface"])],
        foreground=[("disabled", PALETTE["secondary"])],
    )

    style.configure(
        "TEntry",
        fieldbackground=PALETTE["surface"],
        foreground=PALETTE["text"],
        insertcolor=PALETTE["text"],
        bordercolor=PALETTE["surface"],
    )
    style.map(
        "TEntry",
        foreground=[("disabled", PALETTE["secondary"])],
        fieldbackground=[("disabled", PALETTE["surface"])],
    )

    style.configure(
        "TCombobox",
        fieldbackground=PALETTE["surface"],
        foreground=PALETTE["text"],
        background=PALETTE["surface"],
        arrowcolor=PALETTE["text"],
        bordercolor=PALETTE["surface"],
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", PALETTE["surface"]), ("disabled", PALETTE["surface"])],
        foreground=[("readonly", PALETTE["text"]), ("disabled", PALETTE["secondary"])],
    )

    style.configure(
        "Horizontal.TProgressbar",
        background=PALETTE["accent"],
        troughcolor=PALETTE["surface"],
        bordercolor=PALETTE["surface"],
        thickness=16,
    )


def apply_text_widget_theme(widget: tk.Text) -> None:
    widget.configure(
        bg=PALETTE["surface"],
        fg=PALETTE["text"],
        insertbackground=PALETTE["accent"],
        selectbackground=PALETTE["accent"],
        selectforeground=PALETTE["text"],
        highlightbackground=PALETTE["surface"],
        highlightcolor=PALETTE["accent"],
        relief=tk.FLAT,
    )
