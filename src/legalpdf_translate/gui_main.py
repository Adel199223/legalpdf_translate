"""GUI entrypoint."""

from __future__ import annotations

import tkinter as tk

from .gui_app import LegalPDFTranslateApp


def main() -> None:
    root = tk.Tk()
    root.title("LegalPDF Translate")
    root.geometry("980x760")
    LegalPDFTranslateApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
