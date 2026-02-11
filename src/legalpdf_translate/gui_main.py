"""GUI entrypoint."""

from __future__ import annotations

import tkinter as tk

from legalpdf_translate.gui_app import LegalPDFTranslateApp
from legalpdf_translate.gui_theme import apply_theme


def main() -> None:
    root = tk.Tk()
    apply_theme(root)
    root.title("LegalPDF Translate")
    root.geometry("980x760")
    LegalPDFTranslateApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
