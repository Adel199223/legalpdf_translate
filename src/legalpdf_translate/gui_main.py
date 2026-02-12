"""GUI entrypoint."""

from __future__ import annotations

import ctypes
import os
import tkinter as tk
from tkinter import font as tkfont

from legalpdf_translate.gui_app import LegalPDFTranslateApp
from legalpdf_translate.gui_theme import apply_theme
from legalpdf_translate.user_settings import load_gui_settings


def _enable_windows_dpi_awareness() -> None:
    if os.name != "nt":
        return
    try:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    except Exception:
        return

    # Prefer Per-Monitor V2 where available for crisp rendering on multi-DPI setups.
    try:
        dpi_context_per_monitor_v2 = ctypes.c_void_p(-4)
        if bool(user32.SetProcessDpiAwarenessContext(dpi_context_per_monitor_v2)):
            return
    except Exception:
        pass

    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass


def _apply_default_fonts(root: tk.Tk, *, ui_scale: float) -> None:
    base_size = max(11, int(round(12 * float(ui_scale))))
    heading_size = max(12, int(round(13 * float(ui_scale))))
    button_size = max(11, int(round(11 * float(ui_scale))))

    def _set_named_font(name: str, *, family: str, size: int, weight: str = "normal") -> None:
        try:
            named = tkfont.nametofont(name, root=root)
        except tk.TclError:
            return
        named.configure(family=family, size=size, weight=weight)

    _set_named_font("TkDefaultFont", family="Segoe UI", size=base_size)
    _set_named_font("TkTextFont", family="Segoe UI", size=base_size)
    _set_named_font("TkFixedFont", family="Consolas", size=base_size)
    _set_named_font("TkMenuFont", family="Segoe UI", size=base_size)
    _set_named_font("TkHeadingFont", family="Segoe UI Semibold", size=heading_size, weight="bold")
    root.option_add("*Font", ("Segoe UI", base_size))
    root.option_add("*TCombobox*Listbox.font", ("Segoe UI", base_size))
    root.option_add("*TButton.font", ("Segoe UI", button_size))


def main() -> None:
    _enable_windows_dpi_awareness()
    root = tk.Tk()
    settings = load_gui_settings()
    theme_name = str(settings.get("ui_theme", "dark_futuristic") or "dark_futuristic")
    try:
        ui_scale = float(settings.get("ui_scale", 1.0))
    except (TypeError, ValueError):
        ui_scale = 1.0
    _apply_default_fonts(root, ui_scale=ui_scale)
    apply_theme(root, theme_name=theme_name, ui_scale=ui_scale)
    root.title("LegalPDF Translate")
    root.geometry("980x760")
    LegalPDFTranslateApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
