"""Theme and scale utilities for ttk-based GUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

THEMES: dict[str, dict[str, str]] = {
    "dark_futuristic": {
        "bg": "#06132A",
        "surface": "#0D1D3A",
        "surface_alt": "#12284A",
        "text": "#EAF4FF",
        "secondary": "#91A8C7",
        "accent": "#33B8FF",
        "danger": "#D96A6A",
    },
    "dark_simple": {
        "bg": "#0C1118",
        "surface": "#182334",
        "surface_alt": "#213147",
        "text": "#EBF1F8",
        "secondary": "#9AA9BC",
        "accent": "#2FA8FF",
        "danger": "#D46262",
    },
}


def _resolve_palette(theme_name: str) -> dict[str, str]:
    return dict(THEMES.get(theme_name, THEMES["dark_futuristic"]))


def apply_theme(root: tk.Tk, *, theme_name: str = "dark_futuristic", ui_scale: float = 1.0) -> dict[str, str]:
    palette = _resolve_palette(theme_name)
    style = ttk.Style(root)
    style.theme_use("clam")

    scale = float(ui_scale)
    base_size = max(11, int(round(11 * scale)))
    title_size = max(12, int(round(13 * scale)))
    button_size = max(11, int(round(11 * scale)))
    pad_x = max(10, int(round(12 * scale)))
    pad_y = max(6, int(round(8 * scale)))

    root.option_add("*Font", ("Segoe UI", base_size))
    root.option_add("*TCombobox*Listbox.font", ("Segoe UI", base_size))
    try:
        root.tk.call("tk", "scaling", scale)
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
    style.configure(
        "Title.TLabel",
        background=palette["bg"],
        foreground=palette["text"],
        font=("Segoe UI Semibold", title_size),
    )
    style.configure("Muted.TLabel", background=palette["bg"], foreground=palette["secondary"])
    style.configure("Danger.TLabel", background=palette["bg"], foreground=palette["danger"])
    style.configure("TFrame", background=palette["bg"])
    style.configure("Surface.TFrame", background=palette["surface"])
    style.configure("TLabel", background=palette["bg"], foreground=palette["text"])
    style.configure(
        "TLabelframe",
        background=palette["surface"],
        foreground=palette["text"],
        bordercolor=palette["surface_alt"],
        relief=tk.GROOVE,
        padding=(pad_x, pad_y),
    )
    style.configure("TLabelframe.Label", background=palette["surface"], foreground=palette["text"])
    style.configure(
        "Surface.TLabelframe",
        background=palette["surface"],
        foreground=palette["text"],
        bordercolor=palette["surface_alt"],
        relief=tk.GROOVE,
        padding=(pad_x, pad_y),
    )
    style.configure("Surface.TLabelframe.Label", background=palette["surface"], foreground=palette["text"])

    style.configure(
        "TButton",
        background=palette["surface"],
        foreground=palette["text"],
        bordercolor=palette["surface_alt"],
        focuscolor=palette["accent"],
        padding=(pad_x, pad_y),
        font=("Segoe UI", button_size),
    )
    style.map(
        "TButton",
        background=[("active", palette["surface_alt"]), ("disabled", palette["surface"])],
        foreground=[("disabled", palette["secondary"])],
    )
    style.configure(
        "Primary.TButton",
        background=palette["accent"],
        foreground="#041523",
        bordercolor=palette["accent"],
        focuscolor=palette["accent"],
        padding=(pad_x, pad_y),
        font=("Segoe UI Semibold", button_size),
    )
    style.map(
        "Primary.TButton",
        background=[("active", "#68CCFF"), ("disabled", palette["surface"])],
        foreground=[("disabled", palette["secondary"])],
    )
    style.configure(
        "Secondary.TButton",
        background=palette["surface"],
        foreground=palette["text"],
        bordercolor=palette["surface_alt"],
        focuscolor=palette["accent"],
        padding=(pad_x, pad_y),
        font=("Segoe UI", button_size),
    )
    style.map(
        "Secondary.TButton",
        background=[("active", palette["surface_alt"]), ("disabled", palette["surface"])],
        foreground=[("disabled", palette["secondary"])],
    )

    style.configure(
        "TEntry",
        fieldbackground=palette["surface"],
        foreground=palette["text"],
        insertcolor=palette["text"],
        bordercolor=palette["surface_alt"],
        padding=(8, 6),
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
        bordercolor=palette["surface_alt"],
        padding=(8, 6),
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", palette["surface"]), ("disabled", palette["surface"])],
        foreground=[("readonly", palette["text"]), ("disabled", palette["secondary"])],
    )

    style.configure(
        "Horizontal.TProgressbar",
        background=palette["accent"],
        troughcolor=palette["surface_alt"],
        bordercolor=palette["surface_alt"],
        thickness=max(16, int(round(18 * scale))),
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
