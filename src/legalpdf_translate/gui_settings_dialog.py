"""Tabbed settings dialog for global defaults, providers, and diagnostics."""

from __future__ import annotations

import json
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING
from urllib.parse import urlparse
from zipfile import ZIP_DEFLATED, ZipFile

from openai import OpenAI

from .config import OPENAI_MODEL
from .secrets_store import (
    delete_openai_key,
    delete_ocr_key,
    get_openai_key,
    get_ocr_key,
    set_openai_key,
    set_ocr_key,
)

if TYPE_CHECKING:
    from .gui_app import LegalPDFTranslateApp


def _validate_url_or_blank(value: str) -> bool:
    cleaned = value.strip()
    if cleaned == "":
        return True
    parsed = urlparse(cleaned)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _to_int(value: str, *, field: str, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field} must be an integer.") from exc
    if parsed < min_value or parsed > max_value:
        raise ValueError(f"{field} must be between {min_value} and {max_value}.")
    return parsed


def _to_float(value: str, *, field: str, min_value: float, max_value: float) -> float:
    cleaned = value.strip().replace(",", ".")
    try:
        parsed = float(cleaned)
    except ValueError as exc:
        raise ValueError(f"{field} must be a number.") from exc
    if parsed < min_value or parsed > max_value:
        raise ValueError(f"{field} must be between {min_value} and {max_value}.")
    return parsed


class GuiSettingsDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, *, app: "LegalPDFTranslateApp", settings: dict[str, object]) -> None:
        super().__init__(master)
        self._app = app
        self._initial = dict(settings)
        self.title("Settings")
        self.geometry("900x640")
        self.minsize(820, 560)
        self.transient(master)
        self.grab_set()

        self._build_state(settings)
        self._build_ui()
        self._refresh_key_status()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _build_state(self, settings: dict[str, object]) -> None:
        self.ui_theme_var = tk.StringVar(value=str(settings.get("ui_theme", "dark_futuristic")))
        self.ui_scale_var = tk.StringVar(value=f"{float(settings.get('ui_scale', 1.0)):.2f}")
        self.default_lang_var = tk.StringVar(value=str(settings.get("default_lang", "EN")))
        self.default_effort_var = tk.StringVar(value=str(settings.get("default_effort", "high")))
        self.default_images_mode_var = tk.StringVar(value=str(settings.get("default_images_mode", "auto")))
        self.default_workers_var = tk.StringVar(value=str(settings.get("default_workers", 3)))
        self.default_resume_var = tk.BooleanVar(value=bool(settings.get("default_resume", True)))
        self.default_keep_var = tk.BooleanVar(value=bool(settings.get("default_keep_intermediates", True)))
        self.default_breaks_var = tk.BooleanVar(value=bool(settings.get("default_page_breaks", True)))
        self.default_start_var = tk.StringVar(value=str(settings.get("default_start_page", 1)))
        default_end = settings.get("default_end_page")
        self.default_end_var = tk.StringVar(value="" if default_end in (None, "") else str(default_end))
        self.default_outdir_var = tk.StringVar(value=str(settings.get("default_outdir", "")))

        self.ocr_mode_default_var = tk.StringVar(value=str(settings.get("ocr_mode_default", "auto")))
        self.ocr_engine_default_var = tk.StringVar(value=str(settings.get("ocr_engine_default", "local_then_api")))
        self.min_chars_var = tk.StringVar(value=str(settings.get("min_chars_to_accept_ocr", 200)))
        self.ocr_base_url_var = tk.StringVar(value=str(settings.get("ocr_api_base_url", "")))
        self.ocr_model_var = tk.StringVar(value=str(settings.get("ocr_api_model", "")))
        self.ocr_env_var = tk.StringVar(value=str(settings.get("ocr_api_key_env_name", "DEEPSEEK_API_KEY")))

        self.retries_var = tk.StringVar(value=str(settings.get("perf_max_transport_retries", 4)))
        self.backoff_cap_var = tk.StringVar(value=str(settings.get("perf_backoff_cap_seconds", 12.0)))
        self.timeout_text_var = tk.StringVar(value=str(settings.get("perf_timeout_text_seconds", 90)))
        self.timeout_image_var = tk.StringVar(value=str(settings.get("perf_timeout_image_seconds", 120)))
        self.adaptive_effort_enabled_var = tk.BooleanVar(value=bool(settings.get("adaptive_effort_enabled", False)))
        self.adaptive_xhigh_guard_var = tk.BooleanVar(
            value=bool(settings.get("adaptive_effort_xhigh_only_when_image_or_validator_fail", True))
        )
        self.diag_cost_summary_var = tk.BooleanVar(value=bool(settings.get("diagnostics_show_cost_summary", True)))
        self.diag_verbose_meta_var = tk.BooleanVar(value=bool(settings.get("diagnostics_verbose_metadata_logs", False)))

        self.openai_key_var = tk.StringVar(value="")
        self.ocr_key_var = tk.StringVar(value="")
        self.openai_status_var = tk.StringVar(value="Not stored")
        self.ocr_status_var = tk.StringVar(value="Not stored")
        self.provider_summary_var = tk.StringVar(value="")

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(self)
        notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self._build_tab_keys(notebook)
        self._build_tab_ocr_defaults(notebook)
        self._build_tab_appearance(notebook)
        self._build_tab_behavior(notebook)
        self._build_tab_diagnostics(notebook)

        buttons = ttk.Frame(self)
        buttons.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        buttons.columnconfigure(0, weight=1)
        ttk.Button(buttons, text="Apply", command=self._apply).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(buttons, text="Save", command=self._save).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(buttons, text="Cancel", command=self._cancel).grid(row=0, column=3)

    def _build_tab_keys(self, notebook: ttk.Notebook) -> None:
        tab = ttk.Frame(notebook, padding=10)
        tab.columnconfigure(0, weight=1)
        notebook.add(tab, text="Keys & Providers")

        openai = ttk.LabelFrame(tab, text="OpenAI (Translation)", padding=10)
        openai.grid(row=0, column=0, sticky="ew")
        openai.columnconfigure(1, weight=1)
        ttk.Label(openai, text="API key").grid(row=0, column=0, sticky="w")
        self.openai_entry = ttk.Entry(openai, textvariable=self.openai_key_var, show="*")
        self.openai_entry.grid(row=0, column=1, sticky="ew", padx=(6, 6))
        self.openai_toggle = ttk.Button(openai, text="Show", command=self._toggle_openai_key, width=8)
        self.openai_toggle.grid(row=0, column=2, padx=(0, 6))
        ttk.Button(openai, text="Save", command=self._save_openai_key).grid(row=0, column=3, padx=(0, 6))
        ttk.Button(openai, text="Clear", command=self._clear_openai_key).grid(row=0, column=4, padx=(0, 6))
        ttk.Button(openai, text="Test", command=self._test_openai_key).grid(row=0, column=5)
        ttk.Label(openai, textvariable=self.openai_status_var).grid(row=1, column=0, columnspan=6, sticky="w", pady=(6, 0))

        ocr = ttk.LabelFrame(tab, text="OCR API (Fallback)", padding=10)
        ocr.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ocr.columnconfigure(1, weight=1)
        ttk.Label(ocr, text="API key").grid(row=0, column=0, sticky="w")
        self.ocr_entry = ttk.Entry(ocr, textvariable=self.ocr_key_var, show="*")
        self.ocr_entry.grid(row=0, column=1, sticky="ew", padx=(6, 6))
        self.ocr_toggle = ttk.Button(ocr, text="Show", command=self._toggle_ocr_key, width=8)
        self.ocr_toggle.grid(row=0, column=2, padx=(0, 6))
        ttk.Button(ocr, text="Save", command=self._save_ocr_key).grid(row=0, column=3, padx=(0, 6))
        ttk.Button(ocr, text="Clear", command=self._clear_ocr_key).grid(row=0, column=4, padx=(0, 6))
        ttk.Button(ocr, text="Test", command=self._test_ocr_key).grid(row=0, column=5)
        ttk.Label(ocr, textvariable=self.ocr_status_var).grid(row=1, column=0, columnspan=6, sticky="w", pady=(6, 0))

        provider = ttk.LabelFrame(tab, text="Provider Settings", padding=10)
        provider.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        provider.columnconfigure(1, weight=1)
        ttk.Label(provider, text="OCR base URL").grid(row=0, column=0, sticky="w")
        ttk.Entry(provider, textvariable=self.ocr_base_url_var).grid(row=0, column=1, sticky="ew")
        ttk.Label(provider, text="OCR model").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(provider, textvariable=self.ocr_model_var).grid(row=1, column=1, sticky="ew", pady=(6, 0))
        ttk.Label(provider, text="OCR env var name").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(provider, textvariable=self.ocr_env_var).grid(row=2, column=1, sticky="ew", pady=(6, 0))
        ttk.Label(provider, textvariable=self.provider_summary_var, style="Muted.TLabel").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

    def _build_tab_ocr_defaults(self, notebook: ttk.Notebook) -> None:
        tab = ttk.Frame(notebook, padding=10)
        tab.columnconfigure(1, weight=1)
        notebook.add(tab, text="OCR Defaults")

        ttk.Label(tab, text="Default OCR mode").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            tab,
            textvariable=self.ocr_mode_default_var,
            values=["off", "auto", "always"],
            state="readonly",
            width=18,
        ).grid(row=0, column=1, sticky="w")
        ttk.Label(tab, text="Default OCR engine").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            tab,
            textvariable=self.ocr_engine_default_var,
            values=["local", "local_then_api", "api"],
            state="readonly",
            width=18,
        ).grid(row=1, column=1, sticky="w", pady=(8, 0))
        ttk.Label(tab, text="Min chars to accept OCR").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(tab, textvariable=self.min_chars_var, width=12).grid(row=2, column=1, sticky="w", pady=(8, 0))
        ttk.Label(
            tab,
            text="Lower OCR text than threshold is marked suspect for fallback rules.",
            style="Muted.TLabel",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))

    def _build_tab_appearance(self, notebook: ttk.Notebook) -> None:
        tab = ttk.Frame(notebook, padding=10)
        tab.columnconfigure(1, weight=1)
        notebook.add(tab, text="Appearance")

        ttk.Label(tab, text="Theme").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            tab,
            textvariable=self.ui_theme_var,
            values=["dark_futuristic", "dark_simple"],
            state="readonly",
            width=20,
        ).grid(row=0, column=1, sticky="w")
        ttk.Label(tab, text="UI scale").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            tab,
            textvariable=self.ui_scale_var,
            values=["1.00", "1.10", "1.25"],
            state="readonly",
            width=12,
        ).grid(row=1, column=1, sticky="w", pady=(8, 0))
        ttk.Button(tab, text="Apply", command=self._apply).grid(row=2, column=1, sticky="w", pady=(10, 0))

    def _build_tab_behavior(self, notebook: ttk.Notebook) -> None:
        tab = ttk.Frame(notebook, padding=10)
        tab.columnconfigure(1, weight=1)
        notebook.add(tab, text="Behaviour & Performance")

        ttk.Label(tab, text="Default language").grid(row=0, column=0, sticky="w")
        ttk.Combobox(tab, textvariable=self.default_lang_var, values=["EN", "FR", "AR"], state="readonly", width=12).grid(
            row=0, column=1, sticky="w"
        )
        ttk.Label(tab, text="Default effort").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(tab, textvariable=self.default_effort_var, values=["high", "xhigh"], state="readonly", width=12).grid(
            row=1, column=1, sticky="w", pady=(6, 0)
        )
        ttk.Label(tab, text="Default images mode").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(
            tab,
            textvariable=self.default_images_mode_var,
            values=["off", "auto", "always"],
            state="readonly",
            width=12,
        ).grid(row=2, column=1, sticky="w", pady=(6, 0))
        ttk.Label(tab, text="Default workers").grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(
            tab,
            textvariable=self.default_workers_var,
            values=["1", "2", "3", "4", "5", "6"],
            state="readonly",
            width=12,
        ).grid(row=3, column=1, sticky="w", pady=(6, 0))
        ttk.Label(tab, text="Default start page").grid(row=4, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(tab, textvariable=self.default_start_var, width=12).grid(row=4, column=1, sticky="w", pady=(6, 0))
        ttk.Label(tab, text="Default end page").grid(row=5, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(tab, textvariable=self.default_end_var, width=12).grid(row=5, column=1, sticky="w", pady=(6, 0))
        ttk.Label(tab, text="Default output folder").grid(row=6, column=0, sticky="w", pady=(6, 0))
        outdir_row = ttk.Frame(tab)
        outdir_row.grid(row=6, column=1, sticky="ew", pady=(6, 0))
        outdir_row.columnconfigure(0, weight=1)
        ttk.Entry(outdir_row, textvariable=self.default_outdir_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(outdir_row, text="Browse", command=self._pick_default_outdir).grid(row=0, column=1, padx=(6, 0))
        ttk.Checkbutton(tab, text="Default resume ON", variable=self.default_resume_var).grid(
            row=7, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Checkbutton(tab, text="Default keep intermediates ON", variable=self.default_keep_var).grid(
            row=7, column=1, sticky="w", pady=(8, 0)
        )
        ttk.Checkbutton(tab, text="Default page breaks ON", variable=self.default_breaks_var).grid(
            row=8, column=0, sticky="w", pady=(6, 0)
        )

        ttk.Separator(tab, orient=tk.HORIZONTAL).grid(row=9, column=0, columnspan=2, sticky="ew", pady=12)
        ttk.Label(tab, text="Transport retries").grid(row=10, column=0, sticky="w")
        ttk.Entry(tab, textvariable=self.retries_var, width=12).grid(row=10, column=1, sticky="w")
        ttk.Label(tab, text="Backoff cap (seconds)").grid(row=11, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(tab, textvariable=self.backoff_cap_var, width=12).grid(row=11, column=1, sticky="w", pady=(6, 0))
        ttk.Label(tab, text="Text timeout (seconds)").grid(row=12, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(tab, textvariable=self.timeout_text_var, width=12).grid(row=12, column=1, sticky="w", pady=(6, 0))
        ttk.Label(tab, text="Image timeout (seconds)").grid(row=13, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(tab, textvariable=self.timeout_image_var, width=12).grid(row=13, column=1, sticky="w", pady=(6, 0))
        ttk.Checkbutton(tab, text="Adaptive effort", variable=self.adaptive_effort_enabled_var).grid(
            row=14, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Checkbutton(
            tab,
            text="Use xhigh only on image/validator fallback",
            variable=self.adaptive_xhigh_guard_var,
        ).grid(row=14, column=1, sticky="w", pady=(8, 0))
        ttk.Button(tab, text="Restore defaults", command=self._restore_defaults).grid(row=15, column=1, sticky="w", pady=(10, 0))

    def _pick_default_outdir(self) -> None:
        chosen = filedialog.askdirectory(title="Choose default output folder")
        if chosen:
            self.default_outdir_var.set(chosen)

    def _build_tab_diagnostics(self, notebook: ttk.Notebook) -> None:
        tab = ttk.Frame(notebook, padding=10)
        notebook.add(tab, text="Diagnostics")
        ttk.Checkbutton(tab, text="Show cost summary", variable=self.diag_cost_summary_var).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(tab, text="Verbose metadata logs", variable=self.diag_verbose_meta_var).grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Button(tab, text="Create debug bundle", command=self._create_debug_bundle).grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Label(tab, text="Bundle excludes page text files and all credentials.", style="Muted.TLabel").grid(
            row=3, column=0, sticky="w", pady=(8, 0)
        )

    def _toggle_openai_key(self) -> None:
        if self.openai_entry.cget("show"):
            self.openai_entry.configure(show="")
            self.openai_toggle.configure(text="Hide")
        else:
            self.openai_entry.configure(show="*")
            self.openai_toggle.configure(text="Show")

    def _toggle_ocr_key(self) -> None:
        if self.ocr_entry.cget("show"):
            self.ocr_entry.configure(show="")
            self.ocr_toggle.configure(text="Hide")
        else:
            self.ocr_entry.configure(show="*")
            self.ocr_toggle.configure(text="Show")

    def _refresh_key_status(self) -> None:
        try:
            openai_stored = bool(get_openai_key())
            ocr_stored = bool(get_ocr_key())
        except RuntimeError as exc:
            messagebox.showerror("Settings", str(exc))
            openai_stored = False
            ocr_stored = False
        self.openai_status_var.set("Stored" if openai_stored else "Not stored")
        self.ocr_status_var.set("Stored" if ocr_stored else "Not stored")
        self.provider_summary_var.set(
            "Provider mode: OpenAI credentials "
            f"{'present' if openai_stored else 'missing'}, OCR credentials {'present' if ocr_stored else 'missing'}."
        )

    def _save_openai_key(self) -> None:
        key = self.openai_key_var.get().strip()
        if not key:
            messagebox.showerror("Settings", "OpenAI API key cannot be empty.")
            return
        try:
            set_openai_key(key)
            if not get_openai_key():
                raise RuntimeError("Secure credential storage is unavailable on this system.")
        except RuntimeError as exc:
            messagebox.showerror("Settings", str(exc))
            return
        self.openai_key_var.set("")
        self.openai_entry.configure(show="*")
        self.openai_toggle.configure(text="Show")
        self._refresh_key_status()
        messagebox.showinfo("Settings", "Saved")

    def _clear_openai_key(self) -> None:
        try:
            delete_openai_key()
        except RuntimeError as exc:
            messagebox.showerror("Settings", str(exc))
            return
        self._refresh_key_status()

    def _save_ocr_key(self) -> None:
        key = self.ocr_key_var.get().strip()
        if not key:
            messagebox.showerror("Settings", "OCR API key cannot be empty.")
            return
        try:
            set_ocr_key(key)
            if not get_ocr_key():
                raise RuntimeError("Secure credential storage is unavailable on this system.")
        except RuntimeError as exc:
            messagebox.showerror("Settings", str(exc))
            return
        self.ocr_key_var.set("")
        self.ocr_entry.configure(show="*")
        self.ocr_toggle.configure(text="Show")
        self._refresh_key_status()
        messagebox.showinfo("Settings", "Saved")

    def _clear_ocr_key(self) -> None:
        try:
            delete_ocr_key()
        except RuntimeError as exc:
            messagebox.showerror("Settings", str(exc))
            return
        self._refresh_key_status()

    def _test_openai_key(self) -> None:
        try:
            key = get_openai_key()
        except RuntimeError as exc:
            messagebox.showerror("Settings", str(exc))
            return
        if not key:
            messagebox.showwarning("Key Test", "OpenAI key is not stored.")
            return
        started = time.perf_counter()
        try:
            client = OpenAI(api_key=key)
            client.responses.create(
                model=OPENAI_MODEL,
                input=[{"role": "user", "content": [{"type": "input_text", "text": "Reply exactly with OK."}]}],
                max_output_tokens=8,
                store=False,
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Key Test", f"OpenAI key test failed: {type(exc).__name__}")
            return
        latency_ms = int((time.perf_counter() - started) * 1000)
        messagebox.showinfo("Key Test", f"OpenAI test passed ({latency_ms} ms).")

    def _test_ocr_key(self) -> None:
        try:
            key = get_ocr_key()
        except RuntimeError as exc:
            messagebox.showerror("Settings", str(exc))
            return
        if not key:
            messagebox.showwarning("Key Test", "OCR key is not stored.")
            return
        base_url = self.ocr_base_url_var.get().strip()
        model = self.ocr_model_var.get().strip() or "gpt-4o-mini"
        started = time.perf_counter()
        if base_url == "":
            latency_ms = int((time.perf_counter() - started) * 1000)
            messagebox.showinfo("Key Test", f"OCR key is present ({latency_ms} ms).")
            return
        try:
            client = OpenAI(api_key=key, base_url=base_url)
            client.responses.create(
                model=model,
                input=[{"role": "user", "content": [{"type": "input_text", "text": "Reply exactly with OK."}]}],
                max_output_tokens=8,
                store=False,
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Key Test", f"OCR key test failed: {type(exc).__name__}")
            return
        latency_ms = int((time.perf_counter() - started) * 1000)
        messagebox.showinfo("Key Test", f"OCR test passed ({latency_ms} ms).")

    def _restore_defaults(self) -> None:
        self.default_lang_var.set("EN")
        self.default_effort_var.set("high")
        self.default_images_mode_var.set("auto")
        self.default_workers_var.set("3")
        self.default_resume_var.set(True)
        self.default_keep_var.set(True)
        self.default_breaks_var.set(True)
        self.default_start_var.set("1")
        self.default_end_var.set("")
        self.default_outdir_var.set("")
        self.ocr_mode_default_var.set("auto")
        self.ocr_engine_default_var.set("local_then_api")
        self.retries_var.set("4")
        self.backoff_cap_var.set("12.0")
        self.timeout_text_var.set("90")
        self.timeout_image_var.set("120")
        self.adaptive_effort_enabled_var.set(False)
        self.adaptive_xhigh_guard_var.set(True)

    def _collect_values(self) -> dict[str, object]:
        base_url = self.ocr_base_url_var.get().strip()
        if not _validate_url_or_blank(base_url):
            raise ValueError("OCR base URL must be a valid http/https URL.")

        default_end: int | None
        default_end_text = self.default_end_var.get().strip()
        if default_end_text == "":
            default_end = None
        else:
            default_end = _to_int(default_end_text, field="Default end page", min_value=1, max_value=100000)
        default_start = _to_int(self.default_start_var.get(), field="Default start page", min_value=1, max_value=100000)
        if default_end is not None and default_start > default_end:
            raise ValueError("Default start page must be <= default end page.")

        ui_scale = _to_float(self.ui_scale_var.get(), field="UI scale", min_value=1.0, max_value=1.25)
        if ui_scale not in (1.0, 1.1, 1.25):
            raise ValueError("UI scale must be one of 1.00, 1.10, or 1.25.")

        values: dict[str, object] = {
            "ui_theme": self.ui_theme_var.get().strip(),
            "ui_scale": ui_scale,
            "default_lang": self.default_lang_var.get().strip().upper(),
            "default_effort": self.default_effort_var.get().strip().lower(),
            "default_images_mode": self.default_images_mode_var.get().strip().lower(),
            "default_workers": _to_int(self.default_workers_var.get(), field="Default workers", min_value=1, max_value=6),
            "default_resume": bool(self.default_resume_var.get()),
            "default_keep_intermediates": bool(self.default_keep_var.get()),
            "default_page_breaks": bool(self.default_breaks_var.get()),
            "default_start_page": default_start,
            "default_end_page": default_end,
            "default_outdir": self.default_outdir_var.get().strip(),
            "ocr_mode_default": self.ocr_mode_default_var.get().strip().lower(),
            "ocr_engine_default": self.ocr_engine_default_var.get().strip().lower(),
            "ocr_api_base_url": base_url,
            "ocr_api_model": self.ocr_model_var.get().strip(),
            "ocr_api_key_env_name": self.ocr_env_var.get().strip() or "DEEPSEEK_API_KEY",
            "perf_max_transport_retries": _to_int(
                self.retries_var.get(),
                field="Transport retries",
                min_value=0,
                max_value=12,
            ),
            "perf_backoff_cap_seconds": _to_float(
                self.backoff_cap_var.get(),
                field="Backoff cap",
                min_value=1.0,
                max_value=120.0,
            ),
            "perf_timeout_text_seconds": _to_int(
                self.timeout_text_var.get(),
                field="Text timeout",
                min_value=5,
                max_value=600,
            ),
            "perf_timeout_image_seconds": _to_int(
                self.timeout_image_var.get(),
                field="Image timeout",
                min_value=5,
                max_value=1200,
            ),
            "adaptive_effort_enabled": bool(self.adaptive_effort_enabled_var.get()),
            "adaptive_effort_xhigh_only_when_image_or_validator_fail": bool(self.adaptive_xhigh_guard_var.get()),
            "diagnostics_show_cost_summary": bool(self.diag_cost_summary_var.get()),
            "diagnostics_verbose_metadata_logs": bool(self.diag_verbose_meta_var.get()),
            "min_chars_to_accept_ocr": _to_int(
                self.min_chars_var.get(),
                field="Min chars to accept OCR",
                min_value=20,
                max_value=10000,
            ),
        }
        return values

    def _apply(self) -> None:
        try:
            values = self._collect_values()
        except ValueError as exc:
            messagebox.showerror("Settings", str(exc))
            return
        self._app.apply_settings_from_dialog(values, persist=False)

    def _save(self) -> None:
        try:
            values = self._collect_values()
        except ValueError as exc:
            messagebox.showerror("Settings", str(exc))
            return
        self._app.apply_settings_from_dialog(values, persist=True)
        messagebox.showinfo("Settings", "Saved")

    def _cancel(self) -> None:
        self._app.settings_window = None
        self.destroy()

    def _create_debug_bundle(self) -> None:
        try:
            snapshot = self._collect_values()
        except ValueError as exc:
            messagebox.showerror("Settings", str(exc))
            return
        save_path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("Zip archive", "*.zip")],
            title="Save debug bundle",
        )
        if not save_path:
            return
        output = Path(save_path).expanduser().resolve()
        metadata_paths = self._app.collect_debug_bundle_metadata_paths()
        try:
            with ZipFile(output, mode="w", compression=ZIP_DEFLATED) as archive:
                for path in metadata_paths:
                    if not path.exists() or not path.is_file():
                        continue
                    archive.write(path, arcname=path.name)
                archive.writestr("settings_snapshot.json", json.dumps(snapshot, ensure_ascii=False, indent=2))
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Settings", f"Failed to create debug bundle: {exc}")
            return
        messagebox.showinfo("Settings", f"Debug bundle created:\n{output}")
