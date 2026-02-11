"""Tkinter GUI application."""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .checkpoint import load_run_state, parse_effort, parse_image_mode
from .gui_theme import apply_text_widget_theme
from .output_paths import build_output_paths, require_writable_output_dir_text
from .pdf_text_order import get_page_count
from .types import RunConfig, RunSummary, TargetLang
from .user_settings import load_gui_settings, save_gui_settings
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
        self._details_expanded = False
        self._config_control_states: list[tuple[tk.Widget, str]] = []

        self.pdf_path_var = tk.StringVar()
        self.lang_var = tk.StringVar(value=TargetLang.EN.value)
        self.outdir_var = tk.StringVar()
        self.effort_var = tk.StringVar(value="high")
        self.images_var = tk.StringVar(value="auto")
        self.start_page_var = tk.StringVar(value="1")
        self.end_page_var = tk.StringVar(value="")
        self.max_pages_var = tk.StringVar(value="")
        self.resume_var = tk.BooleanVar(value=True)
        self.page_breaks_var = tk.BooleanVar(value=True)
        self.keep_var = tk.BooleanVar(value=True)
        self.context_file_var = tk.StringVar(value="")
        self.show_advanced_var = tk.BooleanVar(value=False)
        self.details_toggle_text_var = tk.StringVar(value="Show details ▾")
        self.status_var = tk.StringVar(value="Idle")
        self.page_count_var = tk.StringVar(value="Pages: -")

        self._apply_saved_settings(load_gui_settings())

        self._build_ui()
        self._set_details_expanded(False)
        self._bind_var_watchers()
        self.pack(fill=tk.BOTH, expand=True)
        self.master.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_controls()
        self.after(120, self._poll_queue)

    def _apply_saved_settings(self, data: dict[str, object]) -> None:
        outdir_text = str(data.get("last_outdir", "") or "").strip()
        if outdir_text:
            outdir_candidate = Path(outdir_text).expanduser().resolve()
            if outdir_candidate.exists() and outdir_candidate.is_dir():
                self.outdir_var.set(str(outdir_candidate))

        lang = str(data.get("last_lang", TargetLang.EN.value) or TargetLang.EN.value).upper()
        if lang in (TargetLang.EN.value, TargetLang.FR.value, TargetLang.AR.value):
            self.lang_var.set(lang)

        effort = str(data.get("effort", "high") or "high").lower()
        if effort in ("high", "xhigh"):
            self.effort_var.set(effort)

        image_mode = str(data.get("image_mode", "auto") or "auto").lower()
        if image_mode in ("off", "auto", "always"):
            self.images_var.set(image_mode)

        resume = data.get("resume")
        if isinstance(resume, bool):
            self.resume_var.set(resume)
        page_breaks = data.get("page_breaks")
        if isinstance(page_breaks, bool):
            self.page_breaks_var.set(page_breaks)
        keep_intermediates = data.get("keep_intermediates")
        if isinstance(keep_intermediates, bool):
            self.keep_var.set(keep_intermediates)

        start_page = data.get("start_page")
        if isinstance(start_page, int) and start_page > 0:
            self.start_page_var.set(str(start_page))
        end_page = data.get("end_page")
        if isinstance(end_page, int) and end_page > 0:
            self.end_page_var.set(str(end_page))
        max_pages = data.get("max_pages")
        if isinstance(max_pages, int) and max_pages > 0:
            self.max_pages_var.set(str(max_pages))

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)

        ttk.Label(self, text="PDF").grid(row=0, column=0, sticky="w")
        self.pdf_entry = ttk.Entry(self, textvariable=self.pdf_path_var)
        self.pdf_entry.grid(row=0, column=1, sticky="ew", padx=6)
        self.pdf_browse_btn = ttk.Button(self, text="Browse", command=self._pick_pdf)
        self.pdf_browse_btn.grid(row=0, column=2, sticky="ew")
        ttk.Label(self, textvariable=self.page_count_var).grid(row=0, column=3, sticky="w", padx=(8, 0))

        ttk.Label(self, text="Language").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.lang_combo = ttk.Combobox(
            self,
            textvariable=self.lang_var,
            values=[TargetLang.EN.value, TargetLang.FR.value, TargetLang.AR.value],
            state="readonly",
            width=12,
        )
        self.lang_combo.grid(row=1, column=1, sticky="w", padx=6, pady=(8, 0))

        ttk.Label(self, text="Output Folder").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.outdir_entry = ttk.Entry(self, textvariable=self.outdir_var)
        self.outdir_entry.grid(row=2, column=1, sticky="ew", padx=6, pady=(8, 0))
        self.outdir_browse_btn = ttk.Button(self, text="Browse", command=self._pick_outdir)
        self.outdir_browse_btn.grid(row=2, column=2, sticky="ew", pady=(8, 0))

        self.show_advanced_btn = ttk.Checkbutton(
            self,
            text="Show Advanced",
            variable=self.show_advanced_var,
            command=self._toggle_advanced,
        )
        self.show_advanced_btn.grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 0))

        self.advanced = ttk.LabelFrame(self, text="Advanced", padding=8)
        self.advanced.columnconfigure(1, weight=1)

        ttk.Label(self.advanced, text="Reasoning effort").grid(row=0, column=0, sticky="w")
        self.effort_combo = ttk.Combobox(
            self.advanced,
            textvariable=self.effort_var,
            values=["high", "xhigh"],
            state="readonly",
            width=12,
        )
        self.effort_combo.grid(row=0, column=1, sticky="w")

        ttk.Label(self.advanced, text="Image mode").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.images_combo = ttk.Combobox(
            self.advanced,
            textvariable=self.images_var,
            values=["off", "auto", "always"],
            state="readonly",
            width=12,
        )
        self.images_combo.grid(row=1, column=1, sticky="w", pady=(6, 0))

        ttk.Label(self.advanced, text="Start page (1-based)").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.start_page_entry = ttk.Entry(self.advanced, textvariable=self.start_page_var, width=12)
        self.start_page_entry.grid(row=2, column=1, sticky="w", pady=(6, 0))

        ttk.Label(self.advanced, text="End page (blank=last)").grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.end_page_entry = ttk.Entry(self.advanced, textvariable=self.end_page_var, width=12)
        self.end_page_entry.grid(row=3, column=1, sticky="w", pady=(6, 0))

        ttk.Label(self.advanced, text="Max pages (blank=all)").grid(row=4, column=0, sticky="w", pady=(6, 0))
        self.max_pages_entry = ttk.Entry(self.advanced, textvariable=self.max_pages_var, width=12)
        self.max_pages_entry.grid(row=4, column=1, sticky="w", pady=(6, 0))

        self.resume_check = ttk.Checkbutton(self.advanced, text="Resume", variable=self.resume_var)
        self.resume_check.grid(row=5, column=0, sticky="w", pady=(6, 0))
        self.page_breaks_check = ttk.Checkbutton(
            self.advanced,
            text="Insert page breaks",
            variable=self.page_breaks_var,
        )
        self.page_breaks_check.grid(row=5, column=1, sticky="w", pady=(6, 0))
        self.keep_check = ttk.Checkbutton(self.advanced, text="Keep intermediates", variable=self.keep_var)
        self.keep_check.grid(row=6, column=0, sticky="w", pady=(6, 0))

        ttk.Label(self.advanced, text="Context file").grid(row=7, column=0, sticky="w", pady=(6, 0))
        self.context_file_entry = ttk.Entry(self.advanced, textvariable=self.context_file_var)
        self.context_file_entry.grid(row=7, column=1, sticky="ew", pady=(6, 0))
        self.context_browse_btn = ttk.Button(self.advanced, text="Browse", command=self._pick_context)
        self.context_browse_btn.grid(row=7, column=2, sticky="ew", pady=(6, 0), padx=(6, 0))

        ttk.Label(self.advanced, text="Context text").grid(row=8, column=0, sticky="nw", pady=(6, 0))
        self.context_text = scrolledtext.ScrolledText(self.advanced, height=5, wrap=tk.WORD)
        self.context_text.grid(row=8, column=1, columnspan=2, sticky="ew", pady=(6, 0))
        apply_text_widget_theme(self.context_text)

        controls = ttk.Frame(self)
        controls.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        controls.columnconfigure(6, weight=1)

        self.translate_btn = ttk.Button(controls, text="Translate", command=self._start_translation)
        self.translate_btn.grid(row=0, column=0, padx=(0, 6))
        self.cancel_btn = ttk.Button(controls, text="Cancel", command=self._cancel_translation, state=tk.DISABLED)
        self.cancel_btn.grid(row=0, column=1, padx=(0, 6))
        self.new_run_btn = ttk.Button(controls, text="New Run", command=self._new_run)
        self.new_run_btn.grid(row=0, column=2, padx=(0, 6))
        self.export_partial_btn = ttk.Button(
            controls,
            text="Export partial DOCX",
            command=self._export_partial,
            state=tk.DISABLED,
        )
        self.export_partial_btn.grid(row=0, column=3, padx=(0, 6))
        self.rebuild_btn = ttk.Button(controls, text="Rebuild DOCX", command=self._start_rebuild_docx, state=tk.DISABLED)
        self.rebuild_btn.grid(row=0, column=4, padx=(0, 6))
        self.open_outdir_btn = ttk.Button(
            controls,
            text="Open output folder",
            command=self._open_output_folder,
            state=tk.DISABLED,
        )
        self.open_outdir_btn.grid(row=0, column=5, padx=(0, 6))

        self.progress = ttk.Progressbar(self, orient=tk.HORIZONTAL, mode="determinate", maximum=100)
        self.progress.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(10, 0))

        self.status_label = ttk.Label(self, textvariable=self.status_var)
        self.status_label.grid(row=7, column=0, columnspan=4, sticky="w", pady=(6, 0))

        self.details_toggle_btn = ttk.Button(
            self,
            textvariable=self.details_toggle_text_var,
            command=self._toggle_details,
        )
        self.details_toggle_btn.grid(row=8, column=0, columnspan=4, sticky="w", pady=(8, 0))

        self.details_frame = ttk.Frame(self)
        self.details_frame.columnconfigure(0, weight=1)
        self.details_frame.rowconfigure(0, weight=1)
        self.log_text = scrolledtext.ScrolledText(self.details_frame, height=12, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        apply_text_widget_theme(self.log_text)

        self._config_control_states = [
            (self.pdf_entry, tk.NORMAL),
            (self.pdf_browse_btn, tk.NORMAL),
            (self.lang_combo, "readonly"),
            (self.outdir_entry, tk.NORMAL),
            (self.outdir_browse_btn, tk.NORMAL),
            (self.show_advanced_btn, tk.NORMAL),
            (self.effort_combo, "readonly"),
            (self.images_combo, "readonly"),
            (self.start_page_entry, tk.NORMAL),
            (self.end_page_entry, tk.NORMAL),
            (self.max_pages_entry, tk.NORMAL),
            (self.resume_check, tk.NORMAL),
            (self.page_breaks_check, tk.NORMAL),
            (self.keep_check, tk.NORMAL),
            (self.context_file_entry, tk.NORMAL),
            (self.context_browse_btn, tk.NORMAL),
        ]

    def _bind_var_watchers(self) -> None:
        self.pdf_path_var.trace_add("write", self._on_form_input_changed)
        self.lang_var.trace_add("write", self._on_setting_changed)
        self.outdir_var.trace_add("write", self._on_setting_changed)
        self.effort_var.trace_add("write", self._on_setting_changed)
        self.images_var.trace_add("write", self._on_setting_changed)
        self.resume_var.trace_add("write", self._on_setting_changed)
        self.page_breaks_var.trace_add("write", self._on_setting_changed)
        self.keep_var.trace_add("write", self._on_setting_changed)
        self.start_page_var.trace_add("write", self._on_setting_changed)
        self.end_page_var.trace_add("write", self._on_setting_changed)
        self.max_pages_var.trace_add("write", self._on_setting_changed)

    def _on_form_input_changed(self, *_: object) -> None:
        self._refresh_controls()

    def _on_setting_changed(self, *_: object) -> None:
        self._persist_gui_settings()
        self._refresh_controls()

    def _toggle_advanced(self) -> None:
        if self.show_advanced_var.get():
            self.advanced.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        else:
            self.advanced.grid_forget()

    def _toggle_details(self) -> None:
        self._set_details_expanded(not self._details_expanded)

    def _set_details_expanded(self, expanded: bool) -> None:
        self._details_expanded = expanded
        if expanded:
            self.details_toggle_text_var.set("Hide details ▴")
            self.details_frame.grid(row=9, column=0, columnspan=4, sticky="nsew", pady=(8, 0))
            self.rowconfigure(9, weight=1)
        else:
            self.details_toggle_text_var.set("Show details ▾")
            self.details_frame.grid_forget()
            self.rowconfigure(9, weight=0)

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

    def _clear_log(self) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _parse_required_int(self, value: str, field_name: str) -> int:
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an integer.") from exc

    def _parse_optional_int(self, value: str, field_name: str) -> int | None:
        cleaned = value.strip()
        if cleaned == "":
            return None
        try:
            return int(cleaned)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an integer.") from exc

    def _build_config(self) -> RunConfig:
        pdf_text = self.pdf_path_var.get().strip()
        if not pdf_text:
            raise ValueError("PDF path is required.")
        outdir_text = self.outdir_var.get().strip()

        pdf = Path(pdf_text).expanduser().resolve()
        outdir = require_writable_output_dir_text(outdir_text)
        lang = TargetLang(self.lang_var.get().strip())

        start_text = self.start_page_var.get().strip() or "1"
        start_page = self._parse_required_int(start_text, "Start page")
        end_page = self._parse_optional_int(self.end_page_var.get(), "End page")
        max_pages = self._parse_optional_int(self.max_pages_var.get(), "Max pages")

        context_file_text = self.context_file_var.get().strip()
        context_file = Path(context_file_text).expanduser().resolve() if context_file_text else None
        context_text = self.context_text.get("1.0", tk.END).strip() or None

        return RunConfig(
            pdf_path=pdf,
            output_dir=outdir,
            target_lang=lang,
            effort=parse_effort(self.effort_var.get()),
            image_mode=parse_image_mode(self.images_var.get()),
            start_page=start_page,
            end_page=end_page,
            max_pages=max_pages,
            resume=self.resume_var.get(),
            page_breaks=self.page_breaks_var.get(),
            keep_intermediates=self.keep_var.get(),
            context_file=context_file,
            context_text=context_text,
        )

    def _set_config_controls_enabled(self, enabled: bool) -> None:
        for widget, enabled_state in self._config_control_states:
            if enabled:
                widget.configure(state=enabled_state)
            else:
                widget.configure(state=tk.DISABLED)
        self.context_text.configure(state=tk.NORMAL if enabled else tk.DISABLED)

    def _set_busy(self, busy: bool, *, translation: bool) -> None:
        self._busy = busy
        self._running_translation = busy and translation
        self._set_config_controls_enabled(not busy)
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
        self.new_run_btn.configure(state=tk.NORMAL if not self._busy else tk.DISABLED)
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

    def _new_queue(self) -> "queue.Queue[tuple[str, object]]":
        self.queue = queue.Queue()
        return self.queue

    def _start_translation(self) -> None:
        try:
            config = self._build_config()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Invalid configuration", str(exc))
            return

        self._persist_gui_settings()
        self.last_summary = None
        self.last_output_docx = None
        self._can_export_partial = False
        self._set_busy(True, translation=True)
        self.progress.configure(value=0)
        self.status_var.set("Starting...")

        run_queue = self._new_queue()

        def log_callback(message: str) -> None:
            run_queue.put(("log", message))

        def progress_callback(page: int, total: int, status: str) -> None:
            run_queue.put(("progress", (page, total, status)))

        workflow = TranslationWorkflow(log_callback=log_callback, progress_callback=progress_callback)
        self.workflow = workflow

        def target() -> None:
            try:
                summary = workflow.run(config)
                run_queue.put(("done", summary))
            except Exception as exc:  # noqa: BLE001
                run_queue.put(("error", str(exc)))

        self.worker = threading.Thread(target=target, daemon=True)
        self.worker.start()

    def _start_rebuild_docx(self) -> None:
        try:
            config = self._build_config()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Invalid configuration", str(exc))
            return

        self._persist_gui_settings()
        self._set_busy(True, translation=False)
        self.status_var.set("Rebuilding DOCX...")

        run_queue = self._new_queue()

        def log_callback(message: str) -> None:
            run_queue.put(("log", message))

        workflow = TranslationWorkflow(log_callback=log_callback)
        self.workflow = workflow

        def target() -> None:
            try:
                rebuilt = workflow.rebuild_docx(config)
                run_queue.put(("rebuild_done", rebuilt))
            except Exception as exc:  # noqa: BLE001
                run_queue.put(("rebuild_error", str(exc)))

        self.worker = threading.Thread(target=target, daemon=True)
        self.worker.start()

    def _cancel_translation(self) -> None:
        if self.workflow is not None and self._running_translation:
            self.workflow.cancel()
            self._append_log("Cancellation requested.")

    def _new_run(self) -> None:
        if self._busy:
            return
        self.last_summary = None
        self.last_output_docx = None
        self._can_export_partial = False
        self.workflow = None
        self.worker = None
        self._new_queue()
        self.progress.configure(value=0)
        self.status_var.set("Idle")
        self._clear_log()
        self._set_details_expanded(False)
        self._persist_gui_settings()
        self._refresh_controls()

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

    def _open_output_file(self) -> None:
        if self.last_output_docx is None:
            return
        output_path = self.last_output_docx.expanduser().resolve()
        if not output_path.exists():
            messagebox.showerror("Open file failed", f"Output file not found:\n{output_path}")
            return
        try:
            if os.name == "nt":
                os.startfile(str(output_path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(output_path)])
            else:
                subprocess.Popen(["xdg-open", str(output_path)])
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Open file failed", str(exc))

    def _show_saved_docx_dialog(self, title: str) -> None:
        if self.last_output_docx is None:
            return
        open_now = messagebox.askyesno(title, f"Saved DOCX:\n{self.last_output_docx}\n\nOpen file now?")
        if open_now:
            self._open_output_file()

    def _int_from_text(self, value: str, *, allow_blank: bool, default: int | None = None) -> int | None:
        cleaned = value.strip()
        if cleaned == "":
            return default if allow_blank else None
        try:
            return int(cleaned)
        except ValueError:
            return default if allow_blank else None

    def _persist_gui_settings(self) -> None:
        outdir_text = self.outdir_var.get().strip()
        if outdir_text:
            try:
                outdir_text = str(Path(outdir_text).expanduser().resolve())
            except Exception:
                pass

        start_page = self._int_from_text(self.start_page_var.get(), allow_blank=True, default=1)
        if start_page is None or start_page <= 0:
            start_page = 1
        end_page = self._int_from_text(self.end_page_var.get(), allow_blank=True, default=None)
        max_pages = self._int_from_text(self.max_pages_var.get(), allow_blank=True, default=None)

        try:
            save_gui_settings(
                {
                    "last_outdir": outdir_text,
                    "last_lang": self.lang_var.get().strip().upper(),
                    "effort": self.effort_var.get().strip().lower(),
                    "image_mode": self.images_var.get().strip().lower(),
                    "resume": bool(self.resume_var.get()),
                    "keep_intermediates": bool(self.keep_var.get()),
                    "page_breaks": bool(self.page_breaks_var.get()),
                    "start_page": start_page,
                    "end_page": end_page,
                    "max_pages": max_pages,
                }
            )
        except Exception:
            pass

    def _on_close(self) -> None:
        self._persist_gui_settings()
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
                if int(total) > 0:
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
                    self._show_saved_docx_dialog("Translation complete")
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
                self._show_saved_docx_dialog("Rebuild complete")
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
