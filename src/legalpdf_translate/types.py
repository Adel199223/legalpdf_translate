"""Shared types for workflow and frontends."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class TargetLang(str, Enum):
    EN = "EN"
    FR = "FR"
    AR = "AR"


class ReasoningEffort(str, Enum):
    HIGH = "high"
    XHIGH = "xhigh"
    MEDIUM = "medium"


class ImageMode(str, Enum):
    OFF = "off"
    AUTO = "auto"
    ALWAYS = "always"


class OcrMode(str, Enum):
    OFF = "off"
    AUTO = "auto"
    ALWAYS = "always"


class OcrEnginePolicy(str, Enum):
    LOCAL = "local"
    LOCAL_THEN_API = "local_then_api"
    API = "api"


class ApiKeySource(str, Enum):
    ENV = "env"
    CREDMAN = "credman"
    INLINE = "inline"


class PageStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


@dataclass(slots=True)
class RunConfig:
    pdf_path: Path
    output_dir: Path
    target_lang: TargetLang
    effort: ReasoningEffort = ReasoningEffort.HIGH
    image_mode: ImageMode = ImageMode.AUTO
    start_page: int = 1
    end_page: int | None = None
    max_pages: int | None = None
    workers: int = 3
    resume: bool = True
    page_breaks: bool = True
    keep_intermediates: bool = True
    ocr_mode: OcrMode = OcrMode.AUTO
    ocr_engine: OcrEnginePolicy = OcrEnginePolicy.LOCAL_THEN_API
    ocr_api_base_url: str | None = None
    ocr_api_model: str | None = None
    ocr_api_key_env_name: str = "DEEPSEEK_API_KEY"
    context_file: Path | None = None
    context_text: str | None = None


@dataclass(slots=True)
class PageResult:
    page_number: int
    status: PageStatus
    image_used: bool = False
    retry_used: bool = False
    usage: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    output_file: Path | None = None


@dataclass(slots=True)
class RunState:
    version: int
    pdf_path: str
    pdf_fingerprint: str
    lang: str
    total_pages: int
    max_pages_effective: int
    selection_start_page: int
    selection_end_page: int
    selection_page_count: int
    settings: dict[str, Any]
    context_hash: str
    created_at: str
    updated_at: str
    frozen_outdir_abs: str
    run_dir_abs: str
    run_status: str
    halt_reason: str | None
    final_docx_path_abs: str | None
    run_started_at: str
    finished_at: str | None
    pages: dict[str, dict[str, Any]]
    last_completed_page: int
    done_count: int
    failed_count: int
    pending_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "pdf_path": self.pdf_path,
            "pdf_fingerprint": self.pdf_fingerprint,
            "lang": self.lang,
            "total_pages": self.total_pages,
            "max_pages_effective": self.max_pages_effective,
            "selection_start_page": self.selection_start_page,
            "selection_end_page": self.selection_end_page,
            "selection_page_count": self.selection_page_count,
            "settings": self.settings,
            "context_hash": self.context_hash,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "frozen_outdir_abs": self.frozen_outdir_abs,
            "run_dir_abs": self.run_dir_abs,
            "run_status": self.run_status,
            "halt_reason": self.halt_reason,
            "final_docx_path_abs": self.final_docx_path_abs,
            "run_started_at": self.run_started_at,
            "finished_at": self.finished_at,
            "pages": self.pages,
            "last_completed_page": self.last_completed_page,
            "done_count": self.done_count,
            "failed_count": self.failed_count,
            "pending_count": self.pending_count,
        }


@dataclass(slots=True)
class RunSummary:
    success: bool
    exit_code: int
    output_docx: Path | None
    partial_docx: Path | None
    run_dir: Path
    completed_pages: int
    failed_page: int | None
    error: str | None = None
    attempted_output_docx: Path | None = None
    run_summary_path: Path | None = None


@dataclass(slots=True)
class AnalyzeSummary:
    run_dir: Path
    analyze_report_path: Path
    selected_pages_count: int
    pages_would_attach_images: int
