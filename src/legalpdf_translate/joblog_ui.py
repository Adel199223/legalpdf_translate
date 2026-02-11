"""Tkinter UI for Job Log save dialog and table window."""

from __future__ import annotations

import re
import tkinter as tk
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Callable

from .joblog_db import insert_job_run, list_job_runs, open_job_log, update_joblog_visible_columns
from .metadata_autofill import (
    MetadataSuggestion,
    apply_service_case_default_rule,
    extract_from_header_text,
    extract_from_photo_ocr_text,
    extract_header_text_from_pdf_with_ocr_fallback,
    extract_ocr_text_from_photo_image,
)
from .user_settings import load_joblog_settings, save_joblog_settings

JOBLOG_COLUMNS = [
    "translation_date",
    "case_number",
    "job_type",
    "case_entity",
    "case_city",
    "service_entity",
    "service_city",
    "service_date",
    "lang",
    "pages",
    "word_count",
    "rate_per_word",
    "expected_total",
    "amount_paid",
    "api_cost",
    "profit",
]

JOBLOG_COLUMN_LABELS = {
    "translation_date": "Date",
    "case_number": "Case #",
    "job_type": "Job Type",
    "case_entity": "Case Entity",
    "case_city": "Case City",
    "service_entity": "Service Entity",
    "service_city": "Service City",
    "service_date": "Service Date",
    "lang": "Lang",
    "pages": "Pages",
    "word_count": "Words",
    "rate_per_word": "Rate/Word",
    "expected_total": "Expected",
    "amount_paid": "Paid",
    "api_cost": "API Cost",
    "profit": "Profit",
}


@dataclass(slots=True)
class JobLogSeed:
    completed_at: str
    job_type: str
    case_number: str
    case_entity: str
    case_city: str
    service_entity: str
    service_city: str
    service_date: str
    lang: str
    pages: int
    word_count: int
    rate_per_word: float
    expected_total: float
    amount_paid: float
    api_cost: float
    profit: float
    pdf_path: Path


def count_words_from_pages_dir(pages_dir: Path) -> int:
    total = 0
    for page_file in sorted(pages_dir.glob("page_*.txt")):
        text = page_file.read_text(encoding="utf-8")
        total += len(re.findall(r"\S+", text))
    return total


def _date_from_completed_at(completed_at: str) -> str:
    cleaned = completed_at.strip()
    if cleaned == "":
        return ""
    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return cleaned[:10]


def build_seed_from_run(
    *,
    pdf_path: Path,
    lang: str,
    pages_dir: Path,
    completed_pages: int,
    completed_at: str,
    default_rate_per_word: float,
    api_cost: float = 0.0,
) -> JobLogSeed:
    word_count = count_words_from_pages_dir(pages_dir)
    expected_total = round(float(default_rate_per_word) * float(word_count), 2)
    return JobLogSeed(
        completed_at=completed_at,
        job_type="Translation",
        case_number="",
        case_entity="",
        case_city="",
        service_entity="",
        service_city="",
        service_date=_date_from_completed_at(completed_at),
        lang=lang,
        pages=int(completed_pages),
        word_count=int(word_count),
        rate_per_word=float(default_rate_per_word),
        expected_total=expected_total,
        amount_paid=0.0,
        api_cost=float(api_cost),
        profit=round(expected_total - float(api_cost), 2),
        pdf_path=pdf_path,
    )


