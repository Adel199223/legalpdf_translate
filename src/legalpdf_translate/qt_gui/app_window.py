"""PySide6 main window for LegalPDF Translate."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from shutil import which
from typing import Any, Callable

from openai import OpenAI
from PySide6.QtCore import QSize, QStandardPaths, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QDesktopServices,
    QIcon,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QMenu,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from legalpdf_translate import __version__
from legalpdf_translate.build_identity import RuntimeBuildIdentity
from legalpdf_translate.checkpoint import (
    load_run_state,
    parse_effort,
    parse_effort_policy,
    parse_image_mode,
    parse_ocr_engine_policy,
    parse_ocr_mode,
)
from legalpdf_translate.config import OPENAI_MODEL
from legalpdf_translate.gmail_draft import (
    GMAIL_DRAFTS_URL,
    assess_gmail_draft_prereqs,
    build_gmail_batch_reply_request,
    create_gmail_draft_via_gog,
    validate_translated_docx_artifacts_for_gmail_draft,
)
from legalpdf_translate.gmail_batch import (
    DownloadedGmailAttachment,
    GmailAttachmentCandidate,
    GmailBatchConfirmedItem,
    GmailBatchSession,
    GmailMessageLoadResult,
    stage_gmail_batch_translated_docx,
    write_gmail_batch_session_report,
)
from legalpdf_translate.gmail_focus import (
    clear_bridge_runtime_metadata,
    request_window_attention,
    write_bridge_runtime_metadata,
)
from legalpdf_translate.gmail_focus_host import ensure_edge_native_host_registered
from legalpdf_translate.gmail_intake import InboundMailContext, LocalGmailIntakeBridge
from legalpdf_translate.joblog_db import job_log_db_path
from legalpdf_translate.honorarios_docx import build_honorarios_draft
from legalpdf_translate.metadata_autofill import (
    choose_court_email_suggestion,
    extract_pdf_header_metadata_priority_pages,
    metadata_config_from_settings,
)
from legalpdf_translate.ocr_engine import (
    OcrEngineConfig,
    default_ocr_api_env_name,
    default_ocr_api_model,
    normalize_ocr_api_provider,
    test_ocr_provider_connection,
)
from legalpdf_translate.output_paths import (
    build_output_paths,
    require_writable_output_dir,
    require_writable_output_dir_text,
)
from legalpdf_translate.source_document import (
    SOURCE_FILE_DIALOG_FILTER,
    extract_ordered_source_text as extract_ordered_page_text,
    get_source_page_count as get_page_count,
    is_supported_source_file,
)
from legalpdf_translate.qt_gui.guarded_inputs import NoWheelComboBox, NoWheelSpinBox
from legalpdf_translate.queue_runner import QueueRunSummary, parse_queue_manifest
from legalpdf_translate.qt_gui.dialogs import (
    QtArabicDocxReviewDialog,
    GmailBatchReviewPreviewCacheTransfer,
    GmailBatchReviewResult,
    JobLogSeed,
    JobLogSavedResult,
    QtGmailBatchReviewDialog,
    QtHonorariosExportDialog,
    QtJobLogWindow,
    QtReviewQueueDialog,
    QtSaveToJobLogDialog,
    QtSettingsDialog,
    build_seed_from_run,
    normalize_review_queue_entries,
)
from legalpdf_translate.qt_gui.tools_dialogs import QtCalibrationAuditDialog, QtGlossaryBuilderDialog
from legalpdf_translate.qt_gui.styles import apply_primary_glow, apply_soft_shadow
from legalpdf_translate.qt_gui.worker import (
    AnalyzeWorker,
    GmailBatchPrepareWorker,
    GmailMessageLoadWorker,
    QueueRunWorker,
    RebuildDocxWorker,
    TranslationRunWorker,
)
from legalpdf_translate.resources_loader import resource_path
from legalpdf_translate.run_report import build_run_report_markdown
from legalpdf_translate.secrets_store import (
    delete_openai_key,
    delete_ocr_key,
    get_openai_key,
    get_ocr_key,
)
from legalpdf_translate.types import (
    AnalyzeSummary,
    EffortPolicy,
    ImageMode,
    OcrEnginePolicy,
    OcrMode,
    RunConfig,
    RunSummary,
    TargetLang,
)
from legalpdf_translate.user_settings import (
    app_data_dir,
    load_gui_settings,
    load_joblog_settings,
    save_gui_settings,
    settings_path,
)
from legalpdf_translate.workflow import TranslationWorkflow


_FRAME_INSETS = (16, 96, 16, 18)  # (left, top, right, bottom)
_LAYOUT_DESKTOP_EXACT = "desktop_exact"
_LAYOUT_DESKTOP_COMPACT = "desktop_compact"
_LAYOUT_STACKED_COMPACT = "stacked_compact"
_LANG_FLAG_ICON_BY_CODE = {
    "EN": "resources/icons/dashboard/flag_en.svg",
    "FR": "resources/icons/dashboard/flag_fr.svg",
    "AR": "resources/icons/dashboard/flag_ar.svg",
}
_PROCESSING_PAGE_LOG_RE = re.compile(r"Processing PDF page (?P<page>\d+)")
_REQUEST_BUDGET_LOG_RE = re.compile(
    r"page=(?P<page>\d+)\s+request_type=(?P<request_type>text_only|image_backed)\s+"
    r"request_timeout_budget_seconds=(?P<budget>[0-9]+(?:\.[0-9]+)?)"
)
_PAGE_TERMINAL_LOG_RE = re.compile(r"page=(?P<page>\d+)\s+image_used=.*\sstatus=(?P<status>done|failed|skipped)")


def _build_identity_metadata(build_identity: RuntimeBuildIdentity | None) -> dict[str, object] | None:
    if build_identity is None:
        return None
    return {
        "worktree_path": build_identity.worktree_path,
        "branch": build_identity.branch,
        "head_sha": build_identity.head_sha,
        "labels": list(build_identity.labels),
        "is_canonical": build_identity.is_canonical,
        "is_lineage_valid": build_identity.is_lineage_valid,
        "canonical_worktree_path": build_identity.canonical_worktree_path,
        "canonical_branch": build_identity.canonical_branch,
        "approved_base_branch": build_identity.approved_base_branch,
        "approved_base_head_floor": build_identity.approved_base_head_floor,
        "canonical_head_floor": build_identity.canonical_head_floor,
    }


def _refresh_gmail_bridge_runtime_metadata(
    window: object,
    *,
    bridge: LocalGmailIntakeBridge | None,
    build_identity: RuntimeBuildIdentity | None,
) -> None:
    if bridge is None or not bridge.is_running:
        return
    title_getter = getattr(window, "windowTitle", None)
    if not callable(title_getter):
        return
    try:
        window_title = str(title_getter() or "").strip()
    except Exception:  # noqa: BLE001
        return
    write_bridge_runtime_metadata(
        base_dir=app_data_dir(),
        port=bridge.port,
        pid=os.getpid(),
        window_title=window_title,
        build_identity=_build_identity_metadata(build_identity),
        running=True,
    )


def _request_gmail_window_attention(
    window: object,
    *,
    reason: str,
    bridge: LocalGmailIntakeBridge | None,
    build_identity: RuntimeBuildIdentity | None,
    append_log: Callable[[str], None] | None,
) -> None:
    _refresh_gmail_bridge_runtime_metadata(
        window,
        bridge=bridge,
        build_identity=build_identity,
    )
    result = request_window_attention(window)
    if not callable(append_log):
        return
    if result.focused:
        append_log(f"Gmail window attention requested ({reason}): foreground focus succeeded.")
        return
    if result.flashed:
        append_log(f"Gmail window attention requested ({reason}): flashed taskbar because foreground focus was blocked.")
        return
    if result.requested:
        append_log(f"Gmail window attention requested ({reason}): {result.reason}.")
        return
    append_log(f"Gmail window attention skipped ({reason}): {result.reason}.")


def _ensure_gmail_native_focus_host_registration(
    window: object,
    *,
    append_log: Callable[[str], None] | None,
) -> None:
    result = ensure_edge_native_host_registered(base_dir=app_data_dir())
    previous_signature = getattr(window, "_gmail_native_host_registration_signature", None)
    current_signature = (result.ok, result.changed, result.reason, result.manifest_path, result.executable_path)
    setattr(window, "_gmail_native_host_registration_signature", current_signature)
    if not callable(append_log):
        return
    if result.ok and result.changed:
        append_log(
            "Edge Gmail focus helper registered for this user: "
            f"{result.manifest_path} -> {result.executable_path}"
        )
        return
    if result.ok:
        if previous_signature is None or previous_signature[0] is False:
            append_log(f"Edge Gmail focus helper ready: {result.manifest_path}")
        return
    if previous_signature != current_signature:
        append_log(f"Edge Gmail focus helper unavailable: {result.reason}.")


def _is_simple_mode() -> bool:
    """True when advanced tools (Glossary Builder, Calibration Audit) should be hidden."""
    env = os.getenv("LEGALPDF_SIMPLE_MODE")
    if env is not None:
        return env.strip().lower() not in {"0", "false", "no"}
    return getattr(sys, "frozen", False)


def _is_truthy_env(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes"}


def _coerce_int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned == "":
            return None
        try:
            return int(cleaned)
        except ValueError:
            try:
                return int(float(cleaned))
            except ValueError:
                return None
    return None


def _coerce_float_or_none(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", ".")
        if cleaned == "":
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _coerce_bool_or_none(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
    return None


def _load_run_summary_metrics(summary_path: Path) -> dict[str, object]:
    defaults: dict[str, object] = {
        "run_id": "",
        "target_lang": "",
        "total_tokens": None,
        "estimated_api_cost": None,
        "quality_risk_score": None,
    }
    if not summary_path.exists() or not summary_path.is_file():
        return defaults
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults
    if not isinstance(payload, dict):
        return defaults

    totals_payload = payload.get("totals", {})
    totals = totals_payload if isinstance(totals_payload, dict) else {}
    run_id = str(payload.get("run_id", "") or "").strip()
    target_lang = str(payload.get("lang", "") or "").strip()
    total_tokens = _coerce_int_or_none(totals.get("total_tokens"))
    estimated_api_cost = _coerce_float_or_none(totals.get("total_cost_estimate_if_available"))
    quality_risk_score = _coerce_float_or_none(payload.get("quality_risk_score"))
    return {
        "run_id": run_id,
        "target_lang": target_lang,
        "total_tokens": total_tokens,
        "estimated_api_cost": estimated_api_cost,
        "quality_risk_score": quality_risk_score,
    }


def _load_review_queue_entries(summary_path: Path) -> list[dict[str, object]]:
    if not summary_path.exists() or not summary_path.is_file():
        return []
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    return normalize_review_queue_entries(payload.get("review_queue", []))


def _load_run_failure_context(summary_path: Path) -> dict[str, object]:
    defaults: dict[str, object] = {
        "suspected_cause": "",
        "halt_reason": "",
        "page_number": None,
        "error": "",
        "exception_class": "",
        "retry_reason": "",
        "validator_defect_reason": "",
        "ar_violation_kind": "",
        "ar_violation_samples": [],
        "request_type": "",
        "request_timeout_budget_seconds": 0.0,
        "request_elapsed_before_failure_seconds": 0.0,
        "cancel_requested_before_failure": False,
    }
    if not summary_path.exists() or not summary_path.is_file():
        return defaults
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults
    if not isinstance(payload, dict):
        return defaults

    failure_obj = payload.get("failure_context")
    failure = failure_obj if isinstance(failure_obj, dict) else {}
    return {
        "suspected_cause": str(payload.get("suspected_cause", "") or ""),
        "halt_reason": str(payload.get("halt_reason", "") or ""),
        "page_number": _coerce_int_or_none(failure.get("page_number")),
        "error": str(failure.get("error", "") or ""),
        "exception_class": str(failure.get("exception_class", "") or ""),
        "retry_reason": str(failure.get("retry_reason", "") or ""),
        "validator_defect_reason": str(failure.get("validator_defect_reason", "") or ""),
        "ar_violation_kind": str(failure.get("ar_violation_kind", "") or ""),
        "ar_violation_samples": [
            str(item)
            for item in failure.get("ar_violation_samples", [])
            if str(item or "").strip() != ""
        ]
        if isinstance(failure.get("ar_violation_samples"), list)
        else [],
        "request_type": str(failure.get("request_type", "") or ""),
        "request_timeout_budget_seconds": _coerce_float_or_none(
            failure.get("request_timeout_budget_seconds")
        )
        or 0.0,
        "request_elapsed_before_failure_seconds": _coerce_float_or_none(
            failure.get("request_elapsed_before_failure_seconds")
        )
        or 0.0,
        "cancel_requested_before_failure": bool(failure.get("cancel_requested_before_failure", False)),
    }


def _normalized_mode_or_none(value: object) -> str | None:
    text = str(value or "").strip().lower()
    if text in {"off", "auto", "always"}:
        return text
    return None


def _load_advisor_recommendation(report_path: Path) -> dict[str, Any] | None:
    if not report_path.exists() or not report_path.is_file():
        return None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None

    recommended_ocr_mode = _normalized_mode_or_none(payload.get("recommended_ocr_mode"))
    recommended_image_mode = _normalized_mode_or_none(payload.get("recommended_image_mode"))
    if recommended_ocr_mode is None and recommended_image_mode is None:
        return None

    reasons = [
        str(item).strip()
        for item in payload.get("recommendation_reasons", [])
        if isinstance(item, str) and str(item).strip()
    ]
    confidence = _coerce_float_or_none(payload.get("confidence"))
    advisor_track = str(payload.get("advisor_track", "") or "").strip().lower()
    if advisor_track not in {"enfr", "ar"}:
        advisor_track = "enfr"
    return {
        "recommended_ocr_mode": recommended_ocr_mode or "auto",
        "recommended_image_mode": recommended_image_mode or "auto",
        "recommendation_reasons": reasons,
        "confidence": confidence if confidence is not None else 0.5,
        "advisor_track": advisor_track,
    }


@dataclass(slots=True)
class _DashboardSnapshot:
    progress_percent: int = 0
    eta_text: str = "--"
    current_task: str = "Idle"
    pages_done: int = 0
    pages_total: int | None = None
    page_retries: int = 0
    images_done: int = 0
    images_total: int | None = None
    image_retries: int = 0
    errors_count: int = 0
    error_retries: int = 0
    pages_title: str = "Pages"
    images_title: str = "Images"
    errors_title: str = "Errors"


class _FuturisticCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("RootWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        rect = self.rect()
        if rect.width() <= 1 or rect.height() <= 1:
            return

        base_gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        base_gradient.setColorAt(0.0, QColor(1, 9, 24))
        base_gradient.setColorAt(0.45, QColor(3, 20, 46))
        base_gradient.setColorAt(1.0, QColor(2, 10, 28))
        painter.fillRect(rect, base_gradient)

        painter.setPen(Qt.PenStyle.NoPen)
        left_glow = QRadialGradient(rect.width() * 0.18, rect.height() * 0.30, rect.width() * 0.34)
        left_glow.setColorAt(0.0, QColor(38, 190, 232, 42))
        left_glow.setColorAt(0.32, QColor(26, 162, 214, 22))
        left_glow.setColorAt(1.0, QColor(20, 158, 214, 0))
        painter.setBrush(left_glow)
        painter.drawEllipse(
            int(rect.width() * -0.03),
            int(rect.height() * 0.05),
            int(rect.width() * 0.44),
            int(rect.width() * 0.44),
        )

        right_glow = QRadialGradient(rect.width() * 0.84, rect.height() * 0.86, rect.width() * 0.18)
        right_glow.setColorAt(0.0, QColor(18, 196, 255, 14))
        right_glow.setColorAt(1.0, QColor(18, 196, 255, 0))
        painter.setBrush(right_glow)
        painter.drawEllipse(
            int(rect.width() * 0.70),
            int(rect.height() * 0.72),
            int(rect.width() * 0.24),
            int(rect.width() * 0.24),
        )

        top_bar = QLinearGradient(0.0, 0.0, float(rect.width()), 0.0)
        top_bar.setColorAt(0.0, QColor(20, 154, 204, 0))
        top_bar.setColorAt(0.5, QColor(36, 220, 255, 12))
        top_bar.setColorAt(1.0, QColor(20, 154, 204, 0))
        painter.fillRect(0, 56, rect.width(), 4, top_bar)

        def _draw_circuit_block(x_start: int, x_end: int, y_start: int, y_end: int, *, mirrored: bool = False) -> None:
            painter.save()
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(90, 218, 255, 12), 1.0))
            for x in range(x_start, x_end, 52):
                painter.drawLine(x, y_start, x, y_end)
            for y in range(y_start, y_end, 50):
                painter.drawLine(x_start, y, x_end, y)

            painter.setPen(QPen(QColor(97, 228, 255, 24), 1.15))
            anchor_x = x_start + 54 if not mirrored else x_end - 54
            mid_y = y_start + ((y_end - y_start) // 3)
            lower_y = y_start + ((y_end - y_start) * 2 // 3)
            elbow = 52
            if mirrored:
                painter.drawLine(anchor_x, mid_y, anchor_x - elbow, mid_y)
                painter.drawLine(anchor_x - elbow, mid_y, anchor_x - elbow, mid_y + 28)
                painter.drawLine(anchor_x - elbow, lower_y, anchor_x - (elbow * 2), lower_y)
                painter.drawLine(anchor_x - (elbow * 2), lower_y, anchor_x - (elbow * 2), lower_y + 34)
            else:
                painter.drawLine(anchor_x, mid_y, anchor_x + elbow, mid_y)
                painter.drawLine(anchor_x + elbow, mid_y, anchor_x + elbow, mid_y + 28)
                painter.drawLine(anchor_x, lower_y, anchor_x + (elbow * 2), lower_y)
                painter.drawLine(anchor_x + (elbow * 2), lower_y, anchor_x + (elbow * 2), lower_y + 34)
            painter.restore()

        window = self.window()
        sidebar = getattr(window, "sidebar_frame", None)
        sidebar_line_x = 108
        if sidebar is not None and sidebar.width() > 0:
            sidebar_line_x = sidebar.width()

        gutter_top = 136
        gutter_bottom = max(gutter_top + 160, rect.height() - 96)
        left_block_start = max(56, sidebar_line_x + 18)
        left_block_end = max(left_block_start + 48, int(rect.width() * 0.21))
        _draw_circuit_block(left_block_start, left_block_end, gutter_top, gutter_bottom, mirrored=False)
        _draw_circuit_block(
            max(int(rect.width() * 0.84), int(rect.width() - 230)),
            rect.width() - 58,
            gutter_top + 34,
            gutter_bottom - 82,
            mirrored=True,
        )

        painter.setPen(QPen(QColor(89, 232, 255, 38), 1.0))
        painter.drawLine(sidebar_line_x, 68, sidebar_line_x, rect.height() - 36)

        painter.setPen(QPen(QColor(110, 235, 255, 30), 1.4))
        painter.drawLine(sidebar_line_x + 76, 156, rect.width() - 138, 156)
        painter.end()
        super().paintEvent(event)


class QtMainWindow(QMainWindow):
    request_cancel = Signal()
    gmail_intake_received = Signal(object)

    def __init__(self, *, build_identity: RuntimeBuildIdentity | None = None) -> None:
        super().__init__()
        self._build_identity = build_identity
        if build_identity is None:
            self.setWindowTitle("LegalPDF Translate")
        else:
            self.setWindowTitle(build_identity.window_title("LegalPDF Translate"))
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.setMinimumSize(720, 540)
        self.resize(1680, 960)
        self._initial_resize_done = False
        self._simple_mode = _is_simple_mode()

        self._defaults = load_gui_settings()
        self._worker_thread: QThread | None = None
        self._worker: object | None = None
        self._after_worker_cleanup: Callable[[], None] | None = None
        self._last_workflow: TranslationWorkflow | None = None
        self._last_summary: RunSummary | None = None
        self._last_output_docx: Path | None = None
        self._last_run_config: RunConfig | None = None
        self._last_run_dir: Path | None = None
        self._last_joblog_seed: JobLogSeed | None = None
        self._last_gmail_intake_context: InboundMailContext | None = None
        self._last_gmail_message_load_result: GmailMessageLoadResult | None = None
        self._last_review_queue: list[dict[str, object]] = []
        self._last_run_report_path: Path | None = None
        self._last_queue_summary_path: Path | None = None
        self._queue_status_rows: list[dict[str, Any]] = []
        self._advisor_recommendation: dict[str, Any] | None = None
        self._advisor_recommendation_applied: bool | None = None
        self._advisor_override_ocr_mode: str | None = None
        self._advisor_override_image_mode: str | None = None
        self._joblog_window: QtJobLogWindow | None = None
        self._review_queue_dialog: QtReviewQueueDialog | None = None
        self._gmail_batch_review_dialog: QtGmailBatchReviewDialog | None = None
        self._settings_dialog: QtSettingsDialog | None = None
        self._glossary_builder_dialog: QtGlossaryBuilderDialog | None = None
        self._calibration_dialog: QtCalibrationAuditDialog | None = None
        self._menu_actions: dict[str, QAction] = {}
        self._overflow_menu_actions: dict[str, QAction] = {}
        self._joblog_db_path = job_log_db_path()
        self._session_started_at = datetime.now()
        self._metadata_logs_dir = app_data_dir() / "logs"
        self._metadata_logs_dir.mkdir(parents=True, exist_ok=True)
        self._metadata_log_file = self._metadata_logs_dir / (
            f"session_{self._session_started_at.strftime('%Y%m%d_%H%M%S')}.log"
        )
        self._busy = False
        self._running = False
        self._cancel_pending = False
        self._can_export_partial = False
        self._last_page_path: str | None = None
        self._progress_done_pages = 0
        self._progress_total_pages = 0
        self._image_pages_seen: set[int] = set()
        self._retry_pages_seen: set[int] = set()
        self._queue_total_jobs = 0
        self._queue_status_by_job_id: dict[str, dict[str, Any]] = {}
        self._run_started_at: float | None = None
        self._active_request_page: int | None = None
        self._active_request_type: str | None = None
        self._active_request_budget_seconds: float | None = None
        self._active_request_started_at: float | None = None
        self._cancel_wait_started_at: float | None = None
        self._dashboard_snapshot = _DashboardSnapshot()
        self._dashboard_error_count = 0
        self._dashboard_error_retry_count = 0
        self._dashboard_eta_text = "--"
        self._ocr_dependency_warning_seen: set[tuple[str, int, str, str]] = set()
        self._transient_safe_profile_active = False
        self._transient_safe_profile_backup: dict[str, object] | None = None
        self._gmail_batch_session: GmailBatchSession | None = None
        self._gmail_batch_preview_cache_transfer: GmailBatchReviewPreviewCacheTransfer | None = None
        self._gmail_batch_in_progress = False
        self._gmail_batch_current_index: int | None = None
        self._gmail_intake_bridge: LocalGmailIntakeBridge | None = None
        self._layout_mode = _LAYOUT_DESKTOP_EXACT
        self._click_debug_enabled = _is_truthy_env(os.getenv("LEGALPDF_QT_CLICK_DEBUG"))
        self._settings_save_timer = QTimer(self)
        self._settings_save_timer.setSingleShot(True)
        self._settings_save_timer.setInterval(250)
        self._settings_save_timer.timeout.connect(self._save_settings)
        self._cancel_wait_timer = QTimer(self)
        self._cancel_wait_timer.setInterval(500)
        self._cancel_wait_timer.timeout.connect(self._refresh_cancel_wait_status)
        self.gmail_intake_received.connect(self._on_gmail_intake_received)

        self._build_ui()
        self._install_menu()
        self._restore_settings()
        self._set_adv_visible(False)
        self._set_details_visible(False)
        self._refresh_page_count()
        self._sync_gmail_intake_bridge()
        self._update_controls()
        self._refresh_canvas()

    def _build_ui(self) -> None:
        root = _FuturisticCanvas(self)
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.sidebar_frame = QFrame(objectName="SidebarPanel")
        self.sidebar_frame.setFixedWidth(136)
        sidebar_layout = QVBoxLayout(self.sidebar_frame)
        self.sidebar_layout = sidebar_layout
        sidebar_layout.setContentsMargins(10, 22, 10, 26)
        sidebar_layout.setSpacing(14)

        self.sidebar_logo_label = QLabel(objectName="SidebarLogoLabel")
        self.sidebar_logo_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.sidebar_logo_label.setPixmap(self._icon("resources/icons/dashboard/logo_l.svg").pixmap(QSize(72, 72)))
        sidebar_layout.addWidget(self.sidebar_logo_label, 0, Qt.AlignmentFlag.AlignHCenter)
        sidebar_layout.addSpacing(10)

        self.dashboard_nav_btn = self._make_sidebar_button(
            "Dashboard",
            "resources/icons/dashboard/home.svg",
            self._focus_dashboard,
            active=True,
        )
        self.new_job_nav_btn = self._make_sidebar_button(
            "New Job",
            "resources/icons/dashboard/new_job.svg",
            self._new_run,
        )
        self.recent_jobs_nav_btn = self._make_sidebar_button(
            "Recent Jobs",
            "resources/icons/dashboard/recent.svg",
            self._open_joblog_window,
        )
        self.settings_nav_btn = self._make_sidebar_button(
            "Settings",
            "resources/icons/dashboard/settings.svg",
            self._open_settings_dialog,
        )
        self.profile_nav_btn = self._make_sidebar_button(
            "Profile",
            "resources/icons/dashboard/profile.svg",
            self._show_profile_coming_soon,
            coming_soon=True,
        )
        self._sidebar_nav_buttons = [
            self.dashboard_nav_btn,
            self.new_job_nav_btn,
            self.recent_jobs_nav_btn,
            self.settings_nav_btn,
            self.profile_nav_btn,
        ]
        sidebar_layout.addWidget(self.dashboard_nav_btn)
        sidebar_layout.addWidget(self.new_job_nav_btn)
        sidebar_layout.addWidget(self.recent_jobs_nav_btn)
        sidebar_layout.addWidget(self.settings_nav_btn)
        sidebar_layout.addStretch(1)
        sidebar_layout.addWidget(self.profile_nav_btn)
        outer.addWidget(self.sidebar_frame)

        self._scroll_area = QScrollArea()
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.viewport().setAutoFillBackground(False)
        self._scroll_area.setStyleSheet("QScrollArea{background:transparent;}")
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background:transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout = scroll_layout
        scroll_layout.setContentsMargins(18, 16, 18, 12)
        scroll_layout.setSpacing(0)
        scroll_layout.addStretch(1)

        self.content_card = QWidget()
        self.content_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.content_card.setStyleSheet("background:transparent;")
        self.content_card.setFixedWidth(1500)
        self.content_card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        content_row = QHBoxLayout()
        self.content_row_layout = content_row
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(0)
        content_row.addStretch(1)
        content_row.addWidget(self.content_card, 0)
        content_row.addStretch(1)
        scroll_layout.addLayout(content_row)
        scroll_layout.addStretch(1)
        self._scroll_area.setWidget(scroll_content)
        outer.addWidget(self._scroll_area, 1)

        card_shell = QVBoxLayout(self.content_card)
        self.card_shell_layout = card_shell
        card_shell.setContentsMargins(0, 0, 0, 0)
        card_shell.setSpacing(16)

        hero_row = QGridLayout()
        hero_row.setContentsMargins(0, 0, 0, 6)
        hero_row.setHorizontalSpacing(0)
        hero_row.setVerticalSpacing(0)
        hero_row.setColumnStretch(0, 1)
        hero_row.setColumnStretch(2, 1)
        self.title_label = QLabel("LegalPDF Translate", objectName="HeroTitleLabel")
        self.header_status_label = QLabel("Idle", objectName="HeroStatusLabel")
        self.header_status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.header_status_label.setMinimumWidth(120)
        apply_primary_glow(self.title_label, blur_radius=34)
        hero_row.addWidget(self.title_label, 0, 1, Qt.AlignmentFlag.AlignCenter)
        hero_row.addWidget(self.header_status_label, 0, 2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        card_shell.addLayout(hero_row)

        self.dashboard_frame = QFrame(objectName="DashboardFrame")
        apply_soft_shadow(self.dashboard_frame, blur_radius=56, offset_y=14)
        dashboard_layout = QVBoxLayout(self.dashboard_frame)
        self.dashboard_layout = dashboard_layout
        dashboard_layout.setContentsMargins(34, 24, 34, 20)
        dashboard_layout.setSpacing(20)

        self.main_card = QFrame(objectName="HiddenUtilityPanel")
        main_layout = QVBoxLayout(self.main_card)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(20)

        body_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        body_row.setContentsMargins(0, 0, 0, 0)
        body_row.setSpacing(26)
        self.body_layout = body_row

        self.setup_panel = QFrame(objectName="ShellPanel")
        self.setup_panel.setMinimumWidth(0)
        self.setup_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        setup_layout = QVBoxLayout(self.setup_panel)
        self.setup_layout = setup_layout
        setup_layout.setContentsMargins(28, 22, 28, 22)
        setup_layout.setSpacing(18)
        setup_layout.addWidget(QLabel("Job Setup", objectName="PanelHeading"))

        setup_grid = QGridLayout()
        self.setup_grid = setup_grid
        setup_grid.setHorizontalSpacing(20)
        setup_grid.setVerticalSpacing(18)
        setup_grid.setColumnMinimumWidth(0, 176)
        setup_grid.setColumnStretch(1, 1)

        self.pdf_edit = QLineEdit(placeholderText="Select PDF or image file...")
        self.pdf_edit.setProperty("embeddedField", True)
        self.pdf_edit.setMinimumWidth(220)
        self.pdf_btn = QToolButton(objectName="FieldBrowseButton")
        self.pdf_btn.setIcon(self._icon("resources/icons/dashboard/folder_search.svg"))
        self.pdf_btn.setIconSize(QSize(18, 18))
        self.pages_label = QLabel("Pages: -", objectName="FieldSupportLabel")
        self.pages_label.setMinimumWidth(74)
        self.pages_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        pdf_support_cluster = QWidget()
        pdf_support_layout = QHBoxLayout(pdf_support_cluster)
        pdf_support_layout.setContentsMargins(0, 0, 0, 0)
        pdf_support_layout.setSpacing(8)
        self.pdf_pages_icon_label = self._make_icon_label("resources/icons/dashboard/pages.svg", 18)
        pdf_support_layout.addWidget(self.pdf_pages_icon_label, 0)
        pdf_support_layout.addWidget(self.pages_label, 0)
        pdf_divider = QFrame(objectName="InlineDivider")
        pdf_divider.setFrameShape(QFrame.Shape.VLine)
        pdf_divider.setFixedHeight(28)
        pdf_btn_divider = QFrame(objectName="InlineDivider")
        pdf_btn_divider.setFrameShape(QFrame.Shape.VLine)
        pdf_btn_divider.setFixedHeight(28)
        pdf_field = QFrame(objectName="FieldChrome")
        pdf_field_layout = QHBoxLayout(pdf_field)
        pdf_field_layout.setContentsMargins(14, 8, 12, 8)
        pdf_field_layout.setSpacing(12)
        pdf_field_layout.addWidget(self._make_icon_label("resources/icons/dashboard/pdf_search.svg", 20))
        pdf_field_layout.addWidget(self.pdf_edit, 1)
        pdf_field_layout.addWidget(pdf_divider, 0)
        pdf_field_layout.addWidget(pdf_support_cluster, 0)
        pdf_field_layout.addWidget(pdf_btn_divider, 0)
        pdf_field_layout.addWidget(self.pdf_btn, 0)
        setup_grid.addWidget(QLabel("Source File", objectName="FieldLabel"), 0, 0)
        setup_grid.addWidget(pdf_field, 0, 1)

        self.lang_combo = NoWheelComboBox()
        self.lang_combo.addItems(["EN", "FR", "AR"])
        self.lang_combo.setProperty("embeddedField", True)
        self.lang_combo.setProperty("langField", True)
        self.lang_combo.setMinimumWidth(64)
        self.lang_combo.setMaximumWidth(72)
        self.flag_label = QLabel(objectName="FlagLabel")
        self.flag_label.setFixedSize(30, 20)
        self.flag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.flag_label.setPixmap(self._icon("resources/icons/dashboard/flag_en.svg").pixmap(QSize(28, 18)))
        lang_divider = QFrame(objectName="InlineDivider")
        lang_divider.setFrameShape(QFrame.Shape.VLine)
        lang_divider.setFixedHeight(28)
        self.lang_caret_btn = QToolButton(objectName="LangCaretButton")
        self.lang_caret_btn.setIcon(self._icon("resources/icons/dashboard/caret_down.svg"))
        self.lang_caret_btn.setIconSize(QSize(12, 12))
        self.lang_caret_btn.setAutoRaise(False)
        lang_field = QFrame(objectName="FieldChrome")
        lang_field_layout = QHBoxLayout(lang_field)
        lang_field_layout.setContentsMargins(14, 8, 12, 8)
        lang_field_layout.setSpacing(12)
        lang_field_layout.addWidget(self._make_icon_label("resources/icons/dashboard/globe.svg", 20))
        lang_field_layout.addWidget(self.lang_combo, 0)
        lang_field_layout.addWidget(self.flag_label, 0)
        lang_field_layout.addStretch(1)
        lang_field_layout.addWidget(lang_divider, 0)
        lang_field_layout.addWidget(self.lang_caret_btn, 0)
        setup_grid.addWidget(QLabel("Target Language", objectName="FieldLabel"), 1, 0)
        setup_grid.addWidget(lang_field, 1, 1)

        self.outdir_edit = QLineEdit(placeholderText="Select output folder...")
        self.outdir_edit.setProperty("embeddedField", True)
        self.outdir_edit.setMinimumWidth(240)
        self.outdir_btn = QToolButton(objectName="FieldBrowseButton")
        self.outdir_btn.setIcon(self._icon("resources/icons/dashboard/folder_search.svg"))
        self.outdir_btn.setIconSize(QSize(18, 18))
        out_divider = QFrame(objectName="InlineDivider")
        out_divider.setFrameShape(QFrame.Shape.VLine)
        out_divider.setFixedHeight(28)
        out_field = QFrame(objectName="FieldChrome")
        out_field_layout = QHBoxLayout(out_field)
        out_field_layout.setContentsMargins(14, 8, 12, 8)
        out_field_layout.setSpacing(12)
        out_field_layout.addWidget(self._make_icon_label("resources/icons/dashboard/folder_search.svg", 20))
        out_field_layout.addWidget(self.outdir_edit, 1)
        out_field_layout.addWidget(out_divider, 0)
        out_field_layout.addWidget(self.outdir_btn, 0)
        setup_grid.addWidget(QLabel("Output Folder", objectName="FieldLabel"), 2, 0)
        setup_grid.addWidget(out_field, 2, 1)
        setup_layout.addLayout(setup_grid)

        self.show_adv = QToolButton(objectName="SectionToggleButton")
        self.show_adv.setText("Advanced Settings")
        self.show_adv.setCheckable(True)
        self.show_adv.setChecked(False)
        self.show_adv.setArrowType(Qt.ArrowType.RightArrow)
        self.show_adv.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.show_adv.setMinimumHeight(64)
        setup_layout.addWidget(self.show_adv)

        self.adv_frame = QFrame(objectName="ShellPanel")
        adv = QFormLayout(self.adv_frame)
        adv.setContentsMargins(14, 14, 14, 14)
        adv.setHorizontalSpacing(12)
        adv.setVerticalSpacing(10)
        self.effort_policy_combo = NoWheelComboBox(); self.effort_policy_combo.addItems(["adaptive", "fixed_high", "fixed_xhigh"])
        self.effort_combo = NoWheelComboBox(); self.effort_combo.addItems(["high", "xhigh"])
        self.images_combo = NoWheelComboBox(); self.images_combo.addItems(["off", "auto", "always"])
        self.ocr_mode_combo = NoWheelComboBox(); self.ocr_mode_combo.addItems(["off", "auto", "always"])
        self.ocr_engine_combo = NoWheelComboBox(); self.ocr_engine_combo.addItems(["local", "local_then_api", "api"])
        self.start_edit = QLineEdit("1")
        self.end_edit = QLineEdit("")
        self.max_edit = QLineEdit("")
        self.workers_spin = NoWheelSpinBox(); self.workers_spin.setRange(1, 6)
        self.resume_check = QCheckBox("Resume")
        self.breaks_check = QCheckBox("Insert page breaks")
        self.keep_check = QCheckBox("Keep intermediates")
        self.context_file_edit = QLineEdit(placeholderText="Optional context file...")
        self.context_btn = QToolButton(objectName="FieldBrowseButton")
        self.context_btn.setIcon(self._icon("resources/icons/dashboard/folder_search.svg"))
        self.context_btn.setIconSize(QSize(18, 18))
        cf = QWidget(); cfl = QHBoxLayout(cf); cfl.setContentsMargins(0, 0, 0, 0); cfl.setSpacing(8); cfl.addWidget(self.context_file_edit); cfl.addWidget(self.context_btn)
        self.context_text = QPlainTextEdit(); self.context_text.setFixedHeight(90); self.context_text.setPlaceholderText("Optional context text...")
        self.analyze_btn = QPushButton("Analyze")
        self.queue_manifest_edit = QLineEdit(placeholderText="Optional queue manifest (.json/.jsonl)...")
        self.queue_manifest_btn = QToolButton(objectName="FieldBrowseButton")
        self.queue_manifest_btn.setIcon(self._icon("resources/icons/dashboard/folder_search.svg"))
        self.queue_manifest_btn.setIconSize(QSize(18, 18))
        queue_manifest_row = QWidget()
        queue_manifest_layout = QHBoxLayout(queue_manifest_row)
        queue_manifest_layout.setContentsMargins(0, 0, 0, 0)
        queue_manifest_layout.setSpacing(8)
        queue_manifest_layout.addWidget(self.queue_manifest_edit)
        queue_manifest_layout.addWidget(self.queue_manifest_btn)
        self.queue_rerun_failed_only_check = QCheckBox("Rerun failed only")
        self.run_queue_btn = QPushButton("Run Queue")
        self.queue_status_label = QLabel("Queue: idle", objectName="MutedLabel")
        toggles = QWidget(); tl = QHBoxLayout(toggles); tl.setContentsMargins(0, 0, 0, 0); tl.setSpacing(12); tl.addWidget(self.resume_check); tl.addWidget(self.breaks_check); tl.addWidget(self.keep_check); tl.addStretch(1)
        adv.addRow("Effort policy", self.effort_policy_combo)
        adv.addRow("Reasoning effort", self.effort_combo)
        adv.addRow("Image mode", self.images_combo)
        adv.addRow("OCR mode", self.ocr_mode_combo)
        adv.addRow("OCR engine", self.ocr_engine_combo)
        adv.addRow("Start page", self.start_edit)
        adv.addRow("End page", self.end_edit)
        adv.addRow("Max pages", self.max_edit)
        adv.addRow("Parallel workers", self.workers_spin)
        adv.addRow("Run options", toggles)
        adv.addRow("Context file", cf)
        adv.addRow("Context text", self.context_text)
        adv.addRow("", self.analyze_btn)
        adv.addRow("Queue manifest", queue_manifest_row)
        adv.addRow("", self.queue_rerun_failed_only_check)
        adv.addRow("", self.run_queue_btn)
        adv.addRow("Queue status", self.queue_status_label)
        setup_layout.addWidget(self.adv_frame)

        self.advisor_frame = QFrame(objectName="ShellPanel")
        advisor_layout = QHBoxLayout(self.advisor_frame)
        advisor_layout.setContentsMargins(12, 10, 12, 10)
        advisor_layout.setSpacing(10)
        advisor_title = QLabel("Advisor", objectName="FieldSupportLabel")
        self.advisor_label = QLabel("", objectName="FieldValueLabel")
        self.advisor_apply_btn = QPushButton("Apply")
        self.advisor_ignore_btn = QPushButton("Ignore")
        advisor_layout.addWidget(advisor_title)
        advisor_layout.addWidget(self.advisor_label, 1)
        advisor_layout.addWidget(self.advisor_apply_btn)
        advisor_layout.addWidget(self.advisor_ignore_btn)
        self.advisor_frame.setVisible(False)
        setup_layout.addWidget(self.advisor_frame)
        setup_layout.addStretch(1)
        body_row.addWidget(self.setup_panel, 7)

        self.progress_panel = QFrame(objectName="ShellPanel")
        self.progress_panel.setMinimumWidth(0)
        self.progress_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        progress_layout = QVBoxLayout(self.progress_panel)
        self.progress_layout = progress_layout
        progress_layout.setContentsMargins(28, 22, 28, 22)
        progress_layout.setSpacing(16)

        self.progress_panel_title = QLabel("Conversion Output", objectName="PanelHeading")
        progress_layout.addWidget(self.progress_panel_title)

        summary_row = QHBoxLayout()
        summary_row.setContentsMargins(0, 0, 0, 0)
        summary_row.setSpacing(18)
        self.progress_summary_label = QLabel("0%", objectName="ProgressSummaryLabel")
        self.progress_eta_label = QLabel("Est. remaining: --", objectName="ProgressSummaryLabel")
        summary_row.addWidget(self.progress_summary_label, 0)
        summary_row.addStretch(1)
        summary_row.addWidget(self.progress_eta_label, 0)
        progress_layout.addLayout(summary_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        progress_layout.addWidget(self.progress)

        task_row = QHBoxLayout()
        task_row.setContentsMargins(0, 0, 0, 0)
        task_row.setSpacing(8)
        task_row.addWidget(QLabel("Current Task:", objectName="CurrentTaskLabel"), 0)
        self.status_label = QLabel("Idle", objectName="CurrentTaskLabel")
        self.status_label.setWordWrap(True)
        task_row.addWidget(self.status_label, 1)
        progress_layout.addLayout(task_row)

        metric_frame = QFrame(objectName="MetricGridFrame")
        metric_grid = QGridLayout(metric_frame)
        self.metric_grid_layout = metric_grid
        metric_grid.setContentsMargins(14, 14, 14, 14)
        metric_grid.setHorizontalSpacing(14)
        metric_grid.setVerticalSpacing(12)

        def _metric_left(icon_rel: str, title: str, attr_name: str) -> QWidget:
            widget = QFrame(objectName="MetricCell")
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(10)
            layout.addWidget(self._make_icon_label(icon_rel, 18))
            label = QLabel(title, objectName="MetricTitle")
            setattr(self, attr_name, label)
            layout.addWidget(label, 1)
            return widget

        def _metric_value(label: str, object_name: str) -> QLabel:
            value = QLabel(label, objectName=object_name)
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            return value

        self.metric_retry_header_label = QLabel("Retries", objectName="MetricTitle")
        self.metric_retry_header_label.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop)

        self.metric_pages_value_label = _metric_value("0 / --", "MetricValue")
        self.metric_pages_retry_value_label = QLabel("0", objectName="MetricRetryValue")
        self.metric_images_value_label = _metric_value("0 / --", "MetricValue")
        self.metric_images_retry_value_label = QLabel("0", objectName="MetricRetryValue")
        self.metric_errors_value_label = _metric_value("0", "MetricValue")
        self.metric_errors_retry_value_label = QLabel("0", objectName="MetricRetryValue")

        metric_grid.addWidget(_metric_left("resources/icons/dashboard/pages.svg", "Pages", "metric_pages_title_label"), 0, 0)
        metric_grid.addWidget(self.metric_pages_value_label, 0, 1)
        metric_grid.addWidget(self.metric_retry_header_label, 0, 2, Qt.AlignmentFlag.AlignCenter)
        metric_grid.addWidget(_metric_left("resources/icons/dashboard/images.svg", "Images", "metric_images_title_label"), 1, 0)
        metric_grid.addWidget(self.metric_images_value_label, 1, 1)
        metric_grid.addWidget(_metric_left("resources/icons/dashboard/warning.svg", "Errors", "metric_errors_title_label"), 2, 0)
        metric_grid.addWidget(self.metric_errors_value_label, 2, 1)
        metric_grid.setColumnStretch(0, 3)
        metric_grid.setColumnStretch(1, 2)
        metric_grid.setColumnStretch(2, 1)
        metric_grid.setColumnMinimumWidth(2, 88)
        progress_layout.addWidget(metric_frame)

        self.output_format_label = QLabel("Output Format: DOCX", objectName="OutputFormatLabel")
        progress_layout.addWidget(self.output_format_label)
        progress_layout.addStretch(1)
        body_row.addWidget(self.progress_panel, 6)
        main_layout.addLayout(body_row)

        self.footer_card = QFrame(objectName="ActionRail")
        footer = QGridLayout(self.footer_card)
        footer.setContentsMargins(22, 18, 22, 18)
        footer.setHorizontalSpacing(18)
        footer.setVerticalSpacing(12)
        self.footer_layout = footer

        self.translate_btn = QPushButton("Start Translate", objectName="PrimaryButton")
        self.cancel_btn = QPushButton("Cancel", objectName="DangerButton")
        self.more_btn = QToolButton(objectName="OverflowMenuButton")
        self.more_btn.setText("...")
        for widget in (self.translate_btn, self.cancel_btn, self.more_btn):
            widget.setMinimumHeight(72)
            widget.setMaximumHeight(72)
        self.cancel_btn.setFixedWidth(186)
        self.more_btn.setFixedWidth(92)
        self.more_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.more_menu = QMenu(self.more_btn)
        self.more_btn.setMenu(self.more_menu)
        self._configure_footer_layout(compact=False)
        apply_primary_glow(self.translate_btn, blur_radius=24)
        apply_primary_glow(self.footer_card, blur_radius=22)
        main_layout.addWidget(self.footer_card)
        dashboard_layout.addWidget(self.main_card)
        card_shell.addWidget(self.dashboard_frame)

        footer_meta_row = QHBoxLayout()
        footer_meta_row.setContentsMargins(8, 4, 0, 0)
        footer_meta_row.setSpacing(0)
        self.footer_meta_label = QLabel("Project v3.0 | LegalPDF", objectName="FooterMetaLabel")
        footer_meta_row.addWidget(self.footer_meta_label, 0, Qt.AlignmentFlag.AlignLeft)
        footer_meta_row.addStretch(1)
        card_shell.addLayout(footer_meta_row)

        self.details_card = QFrame(objectName="ShellPanel")
        details_layout = QVBoxLayout(self.details_card)
        details_layout.setContentsMargins(12, 10, 12, 10)
        self.details_btn = QToolButton(objectName="DisclosureButton")
        self.details_btn.setCheckable(True)
        self.details_btn.setChecked(False)
        self.details_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.details_btn.setArrowType(Qt.ArrowType.RightArrow)
        self.details_btn.setText("Show details")
        self.log_text = QPlainTextEdit(readOnly=True)
        self.log_text.setVisible(False)
        self.log_text.setMaximumBlockCount(5000)
        details_layout.addWidget(self.details_btn)
        details_layout.addWidget(self.log_text)
        self.details_card.setVisible(False)
        card_shell.addWidget(self.details_card)

        self.utility_panel = QFrame(objectName="HiddenUtilityPanel")
        utility_layout = QVBoxLayout(self.utility_panel)
        utility_layout.setContentsMargins(0, 0, 0, 0)
        utility_layout.setSpacing(4)
        final_row = QHBoxLayout()
        final_row.setContentsMargins(0, 0, 0, 0)
        final_row.addWidget(QLabel("Final DOCX"))
        self.final_docx_edit = QLineEdit(readOnly=True)
        final_row.addWidget(self.final_docx_edit, 1)
        utility_layout.addLayout(final_row)
        self.page_label = QLabel("Page: -/-", objectName="MutedLabel")
        self.live_counters_label = QLabel("Done 0/0 | Images 0 | Retries 0", objectName="MutedLabel")
        utility_layout.addWidget(self.page_label)
        utility_layout.addWidget(self.live_counters_label)
        self.new_btn = QPushButton("New Run")
        self.partial_btn = QPushButton("Export partial DOCX")
        self.rebuild_btn = QPushButton("Rebuild DOCX")
        self.open_btn = QPushButton("Open output folder")
        self.report_btn = QPushButton("Export Run Report")
        self.review_queue_btn = QPushButton("Review Queue")
        self.save_joblog_btn = QPushButton("Save to Job Log")
        self.open_joblog_btn = QPushButton("Job Log")
        hidden_buttons = QHBoxLayout()
        hidden_buttons.setContentsMargins(0, 0, 0, 0)
        hidden_buttons.setSpacing(6)
        for btn in (
            self.new_btn,
            self.partial_btn,
            self.rebuild_btn,
            self.open_btn,
            self.report_btn,
            self.review_queue_btn,
            self.save_joblog_btn,
            self.open_joblog_btn,
        ):
            btn.setVisible(False)
            hidden_buttons.addWidget(btn)
        utility_layout.addLayout(hidden_buttons)
        self.utility_panel.setVisible(False)
        card_shell.addWidget(self.utility_panel)

        self._install_overflow_menu()

        self.pdf_btn.clicked.connect(self._pick_pdf)
        self.outdir_btn.clicked.connect(self._pick_outdir)
        self.context_btn.clicked.connect(self._pick_context)
        self.show_adv.toggled.connect(self._set_adv_visible)
        self.details_btn.toggled.connect(self._set_details_visible)
        self.translate_btn.clicked.connect(self._start)
        self.analyze_btn.clicked.connect(self._start_analyze)
        self.run_queue_btn.clicked.connect(self._start_queue)
        self.queue_manifest_btn.clicked.connect(self._pick_queue_manifest)
        self.lang_caret_btn.clicked.connect(self.lang_combo.showPopup)
        self.advisor_apply_btn.clicked.connect(self._apply_advisor_recommendation)
        self.advisor_ignore_btn.clicked.connect(self._ignore_advisor_recommendation)
        self.cancel_btn.clicked.connect(self._cancel)
        self.new_btn.clicked.connect(self._new_run)
        self.partial_btn.clicked.connect(self._export_partial)
        self.rebuild_btn.clicked.connect(self._start_rebuild_docx)
        self.open_btn.clicked.connect(self._open_output_folder)
        self.report_btn.clicked.connect(self._open_run_report)
        self.review_queue_btn.clicked.connect(self._open_review_queue_dialog)
        self.save_joblog_btn.clicked.connect(self._open_save_to_joblog_dialog)
        self.open_joblog_btn.clicked.connect(self._open_joblog_window)

        self.request_cancel.connect(self._dispatch_cancel)
        self.pdf_edit.textChanged.connect(self._on_form_changed)
        self.lang_combo.currentTextChanged.connect(self._on_form_changed)
        self.outdir_edit.textChanged.connect(self._on_form_changed)
        self.effort_combo.currentTextChanged.connect(self._on_form_changed)
        self.effort_policy_combo.currentTextChanged.connect(self._on_form_changed)
        self.images_combo.currentTextChanged.connect(self._on_form_changed)
        self.ocr_mode_combo.currentTextChanged.connect(self._on_form_changed)
        self.ocr_engine_combo.currentTextChanged.connect(self._on_form_changed)
        self.start_edit.textChanged.connect(self._on_form_changed)
        self.end_edit.textChanged.connect(self._on_form_changed)
        self.max_edit.textChanged.connect(self._on_form_changed)
        self.workers_spin.valueChanged.connect(self._on_form_changed)
        self.resume_check.toggled.connect(self._on_form_changed)
        self.breaks_check.toggled.connect(self._on_form_changed)
        self.keep_check.toggled.connect(self._on_form_changed)
        self.queue_manifest_edit.textChanged.connect(self._on_form_changed)
        self.queue_rerun_failed_only_check.toggled.connect(self._on_form_changed)

        self._set_adv_visible(False)
        self._set_details_visible(False)
        self._refresh_dashboard_counters()
        self._apply_responsive_layout()
        self._refresh_canvas()

    def _icon(self, rel_path: str) -> QIcon:
        return QIcon(str(resource_path(rel_path)))

    def _make_icon_label(self, rel_path: str, size: int) -> QLabel:
        label = QLabel()
        label.setPixmap(self._icon(rel_path).pixmap(QSize(size, size)))
        label.setFixedSize(size + 2, size + 2)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def _make_sidebar_button(
        self,
        text: str,
        icon_rel_path: str,
        callback,
        *,
        active: bool = False,
        coming_soon: bool = False,
    ) -> QToolButton:
        button = QToolButton(objectName="SidebarNavButton")
        button.setText(text)
        button.setIcon(self._icon(icon_rel_path))
        button.setIconSize(QSize(26, 26))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setAutoRaise(False)
        button.setCheckable(False)
        button.setFixedWidth(112)
        button.setMinimumHeight(98)
        button.setProperty("navRole", "active" if active else "idle")
        if coming_soon:
            button.setProperty("comingSoon", "true")
        button.clicked.connect(callback)
        return button

    def _configure_footer_layout(self, *, compact: bool) -> None:
        footer = self.footer_layout
        while footer.count():
            footer.takeAt(0)
        footer.setHorizontalSpacing(12 if compact else 18)
        footer.setVerticalSpacing(12)
        for index in range(3):
            footer.setColumnStretch(index, 0)
            footer.setColumnMinimumWidth(index, 0)
        for index in range(2):
            footer.setRowStretch(index, 0)
            footer.setRowMinimumHeight(index, 0)

        if compact:
            footer.setColumnStretch(0, 1)
            footer.addWidget(self.translate_btn, 0, 0, 1, 3)
            footer.addWidget(self.cancel_btn, 1, 1)
            footer.addWidget(self.more_btn, 1, 2)
        else:
            footer.setColumnStretch(0, 1)
            footer.addWidget(self.translate_btn, 0, 0)
            footer.addWidget(self.cancel_btn, 0, 1)
            footer.addWidget(self.more_btn, 0, 2)

        self._footer_compact = compact

    def _layout_mode_for_budget(self, content_budget: int) -> str:
        if content_budget >= 1500:
            return _LAYOUT_DESKTOP_EXACT
        if content_budget >= 1180:
            return _LAYOUT_DESKTOP_COMPACT
        return _LAYOUT_STACKED_COMPACT

    def _apply_responsive_layout(self, *, viewport_width: int | None = None) -> None:
        viewport = self._scroll_area.viewport()
        width = viewport_width if viewport_width is not None else (viewport.width() if viewport is not None else self.width())
        probe_budget = max(360, width - 36)
        mode = self._layout_mode_for_budget(probe_budget)
        self._layout_mode = mode

        if mode == _LAYOUT_DESKTOP_EXACT:
            sidebar_width = 136
            nav_width = 112
            nav_height = 98
            icon_size = 26
            logo_size = 74
            scroll_margins = (18, 16, 18, 12)
            sidebar_margins = (10, 22, 10, 24)
            sidebar_spacing = 14
            dashboard_margins = (36, 26, 36, 22)
            dashboard_spacing = 22
            setup_panel_margins = (30, 24, 30, 24)
            progress_panel_margins = (28, 24, 28, 24)
            field_label_width = 176
            field_min_width = (260, 280)
            body_spacing = 24
            title_status_min_width = 120
            progress_stretch = (10, 9)
            progress_panel_min_width = 580
        elif mode == _LAYOUT_DESKTOP_COMPACT:
            sidebar_width = 118
            nav_width = 100
            nav_height = 92
            icon_size = 24
            logo_size = 66
            scroll_margins = (14, 14, 14, 12)
            sidebar_margins = (8, 18, 8, 20)
            sidebar_spacing = 12
            dashboard_margins = (28, 20, 28, 18)
            dashboard_spacing = 18
            setup_panel_margins = (24, 18, 24, 18)
            progress_panel_margins = (22, 18, 22, 18)
            field_label_width = 154
            field_min_width = (220, 230)
            body_spacing = 22
            title_status_min_width = 104
            progress_stretch = (9, 8)
            progress_panel_min_width = 500
        else:
            sidebar_width = 74
            nav_width = 58
            nav_height = 70
            icon_size = 18
            logo_size = 46
            scroll_margins = (10, 12, 10, 12)
            sidebar_margins = (5, 14, 5, 16)
            sidebar_spacing = 8
            dashboard_margins = (22, 18, 22, 18)
            dashboard_spacing = 18
            setup_panel_margins = (18, 16, 18, 16)
            progress_panel_margins = (18, 16, 18, 16)
            field_label_width = 120
            field_min_width = (150, 170)
            body_spacing = 18
            title_status_min_width = 84
            progress_stretch = (0, 0)
            progress_panel_min_width = 0

        self.sidebar_frame.setFixedWidth(sidebar_width)
        self.sidebar_layout.setContentsMargins(*sidebar_margins)
        self.sidebar_layout.setSpacing(sidebar_spacing)
        self.sidebar_logo_label.setPixmap(
            self._icon("resources/icons/dashboard/logo_l.svg").pixmap(QSize(logo_size, logo_size))
        )
        for button in self._sidebar_nav_buttons:
            button.setFixedWidth(nav_width)
            button.setMinimumHeight(nav_height)
            button.setMaximumHeight(nav_height)
            button.setIconSize(QSize(icon_size, icon_size))

        self.scroll_layout.setContentsMargins(*scroll_margins)
        self.dashboard_layout.setContentsMargins(*dashboard_margins)
        self.dashboard_layout.setSpacing(dashboard_spacing)
        self.setup_layout.setContentsMargins(*setup_panel_margins)
        self.progress_layout.setContentsMargins(*progress_panel_margins)
        self.setup_grid.setColumnMinimumWidth(0, field_label_width)
        self.pdf_edit.setMinimumWidth(field_min_width[0])
        self.outdir_edit.setMinimumWidth(field_min_width[1])
        self.header_status_label.setMinimumWidth(title_status_min_width)
        self.progress_panel.setMinimumWidth(progress_panel_min_width)
        self.progress_panel_title.setVisible(mode != _LAYOUT_STACKED_COMPACT or self.width() > 900)

        self.body_layout.setSpacing(body_spacing)
        if mode == _LAYOUT_STACKED_COMPACT:
            self.body_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            self.body_layout.setStretch(0, 0)
            self.body_layout.setStretch(1, 0)
        else:
            self.body_layout.setDirection(QBoxLayout.Direction.LeftToRight)
            self.body_layout.setStretch(0, progress_stretch[0])
            self.body_layout.setStretch(1, progress_stretch[1])

        self._configure_footer_layout(compact=mode == _LAYOUT_STACKED_COMPACT)
        self.centralWidget().update()

    def _focus_dashboard(self) -> None:
        self._set_dashboard_nav_active(self.dashboard_nav_btn)

    def _show_profile_coming_soon(self) -> None:
        QMessageBox.information(self, "Profile", "Coming soon.")

    def _set_dashboard_nav_active(self, active_button: QToolButton) -> None:
        buttons = getattr(self, "_sidebar_nav_buttons", [])
        for button in buttons:
            button.setProperty("navRole", "active" if button is active_button else "idle")
            button.style().unpolish(button)
            button.style().polish(button)

    def _install_overflow_menu(self) -> None:
        menu = self.more_menu
        actions = {
            "open_output_folder": menu.addAction(self._icon("resources/icons/dashboard/open_folder.svg"), "Open Output Folder"),
            "export_partial": menu.addAction(self._icon("resources/icons/dashboard/export.svg"), "Export Partial DOCX"),
            "rebuild_docx": menu.addAction(self._icon("resources/icons/dashboard/rebuild.svg"), "Rebuild DOCX"),
            "run_report": menu.addAction(self._icon("resources/icons/dashboard/report.svg"), "Generate Run Report"),
            "job_log": menu.addAction(self._icon("resources/icons/dashboard/joblog.svg"), "View Job Log"),
        }
        actions["open_output_folder"].triggered.connect(self._open_output_folder)
        actions["export_partial"].triggered.connect(self._export_partial)
        actions["rebuild_docx"].triggered.connect(self._start_rebuild_docx)
        actions["run_report"].triggered.connect(self._open_run_report)
        actions["job_log"].triggered.connect(self._open_joblog_window)
        self._overflow_menu_actions = actions

    @staticmethod
    def _format_eta_seconds(seconds: float | None) -> str:
        if seconds is None or seconds <= 0:
            return "--"
        rounded = int(round(seconds))
        if rounded < 60:
            return f"~{rounded}s"
        if rounded < 3600:
            minutes = max(1, int(round(rounded / 60.0)))
            return f"~{minutes}m"
        hours = rounded // 3600
        minutes = int(round((rounded % 3600) / 60.0))
        return f"~{hours}h {minutes}m" if minutes else f"~{hours}h"

    def _selected_pdf_page_total(self) -> int | None:
        pages_text = self.pages_label.text().strip()
        if not pages_text.startswith("Pages:"):
            return None
        return _coerce_int_or_none(pages_text.split(":", 1)[1].strip())

    def _apply_dashboard_snapshot(self) -> None:
        snapshot = self._dashboard_snapshot
        self.progress_summary_label.setText(f"{max(0, min(100, int(snapshot.progress_percent)))}%")
        self.progress_eta_label.setText(f"Est. remaining: {snapshot.eta_text}")
        self.status_label.setText(snapshot.current_task or "Idle")

        pages_total = snapshot.pages_total if snapshot.pages_total is not None else self._selected_pdf_page_total()
        images_total = snapshot.images_total if snapshot.images_total is not None else 0
        self.metric_pages_title_label.setText(snapshot.pages_title)
        self.metric_images_title_label.setText(snapshot.images_title)
        self.metric_errors_title_label.setText(snapshot.errors_title)
        self.metric_pages_value_label.setText(
            f"{max(0, int(snapshot.pages_done))} / {pages_total}" if pages_total is not None else f"{max(0, int(snapshot.pages_done))} / --"
        )
        self.metric_pages_retry_value_label.setText(str(max(0, int(snapshot.page_retries))))
        self.metric_images_value_label.setText(f"{max(0, int(snapshot.images_done))} / {max(0, int(images_total))}")
        self.metric_images_retry_value_label.setText(str(max(0, int(snapshot.image_retries))))
        self.metric_errors_value_label.setText(str(max(0, int(snapshot.errors_count))))
        self.metric_errors_retry_value_label.setText(str(max(0, int(snapshot.error_retries))))

    def _refresh_dashboard_counters(self) -> None:
        if self._running and self._progress_total_pages > 0 and self._progress_done_pages > 0 and self._run_started_at is not None:
            elapsed = max(0.0, time.perf_counter() - self._run_started_at)
            remaining_pages = max(0, self._progress_total_pages - self._progress_done_pages)
            per_page = elapsed / float(max(1, self._progress_done_pages))
            self._dashboard_eta_text = self._format_eta_seconds(per_page * float(remaining_pages))

        progress_attr = getattr(self.progress, "value", None)
        if callable(progress_attr):
            progress_value = int(progress_attr())
        elif isinstance(progress_attr, (int, float)):
            progress_value = int(progress_attr)
        else:
            progress_value = 0
        self._dashboard_snapshot.progress_percent = progress_value
        self._dashboard_snapshot.eta_text = self._dashboard_eta_text
        self._dashboard_snapshot.current_task = self.status_label.text().strip() or "Idle"
        if self._queue_total_jobs > 0:
            self._dashboard_snapshot.pages_done = max(0, int(self._dashboard_snapshot.pages_done))
            self._dashboard_snapshot.pages_total = self._queue_total_jobs
            self._dashboard_snapshot.images_total = self._queue_total_jobs
            self._dashboard_snapshot.errors_count = self._dashboard_error_count
            self._dashboard_snapshot.error_retries = self._dashboard_error_retry_count
            self._dashboard_snapshot.pages_title = "Jobs"
            self._dashboard_snapshot.images_title = "Skipped"
            self._dashboard_snapshot.errors_title = "Failed"
        else:
            total_pages = self._progress_total_pages if self._progress_total_pages > 0 else self._selected_pdf_page_total()
            done_pages = max(0, int(self._progress_done_pages))
            retries = len(self._retry_pages_seen)
            images_seen = len(self._image_pages_seen)
            self._dashboard_snapshot.pages_done = done_pages
            self._dashboard_snapshot.pages_total = total_pages
            self._dashboard_snapshot.page_retries = retries
            self._dashboard_snapshot.images_done = images_seen
            self._dashboard_snapshot.images_total = images_seen if images_seen > 0 else 0
            self._dashboard_snapshot.image_retries = retries if images_seen else 0
            self._dashboard_snapshot.errors_count = self._dashboard_error_count
            self._dashboard_snapshot.error_retries = self._dashboard_error_retry_count
            self._dashboard_snapshot.pages_title = "Pages"
            self._dashboard_snapshot.images_title = "Images"
            self._dashboard_snapshot.errors_title = "Errors"
        self._apply_dashboard_snapshot()

    def _refresh_lang_badge(self) -> None:
        lang = str(self.lang_combo.currentText() or "EN").strip().upper()
        self.flag_label.clear()
        self.flag_label.setText("")
        icon_rel = _LANG_FLAG_ICON_BY_CODE.get(lang)
        if not icon_rel:
            self.flag_label.setVisible(False)
            return
        icon_path = resource_path(icon_rel)
        if not icon_path.exists():
            self.flag_label.setVisible(False)
            return
        self.flag_label.setVisible(True)
        self.flag_label.setPixmap(self._icon(icon_rel).pixmap(QSize(28, 18)))

    def _capture_safe_profile_backup(self) -> dict[str, object]:
        return {
            "effort_policy": self.effort_policy_combo.currentText().strip().lower(),
            "image_mode": self.images_combo.currentText().strip().lower(),
            "ocr_mode": self.ocr_mode_combo.currentText().strip().lower(),
            "ocr_engine": self.ocr_engine_combo.currentText().strip().lower(),
            "workers": max(1, min(6, int(self.workers_spin.value()))),
            "resume": self.resume_check.isChecked(),
            "keep_intermediates": self.keep_check.isChecked(),
        }

    def _apply_safe_profile_to_controls(self, values: dict[str, object]) -> None:
        widgets = (
            self.effort_policy_combo,
            self.images_combo,
            self.ocr_mode_combo,
            self.ocr_engine_combo,
            self.workers_spin,
            self.resume_check,
            self.keep_check,
        )
        for widget in widgets:
            widget.blockSignals(True)
        try:
            self.effort_policy_combo.setCurrentText(str(values.get("effort_policy", "fixed_high")))
            self.images_combo.setCurrentText(str(values.get("image_mode", "off")))
            self.ocr_mode_combo.setCurrentText(str(values.get("ocr_mode", "always")))
            self.ocr_engine_combo.setCurrentText(str(values.get("ocr_engine", "api")))
            self.workers_spin.setValue(max(1, min(6, int(values.get("workers", 1)))))
            self.resume_check.setChecked(bool(values.get("resume", False)))
            self.keep_check.setChecked(bool(values.get("keep_intermediates", True)))
        finally:
            for widget in widgets:
                widget.blockSignals(False)
        self._update_controls()

    def _apply_transient_ocr_heavy_safe_profile(self) -> None:
        if self._transient_safe_profile_backup is None:
            self._transient_safe_profile_backup = self._capture_safe_profile_backup()
        self._transient_safe_profile_active = True
        self._apply_safe_profile_to_controls(
            {
                "effort_policy": "fixed_high",
                "image_mode": "off",
                "ocr_mode": "always",
                "ocr_engine": "api",
                "workers": 1,
                "resume": False,
                "keep_intermediates": True,
            }
        )
        self._append_log("Applied OCR-heavy safe profile for this run only. Saved defaults were not changed.")

    def _restore_transient_safe_profile_if_needed(self) -> None:
        if not self._transient_safe_profile_active or self._transient_safe_profile_backup is None:
            return
        backup = dict(self._transient_safe_profile_backup)
        self._transient_safe_profile_active = False
        self._transient_safe_profile_backup = None
        self._apply_safe_profile_to_controls(backup)
        self._append_log("Restored your previous run settings after the OCR-heavy safe-profile run.")

    def _restore_settings(self) -> None:
        defaults = self._defaults
        outdir = self._existing_output_dir_text(str(defaults.get("last_outdir", "") or "").strip())
        if not outdir:
            outdir = self._existing_output_dir_text(
                str(defaults.get("default_outdir", "") or "").strip()
            )
        self.outdir_edit.setText(outdir)

        lang = str(defaults.get("last_lang", defaults.get("default_lang", "EN")) or "EN").strip().upper()
        if lang not in {"EN", "FR", "AR"}:
            lang = "EN"
        self.lang_combo.setCurrentText(lang)
        self.effort_combo.setCurrentText(str(defaults.get("effort", defaults.get("default_effort", "high")) or "high"))
        self.effort_policy_combo.setCurrentText(
            str(defaults.get("effort_policy", defaults.get("default_effort_policy", "adaptive")) or "adaptive")
        )
        self.images_combo.setCurrentText(str(defaults.get("image_mode", defaults.get("default_images_mode", "off")) or "off"))
        self.ocr_mode_combo.setCurrentText(str(defaults.get("ocr_mode", defaults.get("ocr_mode_default", "auto")) or "auto"))
        self.ocr_engine_combo.setCurrentText(
            str(defaults.get("ocr_engine", defaults.get("ocr_engine_default", "local_then_api")) or "local_then_api")
        )

        start_page = defaults.get("start_page", defaults.get("default_start_page", 1))
        end_page = defaults.get("end_page", defaults.get("default_end_page", None))
        max_pages = defaults.get("max_pages", None)
        self.start_edit.setText(str(start_page if isinstance(start_page, int) and start_page > 0 else 1))
        self.end_edit.setText("" if end_page in (None, "") else str(end_page))
        self.max_edit.setText("" if max_pages in (None, "") else str(max_pages))

        workers_value = defaults.get("workers", defaults.get("default_workers", 3))
        try:
            workers = int(workers_value)  # type: ignore[arg-type]
        except Exception:
            workers = 3
        self.workers_spin.setValue(max(1, min(6, workers)))

        self.resume_check.setChecked(bool(defaults.get("resume", defaults.get("default_resume", True))))
        self.breaks_check.setChecked(bool(defaults.get("page_breaks", defaults.get("default_page_breaks", True))))
        self.keep_check.setChecked(bool(defaults.get("keep_intermediates", defaults.get("default_keep_intermediates", True))))
        self.queue_manifest_edit.setText(str(defaults.get("queue_manifest_path", "") or ""))
        self.queue_rerun_failed_only_check.setChecked(bool(defaults.get("queue_rerun_failed_only", False)))
        self._refresh_lang_badge()

    def _save_settings(self) -> None:
        timer = getattr(self, "_settings_save_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()

        def opt_int(text: str) -> int | None:
            cleaned = text.strip()
            if cleaned == "":
                return None
            try:
                return int(cleaned)
            except ValueError:
                return None

        start_text = self.start_edit.text().strip() or "1"
        try:
            start_page = int(start_text)
        except ValueError:
            start_page = 1
        if start_page <= 0:
            start_page = 1

        values = {
            "last_outdir": self.outdir_edit.text().strip(),
            "last_lang": self.lang_combo.currentText().strip().upper(),
            "effort": self.effort_combo.currentText().strip().lower(),
            "effort_policy": self.effort_policy_combo.currentText().strip().lower(),
            "image_mode": self.images_combo.currentText().strip().lower(),
            "ocr_mode": self.ocr_mode_combo.currentText().strip().lower(),
            "ocr_engine": self.ocr_engine_combo.currentText().strip().lower(),
            "start_page": start_page,
            "end_page": opt_int(self.end_edit.text()),
            "max_pages": opt_int(self.max_edit.text()),
            "workers": max(1, min(6, int(self.workers_spin.value()))),
            "resume": self.resume_check.isChecked(),
            "page_breaks": self.breaks_check.isChecked(),
            "keep_intermediates": self.keep_check.isChecked(),
            "queue_manifest_path": self.queue_manifest_edit.text().strip(),
            "queue_rerun_failed_only": self.queue_rerun_failed_only_check.isChecked(),
        }
        if self._transient_safe_profile_active and self._transient_safe_profile_backup is not None:
            for key, value in self._transient_safe_profile_backup.items():
                values[key] = value
        try:
            save_gui_settings(values)
            self._defaults.update(values)
        except Exception:
            pass

    def _install_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")
        file_new = file_menu.addAction("New Run")
        file_new.triggered.connect(self._new_run)
        file_open = file_menu.addAction("Open Output Folder")
        file_open.triggered.connect(self._open_output_folder)
        file_export = file_menu.addAction("Export Partial DOCX")
        file_export.triggered.connect(self._export_partial)
        file_menu.addSeparator()
        file_exit = file_menu.addAction("Exit")
        file_exit.triggered.connect(self.close)

        tools_menu = menu_bar.addMenu("Tools")
        tools_settings = tools_menu.addAction("Settings...")
        tools_settings.triggered.connect(self._open_settings_dialog)
        tools_review_queue = tools_menu.addAction("Review Queue...")
        tools_review_queue.triggered.connect(self._open_review_queue_dialog)
        tools_save_joblog = tools_menu.addAction("Save to Job Log...")
        tools_save_joblog.triggered.connect(self._open_save_to_joblog_dialog)
        tools_joblog = tools_menu.addAction("View Job Log")
        tools_joblog.triggered.connect(self._open_joblog_window)
        if not self._simple_mode:
            tools_menu.addSeparator()
            tools_glossary_builder = tools_menu.addAction("Glossary Builder...")
            tools_glossary_builder.triggered.connect(self._open_glossary_builder_dialog)
            tools_calibration_audit = tools_menu.addAction("Calibration Audit...")
            tools_calibration_audit.triggered.connect(self._open_calibration_audit_dialog)
        else:
            tools_glossary_builder = None
            tools_calibration_audit = None
        tools_menu.addSeparator()
        tools_test = tools_menu.addAction("Test API Keys...")
        tools_test.triggered.connect(self._test_api_keys)
        clear_menu = tools_menu.addMenu("Clear Stored Keys...")
        clear_openai = clear_menu.addAction("OpenAI key")
        clear_openai.triggered.connect(self._clear_openai_key)
        clear_ocr = clear_menu.addAction("OCR key")
        clear_ocr.triggered.connect(self._clear_ocr_key)
        clear_both = clear_menu.addAction("Both")
        clear_both.triggered.connect(self._clear_all_keys)

        help_menu = menu_bar.addMenu("Help")
        help_about = help_menu.addAction("About")
        help_about.triggered.connect(self._show_about)
        help_logs = help_menu.addAction("Open Logs Folder")
        help_logs.triggered.connect(self._open_logs_folder)
        help_how = help_menu.addAction("How it works")
        help_how.triggered.connect(self._show_how_it_works)

        self._menu_actions = {
            "new_run": file_new,
            "open_output_folder": file_open,
            "export_partial": file_export,
            "settings": tools_settings,
            "review_queue": tools_review_queue,
            "save_joblog": tools_save_joblog,
            "job_log": tools_joblog,
            "test_api_keys": tools_test,
            "about": help_about,
            "open_logs": help_logs,
            "how_it_works": help_how,
        }
        if tools_glossary_builder is not None:
            self._menu_actions["glossary_builder"] = tools_glossary_builder
        if tools_calibration_audit is not None:
            self._menu_actions["calibration_audit"] = tools_calibration_audit

    def _set_menu_enabled(self, key: str, enabled: bool) -> None:
        action = self._menu_actions.get(key)
        if action is not None:
            action.setEnabled(enabled)

    def _clear_openai_key(self) -> None:
        try:
            delete_openai_key()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Credential Manager", str(exc))
            return
        QMessageBox.information(self, "Credential Manager", "Stored OpenAI key cleared.")

    def _clear_ocr_key(self) -> None:
        try:
            delete_ocr_key()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Credential Manager", str(exc))
            return
        QMessageBox.information(self, "Credential Manager", "Stored OCR key cleared.")

    def _clear_all_keys(self) -> None:
        try:
            delete_openai_key()
            delete_ocr_key()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Credential Manager", str(exc))
            return
        QMessageBox.information(self, "Credential Manager", "Stored OpenAI and OCR keys cleared.")

    def _test_api_keys(self) -> None:
        lines: list[str] = []
        try:
            openai_key = get_openai_key()
        except RuntimeError as exc:
            QMessageBox.critical(self, "API Key Test", str(exc))
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
            QMessageBox.critical(self, "API Key Test", str(exc))
            return
        if not ocr_key:
            lines.append("OCR API: missing key")
        else:
            provider = normalize_ocr_api_provider(
                self._defaults.get("ocr_api_provider", self._defaults.get("ocr_api_provider_default", "openai"))
            )
            started = time.perf_counter()
            try:
                test_ocr_provider_connection(
                    OcrEngineConfig(
                        policy=parse_ocr_engine_policy(self.ocr_engine_combo.currentText()),
                        api_provider=provider,
                        api_base_url=str(self._defaults.get("ocr_api_base_url", "") or "").strip() or None,
                        api_model=str(self._defaults.get("ocr_api_model", "") or "").strip()
                        or default_ocr_api_model(provider),
                        api_key_env_name=str(
                            self._defaults.get(
                                "ocr_api_key_env_name",
                                default_ocr_api_env_name(provider),
                            )
                            or default_ocr_api_env_name(provider)
                        ),
                    ),
                    api_key=ocr_key,
                )
                latency_ms = int((time.perf_counter() - started) * 1000)
                lines.append(f"OCR API ({provider.value}): PASS ({latency_ms} ms)")
            except Exception as exc:  # noqa: BLE001
                lines.append(f"OCR API ({provider.value}): FAIL ({type(exc).__name__})")

        QMessageBox.information(self, "API Key Test", "\n".join(lines))

    def _show_about(self) -> None:
        build_date = datetime.fromtimestamp(Path(__file__).stat().st_mtime).strftime("%Y-%m-%d")
        QMessageBox.information(
            self,
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
            QMessageBox.critical(self, "Open logs folder", str(exc))

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
        QMessageBox.information(self, "How it works", "\n".join(lines))

    def collect_debug_bundle_metadata_paths(self) -> list[Path]:
        paths: list[Path] = []
        settings_file = settings_path()
        if settings_file.exists():
            paths.append(settings_file)
        if self._metadata_log_file.exists():
            paths.append(self._metadata_log_file)
        if self._last_summary is not None:
            run_state_path = self._last_summary.run_dir / "run_state.json"
            if run_state_path.exists():
                paths.append(run_state_path)
            run_events_path = self._last_summary.run_dir / "run_events.jsonl"
            if run_events_path.exists():
                paths.append(run_events_path)
        if self._last_run_config is not None:
            run_paths = build_output_paths(
                self._last_run_config.output_dir,
                self._last_run_config.pdf_path,
                self._last_run_config.target_lang,
            )
            if run_paths.run_state_path.exists():
                paths.append(run_paths.run_state_path)
        return paths

    def _gmail_intake_settings(self) -> tuple[bool, int, str]:
        enabled = bool(self._defaults.get("gmail_intake_bridge_enabled", False))
        token = str(self._defaults.get("gmail_intake_bridge_token", "") or "").strip()
        try:
            port = int(self._defaults.get("gmail_intake_port", 8765))
        except (TypeError, ValueError):
            port = 8765
        port = max(1, min(65535, port))
        return enabled, port, token

    @staticmethod
    def _existing_output_dir_text(outdir_text: str) -> str:
        cleaned = str(outdir_text or "").strip()
        if cleaned == "":
            return ""
        try:
            candidate = Path(cleaned).expanduser().resolve()
        except OSError:
            return ""
        if not candidate.exists() or not candidate.is_dir():
            return ""
        return str(candidate)

    @staticmethod
    def _writable_output_dir_text(outdir_text: str) -> str:
        cleaned = str(outdir_text or "").strip()
        if cleaned == "":
            return ""
        try:
            return str(require_writable_output_dir(Path(cleaned)))
        except ValueError:
            return ""

    @staticmethod
    def _default_downloads_dir() -> Path:
        candidate = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        if candidate:
            return Path(candidate).expanduser().resolve()
        return (Path.home() / "Downloads").expanduser().resolve()

    def _resolve_effective_gmail_output_dir_text(self) -> str | None:
        current_text = self.outdir_edit.text().strip()
        current_dir = self._writable_output_dir_text(current_text)
        if current_dir:
            if current_dir != current_text:
                self.outdir_edit.setText(current_dir)
            return current_dir

        default_text = str(self._defaults.get("default_outdir", "") or "").strip()
        default_dir = self._writable_output_dir_text(default_text)
        if default_dir:
            if self.outdir_edit.text().strip() != default_dir:
                self.outdir_edit.setText(default_dir)
            return default_dir

        downloads_dir = self._default_downloads_dir()
        try:
            downloads_dir.mkdir(parents=True, exist_ok=True)
            downloads_text = str(require_writable_output_dir(downloads_dir))
        except ValueError as exc:
            self.status_label.setText("Gmail output folder unavailable")
            self.header_status_label.setText("Gmail output folder unavailable")
            self._dashboard_snapshot.current_task = "Gmail output folder unavailable"
            QMessageBox.warning(
                self,
                "Gmail intake",
                "Unable to prepare an output folder for Gmail intake.\n\n"
                f"{exc}",
            )
            return None

        previous_text = current_text or default_text
        if self.outdir_edit.text().strip() != downloads_text:
            self.outdir_edit.setText(downloads_text)
        self.status_label.setText("Gmail output folder set to Downloads")
        self.header_status_label.setText("Gmail output folder set")
        self._dashboard_snapshot.current_task = "Gmail output folder set to Downloads"
        if previous_text:
            self._append_log(
                "Gmail batch output folder fallback applied: "
                f"{previous_text} is unavailable; using Downloads {downloads_text}."
            )
        else:
            self._append_log(
                "Gmail batch output folder fallback applied: "
                f"no valid output folder was set; using Downloads {downloads_text}."
            )
        return downloads_text

    def _clear_gmail_batch_session(self) -> None:
        preview_cache_transfer = self._gmail_batch_preview_cache_transfer
        self._gmail_batch_preview_cache_transfer = None
        if preview_cache_transfer is not None:
            preview_cache_transfer.cleanup()
        session = self._gmail_batch_session
        self._gmail_batch_session = None
        self._gmail_batch_in_progress = False
        self._gmail_batch_current_index = None
        if session is None:
            return
        session.cleanup()

    def _current_gmail_output_dir_text(self) -> str:
        current = self._existing_output_dir_text(self.outdir_edit.text().strip())
        if current:
            return current
        return self._existing_output_dir_text(str(self._defaults.get("default_outdir", "") or "").strip())

    def _has_active_gmail_batch(self) -> bool:
        return self._gmail_batch_session is not None and self._gmail_batch_in_progress

    def _current_gmail_batch_attachment(self) -> DownloadedGmailAttachment | None:
        session = self._gmail_batch_session
        index = self._gmail_batch_current_index
        if session is None or index is None:
            return None
        if index < 0 or index >= len(session.downloaded_attachments):
            return None
        return session.downloaded_attachments[index]

    def _persist_gmail_batch_session_report(
        self,
        session: GmailBatchSession | None = None,
        *,
        status: str | None = None,
        halt_reason: str | None = None,
    ) -> Path | None:
        active_session = session if isinstance(session, GmailBatchSession) else self._gmail_batch_session
        if active_session is None:
            return None
        if status is not None:
            active_session.status = status
        if halt_reason is not None:
            active_session.halt_reason = halt_reason
        try:
            return write_gmail_batch_session_report(active_session)
        except OSError as exc:
            self._append_log(f"Gmail batch diagnostics write failed: {exc}")
            return None

    def _resolve_translation_config(
        self,
        *,
        pdf_override: str | None = None,
        outdir_override: str | None = None,
        lang_override: str | None = None,
        start_page_override: int | None = None,
    ) -> RunConfig | None:
        def _call_build_config() -> RunConfig:
            return self._build_config(
                pdf_override=pdf_override,
                outdir_override=outdir_override,
                lang_override=lang_override,
                start_page_override=start_page_override,
            )

        try:
            config = _call_build_config()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Invalid configuration", str(exc))
            return None

        if (
            config.target_lang in (TargetLang.EN, TargetLang.FR)
            and config.effort_policy == EffortPolicy.FIXED_XHIGH
        ):
            decision = self._warn_fixed_xhigh_for_enfr()
            if decision == "switch":
                self.effort_policy_combo.setCurrentText("fixed_high")
                try:
                    config = _call_build_config()
                except Exception as exc:  # noqa: BLE001
                    QMessageBox.critical(self, "Invalid configuration", str(exc))
                    return None
            elif decision != "proceed":
                return None

        return self._warn_ocr_api_only_if_needed(config, rebuild_config=_call_build_config)

    def _start_translation_run(
        self,
        *,
        config: RunConfig,
        clear_gmail_batch_session: bool,
        consume_advisor_choice: bool,
        status_text: str,
        header_status_text: str,
        dashboard_task: str,
    ) -> None:
        advisor_applied = (
            config.advisor_recommendation_applied
            if isinstance(config.advisor_recommendation_applied, bool)
            else None
        )
        self._save_settings()
        if consume_advisor_choice:
            self._consume_advisor_choice()
        if self._review_queue_dialog is not None and self._review_queue_dialog.isVisible():
            self._review_queue_dialog.close()
            self._review_queue_dialog = None
        if clear_gmail_batch_session:
            self._clear_gmail_batch_session()
            self._last_gmail_message_load_result = None
        self._last_summary = None
        self._last_run_report_path = None
        self._last_queue_summary_path = None
        self._last_run_dir = build_output_paths(config.output_dir, config.pdf_path, config.target_lang).run_dir
        self._last_output_docx = None
        self._last_run_config = config
        self._last_joblog_seed = None
        self._last_review_queue = []
        self._last_workflow = None
        self._can_export_partial = False
        self.final_docx_edit.clear()
        self.progress.setValue(0)
        self.page_label.setText("Page: -/-")
        self.status_label.setText(status_text)
        self.header_status_label.setText(header_status_text)
        self.queue_status_label.setText("Queue: idle")
        self._dashboard_snapshot.current_task = dashboard_task
        self._dashboard_error_count = 0
        self._dashboard_error_retry_count = 0
        self._dashboard_eta_text = "--"
        self._run_started_at = time.perf_counter()
        self._reset_live_counters()
        if advisor_applied is not None:
            self._append_log(f"OCR advisor choice for this run: applied={advisor_applied}")

        max_retries = int(self._defaults.get("perf_max_transport_retries", 4) or 4)
        backoff_cap = float(self._defaults.get("perf_backoff_cap_seconds", 12.0) or 12.0)

        thread = QThread(self)
        worker = TranslationRunWorker(
            config=config,
            max_transport_retries=max_retries,
            backoff_cap_seconds=backoff_cap,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.log.connect(self._append_log)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_finished)
        worker.error.connect(self._on_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(self._cleanup_worker)
        self.request_cancel.connect(worker.cancel, Qt.ConnectionType.QueuedConnection)

        self._worker_thread = thread
        self._worker = worker
        self._set_busy(True, translation=True)
        thread.start()

    def _run_after_worker_cleanup(self, callback: Callable[[], None]) -> None:
        if self._worker is None and self._worker_thread is None:
            callback()
            return
        self._after_worker_cleanup = callback

    def _stop_gmail_batch(
        self,
        *,
        status_text: str,
        header_status_text: str,
        log_message: str | None = None,
        warning_message: str | None = None,
        information_message: str | None = None,
    ) -> None:
        persist_report = getattr(self, "_persist_gmail_batch_session_report", None)
        if callable(persist_report):
            persist_report(status="stopped", halt_reason=status_text)
        self._gmail_batch_in_progress = False
        self._gmail_batch_current_index = None
        self._set_busy(False, translation=False)
        self._run_started_at = None
        self.status_label.setText(status_text)
        self.header_status_label.setText(header_status_text)
        self._dashboard_snapshot.current_task = status_text
        if log_message:
            self._append_log(log_message)
        self._consume_advisor_choice()
        self._update_controls()
        if warning_message:
            QMessageBox.warning(self, "Gmail batch", warning_message)
        elif information_message:
            QMessageBox.information(self, "Gmail batch", information_message)

    def _complete_gmail_batch_stage_three(self) -> None:
        session = self._gmail_batch_session
        total = len(session.downloaded_attachments) if session is not None else 0
        persist_report = getattr(self, "_persist_gmail_batch_session_report", None)
        if callable(persist_report):
            persist_report(session=session, status="ready_for_finalization", halt_reason="")
        self._gmail_batch_in_progress = False
        self._gmail_batch_current_index = None
        self._set_busy(False, translation=False)
        self._run_started_at = None
        self.status_label.setText("Gmail batch ready for finalization")
        self.header_status_label.setText("Gmail batch ready")
        self._dashboard_snapshot.current_task = "Gmail batch ready for finalization"
        self._append_log(
            "Gmail batch Stage 3 complete: "
            f"{total} attachment(s) translated and saved to Job Log."
        )
        self._consume_advisor_choice()
        self._update_controls()
        finalize_batch = getattr(self, "_finalize_completed_gmail_batch", None)
        if callable(finalize_batch):
            finalize_batch()

    def _gmail_batch_honorarios_default_directory(self) -> Path:
        session = self._gmail_batch_session
        if session is not None:
            for item in session.confirmed_items:
                candidate = item.translated_docx_path.expanduser().resolve()
                if candidate.exists():
                    return candidate.parent
        if self._last_output_docx is not None:
            candidate = self._last_output_docx.expanduser().resolve()
            if candidate.exists():
                return candidate.parent
        outdir_text = self._current_gmail_output_dir_text()
        if outdir_text:
            return Path(outdir_text).expanduser().resolve()
        return (Path.home() / "Documents").expanduser().resolve()

    def _build_gmail_batch_honorarios_draft(self):
        session = self._gmail_batch_session
        if session is None or not session.confirmed_items:
            raise ValueError("No confirmed Gmail batch items are available for honorários generation.")
        first_item = session.confirmed_items[0]
        combined_word_count = sum(int(item.translated_word_count) for item in session.confirmed_items)
        return build_honorarios_draft(
            case_number=first_item.case_number,
            word_count=combined_word_count,
            case_entity=first_item.case_entity,
            case_city=first_item.case_city,
        )

    def _set_gmail_batch_finalization_state(
        self,
        *,
        status_text: str,
        header_status_text: str,
        log_message: str | None = None,
    ) -> None:
        self.status_label.setText(status_text)
        self.header_status_label.setText(header_status_text)
        self._dashboard_snapshot.current_task = status_text
        if log_message:
            self._append_log(log_message)
        self._update_controls()

    def _offer_gmail_batch_reply_draft(self, honorarios_docx: Path) -> bool:
        session = self._gmail_batch_session
        persist_report = getattr(self, "_persist_gmail_batch_session_report", None)
        if session is None or not session.confirmed_items:
            QMessageBox.warning(
                self,
                "Gmail draft",
                "No confirmed Gmail batch is available to create the reply draft.",
            )
            return False
        prereqs = assess_gmail_draft_prereqs(
            configured_gog_path=str(self._defaults.get("gmail_gog_path", "") or ""),
            configured_account_email=str(self._defaults.get("gmail_account_email", "") or ""),
        )
        if not prereqs.ready or prereqs.gog_path is None or prereqs.account_email is None:
            if session is not None:
                session.draft_preflight_result = "failed"
                session.draft_created = False
                session.draft_failure_reason = prereqs.message
                if callable(persist_report):
                    persist_report(
                        session=session,
                        status="draft_unavailable",
                        halt_reason="gmail_draft_prereqs_unavailable",
                    )
            QMessageBox.warning(
                self,
                "Gmail draft",
                f"{prereqs.message}\n\n"
                "Check Settings > Keys & Providers > Gmail Drafts and run "
                "'Test Gmail draft prerequisites'.",
            )
            self._set_gmail_batch_finalization_state(
                status_text="Gmail draft unavailable",
                header_status_text="Gmail draft unavailable",
                log_message="Gmail batch finalization stopped because Gmail draft prerequisites are unavailable.",
            )
            return False
        first_item = session.confirmed_items[0]
        try:
            translated_docxs = validate_translated_docx_artifacts_for_gmail_draft(
                translated_docxs=tuple(item.translated_docx_path for item in session.confirmed_items),
                honorarios_docx=honorarios_docx,
            )
            session.draft_preflight_result = "passed"
            session.draft_failure_reason = ""
            session.final_attachment_basenames = tuple(
                path.name for path in (*translated_docxs, honorarios_docx)
            )
            if callable(persist_report):
                persist_report(session=session, status="draft_preflight_passed", halt_reason="")
            request = build_gmail_batch_reply_request(
                gog_path=prereqs.gog_path,
                account_email=prereqs.account_email,
                to_email=first_item.court_email,
                subject=session.message.subject,
                reply_to_message_id=session.intake_context.message_id or session.message.message_id,
                translated_docxs=translated_docxs,
                honorarios_docx=honorarios_docx,
            )
        except ValueError as exc:
            session.draft_preflight_result = "failed"
            session.draft_created = False
            session.draft_failure_reason = str(exc)
            QMessageBox.critical(self, "Gmail draft", str(exc))
            if callable(persist_report):
                persist_report(
                    session=session,
                    status="draft_failed",
                    halt_reason="gmail_draft_preflight_failed",
                )
            self._set_gmail_batch_finalization_state(
                status_text="Gmail draft failed",
                header_status_text="Gmail draft failed",
                log_message=f"Gmail batch finalization failed before draft creation: {exc}",
            )
            return False
        result = create_gmail_draft_via_gog(request)
        if not result.ok:
            details = result.stderr or result.stdout or result.message
            session.draft_created = False
            session.draft_failure_reason = details
            QMessageBox.critical(
                self,
                "Gmail draft",
                "Failed to create Gmail draft.\n\n"
                f"{details}\n\n"
                "Check Settings > Keys & Providers > Gmail Drafts and run "
                "'Test Gmail draft prerequisites'.",
            )
            if callable(persist_report):
                persist_report(
                    session=session,
                    status="draft_failed",
                    halt_reason="gmail_draft_create_failed",
                )
            self._set_gmail_batch_finalization_state(
                status_text="Gmail draft failed",
                header_status_text="Gmail draft failed",
                log_message=f"Gmail batch reply draft creation failed: {details}",
            )
            return False
        count = len(session.confirmed_items)
        session.draft_created = True
        session.draft_failure_reason = ""
        if callable(persist_report):
            persist_report(session=session, status="draft_ready", halt_reason="")
        self._set_gmail_batch_finalization_state(
            status_text="Gmail reply draft ready",
            header_status_text="Gmail draft ready",
            log_message=(
                "Gmail batch Stage 4 complete: "
                f"reply draft created for {count} translated DOCX file(s) "
                f"and honorários {honorarios_docx.expanduser().resolve()}."
            ),
        )
        open_gmail = QMessageBox.question(
            self,
            "Gmail draft",
            "Gmail draft created successfully. Abrir Gmail?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if open_gmail == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl(GMAIL_DRAFTS_URL))
        self._clear_gmail_batch_session()
        return True

    def _finalize_completed_gmail_batch(self) -> None:
        session = self._gmail_batch_session
        persist_report = getattr(self, "_persist_gmail_batch_session_report", None)
        if session is None:
            return
        if not session.confirmed_items or len(session.confirmed_items) != len(session.downloaded_attachments):
            return
        generate_honorarios = QMessageBox.question(
            self,
            "Gmail batch",
            "Generate one honorários DOCX for this Gmail batch now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        session.honorarios_requested = generate_honorarios == QMessageBox.StandardButton.Yes
        if generate_honorarios != QMessageBox.StandardButton.Yes:
            if callable(persist_report):
                persist_report(
                    session=session,
                    status="finalization_skipped",
                    halt_reason="honorarios_generation_skipped",
                )
            self._set_gmail_batch_finalization_state(
                status_text="Gmail batch finalization skipped",
                header_status_text="Gmail batch skipped",
                log_message="Gmail batch finalization skipped before honorários generation.",
            )
            return
        try:
            draft = self._build_gmail_batch_honorarios_draft()
        except ValueError as exc:
            QMessageBox.warning(self, "Gmail batch", str(exc))
            self._set_gmail_batch_finalization_state(
                status_text="Gmail batch finalization failed",
                header_status_text="Gmail batch failed",
                log_message=f"Gmail batch finalization failed: {exc}",
            )
            return
        dialog = QtHonorariosExportDialog(
            parent=self,
            draft=draft,
            default_directory=self._gmail_batch_honorarios_default_directory(),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.saved_path is None:
            if callable(persist_report):
                persist_report(
                    session=session,
                    status="finalization_skipped",
                    halt_reason="honorarios_generation_cancelled",
                )
            self._set_gmail_batch_finalization_state(
                status_text="Gmail batch finalization skipped",
                header_status_text="Gmail batch skipped",
                log_message="Gmail batch finalization stopped because honorários generation was cancelled.",
            )
            dialog.deleteLater()
            return
        honorarios_docx = dialog.saved_path.expanduser().resolve()
        session.requested_honorarios_path = dialog.requested_path
        session.actual_honorarios_path = honorarios_docx
        session.honorarios_auto_renamed = bool(dialog.auto_renamed)
        if callable(persist_report):
            persist_report(session=session, status="honorarios_ready", halt_reason="")
        dialog.deleteLater()
        self._offer_gmail_batch_reply_draft(honorarios_docx)

    def _record_gmail_batch_saved_result(self, saved_result: JobLogSavedResult, *, run_dir: Path) -> bool:
        session = self._gmail_batch_session
        attachment = self._current_gmail_batch_attachment()
        if session is None or attachment is None:
            return False
        persist_report = getattr(self, "_persist_gmail_batch_session_report", None)
        original_translated_docx = saved_result.translated_docx_path.expanduser().resolve()
        # Gmail drafts attach the staged copy so later honorários export cannot overwrite it.
        staged_translated_docx = stage_gmail_batch_translated_docx(
            session=session,
            translated_docx_path=original_translated_docx,
        )
        confirmed_item = GmailBatchConfirmedItem(
            downloaded_attachment=attachment,
            translated_docx_path=staged_translated_docx,
            run_dir=run_dir.expanduser().resolve(),
            translated_word_count=int(saved_result.word_count),
            joblog_row_id=int(saved_result.row_id),
            run_id=saved_result.run_id.strip(),
            case_number=saved_result.case_number.strip(),
            case_entity=saved_result.case_entity.strip(),
            case_city=saved_result.case_city.strip(),
            court_email=saved_result.court_email.strip(),
        )
        session.confirmed_items.append(confirmed_item)
        if callable(persist_report):
            persist_report(session=session, status="joblog_saved", halt_reason="")
        if session.consistency_signature is None:
            session.consistency_signature = confirmed_item.consistency_signature
            return True
        return confirmed_item.consistency_signature == session.consistency_signature

    def _start_next_gmail_batch_translation(self) -> None:
        session = self._gmail_batch_session
        if session is None:
            return
        persist_report = getattr(self, "_persist_gmail_batch_session_report", None)
        next_index = len(session.confirmed_items)
        total = len(session.downloaded_attachments)
        if next_index >= total:
            self._complete_gmail_batch_stage_three()
            return
        attachment = session.downloaded_attachments[next_index]
        outdir_text = self._resolve_effective_gmail_output_dir_text()
        if outdir_text is None:
            self._stop_gmail_batch(
                status_text="Gmail batch stopped",
                header_status_text="Gmail batch stopped",
                log_message="Gmail batch stopped because no usable output folder is available.",
            )
            return
        config = self._resolve_translation_config(
            pdf_override=str(attachment.saved_path),
            outdir_override=outdir_text,
            start_page_override=int(attachment.start_page),
        )
        if config is None:
            self._stop_gmail_batch(
                status_text="Gmail batch stopped",
                header_status_text="Gmail batch stopped",
                log_message=(
                    "Gmail batch stopped before the next attachment could start: "
                    f"{attachment.candidate.filename}"
                ),
            )
            return
        item_number = next_index + 1
        self._gmail_batch_in_progress = True
        self._gmail_batch_current_index = next_index
        config.gmail_batch_context = {
            "source": "gmail_intake",
            "session_id": session.session_id,
            "message_id": session.intake_context.message_id,
            "thread_id": session.intake_context.thread_id,
            "selected_attachment_filename": attachment.candidate.filename,
            "selected_attachment_count": len(session.downloaded_attachments),
            "selected_target_lang": session.selected_target_lang or config.target_lang.value,
            "selected_start_page": int(attachment.start_page),
            "gmail_batch_session_report_path": (
                str(session.session_report_path.expanduser().resolve())
                if isinstance(session.session_report_path, Path)
                else ""
            ),
        }
        self._append_log(
            "Gmail batch starting item "
            f"{item_number}/{total}: {attachment.candidate.filename}"
        )
        if callable(persist_report):
            persist_report(session=session, status="translating", halt_reason="")
        self._start_translation_run(
            config=config,
            clear_gmail_batch_session=False,
            consume_advisor_choice=False,
            status_text=f"Gmail batch {item_number}/{total}: {attachment.candidate.filename}",
            header_status_text=f"Gmail batch {item_number}/{total}",
            dashboard_task=f"Gmail batch {item_number}/{total}: {attachment.candidate.filename}",
        )

    def _start_gmail_message_load(self, context: InboundMailContext) -> None:
        if self._busy:
            return
        self._clear_gmail_batch_session()
        self._last_gmail_message_load_result = None
        self.status_label.setText("Loading Gmail message...")
        self.header_status_label.setText("Loading Gmail message...")
        self._dashboard_snapshot.current_task = "Loading Gmail message..."
        thread = QThread(self)
        worker = GmailMessageLoadWorker(
            context=context,
            configured_gog_path=str(self._defaults.get("gmail_gog_path", "") or ""),
            configured_account_email=str(self._defaults.get("gmail_account_email", "") or ""),
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.log.connect(self._append_log)
        worker.finished.connect(self._on_gmail_message_load_finished)
        worker.error.connect(self._on_gmail_message_load_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(self._cleanup_worker)
        self._worker_thread = thread
        self._worker = worker
        self._run_started_at = time.perf_counter()
        self._set_busy(True, translation=False)
        thread.start()

    def _open_gmail_batch_review_dialog(
        self,
        load_result: GmailMessageLoadResult,
        *,
        output_dir_text: str,
    ) -> GmailBatchReviewResult | None:
        message = load_result.message
        if message is None or load_result.gog_path is None or load_result.account_email is None:
            return None
        preview_cache_transfer = self._gmail_batch_preview_cache_transfer
        self._gmail_batch_preview_cache_transfer = None
        if preview_cache_transfer is not None:
            preview_cache_transfer.cleanup()
        _request_gmail_window_attention(
            self,
            reason="review_dialog",
            bridge=getattr(self, "_gmail_intake_bridge", None),
            build_identity=getattr(self, "_build_identity", None),
            append_log=getattr(self, "_append_log", None),
        )
        start_text = self.start_edit.text().strip() or str(self._defaults.get("default_start_page", 1) or 1)
        try:
            default_start_page = max(1, int(start_text))
        except ValueError:
            default_start_page = 1
        dialog = QtGmailBatchReviewDialog(
            parent=self,
            message=message,
            gog_path=load_result.gog_path,
            account_email=load_result.account_email,
            target_lang=self.lang_combo.currentText().strip().upper(),
            default_start_page=default_start_page,
            output_dir_text=output_dir_text,
        )
        if hasattr(dialog, "raise_") and hasattr(dialog, "activateWindow"):
            QTimer.singleShot(0, dialog.raise_)
            QTimer.singleShot(0, dialog.activateWindow)
        self._gmail_batch_review_dialog = dialog
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return None
            self._gmail_batch_preview_cache_transfer = dialog.take_preview_cache_transfer()
            return dialog.review_result
        finally:
            self._gmail_batch_review_dialog = None
            dialog.deleteLater()

    def _start_gmail_batch_prepare(
        self,
        load_result: GmailMessageLoadResult,
        review_result: GmailBatchReviewResult,
        *,
        output_dir_text: str,
    ) -> None:
        if (
            load_result.message is None
            or load_result.gog_path is None
            or load_result.account_email is None
        ):
            QMessageBox.warning(
                self,
                "Gmail intake",
                "The Gmail batch session could not be prepared because the fetch result is incomplete.",
            )
            return
        self.status_label.setText("Preparing Gmail attachments...")
        self.header_status_label.setText("Preparing Gmail attachments...")
        self._dashboard_snapshot.current_task = "Preparing Gmail attachments..."
        preview_cache_transfer = self._gmail_batch_preview_cache_transfer
        thread = QThread(self)
        worker = GmailBatchPrepareWorker(
            context=load_result.intake_context,
            message=load_result.message,
            gog_path=load_result.gog_path,
            account_email=load_result.account_email,
            selected_attachments=review_result.selections,
            selected_target_lang=review_result.target_lang.strip().upper(),
            effective_output_dir=Path(output_dir_text).expanduser().resolve(),
            cached_preview_paths=(
                dict(preview_cache_transfer.cached_paths)
                if preview_cache_transfer is not None
                else None
            ),
            cached_preview_page_counts=(
                dict(preview_cache_transfer.cached_page_counts)
                if preview_cache_transfer is not None
                else None
            ),
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.log.connect(self._append_log)
        worker.finished.connect(self._on_gmail_batch_prepare_finished)
        worker.error.connect(self._on_gmail_batch_prepare_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(self._cleanup_worker)
        self._worker_thread = thread
        self._worker = worker
        self._run_started_at = time.perf_counter()
        self._set_busy(True, translation=False)
        thread.start()

    def _handle_gmail_intake_from_bridge(self, context: InboundMailContext) -> None:
        self.gmail_intake_received.emit(context)

    def _stop_gmail_intake_bridge(self) -> None:
        bridge = self._gmail_intake_bridge
        self._gmail_intake_bridge = None
        if bridge is None:
            return
        bridge.stop()
        clear_bridge_runtime_metadata(app_data_dir())

    def _sync_gmail_intake_bridge(self) -> None:
        enabled, port, token = self._gmail_intake_settings()
        current = self._gmail_intake_bridge
        current_matches = (
            current is not None
            and current.host == "127.0.0.1"
            and current.port == port
            and current.token == token
            and current.is_running
        )
        if enabled and token != "" and current_matches:
            _refresh_gmail_bridge_runtime_metadata(
                self,
                bridge=current,
                build_identity=self._build_identity,
            )
            return

        if current is not None:
            current_port = current.port
            self._stop_gmail_intake_bridge()
            self._append_log(f"Gmail intake bridge stopped on 127.0.0.1:{current_port}.")

        if not enabled:
            return
        if token == "":
            self._append_log("Gmail intake bridge is enabled but token is blank; bridge not started.")
            return

        bridge = LocalGmailIntakeBridge(
            port=port,
            token=token,
            on_context=self._handle_gmail_intake_from_bridge,
        )
        try:
            bridge.start()
        except Exception as exc:  # noqa: BLE001
            status_text = "Gmail intake bridge unavailable"
            details_text = (
                "Gmail intake bridge could not start on "
                f"127.0.0.1:{port}.\n\n"
                "Another process may already be using this port.\n\n"
                f"Details: {exc}"
            )
            self.status_label.setText(status_text)
            self.header_status_label.setText(status_text)
            self._dashboard_snapshot.current_task = status_text
            self._append_log(f"Gmail intake bridge failed to start on 127.0.0.1:{port}: {exc}")
            QMessageBox.warning(self, status_text, details_text)
            return
        self._gmail_intake_bridge = bridge
        _refresh_gmail_bridge_runtime_metadata(
            self,
            bridge=bridge,
            build_identity=self._build_identity,
        )
        _ensure_gmail_native_focus_host_registration(
            self,
            append_log=self._append_log,
        )
        self._append_log(f"Gmail intake bridge listening on {bridge.url}.")

    def _on_gmail_intake_received(self, context_obj: object) -> None:
        if not isinstance(context_obj, InboundMailContext):
            return
        self._last_gmail_intake_context = context_obj
        subject = context_obj.subject or "(no subject)"
        summary = f"Gmail intake accepted: {subject}"
        self.status_label.setText(summary)
        self.header_status_label.setText("Gmail intake accepted")
        self._dashboard_snapshot.current_task = summary
        account_suffix = (
            f" account_email={context_obj.account_email}" if context_obj.account_email else ""
        )
        self._append_log(
            "Gmail intake accepted: "
            f"thread_id={context_obj.thread_id} "
            f"message_id={context_obj.message_id} "
            f"subject={subject}{account_suffix}"
        )
        _request_gmail_window_attention(
            self,
            reason="intake_received",
            bridge=getattr(self, "_gmail_intake_bridge", None),
            build_identity=getattr(self, "_build_identity", None),
            append_log=getattr(self, "_append_log", None),
        )
        if self._busy:
            blocked_summary = "Gmail intake blocked by current task"
            self.status_label.setText(blocked_summary)
            self.header_status_label.setText("Gmail intake blocked")
            self._dashboard_snapshot.current_task = blocked_summary
            self._append_log(
                "Gmail intake fetch skipped because another task is already running."
            )
            _request_gmail_window_attention(
                self,
                reason="intake_blocked",
                bridge=getattr(self, "_gmail_intake_bridge", None),
                build_identity=getattr(self, "_build_identity", None),
                append_log=getattr(self, "_append_log", None),
            )
            QMessageBox.information(
                self,
                "Gmail intake",
                (
                    "Gmail intake was received, but another task is already running.\n\n"
                    "Finish or cancel the current translation, then click the Gmail extension again."
                ),
            )
            return
        self._start_gmail_message_load(context_obj)

    def _on_gmail_message_load_finished(self, result_obj: object) -> None:
        self._set_busy(False, translation=False)
        self._run_started_at = None
        if not isinstance(result_obj, GmailMessageLoadResult):
            self.status_label.setText("Gmail intake failed")
            self.header_status_label.setText("Gmail intake failed")
            QMessageBox.warning(self, "Gmail intake", "Gmail fetch returned an invalid result.")
            return
        result = result_obj
        self._last_gmail_message_load_result = result
        if not result.ok:
            status_text = (
                "Gmail intake unavailable"
                if result.classification == "unavailable"
                else "Gmail intake failed"
            )
            self.status_label.setText(status_text)
            self.header_status_label.setText(status_text)
            self._dashboard_snapshot.current_task = status_text
            if result.classification == "unavailable":
                QMessageBox.information(self, "Gmail intake", result.status_message)
            else:
                QMessageBox.warning(self, "Gmail intake", result.status_message)
            return
        message = result.message
        if message is None:
            self.status_label.setText("Gmail intake failed")
            self.header_status_label.setText("Gmail intake failed")
            QMessageBox.warning(self, "Gmail intake", "The fetched Gmail message is unavailable.")
            return
        output_dir_text = self._resolve_effective_gmail_output_dir_text()
        if output_dir_text is None:
            return
        self.status_label.setText("Gmail message ready for review")
        self.header_status_label.setText("Gmail message ready")
        self._dashboard_snapshot.current_task = "Gmail message ready for review"
        review_result = self._open_gmail_batch_review_dialog(
            result,
            output_dir_text=output_dir_text,
        )
        if not review_result:
            if message.attachments:
                self._append_log("Gmail attachment review canceled before download.")
                self.status_label.setText("Gmail review canceled")
                self.header_status_label.setText("Gmail review canceled")
            else:
                self._append_log(
                    "Gmail intake message has no supported attachments in the exact message."
                )
                self.status_label.setText("No supported Gmail attachments found")
                self.header_status_label.setText("No Gmail attachments")
            return
        selected_target_lang = review_result.target_lang.strip().upper()
        if selected_target_lang:
            self.lang_combo.setCurrentText(selected_target_lang)
            self._refresh_lang_badge()
            self._append_log(
                "Gmail batch review confirmed: "
                f"{len(review_result.selections)} attachment(s), target_lang={selected_target_lang}"
            )
        self._run_after_worker_cleanup(
            lambda: self._start_gmail_batch_prepare(
                result,
                review_result,
                output_dir_text=output_dir_text,
            )
        )

    def _on_gmail_message_load_error(self, message: str) -> None:
        self._set_busy(False, translation=False)
        self._run_started_at = None
        self.status_label.setText("Gmail intake failed")
        self.header_status_label.setText("Gmail intake failed")
        self._dashboard_snapshot.current_task = "Gmail intake failed"
        self._append_log(f"Gmail intake runtime error: {message}")
        QMessageBox.critical(self, "Gmail intake", message)

    def _on_gmail_batch_prepare_finished(self, session_obj: object) -> None:
        self._set_busy(False, translation=False)
        self._run_started_at = None
        if not isinstance(session_obj, GmailBatchSession):
            self.status_label.setText("Gmail prepare failed")
            self.header_status_label.setText("Gmail prepare failed")
            QMessageBox.warning(self, "Gmail intake", "Attachment preparation returned an invalid session.")
            return
        self._clear_gmail_batch_session()
        self._gmail_batch_session = session_obj
        count = len(session_obj.downloaded_attachments)
        persist_report = getattr(self, "_persist_gmail_batch_session_report", None)
        if callable(persist_report):
            persist_report(session=session_obj, status="queued", halt_reason="")
        self._append_log(
            "Gmail batch prepared: "
            f"{count} attachment(s) in {session_obj.download_dir}"
        )
        self.status_label.setText(f"Gmail batch queued: {count} attachment(s)")
        self.header_status_label.setText("Gmail batch queued")
        self._dashboard_snapshot.current_task = f"Gmail batch queued: {count} attachment(s)"
        self._run_after_worker_cleanup(self._start_next_gmail_batch_translation)

    def _on_gmail_batch_prepare_error(self, message: str) -> None:
        self._set_busy(False, translation=False)
        self._run_started_at = None
        self._clear_gmail_batch_session()
        self.status_label.setText("Gmail prepare failed")
        self.header_status_label.setText("Gmail prepare failed")
        self._dashboard_snapshot.current_task = "Gmail prepare failed"
        self._append_log(f"Gmail batch prepare failed: {message}")
        QMessageBox.warning(self, "Gmail intake", message)

    def apply_settings_from_dialog(self, values: dict[str, object], persist: bool) -> None:
        self._defaults.update(values)
        if persist:
            save_gui_settings(values)
            self._defaults = load_gui_settings()

        self.lang_combo.setCurrentText(str(self._defaults.get("default_lang", "EN")))
        self.effort_combo.setCurrentText(str(self._defaults.get("default_effort", "high")))
        self.effort_policy_combo.setCurrentText(str(self._defaults.get("default_effort_policy", "adaptive")))
        self.images_combo.setCurrentText(str(self._defaults.get("default_images_mode", "off")))
        self.resume_check.setChecked(bool(self._defaults.get("default_resume", True)))
        self.keep_check.setChecked(bool(self._defaults.get("default_keep_intermediates", True)))
        self.breaks_check.setChecked(bool(self._defaults.get("default_page_breaks", True)))
        self.start_edit.setText(str(self._defaults.get("default_start_page", 1)))
        default_end = self._defaults.get("default_end_page")
        self.end_edit.setText("" if default_end in (None, "") else str(default_end))
        try:
            default_workers = int(self._defaults.get("default_workers", 3))
        except (TypeError, ValueError):
            default_workers = 3
        self.workers_spin.setValue(max(1, min(6, default_workers)))
        default_outdir = str(self._defaults.get("default_outdir", "") or "")
        if default_outdir and not self.outdir_edit.text().strip():
            self.outdir_edit.setText(default_outdir)
        self.ocr_mode_combo.setCurrentText(str(self._defaults.get("ocr_mode_default", "auto")))
        self.ocr_engine_combo.setCurrentText(str(self._defaults.get("ocr_engine_default", "local_then_api")))
        self._sync_gmail_intake_bridge()
        self._update_controls()

    def _open_settings_dialog(self) -> None:
        if self._settings_dialog is not None and self._settings_dialog.isVisible():
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return

        current_pdf_path: Path | None = None
        pdf_text = self.pdf_edit.text().strip()
        if pdf_text:
            candidate = Path(pdf_text).expanduser().resolve()
            if candidate.exists() and candidate.is_file():
                current_pdf_path = candidate

        dialog = QtSettingsDialog(
            parent=self,
            settings=self._defaults,
            apply_callback=self.apply_settings_from_dialog,
            collect_debug_paths=self.collect_debug_bundle_metadata_paths,
            current_pdf_path=current_pdf_path,
            build_identity=self._build_identity,
        )
        dialog.setModal(False)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda _obj=None: setattr(self, "_settings_dialog", None))
        self._settings_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _apply_aux_settings(self, values: dict[str, object]) -> None:
        save_gui_settings(values)
        self._defaults = load_gui_settings()
        self._update_controls()

    def _current_pdf_path_for_tools(self) -> Path | None:
        pdf_text = self.pdf_edit.text().strip()
        if pdf_text == "":
            return None
        candidate = Path(pdf_text).expanduser().resolve()
        if not candidate.exists() or not candidate.is_file():
            return None
        return candidate

    def _current_output_dir_for_tools(self) -> Path | None:
        out_text = self.outdir_edit.text().strip()
        if out_text == "":
            return None
        candidate = Path(out_text).expanduser().resolve()
        if not candidate.exists() or not candidate.is_dir():
            return None
        return candidate

    def _open_glossary_builder_dialog(self) -> None:
        if self._glossary_builder_dialog is not None and self._glossary_builder_dialog.isVisible():
            self._glossary_builder_dialog.raise_()
            self._glossary_builder_dialog.activateWindow()
            return
        dialog = QtGlossaryBuilderDialog(
            parent=self,
            settings=self._defaults,
            current_pdf_path=self._current_pdf_path_for_tools(),
            current_output_dir=self._current_output_dir_for_tools(),
            default_target_lang=self.lang_combo.currentText().strip().upper(),
            save_settings_callback=self._apply_aux_settings,
        )
        dialog.setModal(False)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda _obj=None: setattr(self, "_glossary_builder_dialog", None))
        self._glossary_builder_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _open_calibration_audit_dialog(self) -> None:
        if self._calibration_dialog is not None and self._calibration_dialog.isVisible():
            self._calibration_dialog.raise_()
            self._calibration_dialog.activateWindow()
            return
        dialog = QtCalibrationAuditDialog(
            parent=self,
            settings=self._defaults,
            build_config_callback=self._build_config,
            save_settings_callback=self._apply_aux_settings,
        )
        dialog.setModal(False)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda _obj=None: setattr(self, "_calibration_dialog", None))
        self._calibration_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _set_details_visible(self, visible: bool) -> None:
        self.details_card.setVisible(visible)
        self.log_text.setVisible(visible)
        self.details_btn.setArrowType(Qt.ArrowType.DownArrow if visible else Qt.ArrowType.RightArrow)
        self.details_btn.setText("Hide details" if visible else "Show details")
        self._refresh_canvas()

    def _set_adv_visible(self, visible: bool) -> None:
        self.show_adv.setArrowType(Qt.ArrowType.DownArrow if visible else Qt.ArrowType.RightArrow)
        self.show_adv.setChecked(visible)
        self.adv_frame.setVisible(visible)
        self._refresh_canvas()

    def _set_advisor_recommendation(self, recommendation: dict[str, Any] | None) -> None:
        self._advisor_recommendation = dict(recommendation) if isinstance(recommendation, dict) else None
        self._advisor_recommendation_applied = None
        self._advisor_override_ocr_mode = None
        self._advisor_override_image_mode = None
        self._refresh_advisor_banner()

    def _refresh_advisor_banner(self) -> None:
        recommendation = self._advisor_recommendation if isinstance(self._advisor_recommendation, dict) else None
        frame = getattr(self, "advisor_frame", None)
        label = getattr(self, "advisor_label", None)
        apply_btn = getattr(self, "advisor_apply_btn", None)
        ignore_btn = getattr(self, "advisor_ignore_btn", None)
        if frame is None or label is None or apply_btn is None or ignore_btn is None:
            return

        if recommendation is None:
            frame.setVisible(False)
            label.setText("")
            apply_btn.setEnabled(False)
            ignore_btn.setEnabled(False)
            return

        rec_ocr = _normalized_mode_or_none(recommendation.get("recommended_ocr_mode")) or "auto"
        rec_image = _normalized_mode_or_none(recommendation.get("recommended_image_mode")) or "auto"
        track = str(recommendation.get("advisor_track", "enfr") or "enfr").strip().lower()
        confidence = _coerce_float_or_none(recommendation.get("confidence"))
        confidence_text = f"{confidence:.2f}" if confidence is not None else "n/a"
        status_text = "pending"
        if self._advisor_recommendation_applied is True:
            status_text = "applied"
        elif self._advisor_recommendation_applied is False:
            status_text = "ignored"
        label.setText(
            f"Track {track.upper()} recommends OCR={rec_ocr}, Images={rec_image}, "
            f"confidence={confidence_text} ({status_text})."
        )
        frame.setVisible(True)
        can_choose = (not self._busy) and (self._advisor_recommendation_applied is None)
        apply_btn.setEnabled(can_choose)
        ignore_btn.setEnabled(can_choose)
        self._refresh_canvas()

    def _apply_advisor_recommendation(self) -> None:
        recommendation = self._advisor_recommendation if isinstance(self._advisor_recommendation, dict) else None
        if recommendation is None:
            return
        rec_ocr = _normalized_mode_or_none(recommendation.get("recommended_ocr_mode"))
        rec_image = _normalized_mode_or_none(recommendation.get("recommended_image_mode"))
        if rec_ocr is None or rec_image is None:
            QMessageBox.warning(self, "Advisor", "Recommendation is incomplete. Run Analyze again.")
            return
        self._advisor_recommendation_applied = True
        self._advisor_override_ocr_mode = rec_ocr
        self._advisor_override_image_mode = rec_image
        self._append_log(
            "Advisor applied for next run only: "
            f"ocr_mode={rec_ocr}, image_mode={rec_image}"
        )
        self._refresh_advisor_banner()
        self._update_controls()

    def _ignore_advisor_recommendation(self) -> None:
        recommendation = self._advisor_recommendation if isinstance(self._advisor_recommendation, dict) else None
        if recommendation is None:
            return
        self._advisor_recommendation_applied = False
        self._advisor_override_ocr_mode = None
        self._advisor_override_image_mode = None
        self._append_log("Advisor recommendation ignored for next run.")
        self._refresh_advisor_banner()
        self._update_controls()

    def _consume_advisor_choice(self) -> None:
        self._advisor_recommendation_applied = None
        self._advisor_override_ocr_mode = None
        self._advisor_override_image_mode = None
        self._refresh_advisor_banner()

    def _on_form_changed(self) -> None:
        self._schedule_save_settings()
        refresh_lang_badge = getattr(self, "_refresh_lang_badge", None)
        if callable(refresh_lang_badge):
            refresh_lang_badge()
        self._refresh_page_count()
        self._update_controls()

    def _schedule_save_settings(self) -> None:
        self._settings_save_timer.start()

    def _refresh_canvas(self) -> None:
        central = self.centralWidget()
        if central is not None:
            central.update()

    def _refresh_page_count(self) -> None:
        pdf_text = self.pdf_edit.text().strip()
        if pdf_text == self._last_page_path:
            return
        self._last_page_path = pdf_text
        if not pdf_text:
            self.pages_label.setText("Pages: -")
            self._refresh_dashboard_counters()
            return
        pdf_path = Path(pdf_text).expanduser().resolve()
        if not pdf_path.exists() or not pdf_path.is_file():
            self.pages_label.setText("Pages: -")
            self._refresh_dashboard_counters()
            return
        try:
            if not is_supported_source_file(pdf_path):
                self.pages_label.setText("Pages: ?")
            else:
                self.pages_label.setText(f"Pages: {get_source_page_count(pdf_path)}")
        except Exception:
            self.pages_label.setText("Pages: ?")
        self._refresh_dashboard_counters()
    def _pick_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select source file", "", SOURCE_FILE_DIALOG_FILTER)
        if path:
            self.pdf_edit.setText(path)

    def _pick_outdir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select output folder")
        if path:
            self.outdir_edit.setText(path)

    def _pick_context(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select context file", "", "Text Files (*.txt);;All Files (*.*)")
        if path:
            self.context_file_edit.setText(path)

    def _pick_queue_manifest(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select queue manifest",
            "",
            "Queue Manifests (*.json *.jsonl);;JSON (*.json);;JSONL (*.jsonl);;All Files (*.*)",
        )
        if path:
            self.queue_manifest_edit.setText(path)

    @staticmethod
    def _build_queue_job_config_from_base(base_config: RunConfig, job_payload: dict[str, Any]) -> RunConfig:
        pdf_value = str(job_payload.get("pdf", job_payload.get("pdf_path", "")) or "").strip()
        if pdf_value == "":
            raise ValueError("Queue job is missing required field: pdf")
        lang_value = str(job_payload.get("lang", base_config.target_lang.value) or "").strip().upper()
        if lang_value not in {"EN", "FR", "AR"}:
            raise ValueError(f"Queue job has invalid lang: {lang_value}")
        outdir_value = str(
            job_payload.get("outdir", job_payload.get("output_dir", str(base_config.output_dir)))
            or ""
        ).strip()
        if outdir_value == "":
            raise ValueError("Queue job is missing required field: outdir/output_dir")

        config = replace(
            base_config,
            pdf_path=Path(pdf_value).expanduser().resolve(),
            output_dir=require_writable_output_dir_text(outdir_value),
            target_lang=TargetLang(lang_value),
        )
        start_page = _coerce_int_or_none(job_payload.get("start_page"))
        end_page = _coerce_int_or_none(job_payload.get("end_page"))
        max_pages = _coerce_int_or_none(job_payload.get("max_pages"))
        workers = _coerce_int_or_none(job_payload.get("workers"))
        if start_page is not None:
            if start_page <= 0:
                raise ValueError(f"Queue job start_page must be >= 1 (job pdf={pdf_value}).")
            config = replace(config, start_page=int(start_page))
        if end_page is not None:
            if end_page <= 0:
                raise ValueError(f"Queue job end_page must be >= 1 (job pdf={pdf_value}).")
            config = replace(config, end_page=int(end_page))
        if max_pages is not None:
            if max_pages <= 0:
                raise ValueError(f"Queue job max_pages must be >= 1 (job pdf={pdf_value}).")
            config = replace(config, max_pages=int(max_pages))
        if workers is not None:
            config = replace(config, workers=max(1, min(6, int(workers))))

        image_override = _normalized_mode_or_none(job_payload.get("image_mode", job_payload.get("images")))
        if image_override is not None:
            config = replace(config, image_mode=parse_image_mode(image_override))
        ocr_override = _normalized_mode_or_none(job_payload.get("ocr_mode"))
        if ocr_override is not None:
            config = replace(config, ocr_mode=parse_ocr_mode(ocr_override))
        ocr_engine_override = str(job_payload.get("ocr_engine", "") or "").strip().lower()
        if ocr_engine_override in {"local", "local_then_api", "api"}:
            config = replace(config, ocr_engine=parse_ocr_engine_policy(ocr_engine_override))
        resume_override = _coerce_bool_or_none(job_payload.get("resume"))
        if resume_override is not None:
            config = replace(config, resume=bool(resume_override))
        page_breaks_override = _coerce_bool_or_none(job_payload.get("page_breaks"))
        if page_breaks_override is not None:
            config = replace(config, page_breaks=bool(page_breaks_override))
        keep_override = _coerce_bool_or_none(job_payload.get("keep_intermediates"))
        if keep_override is not None:
            config = replace(config, keep_intermediates=bool(keep_override))

        return config

    @staticmethod
    def _derive_queue_base_inputs(
        *,
        jobs: list[dict[str, Any]],
        current_pdf: str,
        current_outdir: str,
        current_lang: str,
    ) -> tuple[str, str, str]:
        pdf_value = current_pdf.strip()
        outdir_value = current_outdir.strip()
        lang_value = current_lang.strip().upper()
        for row in jobs:
            payload = row.get("payload")
            if not isinstance(payload, dict):
                continue
            if pdf_value == "":
                pdf_value = str(payload.get("pdf", payload.get("pdf_path", "")) or "").strip()
            if outdir_value == "":
                outdir_value = str(payload.get("outdir", payload.get("output_dir", "")) or "").strip()
            if lang_value not in {"EN", "FR", "AR"}:
                lang_value = str(payload.get("lang", "") or "").strip().upper()
            if pdf_value != "" and outdir_value != "" and lang_value in {"EN", "FR", "AR"}:
                break
        if lang_value not in {"EN", "FR", "AR"}:
            lang_value = "EN"
        return pdf_value, outdir_value, lang_value

    def _append_log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.appendPlainText(f"[{stamp}] {message}")
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
        processing_match = _PROCESSING_PAGE_LOG_RE.search(message)
        if processing_match:
            self._active_request_page = int(processing_match.group("page"))
        budget_match = _REQUEST_BUDGET_LOG_RE.search(message)
        if budget_match:
            self._active_request_page = int(budget_match.group("page"))
            self._active_request_type = str(budget_match.group("request_type"))
            self._active_request_budget_seconds = float(budget_match.group("budget"))
            self._active_request_started_at = time.perf_counter()
        terminal_match = _PAGE_TERMINAL_LOG_RE.search(message)
        if terminal_match:
            self._clear_active_request_tracking()
        if bool(self._defaults.get("diagnostics_verbose_metadata_logs", False)):
            try:
                self._metadata_log_file.parent.mkdir(parents=True, exist_ok=True)
                with self._metadata_log_file.open("a", encoding="utf-8") as fh:
                    fh.write(f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n")
            except Exception:
                pass

    def _clear_active_request_tracking(self) -> None:
        self._active_request_page = None
        self._active_request_type = None
        self._active_request_budget_seconds = None
        self._active_request_started_at = None

    def _clear_cancel_wait_state(self) -> None:
        self._cancel_wait_started_at = None
        if self._cancel_wait_timer.isActive():
            self._cancel_wait_timer.stop()

    def _refresh_cancel_wait_status(self) -> None:
        if not self._cancel_pending:
            self._clear_cancel_wait_state()
            return
        now = time.perf_counter()
        cancel_wait_started = self._cancel_wait_started_at or now
        waited_seconds = max(0.0, now - cancel_wait_started)
        page_text = str(self._active_request_page) if self._active_request_page is not None else "?"
        if self._active_request_budget_seconds is not None and self._active_request_started_at is not None:
            remaining_seconds = max(
                0.0,
                float(self._active_request_budget_seconds) - max(0.0, now - self._active_request_started_at),
            )
            remaining_text = self._format_eta_seconds(remaining_seconds)
        else:
            remaining_text = "--"
        status = (
            f"Cancelling... page {page_text} | "
            f"waited {self._format_eta_seconds(waited_seconds)} | "
            f"remaining <= {remaining_text}"
        )
        self.status_label.setText(status)
        self.header_status_label.setText("Cancelling...")
        self._dashboard_snapshot.current_task = status
        if self._queue_total_jobs > 0:
            self.queue_status_label.setText(f"Queue: cancelling page {page_text} | remaining <= {remaining_text}")
        else:
            self.queue_status_label.setText(f"Cancel wait: page {page_text} | remaining <= {remaining_text}")
        self._refresh_dashboard_counters()

    def _reset_live_counters(self) -> None:
        self._progress_done_pages = 0
        self._progress_total_pages = 0
        self._image_pages_seen.clear()
        self._retry_pages_seen.clear()
        self._queue_total_jobs = 0
        self._queue_status_by_job_id = {}
        self._clear_active_request_tracking()
        self._clear_cancel_wait_state()
        self._dashboard_snapshot = _DashboardSnapshot()
        self._update_live_counters()

    def _update_live_counters(self) -> None:
        self.live_counters_label.setText(
            "Done "
            f"{self._progress_done_pages}/{self._progress_total_pages} | "
            f"Images {len(self._image_pages_seen)} | Retries {len(self._retry_pages_seen)}"
        )
        self._refresh_dashboard_counters()

    def _warn_fixed_xhigh_for_enfr(self) -> str:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("Cost/Time warning")
        dialog.setText("xhigh can multiply cost and time; recommended: fixed high.")
        proceed_btn = dialog.addButton("Proceed", QMessageBox.ButtonRole.AcceptRole)
        switch_btn = dialog.addButton("Switch to fixed high", QMessageBox.ButtonRole.ActionRole)
        cancel_btn = dialog.addButton(QMessageBox.StandardButton.Cancel)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked is proceed_btn:
            return "proceed"
        if clicked is switch_btn:
            return "switch"
        if clicked is cancel_btn:
            return "cancel"
        return "cancel"

    def _build_config(
        self,
        *,
        pdf_override: str | None = None,
        outdir_override: str | None = None,
        lang_override: str | None = None,
        start_page_override: int | None = None,
    ) -> RunConfig:
        pdf_text = pdf_override.strip() if isinstance(pdf_override, str) else self.pdf_edit.text().strip()
        outdir_text = (
            outdir_override.strip()
            if isinstance(outdir_override, str)
            else self.outdir_edit.text().strip()
        )
        if not pdf_text:
            raise ValueError("Source file path is required.")
        if not outdir_text:
            raise ValueError("Output folder is required.")
        pdf = Path(pdf_text).expanduser().resolve()
        if not pdf.exists() or not pdf.is_file():
            raise ValueError("Source file must exist.")
        if not is_supported_source_file(pdf):
            raise ValueError("Source file must be a PDF or supported image.")
        outdir = require_writable_output_dir_text(outdir_text)

        def opt_int(value: str, field: str) -> int | None:
            v = value.strip()
            if not v:
                return None
            try:
                return int(v)
            except ValueError as exc:
                raise ValueError(f"{field} must be an integer.") from exc

        if start_page_override is None:
            start_text = self.start_edit.text().strip() or "1"
            try:
                start_page = int(start_text)
            except ValueError as exc:
                raise ValueError("Start page must be an integer.") from exc
        else:
            start_page = int(start_page_override)
            if start_page <= 0:
                raise ValueError("Start page must be >= 1.")

        context_file_text = self.context_file_edit.text().strip()
        context_file = Path(context_file_text).expanduser().resolve() if context_file_text else None
        glossary_file_text = str(self._defaults.get("glossary_file_path", "") or "").strip()
        glossary_file = Path(glossary_file_text).expanduser().resolve() if glossary_file_text else None
        selected_image_mode = self.images_combo.currentText()
        selected_ocr_mode = self.ocr_mode_combo.currentText()
        advisor_applied = getattr(self, "_advisor_recommendation_applied", None)
        advisor_override_image = getattr(self, "_advisor_override_image_mode", None)
        advisor_override_ocr = getattr(self, "_advisor_override_ocr_mode", None)
        advisor_payload = getattr(self, "_advisor_recommendation", None)
        if advisor_applied is True:
            if advisor_override_image in {"off", "auto", "always"}:
                selected_image_mode = str(advisor_override_image)
            if advisor_override_ocr in {"off", "auto", "always"}:
                selected_ocr_mode = str(advisor_override_ocr)

        return RunConfig(
            pdf_path=pdf,
            output_dir=outdir,
            target_lang=TargetLang(
                (lang_override.strip() if isinstance(lang_override, str) else self.lang_combo.currentText().strip()).upper()
            ),
            effort=parse_effort(self.effort_combo.currentText()),
            effort_policy=parse_effort_policy(self.effort_policy_combo.currentText()),
            allow_xhigh_escalation=bool(self._defaults.get("allow_xhigh_escalation", False)),
            image_mode=parse_image_mode(selected_image_mode),
            start_page=start_page,
            end_page=opt_int(self.end_edit.text(), "End page"),
            max_pages=opt_int(self.max_edit.text(), "Max pages"),
            workers=max(1, min(6, int(self.workers_spin.value()))),
            resume=self.resume_check.isChecked(),
            page_breaks=self.breaks_check.isChecked(),
            keep_intermediates=self.keep_check.isChecked(),
            ocr_mode=parse_ocr_mode(selected_ocr_mode),
            ocr_engine=parse_ocr_engine_policy(self.ocr_engine_combo.currentText()),
            ocr_api_provider=normalize_ocr_api_provider(
                self._defaults.get("ocr_api_provider", self._defaults.get("ocr_api_provider_default", "openai"))
            ),
            ocr_api_base_url=str(self._defaults.get("ocr_api_base_url", "") or "") or None,
            ocr_api_model=str(self._defaults.get("ocr_api_model", "") or "") or None,
            ocr_api_key_env_name=str(
                self._defaults.get(
                    "ocr_api_key_env_name",
                    default_ocr_api_env_name(
                        normalize_ocr_api_provider(
                            self._defaults.get("ocr_api_provider", self._defaults.get("ocr_api_provider_default", "openai"))
                        )
                    ),
                )
                or default_ocr_api_env_name(
                    normalize_ocr_api_provider(
                        self._defaults.get("ocr_api_provider", self._defaults.get("ocr_api_provider_default", "openai"))
                    )
                )
            ),
            context_file=context_file,
            context_text=self.context_text.toPlainText().strip() or None,
            glossary_file=glossary_file,
            diagnostics_admin_mode=bool(self._defaults.get("diagnostics_admin_mode", True)),
            diagnostics_include_sanitized_snippets=bool(
                self._defaults.get("diagnostics_include_sanitized_snippets", False)
            ),
            advisor_recommendation_applied=(
                advisor_applied
                if isinstance(advisor_applied, bool)
                else None
            ),
            advisor_recommendation=(
                dict(advisor_payload)
                if isinstance(advisor_payload, dict)
                else None
            ),
        )

    def _can_start(self) -> bool:
        if self._busy:
            return False
        pdf = self.pdf_edit.text().strip()
        outdir = self.outdir_edit.text().strip()
        if not pdf or not outdir:
            return False
        p = Path(pdf).expanduser().resolve()
        if not p.exists() or not p.is_file():
            return False
        try:
            require_writable_output_dir_text(outdir)
        except ValueError:
            return False
        return True

    def _rebuild_pages_dir(self) -> Path | None:
        pdf_text = self.pdf_edit.text().strip()
        outdir_text = self.outdir_edit.text().strip()
        if not pdf_text or not outdir_text:
            return None

        outdir = Path(outdir_text).expanduser().resolve()
        if not outdir.exists() or not outdir.is_dir():
            return None
        pdf = Path(pdf_text).expanduser().resolve()
        try:
            lang = TargetLang(self.lang_combo.currentText().strip())
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

    def _update_controls(self) -> None:
        can_start = self._can_start()
        queue_manifest_edit = getattr(self, "queue_manifest_edit", None)
        queue_manifest_text = (
            queue_manifest_edit.text().strip()
            if queue_manifest_edit is not None and hasattr(queue_manifest_edit, "text")
            else ""
        )
        queue_manifest_path = Path(queue_manifest_text).expanduser().resolve() if queue_manifest_text else None
        can_start_queue = (
            (not self._busy)
            and queue_manifest_path is not None
            and queue_manifest_path.exists()
            and queue_manifest_path.is_file()
        )
        self.translate_btn.setEnabled(can_start)
        self.analyze_btn.setEnabled(can_start and not self._busy)
        run_queue_btn = getattr(self, "run_queue_btn", None)
        if run_queue_btn is not None:
            run_queue_btn.setEnabled(can_start_queue)
        self.cancel_btn.setEnabled(self._running and not self._cancel_pending)
        self.new_btn.setEnabled(not self._busy)
        self.partial_btn.setEnabled((not self._busy) and self._can_export_partial and self._last_workflow is not None)
        self.rebuild_btn.setEnabled((not self._busy) and self._has_rebuildable_pages())
        can_open = (
            (not self._busy)
            and self._last_output_docx is not None
            and self._last_output_docx.exists()
            and self._last_output_docx.stat().st_size > 0
        )
        self.open_btn.setEnabled(can_open)
        can_report = False
        if self._running:
            can_report = self._resolve_report_run_dir() is not None
        elif not self._busy:
            can_report = self._resolve_report_run_dir() is not None
        self.report_btn.setEnabled(can_report)
        can_review_queue = (not self._busy) and (
            bool(self._last_review_queue)
            or self._resolve_report_run_dir() is not None
        )
        self.review_queue_btn.setEnabled(can_review_queue)
        self.save_joblog_btn.setEnabled((not self._busy) and (self._last_joblog_seed is not None))
        self.open_joblog_btn.setEnabled(not self._busy)
        more_btn = getattr(self, "more_btn", None)
        if more_btn is not None:
            more_btn.setEnabled(not self._busy)

        self._set_menu_enabled("open_output_folder", can_open)
        self._set_menu_enabled("export_partial", (not self._busy) and self._can_export_partial)
        self._set_menu_enabled("review_queue", can_review_queue)
        self._set_menu_enabled("save_joblog", (not self._busy) and (self._last_joblog_seed is not None))
        self._set_menu_enabled("job_log", not self._busy)
        if not self._simple_mode:
            self._set_menu_enabled("glossary_builder", not self._busy)
            self._set_menu_enabled("calibration_audit", not self._busy)
        self._set_menu_enabled("settings", not self._busy)
        overflow_actions = getattr(self, "_overflow_menu_actions", {})
        if overflow_actions:
            overflow_actions["open_output_folder"].setEnabled(can_open)
            overflow_actions["export_partial"].setEnabled((not self._busy) and self._can_export_partial)
            overflow_actions["rebuild_docx"].setEnabled((not self._busy) and self._has_rebuildable_pages())
            overflow_actions["run_report"].setEnabled(can_report)
            overflow_actions["job_log"].setEnabled(not self._busy)
        refresh_advisor = getattr(self, "_refresh_advisor_banner", None)
        if callable(refresh_advisor):
            refresh_advisor()

    def _set_busy(self, busy: bool, *, translation: bool) -> None:
        self._busy = busy
        self._running = busy and translation
        if not busy:
            self._cancel_pending = False
            self._clear_cancel_wait_state()
            self._clear_active_request_tracking()
            self._restore_transient_safe_profile_if_needed()
        advisor_apply_btn = getattr(self, "advisor_apply_btn", None)
        advisor_ignore_btn = getattr(self, "advisor_ignore_btn", None)
        queue_manifest_edit = getattr(self, "queue_manifest_edit", None)
        queue_manifest_btn = getattr(self, "queue_manifest_btn", None)
        queue_rerun_failed_only_check = getattr(self, "queue_rerun_failed_only_check", None)
        for w in (
            self.pdf_edit, self.pdf_btn, self.lang_combo, self.outdir_edit, self.outdir_btn, self.show_adv,
            self.effort_policy_combo, self.effort_combo, self.images_combo, self.ocr_mode_combo, self.ocr_engine_combo,
            self.start_edit, self.end_edit, self.max_edit, self.workers_spin,
            self.resume_check, self.breaks_check, self.keep_check,
            self.context_file_edit, self.context_btn, self.context_text,
            queue_manifest_edit, queue_manifest_btn, queue_rerun_failed_only_check,
            advisor_apply_btn, advisor_ignore_btn,
        ):
            if w is not None:
                w.setEnabled(not busy)
        self._update_controls()

    def _start(self) -> None:
        if self._busy:
            return
        config = self._resolve_translation_config()
        if config is None:
            return
        self._start_translation_run(
            config=config,
            clear_gmail_batch_session=True,
            consume_advisor_choice=True,
            status_text="Starting...",
            header_status_text="Starting...",
            dashboard_task="Starting...",
        )

    def _start_queue(self) -> None:
        if self._busy:
            return
        manifest_text = self.queue_manifest_edit.text().strip()
        if manifest_text == "":
            QMessageBox.information(self, "Run Queue", "Select a queue manifest first.")
            return
        manifest_path = Path(manifest_text).expanduser().resolve()
        if not manifest_path.exists() or not manifest_path.is_file():
            QMessageBox.critical(self, "Run Queue", f"Queue manifest not found:\n{manifest_path}")
            return

        try:
            manifest_jobs = parse_queue_manifest(manifest_path)
            queue_pdf, queue_outdir, queue_lang = self._derive_queue_base_inputs(
                jobs=manifest_jobs,
                current_pdf=self.pdf_edit.text(),
                current_outdir=self.outdir_edit.text(),
                current_lang=self.lang_combo.currentText(),
            )
            base_config = self._build_config(
                pdf_override=queue_pdf,
                outdir_override=queue_outdir,
                lang_override=queue_lang,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Invalid configuration", str(exc))
            return

        base_config = replace(
            base_config,
            advisor_recommendation_applied=None,
            advisor_recommendation=None,
        )
        base_config = self._warn_ocr_api_only_if_needed(
            base_config,
            rebuild_config=lambda: self._build_config(
                pdf_override=queue_pdf,
                outdir_override=queue_outdir,
                lang_override=queue_lang,
            ),
        )
        if base_config is None:
            return
        rerun_failed_only = self.queue_rerun_failed_only_check.isChecked()
        self._save_settings()
        self._consume_advisor_choice()
        if self._review_queue_dialog is not None and self._review_queue_dialog.isVisible():
            self._review_queue_dialog.close()
            self._review_queue_dialog = None
        self._clear_gmail_batch_session()
        self._last_gmail_message_load_result = None
        self._last_summary = None
        self._last_run_report_path = None
        self._last_queue_summary_path = None
        self._last_run_dir = None
        self._last_output_docx = None
        self._last_run_config = base_config
        self._last_joblog_seed = None
        self._last_review_queue = []
        self._last_workflow = None
        self._can_export_partial = False
        self._queue_status_rows = []
        self.final_docx_edit.clear()
        self.progress.setValue(0)
        self.page_label.setText("Queue: -")
        self.status_label.setText("Queue starting...")
        self.header_status_label.setText("Queue starting...")
        self.queue_status_label.setText("Queue: pending")
        self._dashboard_error_count = 0
        self._dashboard_error_retry_count = 0
        self._dashboard_eta_text = "--"
        self._reset_live_counters()
        self._queue_total_jobs = len(manifest_jobs)
        self._queue_status_by_job_id = {}
        self._run_started_at = time.perf_counter()
        self._dashboard_snapshot.pages_title = "Jobs"
        self._dashboard_snapshot.images_title = "Skipped"
        self._dashboard_snapshot.errors_title = "Failed"
        self._dashboard_snapshot.pages_total = len(manifest_jobs)
        self._apply_dashboard_snapshot()

        max_retries = int(self._defaults.get("perf_max_transport_retries", 4) or 4)
        backoff_cap = float(self._defaults.get("perf_backoff_cap_seconds", 12.0) or 12.0)

        thread = QThread(self)
        worker = QueueRunWorker(
            manifest_path=manifest_path,
            rerun_failed_only=rerun_failed_only,
            build_config=lambda payload: self._build_queue_job_config_from_base(base_config, payload),
            max_transport_retries=max_retries,
            backoff_cap_seconds=backoff_cap,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.log.connect(self._append_log)
        worker.queue_status.connect(self._on_queue_status)
        worker.finished.connect(self._on_queue_finished)
        worker.error.connect(self._on_queue_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(self._cleanup_worker)
        self.request_cancel.connect(worker.cancel, Qt.ConnectionType.QueuedConnection)

        self._worker_thread = thread
        self._worker = worker
        self._set_busy(True, translation=True)
        thread.start()

    def _on_queue_status(self, row_obj: object) -> None:
        if not isinstance(row_obj, dict):
            return
        row = dict(row_obj)
        self._queue_status_rows.append(row)
        status = str(row.get("status", "") or "").strip().lower()
        job_id = str(row.get("job_id", "") or "").strip() or "unknown"
        self._queue_status_by_job_id[job_id] = row
        self.queue_status_label.setText(f"Queue: {job_id} -> {status or 'pending'}")
        if status == "running":
            self.status_label.setText(f"Queue running: {job_id}")
            self.header_status_label.setText("Queue running")
        elif status in {"done", "failed", "skipped"}:
            self._append_log(f"Queue status: {job_id} -> {status}")
        if status == "failed":
            self._dashboard_error_count = max(1, self._dashboard_error_count)
        if self._queue_total_jobs > 0:
            counts = {"done": 0, "failed": 0, "skipped": 0}
            for item in self._queue_status_by_job_id.values():
                item_status = str(item.get("status", "") or "").strip().lower()
                if item_status in counts:
                    counts[item_status] += 1
            completed_jobs = counts["done"] + counts["failed"] + counts["skipped"]
            self.progress.setValue(int(round((completed_jobs / float(self._queue_total_jobs)) * 100.0)))
            self._dashboard_snapshot.pages_done = completed_jobs
            self._dashboard_snapshot.pages_total = self._queue_total_jobs
            self._dashboard_snapshot.images_done = counts["skipped"]
            self._dashboard_snapshot.images_total = self._queue_total_jobs
            self._dashboard_snapshot.errors_count = counts["failed"]
        self._refresh_dashboard_counters()

    def _on_queue_finished(self, summary_obj: object) -> None:
        self._set_busy(False, translation=False)
        self._run_started_at = None
        if not isinstance(summary_obj, QueueRunSummary):
            self.status_label.setText("Queue failed")
            self.header_status_label.setText("Queue failed")
            self.queue_status_label.setText("Queue: failed")
            self._dashboard_error_count = max(1, self._dashboard_error_count)
            self._refresh_dashboard_counters()
            QMessageBox.critical(self, "Queue failed", "Queue worker returned an invalid summary.")
            self._update_controls()
            return

        summary = summary_obj
        self._last_queue_summary_path = summary.queue_summary_path.expanduser().resolve()
        self._append_log(f"Queue summary: {self._last_queue_summary_path}")
        self._append_log(f"Queue checkpoint: {summary.checkpoint_path}")
        for row in reversed(summary.jobs):
            run_dir_text = str(row.get("run_dir", "") or "").strip()
            if run_dir_text == "":
                continue
            candidate = Path(run_dir_text).expanduser().resolve()
            self._last_run_dir = candidate
            break

        queue_result_text = (
            f"Queue complete.\n\nTotal jobs: {summary.total_jobs}\n"
            f"Done: {summary.done_jobs}\nFailed: {summary.failed_jobs}\nSkipped: {summary.skipped_jobs}\n\n"
            f"Summary: {summary.queue_summary_path}"
        )
        if summary.success:
            self.status_label.setText("Queue completed")
            self.header_status_label.setText("Queue completed")
            self.queue_status_label.setText(
                f"Queue: done={summary.done_jobs} failed={summary.failed_jobs} skipped={summary.skipped_jobs}"
            )
            self._dashboard_error_count = 0
            QMessageBox.information(self, "Queue complete", queue_result_text)
        else:
            self.status_label.setText("Queue completed with failures")
            self.header_status_label.setText("Queue warnings")
            self.queue_status_label.setText(
                f"Queue: done={summary.done_jobs} failed={summary.failed_jobs} skipped={summary.skipped_jobs}"
            )
            self._dashboard_error_count = max(1, summary.failed_jobs)
            QMessageBox.warning(self, "Queue completed with failures", queue_result_text)
        self.progress.setValue(100)
        self._dashboard_snapshot.pages_done = summary.total_jobs
        self._dashboard_snapshot.pages_total = summary.total_jobs
        self._dashboard_snapshot.images_done = summary.skipped_jobs
        self._dashboard_snapshot.images_total = summary.total_jobs
        self._dashboard_snapshot.errors_count = summary.failed_jobs
        self._refresh_dashboard_counters()
        self._update_controls()

    def _on_queue_error(self, message: str) -> None:
        self._set_busy(False, translation=False)
        self._run_started_at = None
        self.status_label.setText("Queue failed")
        self.header_status_label.setText("Queue failed")
        self.queue_status_label.setText("Queue: failed")
        self._dashboard_error_count = max(1, self._dashboard_error_count)
        self._refresh_dashboard_counters()
        self._append_log(f"Queue failed: {message}")
        QMessageBox.critical(self, "Queue failed", message)

    def _start_analyze(self) -> None:
        if self._busy:
            return
        try:
            config = self._build_config()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Invalid configuration", str(exc))
            return

        self._save_settings()
        self._set_advisor_recommendation(None)
        if self._review_queue_dialog is not None and self._review_queue_dialog.isVisible():
            self._review_queue_dialog.close()
            self._review_queue_dialog = None
        self._clear_gmail_batch_session()
        self._last_gmail_message_load_result = None
        self._last_summary = None
        self._last_run_report_path = None
        self._last_queue_summary_path = None
        self._last_output_docx = None
        self._last_joblog_seed = None
        self._last_review_queue = []
        self.status_label.setText("Analyzing...")
        self.header_status_label.setText("Analyzing...")
        self.queue_status_label.setText("Queue: idle")
        self.progress.setValue(0)
        self.page_label.setText("Page: -/-")
        self._dashboard_error_count = 0
        self._dashboard_error_retry_count = 0
        self._dashboard_eta_text = "--"
        self._run_started_at = time.perf_counter()
        self._reset_live_counters()

        thread = QThread(self)
        worker = AnalyzeWorker(config=config)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.log.connect(self._append_log)
        worker.finished.connect(self._on_analyze_finished)
        worker.error.connect(self._on_analyze_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(self._cleanup_worker)

        self._worker_thread = thread
        self._worker = worker
        self._set_busy(True, translation=False)
        thread.start()

    def _on_progress(self, selected_index: int, selected_total: int, real_page: int, status: str, image_used: bool, retry_used: bool) -> None:
        if selected_total > 0:
            self.progress.setValue(max(0, min(100, int((float(selected_index) / float(selected_total)) * 100.0))))
        self._progress_done_pages = max(0, int(selected_index))
        self._progress_total_pages = max(0, int(selected_total))
        if real_page > 0:
            extra = []
            if image_used:
                extra.append("image")
                self._image_pages_seen.add(real_page)
            if retry_used:
                extra.append("retry")
                self._retry_pages_seen.add(real_page)
            suffix = f" [{', '.join(extra)}]" if extra else ""
            self.page_label.setText(f"Page {real_page} ({selected_index}/{selected_total}){suffix}")
        else:
            self.page_label.setText(f"Progress: {selected_index}/{selected_total}")
        self._update_live_counters()
        self.status_label.setText(status)
        self.header_status_label.setText(status)
        self._dashboard_snapshot.current_task = status
        self._refresh_dashboard_counters()

    def _on_finished(self, summary_obj: object) -> None:
        summary = summary_obj if isinstance(summary_obj, RunSummary) else None
        gmail_batch_active = self._has_active_gmail_batch()
        gmail_batch_attachment = self._current_gmail_batch_attachment() if gmail_batch_active else None
        gmail_batch_index = self._gmail_batch_current_index if gmail_batch_active else None
        gmail_batch_total = (
            len(self._gmail_batch_session.downloaded_attachments)
            if self._gmail_batch_session is not None
            else 0
        )
        if self._worker is not None and hasattr(self._worker, "workflow"):
            self._last_workflow = getattr(self._worker, "workflow")
        self._set_busy(False, translation=False)
        self._run_started_at = None
        self.queue_status_label.setText("Queue: idle")
        if summary is None:
            self.status_label.setText("Run finished with invalid summary")
            self.header_status_label.setText("Error")
            self._last_joblog_seed = None
            self._last_review_queue = []
            self._dashboard_error_count = max(1, self._dashboard_error_count)
            self._refresh_dashboard_counters()
            if gmail_batch_active:
                self._stop_gmail_batch(
                    status_text="Gmail batch stopped",
                    header_status_text="Gmail batch stopped",
                    log_message="Gmail batch stopped because the translation worker returned an invalid summary.",
                )
            return
        self._last_summary = summary
        self._last_run_dir = summary.run_dir
        self._last_run_report_path = summary.run_summary_path
        summary_path = summary.run_summary_path
        if summary_path is None:
            summary_path = summary.run_dir / "run_summary.json"
        self._last_review_queue = _load_review_queue_entries(summary_path.expanduser().resolve())
        if summary.success and summary.output_docx is not None:
            output = summary.output_docx.expanduser().resolve()
            last_run_config = getattr(self, "_last_run_config", None)
            requires_arabic_review = (
                last_run_config is not None
                and getattr(last_run_config, "target_lang", None) == TargetLang.AR
            )
            self._last_output_docx = output
            self.final_docx_edit.setText(str(output))
            self.status_label.setText("Completed")
            self.header_status_label.setText("Completed")
            self._append_log(f"Saved DOCX: {output}")
            if summary.run_summary_path is not None:
                self._append_log(f"Run report: {summary.run_summary_path}")
            self._prepare_joblog_seed(summary)
            if gmail_batch_active:
                if gmail_batch_attachment is None or gmail_batch_index is None:
                    self._stop_gmail_batch(
                        status_text="Gmail batch stopped",
                        header_status_text="Gmail batch stopped",
                        log_message="Gmail batch stopped because the current attachment context was lost.",
                        warning_message=(
                            "The Gmail batch could not continue because the active attachment context was lost."
                        ),
                    )
                else:
                    item_number = gmail_batch_index + 1
                    self._set_busy(True, translation=False)
                    if requires_arabic_review:
                        arabic_review_status = (
                            f"Arabic DOCX review {item_number}/{gmail_batch_total}: "
                            f"{gmail_batch_attachment.candidate.filename}"
                        )
                        self.status_label.setText(arabic_review_status)
                        self.header_status_label.setText("Arabic DOCX review")
                        self._dashboard_snapshot.current_task = arabic_review_status
                        reviewed = self._open_arabic_docx_review_dialog(
                            output_docx=output,
                            is_gmail_batch=True,
                            attachment_label=gmail_batch_attachment.candidate.filename,
                        )
                        if not reviewed:
                            self._stop_gmail_batch(
                                status_text="Gmail batch stopped",
                                header_status_text="Gmail batch stopped",
                                log_message=(
                                    "Gmail batch stopped because Arabic DOCX review was cancelled for "
                                    f"{gmail_batch_attachment.candidate.filename}."
                                ),
                                information_message=(
                                    "The Gmail batch was stopped because the Arabic DOCX review "
                                    "was cancelled or closed before continuation."
                                ),
                            )
                            return
                    review_status = (
                        f"Gmail batch review {item_number}/{gmail_batch_total}: "
                        f"{gmail_batch_attachment.candidate.filename}"
                    )
                    self.status_label.setText(review_status)
                    self.header_status_label.setText("Gmail batch review")
                    self._dashboard_snapshot.current_task = review_status
                    saved_result = self._open_save_to_joblog_dialog(
                        allow_honorarios_export=False,
                    )
                    if saved_result is None:
                        self._stop_gmail_batch(
                            status_text="Gmail batch stopped",
                            header_status_text="Gmail batch stopped",
                            log_message=(
                                "Gmail batch stopped because Save to Job Log was cancelled for "
                                f"{gmail_batch_attachment.candidate.filename}."
                            ),
                            information_message=(
                                "The Gmail batch was stopped because Save to Job Log was cancelled "
                                "or closed without saving."
                            ),
                        )
                    else:
                        try:
                            consistent = self._record_gmail_batch_saved_result(
                                saved_result,
                                run_dir=summary.run_dir,
                            )
                        except ValueError as exc:
                            self._stop_gmail_batch(
                                status_text="Gmail batch stopped",
                                header_status_text="Gmail batch stopped",
                                log_message=(
                                    "Gmail batch stopped because the translated DOCX could not be "
                                    f"staged for draft attachments: {exc}"
                                ),
                                warning_message=str(exc),
                            )
                            return
                        self._append_log(
                            "Gmail batch saved item "
                            f"{item_number}/{gmail_batch_total}: "
                            f"{gmail_batch_attachment.candidate.filename} "
                            f"-> row {saved_result.row_id}"
                        )
                        if not consistent:
                            self._stop_gmail_batch(
                                status_text="Gmail batch stopped",
                                header_status_text="Gmail batch stopped",
                                log_message=(
                                    "Gmail batch stopped because confirmed case/court metadata "
                                    "no longer matches the earlier attachments."
                                ),
                                warning_message=(
                                    "Selected attachments did not resolve to the same confirmed "
                                    "case/court context. Split this reply into separate batches "
                                    "before continuing."
                                ),
                            )
                        else:
                            self._run_after_worker_cleanup(self._start_next_gmail_batch_translation)
            else:
                if requires_arabic_review:
                    reviewed = self._open_arabic_docx_review_dialog(
                        output_docx=output,
                        is_gmail_batch=False,
                    )
                    if reviewed:
                        self._open_save_to_joblog_dialog()
                    else:
                        self._append_log(
                            "Arabic DOCX review was closed before Save to Job Log opened."
                        )
                else:
                    self._show_saved_docx_dialog("Translation complete")
                    self._open_save_to_joblog_dialog()
            self._dashboard_error_count = 0
        else:
            self._last_output_docx = None
            self._last_joblog_seed = None
            self._append_log(f"Run failed: {summary.error}; failed_page={summary.failed_page}")
            if summary.run_summary_path is not None:
                self._append_log(f"Run report: {summary.run_summary_path}")
            self.status_label.setText(f"Failed ({summary.error})")
            self.header_status_label.setText("Failed")
            if summary.error == "docx_write_failed" and summary.attempted_output_docx is not None:
                self._append_log(f"DOCX save failed at: {summary.attempted_output_docx}")
            details = f"Run stopped at page {summary.failed_page}. Partial pages: {summary.completed_pages}"
            failure_context: dict[str, object] = {}
            if summary.run_summary_path is not None:
                failure_context = _load_run_failure_context(summary.run_summary_path.expanduser().resolve())
            suspected_cause = str(failure_context.get("suspected_cause", "") or "")
            halt_reason = str(failure_context.get("halt_reason", "") or "")
            request_type = str(failure_context.get("request_type", "") or "")
            request_timeout_budget_seconds = float(
                failure_context.get("request_timeout_budget_seconds", 0.0) or 0.0
            )
            request_elapsed_before_failure_seconds = float(
                failure_context.get("request_elapsed_before_failure_seconds", 0.0) or 0.0
            )
            cancel_requested_before_failure = bool(
                failure_context.get("cancel_requested_before_failure", False)
            )
            exception_class = str(failure_context.get("exception_class", "") or "")
            validator_defect_reason = str(failure_context.get("validator_defect_reason", "") or "")
            ar_violation_kind = str(failure_context.get("ar_violation_kind", "") or "")
            ar_violation_samples = [
                str(item)
                for item in failure_context.get("ar_violation_samples", [])
                if str(item or "").strip() != ""
            ] if isinstance(failure_context.get("ar_violation_samples"), list) else []
            if request_type:
                self._append_log(
                    "Failure context: "
                    f"request_type={request_type} "
                    f"deadline={request_timeout_budget_seconds:.1f}s "
                    f"elapsed={request_elapsed_before_failure_seconds:.3f}s "
                    f"cancel_requested={'yes' if cancel_requested_before_failure else 'no'}"
                )
            if suspected_cause or halt_reason or exception_class:
                self._append_log(
                    "Failure classification: "
                    f"suspected_cause={suspected_cause or 'unknown'} "
                    f"halt_reason={halt_reason or 'unknown'} "
                    f"exception_class={exception_class or 'unknown'}"
                )
            if validator_defect_reason or ar_violation_kind:
                self._append_log(
                    "Validator classification: "
                    f"reason={validator_defect_reason or 'unknown'} "
                    f"ar_violation_kind={ar_violation_kind or 'n/a'}"
                )
            if summary.error == "docx_write_failed" and summary.attempted_output_docx is not None:
                details = (
                    f"DOCX save failed at:\n{summary.attempted_output_docx}\n\n"
                    f"Partial pages: {summary.completed_pages}"
                )
            else:
                detail_lines = [details]
                if suspected_cause:
                    detail_lines.append(f"Suspected cause: {suspected_cause}")
                if halt_reason:
                    detail_lines.append(f"Halt reason: {halt_reason}")
                if validator_defect_reason:
                    detail_lines.append(f"Validator reason: {validator_defect_reason}")
                if ar_violation_kind:
                    detail_lines.append(f"Arabic violation: {ar_violation_kind}")
                if ar_violation_samples:
                    detail_lines.append(
                        "Arabic samples: " + "; ".join(ar_violation_samples[:3])
                    )
                if request_type:
                    detail_lines.append(f"Request type: {request_type}")
                if request_timeout_budget_seconds > 0.0:
                    detail_lines.append(f"Request deadline: {request_timeout_budget_seconds:.0f}s")
                if request_elapsed_before_failure_seconds > 0.0:
                    detail_lines.append(
                        f"Elapsed before failure: {request_elapsed_before_failure_seconds:.1f}s"
                    )
                if exception_class:
                    detail_lines.append(f"Failure class: {exception_class}")
                if request_type:
                    detail_lines.append(
                        "Cancel requested before failure: "
                        f"{'yes' if cancel_requested_before_failure else 'no'}"
                    )
                if summary.run_summary_path is not None:
                    detail_lines.append(f"Run report:\n{summary.run_summary_path}")
                details = "\n".join(detail_lines)
            QMessageBox.warning(self, "Translation stopped", details)
            if gmail_batch_active:
                batch_name = (
                    gmail_batch_attachment.candidate.filename
                    if gmail_batch_attachment is not None
                    else "the current attachment"
                )
                self._stop_gmail_batch(
                    status_text="Gmail batch stopped",
                    header_status_text="Gmail batch stopped",
                    log_message=f"Gmail batch stopped after translation failure on {batch_name}.",
                )
            self._dashboard_error_count = 1
        self._progress_done_pages = max(self._progress_done_pages, int(summary.completed_pages))
        self._progress_total_pages = max(self._progress_total_pages, self._progress_done_pages)
        self._update_live_counters()
        self._can_export_partial = summary.completed_pages > 0
        self._update_controls()

    def _on_error(self, message: str) -> None:
        gmail_batch_active = self._has_active_gmail_batch()
        gmail_batch_attachment = self._current_gmail_batch_attachment()
        self._set_busy(False, translation=False)
        self._run_started_at = None
        self._last_joblog_seed = None
        self._last_review_queue = []
        self.queue_status_label.setText("Queue: idle")
        self.status_label.setText("Error")
        self.header_status_label.setText("Error")
        self._dashboard_error_count = max(1, self._dashboard_error_count)
        self._refresh_dashboard_counters()
        self._append_log(f"Runtime error: {message}")
        if gmail_batch_active:
            batch_name = (
                gmail_batch_attachment.candidate.filename
                if gmail_batch_attachment is not None
                else "the current attachment"
            )
            self._stop_gmail_batch(
                status_text="Gmail batch stopped",
                header_status_text="Gmail batch stopped",
                log_message=f"Gmail batch stopped after runtime error on {batch_name}.",
            )
        QMessageBox.critical(self, "Runtime error", message)

    def _on_analyze_finished(self, summary_obj: object) -> None:
        self._set_busy(False, translation=False)
        self._run_started_at = None
        if not isinstance(summary_obj, AnalyzeSummary):
            self.status_label.setText("Analyze failed")
            self.header_status_label.setText("Analyze failed")
            QMessageBox.critical(self, "Analyze failed", "Invalid analyze response.")
            self._update_controls()
            return
        summary = summary_obj
        self._last_review_queue = []
        self.status_label.setText("Analyze complete")
        self.header_status_label.setText("Analyze complete")
        self._append_log(
            "Analyze complete: "
            f"selected_pages={summary.selected_pages_count}, "
            f"would_attach_images={summary.pages_would_attach_images}"
        )
        self._append_log(f"Analyze report: {summary.analyze_report_path}")
        advisor_recommendation = _load_advisor_recommendation(summary.analyze_report_path)
        self._set_advisor_recommendation(advisor_recommendation)
        advisor_message = "none"
        if advisor_recommendation is not None:
            advisor_message = (
                f"OCR={advisor_recommendation.get('recommended_ocr_mode', 'auto')}, "
                f"Images={advisor_recommendation.get('recommended_image_mode', 'auto')}"
            )
            self._append_log(f"Advisor recommendation ready: {advisor_message}")
        self._progress_done_pages = 0
        self._progress_total_pages = int(summary.selected_pages_count)
        self._dashboard_snapshot.pages_done = 0
        self._dashboard_snapshot.pages_total = int(summary.selected_pages_count)
        self._dashboard_snapshot.current_task = "Analyze complete"
        self._update_live_counters()
        QMessageBox.information(
            self,
            "Analyze complete",
            "Analyze-only finished.\n\n"
            f"Selected pages: {summary.selected_pages_count}\n"
            f"Would attach images: {summary.pages_would_attach_images}\n"
            f"Advisor recommendation: {advisor_message}\n"
            f"Report: {summary.analyze_report_path}",
        )
        self._update_controls()

    def _on_analyze_error(self, message: str) -> None:
        self._set_busy(False, translation=False)
        self._run_started_at = None
        self._set_advisor_recommendation(None)
        self._last_review_queue = []
        self.queue_status_label.setText("Queue: idle")
        self.status_label.setText("Analyze failed")
        self.header_status_label.setText("Analyze failed")
        self._dashboard_error_count = max(1, self._dashboard_error_count)
        self._refresh_dashboard_counters()
        self._append_log(f"Analyze failed: {message}")
        QMessageBox.critical(self, "Analyze failed", message)

    def _dispatch_cancel(self) -> None:
        if self._worker is None:
            return
        cancel_cb = getattr(self._worker, "cancel", None)
        if callable(cancel_cb):
            cancel_cb()

    def _begin_cancel_wait(self) -> None:
        if not self._running:
            return
        self._cancel_pending = True
        self._cancel_wait_started_at = time.perf_counter()
        self._append_log("Cancellation requested. Waiting for the current request to finish or time out.")
        self._refresh_cancel_wait_status()
        self._cancel_wait_timer.start()
        self._refresh_dashboard_counters()
        self._update_controls()
        self.request_cancel.emit()

    def _resolve_busy_close_choice(self) -> str:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Run in progress")
        box.setText("A task is still running.")
        box.setInformativeText(
            "Choose how to close the app.\n\n"
            "Keep running: leave the task active.\n"
            "Cancel and wait: request cancellation and wait for the current request to finish or time out.\n"
            "Force close: terminate the app immediately and abandon the in-flight request."
        )
        keep_btn = box.addButton("Keep running", QMessageBox.ButtonRole.RejectRole)
        cancel_wait_btn = box.addButton("Cancel and wait", QMessageBox.ButtonRole.ActionRole)
        force_btn = box.addButton("Force close", QMessageBox.ButtonRole.DestructiveRole)
        box.setDefaultButton(cancel_wait_btn)  # type: ignore[arg-type]
        box.exec()
        clicked = box.clickedButton()
        if clicked is cancel_wait_btn:
            return "cancel_wait"
        if clicked is force_btn:
            return "force_close"
        return "keep_running"

    def _force_exit_app(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.quit()
        os._exit(0)

    def _ocr_heavy_safe_profile_lines(self) -> list[str]:
        return [
            "OCR mode = always",
            "OCR engine = api",
            "Image mode = off",
            "Workers = 1",
            "Effort policy = fixed_high",
            "Resume = off",
            "Keep intermediates = on",
        ]

    def _ocr_heavy_risk_notes(self, config: RunConfig) -> list[str]:
        notes: list[str] = []
        if config.ocr_engine != OcrEnginePolicy.API:
            notes.append(f"OCR engine is '{config.ocr_engine.value}', not 'api'.")
        if config.image_mode != ImageMode.OFF:
            notes.append(f"Image mode is '{config.image_mode.value}'; OCR-success text pages should usually stay text-only.")
        if config.effort_policy == EffortPolicy.FIXED_XHIGH:
            notes.append("Effort policy is 'fixed_xhigh', which increases latency and cost on OCR-heavy documents.")
        if config.workers > 1:
            notes.append(f"Parallel workers is {config.workers}; unstable OCR-heavy runs should use 1.")
        if config.resume:
            notes.append("Resume is on; use off while triaging unstable OCR-heavy runs.")
        if not config.keep_intermediates:
            notes.append("Keep intermediates is off; use on so partial artifacts survive a stop.")
        return notes

    def _show_ocr_heavy_runtime_warning(self, config: RunConfig) -> str:
        risk_notes = self._ocr_heavy_risk_notes(config)
        safer_profile = "\n".join(f"- {line}" for line in self._ocr_heavy_safe_profile_lines())
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("OCR-heavy runtime warning")
        box.setText("Local OCR is unavailable and this document appears OCR-heavy.")
        informative_lines = [
            "This run will rely on API OCR only.",
        ]
        if risk_notes:
            informative_lines.append("Current settings that increase timeout/stall risk:")
            informative_lines.extend(f"- {note}" for note in risk_notes)
        informative_lines.append("")
        informative_lines.append("Safer profile for this document:")
        informative_lines.extend(safer_profile.splitlines())
        box.setInformativeText("\n".join(informative_lines))
        apply_btn = box.addButton("Apply safe OCR profile", QMessageBox.ButtonRole.ActionRole)
        continue_btn = box.addButton("Continue anyway", QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(apply_btn)  # type: ignore[arg-type]
        box.exec()
        clicked = box.clickedButton()
        if clicked is apply_btn:
            return "apply_safe"
        if clicked is continue_btn:
            return "continue"
        return "cancel"

    def _warn_ocr_api_only_if_needed(
        self,
        config: RunConfig,
        *,
        rebuild_config: Callable[[], RunConfig] | None = None,
    ) -> RunConfig | None:
        if config.ocr_mode == OcrMode.OFF:
            return config
        if which("tesseract"):
            return config
        page_index = max(0, int(config.start_page) - 1)
        try:
            ordered = extract_ordered_page_text(config.pdf_path, page_index)
        except Exception:
            return config
        extracted_text = (ordered.text or "").strip()
        likely_ocr_heavy = ordered.extraction_failed or len(extracted_text) < 24
        if not likely_ocr_heavy:
            return config

        warning_key = (
            str(config.pdf_path),
            int(config.start_page),
            config.ocr_mode.value,
            config.ocr_engine.value,
            config.image_mode.value,
            config.effort_policy.value,
            int(config.workers),
            bool(config.resume),
            bool(config.keep_intermediates),
        )
        if warning_key in self._ocr_dependency_warning_seen:
            return config

        decision = self._show_ocr_heavy_runtime_warning(config)
        if decision == "apply_safe":
            self._apply_transient_ocr_heavy_safe_profile()
            try:
                config = (
                    rebuild_config()
                    if callable(rebuild_config)
                    else self._build_config()
                )
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "Invalid configuration", str(exc))
                return None
            self._append_log("OCR warning: applied the OCR-heavy safe profile for this run only.")
            self._ocr_dependency_warning_seen.add(warning_key)
            return config
        if decision == "continue":
            risk_notes = self._ocr_heavy_risk_notes(config)
            risk_suffix = f" Risks: {'; '.join(risk_notes)}" if risk_notes else ""
            self._append_log(
                "OCR warning: local OCR unavailable; this OCR-heavy run will rely on API OCR only."
                f"{risk_suffix}"
            )
            self._ocr_dependency_warning_seen.add(warning_key)
            return config
        self._append_log("OCR warning: user canceled run start.")
        return None

    def _cancel(self) -> None:
        if self._running:
            self._begin_cancel_wait()

    def _cleanup_worker(self) -> None:
        callback = self._after_worker_cleanup
        self._after_worker_cleanup = None
        if self._worker is not None:
            cancel_cb = getattr(self._worker, "cancel", None)
            if callable(cancel_cb):
                try:
                    self.request_cancel.disconnect(cancel_cb)
                except Exception:
                    pass
            self._worker.deleteLater()
            self._worker = None
        if self._worker_thread is not None:
            self._worker_thread.deleteLater()
            self._worker_thread = None
        if callback is not None:
            callback()

    def _new_run(self) -> None:
        if self._busy:
            return
        if self._review_queue_dialog is not None and self._review_queue_dialog.isVisible():
            self._review_queue_dialog.close()
            self._review_queue_dialog = None
        gmail_batch_review_dialog = getattr(self, "_gmail_batch_review_dialog", None)
        if gmail_batch_review_dialog is not None and gmail_batch_review_dialog.isVisible():
            gmail_batch_review_dialog.close()
            self._gmail_batch_review_dialog = None
        clear_gmail_batch_session = getattr(self, "_clear_gmail_batch_session", None)
        if callable(clear_gmail_batch_session):
            clear_gmail_batch_session()
        self._last_summary = None
        self._last_run_report_path = None
        self._last_queue_summary_path = None
        self._last_run_dir = None
        self._last_output_docx = None
        self._last_run_config = None
        self._last_joblog_seed = None
        self._last_review_queue = []
        self._last_gmail_message_load_result = None
        self._queue_status_rows = []
        self._queue_total_jobs = 0
        self._queue_status_by_job_id = {}
        self._advisor_recommendation = None
        self._advisor_recommendation_applied = None
        self._advisor_override_ocr_mode = None
        self._advisor_override_image_mode = None
        self._last_workflow = None
        self._worker = None
        self._worker_thread = None
        self._after_worker_cleanup = None
        self._can_export_partial = False
        self._dashboard_error_count = 0
        self._dashboard_error_retry_count = 0
        self._dashboard_eta_text = "--"
        self._run_started_at = None
        self.progress.setValue(0)
        self.page_label.setText("Page: -/-")
        self.status_label.setText("Idle")
        self.header_status_label.setText("Idle")
        queue_label = getattr(self, "queue_status_label", None)
        if queue_label is not None:
            queue_label.setText("Queue: idle")
        self._reset_live_counters()
        self.final_docx_edit.clear()
        self.log_text.clear()
        self.details_btn.setChecked(False)
        self._set_details_visible(False)
        refresh_advisor = getattr(self, "_refresh_advisor_banner", None)
        if callable(refresh_advisor):
            refresh_advisor()
        focus_dashboard = getattr(self, "_focus_dashboard", None)
        if callable(focus_dashboard):
            focus_dashboard()
        self._save_settings()
        self._update_controls()

    def _export_partial(self) -> None:
        wf = self._last_workflow
        if wf is None:
            QMessageBox.information(self, "Partial export", "No run context available.")
            return
        try:
            partial = wf.export_partial_docx()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Partial export failed", str(exc))
            return
        if partial is None:
            QMessageBox.information(self, "Partial export", "No completed pages available.")
            return
        self._append_log(f"Partial DOCX exported: {partial}")
        QMessageBox.information(self, "Partial export", f"Exported:\n{partial}")

    def _start_rebuild_docx(self) -> None:
        if self._busy:
            return
        try:
            config = self._build_config()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Invalid configuration", str(exc))
            return

        self._save_settings()
        if self._review_queue_dialog is not None and self._review_queue_dialog.isVisible():
            self._review_queue_dialog.close()
            self._review_queue_dialog = None
        self._clear_gmail_batch_session()
        self._last_gmail_message_load_result = None
        self._last_summary = None
        self._last_queue_summary_path = None
        self._last_run_config = config
        self._last_joblog_seed = None
        self._last_review_queue = []
        self.queue_status_label.setText("Queue: idle")
        self._set_busy(True, translation=False)
        self.status_label.setText("Rebuilding DOCX...")
        self.header_status_label.setText("Rebuilding DOCX...")
        self._dashboard_error_count = 0
        self._dashboard_error_retry_count = 0
        self._dashboard_eta_text = "--"
        self._run_started_at = time.perf_counter()

        thread = QThread(self)
        worker = RebuildDocxWorker(config=config)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.log.connect(self._append_log)
        worker.finished.connect(self._on_rebuild_finished)
        worker.error.connect(self._on_rebuild_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(self._cleanup_worker)

        self._worker_thread = thread
        self._worker = worker
        thread.start()

    def _on_rebuild_finished(self, output_obj: object) -> None:
        self._set_busy(False, translation=False)
        self._run_started_at = None
        if not isinstance(output_obj, Path):
            self.status_label.setText("Rebuild failed")
            self.header_status_label.setText("Rebuild failed")
            QMessageBox.critical(self, "Rebuild failed", "Rebuild returned an invalid output path.")
            return
        output = output_obj.expanduser().resolve()
        self._last_output_docx = output
        self._last_joblog_seed = None
        self._last_review_queue = []
        self.final_docx_edit.setText(str(output))
        self.status_label.setText("Completed")
        self.header_status_label.setText("Completed")
        self._dashboard_error_count = 0
        self._refresh_dashboard_counters()
        self._append_log(f"Saved DOCX: {output}")
        self._show_saved_docx_dialog("Rebuild complete")
        self._update_controls()

    def _on_rebuild_error(self, message: str) -> None:
        self._set_busy(False, translation=False)
        self._run_started_at = None
        self._last_review_queue = []
        self.status_label.setText("Rebuild failed")
        self.header_status_label.setText("Rebuild failed")
        self._dashboard_error_count = max(1, self._dashboard_error_count)
        self._refresh_dashboard_counters()
        self._append_log(f"Rebuild failed: {message}")
        QMessageBox.critical(self, "Rebuild failed", message)

    def _open_path_in_system(self, target: Path) -> None:
        resolved = target.expanduser().resolve()
        if not resolved.exists():
            QMessageBox.critical(self, "Open file failed", f"Path not found:\n{resolved}")
            return
        try:
            if os.name == "nt":
                os.startfile(str(resolved))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(resolved)])
            else:
                subprocess.Popen(["xdg-open", str(resolved)])
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Open file failed", str(exc))

    def _open_output_file(self) -> None:
        if self._last_output_docx is None:
            return
        output_path = self._last_output_docx.expanduser().resolve()
        if not output_path.exists():
            QMessageBox.critical(self, "Open file failed", f"Output file not found:\n{output_path}")
            return
        self._open_path_in_system(output_path)

    def _show_saved_docx_dialog(self, title: str) -> None:
        if self._last_output_docx is None:
            return
        message = f"Saved DOCX:\n{self._last_output_docx}\n\nOpen file now?"
        open_now = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if open_now == QMessageBox.StandardButton.Yes:
            self._open_output_file()

    def _open_arabic_docx_review_dialog(
        self,
        *,
        output_docx: Path,
        is_gmail_batch: bool,
        attachment_label: str | None = None,
    ) -> bool:
        dialog = QtArabicDocxReviewDialog(
            parent=self,
            docx_path=output_docx,
            is_gmail_batch=is_gmail_batch,
            attachment_label=attachment_label,
        )
        try:
            return dialog.exec() == QDialog.DialogCode.Accepted
        finally:
            dialog.deleteLater()

    def _prepare_joblog_seed(self, summary: RunSummary) -> None:
        if self._last_run_config is None:
            self._last_joblog_seed = None
            return

        settings = load_joblog_settings()
        default_rate = settings["default_rate_per_word"].get(self._last_run_config.target_lang.value, 0.0)
        try:
            seed = build_seed_from_run(
                pdf_path=self._last_run_config.pdf_path,
                lang=self._last_run_config.target_lang.value,
                output_docx=summary.output_docx,
                partial_docx=summary.partial_docx,
                pages_dir=summary.run_dir / "pages",
                completed_pages=summary.completed_pages,
                completed_at=datetime.now().isoformat(timespec="seconds"),
                default_rate_per_word=float(default_rate),
                api_cost=0.0,
            )
        except Exception as exc:  # noqa: BLE001
            self._append_log(f"Job log seed preparation failed: {exc}")
            self._last_joblog_seed = None
            return

        summary_path = summary.run_summary_path
        if summary_path is None:
            summary_path = summary.run_dir / "run_summary.json"
        metrics = _load_run_summary_metrics(summary_path.expanduser().resolve())
        run_id = str(metrics.get("run_id", "") or "").strip()
        target_lang = str(metrics.get("target_lang", "") or "").strip()
        total_tokens = _coerce_int_or_none(metrics.get("total_tokens"))
        estimated_api_cost = _coerce_float_or_none(metrics.get("estimated_api_cost"))
        quality_risk_score = _coerce_float_or_none(metrics.get("quality_risk_score"))

        seed.run_id = run_id or summary.run_dir.name
        seed.target_lang = target_lang or self._last_run_config.target_lang.value
        seed.total_tokens = total_tokens
        seed.estimated_api_cost = estimated_api_cost
        seed.quality_risk_score = quality_risk_score
        if estimated_api_cost is not None:
            seed.api_cost = float(estimated_api_cost)
            seed.profit = round(seed.expected_total - seed.api_cost, 2)

        suggestion = extract_pdf_header_metadata_priority_pages(
            seed.pdf_path,
            vocab_cities=list(settings["vocab_cities"]),
            config=metadata_config_from_settings(settings),
        )
        if suggestion.case_entity:
            seed.case_entity = suggestion.case_entity
            seed.service_entity = suggestion.case_entity
        if suggestion.case_city:
            seed.case_city = suggestion.case_city
            seed.service_city = suggestion.case_city
        if suggestion.case_number:
            seed.case_number = suggestion.case_number
        seed.court_email = choose_court_email_suggestion(
            exact_email=suggestion.court_email,
            case_entity=seed.case_entity,
            case_city=seed.case_city,
            vocab_court_emails=list(settings.get("vocab_court_emails", [])),
        ) or ""

        self._last_joblog_seed = seed

    def _open_save_to_joblog_dialog(
        self,
        *,
        allow_honorarios_export: bool = True,
    ) -> JobLogSavedResult | None:
        if self._last_joblog_seed is None:
            QMessageBox.information(self, "Job Log", "No completed run available to save.")
            return None

        def _refresh_after_save() -> None:
            if self._joblog_window is not None and self._joblog_window.isVisible():
                self._joblog_window.refresh_rows()

        dialog = QtSaveToJobLogDialog(
            parent=self,
            db_path=self._joblog_db_path,
            seed=self._last_joblog_seed,
            on_saved=_refresh_after_save,
            allow_honorarios_export=allow_honorarios_export,
        )
        dialog.exec()
        return dialog.saved_result

    def _open_joblog_window(self) -> None:
        if self._joblog_window is not None and self._joblog_window.isVisible():
            self._joblog_window.raise_()
            self._joblog_window.activateWindow()
            return
        window = QtJobLogWindow(parent=self, db_path=self._joblog_db_path)
        window.setModal(False)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        window.destroyed.connect(lambda _obj=None: setattr(self, "_joblog_window", None))
        self._joblog_window = window
        window.show()

    def _open_output_folder(self) -> None:
        target: Path | None = None
        if self._last_output_docx is not None:
            out = self._last_output_docx.expanduser().resolve()
            if out.exists():
                target = out
        if target is None:
            outdir_text = self.outdir_edit.text().strip()
            if outdir_text:
                outdir = Path(outdir_text).expanduser().resolve()
                if outdir.exists():
                    target = outdir
        if target is None:
            QMessageBox.information(self, "Open output folder", "No output folder available.")
            return
        try:
            if os.name == "nt":
                if target.is_file():
                    subprocess.Popen(["explorer", f"/select,{target}"])
                else:
                    os.startfile(str(target))  # type: ignore[attr-defined]
            elif target.is_file():
                subprocess.Popen(["xdg-open", str(target.parent)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Open output folder", str(exc))

    def _resolve_report_run_dir(self) -> Path | None:
        if self._last_run_dir is not None:
            return self._last_run_dir.expanduser().resolve()
        if self._last_summary is not None:
            return self._last_summary.run_dir.expanduser().resolve()
        if self._last_run_report_path is not None:
            return self._last_run_report_path.expanduser().resolve().parent
        if self._worker is not None and hasattr(self._worker, "workflow"):
            workflow = getattr(self._worker, "workflow", None)
            if workflow is not None and hasattr(workflow, "_last_paths"):
                paths = getattr(workflow, "_last_paths", None)
                run_dir = getattr(paths, "run_dir", None)
                if isinstance(run_dir, Path):
                    return run_dir.expanduser().resolve()
        return None

    def _open_review_queue_dialog(self) -> None:
        if self._review_queue_dialog is not None and self._review_queue_dialog.isVisible():
            self._review_queue_dialog.raise_()
            self._review_queue_dialog.activateWindow()
            return
        run_dir = self._resolve_report_run_dir()
        if run_dir is None:
            QMessageBox.information(self, "Review Queue", "No run context available.")
            return
        summary_path: Path | None = None
        if self._last_summary is not None and self._last_summary.run_summary_path is not None:
            summary_path = self._last_summary.run_summary_path.expanduser().resolve()
        elif self._last_run_report_path is not None:
            summary_path = self._last_run_report_path.expanduser().resolve()
        else:
            fallback = run_dir / "run_summary.json"
            summary_path = fallback if fallback.exists() else None

        review_entries = list(self._last_review_queue)
        if summary_path is not None:
            review_entries = _load_review_queue_entries(summary_path)
            self._last_review_queue = list(review_entries)

        dialog = QtReviewQueueDialog(
            parent=self,
            review_queue=review_entries,
            run_dir=run_dir,
            run_summary_path=summary_path,
            open_path_callback=self._open_path_in_system,
        )
        dialog.setModal(False)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda _obj=None: setattr(self, "_review_queue_dialog", None))
        self._review_queue_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _open_run_report(self) -> None:
        run_dir = self._resolve_report_run_dir()
        if run_dir is None:
            QMessageBox.information(self, "Run report", "No run report available.")
            return
        if not run_dir.exists():
            QMessageBox.information(self, "Run report", f"Run folder is not ready yet:\n{run_dir}")
            return

        admin_mode = bool(self._defaults.get("diagnostics_admin_mode", True))
        include_snippets = (
            admin_mode and bool(self._defaults.get("diagnostics_include_sanitized_snippets", False))
        )
        try:
            report_text = build_run_report_markdown(
                run_dir=run_dir,
                admin_mode=admin_mode,
                include_sanitized_snippets=include_snippets,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Run report", str(exc))
            return

        chooser = QMessageBox(self)
        chooser.setIcon(QMessageBox.Icon.Question)
        chooser.setWindowTitle("Export Run Report")
        chooser.setText("Choose how to export the run report.")
        save_btn = chooser.addButton("Save .md", QMessageBox.ButtonRole.ActionRole)
        copy_btn = chooser.addButton("Copy to clipboard", QMessageBox.ButtonRole.ActionRole)
        chooser.addButton(QMessageBox.StandardButton.Cancel)
        chooser.exec()
        clicked = chooser.clickedButton()

        if clicked is copy_btn:
            QApplication.clipboard().setText(report_text)
            self._append_log("Run report copied to clipboard.")
            QMessageBox.information(self, "Run report", "Run report copied to clipboard.")
            return

        if clicked is not save_btn:
            return

        default_path = run_dir / "run_report.md"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Run Report",
            str(default_path),
            "Markdown (*.md);;Text (*.txt);;All Files (*.*)",
        )
        if not save_path:
            return
        output_path = Path(save_path).expanduser().resolve()
        try:
            output_path.write_text(report_text, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Run report", f"Failed to save run report: {exc}")
            return
        self._append_log(f"Run report exported: {output_path}")
        open_choice = QMessageBox.question(
            self,
            "Run report",
            "Open report folder now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if open_choice != QMessageBox.StandardButton.Yes:
            return
        try:
            if os.name == "nt":
                subprocess.Popen(["explorer", f"/select,{output_path}"])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(output_path.parent)])
            else:
                subprocess.Popen(["xdg-open", str(output_path.parent)])
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Run report", str(exc))

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if self._click_debug_enabled:
            global_point = event.globalPosition().toPoint()
            target = QApplication.widgetAt(global_point)
            if target is None:
                self._append_log("[click-debug] widgetAt=None")
            else:
                object_name = target.objectName().strip() or "-"
                self._append_log(f"[click-debug] widgetAt={target.__class__.__name__} objectName={object_name}")
        super().mousePressEvent(event)

    def _update_card_max_width(self, *, viewport_width: int | None = None) -> None:
        vp = self._scroll_area.viewport()
        resolved_viewport_width = viewport_width if viewport_width is not None else (vp.width() if vp is not None else self.width())
        self._apply_responsive_layout(viewport_width=resolved_viewport_width)
        scroll_layout = self._scroll_area.widget().layout()
        lr = scroll_layout.contentsMargins()
        available = max(360, resolved_viewport_width - lr.left() - lr.right())
        target_width = max(360, min(1760, available))
        self.content_card.setFixedWidth(target_width)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._update_card_max_width()
        central = self.centralWidget()
        if central is not None:
            central.update()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if self._initial_resize_done:
            return
        self._initial_resize_done = True
        screen = self.screen()
        if screen is None:
            from PySide6.QtGui import QGuiApplication
            screen = QGuiApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            w = int(avail.width() * 0.94)
            h = int(avail.height() * 0.93)
            self.resize(w, h)
            self.move(
                avail.x() + (avail.width() - w) // 2,
                avail.y() + (avail.height() - h) // 2,
            )

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._busy:
            choice = self._resolve_busy_close_choice()
            if choice == "cancel_wait":
                self._begin_cancel_wait()
                event.ignore()
                return
            if choice == "force_close":
                if self._settings_save_timer.isActive():
                    self._settings_save_timer.stop()
                if self._settings_dialog is not None and self._settings_dialog.isVisible():
                    self._settings_dialog.close()
                self._save_settings()
                self._append_log("Force close requested while a task was still running.")
                if self._gmail_batch_review_dialog is not None and self._gmail_batch_review_dialog.isVisible():
                    self._gmail_batch_review_dialog.close()
                self._clear_gmail_batch_session()
                self._stop_gmail_intake_bridge()
                event.accept()
                self._force_exit_app()
                return
            event.ignore()
            return
        if self._settings_save_timer.isActive():
            self._settings_save_timer.stop()
        if self._settings_dialog is not None and self._settings_dialog.isVisible():
            self._settings_dialog.close()
        if self._gmail_batch_review_dialog is not None and self._gmail_batch_review_dialog.isVisible():
            self._gmail_batch_review_dialog.close()
        self._save_settings()
        self._clear_gmail_batch_session()
        self._stop_gmail_intake_bridge()
        super().closeEvent(event)
