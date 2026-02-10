"""Tkinter GUI application."""

from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .checkpoint import parse_effort, parse_image_mode
from .pdf_text_order import get_page_count
from .types import RunConfig, RunSummary, TargetLang
from .workflow import TranslationWorkflow


class LegalPDFTranslateApp(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=12)
        self.master = master
        self.queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self.workflow: TranslationWorkflow | None = None
        self.worker: threading.Thread | None = None
        self.last_summary: RunSummary | None = None

        self.pdf_path_var = tk.StringVar()
        self.lang_var = tk.StringVar(value=TargetLang.EN.value)
        self.outdir_var = tk.StringVar()
        self.effort_var = tk.StringVar(value="high")
        self.images_var = tk.StringVar(value="auto")
        self.max_pages_var = tk.StringVar(value="")
        self.resume_var = tk.BooleanVar(value=True)
        self.page_breaks_var = tk.BooleanVar(value=True)
        self.keep_var = tk.BooleanVar(value=True)
        self.context_file_var = tk.StringVar(value="")
        self.show_advanced_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Idle")
        self.page_count_var = tk.StringVar(value="Pages: -")

        self._build_ui()
        self.pack(fill=tk.BOTH, expand=True)
        self.after(120, self._poll_queue)

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)

        ttk.Label(self, text="PDF").grid(row=0, column=0, sticky="w")
        ttk.Entry(self, textvariable=self.pdf_path_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(self, text="Browse", command=self._pick_pdf).grid(row=0, column=2, sticky="ew")
        ttk.Label(self, textvariable=self.page_count_var).grid(row=0, column=3, sticky="w", padx=(8, 0))

        ttk.Label(self, text="Language").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            self,
            textvariable=self.lang_var,
            values=[TargetLang.EN.value, TargetLang.FR.value, TargetLang.AR.value],
            state="readonly",
            width=12,
        ).grid(row=1, column=1, sticky="w", padx=6, pady=(8, 0))

        ttk.Label(self, text="Output Folder").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(self, textvariable=self.outdir_var).grid(row=2, column=1, sticky="ew", padx=6, pady=(8, 0))
        ttk.Button(self, text="Browse", command=self._pick_outdir).grid(row=2, column=2, sticky="ew", pady=(8, 0))

        ttk.Checkbutton(
            self,
            text="Show Advanced",
            variable=self.show_advanced_var,
            command=self._toggle_advanced,
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 0))

        self.advanced = ttk.LabelFrame(self, text="Advanced", padding=8)
        self.advanced.columnconfigure(1, weight=1)

        ttk.Label(self.advanced, text="Reasoning effort").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            self.advanced,
            textvariable=self.effort_var,
            values=["high", "xhigh"],
            state="readonly",
            width=12,
        ).grid(row=0, column=1, sticky="w")

        ttk.Label(self.advanced, text="Image mode").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(
            self.advanced,
            textvariable=self.images_var,
            values=["off", "auto", "always"],
            state="readonly",
            width=12,
        ).grid(row=1, column=1, sticky="w", pady=(6, 0))

        ttk.Label(self.advanced, text="Max pages (blank=all)").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(self.advanced, textvariable=self.max_pages_var, width=12).grid(
            row=2, column=1, sticky="w", pady=(6, 0)
        )

        ttk.Checkbutton(self.advanced, text="Resume", variable=self.resume_var).grid(
            row=3, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Checkbutton(self.advanced, text="Insert page breaks", variable=self.page_breaks_var).grid(
            row=3, column=1, sticky="w", pady=(6, 0)
        )
        ttk.Checkbutton(self.advanced, text="Keep intermediates", variable=self.keep_var).grid(
            row=4, column=0, sticky="w", pady=(6, 0)
        )

        ttk.Label(self.advanced, text="Context file").grid(row=5, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(self.advanced, textvariable=self.context_file_var).grid(
            row=5, column=1, sticky="ew", pady=(6, 0)
        )
        ttk.Button(self.advanced, text="Browse", command=self._pick_context).grid(
            row=5, column=2, sticky="ew", pady=(6, 0), padx=(6, 0)
        )

        ttk.Label(self.advanced, text="Context text").grid(row=6, column=0, sticky="nw", pady=(6, 0))
        self.context_text = scrolledtext.ScrolledText(self.advanced, height=5, wrap=tk.WORD)
        self.context_text.grid(row=6, column=1, columnspan=2, sticky="ew", pady=(6, 0))

        controls = ttk.Frame(self)
        controls.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        controls.columnconfigure(4, weight=1)

        self.translate_btn = ttk.Button(controls, text="Translate", command=self._start_translation)
        self.translate_btn.grid(row=0, column=0, padx=(0, 6))
        self.cancel_btn = ttk.Button(controls, text="Cancel", command=self._cancel_translation, state=tk.DISABLED)
        self.cancel_btn.grid(row=0, column=1, padx=(0, 6))
        self.export_partial_btn = ttk.Button(
            controls, text="Export partial DOCX", command=self._export_partial, state=tk.DISABLED
        )
        self.export_partial_btn.grid(row=0, column=2, padx=(0, 6))
        self.open_outdir_btn = ttk.Button(
            controls,
            text="Open output folder",
            command=self._open_output_folder,
            state=tk.DISABLED,
        )
        self.open_outdir_btn.grid(row=0, column=3, padx=(0, 6))

        self.progress = ttk.Progressbar(self, orient=tk.HORIZONTAL, mode="determinate", maximum=100)
        self.progress.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Label(self, textvariable=self.status_var).grid(row=7, column=0, columnspan=3, sticky="w", pady=(6, 0))

        self.log_text = scrolledtext.ScrolledText(self, height=12, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.grid(row=8, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        self.rowconfigure(8, weight=1)

    def _toggle_advanced(self) -> None:
        if self.show_advanced_var.get():
            self.advanced.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        else:
            self.advanced.grid_forget()

    def _pick_pdf(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if path:
            self.pdf_path_var.set(path)
            try:
                page_count = get_page_count(Path(path))
                self.page_count_var.set(f"Pages: {page_count}")
            except Exception:
                self.page_count_var.set("Pages: ?")

    def _pick_outdir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.outdir_var.set(path)

    def _pick_context(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self.context_file_var.set(path)

    def _append_log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{stamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _build_config(self) -> RunConfig:
        pdf = Path(self.pdf_path_var.get().strip())
        outdir = Path(self.outdir_var.get().strip())
        lang = TargetLang(self.lang_var.get().strip())

        max_pages_text = self.max_pages_var.get().strip()
        max_pages = int(max_pages_text) if max_pages_text else None
        context_file_text = self.context_file_var.get().strip()
        context_file = Path(context_file_text) if context_file_text else None
        context_text = self.context_text.get("1.0", tk.END).strip() or None

        return RunConfig(
            pdf_path=pdf,
            output_dir=outdir,
            target_lang=lang,
            effort=parse_effort(self.effort_var.get()),
            image_mode=parse_image_mode(self.images_var.get()),
            max_pages=max_pages,
            resume=self.resume_var.get(),
            page_breaks=self.page_breaks_var.get(),
            keep_intermediates=self.keep_var.get(),
            context_file=context_file,
            context_text=context_text,
        )

    def _set_busy(self, busy: bool) -> None:
        self.translate_btn.configure(state=tk.DISABLED if busy else tk.NORMAL)
        self.cancel_btn.configure(state=tk.NORMAL if busy else tk.DISABLED)

    def _start_translation(self) -> None:
        try:
            config = self._build_config()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Invalid configuration", str(exc))
            return

        self.last_summary = None
        self.export_partial_btn.configure(state=tk.DISABLED)
        self.open_outdir_btn.configure(state=tk.NORMAL if self.outdir_var.get().strip() else tk.DISABLED)
        self._set_busy(True)
        self.progress.configure(value=0)
        self.status_var.set("Starting...")

        def log_callback(message: str) -> None:
            self.queue.put(("log", message))

        def progress_callback(page: int, total: int, status: str) -> None:
            self.queue.put(("progress", (page, total, status)))

        self.workflow = TranslationWorkflow(log_callback=log_callback, progress_callback=progress_callback)

        def target() -> None:
            try:
                summary = self.workflow.run(config)
                self.queue.put(("done", summary))
            except Exception as exc:  # noqa: BLE001
                self.queue.put(("error", str(exc)))

        self.worker = threading.Thread(target=target, daemon=True)
        self.worker.start()

    def _cancel_translation(self) -> None:
        if self.workflow is not None:
            self.workflow.cancel()
            self._append_log("Cancellation requested.")

    def _export_partial(self) -> None:
        if self.workflow is None:
            return
        try:
            partial = self.workflow.export_partial_docx()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Partial export failed", str(exc))
            return
        if partial is None:
            messagebox.showinfo("Partial export", "No completed pages available.")
            return
        self._append_log(f"Partial DOCX exported: {partial}")
        messagebox.showinfo("Partial export", f"Exported: {partial}")

    def _open_output_folder(self) -> None:
        path = self.outdir_var.get().strip()
        if not path:
            return
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Open folder failed", str(exc))

    def _poll_queue(self) -> None:
        while True:
            try:
                event, payload = self.queue.get_nowait()
            except queue.Empty:
                break
            if event == "log":
                self._append_log(str(payload))
            elif event == "progress":
                page, total, status = payload  # type: ignore[misc]
                progress_value = (float(page) / float(total)) * 100.0
                self.progress.configure(value=progress_value)
                self.status_var.set(f"Page {page}/{total}: {status}")
            elif event == "done":
                summary = payload  # type: ignore[assignment]
                self.last_summary = summary
                self._set_busy(False)
                self.open_outdir_btn.configure(state=tk.NORMAL if self.outdir_var.get().strip() else tk.DISABLED)
                if summary.success:
                    self.status_var.set("Completed")
                    self._append_log(f"Completed: {summary.output_docx}")
                    messagebox.showinfo("Translation complete", f"Output: {summary.output_docx}")
                else:
                    self.status_var.set(f"Failed ({summary.error})")
                    self._append_log(f"Run failed: {summary.error}; failed_page={summary.failed_page}")
                    if summary.completed_pages > 0:
                        self.export_partial_btn.configure(state=tk.NORMAL)
                    messagebox.showwarning(
                        "Translation stopped",
                        f"Run stopped at page {summary.failed_page}. Partial pages: {summary.completed_pages}",
                    )
            elif event == "error":
                self._set_busy(False)
                self.status_var.set("Error")
                self._append_log(f"Runtime error: {payload}")
                messagebox.showerror("Runtime error", str(payload))
        self.after(120, self._poll_queue)
