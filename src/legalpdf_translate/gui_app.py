"""Tkinter GUI application."""

from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from openai import OpenAI

from .__init__ import __version__
from .checkpoint import (
    load_run_state,
    parse_effort,
    parse_effort_policy,
    parse_image_mode,
    parse_ocr_engine_policy,
    parse_ocr_mode,
)
from .config import OPENAI_MODEL
from .gui_settings_dialog import GuiSettingsDialog
from .gui_theme import apply_text_widget_theme, apply_theme
from .joblog_db import job_log_db_path
from .joblog_ui import JobLogSeed, JobLogWindow, SaveToJobLogDialog, build_seed_from_run
from .metadata_autofill import extract_pdf_header_metadata, metadata_config_from_settings
from .openai_client import OpenAIResponsesClient
from .output_paths import build_output_paths, require_writable_output_dir_text
from .pdf_text_order import get_page_count
from .secrets_store import (
    delete_openai_key,
    delete_ocr_key,
    get_openai_key,
    get_ocr_key,
)
from .types import AnalyzeSummary, EffortPolicy, RunConfig, RunSummary, TargetLang
from .ui_assets import load_image
from .user_settings import app_data_dir, load_gui_settings, load_joblog_settings, save_gui_settings, settings_path
from .workflow import TranslationWorkflow

_PAGE_LOG_RE = re.compile(
    r"page=(?P<page>\d+)\s+image_used=(?P<image>True|False)\s+retry_used=(?P<retry>True|False)\s+status=(?P<status>[a-z_]+)"
)


