"""GUI entrypoint."""

from __future__ import annotations

import tkinter as tk

from legalpdf_translate.gui_app import LegalPDFTranslateApp
from legalpdf_translate.gui_theme import apply_theme
from legalpdf_translate.user_settings import load_gui_settings


def main() -> None:
    root = tk.Tk()
    settings = load_gui_settings()
    theme_name = str(settings.get("ui_theme", "dark_futuristic") or "dark_futuristic")
    try:
        ui_scale = float(settings.get("ui_scale", 1.0))
    except (TypeError, ValueError):
        ui_scale = 1.0
    apply_theme(root, theme_name=theme_name, ui_scale=ui_scale)
    root.title("LegalPDF Translate")
    root.geometry("980x760")
    LegalPDFTranslateApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