class SaveToJobLogDialog(tk.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        *,
        db_path: Path,
        seed: JobLogSeed,
        on_saved: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master)
        self.title("Save to Job Log")
        self.resizable(True, True)
        self.transient(master.winfo_toplevel())
        self.grab_set()

        self._db_path = db_path
        self._seed = seed
        self._on_saved = on_saved
        self._saved = False
        self._settings = load_joblog_settings()
        self._header_text_cache: str | None = None

        self._case_entity_user_set = False
        self._case_city_user_set = False

        self.job_type_var = tk.StringVar(value=seed.job_type or "Translation")
        self.case_number_var = tk.StringVar(value=seed.case_number)
        self.case_entity_var = tk.StringVar(value=seed.case_entity)
        self.case_city_var = tk.StringVar(value=seed.case_city)
        self.service_entity_var = tk.StringVar(value=seed.service_entity)
        self.service_city_var = tk.StringVar(value=seed.service_city)
        self.service_date_var = tk.StringVar(value=seed.service_date)
        self.service_same_var = tk.BooleanVar(value=bool(self._settings["service_equals_case_by_default"]))
        self.photo_translation_enable_var = tk.BooleanVar(value=False)

        self.rate_var = tk.StringVar(value=f"{seed.rate_per_word:.4f}")
        self.expected_total_var = tk.StringVar(value=f"{seed.expected_total:.2f}")
        self.amount_paid_var = tk.StringVar(value=f"{seed.amount_paid:.2f}")
        self.api_cost_var = tk.StringVar(value=f"{seed.api_cost:.2f}")
        self.profit_var = tk.StringVar(value=f"{seed.profit:.2f}")

        self._build_ui()
        self._bind_watchers()
        self._refresh_service_mirror_state()
        self._refresh_photo_controls()

    @property
    def saved(self) -> bool:
        return self._saved

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)

        top = ttk.Frame(self, padding=10)
        top.grid(row=0, column=0, sticky="nsew")
        top.columnconfigure(1, weight=1)
        top.columnconfigure(3, weight=1)

        ttk.Label(top, text="Job type").grid(row=0, column=0, sticky="w")
        self.job_type_combo = ttk.Combobox(
            top,
            textvariable=self.job_type_var,
            values=self._settings["vocab_job_types"],
            state="readonly",
            width=20,
        )
        self.job_type_combo.grid(row=0, column=1, sticky="w", padx=(6, 12))
        ttk.Label(top, text=f"Translation date: {_date_from_completed_at(self._seed.completed_at)}").grid(
            row=0, column=2, sticky="w", padx=(0, 6)
        )
        ttk.Label(top, text=f"Lang: {self._seed.lang} | Pages: {self._seed.pages} | Words: {self._seed.word_count}").grid(
            row=0, column=3, sticky="w"
        )

        case_frame = ttk.LabelFrame(top, text="CASE (belongs to)", padding=8)
        case_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        case_frame.columnconfigure(1, weight=1)
        case_frame.columnconfigure(4, weight=1)

        ttk.Label(case_frame, text="Case entity").grid(row=0, column=0, sticky="w")
        self.case_entity_combo = ttk.Combobox(
            case_frame,
            textvariable=self.case_entity_var,
            values=self._settings["vocab_case_entities"],
        )
        self.case_entity_combo.grid(row=0, column=1, sticky="ew", padx=(6, 6))
        ttk.Button(case_frame, text="Add...", command=self._add_case_entity).grid(row=0, column=2, sticky="w")

        ttk.Label(case_frame, text="Case city").grid(row=0, column=3, sticky="w", padx=(12, 0))
        self.case_city_combo = ttk.Combobox(
            case_frame,
            textvariable=self.case_city_var,
            values=self._settings["vocab_cities"],
        )
        self.case_city_combo.grid(row=0, column=4, sticky="ew", padx=(6, 6))
        ttk.Button(case_frame, text="Add...", command=self._add_city).grid(row=0, column=5, sticky="w")

        ttk.Label(case_frame, text="Case number").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(case_frame, textvariable=self.case_number_var).grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=(6, 6), pady=(8, 0)
        )

        service_frame = ttk.LabelFrame(top, text="SERVICE (provided to)", padding=8)
        service_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        service_frame.columnconfigure(1, weight=1)
        service_frame.columnconfigure(4, weight=1)

        self.service_same_check = ttk.Checkbutton(
            service_frame,
            text="Service same as Case",
            variable=self.service_same_var,
            command=self._on_service_same_toggled,
        )
        self.service_same_check.grid(row=0, column=0, columnspan=2, sticky="w")

        ttk.Label(service_frame, text="Service entity").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.service_entity_combo = ttk.Combobox(
            service_frame,
            textvariable=self.service_entity_var,
            values=self._settings["vocab_service_entities"],
        )
        self.service_entity_combo.grid(row=1, column=1, sticky="ew", padx=(6, 6), pady=(8, 0))
        ttk.Button(service_frame, text="Add...", command=self._add_service_entity).grid(row=1, column=2, sticky="w", pady=(8, 0))

        ttk.Label(service_frame, text="Service city").grid(row=1, column=3, sticky="w", padx=(12, 0), pady=(8, 0))
        self.service_city_combo = ttk.Combobox(
            service_frame,
            textvariable=self.service_city_var,
            values=self._settings["vocab_cities"],
        )
        self.service_city_combo.grid(row=1, column=4, sticky="ew", padx=(6, 6), pady=(8, 0))
        ttk.Button(service_frame, text="Add...", command=self._add_city).grid(row=1, column=5, sticky="w", pady=(8, 0))

        ttk.Label(service_frame, text="Service date (YYYY-MM-DD)").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(service_frame, textvariable=self.service_date_var, width=18).grid(
            row=2, column=1, sticky="w", padx=(6, 0), pady=(8, 0)
        )

        autofill = ttk.Frame(top)
        autofill.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        autofill.columnconfigure(4, weight=1)
        ttk.Button(autofill, text="Autofill from PDF header", command=self._autofill_from_pdf_header).grid(
            row=0, column=0, sticky="w"
        )
        self.photo_btn = ttk.Button(autofill, text="Autofill from photo...", command=self._autofill_from_photo)
        self.photo_btn.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.photo_translate_check = ttk.Checkbutton(
            autofill,
            variable=self.photo_translation_enable_var,
            text="Usually for Interpretation; enable anyway",
            command=self._refresh_photo_controls,
        )
        self.photo_translate_check.grid(row=0, column=2, sticky="w", padx=(10, 0))
        self.photo_hint = ttk.Label(autofill, text="")
        self.photo_hint.grid(row=0, column=3, sticky="w", padx=(8, 0))

        finance = ttk.LabelFrame(top, text="Amounts (EUR)", padding=8)
        finance.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        for idx in range(5):
            finance.columnconfigure(idx * 2 + 1, weight=1)

        fields = [
            ("Rate/word", self.rate_var),
            ("Expected total", self.expected_total_var),
            ("Amount paid", self.amount_paid_var),
            ("API cost", self.api_cost_var),
            ("Profit", self.profit_var),
        ]
        for idx, (label, var) in enumerate(fields):
            ttk.Label(finance, text=label).grid(row=0, column=idx * 2, sticky="w")
            ttk.Entry(finance, textvariable=var, width=12).grid(row=0, column=idx * 2 + 1, sticky="w", padx=(6, 10))

        buttons = ttk.Frame(top)
        buttons.grid(row=5, column=0, columnspan=4, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(buttons, text="Save", command=self._save).grid(row=0, column=1)

    def _bind_watchers(self) -> None:
        self.case_entity_combo.bind("<<ComboboxSelected>>", self._on_case_entity_user_edit)
        self.case_city_combo.bind("<<ComboboxSelected>>", self._on_case_city_user_edit)
        self.case_entity_combo.bind("<KeyRelease>", self._on_case_entity_user_edit)
        self.case_city_combo.bind("<KeyRelease>", self._on_case_city_user_edit)
        self.job_type_combo.bind("<<ComboboxSelected>>", self._on_job_type_changed)
        self.service_entity_combo.bind("<<ComboboxSelected>>", self._on_service_fields_changed)
        self.service_city_combo.bind("<<ComboboxSelected>>", self._on_service_fields_changed)
        self.service_entity_combo.bind("<KeyRelease>", self._on_service_fields_changed)
        self.service_city_combo.bind("<KeyRelease>", self._on_service_fields_changed)
        self.case_entity_var.trace_add("write", self._on_case_fields_changed)
        self.case_city_var.trace_add("write", self._on_case_fields_changed)

    def _on_case_entity_user_edit(self, *_: object) -> None:
        self._case_entity_user_set = True

    def _on_case_city_user_edit(self, *_: object) -> None:
        self._case_city_user_set = True

    def _on_case_fields_changed(self, *_: object) -> None:
        if self.service_same_var.get():
            self._sync_service_with_case()

    def _on_service_fields_changed(self, *_: object) -> None:
        self._apply_non_court_default_rule()

    def _on_service_same_toggled(self) -> None:
        self._refresh_service_mirror_state()
        self._settings["service_equals_case_by_default"] = bool(self.service_same_var.get())

    def _sync_service_with_case(self) -> None:
        self.service_entity_var.set(self.case_entity_var.get().strip())
        self.service_city_var.set(self.case_city_var.get().strip())

    def _refresh_service_mirror_state(self) -> None:
        same = self.service_same_var.get()
        if same:
            self._sync_service_with_case()
        state = tk.DISABLED if same else tk.NORMAL
        self.service_entity_combo.configure(state=state)
        self.service_city_combo.configure(state=state)

    def _on_job_type_changed(self, *_: object) -> None:
        self._refresh_photo_controls()

    def _refresh_photo_controls(self) -> None:
        photo_enabled = bool(self._settings["metadata_photo_enabled"])
        job_type = self.job_type_var.get().strip()
        if not photo_enabled:
            self.photo_btn.configure(state=tk.DISABLED)
            self.photo_translate_check.configure(state=tk.DISABLED)
            self.photo_hint.configure(text="Photo metadata disabled in settings.")
            return
        if job_type == "Interpretation":
            self.photo_btn.configure(state=tk.NORMAL)
            self.photo_translate_check.configure(state=tk.DISABLED)
            self.photo_hint.configure(text="Interpretation mode.")
            return
        self.photo_translate_check.configure(state=tk.NORMAL)
        enabled = bool(self.photo_translation_enable_var.get())
        self.photo_btn.configure(state=tk.NORMAL if enabled else tk.DISABLED)
        self.photo_hint.configure(text="Usually Interpretation.")

    def _ensure_in_vocab(self, key: str, value: str) -> None:
        cleaned = value.strip()
        if cleaned == "":
            return
        bucket = list(self._settings[key])
        lowered = {item.casefold() for item in bucket}
        if cleaned.casefold() in lowered:
            return
        bucket.append(cleaned)
        self._settings[key] = bucket
        self._refresh_vocab_widgets()

    def _refresh_vocab_widgets(self) -> None:
        self.case_entity_combo.configure(values=self._settings["vocab_case_entities"])
        self.service_entity_combo.configure(values=self._settings["vocab_service_entities"])
        self.case_city_combo.configure(values=self._settings["vocab_cities"])
        self.service_city_combo.configure(values=self._settings["vocab_cities"])
        self.job_type_combo.configure(values=self._settings["vocab_job_types"])

    def _add_case_entity(self) -> None:
        value = simpledialog.askstring("Add case entity", "Case entity:", parent=self)
        if not value:
            return
        self._ensure_in_vocab("vocab_case_entities", value)
        self.case_entity_var.set(value.strip())
        self._case_entity_user_set = True

    def _add_service_entity(self) -> None:
        value = simpledialog.askstring("Add service entity", "Service entity:", parent=self)
        if not value:
            return
        self._ensure_in_vocab("vocab_service_entities", value)
        self.service_entity_var.set(value.strip())
        self._apply_non_court_default_rule()

    def _add_city(self) -> None:
        value = simpledialog.askstring("Add city", "City:", parent=self)
        if not value:
            return
        self._ensure_in_vocab("vocab_cities", value)

    def _load_header_text(self) -> str:
        if self._header_text_cache is None:
            self._header_text_cache = extract_header_text_from_pdf_with_ocr_fallback(
                self._seed.pdf_path,
            )
        return self._header_text_cache

    def _apply_header_suggestion(self, suggestion: MetadataSuggestion) -> None:
        if suggestion.case_entity:
            self._ensure_in_vocab("vocab_case_entities", suggestion.case_entity)
            self.case_entity_var.set(suggestion.case_entity)
        if suggestion.case_city:
            self._ensure_in_vocab("vocab_cities", suggestion.case_city)
            self.case_city_var.set(suggestion.case_city)
        if suggestion.case_number:
            self.case_number_var.set(suggestion.case_number)
        if self.service_same_var.get():
            self._sync_service_with_case()
        else:
            if suggestion.service_entity and not self.service_entity_var.get().strip():
                self._ensure_in_vocab("vocab_service_entities", suggestion.service_entity)
                self.service_entity_var.set(suggestion.service_entity)
            if suggestion.service_city and not self.service_city_var.get().strip():
                self._ensure_in_vocab("vocab_cities", suggestion.service_city)
                self.service_city_var.set(suggestion.service_city)
        self._apply_non_court_default_rule()

    def _autofill_from_pdf_header(self) -> None:
        header_text = self._load_header_text()
        if not header_text.strip():
            messagebox.showwarning("Autofill", "No header text could be extracted.")
            return
        suggestion = extract_from_header_text(
            header_text,
            vocab_cities=list(self._settings["vocab_cities"]),
            ai_enabled=bool(self._settings["metadata_ai_enabled"]),
        )
        self._apply_header_suggestion(suggestion)

    def _autofill_from_photo(self) -> None:
        if not bool(self._settings["metadata_photo_enabled"]):
            messagebox.showwarning("Photo autofill", "Photo autofill is disabled in settings.")
            return
        if self.job_type_var.get().strip() == "Translation":
            accepted = messagebox.askyesno(
                "Apply photo metadata",
                "This looks like an Interpretation-style photo (service date/location). "
                "Apply to SERVICE fields anyway?",
            )
            if not accepted:
                return
        image_path_text = filedialog.askopenfilename(
            filetypes=[
                ("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.webp"),
                ("All files", "*.*"),
            ]
        )
        if not image_path_text:
            return
        try:
            ocr_text = extract_ocr_text_from_photo_image(Path(image_path_text))
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Photo autofill failed", str(exc))
            return
        suggestion = extract_from_photo_ocr_text(
            ocr_text,
            vocab_cities=list(self._settings["vocab_cities"]),
            ai_enabled=bool(self._settings["metadata_ai_enabled"]),
        )
        if suggestion.service_city:
            self._ensure_in_vocab("vocab_cities", suggestion.service_city)
            self.service_city_var.set(suggestion.service_city)
        if suggestion.service_date:
            self.service_date_var.set(suggestion.service_date)
        if suggestion.case_number and not self.case_number_var.get().strip():
            self.case_number_var.set(suggestion.case_number)
        self._apply_non_court_default_rule()

    def _apply_non_court_default_rule(self) -> None:
        case_entity, case_city = apply_service_case_default_rule(
            case_entity=self.case_entity_var.get().strip(),
            case_city=self.case_city_var.get().strip(),
            service_entity=self.service_entity_var.get().strip(),
            service_city=self.service_city_var.get().strip(),
            case_entity_user_set=self._case_entity_user_set,
            case_city_user_set=self._case_city_user_set,
            non_court_service_entities=list(self._settings["non_court_service_entities"]),
        )
        if case_entity is not None and case_entity != self.case_entity_var.get().strip():
            self.case_entity_var.set(case_entity)
            self._ensure_in_vocab("vocab_case_entities", case_entity)
        if case_city is not None and case_city != self.case_city_var.get().strip():
            self.case_city_var.set(case_city)
            self._ensure_in_vocab("vocab_cities", case_city)

    def _parse_float(self, value: str, label: str) -> float:
        cleaned = value.strip().replace(",", ".")
        if cleaned == "":
            return 0.0
        try:
            return float(cleaned)
        except ValueError as exc:
            raise ValueError(f"{label} must be numeric.") from exc

    def _save(self) -> None:
        try:
            rate = self._parse_float(self.rate_var.get(), "Rate/word")
            expected_total = self._parse_float(self.expected_total_var.get(), "Expected total")
            amount_paid = self._parse_float(self.amount_paid_var.get(), "Amount paid")
            api_cost = self._parse_float(self.api_cost_var.get(), "API cost")
            profit = self._parse_float(self.profit_var.get(), "Profit")
        except ValueError as exc:
            messagebox.showerror("Invalid values", str(exc))
            return

        if expected_total == 0.0 and rate > 0:
            expected_total = round(rate * float(self._seed.word_count), 2)
        if profit == 0.0:
            if amount_paid > 0:
                profit = round(amount_paid - api_cost, 2)
            else:
                profit = round(expected_total - api_cost, 2)

        service_date = self.service_date_var.get().strip()
        if service_date:
            try:
                datetime.strptime(service_date, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Invalid date", "Service date must be YYYY-MM-DD.")
                return

        case_entity = self.case_entity_var.get().strip()
        case_city = self.case_city_var.get().strip()
        service_entity = self.service_entity_var.get().strip()
        service_city = self.service_city_var.get().strip()
        if self.service_same_var.get():
            service_entity = case_entity
            service_city = case_city

        payload = {
            "completed_at": self._seed.completed_at,
            "job_type": self.job_type_var.get().strip() or "Translation",
            "case_number": self.case_number_var.get().strip(),
            "case_entity": case_entity,
            "case_city": case_city,
            "service_entity": service_entity,
            "service_city": service_city,
            "service_date": service_date,
            "lang": self._seed.lang,
            "pages": int(self._seed.pages),
            "word_count": int(self._seed.word_count),
            "rate_per_word": rate,
            "expected_total": expected_total,
            "amount_paid": amount_paid,
            "api_cost": api_cost,
            "profit": profit,
        }

        with closing(open_job_log(self._db_path)) as conn:
            insert_job_run(conn, payload)

        self._ensure_in_vocab("vocab_job_types", payload["job_type"])
        if case_entity:
            self._ensure_in_vocab("vocab_case_entities", case_entity)
        if service_entity:
            self._ensure_in_vocab("vocab_service_entities", service_entity)
        if case_city:
            self._ensure_in_vocab("vocab_cities", case_city)
        if service_city:
            self._ensure_in_vocab("vocab_cities", service_city)

        save_joblog_settings(
            {
                "vocab_case_entities": self._settings["vocab_case_entities"],
                "vocab_service_entities": self._settings["vocab_service_entities"],
                "vocab_cities": self._settings["vocab_cities"],
                "vocab_job_types": self._settings["vocab_job_types"],
                "default_rate_per_word": self._settings["default_rate_per_word"],
                "joblog_visible_columns": self._settings["joblog_visible_columns"],
                "metadata_ai_enabled": self._settings["metadata_ai_enabled"],
                "metadata_photo_enabled": self._settings["metadata_photo_enabled"],
                "service_equals_case_by_default": bool(self.service_same_var.get()),
                "non_court_service_entities": self._settings["non_court_service_entities"],
            }
        )
        self._saved = True
        if self._on_saved is not None:
            self._on_saved()
        self.destroy()


class JobLogWindow(tk.Toplevel):
    def __init__(self, master: tk.Misc, *, db_path: Path) -> None:
        super().__init__(master)
        self.title("Job Log")
        self.geometry("1280x500")
        self._db_path = db_path
        self._settings = load_joblog_settings()
        self._visible_columns = update_joblog_visible_columns(self._settings["joblog_visible_columns"])
        if not self._visible_columns:
            self._visible_columns = ["translation_date", "case_number", "job_type"]
        self._build_ui()
        self.refresh_rows()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        controls = ttk.Frame(self, padding=8)
        controls.grid(row=0, column=0, sticky="ew")
        ttk.Button(controls, text="Refresh", command=self.refresh_rows).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(controls, text="Columns...", command=self._open_columns_dialog).grid(row=0, column=1)

        frame = ttk.Frame(self, padding=(8, 0, 8, 8))
        frame.grid(row=1, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            frame,
            columns=JOBLOG_COLUMNS,
            show="headings",
            displaycolumns=self._visible_columns,
        )
        for col in JOBLOG_COLUMNS:
            self.tree.heading(col, text=JOBLOG_COLUMN_LABELS[col])
            width = 120
            if col in ("case_number", "service_entity", "case_entity"):
                width = 180
            elif col in ("translation_date", "service_date", "lang", "pages"):
                width = 90
            self.tree.column(col, width=width, anchor="w", stretch=True)

        yscroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

    def refresh_rows(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        with closing(open_job_log(self._db_path)) as conn:
            rows = list_job_runs(conn, limit=1000)
        for row in rows:
            values = [row[col] if col in row.keys() else "" for col in JOBLOG_COLUMNS]
            self.tree.insert(
                "",
                tk.END,
                values=values,
            )

    def _open_columns_dialog(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Visible Columns")
        dialog.transient(self)
        dialog.grab_set()
        vars_by_col: dict[str, tk.BooleanVar] = {}
        for idx, col in enumerate(JOBLOG_COLUMNS):
            var = tk.BooleanVar(value=(col in self._visible_columns))
            vars_by_col[col] = var
            ttk.Checkbutton(dialog, text=JOBLOG_COLUMN_LABELS[col], variable=var).grid(
                row=idx // 2,
                column=idx % 2,
                sticky="w",
                padx=8,
                pady=3,
            )

        def apply_columns() -> None:
            selected = [col for col in JOBLOG_COLUMNS if vars_by_col[col].get()]
            selected = update_joblog_visible_columns(selected)
            if not selected:
                messagebox.showwarning("Columns", "Select at least one column.", parent=dialog)
                return
            self._visible_columns = selected
            self.tree.configure(displaycolumns=self._visible_columns)
            self._settings["joblog_visible_columns"] = list(selected)
            save_joblog_settings({"joblog_visible_columns": list(selected)})
            dialog.destroy()

        button_row = (len(JOBLOG_COLUMNS) + 1) // 2 + 1
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).grid(row=button_row, column=0, sticky="e", padx=8, pady=8)
        ttk.Button(dialog, text="Apply", command=apply_columns).grid(row=button_row, column=1, sticky="w", padx=8, pady=8)
