"""Theme and scale utilities for ttk-based GUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

THEMES: dict[str, dict[str, str]] = {
    "dark_futuristic": {
        "bg": "#0E1320",
        "surface": "#161F33",
        "text": "#E8EDF8",
        "secondary": "#98A5C4",
        "accent": "#3D84FF",
        "danger": "#D65757",
    },
    "dark_simple": {
        "bg": "#111315",
        "surface": "#1A1E22",
        "text": "#ECEDEE",
        "secondary": "#A6ABAF",
        "accent": "#2F74E7",
        "danger": "#D14B4B",
    },
}


def _resolve_palette(theme_name: str) -> dict[str, str]:
    return dict(THEMES.get(theme_name, THEMES["dark_futuristic"]))


def apply_theme(root: tk.Tk, *, theme_name: str = "dark_futuristic", ui_scale: float = 1.0) -> dict[str, str]:
    palette = _resolve_palette(theme_name)
    style = ttk.Style(root)
    style.theme_use("clam")

    base_size = max(9, int(round(10 * float(ui_scale))))
    title_size = max(base_size + 3, int(round(14 * float(ui_scale))))
    root.option_add("*Font", ("Segoe UI", base_size))
    try:
        root.tk.call("tk", "scaling", float(ui_scale))
    except Exception:
        pass

    root.configure(bg=palette["bg"])
    style.configure(
        ".",
        background=palette["bg"],
        foreground=palette["text"],
        fieldbackground=palette["surface"],
        font=("Segoe UI", base_size),
    )
    style.configure("Title.TLabel", font=("Segoe UI Semibold", title_size), foreground=palette["text"])
    style.configure("Muted.TLabel", foreground=palette["secondary"])
    style.configure("Danger.TLabel", foreground=palette["danger"])
    style.configure("TFrame", background=palette["bg"])
    style.configure("TLabel", background=palette["bg"], foreground=palette["text"])
    style.configure(
        "TLabelframe",
        background=palette["bg"],
        foreground=palette["text"],
        bordercolor=palette["surface"],
        relief=tk.GROOVE,
        padding=8,
    )
    style.configure("TLabelframe.Label", background=palette["bg"], foreground=palette["text"])

    style.configure(
        "TButton",
        background=palette["surface"],
        foreground=palette["text"],
        bordercolor=palette["surface"],
        focuscolor=palette["accent"],
        padding=(12, 7),
    )
    style.map(
        "TButton",
        background=[("active", palette["accent"]), ("disabled", palette["surface"])],
        foreground=[("disabled", palette["secondary"])],
    )

    style.configure(
        "TEntry",
        fieldbackground=palette["surface"],
        foreground=palette["text"],
        insertcolor=palette["text"],
        bordercolor=palette["surface"],
        padding=(6, 5),
    )
    style.map(
        "TEntry",
        foreground=[("disabled", palette["secondary"])],
        fieldbackground=[("disabled", palette["surface"])],
    )

    style.configure(
        "TCombobox",
        fieldbackground=palette["surface"],
        foreground=palette["text"],
        background=palette["surface"],
        arrowcolor=palette["text"],
        bordercolor=palette["surface"],
        padding=(6, 5),
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", palette["surface"]), ("disabled", palette["surface"])],
        foreground=[("readonly", palette["text"]), ("disabled", palette["secondary"])],
    )

    style.configure(
        "Horizontal.TProgressbar",
        background=palette["accent"],
        troughcolor=palette["surface"],
        bordercolor=palette["surface"],
        thickness=max(14, int(round(16 * ui_scale))),
    )
    return palette


def apply_text_widget_theme(widget: tk.Text, palette: dict[str, str] | None = None) -> None:
    resolved = palette or THEMES["dark_futuristic"]
    widget.configure(
        bg=resolved["surface"],
        fg=resolved["text"],
        insertbackground=resolved["accent"],
        selectbackground=resolved["accent"],
        selectforeground=resolved["text"],
        highlightbackground=resolved["surface"],
        highlightcolor=resolved["accent"],
        relief=tk.FLAT,
        padx=6,
        pady=6,
    )