class LegalPDFTranslateApp(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=12)
        self.master = master
        self.queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self.workflow: TranslationWorkflow | None = None
        self.worker: threading.Thread | None = None
        self.last_summary: RunSummary | None = None
        self.last_output_docx: Path | None = None
        self.last_run_config: RunConfig | None = None
        self.last_joblog_seed: JobLogSeed | None = None
        self.last_run_report_path: Path | None = None
        self.joblog_window: JobLogWindow | None = None
        self.settings_window: tk.Toplevel | None = None
        self.joblog_db_path = job_log_db_path()
        self.settings_data = load_gui_settings()
        self._session_started_at = datetime.now()
        self._metadata_logs_dir = app_data_dir() / "logs"
        self._metadata_logs_dir.mkdir(parents=True, exist_ok=True)
        self._metadata_log_file = self._metadata_logs_dir / (
            f"session_{self._session_started_at.strftime('%Y%m%d_%H%M%S')}.log"
        )
        self._menu_file: tk.Menu | None = None
        self._menu_tools: tk.Menu | None = None
        self._menu_help: tk.Menu | None = None
        self._bg_label: tk.Label | None = None
        self._header_label: tk.Label | None = None
        self._left_deco_label: tk.Label | None = None
        self._right_deco_label: tk.Label | None = None
        self._header_title_label: tk.Label | None = None
        self._content_frame: ttk.Frame | None = None
        self._bg_image: object | None = None
        self._header_image: object | None = None
        self._left_deco_image: object | None = None
        self._right_deco_image: object | None = None
        self._last_visual_size: tuple[int, int] | None = None

        self._busy = False
        self._running_translation = False
        self._can_export_partial = False
        self._details_expanded = False
        self._config_control_states: list[tuple[tk.Widget, str]] = []
        self._progress_done_pages = 0
        self._progress_total_pages = 0
        self._image_pages_seen: set[int] = set()
        self._retry_pages_seen: set[int] = set()

        self.pdf_path_var = tk.StringVar()
        self.lang_var = tk.StringVar(value=TargetLang.EN.value)
        self.outdir_var = tk.StringVar()
        self.effort_var = tk.StringVar(value="high")
        self.effort_policy_var = tk.StringVar(value="adaptive")
        self.images_var = tk.StringVar(value="off")
        self.ocr_mode_var = tk.StringVar(value="auto")
        self.ocr_engine_var = tk.StringVar(value="local_then_api")
        self.ocr_api_base_url_var = tk.StringVar(value="")
        self.ocr_api_model_var = tk.StringVar(value="")
        self.ocr_api_key_env_name_var = tk.StringVar(value="DEEPSEEK_API_KEY")
        self.start_page_var = tk.StringVar(value="1")
        self.end_page_var = tk.StringVar(value="")
        self.max_pages_var = tk.StringVar(value="")
        self.workers_var = tk.StringVar(value="3")
        self.resume_var = tk.BooleanVar(value=True)
        self.page_breaks_var = tk.BooleanVar(value=True)
        self.keep_var = tk.BooleanVar(value=True)
        self.context_file_var = tk.StringVar(value="")
        self.show_advanced_var = tk.BooleanVar(value=False)
        self.details_toggle_text_var = tk.StringVar(value="Show details ▾")
        self.status_var = tk.StringVar(value="Idle")
        self.page_count_var = tk.StringVar(value="Pages: -")
        self.live_counters_var = tk.StringVar(value="Done 0/0 | Images 0 | Retries 0")

        self._apply_saved_settings(self.settings_data)
        self._apply_theme_from_settings(self.settings_data)

        self._build_ui()
        self._install_menu()
        self._set_details_expanded(False)
        self._bind_var_watchers()
        self.pack(fill=tk.BOTH, expand=True)
        self.master.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_controls()
        self.after(120, self._poll_queue)

    def _apply_saved_settings(self, data: dict[str, object]) -> None:
        outdir_text = str(data.get("last_outdir", data.get("default_outdir", "")) or "").strip()
        if outdir_text:
            outdir_candidate = Path(outdir_text).expanduser().resolve()
            if outdir_candidate.exists() and outdir_candidate.is_dir():
                self.outdir_var.set(str(outdir_candidate))

        lang = str(data.get("default_lang", data.get("last_lang", TargetLang.EN.value)) or TargetLang.EN.value).upper()
        if lang in (TargetLang.EN.value, TargetLang.FR.value, TargetLang.AR.value):
            self.lang_var.set(lang)

        effort = str(data.get("default_effort", data.get("effort", "high")) or "high").lower()
        if effort in ("high", "xhigh"):
            self.effort_var.set(effort)

        effort_policy = str(
            data.get("default_effort_policy", data.get("effort_policy", "adaptive")) or "adaptive"
        ).lower()
        if effort_policy in ("adaptive", "fixed_high", "fixed_xhigh"):
            self.effort_policy_var.set(effort_policy)

        image_mode = str(data.get("default_images_mode", data.get("image_mode", "off")) or "off").lower()
        if image_mode in ("off", "auto", "always"):
            self.images_var.set(image_mode)
        ocr_mode = str(data.get("ocr_mode_default", data.get("ocr_mode", "auto")) or "auto").lower()
        if ocr_mode in ("off", "auto", "always"):
            self.ocr_mode_var.set(ocr_mode)
        ocr_engine = str(data.get("ocr_engine_default", data.get("ocr_engine", "local_then_api")) or "local_then_api").lower()
        if ocr_engine in ("local", "local_then_api", "api"):
            self.ocr_engine_var.set(ocr_engine)
        self.ocr_api_base_url_var.set(str(data.get("ocr_api_base_url", "") or ""))
        self.ocr_api_model_var.set(str(data.get("ocr_api_model", "") or ""))
        self.ocr_api_key_env_name_var.set(
            str(
                data.get(
                    "ocr_api_key_env_name",
                    data.get("ocr_api_key_env", "DEEPSEEK_API_KEY"),
                )
                or "DEEPSEEK_API_KEY"
            )
        )

        resume = data.get("default_resume", data.get("resume"))
        if isinstance(resume, bool):
            self.resume_var.set(resume)
        page_breaks = data.get("default_page_breaks", data.get("page_breaks"))
        if isinstance(page_breaks, bool):
            self.page_breaks_var.set(page_breaks)
        keep_intermediates = data.get("default_keep_intermediates", data.get("keep_intermediates"))
        if isinstance(keep_intermediates, bool):
            self.keep_var.set(keep_intermediates)

        start_page = data.get("default_start_page", data.get("start_page"))
        if isinstance(start_page, int) and start_page > 0:
            self.start_page_var.set(str(start_page))
        end_page = data.get("default_end_page", data.get("end_page"))
        if isinstance(end_page, int) and end_page > 0:
            self.end_page_var.set(str(end_page))
        max_pages = data.get("max_pages")
        if isinstance(max_pages, int) and max_pages > 0:
            self.max_pages_var.set(str(max_pages))
        workers = data.get("workers", data.get("default_workers", 3))
        try:
            workers_int = int(workers)  # type: ignore[arg-type]
        except Exception:
            workers_int = 3
        workers_int = max(1, min(6, workers_int))
        self.workers_var.set(str(workers_int))

    def _apply_theme_from_settings(self, settings: dict[str, object] | None = None) -> None:
        effective = settings if settings is not None else self.settings_data
        theme_name = str(effective.get("ui_theme", "dark_futuristic") or "dark_futuristic")
        scale_raw = effective.get("ui_scale", 1.0)
        try:
            ui_scale = float(scale_raw)
        except (TypeError, ValueError):
            ui_scale = 1.0
        palette = apply_theme(self.master, theme_name=theme_name, ui_scale=ui_scale)
        if self._header_title_label is not None:
            title_size = max(15, int(round(16 * ui_scale)))
            self._header_title_label.configure(
                bg=palette["bg"],
                fg=palette["accent"],
                font=("Segoe UI Semibold", title_size),
            )
        if hasattr(self, "context_text"):
            apply_text_widget_theme(self.context_text, palette)
        if hasattr(self, "log_text"):
            apply_text_widget_theme(self.log_text, palette)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._bg_label = tk.Label(self, bd=0, highlightthickness=0)
        self._bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        self._header_label = tk.Label(self, bd=0, highlightthickness=0)
        self._header_label.place(x=0, y=8)
        self._left_deco_label = tk.Label(self, bd=0, highlightthickness=0)
        self._left_deco_label.place(x=0, y=90)
        self._right_deco_label = tk.Label(self, bd=0, highlightthickness=0)
        self._right_deco_label.place(x=0, y=90)
        self._header_title_label = tk.Label(
            self,
            text="LegalPDF Translate",
            fg="#9EE6FF",
            bg="#0A1830",
            anchor="w",
            padx=16,
            font=("Segoe UI Semibold", 18),
        )
        self._header_title_label.place(x=42, y=20)

        content = ttk.Frame(self, style="Surface.TFrame", padding=(12, 12, 12, 12))
        content.grid(row=1, column=0, sticky="nsew", padx=(22, 22), pady=(72, 12))
        self._content_frame = content
        content.columnconfigure(1, weight=1)

        ttk.Label(content, text="PDF").grid(row=0, column=0, sticky="w")
        self.pdf_entry = ttk.Entry(content, textvariable=self.pdf_path_var)
        self.pdf_entry.grid(row=0, column=1, sticky="ew", padx=6)
        self.pdf_browse_btn = ttk.Button(content, text="Browse", command=self._pick_pdf)
        self.pdf_browse_btn.grid(row=0, column=2, sticky="ew")
        ttk.Label(content, textvariable=self.page_count_var, style="Muted.TLabel").grid(row=0, column=3, sticky="w", padx=(8, 0))

        ttk.Label(content, text="Language").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.lang_combo = ttk.Combobox(
            content,
            textvariable=self.lang_var,
            values=[TargetLang.EN.value, TargetLang.FR.value, TargetLang.AR.value],
            state="readonly",
            width=12,
        )
        self.lang_combo.grid(row=1, column=1, sticky="w", padx=6, pady=(8, 0))

        ttk.Label(content, text="Output Folder").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.outdir_entry = ttk.Entry(content, textvariable=self.outdir_var)
        self.outdir_entry.grid(row=2, column=1, sticky="ew", padx=6, pady=(8, 0))
        self.outdir_browse_btn = ttk.Button(content, text="Browse", command=self._pick_outdir)
        self.outdir_browse_btn.grid(row=2, column=2, sticky="ew", pady=(8, 0))

        self.show_advanced_btn = ttk.Checkbutton(
            content,
            text="Show Advanced",
            variable=self.show_advanced_var,
            command=self._toggle_advanced,
        )
        self.show_advanced_btn.grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 0))
        self.settings_btn = ttk.Button(content, text="Settings...", command=self._open_settings_dialog, style="Secondary.TButton")
        self.settings_btn.grid(row=3, column=3, sticky="e", pady=(10, 0))

        self.advanced = ttk.LabelFrame(content, text="Advanced", padding=8, style="Surface.TLabelframe")
        self.advanced.columnconfigure(1, weight=1)

        ttk.Label(self.advanced, text="Effort policy").grid(row=0, column=0, sticky="w")
        self.effort_policy_combo = ttk.Combobox(
            self.advanced,
            textvariable=self.effort_policy_var,
            values=["adaptive", "fixed_high", "fixed_xhigh"],
            state="readonly",
            width=12,
        )
        self.effort_policy_combo.grid(row=0, column=1, sticky="w")

        ttk.Label(self.advanced, text="Reasoning effort").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.effort_combo = ttk.Combobox(
            self.advanced,
            textvariable=self.effort_var,
            values=["high", "xhigh"],
            state="readonly",
            width=12,
        )
        self.effort_combo.grid(row=1, column=1, sticky="w", pady=(6, 0))

        ttk.Label(self.advanced, text="Image mode").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.images_combo = ttk.Combobox(
            self.advanced,
            textvariable=self.images_var,
            values=["off", "auto", "always"],
            state="readonly",
            width=12,
        )
        self.images_combo.grid(row=2, column=1, sticky="w", pady=(6, 0))

        ttk.Label(self.advanced, text="Start page (1-based)").grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.start_page_entry = ttk.Entry(self.advanced, textvariable=self.start_page_var, width=12)
        self.start_page_entry.grid(row=3, column=1, sticky="w", pady=(6, 0))

        ttk.Label(self.advanced, text="End page (blank=last)").grid(row=4, column=0, sticky="w", pady=(6, 0))
        self.end_page_entry = ttk.Entry(self.advanced, textvariable=self.end_page_var, width=12)
        self.end_page_entry.grid(row=4, column=1, sticky="w", pady=(6, 0))

        ttk.Label(self.advanced, text="Max pages (blank=all)").grid(row=5, column=0, sticky="w", pady=(6, 0))
        self.max_pages_entry = ttk.Entry(self.advanced, textvariable=self.max_pages_var, width=12)
        self.max_pages_entry.grid(row=5, column=1, sticky="w", pady=(6, 0))

        ttk.Label(self.advanced, text="Parallel workers").grid(row=6, column=0, sticky="w", pady=(6, 0))
        self.workers_combo = ttk.Combobox(
            self.advanced,
            textvariable=self.workers_var,
            values=["1", "2", "3", "4", "5", "6"],
            state="readonly",
            width=12,
        )
        self.workers_combo.grid(row=6, column=1, sticky="w", pady=(6, 0))

        self.resume_check = ttk.Checkbutton(self.advanced, text="Resume", variable=self.resume_var)
        self.resume_check.grid(row=7, column=0, sticky="w", pady=(6, 0))
        self.page_breaks_check = ttk.Checkbutton(
            self.advanced,
            text="Insert page breaks",
            variable=self.page_breaks_var,
        )
        self.page_breaks_check.grid(row=7, column=1, sticky="w", pady=(6, 0))
        self.keep_check = ttk.Checkbutton(self.advanced, text="Keep intermediates", variable=self.keep_var)
        self.keep_check.grid(row=8, column=0, sticky="w", pady=(6, 0))

        ttk.Label(self.advanced, text="Context file").grid(row=9, column=0, sticky="w", pady=(6, 0))
        self.context_file_entry = ttk.Entry(self.advanced, textvariable=self.context_file_var)
        self.context_file_entry.grid(row=9, column=1, sticky="ew", pady=(6, 0))
        self.context_browse_btn = ttk.Button(self.advanced, text="Browse", command=self._pick_context)
        self.context_browse_btn.grid(row=9, column=2, sticky="ew", pady=(6, 0), padx=(6, 0))

        ttk.Label(self.advanced, text="Context text").grid(row=10, column=0, sticky="nw", pady=(6, 0))
        self.context_text = scrolledtext.ScrolledText(self.advanced, height=5, wrap=tk.WORD)
        self.context_text.grid(row=10, column=1, columnspan=2, sticky="ew", pady=(6, 0))
        apply_text_widget_theme(self.context_text)

        ttk.Label(self.advanced, text="OCR mode").grid(row=11, column=0, sticky="w", pady=(6, 0))
        self.ocr_mode_combo = ttk.Combobox(
            self.advanced,
            textvariable=self.ocr_mode_var,
            values=["off", "auto", "always"],
            state="readonly",
            width=18,
        )
        self.ocr_mode_combo.grid(row=11, column=1, sticky="w", pady=(6, 0))

        ttk.Label(self.advanced, text="OCR engine").grid(row=12, column=0, sticky="w", pady=(6, 0))
        self.ocr_engine_combo = ttk.Combobox(
            self.advanced,
            textvariable=self.ocr_engine_var,
            values=["local", "local_then_api", "api"],
            state="readonly",
            width=18,
        )
        self.ocr_engine_combo.grid(row=12, column=1, sticky="w", pady=(6, 0))
        self.analyze_btn = ttk.Button(
            self.advanced,
            text="Analyze",
            command=self._start_analyze,
            style="Secondary.TButton",
        )
        self.analyze_btn.grid(row=12, column=2, sticky="e", padx=(6, 0), pady=(6, 0))

        controls = ttk.Frame(content, style="Surface.TFrame")
        controls.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        controls.columnconfigure(10, weight=1)

        self.translate_btn = ttk.Button(controls, text="Translate", command=self._start_translation, style="Primary.TButton")
        self.translate_btn.grid(row=0, column=0, padx=(0, 6))
        self.cancel_btn = ttk.Button(controls, text="Cancel", command=self._cancel_translation, state=tk.DISABLED, style="Secondary.TButton")
        self.cancel_btn.grid(row=0, column=1, padx=(0, 6))
        self.new_run_btn = ttk.Button(controls, text="New Run", command=self._new_run, style="Secondary.TButton")
        self.new_run_btn.grid(row=0, column=2, padx=(0, 6))
        self.export_partial_btn = ttk.Button(
            controls,
            text="Export partial DOCX",
            command=self._export_partial,
            state=tk.DISABLED,
            style="Secondary.TButton",
        )
        self.export_partial_btn.grid(row=0, column=3, padx=(0, 6))
        self.rebuild_btn = ttk.Button(
            controls,
            text="Rebuild DOCX",
            command=self._start_rebuild_docx,
            state=tk.DISABLED,
            style="Secondary.TButton",
        )
        self.rebuild_btn.grid(row=0, column=4, padx=(0, 6))
        self.open_outdir_btn = ttk.Button(
            controls,
            text="Open output folder",
            command=self._open_output_folder,
            state=tk.DISABLED,
            style="Secondary.TButton",
        )
        self.open_outdir_btn.grid(row=0, column=5, padx=(0, 6))
        self.run_report_btn = ttk.Button(
            controls,
            text="Run Report",
            command=self._open_run_report,
            state=tk.DISABLED,
            style="Secondary.TButton",
        )
        self.run_report_btn.grid(row=0, column=6, padx=(0, 6))
        self.save_joblog_btn = ttk.Button(
            controls,
            text="Save to Job Log",
            command=self._open_save_to_joblog_dialog,
            state=tk.DISABLED,
            style="Secondary.TButton",
        )
        self.save_joblog_btn.grid(row=0, column=7, padx=(0, 6))
        self.open_joblog_btn = ttk.Button(
            controls,
            text="Job Log",
            command=self._open_joblog_window,
            style="Secondary.TButton",
        )
        self.open_joblog_btn.grid(row=0, column=8, padx=(0, 6))

        self.progress = ttk.Progressbar(content, orient=tk.HORIZONTAL, mode="determinate", maximum=100)
        self.progress.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(10, 0))

        self.status_label = ttk.Label(content, textvariable=self.status_var)
        self.status_label.grid(row=7, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self.live_counters_label = ttk.Label(content, textvariable=self.live_counters_var, style="Muted.TLabel")
        self.live_counters_label.grid(row=8, column=0, columnspan=4, sticky="w", pady=(4, 0))

        self.details_toggle_btn = ttk.Button(
            content,
            textvariable=self.details_toggle_text_var,
            command=self._toggle_details,
            style="Secondary.TButton",
        )
        self.details_toggle_btn.grid(row=9, column=0, columnspan=4, sticky="w", pady=(8, 0))

        self.details_frame = ttk.Frame(content, style="Surface.TFrame")
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
            (self.settings_btn, tk.NORMAL),
            (self.effort_policy_combo, "readonly"),
            (self.effort_combo, "readonly"),
            (self.images_combo, "readonly"),
            (self.ocr_mode_combo, "readonly"),
            (self.ocr_engine_combo, "readonly"),
            (self.start_page_entry, tk.NORMAL),
            (self.end_page_entry, tk.NORMAL),
            (self.max_pages_entry, tk.NORMAL),
            (self.workers_combo, "readonly"),
            (self.resume_check, tk.NORMAL),
            (self.page_breaks_check, tk.NORMAL),
            (self.keep_check, tk.NORMAL),
            (self.context_file_entry, tk.NORMAL),
            (self.context_browse_btn, tk.NORMAL),
            (self.analyze_btn, tk.NORMAL),
        ]
        self.bind("<Configure>", self._on_root_configure, add="+")
        self.after(10, self._refresh_visual_assets)

    def _refresh_visual_assets(self) -> None:
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        if self._last_visual_size == (width, height):
            return
        self._last_visual_size = (width, height)

        def _snap(value: int, step: int = 8) -> int:
            return max(step, int(round(value / step) * step))

        header_width = max(500, min(940, width - 60))
        header_height = 62
        side_height = max(180, height - 140)
        side_width = max(72, min(120, int(width * 0.1)))
        image_bg_size = (_snap(width), _snap(height))
        image_header_size = (_snap(header_width), _snap(header_height, 2))
        image_side_size = (_snap(side_width, 4), _snap(side_height, 4))
        right_x = max(0, width - side_width - 8)
        header_x = max(0, (width - header_width) // 2)

        if self._bg_label is not None:
            try:
                self._bg_image = load_image("resources/ui/ui_bg_tile.png", size=image_bg_size)
                self._bg_label.configure(image=self._bg_image)
                self._bg_label.place_configure(x=0, y=0, width=width, height=height)
                self._bg_label.lower()
            except Exception:
                pass
        if self._header_label is not None:
            try:
                self._header_image = load_image("resources/ui/ui_banner.png", size=image_header_size)
                self._header_label.configure(image=self._header_image)
                self._header_label.place_configure(x=header_x, y=10, width=header_width, height=header_height)
            except Exception:
                pass
        if self._left_deco_label is not None:
            try:
                self._left_deco_image = load_image("resources/ui/ui_deco_left.png", size=image_side_size)
                self._left_deco_label.configure(image=self._left_deco_image)
                self._left_deco_label.place_configure(x=8, y=88, width=side_width, height=side_height)
            except Exception:
                pass
        if self._right_deco_label is not None:
            try:
                self._right_deco_image = load_image("resources/ui/ui_deco_right.png", size=image_side_size)
                self._right_deco_label.configure(image=self._right_deco_image)
                self._right_deco_label.place_configure(x=right_x, y=88, width=side_width, height=side_height)
            except Exception:
                pass
        if self._header_title_label is not None:
            self._header_title_label.place_configure(x=header_x + 38, y=22, width=max(260, header_width - 80), height=38)
            self._header_title_label.lift()
        if self._content_frame is not None:
            self._content_frame.lift()

    def _on_root_configure(self, event: tk.Event) -> None:
        if event.widget is not self:
            return
        self._refresh_visual_assets()

    def _install_menu(self) -> None:
        menu_bar = tk.Menu(self.master)

        file_menu = tk.Menu(menu_bar, tearoff=False)
        file_menu.add_command(label="New Run", command=self._new_run)
        file_menu.add_command(label="Open Output Folder", command=self._open_output_folder)
        file_menu.add_command(label="Export Partial DOCX", command=self._export_partial)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menu_bar.add_cascade(label="File", menu=file_menu)

        tools_menu = tk.Menu(menu_bar, tearoff=False)
        tools_menu.add_command(label="Settings...", command=self._open_settings_dialog)
        tools_menu.add_command(label="Test API Keys...", command=self._test_api_keys)
        clear_keys_submenu = tk.Menu(tools_menu, tearoff=False)
        clear_keys_submenu.add_command(label="OpenAI key", command=self._clear_openai_key)
        clear_keys_submenu.add_command(label="OCR key", command=self._clear_ocr_key)
        clear_keys_submenu.add_command(label="Both", command=self._clear_all_keys)
        tools_menu.add_cascade(label="Clear Stored Keys...", menu=clear_keys_submenu)
        menu_bar.add_cascade(label="Tools", menu=tools_menu)

        help_menu = tk.Menu(menu_bar, tearoff=False)
        help_menu.add_command(label="About", command=self._show_about)
        help_menu.add_command(label="Open Logs Folder", command=self._open_logs_folder)
        help_menu.add_command(label="How it works", command=self._show_how_it_works)
        menu_bar.add_cascade(label="Help", menu=help_menu)

        self.master.configure(menu=menu_bar)
        self._menu_file = file_menu
        self._menu_tools = tools_menu
        self._menu_help = help_menu

    def _clear_openai_key(self) -> None:
        try:
            delete_openai_key()
        except RuntimeError as exc:
            messagebox.showerror("Credential Manager", str(exc))
            return
        messagebox.showinfo("Credential Manager", "Stored OpenAI key cleared.")

    def _clear_ocr_key(self) -> None:
        try:
            delete_ocr_key()
        except RuntimeError as exc:
            messagebox.showerror("Credential Manager", str(exc))
            return
        messagebox.showinfo("Credential Manager", "Stored OCR key cleared.")

    def _clear_all_keys(self) -> None:
        try:
            delete_openai_key()
            delete_ocr_key()
        except RuntimeError as exc:
            messagebox.showerror("Credential Manager", str(exc))
            return
        messagebox.showinfo("Credential Manager", "Stored OpenAI and OCR keys cleared.")

    def _test_api_keys(self) -> None:
        lines: list[str] = []

        openai_key: str | None
        try:
            openai_key = get_openai_key()
        except RuntimeError as exc:
            messagebox.showerror("API Key Test", str(exc))
            return
        if not openai_key:
            lines.append("OpenAI: missing key")
        else:
            started = time.perf_counter()
            try:
                client = OpenAI(api_key=openai_key)
                client.responses.create(
                    model=OPENAI_MODEL,
                    input=[{"role": "user", "content": [{"type": "input_text", "text": "Reply exactly with OK."}]}],
                    max_output_tokens=8,
                    store=False,
                )
                latency_ms = int((time.perf_counter() - started) * 1000)
                lines.append(f"OpenAI: PASS ({latency_ms} ms)")
            except Exception as exc:  # noqa: BLE001
                lines.append(f"OpenAI: FAIL ({type(exc).__name__})")

        try:
            ocr_key = get_ocr_key()
        except RuntimeError as exc:
            messagebox.showerror("API Key Test", str(exc))
            return
        if not ocr_key:
            lines.append("OCR API: missing key")
        else:
            ocr_base_url = self.ocr_api_base_url_var.get().strip()
            ocr_model = self.ocr_api_model_var.get().strip() or "gpt-4o-mini"
            if ocr_base_url == "":
                lines.append("OCR API: key present (base URL not set)")
            else:
                started = time.perf_counter()
                try:
                    client = OpenAI(api_key=ocr_key, base_url=ocr_base_url)
                    client.responses.create(
                        model=ocr_model,
                        input=[{"role": "user", "content": [{"type": "input_text", "text": "Reply exactly with OK."}]}],
                        max_output_tokens=8,
                        store=False,
                    )
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    lines.append(f"OCR API: PASS ({latency_ms} ms)")
                except Exception as exc:  # noqa: BLE001
                    lines.append(f"OCR API: FAIL ({type(exc).__name__})")

        messagebox.showinfo("API Key Test", "\n".join(lines))

    def _show_about(self) -> None:
        build_date = datetime.fromtimestamp(Path(__file__).stat().st_mtime).strftime("%Y-%m-%d")
        messagebox.showinfo(
            "About",
            f"LegalPDF Translate\nVersion: {__version__}\nBuild date: {build_date}",
        )

    def _open_logs_folder(self) -> None:
        self._metadata_logs_dir.mkdir(parents=True, exist_ok=True)
        target = self._metadata_logs_dir.expanduser().resolve()
        try:
            if os.name == "nt":
                os.startfile(str(target))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Open logs folder", str(exc))

    def _show_how_it_works(self) -> None:
        lines = [
            "1) The app processes selected pages one by one.",
            "2) It reuses checkpoints so runs can resume safely.",
            "3) OCR is used when text is missing or poor.",
            "4) Translation is validated before page acceptance.",
            "5) Cancellation is cooperative between pages.",
            "6) Partial DOCX export is available after progress.",
            "7) Logs store metadata only, not translated content.",
            "8) API keys are stored securely in Credential Manager.",
            "9) New Run clears runtime state without app restart.",
        ]
        win = tk.Toplevel(self.master)
        win.title("How it works")
        win.transient(self.master)
        win.resizable(False, False)
        frame = ttk.Frame(win, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="\n".join(lines), justify=tk.LEFT).pack(anchor="w")
        ttk.Button(frame, text="Close", command=win.destroy).pack(anchor="e", pady=(10, 0))

    def _bind_var_watchers(self) -> None:
        self.pdf_path_var.trace_add("write", self._on_form_input_changed)
        self.lang_var.trace_add("write", self._on_setting_changed)
        self.outdir_var.trace_add("write", self._on_setting_changed)
        self.effort_var.trace_add("write", self._on_setting_changed)
        self.effort_policy_var.trace_add("write", self._on_setting_changed)
        self.images_var.trace_add("write", self._on_setting_changed)
        self.ocr_mode_var.trace_add("write", self._on_setting_changed)
        self.ocr_engine_var.trace_add("write", self._on_setting_changed)
        self.resume_var.trace_add("write", self._on_setting_changed)
        self.page_breaks_var.trace_add("write", self._on_setting_changed)
        self.keep_var.trace_add("write", self._on_setting_changed)
        self.start_page_var.trace_add("write", self._on_setting_changed)
        self.end_page_var.trace_add("write", self._on_setting_changed)
        self.max_pages_var.trace_add("write", self._on_setting_changed)
        self.workers_var.trace_add("write", self._on_setting_changed)

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
            self.details_frame.grid(row=10, column=0, columnspan=4, sticky="nsew", pady=(8, 0))
            if self._content_frame is not None:
                self._content_frame.rowconfigure(10, weight=1)
        else:
            self.details_toggle_text_var.set("Show details ▾")
            self.details_frame.grid_forget()
            if self._content_frame is not None:
                self._content_frame.rowconfigure(10, weight=0)

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
        self._track_page_flags_from_log(message)
        if bool(self.settings_data.get("diagnostics_verbose_metadata_logs", False)):
            try:
                self._metadata_log_file.parent.mkdir(parents=True, exist_ok=True)
                with self._metadata_log_file.open("a", encoding="utf-8") as fh:
                    fh.write(f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n")
            except Exception:
                pass

    def _track_page_flags_from_log(self, message: str) -> None:
        match = _PAGE_LOG_RE.search(message)
        if match is None:
            return
        try:
            page_number = int(match.group("page"))
        except Exception:
            return
        if match.group("image") == "True":
            self._image_pages_seen.add(page_number)
        if match.group("retry") == "True":
            self._retry_pages_seen.add(page_number)
        self._update_live_counters()

    def _reset_live_counters(self) -> None:
        self._progress_done_pages = 0
        self._progress_total_pages = 0
        self._image_pages_seen.clear()
        self._retry_pages_seen.clear()
        self._update_live_counters()

    def _update_live_counters(self) -> None:
        self.live_counters_var.set(
            "Done "
            f"{self._progress_done_pages}/{self._progress_total_pages} | "
            f"Images {len(self._image_pages_seen)} | Retries {len(self._retry_pages_seen)}"
        )

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
        workers = self._parse_required_int(self.workers_var.get().strip() or "3", "Parallel workers")
        workers = max(1, min(6, workers))

        context_file_text = self.context_file_var.get().strip()
        context_file = Path(context_file_text).expanduser().resolve() if context_file_text else None
        context_text = self.context_text.get("1.0", tk.END).strip() or None

        return RunConfig(
            pdf_path=pdf,
            output_dir=outdir,
            target_lang=lang,
            effort=parse_effort(self.effort_var.get()),
            effort_policy=parse_effort_policy(self.effort_policy_var.get()),
            allow_xhigh_escalation=bool(self.settings_data.get("allow_xhigh_escalation", False)),
            image_mode=parse_image_mode(self.images_var.get()),
            ocr_mode=parse_ocr_mode(self.ocr_mode_var.get()),
            ocr_engine=parse_ocr_engine_policy(self.ocr_engine_var.get()),
            ocr_api_base_url=self.ocr_api_base_url_var.get().strip() or None,
            ocr_api_model=self.ocr_api_model_var.get().strip() or None,
            ocr_api_key_env_name=self.ocr_api_key_env_name_var.get().strip() or "DEEPSEEK_API_KEY",
            start_page=start_page,
            end_page=end_page,
            max_pages=max_pages,
            workers=workers,
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
        self.analyze_btn.configure(state=tk.NORMAL if (not self._busy and can_start) else tk.DISABLED)
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
        can_open_report = (
            not self._busy
            and self.last_run_report_path is not None
            and self.last_run_report_path.exists()
        )
        self.run_report_btn.configure(state=tk.NORMAL if can_open_report else tk.DISABLED)
        can_save_joblog = (not self._busy) and (self.last_joblog_seed is not None)
        self.save_joblog_btn.configure(state=tk.NORMAL if can_save_joblog else tk.DISABLED)
        self.open_joblog_btn.configure(state=tk.NORMAL if not self._busy else tk.DISABLED)

        menu_file = getattr(self, "_menu_file", None)
        if menu_file is not None:
            menu_file.entryconfig("Open Output Folder", state=tk.NORMAL if can_open else tk.DISABLED)
            menu_file.entryconfig(
                "Export Partial DOCX",
                state=tk.NORMAL if (not self._busy and self._can_export_partial) else tk.DISABLED,
            )

    def _new_queue(self) -> "queue.Queue[tuple[str, object]]":
        self.queue = queue.Queue()
        return self.queue

    def _warn_fixed_xhigh_for_enfr(self) -> str:
        dialog = tk.Toplevel(self.master)
        dialog.title("Cost/Time warning")
        dialog.transient(self.master)
        dialog.resizable(False, False)
        dialog.grab_set()

        choice = {"value": "cancel"}

        frame = ttk.Frame(dialog, padding=14)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            frame,
            text="xhigh can multiply cost and time; recommended: adaptive or high.",
            justify=tk.LEFT,
            wraplength=420,
        ).pack(anchor="w")
        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(
            buttons,
            text="Proceed",
            style="Primary.TButton",
            command=lambda: (choice.__setitem__("value", "proceed"), dialog.destroy()),
        ).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(
            buttons,
            text="Switch to adaptive",
            style="Secondary.TButton",
            command=lambda: (choice.__setitem__("value", "switch"), dialog.destroy()),
        ).pack(side=tk.RIGHT)
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.wait_window()
        return str(choice["value"])

    def _start_translation(self) -> None:
        try:
            config = self._build_config()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Invalid configuration", str(exc))
            return

        if (
            config.target_lang in (TargetLang.EN, TargetLang.FR)
            and config.effort_policy == EffortPolicy.FIXED_XHIGH
        ):
            decision = self._warn_fixed_xhigh_for_enfr()
            if decision == "switch":
                self.effort_policy_var.set("adaptive")
                try:
                    config = self._build_config()
                except Exception as exc:  # noqa: BLE001
                    messagebox.showerror("Invalid configuration", str(exc))
                    return
            elif decision != "proceed":
                return

        self._persist_gui_settings()
        self.last_summary = None
        self.last_output_docx = None
        self.last_run_config = config
        self.last_joblog_seed = None
        self.last_run_report_path = None
        self._can_export_partial = False
        self._set_busy(True, translation=True)
        self.progress.configure(value=0)
        self.status_var.set("Starting...")
        self._reset_live_counters()

        run_queue = self._new_queue()

        def log_callback(message: str) -> None:
            run_queue.put(("log", message))

        def progress_callback(page: int, total: int, status: str) -> None:
            run_queue.put(("progress", (page, total, status)))

        max_retries = int(self.settings_data.get("perf_max_transport_retries", 4))
        backoff_cap = float(self.settings_data.get("perf_backoff_cap_seconds", 12.0))
        try:
            client = OpenAIResponsesClient(
                max_transport_retries=max_retries,
                backoff_cap_seconds=backoff_cap,
                logger=log_callback,
            )
        except Exception as exc:  # noqa: BLE001
            self._set_busy(False, translation=False)
            messagebox.showerror("Missing credentials", str(exc))
            return

        workflow = TranslationWorkflow(
            client=client,
            log_callback=log_callback,
            progress_callback=progress_callback,
        )
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

    def _start_analyze(self) -> None:
        try:
            config = self._build_config()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Invalid configuration", str(exc))
            return

        self._persist_gui_settings()
        self.last_summary = None
        self.last_run_report_path = None
        self.last_output_docx = None
        self.last_joblog_seed = None
        self._set_busy(True, translation=False)
        self.status_var.set("Analyzing...")
        self.progress.configure(value=0)
        self._reset_live_counters()

        run_queue = self._new_queue()

        def log_callback(message: str) -> None:
            run_queue.put(("log", message))

        workflow = TranslationWorkflow(log_callback=log_callback)
        self.workflow = workflow

        def target() -> None:
            try:
                summary = workflow.analyze(config)
                run_queue.put(("analyze_done", summary))
            except Exception as exc:  # noqa: BLE001
                run_queue.put(("analyze_error", str(exc)))

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
        self.last_run_config = None
        self.last_joblog_seed = None
        self.last_run_report_path = None
        self._can_export_partial = False
        self.workflow = None
        self.worker = None
        self._new_queue()
        self.progress.configure(value=0)
        self.status_var.set("Idle")
        self._reset_live_counters()
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

    def _open_run_report(self) -> None:
        if self.last_run_report_path is None:
            return
        report_path = self.last_run_report_path.expanduser().resolve()
        if not report_path.exists():
            messagebox.showerror("Run report", f"Run report not found:\n{report_path}")
            return
        try:
            if os.name == "nt":
                subprocess.Popen(["explorer", f"/select,{report_path}"])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(report_path.parent)])
            else:
                subprocess.Popen(["xdg-open", str(report_path.parent)])
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Run report", str(exc))

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

    def _prepare_joblog_seed(self, summary: RunSummary) -> None:
        if self.last_run_config is None:
            self.last_joblog_seed = None
            return
        settings = load_joblog_settings()
        default_rate = settings["default_rate_per_word"].get(self.last_run_config.target_lang.value, 0.0)
        seed = build_seed_from_run(
            pdf_path=self.last_run_config.pdf_path,
            lang=self.last_run_config.target_lang.value,
            pages_dir=summary.run_dir / "pages",
            completed_pages=summary.completed_pages,
            completed_at=datetime.now().isoformat(timespec="seconds"),
            default_rate_per_word=float(default_rate),
            api_cost=0.0,
        )

        suggestion = extract_pdf_header_metadata(
            seed.pdf_path,
            vocab_cities=list(settings["vocab_cities"]),
            config=metadata_config_from_settings(settings),
            page_number=1,
        )
        if suggestion.case_entity:
            seed.case_entity = suggestion.case_entity
            seed.service_entity = suggestion.case_entity
        if suggestion.case_city:
            seed.case_city = suggestion.case_city
            seed.service_city = suggestion.case_city
        if suggestion.case_number:
            seed.case_number = suggestion.case_number

        self.last_joblog_seed = seed

    def _open_save_to_joblog_dialog(self) -> None:
        if self.last_joblog_seed is None:
            messagebox.showinfo("Job Log", "No completed run available to save.")
            return

        def _refresh_after_save() -> None:
            if self.joblog_window is not None and self.joblog_window.winfo_exists():
                self.joblog_window.refresh_rows()

        SaveToJobLogDialog(
            self.master,
            db_path=self.joblog_db_path,
            seed=self.last_joblog_seed,
            on_saved=_refresh_after_save,
        )

    def _open_joblog_window(self) -> None:
        if self.joblog_window is not None and self.joblog_window.winfo_exists():
            self.joblog_window.lift()
            self.joblog_window.focus_force()
            return
        self.joblog_window = JobLogWindow(self.master, db_path=self.joblog_db_path)

    def collect_debug_bundle_metadata_paths(self) -> list[Path]:
        paths: list[Path] = []
        settings_file = settings_path()
        if settings_file.exists():
            paths.append(settings_file)
        if self._metadata_log_file.exists():
            paths.append(self._metadata_log_file)
        if self.last_summary is not None:
            run_state_path = self.last_summary.run_dir / "run_state.json"
            if run_state_path.exists():
                paths.append(run_state_path)
        if self.last_run_config is not None:
            run_paths = build_output_paths(
                self.last_run_config.output_dir,
                self.last_run_config.pdf_path,
                self.last_run_config.target_lang,
            )
            if run_paths.run_state_path.exists():
                paths.append(run_paths.run_state_path)
        return paths

    def apply_settings_from_dialog(self, values: dict[str, object], *, persist: bool) -> None:
        self.settings_data.update(values)
        if persist:
            save_gui_settings(values)
            self.settings_data = load_gui_settings()
        self._apply_theme_from_settings(self.settings_data)
        self.lang_var.set(str(self.settings_data.get("default_lang", "EN")))
        self.effort_var.set(str(self.settings_data.get("default_effort", "high")))
        self.effort_policy_var.set(str(self.settings_data.get("default_effort_policy", "adaptive")))
        self.images_var.set(str(self.settings_data.get("default_images_mode", "off")))
        self.resume_var.set(bool(self.settings_data.get("default_resume", True)))
        self.keep_var.set(bool(self.settings_data.get("default_keep_intermediates", True)))
        self.page_breaks_var.set(bool(self.settings_data.get("default_page_breaks", True)))
        self.start_page_var.set(str(self.settings_data.get("default_start_page", 1)))
        default_end = self.settings_data.get("default_end_page")
        self.end_page_var.set("" if default_end in (None, "") else str(default_end))
        try:
            default_workers = int(self.settings_data.get("default_workers", 3))
        except (TypeError, ValueError):
            default_workers = 3
        self.workers_var.set(str(max(1, min(6, default_workers))))
        default_outdir = str(self.settings_data.get("default_outdir", "") or "")
        if default_outdir and not self.outdir_var.get().strip():
            self.outdir_var.set(default_outdir)
        self.ocr_mode_var.set(str(self.settings_data.get("ocr_mode_default", "auto")))
        self.ocr_engine_var.set(str(self.settings_data.get("ocr_engine_default", "local_then_api")))
        self.ocr_api_base_url_var.set(str(self.settings_data.get("ocr_api_base_url", "") or ""))
        self.ocr_api_model_var.set(str(self.settings_data.get("ocr_api_model", "") or ""))
        self.ocr_api_key_env_name_var.set(str(self.settings_data.get("ocr_api_key_env_name", "DEEPSEEK_API_KEY")))
        self._refresh_controls()

    def _open_settings_dialog(self) -> None:
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.lift()
            self.settings_window.focus_force()
            return
        self.settings_window = GuiSettingsDialog(
            self.master,
            app=self,
            settings=self.settings_data,
        )
        self.settings_window.bind("<Destroy>", lambda _: setattr(self, "settings_window", None), add="+")

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
            values = {
                "last_outdir": outdir_text,
                "last_lang": self.lang_var.get().strip().upper(),
                "effort": self.effort_var.get().strip().lower(),
                "effort_policy": self.effort_policy_var.get().strip().lower(),
                "image_mode": self.images_var.get().strip().lower(),
                "ocr_mode": self.ocr_mode_var.get().strip().lower(),
                "ocr_engine": self.ocr_engine_var.get().strip().lower(),
                "ocr_api_base_url": self.ocr_api_base_url_var.get().strip(),
                "ocr_api_model": self.ocr_api_model_var.get().strip(),
                "ocr_api_key_env_name": self.ocr_api_key_env_name_var.get().strip() or "DEEPSEEK_API_KEY",
                "resume": bool(self.resume_var.get()),
                "keep_intermediates": bool(self.keep_var.get()),
                "page_breaks": bool(self.page_breaks_var.get()),
                "start_page": start_page,
                "end_page": end_page,
                "max_pages": max_pages,
                "workers": max(1, min(6, self._int_from_text(self.workers_var.get(), allow_blank=True, default=3) or 3)),
            }
            save_gui_settings(values)
            self.settings_data.update(values)
        except Exception:
            pass

    def _on_close(self) -> None:
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.destroy()
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
                self._progress_done_pages = max(0, int(page))
                self._progress_total_pages = max(0, int(total))
                self._update_live_counters()
                self.status_var.set(f"Page {page}/{total}: {status}")
            elif event == "done":
                summary = payload  # type: ignore[assignment]
                self.last_summary = summary
                self.last_run_report_path = summary.run_summary_path
                self._set_busy(False, translation=False)
                if summary.success and summary.output_docx is not None:
                    self.last_output_docx = summary.output_docx.expanduser().resolve()
                    self.status_var.set("Completed")
                    self._append_log(f"Saved DOCX: {self.last_output_docx}")
                    if summary.run_summary_path is not None:
                        self._append_log(f"Run report: {summary.run_summary_path}")
                    self._prepare_joblog_seed(summary)
                    self._show_saved_docx_dialog("Translation complete")
                    self._open_save_to_joblog_dialog()
                else:
                    self.last_output_docx = None
                    self.last_joblog_seed = None
                    self.status_var.set(f"Failed ({summary.error})")
                    self._append_log(f"Run failed: {summary.error}; failed_page={summary.failed_page}")
                    if summary.run_summary_path is not None:
                        self._append_log(f"Run report: {summary.run_summary_path}")
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
                self._progress_done_pages = max(0, int(summary.completed_pages))
                self._progress_total_pages = max(self._progress_total_pages, self._progress_done_pages)
                self._update_live_counters()
                self._refresh_controls()
            elif event == "analyze_done":
                analysis = payload  # type: ignore[assignment]
                if not isinstance(analysis, AnalyzeSummary):
                    self._set_busy(False, translation=False)
                    self.status_var.set("Analyze failed")
                    messagebox.showerror("Analyze failed", "Invalid analyze response.")
                    self._refresh_controls()
                    continue
                self._set_busy(False, translation=False)
                self.status_var.set("Analyze complete")
                self._append_log(
                    "Analyze complete: "
                    f"selected_pages={analysis.selected_pages_count}, "
                    f"would_attach_images={analysis.pages_would_attach_images}"
                )
                self._append_log(f"Analyze report: {analysis.analyze_report_path}")
                self._progress_done_pages = 0
                self._progress_total_pages = int(analysis.selected_pages_count)
                self._update_live_counters()
                messagebox.showinfo(
                    "Analyze complete",
                    "Analyze-only finished.\n\n"
                    f"Selected pages: {analysis.selected_pages_count}\n"
                    f"Would attach images: {analysis.pages_would_attach_images}\n"
                    f"Report: {analysis.analyze_report_path}",
                )
                self._refresh_controls()
            elif event == "analyze_error":
                self._set_busy(False, translation=False)
                self.status_var.set("Analyze failed")
                self._append_log(f"Analyze failed: {payload}")
                messagebox.showerror("Analyze failed", str(payload))
                self._refresh_controls()
            elif event == "rebuild_done":
                rebuilt = payload  # type: ignore[assignment]
                self._set_busy(False, translation=False)
                self.last_output_docx = rebuilt.expanduser().resolve()
                self.last_joblog_seed = None
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
