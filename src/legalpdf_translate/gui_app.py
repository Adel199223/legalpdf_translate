"""Tkinter GUI application."""

from __future__ import annotations

import queue
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .checkpoint import load_run_state, parse_effort, parse_image_mode
from .output_paths import build_output_paths, require_writable_output_dir_text
from .pdf_text_order import get_page_count
from .types import RunConfig, RunSummary, TargetLang
from .user_settings import load_last_outdir, save_last_outdir
from .workflow import TranslationWorkflow


class LegalPDFTranslateApp(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=12)
        self.master = master
        self.queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self.workflow: TranslationWorkflow | None = None
        self.worker: threading.Thread | None = None
        self.last_summary: RunSummary | None = None
        self.last_output_docx: Path | None = None

        self._busy = False
        self._running_translation = False
        self._can_export_partial = False

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

        last_outdir = load_last_outdir()
        if last_outdir is not None:
            self.outdir_var.set(str(last_outdir))

        self._build_ui()
        self._bind_var_watchers()
        self.pack(fill=tk.BOTH, expand=True)
        self.master.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_controls()
        self.after(120, self._poll_queue)

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)

        ttk.Label(self, text="PDF").grid(row=0, column=0, sticky="w")
        self.pdf_entry = ttk.Entry(self, textvariable=self.pdf_path_var)
        self.pdf_entry.grid(row=0, column=1, sticky="ew", padx=6)
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
        self.outdir_entry = ttk.Entry(self, textvariable=self.outdir_var)
        self.outdir_entry.grid(row=2, column=1, sticky="ew", padx=6, pady=(8, 0))
        self.outdir_browse_btn = ttk.Button(self, text="Browse", command=self._pick_outdir)
        self.outdir_browse_btn.grid(row=2, column=2, sticky="ew", pady=(8, 0))

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
        controls.columnconfigure(5, weight=1)

        self.translate_btn = ttk.Button(controls, text="Translate", command=self._start_translation)
        self.translate_btn.grid(row=0, column=0, padx=(0, 6))
        self.cancel_btn = ttk.Button(controls, text="Cancel", command=self._cancel_translation, state=tk.DISABLED)
        self.cancel_btn.grid(row=0, column=1, padx=(0, 6))
        self.export_partial_btn = ttk.Button(
            controls, text="Export partial DOCX", command=self._export_partial, state=tk.DISABLED
        )
        self.export_partial_btn.grid(row=0, column=2, padx=(0, 6))
        self.rebuild_btn = ttk.Button(controls, text="Rebuild DOCX", command=self._start_rebuild_docx, state=tk.DISABLED)
        self.rebuild_btn.grid(row=0, column=3, padx=(0, 6))
        self.open_outdir_btn = ttk.Button(
            controls,
            text="Open output folder",
            command=self._open_output_folder,
            state=tk.DISABLED,
        )
        self.open_outdir_btn.grid(row=0, column=4, padx=(0, 6))

        self.progress = ttk.Progressbar(self, orient=tk.HORIZONTAL, mode="determinate", maximum=100)
        self.progress.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Label(self, textvariable=self.status_var).grid(row=7, column=0, columnspan=3, sticky="w", pady=(6, 0))

        self.log_text = scrolledtext.ScrolledText(self, height=12, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.grid(row=8, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        self.rowconfigure(8, weight=1)

    def _bind_var_watchers(self) -> None:
        self.pdf_path_var.trace_add("write", self._on_form_input_changed)
        self.lang_var.trace_add("write", self._on_form_input_changed)
        self.outdir_var.trace_add("write", self._on_outdir_changed)

    def _on_form_input_changed(self, *_: object) -> None:
        self._refresh_controls()

    def _on_outdir_changed(self, *_: object) -> None:
        self._persist_outdir_setting()
        self._refresh_controls()

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
        pdf_text = self.pdf_path_var.get().strip()
        if not pdf_text:
            raise ValueError("PDF path is required.")
        outdir_text = self.outdir_var.get().strip()

        pdf = Path(pdf_text).expanduser().resolve()
        outdir = require_writable_output_dir_text(outdir_text)
        lang = TargetLang(self.lang_var.get().strip())

        max_pages_text = self.max_pages_var.get().strip()
        max_pages = int(max_pages_text) if max_pages_text else None
        context_file_text = self.context_file_var.get().strip()
        context_file = Path(context_file_text).expanduser().resolve() if context_file_text else None
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

    def _set_busy(self, busy: bool, *, translation: bool) -> None:
        self._busy = busy
        self._running_translation = busy and translation
        self.outdir_entry.configure(state=tk.DISABLED if busy else tk.NORMAL)
        self.outdir_browse_btn.configure(state=tk.DISABLED if busy else tk.NORMAL)
        self._refresh_controls()

    def _can_start_translation(self) -> bool:
        pdf_text = self.pdf_path_var.get().strip()
        outdir_text = self.outdir_var.get().strip()
        if not pdf_text or not outdir_text:
            return False
        pdf_path = Path(pdf_text).expanduser().resolve()
        if not pdf_path.exists():
            return False
        try:
            require_writable_output_dir_text(outdir_text)
        except ValueError:
            return False
        return True

    def _rebuild_pages_dir(self) -> Path | None:
        pdf_text = self.pdf_path_var.get().strip()
        outdir_text = self.outdir_var.get().strip()
        if not pdf_text or not outdir_text:
            return None

        outdir = Path(outdir_text).expanduser().resolve()
        if not outdir.exists() or not outdir.is_dir():
            return None
        pdf = Path(pdf_text).expanduser().resolve()
        try:
            lang = TargetLang(self.lang_var.get().strip())
        except ValueError:
            return None

        paths = build_output_paths(outdir, pdf, lang)
        state = load_run_state(paths.run_state_path)
        if state is not None and state.run_dir_abs:
            run_dir = Path(state.run_dir_abs).expanduser().resolve()
            return run_dir / "pages"
        return paths.pages_dir

    def _has_rebuildable_pages(self) -> bool:
        pages_dir = self._rebuild_pages_dir()
        if pages_dir is None or not pages_dir.exists():
            return False
        return any(pages_dir.glob("page_*.txt"))

    def _refresh_controls(self) -> None:
        can_start = self._can_start_translation()
        self.translate_btn.configure(state=tk.NORMAL if (not self._busy and can_start) else tk.DISABLED)
        self.cancel_btn.configure(state=tk.NORMAL if self._running_translation else tk.DISABLED)
        self.export_partial_btn.configure(
            state=tk.NORMAL if (not self._busy and self._can_export_partial) else tk.DISABLED
        )
        self.rebuild_btn.configure(
            state=tk.NORMAL if (not self._busy and self._has_rebuildable_pages()) else tk.DISABLED
        )

        can_open = (
            not self._busy
            and self.last_output_docx is not None
            and self.last_output_docx.exists()
            and self.last_output_docx.stat().st_size > 0
        )
        self.open_outdir_btn.configure(state=tk.NORMAL if can_open else tk.DISABLED)

    def _start_translation(self) -> None:
        try:
            config = self._build_config()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Invalid configuration", str(exc))
            return

        self._persist_outdir_setting()
        self.last_summary = None
        self.last_output_docx = None
        self._can_export_partial = False
        self._set_busy(True, translation=True)
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

    def _start_rebuild_docx(self) -> None:
        try:
            config = self._build_config()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Invalid configuration", str(exc))
            return

        self._persist_outdir_setting()
        self._set_busy(True, translation=False)
        self.status_var.set("Rebuilding DOCX...")

        def log_callback(message: str) -> None:
            self.queue.put(("log", message))

        self.workflow = TranslationWorkflow(log_callback=log_callback)

        def target() -> None:
            try:
                rebuilt = self.workflow.rebuild_docx(config)
                self.queue.put(("rebuild_done", rebuilt))
            except Exception as exc:  # noqa: BLE001
                self.queue.put(("rebuild_error", str(exc)))

        self.worker = threading.Thread(target=target, daemon=True)
        self.worker.start()

    def _cancel_translation(self) -> None:
        if self.workflow is not None and self._running_translation:
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
        if self.last_output_docx is None:
            return
        output_path = self.last_output_docx.expanduser().resolve()
        if not output_path.exists():
            messagebox.showerror("Open folder failed", f"Output file not found:\n{output_path}")
            return
        try:
            subprocess.Popen(["explorer", f"/select,{output_path}"])
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Open folder failed", str(exc))

    def _persist_outdir_setting(self) -> None:
        outdir_text = self.outdir_var.get().strip()
        if not outdir_text:
            return
        candidate = Path(outdir_text).expanduser().resolve()
        if candidate.exists() and candidate.is_dir():
            try:
                save_last_outdir(candidate)
            except Exception:
                pass

    def _on_close(self) -> None:
        self._persist_outdir_setting()
        self.master.destroy()

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
                self._set_busy(False, translation=False)
                if summary.success and summary.output_docx is not None:
                    self.last_output_docx = summary.output_docx.expanduser().resolve()
                    self.status_var.set("Completed")
                    self._append_log(f"Saved DOCX: {self.last_output_docx}")
                    messagebox.showinfo("Translation complete", f"Saved DOCX:\n{self.last_output_docx}")
                else:
                    self.last_output_docx = None
                    self.status_var.set(f"Failed ({summary.error})")
                    self._append_log(f"Run failed: {summary.error}; failed_page={summary.failed_page}")
                    if summary.error == "docx_write_failed" and summary.attempted_output_docx is not None:
                        self._append_log(f"DOCX save failed at: {summary.attempted_output_docx}")
                    self._can_export_partial = summary.completed_pages > 0
                    details = (
                        f"Run stopped at page {summary.failed_page}. "
                        f"Partial pages: {summary.completed_pages}"
                    )
                    if summary.error == "docx_write_failed" and summary.attempted_output_docx is not None:
                        details = (
                            f"DOCX save failed at:\n{summary.attempted_output_docx}\n\n"
                            f"Partial pages: {summary.completed_pages}"
                        )
                    messagebox.showwarning("Translation stopped", details)
                self._refresh_controls()
            elif event == "rebuild_done":
                rebuilt = payload  # type: ignore[assignment]
                self._set_busy(False, translation=False)
                self.last_output_docx = rebuilt.expanduser().resolve()
                self.status_var.set("Completed")
                self._append_log(f"Saved DOCX: {self.last_output_docx}")
                messagebox.showinfo("Rebuild complete", f"Saved DOCX:\n{self.last_output_docx}")
                self._refresh_controls()
            elif event == "rebuild_error":
                self._set_busy(False, translation=False)
                self.status_var.set("Rebuild failed")
                self._append_log(f"Rebuild failed: {payload}")
                messagebox.showerror("Rebuild failed", str(payload))
            elif event == "error":
                self._set_busy(False, translation=False)
                self.status_var.set("Error")
                self._append_log(f"Runtime error: {payload}")
                messagebox.showerror("Runtime error", str(payload))
        self.after(120, self._poll_queue)
