"""Qt dialogs for glossary builder and calibration audit tools."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QSize, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from legalpdf_translate.calibration_audit import run_calibration_audit
from legalpdf_translate.glossary import (
    GlossaryEntry,
    build_consistency_glossary_markdown,
    load_project_glossaries,
    merge_glossary_scopes,
    normalize_enabled_tiers_by_target_lang,
    normalize_glossaries,
    save_project_glossaries,
    serialize_glossaries,
    supported_target_langs,
)
from legalpdf_translate.glossary_builder import (
    GlossaryBuilderSuggestion,
    build_glossary_builder_markdown,
    build_lemma_grouped_stats,
    compute_selection_delta,
    compute_selection_metadata,
    create_builder_stats,
    finalize_builder_suggestions,
    serialize_glossary_builder_suggestions,
    update_builder_stats_from_page,
)
from legalpdf_translate.glossary_diagnostics import (
    GlossaryDiagnosticsAccumulator,
    PageCoverageRecord,
    emit_diagnostics_events,
)
from legalpdf_translate.pdf_text_order import extract_ordered_page_text, get_page_count
from legalpdf_translate.qt_gui.window_adaptive import ResponsiveWindowController
from legalpdf_translate.types import RunConfig, TargetLang
from legalpdf_translate.user_settings import app_data_dir


def _entry_conflict_key(entry: GlossaryEntry) -> tuple[str, str, str, int]:
    return (entry.source_text, entry.source_lang, entry.match_mode, int(entry.tier))


def _entry_exact_key(entry: GlossaryEntry) -> tuple[str, str, str, str, int]:
    return (
        entry.source_text,
        entry.preferred_translation,
        entry.source_lang,
        entry.match_mode,
        int(entry.tier),
    )


def _merge_entries_into_scope(
    existing_by_lang: dict[str, list[GlossaryEntry]],
    additions_by_lang: dict[str, list[GlossaryEntry]],
    *,
    replace_conflicts: bool,
) -> tuple[dict[str, list[GlossaryEntry]], int, int, int]:
    supported = supported_target_langs()
    merged = normalize_glossaries(existing_by_lang, supported)
    added = 0
    skipped = 0
    conflicts = 0
    for lang in supported:
        bucket = list(merged.get(lang, []))
        index_by_conflict = {_entry_conflict_key(entry): idx for idx, entry in enumerate(bucket)}
        seen_exact = {_entry_exact_key(entry) for entry in bucket}
        for candidate in additions_by_lang.get(lang, []):
            exact_key = _entry_exact_key(candidate)
            if exact_key in seen_exact:
                skipped += 1
                continue
            conflict_key = _entry_conflict_key(candidate)
            prior_index = index_by_conflict.get(conflict_key)
            if prior_index is None:
                bucket.append(candidate)
                index_by_conflict[conflict_key] = len(bucket) - 1
                seen_exact.add(exact_key)
                added += 1
                continue
            conflicts += 1
            if not replace_conflicts:
                skipped += 1
                continue
            bucket[prior_index] = candidate
            seen_exact = {_entry_exact_key(entry) for entry in bucket}
            added += 1
        merged[lang] = bucket
    return (normalize_glossaries(merged, supported), added, skipped, conflicts)


def _load_page_text_from_run(run_dir: Path, page_number: int, pdf_path: Path | None) -> str:
    pages_dir = run_dir / "pages"
    page_file = pages_dir / f"page_{page_number:04d}.txt"
    if page_file.exists():
        try:
            return page_file.read_text(encoding="utf-8")
        except OSError:
            pass
    if pdf_path is None:
        return ""
    try:
        ordered = extract_ordered_page_text(pdf_path, page_number - 1)
    except Exception:  # noqa: BLE001
        return ""
    if ordered.extraction_failed:
        return ""
    return str(ordered.text or "")


class _GlossaryBuilderWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(object)
    cancelled = Signal()
    error = Signal(str)

    def __init__(
        self,
        *,
        source_mode: str,
        run_dirs: list[str],
        pdf_paths: list[str],
        target_lang: str,
        mode: str,
        lemma_enabled: bool = False,
        lemma_effort: str = "high",
    ) -> None:
        super().__init__()
        self._source_mode = str(source_mode or "run_folders").strip().lower()
        self._run_dirs = list(run_dirs)
        self._pdf_paths = list(pdf_paths)
        self._target_lang = str(target_lang or "EN").strip().upper()
        self._mode = mode if mode in {"full_text", "headers_only"} else "full_text"
        self._cancel_requested = False
        self._lemma_enabled = bool(lemma_enabled)
        self._lemma_effort = str(lemma_effort or "high").strip().lower()

    def cancel(self) -> None:
        self._cancel_requested = True

    def _iter_page_numbers(self, run_state_payload: dict[str, object]) -> list[int]:
        pages_payload = run_state_payload.get("pages")
        numbers: list[int] = []
        if isinstance(pages_payload, dict):
            for raw_key in pages_payload.keys():
                try:
                    value = int(str(raw_key))
                except (TypeError, ValueError):
                    continue
                if value > 0:
                    numbers.append(value)
        if numbers:
            return sorted(set(numbers))
        try:
            start = int(run_state_payload.get("selection_start_page", 1))
            end = int(run_state_payload.get("selection_end_page", start))
        except (TypeError, ValueError):
            return []
        if end < start:
            return []
        return list(range(start, end + 1))

    def run(self) -> None:
        try:
            t0 = time.monotonic()
            stats = create_builder_stats()
            accumulator = GlossaryDiagnosticsAccumulator(total_pages=0)
            total_pages_scanned = 0
            total_sources = 0
            source_mode = self._source_mode
            sources = self._run_dirs if source_mode == "run_folders" else self._pdf_paths
            source_total = max(1, len(sources))

            for source_index, raw_source in enumerate(sources, start=1):
                if self._cancel_requested:
                    self.cancelled.emit()
                    return
                if source_mode == "run_folders":
                    run_dir = Path(raw_source).expanduser().resolve()
                    run_state_path = run_dir / "run_state.json"
                    if not run_state_path.exists():
                        total_sources += 1
                        self.progress.emit(
                            int((source_index / float(source_total)) * 100.0),
                            f"Skipping {run_dir.name}: run_state.json not found.",
                        )
                        continue
                    try:
                        payload = json.loads(run_state_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        total_sources += 1
                        self.progress.emit(
                            int((source_index / float(source_total)) * 100.0),
                            f"Skipping {run_dir.name}: invalid run_state.json.",
                        )
                        continue
                    if not isinstance(payload, dict):
                        total_sources += 1
                        continue
                    pdf_path_raw = str(payload.get("pdf_path", "") or "").strip()
                    pdf_path = None
                    if pdf_path_raw:
                        candidate = Path(pdf_path_raw).expanduser()
                        if not candidate.is_absolute():
                            candidate = (run_dir / candidate).resolve()
                        if candidate.exists() and candidate.is_file():
                            pdf_path = candidate
                    doc_id = run_dir.name
                    for page_number in self._iter_page_numbers(payload):
                        if self._cancel_requested:
                            self.cancelled.emit()
                            return
                        page_text = _load_page_text_from_run(run_dir, page_number, pdf_path)
                        if page_text.strip() == "":
                            continue
                        update_builder_stats_from_page(
                            doc_id=doc_id,
                            page_number=page_number,
                            text=page_text,
                            stats=stats,
                            mode=self._mode,  # type: ignore[arg-type]
                        )
                        _pkg_tc = accumulator.record_page_pkg_stats(
                            page_index=page_number, source_text=page_text, doc_id=doc_id,
                        )
                        accumulator.record_page_coverage(PageCoverageRecord(
                            page_index=page_number, total_pages=0, source_route="direct_text",
                            char_count=len(page_text),
                            segment_count=len([ln for ln in page_text.splitlines() if ln.strip()]),
                            pkg_token_count=_pkg_tc,
                            cg_entries_active=0, cg_matches_count=0, cg_matched_keys=[],
                        ))
                        total_pages_scanned += 1
                    total_sources += 1
                else:
                    pdf_path = Path(raw_source).expanduser().resolve()
                    if not pdf_path.exists() or not pdf_path.is_file():
                        total_sources += 1
                        continue
                    try:
                        page_count = int(get_page_count(pdf_path))
                    except Exception:  # noqa: BLE001
                        total_sources += 1
                        continue
                    for page_number in range(1, page_count + 1):
                        if self._cancel_requested:
                            self.cancelled.emit()
                            return
                        try:
                            ordered = extract_ordered_page_text(pdf_path, page_number - 1)
                        except Exception:  # noqa: BLE001
                            continue
                        if ordered.extraction_failed:
                            continue
                        page_text = str(ordered.text or "")
                        if page_text.strip() == "":
                            continue
                        update_builder_stats_from_page(
                            doc_id=pdf_path.stem,
                            page_number=page_number,
                            text=page_text,
                            stats=stats,
                            mode=self._mode,  # type: ignore[arg-type]
                        )
                        _pkg_tc = accumulator.record_page_pkg_stats(
                            page_index=page_number, source_text=page_text, doc_id=pdf_path.stem,
                        )
                        accumulator.record_page_coverage(PageCoverageRecord(
                            page_index=page_number, total_pages=0, source_route="direct_text",
                            char_count=len(page_text),
                            segment_count=len([ln for ln in page_text.splitlines() if ln.strip()]),
                            pkg_token_count=_pkg_tc,
                            cg_entries_active=0, cg_matches_count=0, cg_matched_keys=[],
                        ))
                        total_pages_scanned += 1
                    total_sources += 1

                self.progress.emit(
                    int((source_index / float(source_total)) * 100.0),
                    f"Processed {source_index}/{source_total} sources; pages scanned: {total_pages_scanned}.",
                )

            # Patch accumulator with final page count
            accumulator._total_pages = total_pages_scanned
            with accumulator._lock:
                for _rec in accumulator._page_coverage.values():
                    _rec.total_pages = total_pages_scanned

            # Optional lemma normalization phase (analytics-only)
            lemma_result = None
            if self._lemma_enabled and total_pages_scanned > 0:
                self.progress.emit(95, "Running lemma normalization...")
                try:
                    from legalpdf_translate.lemma_normalizer import LemmaCache, batch_normalize_lemmas
                    from legalpdf_translate.openai_client import OpenAIResponsesClient as _LemmaClient

                    pkg_tf: dict[str, int] = stats.get("term_tf", {})
                    terms_to_normalize = [t for t, tf in pkg_tf.items() if int(tf) >= 2]
                    if terms_to_normalize:
                        _cache = LemmaCache(cache_path=app_data_dir() / "lemma_cache.json")
                        _client = _LemmaClient()
                        lemma_result = batch_normalize_lemmas(
                            terms_to_normalize,
                            client=_client,
                            effort=self._lemma_effort,
                            cache=_cache,
                        )
                        accumulator.set_lemma_mapping(lemma_result.mapping)
                except Exception:  # noqa: BLE001
                    pass  # Fallback: lemma mode disabled, surface-form Pareto used

            surface_suggestions = finalize_builder_suggestions(stats, target_lang=self._target_lang)

            selection_delta = None
            if lemma_result is not None and lemma_result.mapping and not lemma_result.fallback_to_surface:
                grouped_stats = build_lemma_grouped_stats(stats, lemma_result.mapping)
                lemma_suggestions = finalize_builder_suggestions(grouped_stats, target_lang=self._target_lang)
                selection_delta = compute_selection_delta(surface_suggestions, lemma_suggestions)
                suggestions = lemma_suggestions
            else:
                suggestions = surface_suggestions

            selection_metadata = compute_selection_metadata(
                stats, final_count=len(suggestions), selection_delta=selection_delta,
            )
            self.finished.emit(
                {
                    "suggestions": suggestions,
                    "selection_metadata": selection_metadata,
                    "sources_processed": total_sources,
                    "pages_scanned": total_pages_scanned,
                    "source_mode": source_mode,
                    "accumulator": accumulator,
                    "wall_seconds": time.monotonic() - t0,
                    "lemma_result": lemma_result,
                }
            )
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class _CalibrationAuditWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(object)
    cancelled = Signal()
    error = Signal(str)

    def __init__(
        self,
        *,
        config: RunConfig,
        settings: dict[str, object],
        sample_pages: int,
        user_seed: str,
        include_excerpts: bool,
        excerpt_max_chars: int,
    ) -> None:
        super().__init__()
        self._config = config
        self._settings = dict(settings)
        self._sample_pages = int(sample_pages)
        self._user_seed = str(user_seed or "")
        self._include_excerpts = bool(include_excerpts)
        self._excerpt_max_chars = int(excerpt_max_chars)
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            personal = normalize_glossaries(
                self._settings.get("personal_glossaries_by_lang", self._settings.get("glossaries_by_lang")),
                supported_target_langs(),
            )
            project = normalize_glossaries({}, supported_target_langs())
            glossary_path_raw = str(self._settings.get("glossary_file_path", "") or "").strip()
            if glossary_path_raw:
                project = load_project_glossaries(Path(glossary_path_raw))
            enabled = normalize_enabled_tiers_by_target_lang(
                self._settings.get("enabled_glossary_tiers_by_target_lang"),
                supported_target_langs(),
            )
            raw_addendum = self._settings.get("prompt_addendum_by_lang")
            addendum = raw_addendum if isinstance(raw_addendum, dict) else {}
            result = run_calibration_audit(
                config=self._config,
                personal_glossaries_by_lang=personal,
                project_glossaries_by_lang=project,
                enabled_tiers_by_lang=enabled,
                prompt_addendum_by_lang={lang: str(addendum.get(lang, "") or "") for lang in supported_target_langs()},
                sample_pages=self._sample_pages,
                user_seed=self._user_seed,
                include_excerpts=self._include_excerpts,
                excerpt_max_chars=self._excerpt_max_chars,
                progress_callback=lambda value, message: self.progress.emit(value, message),
                cancel_requested=lambda: self._cancel_requested,
            )
            self.finished.emit(result)
        except RuntimeError as exc:
            if "cancelled" in str(exc).lower():
                self.cancelled.emit()
                return
            self.error.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class QtGlossaryBuilderDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
        settings: dict[str, object],
        current_pdf_path: Path | None,
        current_output_dir: Path | None,
        default_target_lang: str,
        save_settings_callback: Callable[[dict[str, object]], None],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Glossary Builder")
        self.setMinimumSize(780, 560)
        self._settings = dict(settings)
        self._current_pdf_path = current_pdf_path
        self._current_output_dir = current_output_dir
        self._save_settings_callback = save_settings_callback
        self._worker_thread: QThread | None = None
        self._worker: _GlossaryBuilderWorker | None = None
        self._suggestions: list[GlossaryBuilderSuggestion] = []
        self._sources_processed = 0
        self._pages_scanned = 0
        self._accumulator: GlossaryDiagnosticsAccumulator | None = None
        self._wall_seconds: float = 0.0
        self._lemma_result: object | None = None
        self._selection_metadata: dict[str, Any] | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        _scroll_area = QScrollArea()
        _scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        _scroll_area.setWidgetResizable(True)
        _scroll_content = QWidget()
        scroll_layout = QVBoxLayout(_scroll_content)

        source_group = QGroupBox("Corpus")
        source_grid = QGridLayout(source_group)
        source_grid.setColumnStretch(0, 1)
        source_grid.setColumnStretch(1, 0)
        source_grid.setColumnStretch(2, 0)
        source_grid.setColumnStretch(3, 0)
        source_grid.addWidget(QLabel("Source"), 0, 0)
        self.source_combo = QComboBox()
        self.source_combo.addItem("Run folders", "run_folders")
        self.source_combo.addItem("Current PDF only", "current_pdf")
        self.source_combo.addItem("Select PDFs...", "select_pdfs")
        source_grid.addWidget(self.source_combo, 0, 1)
        source_grid.addWidget(QLabel("Target language"), 0, 2)
        self.target_lang_combo = QComboBox()
        self.target_lang_combo.addItems(supported_target_langs())
        self.target_lang_combo.setCurrentText(str(default_target_lang or "EN").strip().upper())
        source_grid.addWidget(self.target_lang_combo, 0, 3)
        source_grid.addWidget(QLabel("Mode"), 1, 2)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Full text", "full_text")
        self.mode_combo.addItem("Headers only", "headers_only")
        source_grid.addWidget(self.mode_combo, 1, 3)
        self.lemma_check = QCheckBox("Enable lemma grouping (affects suggestions; may call OpenAI)")
        self.lemma_check.setChecked(False)
        source_grid.addWidget(self.lemma_check, 2, 2)
        self.lemma_effort_combo = QComboBox()
        self.lemma_effort_combo.addItems(["high", "xhigh"])
        _default_lemma_effort = str(settings.get("openai_reasoning_effort_lemma", "high") or "high")
        if _default_lemma_effort in ("high", "xhigh"):
            self.lemma_effort_combo.setCurrentText(_default_lemma_effort)
        self.lemma_effort_combo.setEnabled(False)
        self.lemma_check.toggled.connect(self.lemma_effort_combo.setEnabled)
        source_grid.addWidget(self.lemma_effort_combo, 2, 3)

        source_grid.addWidget(QLabel("Run folders"), 1, 0)
        self.run_dirs_list = QListWidget()
        self.run_dirs_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        source_grid.addWidget(self.run_dirs_list, 2, 0, 3, 1)
        run_btn_col = QVBoxLayout()
        self.add_run_dir_btn = QPushButton("Add run folder")
        self.remove_run_dir_btn = QPushButton("Remove selected")
        self.clear_run_dirs_btn = QPushButton("Clear")
        run_btn_col.addWidget(self.add_run_dir_btn)
        run_btn_col.addWidget(self.remove_run_dir_btn)
        run_btn_col.addWidget(self.clear_run_dirs_btn)
        run_btn_col.addStretch(1)
        run_btn_wrap = QWidget()
        run_btn_wrap.setLayout(run_btn_col)
        source_grid.addWidget(run_btn_wrap, 2, 1, 3, 1)

        source_grid.addWidget(QLabel("PDF files"), 5, 0)
        self.pdf_paths_list = QListWidget()
        self.pdf_paths_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        source_grid.addWidget(self.pdf_paths_list, 6, 0, 2, 1)
        pdf_btn_col = QVBoxLayout()
        self.add_pdf_btn = QPushButton("Add PDF(s)")
        self.remove_pdf_btn = QPushButton("Remove selected")
        self.clear_pdf_btn = QPushButton("Clear")
        pdf_btn_col.addWidget(self.add_pdf_btn)
        pdf_btn_col.addWidget(self.remove_pdf_btn)
        pdf_btn_col.addWidget(self.clear_pdf_btn)
        pdf_btn_col.addStretch(1)
        pdf_btn_wrap = QWidget()
        pdf_btn_wrap.setLayout(pdf_btn_col)
        source_grid.addWidget(pdf_btn_wrap, 6, 1, 2, 1)

        self.current_pdf_label = QLabel("Current PDF: not available")
        self.current_pdf_label.setWordWrap(True)
        source_grid.addWidget(self.current_pdf_label, 8, 0, 1, 4)

        run_row = QHBoxLayout()
        self.generate_btn = QPushButton("Generate")
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        run_row.addWidget(self.generate_btn)
        run_row.addWidget(self.cancel_btn)
        run_row.addWidget(self.progress, 1)
        source_grid.addLayout(run_row, 9, 0, 1, 4)
        self.summary_label = QLabel("No suggestions generated yet.")
        source_grid.addWidget(self.summary_label, 10, 0, 1, 4)
        scroll_layout.addWidget(source_group)

        table_group = QGroupBox("Suggestions")
        table_layout = QVBoxLayout(table_group)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                "Use",
                "Source term",
                "Occ(doc)",
                "Occ(corpus)",
                "Pages",
                "Docs",
                "Confidence",
                "Scope",
                "Preferred translation",
            ]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        table_layout.addWidget(self.table)
        action_row = QHBoxLayout()
        self.apply_btn = QPushButton("Apply selected")
        self.close_btn = QPushButton("Close")
        action_row.addWidget(self.apply_btn)
        action_row.addStretch(1)
        action_row.addWidget(self.close_btn)
        table_layout.addLayout(action_row)
        scroll_layout.addWidget(table_group, 1)

        # -- Diagnostics section --
        diag_group = QGroupBox("Diagnostics")
        diag_layout = QHBoxLayout(diag_group)
        self.open_run_folder_btn = QPushButton("Open run folder")
        self.export_diagnostics_btn = QPushButton("Export diagnostics report (.md)\u2026")
        self.open_run_folder_btn.setEnabled(False)
        self.export_diagnostics_btn.setEnabled(False)
        self._diag_admin_mode = bool(settings.get("diagnostics_admin_mode", True))
        if not self._diag_admin_mode:
            self.export_diagnostics_btn.setToolTip(
                "Enable Admin Diagnostics in Settings to export a detailed report"
            )
        self.diag_path_label = QLabel("")
        self.diag_path_label.setWordWrap(True)
        diag_layout.addWidget(self.open_run_folder_btn)
        diag_layout.addWidget(self.export_diagnostics_btn)
        diag_layout.addWidget(self.diag_path_label, 1)
        scroll_layout.addWidget(diag_group)

        _scroll_area.setWidget(_scroll_content)
        root.addWidget(_scroll_area)
        self._last_artifact_dir: Path | None = None

        self.add_run_dir_btn.clicked.connect(self._add_run_folder)
        self.remove_run_dir_btn.clicked.connect(self._remove_selected_run_folders)
        self.clear_run_dirs_btn.clicked.connect(self._clear_run_folders)
        self.add_pdf_btn.clicked.connect(self._add_pdfs)
        self.remove_pdf_btn.clicked.connect(self._remove_selected_pdfs)
        self.clear_pdf_btn.clicked.connect(self._clear_pdfs)
        self.source_combo.currentTextChanged.connect(lambda _text: self._refresh_source_controls())
        self.generate_btn.clicked.connect(self._generate)
        self.cancel_btn.clicked.connect(self._cancel_generation)
        self.apply_btn.clicked.connect(self._apply_selected)
        self.close_btn.clicked.connect(self.close)
        self.open_run_folder_btn.clicked.connect(self._open_run_folder)
        self.export_diagnostics_btn.clicked.connect(self._export_diagnostics_report)

        run_dirs_raw = self._settings.get("study_glossary_last_run_dirs")
        if isinstance(run_dirs_raw, list):
            for raw in run_dirs_raw:
                cleaned = str(raw or "").strip()
                if cleaned:
                    self.run_dirs_list.addItem(cleaned)
        if self._current_pdf_path is not None and self._current_pdf_path.exists():
            self.current_pdf_label.setText(f"Current PDF: {self._current_pdf_path}")
        self._refresh_source_controls()
        self._responsive_window = ResponsiveWindowController(
            self,
            role="form",
            preferred_size=QSize(980, 720),
        )

    def _refresh_source_controls(self) -> None:
        mode = str(self.source_combo.currentData() or "run_folders")
        run_enabled = mode == "run_folders"
        pdf_enabled = mode == "select_pdfs"
        self.run_dirs_list.setEnabled(run_enabled)
        self.add_run_dir_btn.setEnabled(run_enabled)
        self.remove_run_dir_btn.setEnabled(run_enabled)
        self.clear_run_dirs_btn.setEnabled(run_enabled)
        self.pdf_paths_list.setEnabled(pdf_enabled)
        self.add_pdf_btn.setEnabled(pdf_enabled)
        self.remove_pdf_btn.setEnabled(pdf_enabled)
        self.clear_pdf_btn.setEnabled(pdf_enabled)

    def _add_run_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Select run folder")
        if not selected:
            return
        candidate = str(Path(selected).expanduser().resolve())
        existing = {self.run_dirs_list.item(i).text().strip().casefold() for i in range(self.run_dirs_list.count())}
        if candidate.casefold() in existing:
            return
        self.run_dirs_list.addItem(candidate)

    def _remove_selected_run_folders(self) -> None:
        for item in self.run_dirs_list.selectedItems():
            self.run_dirs_list.takeItem(self.run_dirs_list.row(item))

    def _clear_run_folders(self) -> None:
        self.run_dirs_list.clear()

    def _add_pdfs(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(
            self,
            "Select PDF files",
            "",
            "PDF Files (*.pdf);;All Files (*.*)",
        )
        if not selected:
            return
        existing = {self.pdf_paths_list.item(i).text().strip().casefold() for i in range(self.pdf_paths_list.count())}
        for raw in selected:
            cleaned = str(Path(raw).expanduser().resolve())
            if cleaned.casefold() in existing:
                continue
            self.pdf_paths_list.addItem(cleaned)
            existing.add(cleaned.casefold())

    def _remove_selected_pdfs(self) -> None:
        for item in self.pdf_paths_list.selectedItems():
            self.pdf_paths_list.takeItem(self.pdf_paths_list.row(item))

    def _clear_pdfs(self) -> None:
        self.pdf_paths_list.clear()

    def _collect_run_dirs(self) -> list[str]:
        rows: list[str] = []
        seen: set[str] = set()
        for idx in range(self.run_dirs_list.count()):
            item = self.run_dirs_list.item(idx)
            if item is None:
                continue
            cleaned = item.text().strip()
            if cleaned == "":
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            rows.append(cleaned)
        return rows

    def _collect_pdf_paths(self) -> list[str]:
        rows: list[str] = []
        seen: set[str] = set()
        for idx in range(self.pdf_paths_list.count()):
            item = self.pdf_paths_list.item(idx)
            if item is None:
                continue
            cleaned = item.text().strip()
            if cleaned == "":
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            rows.append(cleaned)
        return rows

    def _set_busy(self, busy: bool) -> None:
        self.generate_btn.setEnabled(not busy)
        self.cancel_btn.setEnabled(busy)

    def _generate(self) -> None:
        source_mode = str(self.source_combo.currentData() or "run_folders")
        run_dirs = self._collect_run_dirs()
        pdf_paths: list[str] = []
        if source_mode == "run_folders":
            if not run_dirs:
                QMessageBox.warning(self, "Glossary Builder", "Select at least one run folder.")
                return
        elif source_mode == "current_pdf":
            if self._current_pdf_path is None or not self._current_pdf_path.exists():
                QMessageBox.warning(self, "Glossary Builder", "No active PDF is available.")
                return
            pdf_paths = [str(self._current_pdf_path)]
        else:
            pdf_paths = self._collect_pdf_paths()
            if not pdf_paths:
                QMessageBox.warning(self, "Glossary Builder", "Select one or more PDF files.")
                return

        self.table.setRowCount(0)
        self._suggestions = []
        self.progress.setValue(0)
        self.summary_label.setText("Generating suggestions...")
        self._set_busy(True)

        thread = QThread(self)
        _lemma_effort = self.lemma_effort_combo.currentText().strip().lower() or "high"
        worker = _GlossaryBuilderWorker(
            source_mode=source_mode,
            run_dirs=run_dirs,
            pdf_paths=pdf_paths,
            target_lang=self.target_lang_combo.currentText().strip().upper(),
            mode=str(self.mode_combo.currentData() or "full_text"),
            lemma_enabled=bool(self.lemma_check.isChecked()),
            lemma_effort=_lemma_effort,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_generate_progress)
        worker.finished.connect(self._on_generate_finished)
        worker.cancelled.connect(self._on_generate_cancelled)
        worker.error.connect(self._on_generate_error)
        worker.finished.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._worker = worker
        self._worker_thread = thread
        thread.start()

    def _cancel_generation(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def _on_generate_progress(self, value: int, message: str) -> None:
        self.progress.setValue(max(0, min(100, int(value))))
        self.summary_label.setText(message)

    def _populate_table(self) -> None:
        self.table.setRowCount(0)
        for row_data in self._suggestions:
            row = self.table.rowCount()
            self.table.insertRow(row)
            use_check = QCheckBox()
            use_check.setChecked(True)
            use_wrap = QWidget()
            use_layout = QHBoxLayout(use_wrap)
            use_layout.setContentsMargins(0, 0, 0, 0)
            use_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            use_layout.addWidget(use_check)
            self.table.setCellWidget(row, 0, use_wrap)
            self.table.setItem(row, 1, QTableWidgetItem(row_data.source_term))
            self.table.setItem(row, 2, QTableWidgetItem(str(int(row_data.occurrences_doc))))
            self.table.setItem(row, 3, QTableWidgetItem(str(int(row_data.occurrences_corpus))))
            self.table.setItem(row, 4, QTableWidgetItem(str(int(row_data.df_pages))))
            self.table.setItem(row, 5, QTableWidgetItem(str(int(row_data.df_docs))))
            self.table.setItem(row, 6, QTableWidgetItem(f"{float(row_data.confidence):.3f}"))
            scope_combo = QComboBox()
            scope_combo.addItem("personal")
            scope_combo.addItem("project")
            scope_combo.setCurrentText(row_data.recommended_scope)
            self.table.setCellWidget(row, 7, scope_combo)
            translation_item = QTableWidgetItem(row_data.suggested_translation)
            self.table.setItem(row, 8, translation_item)

    def _artifact_dir(self) -> Path:
        if (
            self._current_output_dir is not None
            and self._current_output_dir.exists()
            and self._current_pdf_path is not None
            and self._current_pdf_path.exists()
        ):
            try:
                target_lang = TargetLang(self.target_lang_combo.currentText().strip().upper())
            except Exception:
                target_lang = TargetLang.EN
            from legalpdf_translate.output_paths import build_output_paths

            return build_output_paths(self._current_output_dir, self._current_pdf_path, target_lang).run_dir
        return app_data_dir() / "glossary_builder"

    def _write_artifacts(self) -> None:
        artifact_dir = self._artifact_dir().expanduser().resolve()
        artifact_dir.mkdir(parents=True, exist_ok=True)
        generated_at = datetime.now().replace(microsecond=0).isoformat()
        json_path = artifact_dir / "glossary_builder_suggestions.json"
        md_path = artifact_dir / "glossary_builder_suggestions.md"
        payload = {
            "generated_at_iso": generated_at,
            "target_lang": self.target_lang_combo.currentText().strip().upper(),
            "sources_processed": int(self._sources_processed),
            "pages_scanned": int(self._pages_scanned),
            "suggestions": serialize_glossary_builder_suggestions(self._suggestions),
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        markdown = build_glossary_builder_markdown(
            self._suggestions,
            generated_at_iso=generated_at,
            corpus_label=str(self.source_combo.currentText()),
            total_sources=self._sources_processed,
            total_pages_scanned=self._pages_scanned,
        )
        md_path.write_text(markdown, encoding="utf-8")

        if self._diag_admin_mode and self._accumulator is not None:
            self._write_run_report_artifacts(artifact_dir)

    def _write_run_report_artifacts(self, artifact_dir: Path) -> None:
        """Write run_state.json, run_summary.json, run_events.jsonl for diagnostics export."""
        from datetime import UTC
        from datetime import datetime as _dt

        from legalpdf_translate.run_report import RunEventCollector

        now_iso = _dt.now(UTC).isoformat()
        target_lang = self.target_lang_combo.currentText().strip().upper()
        pdf_path_str = str(self._current_pdf_path or "")
        pages_scanned = int(self._pages_scanned)

        # Clear stale events (RunEventCollector appends)
        events_path = artifact_dir / "run_events.jsonl"
        if events_path.exists():
            events_path.unlink()

        run_state = {
            "version": 1,
            "run_started_at": now_iso,
            "finished_at": now_iso,
            "run_status": "completed",
            "halt_reason": None,
            "lang": target_lang,
            "pdf_path": pdf_path_str,
            "total_pages": pages_scanned,
            "max_pages_effective": pages_scanned,
            "selection_start_page": 1,
            "selection_end_page": pages_scanned,
            "selection_page_count": pages_scanned,
            "run_dir_abs": str(artifact_dir),
            "pages": {},
            "done_count": pages_scanned,
            "failed_count": 0,
            "pending_count": 0,
        }
        (artifact_dir / "run_state.json").write_text(
            json.dumps(run_state, ensure_ascii=False, indent=2), encoding="utf-8",
        )

        # Merge lemma API usage into totals (instead of hardcoding 0)
        _lemma_in = int(getattr(self._lemma_result, "input_tokens", 0)) if self._lemma_result else 0
        _lemma_out = int(getattr(self._lemma_result, "output_tokens", 0)) if self._lemma_result else 0
        _lemma_api = int(getattr(self._lemma_result, "api_calls", 0)) if self._lemma_result else 0

        run_summary = {
            "run_id": f"glossary_builder_{now_iso}",
            "pdf_path": pdf_path_str,
            "lang": target_lang,
            "selected_pages_count": pages_scanned,
            "totals": {
                "total_wall_seconds": round(self._wall_seconds, 3),
                "api_calls_total": _lemma_api,
                "total_input_tokens": _lemma_in,
                "total_output_tokens": _lemma_out,
                "total_reasoning_tokens": 0,
                "total_tokens": _lemma_in + _lemma_out,
            },
            "counts": {
                "pages_images": 0,
                "pages_retries": 0,
                "pages_failed": 0,
            },
            "pipeline": {},
            "settings": {
                "lemma_enabled": bool(self._lemma_result is not None),
                "lemma_effort": (
                    self.lemma_effort_combo.currentText().strip().lower()
                    if self._lemma_result is not None else ""
                ),
            },
        }
        (artifact_dir / "run_summary.json").write_text(
            json.dumps(run_summary, ensure_ascii=False, indent=2), encoding="utf-8",
        )

        collector = RunEventCollector(run_dir=artifact_dir, enabled=True)
        emit_diagnostics_events(self._accumulator, collector)

        # Emit lemma normalization summary event if lemma phase ran
        if self._lemma_result is not None:
            lr = self._lemma_result
            collector.add_event(
                event_type="lemma_normalization_summary",
                stage="glossary_diagnostics",
                details={
                    "terms_total": int(getattr(lr, "cache_hits", 0)) + int(getattr(lr, "cache_misses", 0)),
                    "cache_hits": int(getattr(lr, "cache_hits", 0)),
                    "api_calls": int(getattr(lr, "api_calls", 0)),
                    "input_tokens": int(getattr(lr, "input_tokens", 0)),
                    "output_tokens": int(getattr(lr, "output_tokens", 0)),
                    "failures": int(getattr(lr, "failures", 0)),
                    "fallback_to_surface": bool(getattr(lr, "fallback_to_surface", False)),
                    "wall_seconds": round(float(getattr(lr, "wall_seconds", 0.0)), 3),
                },
            )

        # Emit suggestion selection summary event
        if self._selection_metadata is not None:
            collector.add_event(
                event_type="suggestion_selection_summary",
                stage="glossary_diagnostics",
                details=self._selection_metadata,
            )

    def _on_generate_finished(self, payload: object) -> None:
        self._set_busy(False)
        data = payload if isinstance(payload, dict) else {}
        suggestions = data.get("suggestions")
        self._suggestions = [row for row in suggestions if isinstance(row, GlossaryBuilderSuggestion)] if isinstance(suggestions, list) else []
        self._sources_processed = int(data.get("sources_processed", 0) or 0)
        self._pages_scanned = int(data.get("pages_scanned", 0) or 0)
        self._accumulator = data.get("accumulator") if isinstance(data.get("accumulator"), GlossaryDiagnosticsAccumulator) else None
        self._wall_seconds = float(data.get("wall_seconds", 0.0) or 0.0)
        self._lemma_result = data.get("lemma_result")
        _sm = data.get("selection_metadata")
        self._selection_metadata = _sm if isinstance(_sm, dict) else None
        self._populate_table()
        self.progress.setValue(100)
        self.summary_label.setText(
            f"Generated {len(self._suggestions)} suggestions from {self._sources_processed} sources / {self._pages_scanned} pages."
        )
        try:
            self._write_artifacts()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Glossary Builder", f"Suggestions generated but artifact save failed: {exc}")
        self._worker = None
        self._worker_thread = None
        self._update_diagnostics_buttons()

    def _update_diagnostics_buttons(self) -> None:
        try:
            artifact_dir = self._artifact_dir().expanduser().resolve()
        except Exception:
            artifact_dir = None
        self._last_artifact_dir = artifact_dir
        has_dir = artifact_dir is not None and artifact_dir.exists()
        self.open_run_folder_btn.setEnabled(has_dir)
        can_export = has_dir and self._diag_admin_mode
        self.export_diagnostics_btn.setEnabled(can_export)
        if has_dir:
            self.diag_path_label.setText(str(artifact_dir))
        else:
            self.diag_path_label.setText("")

    def _on_generate_cancelled(self) -> None:
        self._set_busy(False)
        self.summary_label.setText("Generation cancelled.")
        self.progress.setValue(0)
        self._worker = None
        self._worker_thread = None

    def _on_generate_error(self, message: str) -> None:
        self._set_busy(False)
        self.summary_label.setText("Generation failed.")
        self.progress.setValue(0)
        self._worker = None
        self._worker_thread = None
        QMessageBox.critical(self, "Glossary Builder", message or "Failed to generate suggestions.")

    def _open_run_folder(self) -> None:
        target = self._last_artifact_dir
        if target is None or not target.exists():
            QMessageBox.information(self, "Glossary Builder", "No run folder available.")
            return
        import os
        import subprocess

        try:
            if os.name == "nt":
                os.startfile(str(target))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Glossary Builder", f"Failed to open folder: {exc}")

    def _export_diagnostics_report(self) -> None:
        run_dir = self._last_artifact_dir
        if run_dir is None or not run_dir.exists():
            QMessageBox.information(self, "Glossary Builder", "No run folder available.")
            return
        from legalpdf_translate.run_report import build_run_report_markdown

        include_snippets = bool(self._settings.get("diagnostics_include_sanitized_snippets", False))
        try:
            report_text = build_run_report_markdown(
                run_dir=run_dir,
                admin_mode=True,
                include_sanitized_snippets=include_snippets,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Glossary Builder",
                f"Failed to generate diagnostics report:\n{exc}\n\n"
                f"Run folder: {run_dir}\n"
                "Check that run_events.jsonl and run_summary.json exist.",
            )
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"glossary_run_report_{timestamp}.md"
        default_path = run_dir / default_name
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Diagnostics Report",
            str(default_path),
            "Markdown (*.md);;Text (*.txt);;All Files (*.*)",
        )
        if not save_path:
            return
        output_path = Path(save_path).expanduser().resolve()
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report_text, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Glossary Builder", f"Failed to save report: {exc}")
            return
        self.summary_label.setText(f"Diagnostics report exported: {output_path.name}")

    def _selected_rows(self) -> list[tuple[GlossaryBuilderSuggestion, str, str]]:
        selected: list[tuple[GlossaryBuilderSuggestion, str, str]] = []
        for row_index, suggestion in enumerate(self._suggestions):
            use_wrap = self.table.cellWidget(row_index, 0)
            use_checked = False
            if use_wrap is not None:
                checkbox = use_wrap.findChild(QCheckBox)
                use_checked = bool(checkbox and checkbox.isChecked())
            if not use_checked:
                continue
            scope_widget = self.table.cellWidget(row_index, 7)
            scope = "personal"
            if isinstance(scope_widget, QComboBox):
                scope = str(scope_widget.currentText() or "personal").strip().lower()
            translation_item = self.table.item(row_index, 8)
            translation = translation_item.text().strip() if translation_item else ""
            selected.append((suggestion, scope, translation))
        return selected

    def _apply_selected(self) -> None:
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(self, "Glossary Builder", "No selected rows to apply.")
            return

        additions_personal: dict[str, list[GlossaryEntry]] = {lang: [] for lang in supported_target_langs()}
        additions_project: dict[str, list[GlossaryEntry]] = {lang: [] for lang in supported_target_langs()}
        skipped_missing_translation = 0
        target_lang = self.target_lang_combo.currentText().strip().upper()
        if target_lang not in supported_target_langs():
            QMessageBox.critical(self, "Glossary Builder", f"Unsupported target language: {target_lang}")
            return
        for suggestion, scope, translation in rows:
            preferred = translation.strip()
            if preferred == "":
                skipped_missing_translation += 1
                continue
            entry = GlossaryEntry(
                source_text=suggestion.source_term.strip(),
                preferred_translation=preferred,
                match_mode="exact",
                source_lang="PT",
                tier=2,
            )
            if scope == "project":
                additions_project[target_lang].append(entry)
            else:
                additions_personal[target_lang].append(entry)

        if all(len(values) == 0 for values in additions_personal.values()) and all(
            len(values) == 0 for values in additions_project.values()
        ):
            QMessageBox.information(
                self,
                "Glossary Builder",
                "No rows with preferred translation were selected.",
            )
            return

        personal = normalize_glossaries(
            self._settings.get("personal_glossaries_by_lang", self._settings.get("glossaries_by_lang")),
            supported_target_langs(),
        )
        project_path_raw = str(self._settings.get("glossary_file_path", "") or "").strip()
        project_path: Path | None = Path(project_path_raw).expanduser().resolve() if project_path_raw else None
        if any(additions_project.get(lang) for lang in supported_target_langs()) and project_path is None:
            selected, _ = QFileDialog.getSaveFileName(
                self,
                "Select project glossary file",
                str((app_data_dir() / "project_glossary.json").expanduser().resolve()),
                "JSON Files (*.json);;All Files (*.*)",
            )
            if not selected:
                QMessageBox.information(self, "Glossary Builder", "Project rows were not applied (no file selected).")
                additions_project = {lang: [] for lang in supported_target_langs()}
            else:
                project_path = Path(selected).expanduser().resolve()
                self._settings["glossary_file_path"] = str(project_path)

        project = normalize_glossaries({}, supported_target_langs())
        if project_path is not None:
            try:
                project = load_project_glossaries(project_path)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "Glossary Builder", f"Unable to load project glossary:\n{exc}")
                return

        conflicts_estimate = 0
        for lang in supported_target_langs():
            for target_scope, base in (("personal", personal), ("project", project)):
                additions = additions_personal if target_scope == "personal" else additions_project
                for entry in additions.get(lang, []):
                    for existing in base.get(lang, []):
                        if _entry_conflict_key(existing) == _entry_conflict_key(entry) and (
                            existing.preferred_translation != entry.preferred_translation
                        ):
                            conflicts_estimate += 1
                            break
        replace_conflicts = False
        if conflicts_estimate > 0:
            decision = QMessageBox.question(
                self,
                "Glossary Builder",
                "Conflicts detected. Replace existing conflicting rows?\n\nYes = replace, No = keep existing, Cancel = abort.",
                buttons=(
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No
                    | QMessageBox.StandardButton.Cancel
                ),
                defaultButton=QMessageBox.StandardButton.No,
            )
            if decision == QMessageBox.StandardButton.Cancel:
                return
            replace_conflicts = decision == QMessageBox.StandardButton.Yes

        personal_merged, personal_added, personal_skipped, personal_conflicts = _merge_entries_into_scope(
            personal,
            additions_personal,
            replace_conflicts=replace_conflicts,
        )
        project_merged, project_added, project_skipped, project_conflicts = _merge_entries_into_scope(
            project,
            additions_project,
            replace_conflicts=replace_conflicts,
        )

        if project_path is not None:
            try:
                save_project_glossaries(project_path, project_merged)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "Glossary Builder", f"Unable to save project glossary:\n{exc}")
                return

        self._settings["personal_glossaries_by_lang"] = serialize_glossaries(personal_merged)
        self._settings["glossaries_by_lang"] = serialize_glossaries(personal_merged)
        self._save_settings_callback(
            {
                "personal_glossaries_by_lang": self._settings["personal_glossaries_by_lang"],
                "glossaries_by_lang": self._settings["glossaries_by_lang"],
                "glossary_file_path": str(self._settings.get("glossary_file_path", "") or ""),
            }
        )
        QMessageBox.information(
            self,
            "Glossary Builder",
            (
                f"Applied.\n\n"
                f"Personal: added {personal_added}, skipped {personal_skipped}, conflicts {personal_conflicts}\n"
                f"Project: added {project_added}, skipped {project_skipped}, conflicts {project_conflicts}\n"
                f"Skipped (missing translation): {skipped_missing_translation}"
            ),
        )


class QtCalibrationAuditDialog(QDialog):
    def __init__(
        self,
        *,
        parent: QWidget | None,
        settings: dict[str, object],
        build_config_callback: Callable[[], RunConfig],
        save_settings_callback: Callable[[dict[str, object]], None],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calibration Audit")
        self.setMinimumSize(780, 560)
        self._settings = dict(settings)
        self._build_config_callback = build_config_callback
        self._save_settings_callback = save_settings_callback
        self._worker_thread: QThread | None = None
        self._worker: _CalibrationAuditWorker | None = None
        self._last_result: dict[str, object] | None = None
        self._last_config: RunConfig | None = None

        root = QVBoxLayout(self)
        options_group = QGroupBox("Run options")
        options_grid = QGridLayout(options_group)
        options_grid.addWidget(QLabel("Sample pages"), 0, 0)
        self.sample_pages_spin = QSpinBox()
        self.sample_pages_spin.setRange(1, 20)
        self.sample_pages_spin.setValue(int(self._settings.get("calibration_sample_pages_default", 5) or 5))
        options_grid.addWidget(self.sample_pages_spin, 0, 1)
        options_grid.addWidget(QLabel("User seed"), 0, 2)
        self.user_seed_edit = QLineEdit(str(self._settings.get("calibration_user_seed", "") or ""))
        options_grid.addWidget(self.user_seed_edit, 0, 3)
        self.include_excerpts_check = QCheckBox("Store evidence excerpts (privacy-sensitive)")
        self.include_excerpts_check.setChecked(bool(self._settings.get("calibration_enable_excerpt_storage", False)))
        options_grid.addWidget(self.include_excerpts_check, 1, 0, 1, 2)
        options_grid.addWidget(QLabel("Excerpt max chars"), 1, 2)
        self.excerpt_chars_spin = QSpinBox()
        self.excerpt_chars_spin.setRange(40, 500)
        self.excerpt_chars_spin.setValue(int(self._settings.get("calibration_excerpt_max_chars", 200) or 200))
        options_grid.addWidget(self.excerpt_chars_spin, 1, 3)
        run_row = QHBoxLayout()
        self.run_btn = QPushButton("Run audit")
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        run_row.addWidget(self.run_btn)
        run_row.addWidget(self.cancel_btn)
        run_row.addWidget(self.progress, 1)
        options_grid.addLayout(run_row, 2, 0, 1, 4)
        self.summary_label = QLabel("No audit run yet.")
        options_grid.addWidget(self.summary_label, 3, 0, 1, 4)
        root.addWidget(options_group)

        findings_group = QGroupBox("Findings")
        findings_layout = QVBoxLayout(findings_group)
        self.findings_table = QTableWidget(0, 6)
        self.findings_table.setHorizontalHeaderLabels(
            ["Use", "Page", "Issue type", "Severity", "Explanation", "Recommended fix"]
        )
        self.findings_table.verticalHeader().setVisible(False)
        self.findings_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.findings_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.findings_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        findings_layout.addWidget(self.findings_table)
        root.addWidget(findings_group, 1)

        suggestions_group = QGroupBox("Suggestions")
        suggestions_layout = QVBoxLayout(suggestions_group)
        self.glossary_suggestions_table = QTableWidget(0, 9)
        self.glossary_suggestions_table.setHorizontalHeaderLabels(
            ["Use", "Source", "Preferred translation", "Target", "Source lang", "Match", "Tier", "Scope", "Page"]
        )
        self.glossary_suggestions_table.verticalHeader().setVisible(False)
        self.glossary_suggestions_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.glossary_suggestions_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        suggestions_layout.addWidget(self.glossary_suggestions_table)
        self.apply_addendum_check = QCheckBox("Apply prompt addendum suggestion")
        suggestions_layout.addWidget(self.apply_addendum_check)
        self.addendum_edit = QLineEdit()
        suggestions_layout.addWidget(self.addendum_edit)
        action_row = QHBoxLayout()
        self.apply_btn = QPushButton("Apply selected suggestions")
        self.close_btn = QPushButton("Close")
        action_row.addWidget(self.apply_btn)
        action_row.addStretch(1)
        action_row.addWidget(self.close_btn)
        suggestions_layout.addLayout(action_row)
        root.addWidget(suggestions_group)

        self.run_btn.clicked.connect(self._run_audit)
        self.cancel_btn.clicked.connect(self._cancel_audit)
        self.apply_btn.clicked.connect(self._apply_suggestions)
        self.close_btn.clicked.connect(self.close)
        self._responsive_window = ResponsiveWindowController(
            self,
            role="form",
            preferred_size=QSize(980, 740),
        )

    def _set_busy(self, busy: bool) -> None:
        self.run_btn.setEnabled(not busy)
        self.cancel_btn.setEnabled(busy)

    def _run_audit(self) -> None:
        try:
            config = self._build_config_callback()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Calibration Audit", str(exc))
            return
        self._last_config = config
        self._last_result = None
        self.findings_table.setRowCount(0)
        self.glossary_suggestions_table.setRowCount(0)
        self.addendum_edit.clear()
        self.apply_addendum_check.setChecked(False)
        self.progress.setValue(0)
        self.summary_label.setText("Running calibration audit...")
        self._set_busy(True)

        thread = QThread(self)
        worker = _CalibrationAuditWorker(
            config=config,
            settings=self._settings,
            sample_pages=int(self.sample_pages_spin.value()),
            user_seed=self.user_seed_edit.text().strip(),
            include_excerpts=bool(self.include_excerpts_check.isChecked()),
            excerpt_max_chars=int(self.excerpt_chars_spin.value()),
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_audit_progress)
        worker.finished.connect(self._on_audit_finished)
        worker.cancelled.connect(self._on_audit_cancelled)
        worker.error.connect(self._on_audit_error)
        worker.finished.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._worker = worker
        self._worker_thread = thread
        thread.start()

    def _cancel_audit(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def _on_audit_progress(self, value: int, message: str) -> None:
        self.progress.setValue(max(0, min(100, int(value))))
        self.summary_label.setText(message)

    def _on_audit_finished(self, payload: object) -> None:
        self._set_busy(False)
        self.progress.setValue(100)
        result = payload if isinstance(payload, dict) else {}
        self._last_result = result
        report = result.get("report", {})
        suggestions = result.get("suggestions", {})
        findings = report.get("findings", []) if isinstance(report, dict) else []
        if isinstance(findings, list):
            self._populate_findings(findings)
        glossary_rows = suggestions.get("glossary_suggestions", []) if isinstance(suggestions, dict) else []
        if isinstance(glossary_rows, list):
            self._populate_glossary_suggestions(glossary_rows)
        addendum_rows = suggestions.get("prompt_addendum_suggestions", []) if isinstance(suggestions, dict) else []
        if isinstance(addendum_rows, list) and addendum_rows:
            self.addendum_edit.setText(str(addendum_rows[0]))
            self.apply_addendum_check.setChecked(True)
        report_path = result.get("report_json_path")
        self.summary_label.setText(
            f"Audit complete. Findings: {self.findings_table.rowCount()}. Report: {report_path}"
        )
        self._worker = None
        self._worker_thread = None

    def _on_audit_cancelled(self) -> None:
        self._set_busy(False)
        self.progress.setValue(0)
        self.summary_label.setText("Calibration audit cancelled.")
        self._worker = None
        self._worker_thread = None

    def _on_audit_error(self, message: str) -> None:
        self._set_busy(False)
        self.progress.setValue(0)
        self.summary_label.setText("Calibration audit failed.")
        self._worker = None
        self._worker_thread = None
        QMessageBox.critical(self, "Calibration Audit", message or "Calibration audit failed.")

    def _populate_findings(self, findings: list[object]) -> None:
        self.findings_table.setRowCount(0)
        for row in findings:
            if not isinstance(row, dict):
                continue
            table_row = self.findings_table.rowCount()
            self.findings_table.insertRow(table_row)
            check = QCheckBox()
            check.setChecked(True)
            wrap = QWidget()
            lay = QHBoxLayout(wrap)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(check)
            self.findings_table.setCellWidget(table_row, 0, wrap)
            self.findings_table.setItem(table_row, 1, QTableWidgetItem(str(row.get("page_number", ""))))
            self.findings_table.setItem(table_row, 2, QTableWidgetItem(str(row.get("issue_type", ""))))
            self.findings_table.setItem(table_row, 3, QTableWidgetItem(str(row.get("severity", ""))))
            self.findings_table.setItem(table_row, 4, QTableWidgetItem(str(row.get("explanation", ""))))
            self.findings_table.setItem(table_row, 5, QTableWidgetItem(str(row.get("recommended_fix", ""))))

    def _populate_glossary_suggestions(self, rows: list[object]) -> None:
        self.glossary_suggestions_table.setRowCount(0)
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            table_row = self.glossary_suggestions_table.rowCount()
            self.glossary_suggestions_table.insertRow(table_row)
            check = QCheckBox()
            check.setChecked(True)
            wrap = QWidget()
            lay = QHBoxLayout(wrap)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(check)
            self.glossary_suggestions_table.setCellWidget(table_row, 0, wrap)
            self.glossary_suggestions_table.setItem(table_row, 1, QTableWidgetItem(str(raw.get("source_text", ""))))
            self.glossary_suggestions_table.setItem(
                table_row,
                2,
                QTableWidgetItem(str(raw.get("preferred_translation", ""))),
            )
            self.glossary_suggestions_table.setItem(table_row, 3, QTableWidgetItem(str(raw.get("target_lang", ""))))
            self.glossary_suggestions_table.setItem(table_row, 4, QTableWidgetItem(str(raw.get("source_lang", ""))))
            self.glossary_suggestions_table.setItem(table_row, 5, QTableWidgetItem(str(raw.get("match_mode", ""))))
            self.glossary_suggestions_table.setItem(table_row, 6, QTableWidgetItem(str(raw.get("tier", 2))))
            scope_combo = QComboBox()
            scope_combo.addItem("personal")
            scope_combo.addItem("project")
            scope_combo.setCurrentText("personal")
            self.glossary_suggestions_table.setCellWidget(table_row, 7, scope_combo)
            self.glossary_suggestions_table.setItem(table_row, 8, QTableWidgetItem(str(raw.get("page_number", ""))))

    def _selected_glossary_suggestions(self) -> list[tuple[GlossaryEntry, str, str]]:
        rows: list[tuple[GlossaryEntry, str, str]] = []
        for row in range(self.glossary_suggestions_table.rowCount()):
            wrap = self.glossary_suggestions_table.cellWidget(row, 0)
            checkbox = wrap.findChild(QCheckBox) if wrap is not None else None
            if checkbox is None or not checkbox.isChecked():
                continue
            source = (
                self.glossary_suggestions_table.item(row, 1).text()
                if self.glossary_suggestions_table.item(row, 1)
                else ""
            ).strip()
            target = (
                self.glossary_suggestions_table.item(row, 2).text()
                if self.glossary_suggestions_table.item(row, 2)
                else ""
            ).strip()
            target_lang = (
                self.glossary_suggestions_table.item(row, 3).text()
                if self.glossary_suggestions_table.item(row, 3)
                else ""
            ).strip().upper()
            source_lang = (
                self.glossary_suggestions_table.item(row, 4).text()
                if self.glossary_suggestions_table.item(row, 4)
                else "PT"
            ).strip().upper() or "PT"
            match_mode = (
                self.glossary_suggestions_table.item(row, 5).text()
                if self.glossary_suggestions_table.item(row, 5)
                else "exact"
            ).strip().lower() or "exact"
            tier_text = (
                self.glossary_suggestions_table.item(row, 6).text()
                if self.glossary_suggestions_table.item(row, 6)
                else "2"
            ).strip()
            scope_widget = self.glossary_suggestions_table.cellWidget(row, 7)
            scope = scope_widget.currentText().strip().lower() if isinstance(scope_widget, QComboBox) else "personal"
            try:
                tier = int(tier_text)
            except ValueError:
                tier = 2
            if source == "" or target == "" or target_lang not in supported_target_langs():
                continue
            entry = GlossaryEntry(
                source_text=source,
                preferred_translation=target,
                match_mode="contains" if match_mode == "contains" else "exact",
                source_lang=source_lang if source_lang in {"AUTO", "ANY", "PT", "EN", "FR"} else "PT",  # type: ignore[arg-type]
                tier=max(1, min(6, tier)),
            )
            rows.append((entry, scope, target_lang))
        return rows

    def _apply_suggestions(self) -> None:
        suggestions = self._selected_glossary_suggestions()
        apply_addendum = self.apply_addendum_check.isChecked()
        addendum_text = self.addendum_edit.text().strip()
        if not suggestions and not (apply_addendum and addendum_text):
            QMessageBox.information(self, "Calibration Audit", "Nothing selected to apply.")
            return

        additions_personal: dict[str, list[GlossaryEntry]] = {lang: [] for lang in supported_target_langs()}
        additions_project: dict[str, list[GlossaryEntry]] = {lang: [] for lang in supported_target_langs()}
        for entry, scope, target_lang in suggestions:
            if scope == "project":
                additions_project[target_lang].append(entry)
            else:
                additions_personal[target_lang].append(entry)

        personal = normalize_glossaries(
            self._settings.get("personal_glossaries_by_lang", self._settings.get("glossaries_by_lang")),
            supported_target_langs(),
        )
        project_path_raw = str(self._settings.get("glossary_file_path", "") or "").strip()
        project_path: Path | None = Path(project_path_raw).expanduser().resolve() if project_path_raw else None
        if any(additions_project.get(lang) for lang in supported_target_langs()) and project_path is None:
            selected, _ = QFileDialog.getSaveFileName(
                self,
                "Select project glossary file",
                str((app_data_dir() / "project_glossary.json").expanduser().resolve()),
                "JSON Files (*.json);;All Files (*.*)",
            )
            if not selected:
                QMessageBox.information(self, "Calibration Audit", "Project suggestions were skipped.")
                additions_project = {lang: [] for lang in supported_target_langs()}
            else:
                project_path = Path(selected).expanduser().resolve()
                self._settings["glossary_file_path"] = str(project_path)
        project = normalize_glossaries({}, supported_target_langs())
        if project_path is not None:
            try:
                project = load_project_glossaries(project_path)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "Calibration Audit", f"Unable to load project glossary:\n{exc}")
                return

        conflict_estimate = 0
        for lang in supported_target_langs():
            for target_scope, scope_rows in (("personal", additions_personal), ("project", additions_project)):
                base = personal if target_scope == "personal" else project
                for entry in scope_rows.get(lang, []):
                    for existing in base.get(lang, []):
                        if _entry_conflict_key(existing) == _entry_conflict_key(entry) and (
                            existing.preferred_translation != entry.preferred_translation
                        ):
                            conflict_estimate += 1
                            break
        replace_conflicts = False
        if conflict_estimate > 0:
            decision = QMessageBox.question(
                self,
                "Calibration Audit",
                "Conflicts detected. Replace existing conflicting entries?",
                buttons=(
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No
                    | QMessageBox.StandardButton.Cancel
                ),
                defaultButton=QMessageBox.StandardButton.No,
            )
            if decision == QMessageBox.StandardButton.Cancel:
                return
            replace_conflicts = decision == QMessageBox.StandardButton.Yes

        personal_merged, personal_added, personal_skipped, personal_conflicts = _merge_entries_into_scope(
            personal,
            additions_personal,
            replace_conflicts=replace_conflicts,
        )
        project_merged, project_added, project_skipped, project_conflicts = _merge_entries_into_scope(
            project,
            additions_project,
            replace_conflicts=replace_conflicts,
        )
        if project_path is not None:
            try:
                save_project_glossaries(project_path, project_merged)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "Calibration Audit", f"Unable to save project glossary:\n{exc}")
                return

        updates: dict[str, object] = {
            "personal_glossaries_by_lang": serialize_glossaries(personal_merged),
            "glossaries_by_lang": serialize_glossaries(personal_merged),
            "glossary_file_path": str(self._settings.get("glossary_file_path", "") or ""),
            "calibration_sample_pages_default": int(self.sample_pages_spin.value()),
            "calibration_user_seed": self.user_seed_edit.text().strip(),
            "calibration_enable_excerpt_storage": bool(self.include_excerpts_check.isChecked()),
            "calibration_excerpt_max_chars": int(self.excerpt_chars_spin.value()),
        }
        if apply_addendum and addendum_text and self._last_config is not None:
            existing_addendum = self._settings.get("prompt_addendum_by_lang")
            addendum_map = dict(existing_addendum) if isinstance(existing_addendum, dict) else {}
            addendum_map[self._last_config.target_lang.value] = addendum_text
            updates["prompt_addendum_by_lang"] = addendum_map
        self._save_settings_callback(updates)
        if "prompt_addendum_by_lang" in updates:
            self._settings["prompt_addendum_by_lang"] = updates["prompt_addendum_by_lang"]
        self._settings.update(updates)
        QMessageBox.information(
            self,
            "Calibration Audit",
            (
                f"Applied.\n\n"
                f"Personal: added {personal_added}, skipped {personal_skipped}, conflicts {personal_conflicts}\n"
                f"Project: added {project_added}, skipped {project_skipped}, conflicts {project_conflicts}\n"
                f"Addendum updated: {'yes' if 'prompt_addendum_by_lang' in updates else 'no'}"
            ),
        )


def export_current_consistency_glossary_markdown(
    *,
    parent: QWidget | None,
    settings: dict[str, object],
) -> None:
    personal = normalize_glossaries(
        settings.get("personal_glossaries_by_lang", settings.get("glossaries_by_lang")),
        supported_target_langs(),
    )
    if not any(personal.get(lang) for lang in supported_target_langs()):
        QMessageBox.information(parent, "Glossary", "No glossary content to export.")
        return
    enabled = normalize_enabled_tiers_by_target_lang(
        settings.get("enabled_glossary_tiers_by_target_lang"),
        supported_target_langs(),
    )
    markdown = build_consistency_glossary_markdown(
        merge_glossary_scopes(normalize_glossaries({}, supported_target_langs()), personal),
        enabled_tiers_by_lang=enabled,
        generated_at_iso=datetime.now().replace(microsecond=0).isoformat(),
        title="AI Glossary",
    )
    default_target = (app_data_dir() / f"AI_Glossary_{datetime.now().date().isoformat()}.md").resolve()
    selected, _ = QFileDialog.getSaveFileName(
        parent,
        "Export AI Glossary",
        str(default_target),
        "Markdown (*.md);;Text (*.txt);;All Files (*.*)",
    )
    if not selected:
        return
    target = Path(selected).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8")
